"""Pure grading matrix; no database or Django setup needed."""

from decimal import Decimal

import pytest

from apps.practice.grading import QuestionKey, grade_question


@pytest.mark.parametrize(
    ("kind", "key", "answer", "scoring", "status", "earned"),
    [
        (
            "MCQ",
            {"correct_choice": "B", "all_choices": ("A", "B")},
            {"choice": "B"},
            {"type": "per_question", "points": "2"},
            "CORRECT",
            "2",
        ),
        (
            "MCQ",
            {"correct_choice": "B", "all_choices": ("A", "B")},
            {"choice": "A"},
            {"type": "per_question", "points": "2"},
            "WRONG",
            "0",
        ),
        (
            "MCQ",
            {"correct_choice": "B", "all_choices": ("A", "B")},
            {},
            {"type": "per_question", "points": "2"},
            "BLANK",
            "0",
        ),
        (
            "MCQ_MULTI",
            {"correct_choices": frozenset({"A", "C"}), "all_choices": ("A", "B", "C", "D")},
            {"choices": ["A", "C"]},
            {"type": "per_question", "points": "4"},
            "CORRECT",
            "4",
        ),
        (
            "MCQ_MULTI",
            {"correct_choices": frozenset({"A", "C"}), "all_choices": ("A", "B", "C", "D")},
            {"choices": ["A", "B"]},
            {"type": "per_question", "points": "4"},
            "WRONG",
            "0",
        ),
        (
            "MCQ_MULTI",
            {"correct_choices": frozenset({"A", "C"}), "all_choices": ("A", "B", "C", "D")},
            {"choices": ["A", "B"]},
            {"type": "per_question", "points": "4", "partial": True},
            "WRONG",
            "0",
        ),
        (
            "MCQ_MULTI",
            {"correct_choices": frozenset({"A", "C"}), "all_choices": ("A", "B", "C", "D")},
            {"choices": ["A"]},
            {"type": "per_question", "points": "4", "partial": True},
            "PARTIAL",
            "2",
        ),
        (
            "TRUE_FALSE",
            {"tf_answer": False},
            {"value": False},
            {"type": "per_question", "points": "1"},
            "CORRECT",
            "1",
        ),
        (
            "TRUE_FALSE",
            {"tf_answer": False},
            {"value": True},
            {"type": "per_question", "points": "1"},
            "WRONG",
            "0",
        ),
        (
            "SHORT",
            {"short_answer": "3.5"},
            {"text": "+3,5"},
            {"type": "per_question", "points": "1"},
            "CORRECT",
            "1",
        ),
        (
            "SHORT",
            {"short_answer": "3.5", "tolerance": Decimal("0.1")},
            {"text": "3.59"},
            {"type": "per_question", "points": "1"},
            "CORRECT",
            "1",
        ),
        (
            "SHORT",
            {"short_answer": "Hà Nội"},
            {"text": "hà nội"},
            {"type": "per_question", "points": "1"},
            "CORRECT",
            "1",
        ),
        (
            "ESSAY",
            {"points": Decimal("3")},
            {"text": "Bài luận"},
            {"type": "manual"},
            "MANUAL",
            "0",
        ),
    ],
)
def test_grade_matrix(kind, key, answer, scoring, status, earned):
    result = grade_question(QuestionKey(kind=kind, **key), answer, scoring)
    assert result.status == status
    assert result.earned == Decimal(earned)
    assert isinstance(result.max_points, Decimal)


def test_tf_group_ladder_and_point_override():
    key = QuestionKey(
        kind="TF_GROUP",
        statements={"a": True, "b": False, "c": True, "d": False},
        points=Decimal("2"),
    )
    scoring = {
        "type": "tf_ladder",
        "ladder": {"0": "0", "1": "0.1", "2": "0.25", "3": "0.5", "4": "1"},
    }
    partial = grade_question(key, {"a": True, "b": False, "c": None, "d": None}, scoring)
    assert partial.status == "PARTIAL"
    assert partial.earned == Decimal("0.50")
    assert partial.max_points == Decimal("2")
    blank = grade_question(key, {}, scoring)
    assert blank.status == "BLANK"
    assert blank.earned == 0


@pytest.mark.parametrize(
    ("key", "answer", "scoring"),
    [
        (
            QuestionKey(kind="MCQ", correct_choice="A", all_choices=("A", "B")),
            {"choice": "C"},
            {"type": "per_question", "points": 1},
        ),
        (
            QuestionKey(kind="TRUE_FALSE", tf_answer=True),
            {"value": "true"},
            {"type": "per_question", "points": 1},
        ),
        (
            QuestionKey(kind="MCQ_MULTI", correct_choices=frozenset({"A"}), all_choices=("A", "B")),
            {"choices": ["A", "A"]},
            {"type": "per_question", "points": 1},
        ),
        (
            QuestionKey(kind="TF_GROUP", statements={"a": True, "b": False, "c": True, "d": False}),
            {"e": True},
            {"type": "tf_ladder", "ladder": {str(i): i for i in range(5)}},
        ),
    ],
)
def test_malformed_answer_rejected(key, answer, scoring):
    with pytest.raises(ValueError):
        grade_question(key, answer, scoring)
