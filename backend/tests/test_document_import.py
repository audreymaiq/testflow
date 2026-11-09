"""Document upload through per-page extraction and review, with synthetic inference."""

import json
from io import BytesIO
from urllib.error import URLError

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.imports import document_ingest, inference_client, tasks
from apps.imports.models import ImportJob, PageResult

from .test_document_ingest import docx_bytes, pdf_bytes


@pytest.fixture
def context(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.IMPORT_INFERENCE_URL = "http://extractor.internal:8001"
    owner = get_user_model().objects.create_user(
        "document_owner", email="document_owner@example.com", password="HardToGuess#2026"
    )
    client = APIClient()
    client.force_authenticate(owner)
    return client, owner


def page_response(page_no, source):
    return BytesIO(
        json.dumps(
            {
                "page_json": {
                    "schema_version": 1,
                    "page_no": page_no,
                    "blocks": [
                        {
                            "type": "question",
                            "number_label": f"Câu {page_no}",
                            "kind": "MCQ",
                            "text": f"Nội dung câu {page_no}?",
                            "choices": [
                                {"label": "A", "text": "Một"},
                                {"label": "B", "text": "Hai"},
                            ],
                        }
                    ],
                },
                "source": source,
                "model_name": "synthetic-structured-extractor",
                "artifact_digest": "a" * 64,
            }
        ).encode("utf-8")
    )


@pytest.mark.django_db
def test_mixed_pdf_import_routes_text_and_image_and_resumes(
    context, monkeypatch, django_capture_on_commit_callbacks
):
    client, _ = context
    dispatched = []
    monkeypatch.setattr(
        tasks.process_document_job, "delay", lambda job_id: dispatched.append(job_id)
    )
    content = pdf_bytes(
        pages=2,
        text=["A question on this page with enough searchable text", ""],
    )
    with django_capture_on_commit_callbacks(execute=True):
        uploaded = client.post(
            "/api/v1/imports/document/",
            {"file": SimpleUploadedFile("mixed.pdf", content, content_type="image/png")},
            format="multipart",
        )
    assert uploaded.status_code == 202, uploaded.data
    job_id = uploaded.data["id"]
    assert dispatched == [job_id]
    seen = []

    def fake_urlopen(request, timeout):
        assert timeout == 60
        body = json.loads(request.data)
        page_no = body["page_no"]
        seen.append(page_no)
        if page_no == 2 and seen.count(2) == 1:
            raise URLError("synthetic transient outage")
        if page_no == 1:
            assert "A question on this page" in body["text_layer"]
            assert "image_b64" not in body
            source = "TEXT_LAYER"
        else:
            assert body["image_b64"]
            assert "text_layer" not in body
            source = "VLM"
        return page_response(page_no, source)

    monkeypatch.setattr(inference_client, "urlopen", fake_urlopen)
    tasks.process_document_job.apply(args=(job_id,), throw=False)

    job = ImportJob.objects.get(pk=job_id)
    assert job.status == ImportJob.Status.NEEDS_REVIEW
    assert job.page_count == 2
    assert seen == [1, 2, 2]
    pages = list(PageResult.objects.filter(job=job).order_by("page_no"))
    assert [page.source for page in pages] == ["TEXT_LAYER", "VLM"]
    assert [page.attempts for page in pages] == [1, 2]
    assert pages[0].text_layer and not pages[1].text_layer
    assert all(page.image.name.startswith(f"imports/{job_id}/pages/") for page in pages)
    assert len(job.draft.data["sections"][0]["questions"]) == 2
    assert client.get(f"/api/v1/imports/{job_id}/pages/2/image/").status_code == 200


@pytest.mark.django_db
def test_docx_conversion_and_corrupt_pdf_failure(
    context, monkeypatch, django_capture_on_commit_callbacks
):
    client, _ = context
    monkeypatch.setattr(tasks.process_document_job, "delay", lambda _job_id: None)

    def converted(_command, *, cwd, capture_output, timeout, check):
        (cwd / "output" / "source.pdf").write_bytes(pdf_bytes())
        return type("Result", (), {"returncode": 0})()

    monkeypatch.setattr(document_ingest.subprocess, "run", converted)
    monkeypatch.setattr(
        inference_client,
        "urlopen",
        lambda request, timeout: page_response(json.loads(request.data)["page_no"], "TEXT_LAYER"),
    )
    with django_capture_on_commit_callbacks(execute=True):
        uploaded = client.post(
            "/api/v1/imports/document/",
            {"file": SimpleUploadedFile("source.docx", docx_bytes())},
            format="multipart",
        )
    assert uploaded.status_code == 202, uploaded.data
    tasks.process_document_job.apply(args=(uploaded.data["id"],), throw=True)
    assert ImportJob.objects.get(pk=uploaded.data["id"]).status == ImportJob.Status.NEEDS_REVIEW

    with django_capture_on_commit_callbacks(execute=True):
        corrupt = client.post(
            "/api/v1/imports/document/",
            {"file": SimpleUploadedFile("broken.pdf", b"%PDF-corrupt")},
            format="multipart",
        )
    assert corrupt.status_code == 202
    tasks.process_document_job.apply(args=(corrupt.data["id"],), throw=True)
    failed = ImportJob.objects.get(pk=corrupt.data["id"])
    assert failed.status == ImportJob.Status.FAILED
    assert failed.error_code == "PDF_INVALID"
