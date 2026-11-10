"""Import upload, draft review, and atomic confirmation."""

import hashlib
import logging
import re
from pathlib import PurePath
from time import monotonic

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone
from pydantic import ValidationError as ContractValidationError
from testflow_contracts.exam import ExamDraft
from testflow_contracts.page import PageSchema

from apps.catalog.services import create_exam, is_reviewer
from apps.common.errors import (
    Conflict,
    ExternalServiceError,
    NotFound,
    QuotaExceeded,
    ValidationFailed,
)

from .document_ingest import DOCX_MIME, MAX_DOCUMENT_BYTES, DocumentRejected, validate_docx
from .figure_crop import FigureRejected, crop_figure
from .image_ingest import MAX_IMAGE_BYTES, MAX_PAGE_PNG_BYTES
from .models import Draft, ImportJob, PageResult, ReviewEdit
from .txt_parser import MAX_BYTES, parse_txt

logger = logging.getLogger("testflow.imports")


class FileTooLarge(ValidationFailed):
    status_code = 413


class InvalidFileType(ValidationFailed):
    status_code = 415


def _reserve_upload(job: ImportJob, raw: bytes) -> None:
    """Serialize deduplication and daily quota checks across all import types."""
    type(job.uploader).objects.select_for_update().get(pk=job.uploader_id)
    existing = (
        ImportJob.objects.filter(sha256=job.sha256)
        .exclude(status__in=[ImportJob.Status.REJECTED, ImportJob.Status.FAILED])
        .first()
    )
    if existing:
        details = (
            {"existing_job_id": str(existing.id)} if existing.uploader_id == job.uploader_id else {}
        )
        raise Conflict("DUPLICATE_FILE", "Tệp này đã được nhập.", details)
    local_midnight = timezone.localtime(timezone.now()).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    used = ImportJob.objects.filter(
        uploader_id=job.uploader_id, created_at__gte=local_midnight
    ).count()
    if used >= settings.IMPORT_DAILY_JOB_LIMIT:
        raise QuotaExceeded(
            "UPLOAD_QUOTA_EXCEEDED",
            "Bạn đã dùng hết số lượt nhập đề hôm nay.",
            {"daily_limit": settings.IMPORT_DAILY_JOB_LIMIT},
        )
    job.original_file.save("original", ContentFile(raw), save=False)
    job.save()


def _image_mime(raw: bytes) -> str:
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "image/webp"
    raise InvalidFileType("INVALID_FILE_TYPE", "Chỉ chấp nhận ảnh JPEG, PNG hoặc WebP.")


def _document_mime(raw: bytes) -> str:
    if raw.startswith(b"%PDF-"):
        return "application/pdf"
    if raw.startswith(b"PK\x03\x04"):
        try:
            validate_docx(raw)
        except DocumentRejected as exc:
            raise InvalidFileType(exc.code, "Tệp DOCX không hợp lệ hoặc không an toàn.") from exc
        return DOCX_MIME
    return _image_mime(raw)


def _owned_job(job_id, user, *, lock=False):
    queryset = ImportJob.objects.select_for_update(of=("self",)) if lock else ImportJob.objects
    if not is_reviewer(user):
        queryset = queryset.filter(uploader=user)
    job = queryset.select_related("draft").filter(pk=job_id).first()
    if job is None:
        raise NotFound("IMPORT_NOT_FOUND", "Không tìm thấy lần nhập đề.")
    return job


def reviewable_job(job_id, *, user):
    return _owned_job(job_id, user)


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
    if include_draft and job.source_kind == "OCR":
        payload["pages"] = [
            {
                "page_no": page.page_no,
                "status": page.status,
                "source": page.source or None,
                "attempts": page.attempts,
                "error_code": page.error_code or None,
                "provider_name": page.provider_name or None,
                "model_name": page.model_name or None,
                "model_version": page.model_version or None,
                "artifact_digest": page.artifact_digest or None,
                "latency_ms": page.latency_ms,
            }
            for page in job.pages.order_by("page_no")
        ]
    if hasattr(job, "draft") and job.status in {
        ImportJob.Status.NEEDS_REVIEW,
        ImportJob.Status.APPROVED,
        ImportJob.Status.REJECTED,
    }:
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
            _reserve_upload(job, raw)
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


def create_image_job(upload, *, uploader, subject_hint=""):
    """Accept a bounded image and enqueue its private, asynchronous extraction."""
    return _create_binary_job(
        upload, uploader=uploader, subject_hint=subject_hint, allow_documents=False
    )


def create_document_job(upload, *, uploader, subject_hint=""):
    """Accept a PDF, DOCX, or image through one content-validated import boundary."""
    return _create_binary_job(
        upload, uploader=uploader, subject_hint=subject_hint, allow_documents=True
    )


@transaction.atomic
def retry_page(job_id, page_no: int, *, user):
    """Retry one failed page before manual edits, then rebuild the draft."""
    job = _owned_job(job_id, user, lock=True)
    if job.source_kind != "OCR" or job.status != ImportJob.Status.NEEDS_REVIEW:
        raise Conflict("IMPORT_STATE_CONFLICT", "Đề chưa ở trạng thái cho phép thử lại trang.")
    if ReviewEdit.objects.filter(job=job).exists():
        raise Conflict("IMPORT_REVIEW_EDITED", "Không thể thử lại sau khi đã sửa bản nháp.")
    page = PageResult.objects.select_for_update().filter(job=job, page_no=page_no).first()
    if page is None:
        raise NotFound("IMPORT_PAGE_NOT_FOUND", "Không tìm thấy trang cần thử lại.")
    if page.status != PageResult.Status.FAILED:
        raise Conflict("IMPORT_PAGE_NOT_FAILED", "Trang này không có lỗi trích xuất.")
    page.status = PageResult.Status.PENDING
    page.attempts = 0
    page.error_code = ""
    page.save(update_fields=["status", "attempts", "error_code", "updated_at"])
    job.transition(ImportJob.Status.EXTRACTING)

    def enqueue() -> None:
        from .tasks import process_document_job, process_image_job

        worker = (
            process_document_job
            if job.mime_type in {"application/pdf", DOCX_MIME}
            else process_image_job
        )
        try:
            worker.delay(str(job.id))
        except Exception:
            logger.exception(
                "Page retry queue unavailable",
                extra={"import_job_id": str(job.id), "stage": "enqueue"},
            )

    transaction.on_commit(enqueue)
    return job


def _create_binary_job(upload, *, uploader, subject_hint: str, allow_documents: bool):
    if not settings.IMPORT_INFERENCE_URL.startswith(("http://", "https://")):
        raise ExternalServiceError(
            "OCR_UNAVAILABLE", "Dịch vụ nhận dạng đề hiện chưa được cấu hình."
        )
    limit = MAX_DOCUMENT_BYTES if allow_documents else MAX_IMAGE_BYTES
    if upload.size > limit:
        raise FileTooLarge("FILE_TOO_LARGE", "Tệp vượt giới hạn cho phép.")
    raw = upload.read(limit + 1)
    if len(raw) > limit:
        raise FileTooLarge("FILE_TOO_LARGE", "Tệp vượt giới hạn cho phép.")
    mime = _document_mime(raw) if allow_documents else _image_mime(raw)
    if mime.startswith("image/") and len(raw) > MAX_IMAGE_BYTES:
        raise FileTooLarge("FILE_TOO_LARGE", "Ảnh vượt giới hạn 10 MB.")
    filename = PurePath(upload.name.replace("\\", "/")).name[:255]
    job = ImportJob(
        uploader=uploader,
        original_filename=filename,
        sha256=hashlib.sha256(raw).hexdigest(),
        mime_type=mime,
        file_size=len(raw),
        source_kind="OCR",
        subject_hint=subject_hint,
        pipeline_version="document-v1" if mime in {"application/pdf", DOCX_MIME} else "image-v1",
    )
    try:
        with transaction.atomic():
            _reserve_upload(job, raw)
            if mime in {"application/pdf", DOCX_MIME}:
                from .tasks import process_document_job

                worker = process_document_job
            else:
                from .tasks import process_image_job

                worker = process_image_job

            def enqueue() -> None:
                try:
                    worker.delay(str(job.id))
                except Exception:
                    job.transition(ImportJob.Status.FAILED, error_code="QUEUE_UNAVAILABLE")
                    logger.exception(
                        "Image import queue unavailable",
                        extra={"import_job_id": str(job.id), "stage": "enqueue"},
                    )

            transaction.on_commit(enqueue)
    except Exception as exc:
        if not job.pk or not ImportJob.objects.filter(pk=job.pk).exists():
            if job.original_file.name:
                job.original_file.delete(save=False)
        if isinstance(exc, IntegrityError):
            raise Conflict("DUPLICATE_FILE", "Tệp này đã được nhập.") from exc
        raise
    if job.status == ImportJob.Status.FAILED:
        raise ExternalServiceError("QUEUE_UNAVAILABLE", "Hàng đợi xử lý đề hiện không khả dụng.")
    logger.info("Image import queued", extra={"import_job_id": str(job.id), "stage": "upload"})
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
    current_count = sum(len(section["questions"]) for section in before["sections"])
    source_count = sum(len(section["questions"]) for section in draft.original_data["sections"])
    required_count = max(current_count, source_count + draft.skipped_count)
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
        draft.skipped_count = 0
    elif before != after:
        # A later correction invalidates human sign-off against the prior draft.
        draft.warnings = [
            {
                key: value
                for key, value in item.items()
                if key not in {"resolved_at", "resolved_by", "resolution_reason"}
            }
            for item in draft.warnings
        ]
    draft.updated_by = user
    draft.save(update_fields=["data", "warnings", "skipped_count", "updated_by", "updated_at"])
    ReviewEdit.objects.create(job=job, reviewer=user, path="/", before=before, after=after)
    return job


REVIEW_RESOLVABLE_CODES = {
    "E_ANSWER_CONFLICT",
    "E_ANSWER_INVALID",
    "E_ANSWER_UNMATCHED",
    "E_ANSWER_UNSUPPORTED",
    "E_CONTINUATION_UNMATCHED",
    "E_FIGURE_UNMATCHED",
    "E_HEADER_CONFLICT",
    "E_NO_QUESTIONS",
    "E_PASSAGE_UNANCHORED",
    "E_PASSAGE_UNMATCHED",
    "E_QUESTION_INVALID",
}


@transaction.atomic
def resolve_review_issue(job_id, issue_index: int, *, user, reason: str):
    """Record a source-page review after a material draft correction."""
    job = _owned_job(job_id, user, lock=True)
    if job.source_kind != "OCR" or job.status != ImportJob.Status.NEEDS_REVIEW:
        raise Conflict("IMPORT_STATE_CONFLICT", "Bản nháp OCR không còn cho phép duyệt lỗi.")
    issues = list(job.draft.warnings)
    if not 0 <= issue_index < len(issues):
        raise NotFound("IMPORT_ISSUE_NOT_FOUND", "Không tìm thấy lỗi cần duyệt.")
    issue = issues[issue_index]
    if issue.get("severity") != "ERROR" or issue.get("code") not in REVIEW_RESOLVABLE_CODES:
        raise ValidationFailed("ISSUE_NOT_RESOLVABLE", "Lỗi này cần xử lý tại trang nguồn.")
    if issue.get("resolved_at"):
        raise Conflict("ISSUE_ALREADY_RESOLVED", "Lỗi đã được duyệt.")
    if not 10 <= len(reason.strip()) <= 500:
        raise ValidationFailed("ISSUE_REASON_REQUIRED", "Cần ghi lý do duyệt từ 10 đến 500 ký tự.")
    if job.draft.data == job.draft.original_data:
        raise ValidationFailed("DRAFT_EDIT_REQUIRED", "Cần sửa bản nháp trước khi duyệt lỗi nguồn.")
    page_no = issue.get("page_no")
    if (
        page_no
        and not PageResult.objects.filter(
            job=job, page_no=page_no, status=PageResult.Status.DONE
        ).exists()
    ):
        raise ValidationFailed("ISSUE_PAGE_UNAVAILABLE", "Trang nguồn chưa được trích xuất đầy đủ.")
    before = dict(issue)
    issue = {
        **issue,
        "resolved_at": timezone.now().isoformat(),
        "resolved_by": user.pk,
        "resolution_reason": reason.strip(),
    }
    issues[issue_index] = issue
    job.draft.warnings = issues
    job.draft.updated_by = user
    job.draft.save(update_fields=["warnings", "updated_by", "updated_at"])
    ReviewEdit.objects.create(
        job=job,
        reviewer=user,
        path=f"/warnings/{issue_index}",
        before=before,
        after=issue,
    )
    return job


@transaction.atomic
def confirm(job_id, *, user):
    started = monotonic()
    job = _owned_job(job_id, user, lock=True)
    if job.status != ImportJob.Status.NEEDS_REVIEW:
        raise Conflict("IMPORT_STATE_CONFLICT", "Lần nhập đề đã được xử lý.")
    if any(item["severity"] == "ERROR" and not item.get("resolved_at") for item in _issues(job)):
        raise ValidationFailed("DRAFT_HAS_ERRORS", "Cần sửa lỗi bản nháp trước khi lưu đề.")
    draft = ExamDraft.model_validate(job.draft.data)
    figure_payloads = {}
    for section in draft.sections:
        for question in section.questions:
            for ref in question.figure_refs:
                if ref in figure_payloads:
                    continue
                match = re.fullmatch(r"p([1-9]\d*):(.+)", ref)
                if match is None:
                    raise ValidationFailed("FIGURE_REF_INVALID", "Tham chiếu hình không hợp lệ.")
                page_no, figure_id = int(match.group(1)), match.group(2)
                page = PageResult.objects.filter(job=job, page_no=page_no).first()
                if page is None or page.status != PageResult.Status.DONE or not page.image:
                    raise ValidationFailed("FIGURE_PAGE_MISSING", "Không tìm thấy trang chứa hình.")
                try:
                    schema = PageSchema.model_validate(page.page_json)
                except ContractValidationError as exc:
                    raise ValidationFailed(
                        "FIGURE_PAGE_INVALID", "Trang chứa hình không hợp lệ."
                    ) from exc
                figure = next((item for item in schema.figures if item.id == figure_id), None)
                if figure is None:
                    raise ValidationFailed(
                        "FIGURE_REF_INVALID", "Không tìm thấy hình trên trang nguồn."
                    )
                try:
                    with page.image.open("rb") as image:
                        page_png = image.read(MAX_PAGE_PNG_BYTES + 1)
                    if len(page_png) > MAX_PAGE_PNG_BYTES:
                        raise FigureRejected("FIGURE_PAGE_TOO_LARGE")
                    figure_payloads[ref] = crop_figure(page_png, figure.bbox)
                except (OSError, FigureRejected) as exc:
                    raise ValidationFailed(
                        "FIGURE_CROP_FAILED", "Không thể trích hình từ trang."
                    ) from exc
    exam = create_exam(
        draft,
        owner=job.uploader,
        source_kind=job.source_kind,
        source_job=job.id,
        figure_payloads=figure_payloads,
    )
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
