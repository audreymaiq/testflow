"""Separate input and output serializers for session APIs."""

from rest_framework import serializers

from .models import SessionMode


class CreateSessionSerializer(serializers.Serializer):
    exam_id = serializers.UUIDField()
    mode = serializers.ChoiceField(choices=SessionMode.choices)
    chapter_ids = serializers.ListField(child=serializers.CharField(), required=False)
    include_wrong_bank = serializers.BooleanField(required=False)
    only_wrong_bank = serializers.BooleanField(required=False)
    shuffle_questions = serializers.BooleanField(required=False)
    shuffle_options = serializers.BooleanField(required=False)


class SaveAnswerSerializer(serializers.Serializer):
    value = serializers.JSONField()
    flagged = serializers.BooleanField(required=False, default=False)
    time_spent_seconds = serializers.IntegerField(
        required=False, min_value=0, max_value=86400, default=0
    )


class EmptySerializer(serializers.Serializer):
    pass


class SessionResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    exam_id = serializers.UUIDField()
    mode = serializers.CharField()
    status = serializers.CharField()
    deadline_at = serializers.DateTimeField(allow_null=True)
    server_time = serializers.DateTimeField()
    question_order = serializers.JSONField()
    sections = serializers.JSONField()
    answers = serializers.JSONField()


class AnswerResponseSerializer(serializers.Serializer):
    question_id = serializers.UUIDField()
    value = serializers.JSONField(required=False)
    flagged = serializers.BooleanField(required=False)
    feedback = serializers.JSONField(required=False)


class ResultResponseSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    exam_id = serializers.UUIDField()
    mode = serializers.CharField()
    status = serializers.CharField()
    questions = serializers.JSONField()
    counts = serializers.JSONField()
    correct_percent = serializers.CharField()
    total_score = serializers.CharField(allow_null=True)
    max_score = serializers.CharField(allow_null=True)
