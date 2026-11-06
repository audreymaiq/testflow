"""Validated external identity contracts."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import User
from .services import register_user


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "email", "display_name", "school", "grade", "roles")
        read_only_fields = ("id", "username", "email", "school", "roles")

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_roles(self, obj) -> list[str]:
        return list(obj.groups.values_list("name", flat=True))


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def create(self, validated_data):
        return register_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class LogoutSerializer(serializers.Serializer):
    pass


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=100)
    token = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
