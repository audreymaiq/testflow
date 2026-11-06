"""Identity business operations."""

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

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


def request_password_reset(*, email: str) -> None:
    from .tasks import send_password_reset

    send_password_reset.apply_async(
        args=(normalize_text(email).lower(),), argsrepr="(<email-redacted>,)"
    )


def deliver_password_reset(email: str) -> None:
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is None or not user.has_usable_password():
        return
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = f"{settings.PUBLIC_WEB_ORIGIN}/reset-password/{uid}/{token}"
    send_mail(
        "Đặt lại mật khẩu TestFlow",
        f"Bạn đã yêu cầu đặt lại mật khẩu TestFlow. Liên kết có hiệu lực trong 1 giờ:\n{link}\n"
        "Nếu bạn không yêu cầu, hãy bỏ qua email này.",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


@transaction.atomic
def confirm_password_reset(*, uid: str, token: str, password: str) -> None:
    invalid = ValidationError({"token": "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn."})
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.select_for_update().get(pk=user_id, is_active=True)
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError, DjangoValidationError,
            User.DoesNotExist) as exc:
        raise invalid from exc
    if not user.has_usable_password() or not default_token_generator.check_token(user, token):
        raise invalid
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise ValidationError({"password": list(exc.messages)}) from exc
    user.set_password(password)
    user.save(update_fields=["password"])
    for outstanding in OutstandingToken.objects.filter(
        user=user, expires_at__gt=timezone.now()
    ).iterator():
        BlacklistedToken.objects.get_or_create(token=outstanding)
