"""Catalog HTTP input and output contracts."""

from pydantic import ValidationError as ContractValidationError
from rest_framework import serializers
from testflow_contracts.exam import ExamDraft

from .models import Chapter, Exam, Section, Subject


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


class ExamDetailSerializer(ExamListSerializer):
    chapters = ChapterSerializer(many=True, read_only=True)
    sections = SectionSerializer(many=True, read_only=True)

    class Meta(ExamListSerializer.Meta):
        fields: tuple[str, ...] = (
            *ExamListSerializer.Meta.fields,
            "chapters",
            "sections",
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
