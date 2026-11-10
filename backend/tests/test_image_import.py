"""Synthetic end-to-end image import evidence, without a production OCR claim."""

import json
from io import BytesIO
from urllib.error import URLError

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.catalog.models import Asset, Exam, QuestionAsset, School, Subject, Visibility
from apps.catalog.services import make_private
from apps.imports import inference_client, tasks
from apps.imports.models import Draft, ImportJob, PageResult, ReviewEdit


def image_file():
    output = BytesIO()
    Image.new("RGB", (64, 64), "white").save(output, format="PNG")
    return SimpleUploadedFile("exam.png", output.getvalue(), content_type="image/png")


@pytest.fixture
def context(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.IMPORT_INFERENCE_URL = "http://ocr.internal:8001"
    settings.IMPORT_INFERENCE_TOKEN = "test-token"
    Subject.objects.update_or_create(code="toan", defaults={"name": "Toán", "levels": ["THPT"]})
    School.objects.get_or_create(name="Trường Mẫu")
    owner = get_user_model().objects.create_user(
        "image_owner", email="image_owner@example.com", password="HardToGuess#2026"
    )
    client = APIClient()
    client.force_authenticate(owner)
    return client, owner


def upload(client):
    return client.post(
        "/api/v1/imports/image/",
        {"file": image_file(), "subject_hint": "Toán"},
        format="multipart",
    )


@pytest.mark.django_db
def test_image_upload_worker_review_and_confirm(
    context, monkeypatch, django_capture_on_commit_callbacks
):
    client, owner = context
    dispatched = []
    monkeypatch.setattr(tasks.process_image_job, "delay", lambda job_id: dispatched.append(job_id))

    with django_capture_on_commit_callbacks(execute=True):
        uploaded = upload(client)
    assert uploaded.status_code == 202, uploaded.data
    job_id = uploaded.data["id"]
    assert dispatched == [job_id]
    job = ImportJob.objects.get(pk=job_id)
    assert job.status == ImportJob.Status.UPLOADED
    assert job.original_file.name == f"imports/{job_id}/original.png"
    assert job.source_kind == "OCR"

    def fake_urlopen(request, timeout):
        assert request.full_url == "http://ocr.internal:8001/v1/extract-page"
        assert request.get_header("Authorization") == "Bearer test-token"
        assert json.loads(request.data)["page_no"] == 1
        response = {
            "page_json": {
                "schema_version": 1,
                "page_no": 1,
                "blocks": [
                    {
                        "type": "question",
                        "number_label": "Câu 1",
                        "kind": "MCQ",
                        "text": "Hai cộng hai bằng mấy?",
                        "choices": [
                            {"label": "A", "text": "Ba"},
                            {"label": "B", "text": "Bốn"},
                        ],
                    }
                ],
            },
            "model_name": "fixture-model",
            "source": "VLM",
            "artifact_digest": "a" * 64,
        }
        return BytesIO(json.dumps(response).encode("utf-8"))

    monkeypatch.setattr(inference_client, "urlopen", fake_urlopen)
    tasks.process_image_job.apply(args=(job_id,), throw=True)
    job.refresh_from_db()
    assert job.status == ImportJob.Status.NEEDS_REVIEW
    assert job.page_count == 1
    page = PageResult.objects.get(job=job, page_no=1)
    assert page.status == PageResult.Status.DONE
    assert page.source == PageResult.Source.VLM
    assert page.model_name == "fixture-model"
    assert page.artifact_digest == "a" * 64
    assert page.image.name == f"imports/{job_id}/pages/1.png"
    assert page.page_json["blocks"][0]["text"] == "Hai cộng hai bằng mấy?"
    assert client.post(f"/api/v1/imports/{job_id}/confirm/").status_code == 400

    draft = client.get(f"/api/v1/imports/{job_id}/").data["draft"]
    draft["metadata"].update(
        {
            "title": "Đề kiểm tra mẫu",
            "level": "THPT",
            "grade": 12,
            "subject": "toan",
            "exam_type": "KIEM_TRA",
            "schools": ["Trường Mẫu"],
        }
    )
    draft["sections"][0]["questions"][0]["choices"][1]["is_correct"] = True
    edited = client.patch(f"/api/v1/imports/{job_id}/", {"draft": draft}, format="json")
    assert edited.status_code == 200, edited.data
    confirmed = client.post(f"/api/v1/imports/{job_id}/confirm/")
    assert confirmed.status_code == 200, confirmed.data
    exam = Exam.objects.get(pk=confirmed.data["exam_id"])
    assert exam.owner_id == owner.id
    assert exam.source_kind == "OCR"


@pytest.mark.django_db
def test_image_upload_rejects_unconfigured_and_disguised_content(context, settings):
    client, _ = context
    settings.IMPORT_INFERENCE_URL = ""
    unavailable = upload(client)
    assert unavailable.status_code == 502
    assert unavailable.data["error"]["code"] == "OCR_UNAVAILABLE"
    assert ImportJob.objects.count() == 0

    settings.IMPORT_INFERENCE_URL = "http://ocr.internal:8001"
    disguised = client.post(
        "/api/v1/imports/image/",
        {"file": SimpleUploadedFile("exam.png", b"not an image")},
        format="multipart",
    )
    assert disguised.status_code == 415
    assert ImportJob.objects.count() == 0


@pytest.mark.django_db
def test_worker_rejects_corrupt_image_after_magic_bytes(
    context, monkeypatch, django_capture_on_commit_callbacks
):
    client, _ = context
    monkeypatch.setattr(tasks.process_image_job, "delay", lambda job_id: None)
    with django_capture_on_commit_callbacks(execute=True):
        uploaded = client.post(
            "/api/v1/imports/image/",
            {"file": SimpleUploadedFile("corrupt.png", b"\x89PNG\r\n\x1a\ncorrupt")},
            format="multipart",
        )
    assert uploaded.status_code == 202
    tasks.process_image_job.apply(args=(uploaded.data["id"],), throw=True)
    job = ImportJob.objects.get(pk=uploaded.data["id"])
    assert job.status == ImportJob.Status.FAILED
    assert job.error_code == "IMAGE_DECODE_FAILED"
    assert not PageResult.objects.filter(job=job).exists()


@pytest.mark.django_db
def test_worker_marks_provider_configuration_loss_as_failure(
    context, settings, monkeypatch, django_capture_on_commit_callbacks
):
    client, _ = context
    monkeypatch.setattr(tasks.process_image_job, "delay", lambda job_id: None)
    with django_capture_on_commit_callbacks(execute=True):
        uploaded = upload(client)
    assert uploaded.status_code == 202
    settings.IMPORT_INFERENCE_URL = ""

    tasks.process_image_job.apply(args=(uploaded.data["id"],), throw=True)
    job = ImportJob.objects.get(pk=uploaded.data["id"])
    page = PageResult.objects.get(job=job, page_no=1)
    assert job.status == ImportJob.Status.FAILED
    assert job.error_code == page.error_code == "OCR_PROVIDER_UNCONFIGURED"


@pytest.mark.django_db
def test_worker_fails_invalid_persisted_page_instead_of_stranding_job(context):
    _, owner = context
    job = ImportJob.objects.create(
        uploader=owner,
        original_file="imports/invalid/original.png",
        original_filename="exam.png",
        sha256="c" * 64,
        mime_type="image/png",
        file_size=8,
        source_kind="OCR",
        status=ImportJob.Status.ASSEMBLING,
        page_count=1,
    )
    page = PageResult.objects.create(
        job=job,
        page_no=1,
        status=PageResult.Status.DONE,
        page_json={"schema_version": 1, "page_no": 1, "blocks": "invalid"},
    )

    tasks.process_image_job.apply(args=(str(job.id),), throw=True)

    job.refresh_from_db()
    page.refresh_from_db()
    assert job.status == ImportJob.Status.FAILED
    assert job.error_code == page.error_code == "PAGE_RESULT_INVALID"
    assert page.status == PageResult.Status.FAILED
    assert not Draft.objects.filter(job=job).exists()


@pytest.mark.django_db
def test_worker_records_assembly_rejection_instead_of_stranding_job(context, monkeypatch):
    _, owner = context
    job = ImportJob.objects.create(
        uploader=owner,
        original_file="imports/assembly/original.png",
        original_filename="exam.png",
        sha256="d" * 64,
        mime_type="image/png",
        file_size=8,
        source_kind="OCR",
        status=ImportJob.Status.ASSEMBLING,
        page_count=1,
    )
    PageResult.objects.create(
        job=job,
        page_no=1,
        status=PageResult.Status.DONE,
        page_json={"schema_version": 1, "page_no": 1, "blocks": []},
    )

    def reject_assembly(_pages):
        raise ValueError("synthetic assembly rejection")

    monkeypatch.setattr(tasks, "assemble_pages", reject_assembly)
    tasks.process_image_job.apply(args=(str(job.id),), throw=True)

    job.refresh_from_db()
    assert job.status == ImportJob.Status.FAILED
    assert job.error_code == "ASSEMBLY_INVALID"
    assert not Draft.objects.filter(job=job).exists()


@pytest.mark.django_db
def test_worker_exhausts_transient_provider_retries(
    context, monkeypatch, django_capture_on_commit_callbacks
):
    client, _ = context
    monkeypatch.setattr(tasks.process_image_job, "delay", lambda job_id: None)
    with django_capture_on_commit_callbacks(execute=True):
        uploaded = upload(client)
    attempts = []

    def unavailable(_request, timeout):
        attempts.append(timeout)
        raise URLError("synthetic outage")

    monkeypatch.setattr(inference_client, "urlopen", unavailable)
    tasks.process_image_job.apply(args=(uploaded.data["id"],), throw=False)

    job = ImportJob.objects.get(pk=uploaded.data["id"])
    page = PageResult.objects.get(job=job, page_no=1)
    assert len(attempts) == 3
    assert page.attempts == 3
    assert job.status == ImportJob.Status.NEEDS_REVIEW
    assert page.status == PageResult.Status.FAILED
    assert page.error_code == "INFERENCE_UNAVAILABLE"
    assert any(issue["code"] == "E_PAGE_FAILED" for issue in job.draft.warnings)
    assert client.post(f"/api/v1/imports/{job.id}/confirm/").status_code == 400

    retry_url = f"/api/v1/imports/{job.id}/pages/1/retry/"
    dispatched = []
    monkeypatch.setattr(tasks.process_image_job, "delay", lambda job_id: dispatched.append(job_id))
    with django_capture_on_commit_callbacks(execute=True):
        retried = client.post(retry_url)
    assert retried.status_code == 202
    assert retried.data["status"] == ImportJob.Status.EXTRACTING
    assert "draft" not in retried.data
    assert dispatched == [str(job.id)]

    def recovered(_request, timeout):
        return BytesIO(
            json.dumps(
                {
                    "page_json": {"schema_version": 1, "page_no": 1, "blocks": []},
                    "source": "VLM",
                    "model_name": "synthetic-recovery",
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr(inference_client, "urlopen", recovered)
    tasks.process_image_job.apply(args=(str(job.id),), throw=True)
    job.refresh_from_db()
    page.refresh_from_db()
    assert job.status == ImportJob.Status.NEEDS_REVIEW
    assert page.status == PageResult.Status.DONE
    assert not any(issue["code"] == "E_PAGE_FAILED" for issue in job.draft.warnings)


@pytest.mark.django_db(transaction=True)
def test_page_image_is_private_to_owner_and_reviewer(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    User = get_user_model()
    owner = User.objects.create_user(
        "page_image_owner", email="page_image_owner@example.com", password="HardToGuess#2026"
    )
    other = User.objects.create_user(
        "page_image_other", email="page_image_other@example.com", password="HardToGuess#2026"
    )
    reviewer = User.objects.create_user(
        "page_image_reviewer", email="page_image_reviewer@example.com", password="HardToGuess#2026"
    )
    reviewer.groups.add(Group.objects.get_or_create(name="Reviewer")[0])
    job = ImportJob.objects.create(
        uploader=owner,
        original_file="imports/private/original.png",
        original_filename="exam.png",
        sha256="b" * 64,
        mime_type="image/png",
        file_size=8,
        source_kind="OCR",
    )
    page = PageResult(job=job, page_no=1)
    page.image.save("page.png", image_file(), save=True)
    url = f"/api/v1/imports/{job.id}/pages/1/image/"

    def request(actor):
        api = APIClient()
        if actor:
            api.force_authenticate(actor)
        return api.get(url)

    assert request(None).status_code == 401
    assert request(other).status_code == 404
    for actor in (owner, reviewer):
        response = request(actor)
        assert response.status_code == 200
        assert b"".join(response.streaming_content).startswith(b"\x89PNG")
        assert response["Cache-Control"] == "private, no-store"
        assert response["X-Content-Type-Options"] == "nosniff"
        response.close()
    page.image.delete(save=False)
    assert request(owner).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_queue_failure_returns_error_and_releases_duplicate_reservation(
    settings, tmp_path, monkeypatch
):
    settings.MEDIA_ROOT = tmp_path
    settings.IMPORT_INFERENCE_URL = "http://ocr.internal:8001"
    owner = get_user_model().objects.create_user(
        "queue_owner", email="queue_owner@example.com", password="HardToGuess#2026"
    )
    client = APIClient()
    client.force_authenticate(owner)

    def unavailable(job_id):
        raise RuntimeError("synthetic queue outage")

    monkeypatch.setattr(tasks.process_image_job, "delay", unavailable)
    response = upload(client)
    assert response.status_code == 502
    assert response.data["error"]["code"] == "QUEUE_UNAVAILABLE"
    job = ImportJob.objects.get()
    assert job.status == ImportJob.Status.FAILED
    assert job.error_code == "QUEUE_UNAVAILABLE"

    dispatched = []
    monkeypatch.setattr(tasks.process_image_job, "delay", lambda job_id: dispatched.append(job_id))
    retried = upload(client)
    assert retried.status_code == 202
    assert dispatched == [retried.data["id"]]


@pytest.mark.django_db
def test_page_retry_is_owner_scoped_and_preserves_manual_review(context):
    client, owner = context
    job = ImportJob.objects.create(
        uploader=owner,
        original_file="imports/retry/original.png",
        original_filename="retry.png",
        sha256="f" * 64,
        mime_type="image/png",
        file_size=8,
        source_kind="OCR",
        status=ImportJob.Status.NEEDS_REVIEW,
        page_count=1,
    )
    PageResult.objects.create(job=job, page_no=1, status=PageResult.Status.FAILED)
    url = f"/api/v1/imports/{job.id}/pages/1/retry/"
    outsider = get_user_model().objects.create_user(
        "retry_outsider", email="retry_outsider@example.com", password="HardToGuess#2026"
    )
    other = APIClient()
    other.force_authenticate(outsider)
    assert other.post(url).status_code == 404
    ReviewEdit.objects.create(job=job, reviewer=owner, path="/", before={}, after={})
    response = client.post(url)
    assert response.status_code == 409
    assert response.data["error"]["code"] == "IMPORT_REVIEW_EDITED"
    job.refresh_from_db()
    assert job.status == ImportJob.Status.NEEDS_REVIEW


@pytest.mark.django_db
def test_worker_loss_recovery_has_persisted_page_attempt_limit(context, monkeypatch):
    _, owner = context
    job = ImportJob.objects.create(
        uploader=owner,
        original_file="imports/recovery/original.png",
        original_filename="recovery.png",
        sha256="1" * 64,
        mime_type="image/png",
        file_size=100,
        source_kind="OCR",
        status=ImportJob.Status.EXTRACTING,
        page_count=1,
    )
    page = PageResult.objects.create(job=job, page_no=1, attempts=3)
    page.image.save("page.png", image_file(), save=True)

    def unexpected(_request, timeout):
        raise AssertionError("exhausted page must not call inference again")

    monkeypatch.setattr(inference_client, "urlopen", unexpected)
    tasks.process_image_job.apply(args=(str(job.id),), throw=True)
    job.refresh_from_db()
    page.refresh_from_db()
    assert job.status == ImportJob.Status.NEEDS_REVIEW
    assert page.status == PageResult.Status.FAILED
    assert page.attempts == 3
    assert page.error_code == "EXTRACTION_ATTEMPTS_EXHAUSTED"
    assert any(issue["code"] == "E_PAGE_FAILED" for issue in job.draft.warnings)


@pytest.mark.django_db
def test_figure_is_cropped_and_attached_only_at_private_confirmation(
    context, monkeypatch, django_capture_on_commit_callbacks
):
    client, owner = context
    monkeypatch.setattr(tasks.process_image_job, "delay", lambda _job_id: None)
    with django_capture_on_commit_callbacks(execute=True):
        uploaded = upload(client)
    job_id = uploaded.data["id"]

    def figure_response(_request, timeout):
        return BytesIO(
            json.dumps(
                {
                    "page_json": {
                        "schema_version": 1,
                        "page_no": 1,
                        "figures": [{"id": "fig-1", "bbox": [0.1, 0.1, 0.5, 0.5]}],
                        "blocks": [
                            {
                                "type": "question",
                                "number_label": "Câu 1",
                                "kind": "MCQ",
                                "text": "Chọn hình phù hợp?",
                                "choices": [
                                    {"label": "A", "text": "Một"},
                                    {"label": "B", "text": "Hai"},
                                ],
                                "figure_refs": ["fig-1"],
                            },
                            {
                                "type": "answer_key",
                                "entries": [{"number_label": "Câu 1", "answer": "B"}],
                            },
                        ],
                    },
                    "source": "VLM",
                    "model_name": "synthetic-figure",
                }
            ).encode("utf-8")
        )

    monkeypatch.setattr(inference_client, "urlopen", figure_response)
    tasks.process_image_job.apply(args=(job_id,), throw=True)
    job = ImportJob.objects.get(pk=job_id)
    assert job.status == ImportJob.Status.NEEDS_REVIEW
    assert not any(issue["severity"] == "ERROR" for issue in job.draft.warnings)
    assert Asset.objects.count() == 0

    draft = client.get(f"/api/v1/imports/{job_id}/").data["draft"]
    draft["metadata"].update(
        {
            "title": "Đề kiểm tra hình",
            "level": "THPT",
            "grade": 12,
            "subject": "toan",
            "exam_type": "KIEM_TRA",
            "schools": ["Trường Mẫu"],
        }
    )
    edited = client.patch(f"/api/v1/imports/{job_id}/", {"draft": draft}, format="json")
    assert edited.status_code == 200, edited.data
    confirmed = client.post(f"/api/v1/imports/{job_id}/confirm/")
    assert confirmed.status_code == 200, confirmed.data
    exam = Exam.objects.get(pk=confirmed.data["exam_id"])
    assert exam.owner_id == owner.id
    assert exam.visibility == "PRIVATE"
    link = QuestionAsset.objects.get(question__section__exam=exam)
    assert link.asset.source_job == job.id
    assert link.asset.width > 2 and link.asset.height > 2
    with link.asset.file.open("rb") as image:
        assert image.read(8) == b"\x89PNG\r\n\x1a\n"

    preview = client.get(f"/api/v1/exams/{exam.id}/preview/")
    assert preview.status_code == 200
    assert preview.data["questions"][0]["assets"] == [str(link.asset_id)]

    catalog_asset_url = f"/api/v1/exams/{exam.id}/assets/{link.asset_id}/"
    owner_image = client.get(catalog_asset_url)
    assert owner_image.status_code == 200
    assert b"".join(owner_image.streaming_content).startswith(b"\x89PNG\r\n\x1a\n")

    student = get_user_model().objects.create_user("figure_student")
    student_client = APIClient()
    student_client.force_authenticate(student)
    assert student_client.get(catalog_asset_url).status_code == 404

    Exam.objects.filter(pk=exam.pk).update(visibility=Visibility.PUBLIC)
    created = student_client.post(
        "/api/v1/practice/sessions/",
        {"exam_id": str(exam.id), "mode": "PRACTICE"},
        format="json",
    )
    assert created.status_code == 201, created.data
    assert created.data["sections"][0]["questions"][0]["assets"] == [str(link.asset_id)]
    session_asset_url = f"/api/v1/practice/sessions/{created.data['id']}/assets/{link.asset_id}/"

    make_private(exam.id, owner=owner)
    assert student_client.get(catalog_asset_url).status_code == 404
    session_image = student_client.get(session_asset_url)
    assert session_image.status_code == 200
    assert b"".join(session_image.streaming_content).startswith(b"\x89PNG\r\n\x1a\n")
    assert client.get(session_asset_url).status_code == 404
