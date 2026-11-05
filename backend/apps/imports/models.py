"""Private import jobs and reviewable drafts."""

import uuid
from typing import ClassVar

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from apps.common.errors import Conflict


def private_upload_path(instance, _filename):
    return f"imports/{instance.id}/original.txt"


class ImportJob(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "UPLOADED"
        INGESTING = "INGESTING"
        EXTRACTING = "EXTRACTING"
        ASSEMBLING = "ASSEMBLING"
        NEEDS_REVIEW = "NEEDS_REVIEW"
        APPROVED = "APPROVED"
        REJECTED = "REJECTED"
        FAILED = "FAILED"

    TRANSITIONS: ClassVar = {
        Status.UPLOADED: {Status.INGESTING, Status.ASSEMBLING, Status.FAILED},
        Status.INGESTING: {Status.EXTRACTING, Status.ASSEMBLING, Status.FAILED},
        Status.EXTRACTING: {Status.ASSEMBLING, Status.FAILED},
        Status.ASSEMBLING: {Status.NEEDS_REVIEW, Status.FAILED},
        Status.NEEDS_REVIEW: {Status.APPROVED, Status.REJECTED, Status.FAILED},
        Status.APPROVED: set(),
        Status.REJECTED: set(),
        Status.FAILED: set(),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    original_file = models.FileField(upload_to=private_upload_path)
    original_filename = models.CharField(max_length=255)
    sha256 = models.CharField(max_length=64, db_index=True)
    mime_type = models.CharField(max_length=100)
    file_size = models.BigIntegerField()
    page_count = models.PositiveSmallIntegerField(null=True)
    source_kind = models.CharField(max_length=4)
    subject_hint = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPLOADED)
    status_changed_at = models.DateTimeField(default=timezone.now)
    error_code = models.CharField(max_length=50, blank=True)
    error_detail = models.TextField(blank=True)
    pipeline_version = models.CharField(max_length=40, blank=True)
    timings = models.JSONField(default=dict)
    exam_id = models.UUIDField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["sha256"],
                condition=~models.Q(status__in=["REJECTED", "FAILED"]),
                name="imports_active_sha256_unique",
            ),
        )
        indexes = (
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["uploader", "created_at"]),
        )

    def transition(self, to, *, error_code="", error_detail=""):
        """Lock and validate every state change; return the refreshed job."""
        with transaction.atomic():
            locked = type(self).objects.select_for_update().get(pk=self.pk)
            if to not in self.TRANSITIONS[locked.status]:
                raise Conflict(
                    "IMPORT_STATE_CONFLICT", "Trạng thái nhập đề không cho phép thao tác này."
                )
            locked.status = to
            locked.status_changed_at = timezone.now()
            locked.error_code = error_code
            locked.error_detail = error_detail
            locked.save(
                update_fields=[
                    "status",
                    "status_changed_at",
                    "error_code",
                    "error_detail",
                    "updated_at",
                ]
            )
            self.status = locked.status
            self.status_changed_at = locked.status_changed_at
            self.error_code = locked.error_code
            self.error_detail = locked.error_detail
            return locked


class Draft(models.Model):
    job = models.OneToOneField(ImportJob, on_delete=models.CASCADE, related_name="draft")
    schema_version = models.PositiveSmallIntegerField()
    data = models.JSONField()
    original_data = models.JSONField()
    warnings = models.JSONField(default=list)
    skipped_count = models.PositiveIntegerField(default=0)
    priority_score = models.FloatField(default=0)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)


class ReviewEdit(models.Model):
    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="edits")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    path = models.CharField(max_length=200)
    before = models.JSONField()
    after = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
