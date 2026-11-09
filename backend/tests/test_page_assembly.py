"""Synthetic cases for deterministic, source-aware document assembly."""

import pytest
from testflow_contracts.exam import ExamDraft
from testflow_contracts.page import PageSchema

from apps.imports.page_assembly import assemble_pages


def page(page_no=1, *, blocks=None, header=None, figures=None):
    return PageSchema.model_validate(
        {
            "schema_version": 1,
            "page_no": page_no,
            "header": header or {},
            "blocks": blocks or [],
            "figures": figures or [],
        }
    )


def question(number="Câu 1", *, choices=None, **rest):
    return {
        "type": "question",
        "number_label": number,
        "kind": "MCQ",
        "text": "Hai cộng hai bằng mấy?",
        "choices": choices or [{"label": "A", "text": "Ba"}, {"label": "B", "text": "Bốn"}],
        **rest,
    }


def codes(outcome):
    return {issue.code for issue in outcome.issues}


def test_question_only_page_remains_reviewable_without_invented_metadata_or_key():
    outcome = assemble_pages([page(blocks=[question()])])

    assert outcome.valid == 1 and outcome.skipped == 0
    assert outcome.draft.metadata.title is None
    assert outcome.draft.metadata.subject is None
    assert outcome.draft.metadata.level is None
    assert outcome.draft.metadata.schools == []
    draft_question = outcome.draft.sections[0].questions[0]
    assert draft_question.number_label == "Câu 1"
    assert draft_question.provenance.kind == "page"
    assert draft_question.provenance.page_no == 1
    assert not any(choice.is_correct for choice in draft_question.choices)
    assert "W_NO_ANSWER_KEY" in codes(outcome)
    assert not any(issue.severity == "ERROR" for issue in outcome.issues)
    assert ExamDraft.model_validate(outcome.draft.model_dump()) == outcome.draft


def test_header_is_only_copied_when_present_and_conflicts_are_reported():
    outcome = assemble_pages(
        [
            page(1, blocks=[question()], header={"title": "Đề kiểm tra", "school": "Trường A"}),
            page(2, header={"title": "Đề khác", "school": "Trường B", "year": 1999}),
            page(3, header={"title": "Đề kiểm tra", "school": "Trường A"}),
        ]
    )

    assert outcome.draft.metadata.title is None
    assert outcome.draft.metadata.schools == []
    assert outcome.draft.metadata.year is None
    assert [issue.code for issue in outcome.issues].count("E_HEADER_CONFLICT") == 2
    assert "W_HEADER_INVALID" in codes(outcome)


def test_answer_key_on_later_page_maps_by_original_number():
    outcome = assemble_pages(
        [
            page(1, blocks=[question("Câu 7")]),
            page(
                2,
                blocks=[{"type": "answer_key", "entries": [{"number_label": "7", "answer": "B"}]}],
            ),
        ]
    )

    assert outcome.draft.sections[0].questions[0].choices[1].is_correct
    assert "W_NO_ANSWER_KEY" not in codes(outcome)
    assert not any(issue.severity == "ERROR" for issue in outcome.issues)


def test_duplicate_number_does_not_attach_answer_to_wrong_question():
    outcome = assemble_pages(
        [
            page(
                blocks=[
                    question(),
                    question(),
                    {"type": "answer_key", "entries": [{"number_label": "Câu 1", "answer": "B"}]},
                ]
            )
        ]
    )

    assert "E_ANSWER_UNMATCHED" in codes(outcome)
    assert all(
        not any(choice.is_correct for choice in question.choices)
        for question in outcome.draft.sections[0].questions
    )


def test_multi_answer_key_preserves_two_correct_choices():
    block = question("Câu 2")
    block["kind"] = "MCQ_MULTI"
    outcome = assemble_pages(
        [
            page(
                blocks=[
                    block,
                    {
                        "type": "answer_key",
                        "entries": [{"number_label": "Câu 2", "answer": "A,B"}],
                    },
                ]
            )
        ]
    )

    assert [
        choice.label
        for choice in outcome.draft.sections[0].questions[0].choices
        if choice.is_correct
    ] == ["A", "B"]
    assert "W_NO_ANSWER_KEY" not in codes(outcome)


def test_invalid_answer_stays_unset_and_is_reported():
    outcome = assemble_pages(
        [
            page(
                blocks=[
                    question(),
                    {
                        "type": "answer_key",
                        "entries": [{"number_label": "Câu 1", "answer": "F"}],
                    },
                ]
            )
        ]
    )

    assert {"E_ANSWER_INVALID", "W_NO_ANSWER_KEY"} <= codes(outcome)
    assert not any(choice.is_correct for choice in outcome.draft.sections[0].questions[0].choices)


def test_unsupported_page_content_is_reported_and_skipped_not_silently_lost():
    outcome = assemble_pages(
        [
            page(
                blocks=[
                    question(figure_refs=["f1"]),
                    question("Câu 2", continues_on_next=True),
                    question("Câu 3", passage_ref="p1"),
                ],
                figures=[{"id": "f1", "bbox": [0.1, 0.1, 0.2, 0.2]}],
            )
        ]
    )

    assert outcome.valid == 1 and outcome.skipped == 2
    assert outcome.draft.sections[0].questions[0].figure_refs == ["f1"]
    assert {
        "E_FIGURE_UNSUPPORTED",
        "E_CONTINUATION_UNMATCHED",
        "E_PASSAGE_UNMATCHED",
    } <= codes(outcome)


def test_invalid_choice_and_page_gap_are_errors_with_surviving_question():
    invalid = question("Câu 1", choices=[{"label": "B", "text": "Sai"}])
    outcome = assemble_pages([page(1, blocks=[invalid]), page(3, blocks=[question("Câu 2")])])

    assert outcome.valid == 1 and outcome.skipped == 1
    assert {"E_QUESTION_INVALID", "E_PAGE_GAP"} <= codes(outcome)
    assert outcome.draft.sections[0].questions[0].provenance.page_no == 3


def test_section_changes_keep_unique_question_ids():
    outcome = assemble_pages(
        [
            page(
                blocks=[
                    {"type": "section_heading", "text": "Phần I"},
                    question(),
                    {"type": "section_heading", "text": "Phần II"},
                    question("Câu 2"),
                ]
            )
        ]
    )

    assert [section.title for section in outcome.draft.sections] == ["Phần I", "Phần II"]
    assert len({q.tmp_id for section in outcome.draft.sections for q in section.questions}) == 2


def test_duplicate_page_number_is_rejected():
    with pytest.raises(ValueError, match="unique"):
        assemble_pages([page(1), page(1)])


def test_shared_passage_survives_cross_page_question_reference():
    outcome = assemble_pages(
        [
            page(1, blocks=[{"type": "passage", "id": "reading-1", "text": "Đọc đoạn văn."}]),
            page(2, blocks=[question(passage_ref="reading-1")]),
        ]
    )
    section = outcome.draft.sections[0]
    assert len(section.passages) == 1
    assert section.questions[0].passage_ref == section.passages[0].tmp_id
    assert "E_PASSAGE_UNANCHORED" not in codes(outcome)
    assert "E_PASSAGE_UNMATCHED" not in codes(outcome)


def test_unreferenced_passage_blocks_confirmation_instead_of_disappearing():
    outcome = assemble_pages(
        [
            page(
                blocks=[
                    {"type": "passage", "id": "reading-1", "text": "Đọc đoạn văn."},
                    {"type": "section_heading", "text": "Phần kế tiếp"},
                    question(),
                ]
            )
        ]
    )
    assert "E_PASSAGE_UNANCHORED" in codes(outcome)


def test_question_continuation_merges_text_and_choices_without_guessing():
    first = question("Câu 9", choices=[{"label": "A", "text": "Một"}])
    first["continues_on_next"] = True
    second = question(
        "Câu 9", choices=[{"label": "B", "text": "Hai"}], continues_from_previous=True
    )
    second["text"] = "phần tiếp theo"
    outcome = assemble_pages([page(1, blocks=[first]), page(2, blocks=[second])])
    assert outcome.valid == 1 and outcome.skipped == 0
    merged = outcome.draft.sections[0].questions[0]
    assert merged.text.endswith("phần tiếp theo")
    assert [choice.label for choice in merged.choices] == ["A", "B"]
    assert merged.provenance.page_no == 1
    assert "E_CONTINUATION_UNMATCHED" not in codes(outcome)


def test_mismatched_continuation_is_blocked_and_counted_as_skipped():
    first = question("Câu 9", continues_on_next=True)
    second = question("Câu 10", continues_from_previous=True)
    outcome = assemble_pages([page(1, blocks=[first]), page(2, blocks=[second])])
    assert outcome.valid == 0 and outcome.skipped == 1
    assert "E_CONTINUATION_UNMATCHED" in codes(outcome)
