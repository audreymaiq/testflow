"""Pure, finite-state Quiz Rush v1 and extended v2 TXT parser."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from testflow_contracts.exam import ExamDraft, Metadata, QuestionDraft

MAX_BYTES = 2 * 1024 * 1024
MAX_LINES = 20_000
CHAPTER_COLORS = ("#3B66A5", "#A56736", "#925472", "#6552A0")
OPTION = re.compile(r"^([A-Fa-f])\.\s*(.+)$")
CHAPTER = re.compile(r"^\[([^\]]+)\]\s*(.*)$")
State = Literal["HEADER", "STEM", "OPTIONS", "ANSWER", "CODE"]


@dataclass(frozen=True)
class ParseIssue:
    line: int
    code: str
    message: str
    severity: Literal["ERROR", "WARNING"] = "ERROR"


@dataclass(frozen=True)
class ParseOutcome:
    draft: ExamDraft
    issues: tuple[ParseIssue, ...]
    valid: int
    skipped: int


@dataclass
class _Pending:
    line: int
    chapter: str | None
    text_parts: list[str]
    choices: list[tuple[str, str]] = field(default_factory=list)
    answer: str | None = None
    explanation: str = ""


def _empty(issue: ParseIssue) -> ParseOutcome:
    return ParseOutcome(
        draft=ExamDraft.model_validate({"schema_version": 1, "metadata": {}, "sections": []}),
        issues=(issue,),
        valid=0,
        skipped=0,
    )


def _clean_text(text: str) -> str:
    text = unicodedata.normalize(
        "NFC", text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    )
    return "".join(
        char
        for char in text
        if char in {"\n", "\t"} or unicodedata.category(char) not in {"Cc", "Cf"}
    )


def parse_txt(text: str) -> ParseOutcome:
    """Parse TXT without filesystem, database or network access."""
    if len(text.encode("utf-8")) > MAX_BYTES:
        return _empty(ParseIssue(1, "T_TOO_LARGE", "File TXT vượt giới hạn 2 MB."))
    lines = _clean_text(text).split("\n")
    if len(lines) > MAX_LINES:
        return _empty(ParseIssue(MAX_LINES + 1, "T_TOO_MANY_LINES", "File TXT vượt 20.000 dòng."))

    metadata: dict = {}
    chapters: dict[str, str] = {}
    questions: list[dict] = []
    issues: list[ParseIssue] = []
    seen: set[tuple[str, str]] = set()
    current_chapter: str | None = None
    pending: _Pending | None = None
    state: State = "HEADER"
    skipped = 0

    def issue(line: int, code: str, message: str, *, warning: bool = False) -> None:
        issues.append(ParseIssue(line, code, message, "WARNING" if warning else "ERROR"))

    def finish() -> None:
        nonlocal pending, state, skipped
        if pending is None:
            return
        item = pending
        pending = None
        state = "HEADER"
        stem = "\n".join(item.text_parts).strip()
        if item.chapter is None:
            issue(item.line, "T_NO_CHAPTER", "Câu hỏi chưa thuộc chương nào.")
            skipped += 1
            return
        if not stem:
            issue(item.line, "T_EMPTY_QUESTION", "Câu hỏi trống.")
            skipped += 1
            return
        if item.answer is None:
            issue(item.line, "T_NO_ANSWER", "Câu hỏi thiếu dòng đáp án =>.")
            skipped += 1
            return
        raw = item.answer.strip()
        labels = [label for label, _ in item.choices]
        kind: str
        answer_fields: dict = {}
        if item.choices:
            if len(labels) < 2:
                issue(item.line, "T_TOO_FEW_OPTIONS", "Cần ít nhất hai lựa chọn.")
                skipped += 1
                return
            if labels != list("ABCDEF"[: len(labels)]):
                issue(item.line, "T_OPTION_ORDER", "Lựa chọn phải liên tục từ A đến F.")
                skipped += 1
                return
            answers = [part.strip().upper() for part in raw.split(",")]
            if (
                not answers
                or len(set(answers)) != len(answers)
                or any(label not in labels for label in answers)
            ):
                issue(item.line, "T_ANSWER_OUT_OF_RANGE", "Đáp án không nằm trong các lựa chọn.")
                skipped += 1
                return
            kind = "MCQ" if len(answers) == 1 else "MCQ_MULTI"
            answer_fields["choices"] = [
                {"label": label, "text": content, "is_correct": label in answers}
                for label, content in item.choices
            ]
        elif raw.upper() in {"T", "F"}:
            kind = "TRUE_FALSE"
            answer_fields["tf_answer"] = raw.upper() == "T"
        elif raw.startswith("#") and raw[1:].strip():
            kind = "SHORT"
            answer_fields["short_answer"] = raw[1:].strip()
        else:
            issue(item.line, "T_ANSWER_INVALID", "Đáp án không đúng cú pháp TXT v1/v2.")
            skipped += 1
            return
        key = (item.chapter, unicodedata.normalize("NFC", stem).casefold())
        if key in seen:
            issue(item.line, "W_DUP_QUESTION", "Câu hỏi trùng nội dung trong chương.", warning=True)
        seen.add(key)
        candidate = {
            "tmp_id": f"txt-{len(questions) + 1}",
            "order": len(questions) + 1,
            "number_label": f"Câu {len(questions) + 1}",
            "kind": kind,
            "chapter": item.chapter,
            "text": stem,
            "explanation": item.explanation,
            "provenance": {"kind": "txt", "line": item.line},
            **answer_fields,
        }
        try:
            QuestionDraft.model_validate(candidate)
        except ValueError:
            issue(item.line, "T_QUESTION_INVALID", "Nội dung câu hỏi hoặc đáp án không hợp lệ.")
            skipped += 1
            return
        questions.append(candidate)

    simple = {
        "TITLE": "title",
        "SUBTITLE": "subtitle",
        "ICON": "icon",
        "COLOR": "color",
        "SUBJECT": "subject",
        "LEVEL": "level",
        "TYPE": "exam_type",
    }
    numeric = {"GRADE": "grade", "YEAR": "year", "TERM": "term", "DURATION": "duration_minutes"}
    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if state == "CODE":
            assert pending is not None
            if line.startswith("```"):
                pending.text_parts.append(raw_line)
                state = "STEM"
            else:
                pending.text_parts.append(raw_line)
            continue
        if not line:
            continue
        if line.startswith("```"):
            if pending is None:
                issue(line_no, "T_UNKNOWN_LINE", "Khối code nằm ngoài câu hỏi.")
            else:
                pending.text_parts.append(raw_line)
                state = "CODE"
            continue
        chapter = CHAPTER.fullmatch(line)
        if chapter:
            finish()
            code = chapter.group(1).strip()
            if not code:
                issue(line_no, "T_CHAPTER_INVALID", "Mã chương trống.")
                current_chapter = None
            else:
                current_chapter = code
                chapters.setdefault(code, chapter.group(2).strip() or code)
            continue
        if line.startswith("#EXPLAIN:"):
            if pending is None or state != "ANSWER":
                issue(line_no, "T_UNKNOWN_LINE", "Lời giải phải đứng ngay sau đáp án.")
            else:
                pending.explanation = line[len("#EXPLAIN:") :].strip()
            continue
        if line.startswith("#"):
            key, separator, value = line[1:].partition(":")
            key = key.strip().upper()
            value = value.strip()
            if not separator:
                issue(line_no, "T_UNKNOWN_LINE", "Dòng metadata không đúng cú pháp.")
            elif key in simple:
                metadata[simple[key]] = value
            elif key in numeric:
                try:
                    metadata[numeric[key]] = int(value)
                except ValueError:
                    issue(line_no, "T_METADATA_INVALID", f"{key} phải là số nguyên.")
            elif key in {"TRUONG", "NGANH"}:
                metadata["schools" if key == "TRUONG" else "majors"] = [
                    part.strip() for part in value.split(",") if part.strip()
                ]
            else:
                issue(line_no, "T_UNKNOWN_LINE", f"Không nhận ra metadata {key}.")
            continue
        option = OPTION.fullmatch(line)
        if option:
            if pending is None or state == "ANSWER":
                issue(line_no, "T_OPTION_WITHOUT_QUESTION", "Lựa chọn không thuộc câu hỏi.")
            else:
                pending.choices.append((option.group(1).upper(), option.group(2)))
                state = "OPTIONS"
            continue
        if line.startswith("=>"):
            if pending is None or state == "ANSWER":
                issue(line_no, "T_ANSWER_WITHOUT_QUESTION", "Dòng đáp án không thuộc câu hỏi.")
            else:
                pending.answer = line[2:].strip()
                state = "ANSWER"
            continue
        finish()
        pending = _Pending(line_no, current_chapter, [line])
        state = "STEM"
    if state == "CODE":
        issue(len(lines), "T_CODE_UNCLOSED", "Khối code chưa đóng.")
    finish()
    chapter_items = [
        {
            "code": code,
            "name": name,
            "description": f"{sum(q['chapter'] == code for q in questions)} câu hỏi",
            "color": CHAPTER_COLORS[index % len(CHAPTER_COLORS)],
            "order": index + 1,
        }
        for index, (code, name) in enumerate(chapters.items())
    ]
    sections = (
        [
            {
                "order": 1,
                "title": "Câu hỏi",
                "kind": "MIXED",
                "scoring": {"type": "per_question", "points": "1"},
                "questions": questions,
            }
        ]
        if questions
        else []
    )
    try:
        Metadata.model_validate(metadata)
    except ValueError:
        issue(1, "T_METADATA_INVALID", "Thông tin đề chưa hợp lệ; cần sửa ở bản nháp.")
        metadata = {}
    draft = ExamDraft.model_validate(
        {
            "schema_version": 1,
            "metadata": metadata,
            "chapters": chapter_items,
            "sections": sections,
        }
    )
    return ParseOutcome(
        draft, tuple(sorted(issues, key=lambda item: item.line)), len(questions), skipped
    )
