"""Per-page persistence for resumable, model-neutral document imports."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.imports.models import ImportJob, PageResult, private_page_path


@pytest.mark.django_db
def test_page_result_tracks_extractor_output_and_retries():
    uploader = get_user_model().objects.create_user(
        "page_owner", email="page_owner@example.com", password="HardToGuess#2026"
    )
    job = ImportJob.objects.create(
        uploader=uploader,
        original_file="imports/private/original.pdf",
        original_filename="exam.pdf",
        sha256="a" * 64,
        mime_type="application/pdf",
        file_size=10,
        source_kind="OCR",
    )
    page = PageResult.objects.create(job=job, page_no=1)
    assert page.status == PageResult.Status.PENDING
    assert page.attempts == 0
    assert page.raw_output == page.page_json == {}
    assert private_page_path(page, "untrusted.jpg") == f"imports/{job.id}/pages/1.png"

    page.source = PageResult.Source.VLM
    page.status = PageResult.Status.DONE
    page.attempts = 2
    page.provider_name = "internal-service"
    page.model_name = "evaluated-extractor"
    page.model_version = "v1"
    page.artifact_digest = "b" * 64
    page.latency_ms = 240
    page.raw_output = {"text": "raw"}
    page.page_json = {"schema_version": 1, "page_no": 1, "blocks": []}
    page.save()
    page.refresh_from_db()
    assert page.job_id == job.id
    assert page.raw_output == {"text": "raw"}
    assert page.page_json["page_no"] == 1
    assert page.provider_name == "internal-service"
    assert page.artifact_digest == "b" * 64
    assert job.pages.count() == 1


@pytest.mark.django_db
def test_page_result_rejects_duplicate_or_zero_page_number():
    uploader = get_user_model().objects.create_user(
        "page_guard", email="page_guard@example.com", password="HardToGuess#2026"
    )
    job = ImportJob.objects.create(
        uploader=uploader,
        original_file="imports/private/original.pdf",
        original_filename="exam.pdf",
        sha256="c" * 64,
        mime_type="application/pdf",
        file_size=10,
        source_kind="OCR",
    )
    PageResult.objects.create(job=job, page_no=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        PageResult.objects.create(job=job, page_no=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        PageResult.objects.create(job=job, page_no=0)
    assert job.pages.count() == 1
