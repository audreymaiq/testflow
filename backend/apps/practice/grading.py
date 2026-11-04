"""Pure Decimal grading for the six R1 question kinds."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

GradeStatus = Literal["CORRECT", "PARTIAL", "WRONG", "BLANK", "MANUAL"]
ZERO = Decimal("0")


@dataclass(frozen=True)
class QuestionKey:
    kind: str
    correct_choice: str | None = None
    correct_choices: frozenset[str] | None = None
    all_choices: tuple[str, ...] = ()
    tf_answer: bool | None = None
    statements: Mapping[str, bool] | None = None
    short_answer: str | None = None
    tolerance: Decimal | None = None
    points: Decimal | None = None


@dataclass(frozen=True)
class GradeResult:
    earned: Decimal
    max_points: Decimal
    status: GradeStatus


def _decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _max_points(key: QuestionKey, scoring: Mapping) -> Decimal:
    if key.points is not None:
        result = key.points
    elif scoring.get("type") == "tf_ladder":
        result = _decimal(scoring["ladder"]["4"])
    else:
        result = _decimal(scoring.get("points", 0))
    if result < ZERO:
        raise ValueError("negative points are invalid")
    return result


def _result(status: GradeStatus, max_points: Decimal, earned: Decimal = ZERO) -> GradeResult:
    return GradeResult(earned=earned, max_points=max_points, status=status)


def _mcq(key: QuestionKey, answer: dict, scoring: Mapping, maximum: Decimal) -> GradeResult:
    if key.correct_choice is None:
        return _result("MANUAL", maximum)
    choice = answer.get("choice")
    if choice in (None, ""):
        return _result("BLANK", maximum)
    if not isinstance(choice, str) or choice not in key.all_choices:
        raise ValueError("invalid MCQ choice")
    return (
        _result("CORRECT", maximum, maximum)
        if choice == key.correct_choice
        else _result("WRONG", maximum)
    )


def _multi(key: QuestionKey, answer: dict, scoring: Mapping, maximum: Decimal) -> GradeResult:
    correct = key.correct_choices
    if not correct:
        return _result("MANUAL", maximum)
    raw = answer.get("choices", [])
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise ValueError("invalid MCQ_MULTI answer")
    selected = set(raw)
    if len(selected) != len(raw) or not selected.issubset(set(key.all_choices)):
        raise ValueError("invalid MCQ_MULTI choices")
    if not selected:
        return _result("BLANK", maximum)
    if selected == correct:
        return _result("CORRECT", maximum, maximum)
    if not scoring.get("partial", False):
        return _result("WRONG", maximum)
    right_fraction = Decimal(len(selected & correct)) / Decimal(len(correct))
    wrong_options = set(key.all_choices) - correct
    wrong_fraction = Decimal(len(selected - correct)) / Decimal(max(1, len(wrong_options)))
    earned = max(ZERO, right_fraction - wrong_fraction) * maximum
    return _result("PARTIAL", maximum, earned) if earned > ZERO else _result("WRONG", maximum)


def _true_false(key: QuestionKey, answer: dict, scoring: Mapping, maximum: Decimal) -> GradeResult:
    if key.tf_answer is None:
        return _result("MANUAL", maximum)
    value = answer.get("value")
    if value is None:
        return _result("BLANK", maximum)
    if not isinstance(value, bool):
        raise ValueError("TRUE_FALSE answer must be boolean")
    return (
        _result("CORRECT", maximum, maximum)
        if value == key.tf_answer
        else _result("WRONG", maximum)
    )


def _tf_group(key: QuestionKey, answer: dict, scoring: Mapping, maximum: Decimal) -> GradeResult:
    if not key.statements or len(key.statements) != 4:
        return _result("MANUAL", maximum)
    if any(label not in key.statements for label in answer):
        raise ValueError("unknown TF_GROUP statement")
    if any(value is not None and not isinstance(value, bool) for value in answer.values()):
        raise ValueError("TF_GROUP values must be boolean or null")
    if all(answer.get(label) is None for label in key.statements):
        return _result("BLANK", maximum)
    correct_count = sum(answer.get(label) is truth for label, truth in key.statements.items())
    ladder = scoring.get("ladder")
    if not isinstance(ladder, dict) or set(ladder) != {"0", "1", "2", "3", "4"}:
        raise ValueError("invalid TF_GROUP ladder")
    full = _decimal(ladder["4"])
    raw = _decimal(ladder[str(correct_count)])
    earned = raw * maximum / full if full > ZERO else ZERO
    status: GradeStatus = (
        "CORRECT" if correct_count == 4 else "PARTIAL" if earned > ZERO else "WRONG"
    )
    return _result(status, maximum, earned)


def _short(key: QuestionKey, answer: dict, scoring: Mapping, maximum: Decimal) -> GradeResult:
    if not key.short_answer:
        return _result("MANUAL", maximum)
    raw = answer.get("text", "")
    if not isinstance(raw, str):
        raise ValueError("SHORT answer must be text")
    response = unicodedata.normalize("NFC", raw.strip()).replace(",", ".").removeprefix("+")
    expected = (
        unicodedata.normalize("NFC", key.short_answer.strip()).replace(",", ".").removeprefix("+")
    )
    if not response:
        return _result("BLANK", maximum)
    try:
        delta = abs(Decimal(response) - Decimal(expected))
        correct = delta <= (key.tolerance if key.tolerance is not None else ZERO)
    except InvalidOperation:
        correct = response.casefold() == expected.casefold()
    return _result("CORRECT", maximum, maximum) if correct else _result("WRONG", maximum)


def _essay(key: QuestionKey, answer: dict, scoring: Mapping, maximum: Decimal) -> GradeResult:
    return _result("MANUAL", maximum)


GRADERS: dict[str, Callable[[QuestionKey, dict, Mapping, Decimal], GradeResult]] = {
    "MCQ": _mcq,
    "MCQ_MULTI": _multi,
    "TRUE_FALSE": _true_false,
    "TF_GROUP": _tf_group,
    "SHORT": _short,
    "ESSAY": _essay,
}


def grade_question(key: QuestionKey, answer: dict | None, scoring: Mapping) -> GradeResult:
    """Grade one question without DB, HTTP or mutable global state."""
    if key.kind not in GRADERS:
        raise ValueError("unsupported question kind")
    if answer is not None and not isinstance(answer, dict):
        raise ValueError("answer must be an object")
    maximum = _max_points(key, scoring)
    return GRADERS[key.kind](key, answer or {}, scoring, maximum)
