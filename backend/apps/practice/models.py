"""Durable session, answer and wrong-bank state."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.catalog.models import Exam, Question


class SessionMode(models.TextChoices):
    TIMED = "TIMED"
    PRACTICE = "PRACTICE"


class SessionStatus(models.TextChoices):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    EXPIRED = "EXPIRED"


class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    exam = models.ForeignKey(Exam, on_delete=models.PROTECT)
    mode = models.CharField(max_length=8, choices=SessionMode.choices)
    time_limit_seconds = models.PositiveIntegerField(null=True, blank=True)
    config = models.JSONField(default=dict)
    question_order = models.JSONField(default=dict)
    option_order = models.JSONField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    deadline_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=12, choices=SessionStatus.choices, default=SessionStatus.IN_PROGRESS
    )
    total_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    max_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    result_snapshot = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = (
            models.Index(fields=("user", "-started_at"), name="session_user_time_idx"),
            models.Index(fields=("status", "deadline_at"), name="session_deadline_idx"),
        )
        constraints = (
            models.UniqueConstraint(
                fields=("user", "exam"),
                condition=Q(status="IN_PROGRESS"),
                name="one_active_session_per_exam",
            ),
        )


class Answer(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    value = models.JSONField(default=dict)
    flagged = models.BooleanField(default=False)
    time_spent_seconds = models.PositiveIntegerField(default=0)
    locked_at = models.DateTimeField(null=True, blank=True)
    feedback_snapshot = models.JSONField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("session", "question"), name="answer_session_question_unique"
            ),
        )


class WrongQuestion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    times_wrong = models.PositiveSmallIntegerField(default=1)
    first_wrong_at = models.DateTimeField(auto_now_add=True)
    last_wrong_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=("user", "question"), name="wrong_user_question_unique"),
        )
        indexes = (models.Index(fields=("user", "question"), name="wrong_user_question_idx"),)
