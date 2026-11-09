"""Requeue stale document imports after lost workers or broker delivery."""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.imports.document_ingest import DOCX_MIME
from apps.imports.models import ImportJob
from apps.imports.tasks import process_document_job, process_image_job

logger = logging.getLogger("testflow.imports")


class Command(BaseCommand):
    help = "Requeue stale OCR import jobs whose worker has not completed."

    def add_arguments(self, parser):
        parser.add_argument("--older-than-minutes", type=int, default=5)
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        minutes = options["older_than_minutes"]
        limit = options["limit"]
        if minutes < 1 or not 1 <= limit <= 1000:
            raise ValueError("older-than-minutes must be positive; limit must be 1..1000")
        cutoff = timezone.now() - timedelta(minutes=minutes)
        pending = (
            ImportJob.objects.filter(
                source_kind="OCR",
                status__in=[
                    ImportJob.Status.UPLOADED,
                    ImportJob.Status.INGESTING,
                    ImportJob.Status.EXTRACTING,
                    ImportJob.Status.ASSEMBLING,
                ],
                updated_at__lt=cutoff,
            )
            .order_by("updated_at")
            .values_list("id", flat=True)[:limit]
        )
        count = 0
        for job_id in list(pending):
            with transaction.atomic():
                job = (
                    ImportJob.objects.select_for_update(skip_locked=True).filter(pk=job_id).first()
                )
                if job is None or job.updated_at >= cutoff:
                    continue
                job.save(update_fields=["updated_at"])
            worker = (
                process_document_job
                if job.mime_type in {"application/pdf", DOCX_MIME}
                else process_image_job
            )
            try:
                worker.delay(str(job_id))
            except Exception:
                logger.exception(
                    "Import recovery queue unavailable", extra={"import_job_id": str(job_id)}
                )
            else:
                count += 1
        self.stdout.write(f"Requeued {count} import jobs")
