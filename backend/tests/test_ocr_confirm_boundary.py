"""Synthetic OCR draft tests for the shared confirmation boundary."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from testflow_contracts.exam import ExamDraft

from apps.catalog.models import Exam, School, Subject
from apps.imports.models import Draft, ImportJob


def ocr_draft():
    return ExamDraft.model_validate(
        {
            "schema_version": 1,
            "metadata": {
                "title": "Đề kiểm tra mẫu",
                "level": "THPT",
                "grade": 12,
                "subject": "toan",
                "exam_type": "KIEM_TRA",
                "schools": ["Trường Mẫu"],
            },
            "sections": [
                {
                    "order": 1,
                    "title": "Câu hỏi",
                    "kind": "MCQ",
                    "scoring": {"type": "per_question", "points": "1"},
                    "questions": [
                        {
                            "tmp_id": "page-1-q-1",
                            "order": 1,
                            "number_label": "Câu 1",
                            "kind": "MCQ",
                            "text": "Hai cộng hai bằng mấy?",
                            "choices": [
                                {"label": "A", "text": "Ba"},
                                {"label": "B", "text": "Bốn", "is_correct": True},
                            ],
                            "provenance": {"kind": "page", "page_no": 1},
                        }
                    ],
                }
            ],
        }
    ).model_dump(mode="json")


@pytest.fixture
def context(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    Subject.objects.update_or_create(code="toan", defaults={"name": "Toán", "levels": ["THPT"]})
    School.objects.get_or_create(name="Trường Mẫu")
    owner = get_user_model().objects.create_user(
        "ocr_owner", email="ocr_owner@example.com", password="HardToGuess#2026"
    )
    client = APIClient()
    client.force_authenticate(owner)
    return client, owner


def make_job(owner, *, digest, issues=None, skipped_count=0):
    job = ImportJob.objects.create(
        uploader=owner,
        original_file="imports/synthetic/original.png",
        original_filename="synthetic.png",
        sha256=digest,
        mime_type="image/png",
        file_size=64,
        source_kind="OCR",
        status=ImportJob.Status.NEEDS_REVIEW,
    )
    data = ocr_draft()
    Draft.objects.create(
        job=job,
        schema_version=1,
        data=data,
        original_data=data,
        warnings=issues or [],
        skipped_count=skipped_count,
    )
    return job


@pytest.mark.django_db
def test_generic_edit_cannot_clear_unresolved_ocr_source_error(context):
    client, owner = context
    error = {
        "page_no": 1,
        "code": "E_HEADER_CONFLICT",
        "message": "Thông tin trên hai trang khác nhau.",
        "severity": "ERROR",
    }
    job = make_job(owner, digest="e" * 64, issues=[error])

    edited = client.patch(f"/api/v1/imports/{job.id}/", {"draft": ocr_draft()}, format="json")
    assert edited.status_code == 200, edited.data
    assert edited.data["report"]["issues"] == [error]
    rejected = client.post(f"/api/v1/imports/{job.id}/confirm/")
    assert rejected.status_code == 400
    assert rejected.data["error"]["code"] == "DRAFT_HAS_ERRORS"
    assert Exam.objects.count() == 0


@pytest.mark.django_db
def test_confirmed_ocr_draft_retains_ocr_source_kind(context):
    client, owner = context
    job = make_job(owner, digest="f" * 64)

    response = client.post(f"/api/v1/imports/{job.id}/confirm/")
    assert response.status_code == 200, response.data
    exam = Exam.objects.get(pk=response.data["exam_id"])
    assert exam.owner_id == owner.id
    assert exam.source_kind == "OCR"
    assert exam.visibility == "PRIVATE"
    assert str(exam.source_job) == str(job.id)


@pytest.mark.django_db
def test_generic_ocr_edit_preserves_unresolved_skipped_count(context):
    client, owner = context
    error = {
        "page_no": 1,
        "code": "E_FIGURE_UNSUPPORTED",
        "message": "Figure needs review.",
        "severity": "ERROR",
    }
    job = make_job(owner, digest="a" * 64, issues=[error], skipped_count=1)
    data = ocr_draft()
    extra = data["sections"][0]["questions"][0].copy()
    extra["tmp_id"] = "page-1-q-2"
    extra["order"] = 2
    extra["number_label"] = "Câu 2"
    data["sections"][0]["questions"].append(extra)

    edited = client.patch(f"/api/v1/imports/{job.id}/", {"draft": data}, format="json")
    assert edited.status_code == 200, edited.data
    assert edited.data["report"]["skipped"] == 1
    assert edited.data["report"]["issues"] == [error]
    data["metadata"]["subtitle"] = "Reviewed against the source image"
    edited_again = client.patch(f"/api/v1/imports/{job.id}/", {"draft": data}, format="json")
    assert edited_again.status_code == 200, edited_again.data
    assert edited_again.data["report"]["skipped"] == 1
    assert client.post(f"/api/v1/imports/{job.id}/confirm/").status_code == 400
