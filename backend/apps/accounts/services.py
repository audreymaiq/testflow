"""Identity business operations."""

from django.contrib.auth import authenticate
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework.exceptions import AuthenticationFailed, ValidationError

from apps.common.text import normalize_text

from .models import User


@transaction.atomic
def register_user(*, username: str, email: str, password: str) -> User:
    username = normalize_text(username)
    email = normalize_text(email).lower()
    if not username or not email:
        raise ValidationError({"username": "Tên đăng nhập và email là bắt buộc."})
    try:
        UnicodeUsernameValidator()(username)
    except DjangoValidationError as exc:
        raise ValidationError({"username": list(exc.messages)}) from exc
    if User.objects.filter(username__iexact=username).exists():
        raise ValidationError({"username": "Tên đăng nhập đã được sử dụng."})
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({"email": "Email đã được sử dụng."})
    user = User(username=username, email=email)
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise ValidationError({"password": list(exc.messages)}) from exc
    user.set_password(password)
    try:
        user.save()
    except IntegrityError as exc:
        raise ValidationError({"identifier": "Tên đăng nhập hoặc email đã được sử dụng."}) from exc
    student, _ = Group.objects.get_or_create(name="Student")
    user.groups.add(student)
    return user


def login_user(*, identifier: str, password: str) -> User:
    identifier = normalize_text(identifier)
    user = User.objects.filter(username__iexact=identifier).first()
    if user is None:
        user = User.objects.filter(email__iexact=identifier).first()
    if user is None or not user.is_active:
        raise AuthenticationFailed("Tên đăng nhập hoặc mật khẩu không đúng.")
    authenticated = authenticate(username=user.username, password=password)
    if authenticated is None:
        raise AuthenticationFailed("Tên đăng nhập hoặc mật khẩu không đúng.")
    return authenticated
