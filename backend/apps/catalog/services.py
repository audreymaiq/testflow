"""The only finalized exam write path and catalog business transitions."""

import hashlib
from collections.abc import Mapping
from decimal import Decimal
from io import BytesIO

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
from testflow_contracts.exam import ExamDraft

from apps.common.errors import Conflict, DomainPermissionDenied, NotFound, ValidationFailed
from apps.common.text import search_fold

from .models import (
    Asset,
    Chapter,
    Choice,
    Exam,
    Passage,
    PublishRequest,
    PublishRequestStatus,
    Question,
    QuestionAsset,
    Section,
    Statement,
    Visibility,
)
from .taxonomy import lookup, resolve


def _has_key(question) -> bool:
    if question.kind == "MCQ":
        return sum(choice.is_correct for choice in question.choices) == 1
    if question.kind == "MCQ_MULTI":
        return any(choice.is_correct for choice in question.choices)
    if question.kind == "TRUE_FALSE":
        return question.tf_answer is not None
    if question.kind == "TF_GROUP":
        return all(statement.is_true is not None for statement in question.statements)
    if question.kind == "SHORT":
        return bool(question.short_answer)
    return False


@transaction.atomic
def create_exam(
    draft: ExamDraft,
    *,
    owner,
    source_kind: str = "MANUAL",
    source_job=None,
    allow_schoolless_demo: bool = False,
    figure_payloads: Mapping[str, bytes] | None = None,
) -> Exam:
    """Validate and persist a confirmed PRIVATE exam atomically."""
    metadata = draft.metadata
    if not owner or not owner.is_authenticated:
        raise ValidationFailed("OWNER_REQUIRED", "Cần đăng nhập để tạo đề.")
    if not metadata.title or not metadata.level or not metadata.subject or not metadata.exam_type:
        raise ValidationFailed("METADATA_REQUIRED", "Thiếu tên đề, cấp học, môn hoặc loại đề.")
    if not metadata.schools and not allow_schoolless_demo:
        raise ValidationFailed("SCHOOL_REQUIRED", "Cần chọn hoặc thêm ít nhất một trường.")
    if metadata.level in {"TIEU_HOC", "THCS", "THPT"} and metadata.grade is None:
        raise ValidationFailed("GRADE_REQUIRED", "Cấp học này cần lớp cụ thể.")
    if not draft.sections or not any(section.questions for section in draft.sections):
        raise ValidationFailed("E_NO_QUESTIONS", "Đề cần ít nhất một câu hỏi.")
    if source_kind not in {"MANUAL", "TXT", "OCR"}:
        raise ValidationFailed("SOURCE_KIND_INVALID", "Nguồn đề không hợp lệ.")
    subject = resolve("SUBJECT", metadata.subject)
    if subject is None or (subject.levels and metadata.level not in subject.levels):
        raise ValidationFailed(
            "SUBJECT_INVALID", "Môn học không tồn tại hoặc không áp dụng cho cấp học."
        )
    if draft.chapters and [chapter.order for chapter in draft.chapters] != list(
        range(1, len(draft.chapters) + 1)
    ):
        raise ValidationFailed("CHAPTER_ORDER", "Thứ tự chương phải liên tục từ 1.")

    questions = [question for section in draft.sections for question in section.questions]
    referenced_figures = {ref for question in questions for ref in question.figure_refs}
    payloads = figure_payloads or {}
    if referenced_figures - payloads.keys():
        raise ValidationFailed("FIGURE_ASSETS_UNAVAILABLE", "Hình minh họa chưa có tệp an toàn.")
    figure_specs = {}
    for ref in referenced_figures:
        png = payloads[ref]
        if not png or len(png) > 10 * 1024 * 1024:
            raise ValidationFailed("FIGURE_ASSET_INVALID", "Tệp hình minh họa không hợp lệ.")
        try:
            with Image.open(BytesIO(png)) as image:
                if (
                    image.format != "PNG"
                    or not 2 <= image.width <= 3000
                    or not 2 <= image.height <= 3000
                ):
                    raise ValueError("invalid figure dimensions")
                image.load()
                figure_specs[ref] = (
                    png,
                    image.width,
                    image.height,
                    hashlib.sha256(png).hexdigest(),
                )
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            raise ValidationFailed(
                "FIGURE_ASSET_INVALID", "Tệp hình minh họa không hợp lệ."
            ) from exc
    graded = [question for question in questions if question.kind != "ESSAY"]
    has_answer_key = bool(graded) and all(_has_key(question) for question in graded)
    max_score = metadata.max_score
    if metadata.scoring_preset == "PRACTICE_NO_SCORE":
        max_score = None
    elif metadata.scoring_preset in {"UNIFORM_10", "THPT_2025"}:
        max_score = Decimal("10.00")
    elif metadata.scoring_preset == "UNIFORM_100":
        max_score = Decimal("100.00")
    elif max_score is None:
        raise ValidationFailed("MAX_SCORE_REQUIRED", "Thang điểm tùy chỉnh cần điểm tối đa.")

    schools = []
    for name in metadata.schools:
        school = resolve("SCHOOL", name)
        if school is None:
            raise ValidationFailed(
                "SCHOOL_UNKNOWN",
                "Chọn trường đã có hoặc tạo tên mới trong danh mục.",
                {"name": name, **lookup("SCHOOL", name)},
            )
        schools.append(school)
    majors = []
    for name in metadata.majors:
        major = resolve("MAJOR", name)
        if major is None:
            raise ValidationFailed(
                "MAJOR_UNKNOWN",
                "Chọn ngành đã có hoặc tạo tên mới trong danh mục.",
                {"name": name, **lookup("MAJOR", name)},
            )
        majors.append(major)

    exam = Exam(
        title=metadata.title,
        subtitle=metadata.subtitle,
        icon=metadata.icon,
        color=metadata.color,
        level=metadata.level,
        grade=metadata.grade,
        subject=subject,
        exam_type=metadata.exam_type,
        province=metadata.province,
        year=metadata.year,
        term=metadata.term,
        duration_minutes=metadata.duration_minutes,
        scoring_preset=metadata.scoring_preset,
        max_score=max_score,
        owner=owner,
        visibility=Visibility.PRIVATE,
        has_answer_key=has_answer_key,
        question_count=len(questions),
        source_kind=source_kind,
        source_job=source_job,
        source=metadata.source,
    )
    try:
        exam.full_clean()
    except DjangoValidationError as exc:
        raise ValidationFailed(
            "EXAM_INVALID", "Thông tin đề không hợp lệ.", exc.message_dict
        ) from exc
    exam.save()

    exam.schools.add(*schools)
    exam.majors.add(*majors)

    chapter_by_code = {}
    asset_by_ref: dict[str, Asset] = {}
    for chapter_draft in draft.chapters:
        chapter = Chapter.objects.create(
            exam=exam,
            code=chapter_draft.code,
            name=chapter_draft.name,
            description=chapter_draft.description,
            color=chapter_draft.color,
            order=chapter_draft.order,
        )
        chapter_by_code[chapter.code] = chapter
    for section_draft in draft.sections:
        section = Section.objects.create(
            exam=exam,
            order=section_draft.order,
            title=section_draft.title,
            kind=section_draft.kind,
            scoring=section_draft.scoring.model_dump(mode="json"),
        )
        passage_by_tmp_id = {}
        for passage_draft in section_draft.passages:
            passage = Passage.objects.create(
                section=section,
                source_tmp_id=passage_draft.tmp_id,
                order=passage_draft.order,
                text=passage_draft.text,
            )
            passage_by_tmp_id[passage_draft.tmp_id] = passage
        for question_draft in section_draft.questions:
            question = Question.objects.create(
                section=section,
                source_tmp_id=question_draft.tmp_id,
                provenance=question_draft.provenance.model_dump(mode="json"),
                passage=(
                    passage_by_tmp_id.get(question_draft.passage_ref)
                    if question_draft.passage_ref
                    else None
                ),
                chapter=chapter_by_code.get(question_draft.chapter),
                order=question_draft.order,
                number_label=question_draft.number_label,
                kind=question_draft.kind,
                tf_answer=question_draft.tf_answer,
                text=question_draft.text,
                explanation=question_draft.explanation,
                points=question_draft.points,
                short_answer=question_draft.short_answer or "",
                short_tolerance=question_draft.short_tolerance,
                essay_model_answer=question_draft.essay_model_answer,
            )
            for asset_order, ref in enumerate(question_draft.figure_refs, start=1):
                asset = asset_by_ref.get(ref)
                if asset is None:
                    png, width, height, digest = figure_specs[ref]
                    asset = Asset(
                        width=width,
                        height=height,
                        sha256=digest,
                        source_job=source_job,
                    )
                    asset.file.save("figure.png", ContentFile(png), save=False)
                    asset.save()
                    asset_by_ref[ref] = asset
                QuestionAsset.objects.create(question=question, asset=asset, order=asset_order)
            Choice.objects.bulk_create(
                [
                    Choice(
                        question=question,
                        label=choice.label,
                        text=choice.text,
                        is_correct=choice.is_correct,
                    )
                    for choice in question_draft.choices
                ]
            )
            Statement.objects.bulk_create(
                [
                    Statement(
                        question=question, label=item.label, text=item.text, is_true=item.is_true
                    )
                    for item in question_draft.statements
                ]
            )

    exam.search_text = search_fold(
        " ".join(
            [
                exam.title,
                exam.subtitle,
                subject.name,
                *metadata.schools,
                *metadata.majors,
                exam.province,
            ]
        )
    )
    exam.save(update_fields=("search_text", "updated_at"))
    return exam


def is_reviewer(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(name="Reviewer").exists()
            or (user.is_staff and user.groups.filter(name="Admin").exists())
        )
    )


def is_admin(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and user.is_staff
        and (user.is_superuser or user.groups.filter(name="Admin").exists())
    )


def _owned_exam(exam_id, owner):
    exam = (
        Exam.objects.select_for_update()
        .filter(pk=exam_id, owner_id=owner.pk, deleted_at__isnull=True)
        .first()
    )
    if exam is None:
        raise NotFound("EXAM_NOT_FOUND", "Không tìm thấy đề của bạn.")
    return exam


def _close_pending(exam, *, reason: str):
    exam.publish_requests.filter(status=PublishRequestStatus.PENDING).update(
        status=PublishRequestStatus.REJECTED, reason=reason, decided_at=timezone.now()
    )


@transaction.atomic
def request_publication(exam_id, *, owner) -> PublishRequest:
    exam = _owned_exam(exam_id, owner)
    if exam.visibility != Visibility.PRIVATE:
        raise Conflict("EXAM_NOT_PRIVATE", "Chỉ đề riêng tư mới có thể gửi duyệt.")
    if not exam.source.strip():
        raise ValidationFailed("SOURCE_REQUIRED", "Cần ghi rõ nguồn trước khi gửi duyệt công khai.")
    if not exam.sections.exists() or not exam.question_count:
        raise ValidationFailed("EXAM_EMPTY", "Đề cần có câu hỏi trước khi công khai.")
    request = exam.publish_requests.filter(status=PublishRequestStatus.PENDING).first()
    if request is not None:
        return request
    return PublishRequest.objects.create(
        exam=exam, requested_by=owner, status=PublishRequestStatus.PENDING
    )


@transaction.atomic
def make_private(exam_id, *, owner) -> Exam:
    exam = _owned_exam(exam_id, owner)
    if exam.visibility == Visibility.HIDDEN:
        raise Conflict("EXAM_HIDDEN", "Đề đang bị quản trị viên ẩn.")
    exam.visibility = Visibility.PRIVATE
    exam.save(update_fields=("visibility", "updated_at"))
    _close_pending(exam, reason="Người sở hữu đã rút yêu cầu công khai.")
    return exam


@transaction.atomic
def soft_delete_exam(exam_id, *, owner) -> None:
    exam = _owned_exam(exam_id, owner)
    exam.deleted_at = timezone.now()
    exam.visibility = Visibility.PRIVATE
    exam.save(update_fields=("deleted_at", "visibility", "updated_at"))
    _close_pending(exam, reason="Người sở hữu đã xóa đề.")


@transaction.atomic
def decide_publication(request_id, *, reviewer, approve: bool, reason: str = "") -> PublishRequest:
    if not is_reviewer(reviewer):
        raise DomainPermissionDenied("REVIEWER_REQUIRED", "Cần quyền duyệt đề.")
    target = PublishRequest.objects.filter(pk=request_id).values("exam_id").first()
    if target is None:
        raise NotFound("REQUEST_NOT_FOUND", "Không tìm thấy yêu cầu công khai.")
    exam = Exam.objects.select_for_update().get(pk=target["exam_id"])
    request = PublishRequest.objects.select_for_update().get(pk=request_id)
    if (
        request.status != PublishRequestStatus.PENDING
        or exam.visibility != Visibility.PRIVATE
        or exam.deleted_at
    ):
        raise Conflict("REQUEST_STALE", "Yêu cầu này không còn hiệu lực.")
    if exam.owner_id == reviewer.pk:
        raise DomainPermissionDenied("SELF_REVIEW_FORBIDDEN", "Không thể tự duyệt đề của mình.")
    if not approve and not reason.strip():
        raise ValidationFailed("REASON_REQUIRED", "Cần ghi lý do từ chối.")
    request.status = PublishRequestStatus.APPROVED if approve else PublishRequestStatus.REJECTED
    request.reason = reason.strip()
    request.reviewed_by = reviewer
    request.decided_at = timezone.now()
    request.save(update_fields=("status", "reason", "reviewed_by", "decided_at", "updated_at"))
    if approve:
        exam.visibility = Visibility.PUBLIC
        exam.save(update_fields=("visibility", "updated_at"))
    return request


@transaction.atomic
def hide_exam(exam_id, *, admin) -> Exam:
    if not is_admin(admin):
        raise DomainPermissionDenied("ADMIN_REQUIRED", "Cần quyền quản trị.")
    exam = Exam.objects.select_for_update().filter(pk=exam_id, deleted_at__isnull=True).first()
    if exam is None:
        raise NotFound("EXAM_NOT_FOUND", "Không tìm thấy đề.")
    exam.visibility = Visibility.HIDDEN
    exam.save(update_fields=("visibility", "updated_at"))
    _close_pending(exam, reason="Quản trị viên đã ẩn đề.")
    return exam


def export_exam(exam: Exam) -> ExamDraft:
    """Reconstruct a v1 draft for editing/export and round-trip checks."""
    exam = (
        Exam.objects.select_related("subject")
        .prefetch_related(
            "schools",
            "majors",
            "chapters",
            "sections__passages",
            "sections__questions__choices",
            "sections__questions__statements",
            "sections__questions__chapter",
            "sections__questions__passage",
            "sections__questions__questionasset_set",
        )
        .get(pk=exam.pk)
    )
    return ExamDraft.model_validate(
        {
            "schema_version": 1,
            "metadata": {
                "title": exam.title,
                "subtitle": exam.subtitle,
                "icon": exam.icon,
                "color": exam.color,
                "level": exam.level,
                "grade": exam.grade,
                "subject": exam.subject.code,
                "exam_type": exam.exam_type,
                "schools": [school.name for school in exam.schools.all()],
                "majors": [major.name for major in exam.majors.all()],
                "province": exam.province,
                "year": exam.year,
                "term": exam.term,
                "duration_minutes": exam.duration_minutes,
                "scoring_preset": exam.scoring_preset,
                "max_score": exam.max_score,
                "source": exam.source,
            },
            "chapters": [
                {
                    "code": chapter.code,
                    "name": chapter.name,
                    "description": chapter.description,
                    "color": chapter.color,
                    "order": chapter.order,
                }
                for chapter in exam.chapters.all()
            ],
            "sections": [
                {
                    "order": section.order,
                    "title": section.title,
                    "kind": section.kind,
                    "scoring": section.scoring,
                    "passages": [
                        {
                            "tmp_id": passage.source_tmp_id,
                            "order": passage.order,
                            "text": passage.text,
                        }
                        for passage in section.passages.all()
                    ],
                    "questions": [
                        {
                            "tmp_id": question.source_tmp_id,
                            "order": question.order,
                            "number_label": question.number_label,
                            "kind": question.kind,
                            "chapter": question.chapter.code if question.chapter else None,
                            "passage_ref": question.passage.source_tmp_id
                            if question.passage
                            else None,
                            "text": question.text,
                            "explanation": question.explanation,
                            "figure_refs": [
                                str(link.asset_id) for link in question.questionasset_set.all()
                            ],
                            "choices": [
                                {
                                    "label": choice.label,
                                    "text": choice.text,
                                    "is_correct": choice.is_correct,
                                }
                                for choice in question.choices.all()
                            ],
                            "statements": [
                                {"label": item.label, "text": item.text, "is_true": item.is_true}
                                for item in question.statements.all()
                            ],
                            "tf_answer": question.tf_answer,
                            "short_answer": question.short_answer or None,
                            "short_tolerance": question.short_tolerance,
                            "essay_model_answer": question.essay_model_answer,
                            "points": question.points,
                            "provenance": question.provenance,
                        }
                        for question in section.questions.all()
                    ],
                }
                for section in exam.sections.all()
            ],
        }
    )


def export_figure_payloads(exam: Exam) -> dict[str, bytes]:
    """Supply the private figure bytes needed to recreate an exported exam."""
    assets = Asset.objects.filter(questionasset__question__section__exam_id=exam.pk).distinct()
    payloads = {}
    for asset in assets:
        with asset.file.open("rb") as image:
            payloads[str(asset.pk)] = image.read(10 * 1024 * 1024 + 1)
    return payloads
