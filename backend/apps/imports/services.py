"""Import upload, draft review, and atomic confirmation."""

import hashlib
import logging
from pathlib import PurePath
from time import monotonic

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone
from pydantic import ValidationError as ContractValidationError
from testflow_contracts.exam import ExamDraft

from apps.catalog.services import create_exam
from apps.common.errors import Conflict, NotFound, QuotaExceeded, ValidationFailed

from .models import Draft, ImportJob, ReviewEdit
from .txt_parser import MAX_BYTES, parse_txt

logger = logging.getLogger("testflow.imports")


class FileTooLarge(ValidationFailed):
    status_code = 413


class InvalidFileType(ValidationFailed):
    status_code = 415


def _owned_job(job_id, user, *, lock=False):
    queryset = ImportJob.objects.select_for_update() if lock else ImportJob.objects
    job = queryset.filter(pk=job_id, uploader=user).first()
    if job is None:
        raise NotFound("IMPORT_NOT_FOUND", "Không tìm thấy lần nhập đề.")
    return job


def _issues(job):
    return job.draft.warnings


def report(job):
    issues = _issues(job)
    valid = sum(len(section["questions"]) for section in job.draft.data["sections"])
    return {
        "valid": valid,
        "skipped": job.draft.skipped_count,
        "issues": issues,
    }


def job_payload(job, *, include_draft=False):
    payload = {
        "id": str(job.id),
        "status": job.status,
        "source_kind": job.source_kind,
        "original_filename": job.original_filename,
        "page_count": job.page_count,
        "error_code": job.error_code,
        "exam_id": str(job.exam_id) if job.exam_id else None,
        "created_at": job.created_at.isoformat(),
    }
    if job.status == ImportJob.Status.REJECTED:
        payload["discard_reason"] = job.error_detail
    if hasattr(job, "draft"):
        payload["report"] = report(job)
        payload["draft_summary"] = {
            "title": job.draft.data["metadata"].get("title"),
            "questions": payload["report"]["valid"],
            "chapters": len(job.draft.data["chapters"]),
        }
        if include_draft:
            payload["draft"] = job.draft.data
    return payload


def create_txt_job(upload, *, uploader, duration_mode="FILE", duration_minutes=None):
    started = monotonic()
    if (
        duration_mode not in {"FILE", "TIMED", "UNTIMED"}
        or (
            duration_mode == "TIMED"
            and (duration_minutes is None or not 1 <= duration_minutes <= 300)
        )
        or (duration_mode != "TIMED" and duration_minutes is not None)
    ):
        raise ValidationFailed("DURATION_INVALID", "Thời gian làm bài không hợp lệ.")
    if not upload.name.lower().endswith(".txt"):
        raise InvalidFileType("INVALID_FILE_TYPE", "Chỉ chấp nhận tệp .txt.")
    if upload.size > MAX_BYTES:
        raise FileTooLarge("FILE_TOO_LARGE", "Tệp TXT vượt giới hạn 2 MB.")
    raw = upload.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise FileTooLarge("FILE_TOO_LARGE", "Tệp TXT vượt giới hạn 2 MB.")
    if b"\x00" in raw:
        raise InvalidFileType("INVALID_FILE_TYPE", "Tệp không phải văn bản TXT.")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidFileType("INVALID_FILE_TYPE", "Tệp TXT cần mã hóa UTF-8.") from exc
    digest = hashlib.sha256(raw).hexdigest()
    outcome = parse_txt(content)
    data = outcome.draft.model_dump(mode="json")
    if duration_mode != "FILE":
        data["metadata"]["duration_minutes"] = (
            duration_minutes if duration_mode == "TIMED" else None
        )
    parse_ms = round((monotonic() - started) * 1000, 2)
    filename = PurePath(upload.name.replace("\\", "/")).name[:255]
    job = ImportJob(
        uploader=uploader,
        original_filename=filename,
        sha256=digest,
        mime_type="text/plain; charset=utf-8",
        file_size=len(raw),
        source_kind="TXT",
        timings={"assemble_ms": parse_ms},
    )
    try:
        with transaction.atomic():
            type(uploader).objects.select_for_update().get(pk=uploader.pk)
            existing = (
                ImportJob.objects.filter(sha256=digest)
                .exclude(status__in=[ImportJob.Status.REJECTED, ImportJob.Status.FAILED])
                .first()
            )
            if existing:
                details = (
                    {"existing_job_id": str(existing.id)}
                    if existing.uploader_id == uploader.id
                    else {}
                )
                raise Conflict("DUPLICATE_FILE", "Tệp này đã được nhập.", details)
            local_midnight = timezone.localtime(timezone.now()).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            used = ImportJob.objects.filter(
                uploader=uploader, created_at__gte=local_midnight
            ).count()
            if used >= settings.IMPORT_DAILY_JOB_LIMIT:
                raise QuotaExceeded(
                    "UPLOAD_QUOTA_EXCEEDED",
                    "Bạn đã dùng hết số lượt nhập đề hôm nay.",
                    {"daily_limit": settings.IMPORT_DAILY_JOB_LIMIT},
                )
            job.original_file.save("original.txt", ContentFile(raw), save=False)
            job.save()
            job.transition(ImportJob.Status.ASSEMBLING)
            Draft.objects.create(
                job=job,
                schema_version=outcome.draft.schema_version,
                data=data,
                original_data=data,
                warnings=[issue.__dict__ for issue in outcome.issues],
                skipped_count=outcome.skipped,
            )
            job.transition(ImportJob.Status.NEEDS_REVIEW)
    except Exception as exc:
        if job.original_file.name:
            job.original_file.delete(save=False)
        if isinstance(exc, IntegrityError):
            raise Conflict("DUPLICATE_FILE", "Tệp này đã được nhập.") from exc
        raise
    logger.info(
        "TXT import assembled",
        extra={"import_job_id": str(job.id), "stage": "assemble", "latency_ms": parse_ms},
    )
    return job


@transaction.atomic
def replace_draft(job_id, *, user, data):
    job = _owned_job(job_id, user, lock=True)
    if job.status != ImportJob.Status.NEEDS_REVIEW:
        raise Conflict("IMPORT_STATE_CONFLICT", "Bản nháp không còn cho phép sửa.")
    try:
        validated = ExamDraft.model_validate(data)
    except ContractValidationError as exc:
        raise ValidationFailed(
            "DRAFT_INVALID", "Bản nháp chưa hợp lệ.", exc.errors(include_url=False)
        ) from exc
    draft = job.draft
    before = draft.data
    after = validated.model_dump(mode="json")
    required_count = sum(len(section["questions"]) for section in before["sections"])
    required_count += draft.skipped_count
    after_count = sum(len(section["questions"]) for section in after["sections"])
    if after_count < required_count:
        raise ValidationFailed(
            "DRAFT_QUESTIONS_MISSING", "Bản nháp vẫn thiếu câu hỏi đã bỏ qua khi phân tích."
        )
    draft.data = after
    if job.source_kind == "TXT":
        # TXT parse errors describe skipped source lines. Once the reviewer has
        # restored the missing question count, the edited draft supersedes them.
        draft.warnings = [item for item in draft.warnings if item["severity"] != "ERROR"]
    # OCR errors can describe lost figures, page gaps or conflicting metadata.
    # A generic JSON edit cannot prove those source-level defects were repaired.
    draft.skipped_count = 0
    draft.updated_by = user
    draft.save(update_fields=["data", "warnings", "skipped_count", "updated_by", "updated_at"])
    ReviewEdit.objects.create(job=job, reviewer=user, path="/", before=before, after=after)
    return job


@transaction.atomic
def confirm(job_id, *, user):
    started = monotonic()
    job = _owned_job(job_id, user, lock=True)
    if job.status != ImportJob.Status.NEEDS_REVIEW:
        raise Conflict("IMPORT_STATE_CONFLICT", "Lần nhập đề đã được xử lý.")
    if any(item["severity"] == "ERROR" for item in _issues(job)):
        raise ValidationFailed("DRAFT_HAS_ERRORS", "Cần sửa lỗi bản nháp trước khi lưu đề.")
    draft = ExamDraft.model_validate(job.draft.data)
    exam = create_exam(draft, owner=user, source_kind=job.source_kind, source_job=job.id)
    job.exam_id = exam.id
    job.save(update_fields=["exam_id", "updated_at"])
    job.transition(ImportJob.Status.APPROVED)
    logger.info(
        "Import confirmed",
        extra={
            "import_job_id": str(job.id),
            "stage": "confirm",
            "latency_ms": round((monotonic() - started) * 1000, 2),
        },
    )
    return exam


@transaction.atomic
def discard(job_id, *, user, reason=""):
    job = _owned_job(job_id, user, lock=True)
    if job.status != ImportJob.Status.NEEDS_REVIEW:
        raise Conflict("IMPORT_STATE_CONFLICT", "Lần nhập đề đã được xử lý.")
    job.transition(ImportJob.Status.REJECTED, error_detail=reason)
    return job
