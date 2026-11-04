"""User-scoped practice reads; never disclose invisible exam metadata."""

from django.db.models import Count, Q

from apps.catalog.selectors import visible_exams
from apps.common.errors import NotFound

from .models import Session, SessionStatus, WrongQuestion


def visible_history(user):
    return (
        Session.objects.filter(user_id=user.pk, exam_id__in=visible_exams(user).values("id"))
        .select_related("exam")
        .order_by("-started_at", "-id")
    )


def personal_stats(user):
    return visible_history(user).aggregate(
        total_sessions=Count("id"),
        completed_sessions=Count(
            "id", filter=Q(status__in=[SessionStatus.SUBMITTED, SessionStatus.EXPIRED])
        ),
        timed_sessions=Count("id", filter=Q(mode="TIMED")),
        practice_sessions=Count("id", filter=Q(mode="PRACTICE")),
    )


def exam_practice_summary(user, exam_id):
    if not visible_exams(user).filter(pk=exam_id).exists():
        raise NotFound("EXAM_NOT_FOUND", "Không tìm thấy đề.")
    return {
        "wrong_question_count": WrongQuestion.objects.filter(
            user_id=user.pk, question__section__exam_id=exam_id
        ).count(),
        "session_count": Session.objects.filter(user_id=user.pk, exam_id=exam_id).count(),
    }
