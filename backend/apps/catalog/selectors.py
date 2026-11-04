"""Canonical exam visibility and read queries."""

from django.db.models import Q

from apps.common.text import search_fold

from .models import Exam, PublishRequest, Visibility


def visible_exams(user):
    exams = Exam.objects.filter(deleted_at__isnull=True)
    if user is not None and user.is_authenticated:
        if user.is_staff and (user.is_superuser or user.groups.filter(name="Admin").exists()):
            return exams
        return exams.filter(
            Q(visibility=Visibility.PUBLIC) | Q(owner_id=user.pk, visibility=Visibility.PRIVATE)
        )
    return exams.filter(visibility=Visibility.PUBLIC)


def list_exams(user, filters):
    queryset = (
        visible_exams(user).select_related("subject", "owner").prefetch_related("schools", "majors")
    )
    for field in ("level", "grade", "exam_type", "year", "has_answer_key"):
        if filters.get(field) not in (None, ""):
            queryset = queryset.filter(**{field: filters[field]})
    if filters.get("subject"):
        queryset = queryset.filter(subject__code=filters["subject"])
    if filters.get("school"):
        queryset = queryset.filter(schools__name__iexact=filters["school"])
    if filters.get("major"):
        queryset = queryset.filter(majors__name__iexact=filters["major"])
    if filters.get("mine") is True:
        queryset = (
            queryset.filter(owner_id=user.pk) if user and user.is_authenticated else queryset.none()
        )
    if filters.get("q"):
        queryset = queryset.filter(search_text__contains=search_fold(filters["q"]))
    ordering = filters.get("ordering", "-created_at")
    if ordering not in {"-created_at", "-attempt_count", "year"}:
        ordering = "-created_at"
    return queryset.order_by(ordering, "id").distinct()


def publication_queue(status):
    return (
        PublishRequest.objects.filter(
            status=status, exam__deleted_at__isnull=True, exam__visibility=Visibility.PRIVATE
        )
        .select_related("exam", "requested_by")
        .order_by("created_at", "id")
    )
