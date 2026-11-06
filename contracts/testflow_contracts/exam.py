"""ExamDraft v1: source-independent normalized exam input."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Level = Literal["TIEU_HOC", "THCS", "THPT", "DAI_HOC", "KHAC"]
QuestionKind = Literal["MCQ", "MCQ_MULTI", "TF_GROUP", "TRUE_FALSE", "SHORT", "ESSAY"]
ExamType = Literal["THI_CHINH_THUC", "GIUA_KY", "CUOI_KY", "KIEM_TRA", "ON_TAP", "OLYMPIC", "KHAC"]
ScoringPreset = Literal["THPT_2025", "UNIFORM_10", "UNIFORM_100", "PRACTICE_NO_SCORE", "CUSTOM"]
_TAG = re.compile(r"<\s*/?\s*[A-Za-z][^>]*>")


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def normalize_strings(cls, value):
        if isinstance(value, str):
            value = value.replace("\r\n", "\n").replace("\r", "\n")
            return "".join(
                char
                for char in unicodedata.normalize("NFC", value.strip())
                if char in {"\n", "\t"} or unicodedata.category(char) not in {"Cc", "Cf"}
            )
        return value


class Metadata(ContractModel):
    title: str | None = None
    subtitle: str = ""
    icon: str = ""
    color: str = ""
    level: Level | None = None
    grade: int | None = None
    subject: str | None = None
    exam_type: ExamType | None = None
    schools: list[str] = Field(default_factory=list)
    majors: list[str] = Field(default_factory=list)
    province: str = ""
    year: int | None = None
    term: int | None = None
    duration_minutes: int | None = None
    scoring_preset: ScoringPreset = "UNIFORM_10"
    max_score: Decimal | None = None
    source: str = ""

    @model_validator(mode="after")
    def grade_matches_level(self):
        ranges = {"TIEU_HOC": range(1, 6), "THCS": range(6, 10), "THPT": range(10, 13)}
        if self.level in ranges and self.grade is not None and self.grade not in ranges[self.level]:
            raise ValueError("grade does not match level")
        if self.level in {"DAI_HOC", "KHAC"} and self.grade is not None:
            raise ValueError("grade must be null for this level")
        if self.year is not None and not 2000 <= self.year <= date.today().year + 1:
            raise ValueError("year outside supported range")
        if self.term is not None and self.term not in (1, 2, 3):
            raise ValueError("term must be 1, 2 or 3")
        if self.duration_minutes is not None and self.duration_minutes <= 0:
            raise ValueError("duration must be positive")
        return self


class ChapterDraft(ContractModel):
    code: str
    name: str
    description: str = ""
    color: str = ""
    order: int


class ChoiceDraft(ContractModel):
    label: str
    text: str
    is_correct: bool = False

    @field_validator("text")
    @classmethod
    def reject_html(cls, value: str) -> str:
        if _TAG.search(value):
            raise ValueError("HTML is not allowed")
        return value


class StatementDraft(ContractModel):
    label: str
    text: str
    is_true: bool | None = None


class PassageDraft(ContractModel):
    tmp_id: str
    order: int
    text: str


class Provenance(ContractModel):
    kind: Literal["manual", "txt", "page"]
    line: int | None = None
    page_no: int | None = None
    bbox: list[float] | None = None


class QuestionDraft(ContractModel):
    tmp_id: str
    order: int
    number_label: str = ""
    kind: QuestionKind
    chapter: str | None = None
    passage_ref: str | None = None
    text: str
    explanation: str = ""
    choices: list[ChoiceDraft] = Field(default_factory=list)
    statements: list[StatementDraft] = Field(default_factory=list)
    tf_answer: bool | None = None
    short_answer: str | None = None
    short_tolerance: Decimal | None = None
    essay_model_answer: str = ""
    points: Decimal | None = None
    provenance: Provenance

    @model_validator(mode="after")
    def validate_kind(self):
        if not self.text or _TAG.search(self.text) or _TAG.search(self.explanation):
            raise ValueError("question text must be nonempty plain text")
        if self.order < 1:
            raise ValueError("question order must be positive")
        if self.kind in {"MCQ", "MCQ_MULTI"}:
            labels = [choice.label for choice in self.choices]
            if len(labels) not in range(2, 7) or labels != list("ABCDEF"[: len(labels)]):
                raise ValueError("MCQ choices must be labeled consecutively A-F")
            correct = sum(choice.is_correct for choice in self.choices)
            if (self.kind == "MCQ" and correct > 1) or (
                self.kind == "MCQ_MULTI" and correct > len(labels)
            ):
                raise ValueError("invalid answer key")
        elif self.choices:
            raise ValueError("choices are only valid for MCQ questions")
        if self.kind == "TF_GROUP":
            if [item.label for item in self.statements] != list("abcd"):
                raise ValueError("TF_GROUP requires statements a-d")
        elif self.statements:
            raise ValueError("statements are only valid for TF_GROUP")
        if self.kind != "TRUE_FALSE" and self.tf_answer is not None:
            raise ValueError("tf_answer is only valid for TRUE_FALSE")
        if self.kind != "SHORT" and self.short_answer:
            raise ValueError("short_answer is only valid for SHORT")
        if self.kind != "ESSAY" and self.essay_model_answer:
            raise ValueError("essay_model_answer is only valid for ESSAY")
        if self.points is not None and self.points < 0:
            raise ValueError("points must not be negative")
        return self


class Scoring(ContractModel):
    type: Literal["per_question", "tf_ladder", "manual"]
    points: Decimal | None = None
    ladder: dict[str, Decimal] | None = None
    partial: bool = False

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.type == "per_question" and (self.points is None or self.points < 0):
            raise ValueError("per_question scoring needs nonnegative points")
        if self.type == "tf_ladder" and (
            self.ladder is None or set(self.ladder) != {"0", "1", "2", "3", "4"}
        ):
            raise ValueError("tf_ladder needs keys 0..4")
        return self


class SectionDraft(ContractModel):
    order: int
    title: str
    kind: Literal["MCQ", "MCQ_MULTI", "TF_GROUP", "TRUE_FALSE", "SHORT", "ESSAY", "MIXED"]
    scoring: Scoring
    passages: list[PassageDraft] = Field(default_factory=list)
    questions: list[QuestionDraft] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_order(self):
        if self.order < 1 or [q.order for q in self.questions] != list(
            range(1, len(self.questions) + 1)
        ):
            raise ValueError("section questions must have consecutive order from 1")
        if self.kind != "MIXED" and any(q.kind != self.kind for q in self.questions):
            raise ValueError("question kind must match section kind")
        return self


class ExamDraft(ContractModel):
    schema_version: Literal[1]
    metadata: Metadata
    chapters: list[ChapterDraft] = Field(default_factory=list)
    sections: list[SectionDraft] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self):
        if [s.order for s in self.sections] != list(range(1, len(self.sections) + 1)):
            raise ValueError("sections must have consecutive order from 1")
        chapter_codes = [chapter.code for chapter in self.chapters]
        if len(set(chapter_codes)) != len(chapter_codes):
            raise ValueError("chapter codes must be unique")
        ids = []
        for section in self.sections:
            passages = {passage.tmp_id for passage in section.passages}
            for question in section.questions:
                ids.append(question.tmp_id)
                if question.chapter and question.chapter not in chapter_codes:
                    raise ValueError("question references an unknown chapter")
                if question.passage_ref and question.passage_ref not in passages:
                    raise ValueError("question references an unknown passage")
        if len(set(ids)) != len(ids):
            raise ValueError("temporary question IDs must be unique")
        return self
