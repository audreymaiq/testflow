"""Normalized, durable exam catalog schema."""

import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q


class Timestamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Level(models.TextChoices):
    TIEU_HOC = "TIEU_HOC"
    THCS = "THCS"
    THPT = "THPT"
    DAI_HOC = "DAI_HOC"
    KHAC = "KHAC"


class ExamType(models.TextChoices):
    THI_CHINH_THUC = "THI_CHINH_THUC"
    GIUA_KY = "GIUA_KY"
    CUOI_KY = "CUOI_KY"
    KIEM_TRA = "KIEM_TRA"
    ON_TAP = "ON_TAP"
    OLYMPIC = "OLYMPIC"
    KHAC = "KHAC"


class Visibility(models.TextChoices):
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"
    HIDDEN = "HIDDEN"


class PublishRequestStatus(models.TextChoices):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


COLOR_VALIDATOR = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Expected #RRGGBB")


class Subject(Timestamped):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    levels = ArrayField(models.CharField(max_length=10), default=list, blank=True)
    has_formula = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class School(Timestamped):
    name = models.CharField(max_length=200, unique=True)


class Major(Timestamped):
    name = models.CharField(max_length=200, unique=True)


class TaxonomyKind(models.TextChoices):
    SUBJECT = "SUBJECT"
    SCHOOL = "SCHOOL"
    MAJOR = "MAJOR"


class TaxonomyAlias(Timestamped):
    kind = models.CharField(max_length=7, choices=TaxonomyKind.choices)
    key = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.CASCADE)
    school = models.ForeignKey(School, null=True, blank=True, on_delete=models.CASCADE)
    major = models.ForeignKey(Major, null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=("kind", "key"), name="taxonomy_alias_key_unique"),
            models.CheckConstraint(
                condition=(
                    Q(
                        kind="SUBJECT",
                        subject__isnull=False,
                        school__isnull=True,
                        major__isnull=True,
                    )
                    | Q(
                        kind="SCHOOL",
                        subject__isnull=True,
                        school__isnull=False,
                        major__isnull=True,
                    )
                    | Q(
                        kind="MAJOR", subject__isnull=True, school__isnull=True, major__isnull=False
                    )
                ),
                name="taxonomy_alias_one_target",
            ),
        )


class TaxonomyProposal(Timestamped):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        APPROVED = "APPROVED"
        REJECTED = "REJECTED"

    kind = models.CharField(max_length=7, choices=TaxonomyKind.choices)
    name = models.CharField(max_length=200)
    key = models.CharField(max_length=200)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_taxonomy_proposals",
    )
    target_id = models.PositiveBigIntegerField(null=True, blank=True)
    reason = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("kind", "key"),
                condition=Q(status="PENDING"),
                name="one_pending_taxonomy_name",
            ),
        )


class Exam(Timestamped):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    subtitle = models.CharField(max_length=300, blank=True)
    icon = models.CharField(max_length=16, blank=True)
    color = models.CharField(max_length=9, blank=True, validators=[COLOR_VALIDATOR])
    level = models.CharField(max_length=10, choices=Level.choices)
    grade = models.PositiveSmallIntegerField(null=True, blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT)
    exam_type = models.CharField(max_length=16, choices=ExamType.choices)
    schools = models.ManyToManyField(School, blank=True)
    majors = models.ManyToManyField(Major, blank=True)
    province = models.CharField(max_length=100, blank=True)
    year = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(2000)]
    )
    term = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    scoring_preset = models.CharField(max_length=20)
    max_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    visibility = models.CharField(
        max_length=8, choices=Visibility.choices, default=Visibility.PRIVATE
    )
    has_answer_key = models.BooleanField(default=False)
    question_count = models.PositiveSmallIntegerField(default=0)
    attempt_count = models.PositiveIntegerField(default=0)
    deleted_at = models.DateTimeField(null=True, blank=True)
    source_kind = models.CharField(max_length=10)
    source_job = models.UUIDField(null=True, blank=True)
    source = models.CharField(max_length=500, blank=True)
    is_system_sample = models.BooleanField(default=False)
    search_text = models.TextField(blank=True)

    class Meta:
        indexes = (
            models.Index(
                fields=("visibility", "level", "grade", "-created_at"), name="exam_visibility_idx"
            ),
            models.Index(fields=("owner", "-created_at"), name="exam_owner_idx"),
            models.Index(fields=("subject", "level", "grade"), name="exam_subject_idx"),
            models.Index(fields=("exam_type", "year"), name="exam_type_year_idx"),
        )
        constraints = (
            models.CheckConstraint(
                condition=(
                    Q(level="TIEU_HOC", grade__gte=1, grade__lte=5)
                    | Q(level="THCS", grade__gte=6, grade__lte=9)
                    | Q(level="THPT", grade__gte=10, grade__lte=12)
                    | Q(level__in=["DAI_HOC", "KHAC"], grade__isnull=True)
                ),
                name="exam_level_grade_valid",
            ),
        )


class PublishRequest(Timestamped):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="publish_requests")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="publish_requests"
    )
    status = models.CharField(max_length=10, choices=PublishRequestStatus.choices)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_publish_requests",
    )
    reason = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("exam",), condition=Q(status="PENDING"), name="one_pending_publish_request"
            ),
        )


class Section(Timestamped):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="sections")
    order = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=12)
    scoring = models.JSONField()

    class Meta:
        ordering = ("order",)
        constraints = (
            models.UniqueConstraint(fields=("exam", "order"), name="section_exam_order_unique"),
        )


class Chapter(Timestamped):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="chapters")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=300, blank=True)
    color = models.CharField(max_length=9, blank=True, validators=[COLOR_VALIDATOR])
    order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ("order",)
        constraints = (
            models.UniqueConstraint(fields=("exam", "code"), name="chapter_exam_code_unique"),
        )


class Passage(Timestamped):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="passages")
    source_tmp_id = models.CharField(max_length=80, blank=True)
    order = models.PositiveSmallIntegerField()
    text = models.TextField()

    class Meta:
        ordering = ("order",)
        constraints = (
            models.UniqueConstraint(
                fields=("section", "order"), name="passage_section_order_unique"
            ),
        )


class Question(Timestamped):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="questions")
    source_tmp_id = models.CharField(max_length=80, blank=True)
    provenance = models.JSONField(default=dict)
    passage = models.ForeignKey(Passage, on_delete=models.SET_NULL, null=True, blank=True)
    chapter = models.ForeignKey(Chapter, on_delete=models.SET_NULL, null=True, blank=True)
    order = models.PositiveSmallIntegerField()
    number_label = models.CharField(max_length=10, blank=True)
    kind = models.CharField(max_length=12)
    tf_answer = models.BooleanField(null=True, blank=True)
    text = models.TextField()
    explanation = models.TextField(blank=True)
    points = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    short_answer = models.CharField(max_length=40, blank=True)
    short_tolerance = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    essay_model_answer = models.TextField(blank=True)

    class Meta:
        ordering = ("order",)
        constraints = (
            models.UniqueConstraint(
                fields=("section", "order"), name="question_section_order_unique"
            ),
        )


class Choice(Timestamped):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    label = models.CharField(max_length=2)
    text = models.TextField()
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ("label",)
        constraints = (
            models.UniqueConstraint(
                fields=("question", "label"), name="choice_question_label_unique"
            ),
        )


class Statement(Timestamped):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="statements")
    label = models.CharField(max_length=2)
    text = models.TextField()
    is_true = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ("label",)
        constraints = (
            models.UniqueConstraint(
                fields=("question", "label"), name="statement_question_label_unique"
            ),
        )


class Asset(Timestamped):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ImageField(upload_to="assets/")
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    alt_text = models.CharField(max_length=300, blank=True)
    source_job = models.UUIDField(null=True, blank=True)


class QuestionAsset(Timestamped):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, null=True, blank=True)
    passage = models.ForeignKey(Passage, on_delete=models.CASCADE, null=True, blank=True)
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT)
    order = models.PositiveSmallIntegerField()

    class Meta:
        constraints = (
            models.CheckConstraint(
                condition=(
                    Q(question__isnull=False, passage__isnull=True)
                    | Q(question__isnull=True, passage__isnull=False)
                ),
                name="question_asset_one_parent",
            ),
        )
