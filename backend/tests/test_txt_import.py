"""TXT import API, ownership, review, and state transition evidence."""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.catalog.models import Exam, Subject
from apps.common.errors import Conflict
from apps.imports.models import ImportJob, ReviewEdit

GOOD = (
    "#TITLE: Bộ câu hỏi mẫu\n#SUBJECT: toan\n#LEVEL: THPT\n#GRADE: 12\n"
    "#TYPE: ON_TAP\n[CH1] Đại số\n2 + 2 = ?\nA. 3\nB. 4\n=>B\n"
)


@pytest.fixture
def clients(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    Subject.objects.update_or_create(code="toan", defaults={"name": "Toán", "levels": ["THPT"]})
    owner = get_user_model().objects.create_user(
        "txt_owner", email="txt_owner@example.com", password="HardToGuess#2026"
    )
    other = get_user_model().objects.create_user(
        "txt_other", email="txt_other@example.com", password="HardToGuess#2026"
    )
    own = APIClient()
    own.force_authenticate(owner)
    outsider = APIClient()
    outsider.force_authenticate(other)
    return own, outsider, owner


def upload(client, text=GOOD, filename="questions.txt"):
    file = SimpleUploadedFile(filename, text.encode("utf-8"), content_type="text/plain")
    return client.post("/api/v1/imports/txt/", {"file": file}, format="multipart")


@pytest.mark.django_db
def test_txt_import_review_confirm_and_private_exam(clients):
    owner_client, other_client, owner = clients
    response = upload(owner_client)
    assert response.status_code == 201, response.data
    body = response.data
    assert body["status"] == "NEEDS_REVIEW"
    assert body["report"] == {"valid": 1, "skipped": 0, "issues": []}
    job_id = body["id"]
    job = ImportJob.objects.get(pk=job_id)
    assert job.original_file.name.startswith(f"imports/{job_id}/")
    assert job.uploader == owner
    assert job.timings["assemble_ms"] >= 0
    assert Exam.objects.count() == 0
    assert other_client.get(f"/api/v1/imports/{job_id}/").status_code == 404
    assert other_client.post(f"/api/v1/imports/{job_id}/confirm/").status_code == 404
    assert upload(other_client).status_code == 409
    assert "existing_job_id" not in upload(other_client).data["error"]["details"]

    detail = owner_client.get(f"/api/v1/imports/{job_id}/")
    assert detail.status_code == 200
    assert detail.data["draft"]["sections"][0]["questions"][0]["choices"][1]["is_correct"]
    assert upload(owner_client).data["error"]["details"]["existing_job_id"] == job_id
    confirmed = owner_client.post(f"/api/v1/imports/{job_id}/confirm/")
    assert confirmed.status_code == 200, confirmed.data
    exam = Exam.objects.get(pk=confirmed.data["exam_id"])
    assert exam.owner == owner and exam.visibility == "PRIVATE" and exam.source_kind == "TXT"
    assert str(exam.source_job) == job_id
    assert owner_client.post(f"/api/v1/imports/{job_id}/confirm/").status_code == 409
    assert other_client.get(f"/api/v1/exams/{exam.id}/").status_code == 404


@pytest.mark.django_db
def test_errors_need_review_and_edit_is_audited(clients):
    client, _, _ = clients
    response = upload(client, GOOD.replace("=>B", "=>Z"))
    assert response.status_code == 201
    job_id = response.data["id"]
    assert response.data["report"]["skipped"] == 1
    assert response.data["report"]["issues"][0]["line"] == 7
    assert client.post(f"/api/v1/imports/{job_id}/confirm/").status_code == 400
    assert Exam.objects.count() == 0
    original = client.get(f"/api/v1/imports/{job_id}/").data["draft"]
    assert not original["sections"]
    fixed = upload(client, GOOD + "\n#SUBTITLE: Fixed").data["draft_summary"]
    assert fixed["questions"] == 1
    good_draft = client.get("/api/v1/imports/mine/").data["results"][0]
    good_data = client.get(f"/api/v1/imports/{good_draft['id']}/").data["draft"]
    good_data["metadata"]["title"] = "Đề đã sửa"
    edited = client.patch(f"/api/v1/imports/{job_id}/", {"draft": good_data}, format="json")
    assert edited.status_code == 200, edited.data
    assert edited.data["report"]["skipped"] == 0
    assert ReviewEdit.objects.filter(job_id=job_id, path="/").count() == 1
    assert client.post(f"/api/v1/imports/{job_id}/confirm/").status_code == 200


@pytest.mark.django_db
def test_reject_allows_reupload_and_invalid_file(clients):
    client, _, _ = clients
    assert upload(client, filename="questions.pdf").status_code == 415
    assert upload(client, "\x00garbage").status_code == 415
    assert upload(client, "x" * (2 * 1024 * 1024 + 1)).status_code == 413
    job_id = upload(client).data["id"]
    discarded = client.post(
        f"/api/v1/imports/{job_id}/discard/", {"reason": "Tệp thiếu đáp án"}, format="json"
    )
    assert discarded.status_code == 200
    assert discarded.data["discard_reason"] == "Tệp thiếu đáp án"
    assert ImportJob.objects.get(pk=job_id).error_detail == "Tệp thiếu đáp án"
    assert upload(client).status_code == 201


@pytest.mark.django_db
def test_import_transition_graph(clients):
    client, _, _ = clients
    job = ImportJob.objects.get(pk=upload(client).data["id"])
    for source in ImportJob.Status:
        for destination in ImportJob.Status:
            ImportJob.objects.filter(pk=job.pk).update(status=source)
            job.refresh_from_db()
            if destination in ImportJob.TRANSITIONS[source]:
                assert job.transition(destination).status == destination
            else:
                with pytest.raises(Conflict):
                    job.transition(destination)


@pytest.mark.django_db
def test_daily_quota_and_duplicate_precedence(clients, settings, tmp_path):
    client, _, _ = clients
    settings.IMPORT_DAILY_JOB_LIMIT = 1
    first = upload(client)
    assert first.status_code == 201
    duplicate = upload(client)
    assert duplicate.status_code == 409
    assert duplicate.data["error"]["code"] == "DUPLICATE_FILE"
    other = upload(client, GOOD.replace("2 + 2", "3 + 3"))
    assert other.status_code == 429
    assert other.data["error"]["code"] == "UPLOAD_QUOTA_EXCEEDED"
    assert other.data["error"]["details"]["daily_limit"] == 1
    assert ImportJob.objects.count() == 1
    assert len(list(tmp_path.rglob("original.txt"))) == 1
