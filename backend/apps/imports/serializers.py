from rest_framework import serializers


class TxtUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class DraftReplaceSerializer(serializers.Serializer):
    draft = serializers.JSONField()
