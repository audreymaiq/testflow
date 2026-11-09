from rest_framework import serializers


class TxtUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    duration_mode = serializers.ChoiceField(choices=["FILE", "TIMED", "UNTIMED"], default="FILE")
    duration_minutes = serializers.IntegerField(required=False, min_value=1, max_value=300)

    def validate(self, attrs):
        mode = attrs["duration_mode"]
        has_minutes = "duration_minutes" in attrs
        if mode == "TIMED" and not has_minutes:
            raise serializers.ValidationError({"duration_minutes": "Nhập thời gian làm bài."})
        if mode != "TIMED" and has_minutes:
            raise serializers.ValidationError(
                {"duration_minutes": "Chỉ nhập số phút cho bài có giờ."}
            )
        return attrs


class DraftReplaceSerializer(serializers.Serializer):
    draft = serializers.JSONField()


class DiscardSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
