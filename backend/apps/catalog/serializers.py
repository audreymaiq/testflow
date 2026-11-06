"""Catalog HTTP input and output contracts."""

from django.db.models import Count
from drf_spectacular.utils import extend_schema_field
from pydantic import ValidationError as ContractValidationError
from rest_framework import serializers
from testflow_contracts.exam import ExamDraft

from .models import (
    Chapter,
    Exam,
    PublishRequest,
    PublishRequestStatus,
    Section,
    Subject,
    TaxonomyKind,
    Visibility,
)


class ManualCreateSerializer(serializers.Serializer):
    draft = serializers.JSONField()

    def validate_draft(self, value):
        try:
            return ExamDraft.model_validate(value)
        except ContractValidationError as exc:
            raise serializers.ValidationError(exc.errors(include_url=False)) from exc


class ExamFilterSerializer(serializers.Serializer):
    level = serializers.CharField(required=False)
    grade = serializers.IntegerField(required=False)
    subject = serializers.CharField(required=False)
    school = serializers.CharField(required=False)
    major = serializers.CharField(required=False)
    year = serializers.IntegerField(required=False)
    exam_type = serializers.CharField(required=False)
    has_answer_key = serializers.BooleanField(required=False)
    mine = serializers.BooleanField(required=False)
    q = serializers.CharField(required=False, max_length=200)
    ordering = serializers.ChoiceField(
        required=False, choices=("-created_at", "-attempt_count", "year")
    )


class ExamListSerializer(serializers.ModelSerializer):
    subject = serializers.SlugRelatedField(read_only=True, slug_field="name")
    schools = serializers.SlugRelatedField(read_only=True, slug_field="name", many=True)
    majors = serializers.SlugRelatedField(read_only=True, slug_field="name", many=True)
    chapter_count = serializers.SerializerMethodField()

    @extend_schema_field(serializers.IntegerField())
    def get_chapter_count(self, exam):
        return len(exam.chapters.all())

    class Meta:
        model = Exam
        fields: tuple[str, ...] = (
            "id",
            "title",
            "subtitle",
            "icon",
            "color",
            "level",
            "grade",
            "subject",
            "exam_type",
            "schools",
            "majors",
            "province",
            "year",
            "term",
            "duration_minutes",
            "visibility",
            "has_answer_key",
            "question_count",
            "chapter_count",
            "is_system_sample",
            "attempt_count",
            "created_at",
        )


class ChapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chapter
        fields = ("id", "code", "name", "description", "color", "order")


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ("id", "order", "title", "kind")


class SectionStatsSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    count = serializers.IntegerField()


class ChapterStatsSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    count = serializers.IntegerField()


class ExamDetailSerializer(ExamListSerializer):
    chapters = ChapterSerializer(many=True, read_only=True)
    sections = SectionSerializer(many=True, read_only=True)
    section_stats = serializers.SerializerMethodField()
    chapter_stats = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField())
    def get_is_owner(self, exam):
        user = self.context.get("request").user if self.context.get("request") else None
        return bool(user and user.is_authenticated and exam.owner_id == user.pk)

    @extend_schema_field(SectionStatsSerializer(many=True))
    def get_section_stats(self, exam):
        return list(
            exam.sections.order_by("order")
            .annotate(count=Count("questions"))
            .values("id", "title", "count")
        )

    @extend_schema_field(ChapterStatsSerializer(many=True))
    def get_chapter_stats(self, exam):
        return list(
            exam.chapters.order_by("order")
            .annotate(count=Count("question"))
            .values("id", "name", "count")
        )

    class Meta(ExamListSerializer.Meta):
        fields: tuple[str, ...] = (
            *ExamListSerializer.Meta.fields,
            "chapters",
            "sections",
            "section_stats",
            "chapter_stats",
            "is_owner",
            "source",
        )


class PreviewChoiceSerializer(serializers.Serializer):
    label = serializers.CharField()
    text = serializers.CharField()


class PreviewQuestionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    text = serializers.CharField()
    choices = PreviewChoiceSerializer(many=True)


class PreviewResponseSerializer(serializers.Serializer):
    questions = PreviewQuestionSerializer(many=True)


class FacetsResponseSerializer(serializers.Serializer):
    subjects = serializers.ListField(child=serializers.ListField(child=serializers.CharField()))
    schools = serializers.ListField(child=serializers.CharField())
    majors = serializers.ListField(child=serializers.CharField())
    levels = serializers.ListField(child=serializers.CharField())


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ("code", "name", "levels", "has_formula")


class TaxonomyLookupSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=TaxonomyKind.choices)
    name = serializers.CharField(max_length=200)


class ProfileSchoolSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, allow_blank=True)


class TaxonomyCreateSerializer(TaxonomyLookupSerializer):
    has_formula = serializers.BooleanField(required=False)


class VisibilityChangeSerializer(serializers.Serializer):
    visibility = serializers.CharField()

    def validate_visibility(self, value):
        if value not in (Visibility.PRIVATE, Visibility.PUBLIC):
            raise serializers.ValidationError("Chỉ có thể chọn PRIVATE hoặc PUBLIC.")
        return value


class VisibilityResponseSerializer(serializers.Serializer):
    visibility = serializers.CharField()
    request_id = serializers.IntegerField(allow_null=True)


class PublicationRequestSerializer(serializers.ModelSerializer):
    exam_title = serializers.CharField(source="exam.title", read_only=True)
    source = serializers.CharField(source="exam.source", read_only=True)
    owner_name = serializers.CharField(source="requested_by.username", read_only=True)

    class Meta:
        model = PublishRequest
        fields: tuple[str, ...] = (
            "id",
            "exam",
            "exam_title",
            "source",
            "owner_name",
            "status",
            "reason",
            "created_at",
            "decided_at",
        )


class PublicationDetailSerializer(PublicationRequestSerializer):
    draft = serializers.SerializerMethodField()

    @extend_schema_field(serializers.JSONField())
    def get_draft(self, request):
        from .services import export_exam

        return export_exam(request.exam).model_dump(mode="json")

    class Meta(PublicationRequestSerializer.Meta):
        fields: tuple[str, ...] = (*PublicationRequestSerializer.Meta.fields, "draft")


class PublicationFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=(PublishRequestStatus.PENDING,),
        required=False,
        default=PublishRequestStatus.PENDING,
    )


class PublicationDecisionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)
