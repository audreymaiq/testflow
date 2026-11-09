"""Deterministic PageSchema v1 to ExamDraft v1 assembly.

This accepts validated page output, never infers absent exam metadata or answers,
and reports content that the v1 draft cannot represent without loss.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from testflow_contracts.exam import ExamDraft, Metadata, QuestionDraft
from testflow_contracts.page import (
    AnswerKeyBlock,
    PageSchema,
    PassageBlock,
    QuestionBlock,
    SectionHeading,
)


@dataclass(frozen=True)
class AssemblyIssue:
    page_no: int
    code: str
    message: str
    severity: Literal["ERROR", "WARNING"] = "ERROR"


@dataclass(frozen=True)
class AssemblyOutcome:
    draft: ExamDraft
    issues: tuple[AssemblyIssue, ...]
    valid: int
    skipped: int


_QUESTION_NUMBER = re.compile(r"^(?:(?:câu|cau|question|q)\s*\.?\s*)?(\d+)\s*[.:]?$", re.I)


def _number_key(label: str) -> str:
    compact = " ".join(label.casefold().split())
    match = _QUESTION_NUMBER.fullmatch(compact)
    return f"#{int(match.group(1))}" if match else compact


def _missing_key(question: dict) -> bool:
    kind = question["kind"]
    if kind in {"MCQ", "MCQ_MULTI"}:
        return not any(choice.get("is_correct") for choice in question["choices"])
    if kind == "TRUE_FALSE":
        return question.get("tf_answer") is None
    if kind == "SHORT":
        return not bool(question.get("short_answer"))
    if kind == "TF_GROUP":
        return not all(item.get("is_true") is not None for item in question["statements"])
    return False


def _merge_continuation(first: QuestionBlock, second: QuestionBlock) -> QuestionBlock:
    if first.kind != second.kind or (
        first.number_label
        and second.number_label
        and _number_key(first.number_label) != _number_key(second.number_label)
    ):
        raise ValueError("continuation kind or number mismatch")
    if first.passage_ref and second.passage_ref and first.passage_ref != second.passage_ref:
        raise ValueError("continuation passage mismatch")

    def merge_labeled(left, right):
        values = [item.model_dump() for item in left]
        by_label = {item["label"]: item for item in values}
        for item in right:
            if item.label in by_label:
                existing = by_label[item.label]
                existing["text"] = f"{existing['text'].rstrip()} {item.text.lstrip()}".strip()
            else:
                added = item.model_dump()
                values.append(added)
                by_label[item.label] = added
        return values

    return QuestionBlock.model_validate(
        {
            **first.model_dump(),
            "number_label": first.number_label or second.number_label,
            "text": f"{first.text.rstrip()} {second.text.lstrip()}".strip(),
            "choices": merge_labeled(first.choices, second.choices),
            "statements": merge_labeled(first.statements, second.statements),
            "figure_refs": list(dict.fromkeys([*first.figure_refs, *second.figure_refs])),
            "passage_ref": first.passage_ref or second.passage_ref,
            "continues_from_previous": False,
            "continues_on_next": second.continues_on_next,
        }
    )


def assemble_pages(pages: Sequence[PageSchema]) -> AssemblyOutcome:
    """Build a reviewable draft from page blocks in physical page order.

    Unsupported continuations, passages and figures are explicit errors, so a
    caller must not confirm a lossy draft. No model or database access occurs.
    """
    ordered = sorted(pages, key=lambda page: page.page_no)
    numbers = [page.page_no for page in ordered]
    if len(numbers) != len(set(numbers)):
        raise ValueError("page numbers must be unique")

    issues: list[AssemblyIssue] = []
    metadata: dict = {}
    conflicted_fields: set[str] = set()
    sections: list[dict] = []
    current: dict | None = None
    answer_entries: list[tuple[int, str, str]] = []
    question_index: dict[str, list[tuple[dict, int]]] = {}
    passages_by_id: dict[str, list[tuple[dict, str]]] = {}
    pending: tuple[QuestionBlock, int, int, dict] | None = None
    skipped = 0
    question_serial = 0

    def issue(page_no: int, code: str, message: str, *, warning: bool = False) -> None:
        issues.append(AssemblyIssue(page_no, code, message, "WARNING" if warning else "ERROR"))

    def section(title: str = "Câu hỏi") -> dict:
        nonlocal current
        if current is None:
            current = {"title": title, "passages": [], "questions": []}
            sections.append(current)
        return current

    for page in ordered:
        if pending is not None and page.page_no != pending[2] + 1:
            issue(pending[1], "E_CONTINUATION_UNMATCHED", "Câu qua trang không có phần tiếp theo.")
            skipped += 1
            pending = None
        if page.page_no > 1 and page.page_no - 1 not in numbers:
            issue(page.page_no, "E_PAGE_GAP", "Thiếu trang trước trang này.")
        header = page.header
        for field in ("title", "subject", "year", "duration_minutes"):
            value = getattr(header, field)
            if value is None or value == "":
                continue
            if field in conflicted_fields:
                continue
            if field not in metadata:
                try:
                    Metadata.model_validate({field: value})
                except ValueError:
                    issue(
                        page.page_no,
                        "W_HEADER_INVALID",
                        f"Thông tin {field} cần kiểm tra.",
                        warning=True,
                    )
                    continue
                metadata[field] = value
            elif metadata[field] != value:
                metadata.pop(field)
                conflicted_fields.add(field)
                issue(
                    page.page_no,
                    "E_HEADER_CONFLICT",
                    f"Thông tin {field} không thống nhất giữa các trang.",
                )
        if header.school and "schools" not in conflicted_fields:
            if "schools" not in metadata:
                metadata["schools"] = [header.school]
            elif metadata["schools"] != [header.school]:
                metadata.pop("schools")
                conflicted_fields.add("schools")
                issue(
                    page.page_no,
                    "E_HEADER_CONFLICT",
                    "Tên trường không thống nhất giữa các trang.",
                )

        for block in page.blocks:
            if isinstance(block, SectionHeading):
                if pending is not None:
                    issue(
                        pending[1], "E_CONTINUATION_UNMATCHED", "Câu qua trang đổi phần đột ngột."
                    )
                    skipped += 1
                    pending = None
                if current is not None and not current["questions"] and not current["passages"]:
                    current["title"] = block.text
                else:
                    current = None
                    section(block.text)
            elif isinstance(block, PassageBlock):
                group = section()
                passage_id = f"page-{page.page_no}-passage-{block.id}"
                group["passages"].append(
                    {"tmp_id": passage_id, "order": len(group["passages"]) + 1, "text": block.text}
                )
                passages_by_id.setdefault(block.id, []).append((group, passage_id))
            elif isinstance(block, AnswerKeyBlock):
                answer_entries.extend(
                    (page.page_no, entry.number_label, entry.answer) for entry in block.entries
                )
            elif isinstance(block, QuestionBlock):
                source_page_no = page.page_no
                continuation_group = None
                if block.continues_from_previous:
                    if pending is None or pending[2] + 1 != page.page_no:
                        issue(
                            page.page_no,
                            "E_CONTINUATION_UNMATCHED",
                            "Phần tiếp của câu không có trang trước phù hợp.",
                        )
                        skipped += 1
                        continue
                    first, source_page_no, _, continuation_group = pending
                    pending = None
                    try:
                        block = _merge_continuation(first, block)
                    except ValueError:
                        issue(
                            page.page_no,
                            "E_CONTINUATION_UNMATCHED",
                            "Hai phần của câu qua trang không khớp.",
                        )
                        skipped += 1
                        continue
                elif pending is not None:
                    issue(
                        pending[1],
                        "E_CONTINUATION_UNMATCHED",
                        "Câu qua trang không có phần tiếp theo.",
                    )
                    skipped += 1
                    pending = None
                if block.continues_on_next:
                    pending = (block, source_page_no, page.page_no, continuation_group or section())
                    continue
                if block.figure_refs:
                    issue(
                        page.page_no, "E_FIGURE_UNSUPPORTED", "Câu có hình cần được gắn thủ công."
                    )
                    skipped += 1
                    continue
                group = continuation_group or section()
                passage_ref = None
                if block.passage_ref:
                    passage_matches = [
                        passage_id
                        for passage_group, passage_id in passages_by_id.get(block.passage_ref, [])
                        if passage_group is group
                    ]
                    if len(passage_matches) != 1:
                        issue(
                            page.page_no,
                            "E_PASSAGE_UNMATCHED",
                            "Không ghép được câu hỏi với đúng một đoạn văn trong phần này.",
                        )
                        skipped += 1
                        continue
                    passage_ref = passage_matches[0]
                question_serial += 1
                candidate = {
                    "tmp_id": f"page-{source_page_no}-q-{question_serial}",
                    "order": len(group["questions"]) + 1,
                    "number_label": block.number_label,
                    "kind": block.kind,
                    "text": block.text,
                    "passage_ref": passage_ref,
                    "choices": [
                        {"label": choice.label, "text": choice.text} for choice in block.choices
                    ],
                    "statements": [
                        {"label": statement.label, "text": statement.text}
                        for statement in block.statements
                    ],
                    "provenance": {"kind": "page", "page_no": source_page_no},
                }
                try:
                    QuestionDraft.model_validate(candidate)
                except ValueError:
                    issue(page.page_no, "E_QUESTION_INVALID", "Câu hỏi hoặc lựa chọn chưa hợp lệ.")
                    skipped += 1
                    continue
                group["questions"].append(candidate)
                if block.number_label:
                    question_index.setdefault(_number_key(block.number_label), []).append(
                        (candidate, page.page_no)
                    )
        if page.figures:
            issue(
                page.page_no, "E_FIGURE_UNSUPPORTED", "Hình trên trang chưa được đưa vào bản nháp."
            )

    if pending is not None:
        issue(pending[1], "E_CONTINUATION_UNMATCHED", "Câu qua trang không có phần tiếp theo.")
        skipped += 1

    for page_no, label, answer in answer_entries:
        matches = question_index.get(_number_key(label), [])
        if len(matches) != 1:
            issue(
                page_no,
                "E_ANSWER_UNMATCHED",
                f"Không ghép được đáp án cho {label} vào đúng một câu.",
            )
            continue
        question, _ = matches[0]
        value = answer.strip().upper()
        if question["kind"] in {"MCQ", "MCQ_MULTI"}:
            labels = [part.strip() for part in value.split(",")]
            available = {choice["label"] for choice in question["choices"]}
            if (
                not labels
                or len(set(labels)) != len(labels)
                or not set(labels) <= available
                or (question["kind"] == "MCQ" and len(labels) != 1)
            ):
                issue(page_no, "E_ANSWER_INVALID", f"Đáp án {label} không khớp lựa chọn.")
                continue
            if any(choice.get("is_correct") for choice in question["choices"]):
                issue(page_no, "E_ANSWER_CONFLICT", f"Có nhiều đáp án cho {label}.")
                continue
            for choice in question["choices"]:
                choice["is_correct"] = choice["label"] in labels
        elif question["kind"] == "TRUE_FALSE" and value in {"T", "F"}:
            if question.get("tf_answer") is not None:
                issue(page_no, "E_ANSWER_CONFLICT", f"Có nhiều đáp án cho {label}.")
            else:
                question["tf_answer"] = value == "T"
        elif question["kind"] == "SHORT" and answer.strip():
            if question.get("short_answer"):
                issue(page_no, "E_ANSWER_CONFLICT", f"Có nhiều đáp án cho {label}.")
            else:
                question["short_answer"] = answer.strip()
        else:
            issue(page_no, "E_ANSWER_UNSUPPORTED", f"Đáp án {label} cần được kiểm tra thủ công.")

    if not any(group["questions"] for group in sections):
        issue(numbers[0] if numbers else 0, "E_NO_QUESTIONS", "Không nhận được câu hỏi nào.")
    else:
        issue(
            numbers[0],
            "W_SCORING_REVIEW",
            "Cần kiểm tra thang điểm trước khi lưu đề.",
            warning=True,
        )
        unanswered = sum(
            _missing_key(question) for group in sections for question in group["questions"]
        )
        if unanswered:
            issue(numbers[0], "W_NO_ANSWER_KEY", f"{unanswered} câu chưa có đáp án.", warning=True)

    for group in sections:
        referenced = {question.get("passage_ref") for question in group["questions"]}
        if any(passage["tmp_id"] not in referenced for passage in group["passages"]):
            issue(numbers[0] if numbers else 0, "E_PASSAGE_UNANCHORED", "Đoạn văn chưa có câu hỏi.")
    complete_sections = [group for group in sections if group["questions"]]
    draft = ExamDraft.model_validate(
        {
            "schema_version": 1,
            "metadata": metadata,
            "sections": [
                {
                    "order": index,
                    "title": group["title"],
                    "kind": "MIXED",
                    "scoring": {"type": "per_question", "points": "1"},
                    "passages": group["passages"],
                    "questions": group["questions"],
                }
                for index, group in enumerate(complete_sections, start=1)
            ],
        }
    )
    return AssemblyOutcome(
        draft, tuple(issues), sum(len(group["questions"]) for group in sections), skipped
    )
