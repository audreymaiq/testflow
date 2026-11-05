from rest_framework import serializers


class TxtUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class DraftReplaceSerializer(serializers.Serializer):
    draft = serializers.JSONField()


class DiscardSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
