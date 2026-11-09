"""Durable per-page document import orchestration; inference remains a separate service."""

import logging
import uuid
from contextlib import contextmanager

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import connection
from pydantic import ValidationError
from testflow_contracts.page import PageSchema

from .document_ingest import DOCX_MIME, MAX_PAGES, DocumentPages, DocumentRejected
from .image_ingest import ImageRejected, normalize_image
from .inference_client import ExtractionError, extract_page
from .models import Draft, ImportJob, PageResult
from .page_assembly import assemble_pages

logger = logging.getLogger("testflow.imports")
IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
DOCUMENT_MIMES = {"application/pdf", DOCX_MIME}
TERMINAL = {
    ImportJob.Status.FAILED,
    ImportJob.Status.REJECTED,
    ImportJob.Status.APPROVED,
    ImportJob.Status.NEEDS_REVIEW,
}


@contextmanager
def _job_lock(job_id: str):
    """Hold one PostgreSQL session lock while a worker processes this job."""
    key = uuid.UUID(job_id).int & ((1 << 63) - 1)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [key])
        acquired = cursor.fetchone()[0]
    try:
        yield acquired
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [key])


def _fail(job: ImportJob, code: str, *, page: PageResult | None = None) -> None:
    if page is not None:
        page.status = PageResult.Status.FAILED
        page.error_code = code
        page.save(update_fields=["status", "error_code", "updated_at"])
    job.transition(ImportJob.Status.FAILED, error_code=code)
    logger.warning("Document import failed", extra={"import_job_id": str(job.id), "stage": code})


def _ingest_image(job: ImportJob) -> None:
    with job.original_file.open("rb") as source:
        normalized = normalize_image(source.read())
    if normalized.source_mime_type != job.mime_type:
        raise ImageRejected("IMAGE_TYPE_MISMATCH")
    page, _ = PageResult.objects.get_or_create(job=job, page_no=1)
    if not page.image:
        page.image.save("page.png", ContentFile(normalized.png), save=True)
    job.page_count = 1
    job.save(update_fields=["page_count", "updated_at"])


def _ingest_document(job: ImportJob) -> None:
    with job.original_file.open("rb") as source:
        raw = source.read()
    with DocumentPages(raw, job.mime_type) as document:
        if job.page_count is not None and job.page_count != document.page_count:
            raise DocumentRejected("DOCUMENT_CHANGED")
        job.page_count = document.page_count
        job.save(update_fields=["page_count", "updated_at"])
        for page_no in range(1, document.page_count + 1):
            page, _ = PageResult.objects.get_or_create(job=job, page_no=page_no)
            if page.image:
                continue
            rendered = document.render(page_no)
            page.text_layer = rendered.text_layer
            page.image.save("page.png", ContentFile(rendered.png), save=False)
            page.save(update_fields=["image", "text_layer", "updated_at"])


def _extract_pages(task, job: ImportJob) -> bool:
    if not job.page_count or job.page_count > MAX_PAGES:
        _fail(job, "PAGE_COUNT_INVALID")
        return False
    for page_no in range(1, job.page_count + 1):
        page = PageResult.objects.filter(job=job, page_no=page_no).first()
        if page is None or not page.image:
            _fail(job, "PAGE_RESULT_MISSING")
            return False
        if page.status in {PageResult.Status.DONE, PageResult.Status.FAILED}:
            continue
        if page.attempts >= 3:
            page.status = PageResult.Status.FAILED
            page.error_code = page.error_code or "EXTRACTION_ATTEMPTS_EXHAUSTED"
            page.save(update_fields=["status", "error_code", "updated_at"])
            continue
        if not settings.IMPORT_INFERENCE_URL.startswith(("http://", "https://")):
            _fail(job, "OCR_PROVIDER_UNCONFIGURED", page=page)
            return False
        page.attempts += 1
        page.status = PageResult.Status.PENDING
        page.error_code = ""
        page.save(update_fields=["attempts", "status", "error_code", "updated_at"])
        try:
            inputs = {"text_layer": page.text_layer} if page.text_layer else {}
            if not inputs:
                with page.image.open("rb") as image:
                    inputs["image_png"] = image.read()
            extraction = extract_page(
                service_url=settings.IMPORT_INFERENCE_URL,
                token=settings.IMPORT_INFERENCE_TOKEN,
                page_no=page_no,
                subject_hint=job.subject_hint,
                **inputs,
            )
        except ExtractionError as exc:
            if exc.retryable and page.attempts < 3 and task.request.retries < task.max_retries:
                page.error_code = exc.code
                page.save(update_fields=["error_code", "updated_at"])
                raise task.retry(exc=exc, countdown=2 ** (page.attempts - 1)) from exc
            page.status = PageResult.Status.FAILED
            page.error_code = exc.code
            page.save(update_fields=["status", "error_code", "updated_at"])
            logger.warning(
                "Document page extraction failed",
                extra={"import_job_id": str(job.id), "page_no": page_no, "stage": exc.code},
            )
            continue
        except OSError:
            _fail(job, "PAGE_IMAGE_UNAVAILABLE", page=page)
            return False
        page.source = extraction.source
        page.raw_output = extraction.raw_output
        page.page_json = extraction.page.model_dump(mode="json")
        page.provider_name = extraction.provider_name
        page.model_name = extraction.model_name
        page.model_version = extraction.model_version
        page.artifact_digest = extraction.artifact_digest
        page.latency_ms = extraction.latency_ms
        page.status = PageResult.Status.DONE
        page.error_code = ""
        page.save()
    return True


def _assemble(job: ImportJob) -> None:
    if not job.page_count or job.page_count > MAX_PAGES:
        _fail(job, "PAGE_COUNT_INVALID")
        return
    pages = list(PageResult.objects.filter(job=job).order_by("page_no"))
    if len(pages) != job.page_count or [page.page_no for page in pages] != list(
        range(1, job.page_count + 1)
    ):
        _fail(job, "PAGE_RESULT_MISSING")
        return
    validated = []
    failed = []
    for page in pages:
        if page.status == PageResult.Status.FAILED:
            failed.append(
                {
                    "page_no": page.page_no,
                    "code": "E_PAGE_FAILED",
                    "message": "Trang chưa được trích xuất; cần thử lại trước khi xác nhận đề.",
                    "severity": "ERROR",
                }
            )
            continue
        if page.status != PageResult.Status.DONE:
            _fail(job, "PAGE_RESULT_INCOMPLETE", page=page)
            return
        try:
            result = PageSchema.model_validate(page.page_json)
        except ValidationError:
            _fail(job, "PAGE_RESULT_INVALID", page=page)
            return
        if result.page_no != page.page_no:
            _fail(job, "PAGE_RESULT_INVALID", page=page)
            return
        validated.append(result)
    try:
        outcome = assemble_pages(validated)
    except ValueError:
        logger.exception(
            "Document import assembly rejected extracted pages",
            extra={"import_job_id": str(job.id), "stage": "assemble"},
        )
        _fail(job, "ASSEMBLY_INVALID")
        return
    data = outcome.draft.model_dump(mode="json")
    Draft.objects.update_or_create(
        job=job,
        defaults={
            "schema_version": outcome.draft.schema_version,
            "data": data,
            "original_data": data,
            "warnings": [issue.__dict__ for issue in outcome.issues] + failed,
            "skipped_count": outcome.skipped,
        },
    )
    job.transition(ImportJob.Status.NEEDS_REVIEW)
    logger.info(
        "Document import assembled", extra={"import_job_id": str(job.id), "stage": "assemble"}
    )


def _process_job(task, job_id: str, *, document: bool) -> None:
    job = ImportJob.objects.get(pk=job_id)
    allowed = DOCUMENT_MIMES if document else IMAGE_MIMES
    if job.source_kind != "OCR" or job.mime_type not in allowed:
        raise ValueError("worker received an incompatible import")
    if job.status in TERMINAL:
        return
    if job.status == ImportJob.Status.UPLOADED:
        job.transition(ImportJob.Status.INGESTING)
    if job.status == ImportJob.Status.INGESTING:
        try:
            if document:
                _ingest_document(job)
            else:
                _ingest_image(job)
        except (DocumentRejected, ImageRejected, OSError) as exc:
            code = (
                exc.code
                if isinstance(exc, (DocumentRejected, ImageRejected))
                else "SOURCE_UNAVAILABLE"
            )
            _fail(job, code)
            return
        job.transition(ImportJob.Status.EXTRACTING)
    if job.status == ImportJob.Status.EXTRACTING:
        if not _extract_pages(task, job):
            return
        job.transition(ImportJob.Status.ASSEMBLING)
    if job.status == ImportJob.Status.ASSEMBLING:
        _assemble(job)


@shared_task(bind=True, max_retries=2, acks_late=True)
def process_image_job(self, job_id: str) -> None:
    with _job_lock(job_id) as acquired:
        if acquired:
            _process_job(self, job_id, document=False)


@shared_task(bind=True, max_retries=MAX_PAGES * 2, acks_late=True)
def process_document_job(self, job_id: str) -> None:
    with _job_lock(job_id) as acquired:
        if acquired:
            _process_job(self, job_id, document=True)
