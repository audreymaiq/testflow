"""Synthetic smoke checks for the offline evaluator; not OCR quality evidence."""

import json

import pytest
from eval.run import run, score_exam
from testflow_contracts.exam import ExamDraft


def draft(text="2 + 2 = ?", answer="B"):
    return ExamDraft.model_validate(
        {
            "schema_version": 1,
            "metadata": {
                "title": "Synthetic math",
                "level": "THPT",
                "grade": 12,
                "subject": "toan",
                "exam_type": "ON_TAP",
            },
            "sections": [
                {
                    "order": 1,
                    "title": "Part I",
                    "kind": "MCQ",
                    "scoring": {"type": "per_question", "points": 1},
                    "questions": [
                        {
                            "tmp_id": "q1",
                            "order": 1,
                            "number_label": "Câu 1",
                            "kind": "MCQ",
                            "text": text,
                            "provenance": {"kind": "manual"},
                            "choices": [
                                {"label": "A", "text": "3", "is_correct": answer == "A"},
                                {"label": "B", "text": "4", "is_correct": answer == "B"},
                            ],
                        }
                    ],
                }
            ],
        }
    )


def test_exact_and_wrong_answer_metrics():
    exact = score_exam(draft(), draft(), review_edit_count=0)
    assert exact["question_recall"] == 1
    assert exact["question_precision"] == 1
    assert exact["field_accuracy"] == 1
    assert exact["question_text_cer"] == 0
    assert exact["review_edit_count"] == 0
    wrong = score_exam(draft(), draft(answer="A"))
    assert wrong["question_recall"] == 1
    assert wrong["field_accuracy"] < 1
    assert wrong["review_edit_count"] is None


def test_gold_and_predictions_required_and_synthetic_is_labeled(tmp_path):
    gold_root = tmp_path / "gold"
    pred_root = tmp_path / "predictions" / "fake"
    case = gold_root / "synthetic-01"
    case.mkdir(parents=True)
    pred_root.mkdir(parents=True)
    (case / "meta.json").write_text(
        json.dumps({"split": "dev", "level": "THPT", "modality": "text", "synthetic": True}),
        encoding="utf-8",
    )
    (case / "gold.json").write_text(draft().model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="No annotated"):
        run(gold_root, pred_root, split="dev")
    with pytest.raises(FileNotFoundError, match="Missing prediction"):
        run(gold_root, pred_root, split="dev", allow_synthetic=True)
    (pred_root / "synthetic-01.json").write_text(
        json.dumps(
            {
                "draft": draft().model_dump(mode="json"),
                "review_edit_count": 0,
                "page_latencies_seconds": [1.5],
                "gpu_seconds": 1.5,
                "api_cost": 0,
            }
        ),
        encoding="utf-8",
    )
    result = run(gold_root, pred_root, split="dev", allow_synthetic=True)
    assert result["synthetic_only"]
    assert result["overall"]["exam_count"] == 1
    assert result["overall"]["latency_seconds_per_page_p50"] == 1.5
