"""Durable image import worker; extraction stays outside the application database."""

import logging

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from testflow_contracts.page import PageSchema

from .image_ingest import ImageRejected, normalize_image
from .inference_client import ExtractionError, extract_page
from .models import Draft, ImportJob, PageResult
from .page_assembly import assemble_pages

logger = logging.getLogger("testflow.imports")


def _fail(job: ImportJob, code: str, *, page: PageResult | None = None) -> None:
    if page is not None:
        page.status = PageResult.Status.FAILED
        page.error_code = code
        page.save(update_fields=["status", "error_code", "updated_at"])
    job.transition(ImportJob.Status.FAILED, error_code=code)
    logger.warning("Image import failed", extra={"import_job_id": str(job.id), "stage": code})


@shared_task(bind=True, max_retries=2)
def process_image_job(self, job_id: str) -> None:
    """Resume from persisted page state; retry only transient inference errors."""
    job = ImportJob.objects.get(pk=job_id)
    if job.source_kind != "OCR" or job.mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("image worker received an incompatible import")
    if job.status in {
        ImportJob.Status.FAILED,
        ImportJob.Status.REJECTED,
        ImportJob.Status.APPROVED,
        ImportJob.Status.NEEDS_REVIEW,
    }:
        return

    if job.status == ImportJob.Status.UPLOADED:
        job.transition(ImportJob.Status.INGESTING)
    if job.status == ImportJob.Status.INGESTING:
        try:
            with job.original_file.open("rb") as source:
                normalized = normalize_image(source.read())
            if normalized.source_mime_type != job.mime_type:
                raise ImageRejected("IMAGE_TYPE_MISMATCH")
        except (ImageRejected, OSError) as exc:
            _fail(job, exc.code if isinstance(exc, ImageRejected) else "SOURCE_UNAVAILABLE")
            return
        page, _ = PageResult.objects.get_or_create(job=job, page_no=1)
        if not page.image:
            page.image.save("page.png", ContentFile(normalized.png), save=True)
        job.page_count = 1
        job.save(update_fields=["page_count", "updated_at"])
        job.transition(ImportJob.Status.EXTRACTING)

    page = PageResult.objects.get(job=job, page_no=1)
    if job.status == ImportJob.Status.EXTRACTING:
        if page.status != PageResult.Status.DONE:
            page.attempts += 1
            page.status = PageResult.Status.PENDING
            page.error_code = ""
            page.save(update_fields=["attempts", "status", "error_code", "updated_at"])
            try:
                with page.image.open("rb") as image:
                    extraction = extract_page(
                        service_url=settings.IMPORT_INFERENCE_URL,
                        token=settings.IMPORT_INFERENCE_TOKEN,
                        image_png=image.read(),
                        page_no=1,
                        subject_hint=job.subject_hint,
                    )
            except ExtractionError as exc:
                if exc.retryable and self.request.retries < self.max_retries:
                    page.error_code = exc.code
                    page.save(update_fields=["error_code", "updated_at"])
                    raise self.retry(exc=exc, countdown=2**self.request.retries) from exc
                _fail(job, exc.code, page=page)
                return
            except OSError:
                _fail(job, "PAGE_IMAGE_UNAVAILABLE", page=page)
                return
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
        job.transition(ImportJob.Status.ASSEMBLING)

    if job.status == ImportJob.Status.ASSEMBLING:
        outcome = assemble_pages([PageSchema.model_validate(page.page_json)])
        data = outcome.draft.model_dump(mode="json")
        Draft.objects.update_or_create(
            job=job,
            defaults={
                "schema_version": outcome.draft.schema_version,
                "data": data,
                "original_data": data,
                "warnings": [issue.__dict__ for issue in outcome.issues],
                "skipped_count": outcome.skipped,
            },
        )
        job.transition(ImportJob.Status.NEEDS_REVIEW)
        logger.info(
            "Image import assembled",
            extra={"import_job_id": str(job.id), "stage": "assemble"},
        )
