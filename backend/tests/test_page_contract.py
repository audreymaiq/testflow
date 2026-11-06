"""Conformance checks for the independent OCR page wire contract."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from testflow_contracts.page import PageSchema, QuestionBlock


def sample_page():
    return {
        "schema_version": 1,
        "page_no": 2,
        "header": {"subject": "Toa\u0301n"},
        "blocks": [
            {"type": "section_heading", "text": "PHẦN I"},
            {"type": "passage", "id": "p1", "text": "Đọc đoạn sau."},
            {
                "type": "question",
                "number_label": "Câu 3",
                "kind": "MCQ",
                "text": "2 + 2 = ?",
                "passage_ref": "p1",
                "choices": [{"label": "A", "text": "3"}, {"label": "B", "text": "4"}],
                "figure_refs": ["f1"],
                "continues_on_next": True,
            },
            {
                "type": "answer_key",
                "entries": [{"number_label": "Câu 3", "answer": "B"}],
            },
        ],
        "figures": [{"id": "f1", "bbox": [0.1, 0.2, 0.7, 0.8], "anchor": "after_question_text"}],
    }


def test_page_schema_round_trip_and_normalization():
    page = PageSchema.model_validate(sample_page())
    assert page.header.subject == "Toán"
    assert isinstance(page.blocks[2], QuestionBlock)
    assert page.blocks[2].continues_on_next
    assert page.figures[0].bbox == (0.1, 0.2, 0.7, 0.8)
    assert PageSchema.model_validate_json(page.model_dump_json()) == page
    assert PageSchema.model_json_schema()["properties"]["schema_version"]["const"] == 1


@pytest.mark.parametrize(
    "change",
    [
        lambda page: page.update(schema_version=2),
        lambda page: page.update(page_no=0),
        lambda page: page.update(unexpected="field"),
        lambda page: page["blocks"][2].update(text="<script>alert(1)</script>"),
        lambda page: page["figures"][0].update(bbox=[0.7, 0.2, 0.1, 0.8]),
        lambda page: page["figures"].append(page["figures"][0].copy()),
    ],
)
def test_page_schema_rejects_invalid_structure(change):
    page = sample_page()
    change(page)
    with pytest.raises(ValidationError):
        PageSchema.model_validate(page)


def test_cross_page_passage_reference_remains_for_assembly():
    page = sample_page()
    page["blocks"] = [page["blocks"][2]]
    page["figures"] = []
    page["blocks"][0]["figure_refs"] = []
    assert PageSchema.model_validate(page).blocks[0].passage_ref == "p1"


def test_exported_json_schema_matches_runtime_contract():
    schema_file = Path(__file__).resolve().parents[2] / "contracts/schemas/page-v1.json"
    assert json.loads(schema_file.read_text(encoding="utf-8")) == PageSchema.model_json_schema()
