"""Versioned, model-neutral extraction result for one normalized page.

Figure coordinates are fractions of the page image dimensions, not pixels.
The original model response belongs in PageResult.raw_output, outside this schema.
Cross-page references are resolved by the deterministic assembler, not here.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .exam import ContractModel, QuestionKind

_TAG = re.compile(r"<\s*/?\s*[A-Za-z][^>]*>")


class PageContractModel(ContractModel):
    @field_validator("*", mode="after")
    @classmethod
    def reject_html(cls, value):
        if isinstance(value, str) and _TAG.search(value):
            raise ValueError("HTML is not allowed")
        return value


class PageHeader(PageContractModel):
    title: str | None = None
    subject: str | None = None
    year: int | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    school: str | None = None


class SectionHeading(PageContractModel):
    type: Literal["section_heading"]
    text: str


class PassageBlock(PageContractModel):
    type: Literal["passage"]
    id: str = Field(min_length=1)
    text: str


class PageChoice(PageContractModel):
    label: str
    text: str


class PageStatement(PageContractModel):
    label: str
    text: str


class QuestionBlock(PageContractModel):
    """References may span pages and are checked during deterministic assembly."""

    type: Literal["question"]
    number_label: str = ""
    kind: QuestionKind
    text: str
    passage_ref: str | None = None
    choices: list[PageChoice] = Field(default_factory=list, max_length=6)
    statements: list[PageStatement] = Field(default_factory=list, max_length=4)
    figure_refs: list[str] = Field(default_factory=list, max_length=20)
    continues_from_previous: bool = False
    continues_on_next: bool = False


class AnswerKeyEntry(PageContractModel):
    number_label: str
    answer: str


class AnswerKeyBlock(PageContractModel):
    type: Literal["answer_key"]
    entries: list[AnswerKeyEntry] = Field(default_factory=list, max_length=200)


PageBlock = SectionHeading | PassageBlock | QuestionBlock | AnswerKeyBlock


class PageFigure(PageContractModel):
    """A page-local figure with a normalized bounding box."""

    id: str = Field(min_length=1)
    bbox: tuple[float, float, float, float] = Field(
        description="[x0, y0, x1, y1] as fractions of normalized page image width and height"
    )
    anchor: str = "unanchored"

    @field_validator("bbox")
    @classmethod
    def valid_normalized_box(cls, value: tuple[float, float, float, float]):
        x0, y0, x1, y1 = value
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError("bbox must be normalized and have positive area")
        return value


class PageSchema(PageContractModel):
    """Validated v1 content from one page; raw provider output is stored separately."""

    schema_version: Literal[1]
    page_no: int = Field(ge=1)
    header: PageHeader = Field(default_factory=PageHeader)
    blocks: list[PageBlock] = Field(default_factory=list, max_length=300)
    figures: list[PageFigure] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_local_ids(self):
        figure_ids = [figure.id for figure in self.figures]
        passage_ids = [
            block.id for block in self.blocks if isinstance(block, PassageBlock)
        ]
        if len(figure_ids) != len(set(figure_ids)):
            raise ValueError("figure ids must be unique within a page")
        if len(passage_ids) != len(set(passage_ids)):
            raise ValueError("passage ids must be unique within a page")
        return self
