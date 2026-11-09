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
    sections: list[dict] = []
    current: dict | None = None
    answer_entries: list[tuple[int, str, str]] = []
    question_index: dict[str, list[tuple[dict, int]]] = {}
    skipped = 0
    question_serial = 0

    def issue(page_no: int, code: str, message: str, *, warning: bool = False) -> None:
        issues.append(AssemblyIssue(page_no, code, message, "WARNING" if warning else "ERROR"))

    def section(title: str = "Câu hỏi") -> dict:
        nonlocal current
        if current is None:
            current = {"title": title, "questions": []}
            sections.append(current)
        return current

    for page in ordered:
        if page.page_no > 1 and page.page_no - 1 not in numbers:
            issue(page.page_no, "E_PAGE_GAP", "Thiếu trang trước trang này.")
        header = page.header
        for field in ("title", "subject", "year", "duration_minutes"):
            value = getattr(header, field)
            if value is None or value == "":
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
                issue(
                    page.page_no,
                    "W_HEADER_CONFLICT",
                    f"Thông tin {field} không thống nhất giữa các trang.",
                    warning=True,
                )
        if header.school:
            if "schools" not in metadata:
                metadata["schools"] = [header.school]
            elif metadata["schools"] != [header.school]:
                issue(
                    page.page_no,
                    "W_HEADER_CONFLICT",
                    "Tên trường không thống nhất giữa các trang.",
                    warning=True,
                )

        for block in page.blocks:
            if isinstance(block, SectionHeading):
                if current is not None and not current["questions"]:
                    current["title"] = block.text
                else:
                    current = None
                    section(block.text)
            elif isinstance(block, PassageBlock):
                issue(
                    page.page_no, "E_PASSAGE_UNSUPPORTED", "Đoạn văn chung cần được gắn thủ công."
                )
            elif isinstance(block, AnswerKeyBlock):
                answer_entries.extend(
                    (page.page_no, entry.number_label, entry.answer) for entry in block.entries
                )
            elif isinstance(block, QuestionBlock):
                if block.continues_from_previous or block.continues_on_next:
                    issue(
                        page.page_no,
                        "E_CONTINUATION_UNSUPPORTED",
                        "Câu qua trang cần được ghép thủ công.",
                    )
                    skipped += 1
                    continue
                if block.figure_refs:
                    issue(
                        page.page_no, "E_FIGURE_UNSUPPORTED", "Câu có hình cần được gắn thủ công."
                    )
                    skipped += 1
                    continue
                if block.passage_ref:
                    issue(
                        page.page_no,
                        "E_PASSAGE_UNSUPPORTED",
                        "Câu thuộc đoạn văn chung cần được gắn thủ công.",
                    )
                    skipped += 1
                    continue
                group = section()
                question_serial += 1
                candidate = {
                    "tmp_id": f"page-{page.page_no}-q-{question_serial}",
                    "order": len(group["questions"]) + 1,
                    "number_label": block.number_label,
                    "kind": block.kind,
                    "text": block.text,
                    "choices": [
                        {"label": choice.label, "text": choice.text} for choice in block.choices
                    ],
                    "statements": [
                        {"label": statement.label, "text": statement.text}
                        for statement in block.statements
                    ],
                    "provenance": {"kind": "page", "page_no": page.page_no},
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
                    "questions": group["questions"],
                }
                for index, group in enumerate(complete_sections, start=1)
            ],
        }
    )
    return AssemblyOutcome(
        draft, tuple(issues), sum(len(group["questions"]) for group in sections), skipped
    )
