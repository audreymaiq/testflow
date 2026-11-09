"""Server-owned practice and timed-session lifecycle."""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import Exam, Question, Visibility
from apps.catalog.selectors import visible_exams
from apps.common.errors import Conflict, NotFound, ValidationFailed

from .grading import GradeResult, QuestionKey, grade_question
from .models import Answer, Session, SessionMode, SessionStatus, WrongQuestion
from .schemas import SessionConfig
from .selection import build_question_set

CENT = Decimal("0.01")


def _require_session(session_id, user, *, lock=False) -> Session:
    queryset = Session.objects.select_related("exam")
    if lock:
        queryset = queryset.select_for_update()
    session = queryset.filter(pk=session_id, user_id=user.pk).first()
    if (
        session is None
        or session.exam.deleted_at is not None
        or session.exam.visibility == Visibility.HIDDEN
    ):
        raise NotFound("SESSION_NOT_FOUND", "Không tìm thấy phiên làm bài.")
    return session


def _selected_ids(session: Session) -> list[str]:
    return [question_id for ids in session.question_order.values() for question_id in ids]


def _question(session: Session, question_id) -> Question:
    if str(question_id) not in _selected_ids(session):
        raise NotFound("QUESTION_NOT_FOUND", "Câu hỏi không thuộc phiên này.")
    question = (
        Question.objects.select_related("section")
        .prefetch_related("choices", "statements")
        .filter(pk=question_id, section__exam_id=session.exam_id)
        .first()
    )
    if question is None:
        raise NotFound("QUESTION_NOT_FOUND", "Không tìm thấy câu hỏi.")
    return question


def _validate_answer(question: Question, value: dict) -> None:
    if not isinstance(value, dict):
        raise ValidationFailed("ANSWER_INVALID", "Câu trả lời phải là object JSON.")
    if question.kind == "MCQ":
        allowed = {choice.label for choice in question.choices.all()}
        if set(value) - {"choice"} or value.get("choice") not in (None, "", *allowed):
            raise ValidationFailed("ANSWER_INVALID", "Phương án không hợp lệ.")
    elif question.kind == "MCQ_MULTI":
        labels = value.get("choices", [])
        allowed = {choice.label for choice in question.choices.all()}
        if (
            set(value) - {"choices"}
            or not isinstance(labels, list)
            or any(not isinstance(label, str) for label in labels)
            or len(labels) != len(set(labels))
            or not set(labels).issubset(allowed)
        ):
            raise ValidationFailed("ANSWER_INVALID", "Các phương án không hợp lệ.")
    elif question.kind == "TRUE_FALSE":
        if set(value) - {"value"} or ("value" in value and not isinstance(value["value"], bool)):
            raise ValidationFailed("ANSWER_INVALID", "Câu trả lời cần true hoặc false.")
    elif question.kind == "TF_GROUP":
        allowed = {item.label for item in question.statements.all()}
        if set(value) - allowed or any(
            item is not None and not isinstance(item, bool) for item in value.values()
        ):
            raise ValidationFailed("ANSWER_INVALID", "Các ý đúng sai không hợp lệ.")
    elif question.kind in {"SHORT", "ESSAY"}:
        text = value.get("text", "")
        limit = 400 if question.kind == "SHORT" else 10000
        if set(value) - {"text"} or not isinstance(text, str) or len(text) > limit:
            raise ValidationFailed("ANSWER_INVALID", "Nội dung câu trả lời không hợp lệ.")
    else:
        raise ValidationFailed("QUESTION_KIND_INVALID", "Loại câu hỏi không hỗ trợ.")


def _question_key(question: Question, *, points=None) -> QuestionKey:
    choices = list(question.choices.all())
    return QuestionKey(
        kind=question.kind,
        correct_choice=next((choice.label for choice in choices if choice.is_correct), None),
        correct_choices=frozenset(choice.label for choice in choices if choice.is_correct),
        all_choices=tuple(choice.label for choice in choices),
        tf_answer=question.tf_answer,
        statements={item.label: item.is_true for item in question.statements.all()}
        if question.kind == "TF_GROUP"
        and all(item.is_true is not None for item in question.statements.all())
        else None,
        short_answer=question.short_answer or None,
        tolerance=question.short_tolerance,
        points=question.points if question.points is not None else points,
    )


def _scoring(session: Session, question: Question, auto_count: int):
    scoring = dict(question.section.scoring)
    points = None
    if session.exam.scoring_preset in {"UNIFORM_10", "UNIFORM_100"} and question.kind != "ESSAY":
        scale = Decimal("10") if session.exam.scoring_preset == "UNIFORM_10" else Decimal("100")
        points = scale / Decimal(max(1, auto_count))
    return scoring, points


def _grade(session: Session, question: Question, value: dict, auto_count: int) -> GradeResult:
    scoring, points = _scoring(session, question, auto_count)
    return grade_question(_question_key(question, points=points), value, scoring)


def _correct_answer(question: Question) -> dict:
    if question.kind == "MCQ":
        return {
            "choice": next((item.label for item in question.choices.all() if item.is_correct), None)
        }
    if question.kind == "MCQ_MULTI":
        return {"choices": [item.label for item in question.choices.all() if item.is_correct]}
    if question.kind == "TRUE_FALSE":
        return {"value": question.tf_answer}
    if question.kind == "TF_GROUP":
        return {item.label: item.is_true for item in question.statements.all()}
    if question.kind == "SHORT":
        return {"text": question.short_answer}
    return {"text": question.essay_model_answer}


def _record_wrong(user, question: Question, status: str) -> None:
    if status in {"WRONG", "PARTIAL", "SKIPPED"}:
        wrong, created = WrongQuestion.objects.get_or_create(user=user, question=question)
        if not created:
            WrongQuestion.objects.filter(pk=wrong.pk).update(
                times_wrong=F("times_wrong") + 1, last_wrong_at=timezone.now()
            )
    elif status == "CORRECT":
        WrongQuestion.objects.filter(user=user, question=question).delete()


@transaction.atomic
def create_session(*, user, exam_id, mode: str, config: SessionConfig) -> Session:
    if mode not in SessionMode.values:
        raise ValidationFailed("MODE_INVALID", "Chế độ làm bài không hợp lệ.")
    exam = (
        visible_exams(user)
        .exclude(visibility=Visibility.HIDDEN)
        .select_for_update()
        .filter(pk=exam_id)
        .first()
    )
    if exam is None:
        raise NotFound("EXAM_NOT_FOUND", "Không tìm thấy đề.")
    if not exam.has_answer_key:
        raise ValidationFailed("ANSWER_KEY_REQUIRED", "Đề chưa có đủ đáp án để chấm.")
    existing = Session.objects.filter(
        user=user, exam=exam, status=SessionStatus.IN_PROGRESS
    ).first()
    if existing is not None:
        if existing.deadline_at and existing.deadline_at <= timezone.now():
            submit_session(existing.id, user=user)
        else:
            if existing.mode != mode:
                raise Conflict(
                    "SESSION_MODE_CONFLICT",
                    "Bạn đang làm đề này ở chế độ khác. Hãy tiếp tục hoặc nộp bài hiện tại.",
                )
            return existing
    questions = list(
        Question.objects.filter(section__exam=exam)
        .select_related("section", "chapter")
        .prefetch_related("choices")
        .order_by("section__order", "order")
    )
    allowed_chapters = {
        str(chapter_id) for chapter_id in exam.chapters.values_list("id", flat=True)
    }
    if not set(config.chapter_ids).issubset(allowed_chapters):
        raise ValidationFailed("CHAPTER_INVALID", "Chương không thuộc đề này.")
    wrong_ids = set(
        str(question_id)
        for question_id in WrongQuestion.objects.filter(
            user=user, question__section__exam=exam
        ).values_list("question_id", flat=True)
    )
    sections: dict[str, list[tuple[str, str | None, tuple[str, ...]]]] = {}
    for question in questions:
        sections.setdefault(str(question.section_id), []).append(
            (
                str(question.id),
                str(question.chapter_id) if question.chapter_id else None,
                tuple(choice.label for choice in question.choices.all()),
            )
        )
    question_order, option_order = build_question_set(sections, config, wrong_ids)
    if not question_order:
        raise ValidationFailed("NO_QUESTIONS", "Không có câu hỏi phù hợp với cấu hình.")
    if mode == SessionMode.TIMED and not exam.duration_minutes:
        raise ValidationFailed("DURATION_REQUIRED", "Đề chưa có thời gian làm bài.")
    started = timezone.now()
    time_limit = exam.duration_minutes * 60 if mode == SessionMode.TIMED else None
    return Session.objects.create(
        user=user,
        exam=exam,
        mode=mode,
        time_limit_seconds=time_limit,
        config=config.model_dump(mode="json"),
        question_order=question_order,
        option_order=option_order,
        deadline_at=started + timedelta(seconds=time_limit) if time_limit else None,
    )


def session_payload(session_id, user) -> dict:
    session = _require_session(session_id, user)
    if (
        session.status == SessionStatus.IN_PROGRESS
        and session.deadline_at
        and session.deadline_at <= timezone.now()
    ):
        submit_session(session.id, user=user)
        session.refresh_from_db()
    ids = _selected_ids(session)
    questions = (
        Question.objects.filter(id__in=ids)
        .select_related("section", "passage")
        .prefetch_related("choices", "statements")
    )
    by_id = {str(question.id): question for question in questions}
    answer_by_id = {str(answer.question_id): answer for answer in session.answers.all()}
    sections = []
    for section_id, question_ids in session.question_order.items():
        section_questions = []
        for question_id in question_ids:
            question = by_id[question_id]
            choice_by_label = {choice.label: choice for choice in question.choices.all()}
            labels = (session.option_order or {}).get(question_id, list(choice_by_label))
            item = {
                "id": question_id,
                "number_label": question.number_label,
                "kind": question.kind,
                "text": question.text,
                "passage": question.passage.text if question.passage else None,
                "choices": [
                    {"label": label, "text": choice_by_label[label].text} for label in labels
                ],
                "statements": [
                    {"label": statement.label, "text": statement.text}
                    for statement in question.statements.all()
                ],
            }
            if session.mode == SessionMode.PRACTICE and question_id in answer_by_id:
                item["feedback"] = answer_by_id[question_id].feedback_snapshot
            section_questions.append(item)
        sections.append({"id": section_id, "questions": section_questions})
    return {
        "id": str(session.id),
        "exam_id": str(session.exam_id),
        "mode": session.mode,
        "status": session.status,
        "deadline_at": session.deadline_at.isoformat() if session.deadline_at else None,
        "server_time": timezone.now().isoformat(),
        "question_order": session.question_order,
        "sections": sections,
        "answers": [
            {
                "question_id": str(answer.question_id),
                "value": answer.value,
                "flagged": answer.flagged,
                "time_spent_seconds": answer.time_spent_seconds,
            }
            for answer in answer_by_id.values()
        ],
    }


@transaction.atomic
def save_answer(
    session_id, question_id, *, user, value: dict, flagged=False, time_spent_seconds=0
) -> dict:
    session = _require_session(session_id, user, lock=True)
    if session.status != SessionStatus.IN_PROGRESS:
        raise Conflict("SESSION_CLOSED", "Phiên làm bài đã kết thúc.")
    if session.deadline_at and session.deadline_at <= timezone.now():
        raise Conflict("DEADLINE_PASSED", "Đã hết thời gian làm bài.")
    question = _question(session, question_id)
    _validate_answer(question, value)
    answer, created = Answer.objects.get_or_create(
        session=session,
        question=question,
        defaults={"value": value, "flagged": flagged, "time_spent_seconds": time_spent_seconds},
    )
    if session.mode == SessionMode.PRACTICE and answer.locked_at:
        if answer.value == value:
            return {
                "question_id": str(question.id),
                "value": answer.value,
                "feedback": answer.feedback_snapshot,
            }
        raise Conflict("ANSWER_LOCKED", "Câu hỏi này đã được chấm và khóa.")
    if not created:
        answer.value = value
        answer.flagged = flagged
        answer.time_spent_seconds = time_spent_seconds
    if session.mode == SessionMode.PRACTICE:
        auto_count = (
            Question.objects.filter(id__in=_selected_ids(session)).exclude(kind="ESSAY").count()
        )
        grade = _grade(session, question, value, auto_count)
        if grade.status == "BLANK":
            raise ValidationFailed("ANSWER_BLANK", "Chọn đáp án hoặc dùng Bỏ qua.")
        feedback = {
            "status": grade.status,
            "earned": str(grade.earned),
            "max_points": str(grade.max_points),
            "correct_answer": _correct_answer(question),
            "explanation": question.explanation,
        }
        answer.feedback_snapshot = feedback
        answer.locked_at = timezone.now()
        _record_wrong(user, question, grade.status)
    answer.save()
    result = {"question_id": str(question.id), "value": answer.value, "flagged": answer.flagged}
    if session.mode == SessionMode.PRACTICE:
        result["feedback"] = answer.feedback_snapshot
    return result


@transaction.atomic
def skip_question(session_id, question_id, *, user) -> dict:
    session = _require_session(session_id, user, lock=True)
    if session.mode != SessionMode.PRACTICE or session.status != SessionStatus.IN_PROGRESS:
        raise Conflict("SKIP_UNAVAILABLE", "Không thể bỏ qua câu này.")
    question = _question(session, question_id)
    if Answer.objects.filter(session=session, question=question, locked_at__isnull=False).exists():
        raise Conflict("ANSWER_LOCKED", "Câu hỏi này đã được khóa.")
    feedback = {
        "status": "SKIPPED",
        "earned": "0",
        "max_points": "0",
        "correct_answer": _correct_answer(question),
        "explanation": question.explanation,
    }
    Answer.objects.update_or_create(
        session=session,
        question=question,
        defaults={"value": {}, "feedback_snapshot": feedback, "locked_at": timezone.now()},
    )
    _record_wrong(user, question, "SKIPPED")
    return {"question_id": str(question.id), "feedback": feedback}


@transaction.atomic
def submit_session(session_id, *, user) -> dict:
    session = _require_session(session_id, user, lock=True)
    if session.status != SessionStatus.IN_PROGRESS:
        return session.result_snapshot
    ids = _selected_ids(session)
    questions = (
        Question.objects.filter(id__in=ids)
        .select_related("section")
        .prefetch_related("choices", "statements")
    )
    by_id = {str(question.id): question for question in questions}
    answers = {str(answer.question_id): answer for answer in session.answers.all()}
    auto_count = sum(question.kind != "ESSAY" for question in questions)
    results = []
    total = Decimal("0")
    maximum = Decimal("0")
    counts = {"CORRECT": 0, "PARTIAL": 0, "WRONG": 0, "BLANK": 0, "MANUAL": 0, "SKIPPED": 0}
    for question_id in ids:
        question = by_id[question_id]
        answer = answers.get(question_id)
        value = answer.value if answer else {}
        grade = _grade(session, question, value, auto_count)
        status = (
            "SKIPPED"
            if answer
            and answer.feedback_snapshot
            and answer.feedback_snapshot.get("status") == "SKIPPED"
            else grade.status
        )
        earned = Decimal("0") if status == "SKIPPED" else grade.earned
        total += earned
        maximum += grade.max_points
        counts[status] += 1
        results.append(
            {
                "question_id": question_id,
                "value": value,
                "status": status,
                "earned": str(earned),
                "max_points": str(grade.max_points),
                "correct_answer": _correct_answer(question),
                "explanation": question.explanation,
            }
        )
        if session.mode == SessionMode.TIMED and status in {"WRONG", "PARTIAL"}:
            _record_wrong(user, question, status)
    submitted_at = timezone.now()
    session.status = (
        SessionStatus.EXPIRED
        if session.deadline_at and submitted_at >= session.deadline_at
        else SessionStatus.SUBMITTED
    )
    session.submitted_at = submitted_at
    scored_count = (
        counts["CORRECT"]
        + counts["PARTIAL"]
        + counts["WRONG"]
        + counts["BLANK"]
        + counts["SKIPPED"]
    )
    snapshot = {
        "session_id": str(session.id),
        "exam_id": str(session.exam_id),
        "mode": session.mode,
        "status": session.status,
        "questions": results,
        "counts": counts,
        "correct_percent": str(
            (Decimal(counts["CORRECT"]) * 100 / Decimal(scored_count)).quantize(
                CENT, rounding=ROUND_HALF_UP
            )
        )
        if scored_count
        else "0",
        "total_score": None
        if session.exam.scoring_preset == "PRACTICE_NO_SCORE"
        else str(total.quantize(CENT, rounding=ROUND_HALF_UP)),
        "max_score": None
        if session.exam.scoring_preset == "PRACTICE_NO_SCORE"
        else str(maximum.quantize(CENT, rounding=ROUND_HALF_UP)),
    }
    session.total_score = (
        None if snapshot["total_score"] is None else Decimal(snapshot["total_score"])
    )
    session.max_score = None if snapshot["max_score"] is None else Decimal(snapshot["max_score"])
    session.result_snapshot = snapshot
    session.save(
        update_fields=("status", "submitted_at", "total_score", "max_score", "result_snapshot")
    )
    if session.exam.visibility == Visibility.PUBLIC:
        Exam.objects.filter(pk=session.exam_id).update(attempt_count=F("attempt_count") + 1)
    return snapshot


def result_payload(session_id, user) -> dict:
    session = _require_session(session_id, user)
    if session.status == SessionStatus.IN_PROGRESS:
        if session.deadline_at and session.deadline_at <= timezone.now():
            return submit_session(session.id, user=user)
        raise Conflict("RESULT_NOT_READY", "Bài làm chưa được nộp.")
    return session.result_snapshot
