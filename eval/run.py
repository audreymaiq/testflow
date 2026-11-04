"""Score real, precomputed extractor output against private annotated ExamDrafts.

No OCR model is bundled. Missing gold or predictions is an explicit failure.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import unicodedata
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path

from testflow_contracts.exam import ExamDraft

FORMULA = re.compile(r"\$([^$]+)\$")


def normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for row, char in enumerate(left, 1):
        current = [row]
        for column, other in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (char != other),
                )
            )
        previous = current
    return previous[-1]


def _questions(draft: ExamDraft):
    return [question for section in draft.sections for question in section.questions]


def _answer(question):
    if question.kind in {"MCQ", "MCQ_MULTI"}:
        return tuple(choice.label for choice in question.choices if choice.is_correct)
    if question.kind == "TRUE_FALSE":
        return question.tf_answer
    if question.kind == "TF_GROUP":
        return tuple((item.label, item.is_true) for item in question.statements)
    if question.kind == "SHORT":
        return normalized(question.short_answer or "")
    return None


def match_questions(gold, predicted):
    """Deterministic one-to-one match by label and stem similarity."""
    candidates = []
    for gold_index, expected in enumerate(gold):
        for predicted_index, actual in enumerate(predicted):
            similarity = SequenceMatcher(
                None, normalized(expected.text), normalized(actual.text)
            ).ratio()
            label_bonus = (
                0.1
                if expected.number_label
                and expected.number_label == actual.number_label
                else 0
            )
            if similarity >= 0.8 or (similarity >= 0.6 and label_bonus):
                candidates.append(
                    (similarity + label_bonus, gold_index, predicted_index)
                )
    matched = []
    used_gold = set()
    used_predicted = set()
    for _score, gold_index, predicted_index in sorted(
        candidates, key=lambda item: (-item[0], item[1], item[2])
    ):
        if gold_index not in used_gold and predicted_index not in used_predicted:
            matched.append((gold[gold_index], predicted[predicted_index]))
            used_gold.add(gold_index)
            used_predicted.add(predicted_index)
    return matched


def score_exam(gold: ExamDraft, prediction: ExamDraft, *, review_edit_count=None):
    expected = _questions(gold)
    actual = _questions(prediction)
    matched = match_questions(expected, actual)
    matched_count = len(matched)
    field_count = 0
    field_correct = 0
    text_distance = 0
    text_length = 0
    formula_count = 0
    formula_correct = 0
    for left, right in matched:
        for correct in (
            normalized(left.text) == normalized(right.text),
            left.kind == right.kind,
            _answer(left) == _answer(right),
        ):
            field_count += 1
            field_correct += int(correct)
        for index, choice in enumerate(left.choices):
            field_count += 1
            field_correct += int(
                index < len(right.choices)
                and normalized(choice.text) == normalized(right.choices[index].text)
            )
        text_distance += distance(normalized(left.text), normalized(right.text))
        text_length += max(1, len(normalized(left.text)))
        left_formulas = [normalized(item) for item in FORMULA.findall(left.text)]
        right_formulas = [normalized(item) for item in FORMULA.findall(right.text)]
        formula_count += len(left_formulas)
        formula_correct += sum(
            index < len(right_formulas) and formula == right_formulas[index]
            for index, formula in enumerate(left_formulas)
        )
    return {
        "gold_questions": len(expected),
        "predicted_questions": len(actual),
        "matched_questions": matched_count,
        "question_recall": matched_count / len(expected) if expected else None,
        "question_precision": matched_count / len(actual) if actual else None,
        "field_accuracy": field_correct / field_count if field_count else None,
        "question_text_cer": text_distance / text_length if text_length else None,
        "formula_exact": formula_correct / formula_count if formula_count else None,
        "review_edit_count": review_edit_count,
    }


def _mean(values):
    return statistics.mean(values) if values else None


def _percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def aggregate(rows):
    return {
        "exam_count": len(rows),
        "question_recall": _mean(
            [
                row["question_recall"]
                for row in rows
                if row["question_recall"] is not None
            ]
        ),
        "question_precision": _mean(
            [
                row["question_precision"]
                for row in rows
                if row["question_precision"] is not None
            ]
        ),
        "field_accuracy": _mean(
            [row["field_accuracy"] for row in rows if row["field_accuracy"] is not None]
        ),
        "question_text_cer": _mean(
            [
                row["question_text_cer"]
                for row in rows
                if row["question_text_cer"] is not None
            ]
        ),
        "formula_exact": _mean(
            [row["formula_exact"] for row in rows if row["formula_exact"] is not None]
        ),
        "review_edits_mean": _mean(
            [
                row["review_edit_count"]
                for row in rows
                if row["review_edit_count"] is not None
            ]
        ),
        "latency_seconds_per_page_p50": _percentile(
            [value for row in rows for value in row["page_latencies_seconds"]], 0.5
        ),
        "latency_seconds_per_page_p95": _percentile(
            [value for row in rows for value in row["page_latencies_seconds"]], 0.95
        ),
        "gpu_seconds_total": sum(row["gpu_seconds"] for row in rows),
        "api_cost_total": sum(row["api_cost"] for row in rows),
    }


def run(gold_root: Path, prediction_root: Path, *, split: str, allow_synthetic=False):
    rows = []
    for metadata_path in sorted(gold_root.glob("*/meta.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata["split"] != split:
            continue
        if metadata.get("synthetic") and not allow_synthetic:
            continue
        exam_id = metadata_path.parent.name
        prediction_path = prediction_root / f"{exam_id}.json"
        if not prediction_path.exists():
            raise FileNotFoundError(
                f"Missing prediction for {exam_id}: {prediction_path}"
            )
        gold = ExamDraft.model_validate_json(
            (metadata_path.parent / "gold.json").read_text(encoding="utf-8")
        )
        payload = json.loads(prediction_path.read_text(encoding="utf-8"))
        predicted = ExamDraft.model_validate(payload["draft"])
        row = score_exam(
            gold, predicted, review_edit_count=payload.get("review_edit_count")
        )
        row.update(
            exam_id=exam_id,
            level=metadata["level"],
            modality=metadata["modality"],
            synthetic=bool(metadata.get("synthetic")),
            page_latencies_seconds=payload.get("page_latencies_seconds", []),
            gpu_seconds=payload.get("gpu_seconds", 0),
            api_cost=payload.get("api_cost", 0),
        )
        rows.append(row)
    if not rows:
        raise ValueError(f"No annotated {split} exams at {gold_root}")
    by_level = {
        level: aggregate([row for row in rows if row["level"] == level])
        for level in sorted({row["level"] for row in rows})
    }
    return {
        "split": split,
        "synthetic_only": all(row["synthetic"] for row in rows),
        "overall": aggregate(rows),
        "by_level": by_level,
        "exams": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extractor",
        required=True,
        help="Prediction directory name under eval/predictions",
    )
    parser.add_argument("--split", choices=["dev", "held-out"], default="dev")
    parser.add_argument("--gold-root", type=Path, default=Path("eval/gold"))
    parser.add_argument(
        "--prediction-root", type=Path, default=Path("eval/predictions")
    )
    parser.add_argument("--allow-synthetic", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = run(
            args.gold_root,
            args.prediction_root / args.extractor,
            split=args.split,
            allow_synthetic=args.allow_synthetic,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Evaluation blocked: {exc}", file=sys.stderr)
        return 2
    result["extractor"] = args.extractor
    result["generated_at"] = datetime.now(UTC).isoformat()
    output = (
        args.output
        or Path("eval/results")
        / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}_{args.extractor}_{args.split}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "exams": result["overall"]["exam_count"],
                "synthetic_only": result["synthetic_only"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
