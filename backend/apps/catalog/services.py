"""The only finalized exam write path and catalog business transitions."""

from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from testflow_contracts.exam import ExamDraft

from apps.common.errors import ValidationFailed
from apps.common.text import normalize_text, search_fold

from .models import (
    Chapter,
    Choice,
    Exam,
    Major,
    Passage,
    Question,
    School,
    Section,
    Statement,
    Subject,
    Visibility,
)


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
def create_exam(draft: ExamDraft, *, owner, source_kind: str = "MANUAL", source_job=None) -> Exam:
    """Validate and persist a confirmed PRIVATE exam atomically."""
    metadata = draft.metadata
    if not owner or not owner.is_authenticated:
        raise ValidationFailed("OWNER_REQUIRED", "Cần đăng nhập để tạo đề.")
    if not metadata.title or not metadata.level or not metadata.subject or not metadata.exam_type:
        raise ValidationFailed("METADATA_REQUIRED", "Thiếu tên đề, cấp học, môn hoặc loại đề.")
    if metadata.level in {"TIEU_HOC", "THCS", "THPT"} and metadata.grade is None:
        raise ValidationFailed("GRADE_REQUIRED", "Cấp học này cần lớp cụ thể.")
    if not draft.sections or not any(section.questions for section in draft.sections):
        raise ValidationFailed("E_NO_QUESTIONS", "Đề cần ít nhất một câu hỏi.")
    if source_kind not in {"MANUAL", "TXT", "OCR"}:
        raise ValidationFailed("SOURCE_KIND_INVALID", "Nguồn đề không hợp lệ.")
    subject = Subject.objects.filter(code=metadata.subject, is_active=True).first()
    if subject is None or (subject.levels and metadata.level not in subject.levels):
        raise ValidationFailed(
            "SUBJECT_INVALID", "Môn học không tồn tại hoặc không áp dụng cho cấp học."
        )
    if draft.chapters and [chapter.order for chapter in draft.chapters] != list(
        range(1, len(draft.chapters) + 1)
    ):
        raise ValidationFailed("CHAPTER_ORDER", "Thứ tự chương phải liên tục từ 1.")

    questions = [question for section in draft.sections for question in section.questions]
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

    for school_name in metadata.schools:
        name = normalize_text(school_name)
        if name:
            school, _ = School.objects.get_or_create(name=name)
            exam.schools.add(school)
    for major_name in metadata.majors:
        name = normalize_text(major_name)
        if name:
            major, _ = Major.objects.get_or_create(name=name)
            exam.majors.add(major)

    chapter_by_code = {}
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
