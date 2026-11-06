import re

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.permissions import IsAdmin, IsReviewer


@pytest.mark.django_db
def test_registration_and_identity_constraints():
    client = APIClient()
    response = client.post(reverse("register"), {
        "username": "HọcSinh", "email": "STUDENT@example.com", "password": "HardToGuess#2026",
    })
    assert response.status_code == 201
    assert "access" in response.data
    assert "refresh" not in response.data
    assert response.cookies["tf_refresh"]["httponly"]
    user = get_user_model().objects.get(username="HọcSinh")
    assert user.email == "student@example.com"
    assert user.groups.filter(name="Student").exists()
    assert user.check_password("HardToGuess#2026")
    duplicate = client.post(reverse("register"), {
        "username": "họcsinh", "email": "other@example.com", "password": "HardToGuess#2026",
    })
    assert duplicate.status_code == 400
    assert get_user_model().objects.count() == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        get_user_model().objects.create_user(
            username="HỌCSINH", email="third@example.com", password="HardToGuess#2026"
        )


@pytest.mark.django_db
def test_token_rotation_logout_and_me():
    client = APIClient()
    client.post(reverse("register"), {
        "username": "student", "email": "student@example.com", "password": "HardToGuess#2026",
    })
    assert client.get(reverse("me")).status_code == 401
    bad = client.post(reverse("login"), {"identifier": "student", "password": "wrong"})
    assert bad.status_code == 401
    login = client.post(reverse("login"), {
        "identifier": "STUDENT@EXAMPLE.COM", "password": "HardToGuess#2026",
    })
    assert login.status_code == 200
    old_refresh = client.cookies["tf_refresh"].value
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    assert client.get(reverse("me")).status_code == 200
    refresh = client.post(reverse("refresh"))
    assert refresh.status_code == 200
    assert client.cookies["tf_refresh"].value != old_refresh
    client.cookies["tf_refresh"] = old_refresh
    assert client.post(reverse("refresh")).status_code == 401
    client.cookies["tf_refresh"] = refresh.cookies["tf_refresh"].value
    assert client.post(reverse("logout")).status_code == 204
    assert client.post(reverse("refresh")).status_code == 400


@pytest.mark.django_db
def test_cross_origin_cookie_operation_is_rejected():
    client = APIClient()
    result = client.post(reverse("register"), {
        "username": "student", "email": "student@example.com", "password": "HardToGuess#2026",
    }, HTTP_ORIGIN="https://attacker.example")
    assert result.status_code == 403
    assert get_user_model().objects.count() == 0


@pytest.mark.django_db
def test_student_cannot_use_reviewer_or_admin_permissions():
    assert set(Group.objects.values_list("name", flat=True)) >= {"Student", "Reviewer", "Admin"}
    user = get_user_model().objects.create_user(
        username="student", email="student@example.com", password="HardToGuess#2026"
    )
    student_request = type("Request", (), {"user": user})()
    assert not IsReviewer().has_permission(student_request, None)
    assert not IsAdmin().has_permission(student_request, None)
    user.groups.add(Group.objects.get(name="Reviewer"))
    assert IsReviewer().has_permission(student_request, None)
    assert not IsAdmin().has_permission(student_request, None)


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PUBLIC_WEB_ORIGIN="https://testflow.example",
)
def test_password_reset_is_private_one_time_and_revokes_sessions():
    client = APIClient()
    created = client.post(reverse("register"), {
        "username": "student", "email": "student@example.com", "password": "HardToGuess#2026",
    })
    old_access = created.data["access"]
    old_refresh = client.cookies["tf_refresh"].value
    unknown = client.post(reverse("password-reset-request"), {"email": "missing@example.com"})
    known = client.post(reverse("password-reset-request"), {"email": "STUDENT@example.com"})
    assert unknown.status_code == known.status_code == 202
    assert unknown.data == known.data
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["student@example.com"]
    match = re.search(
        r"https://testflow.example/reset-password/([^/\s]+)/([^\s]+)", mail.outbox[0].body
    )
    assert match is not None
    uid, token = match.groups()
    assert client.post(reverse("password-reset-confirm"), {
        "uid": uid, "token": token, "password": "short",
    }).status_code == 400
    assert client.post(reverse("password-reset-confirm"), {
        "uid": "invalid", "token": token, "password": "NewHardToGuess#2026",
    }).status_code == 400
    reset = client.post(reverse("password-reset-confirm"), {
        "uid": uid, "token": token, "password": "NewHardToGuess#2026",
    })
    assert reset.status_code == 204
    assert client.post(reverse("password-reset-confirm"), {
        "uid": uid, "token": token, "password": "AnotherHard#2026",
    }).status_code == 400
    client.cookies["tf_refresh"] = old_refresh
    assert client.post(reverse("refresh")).status_code == 401
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access}")
    assert client.get(reverse("me")).status_code == 401
    client.credentials()
    assert client.post(reverse("login"), {
        "identifier": "student", "password": "HardToGuess#2026",
    }).status_code == 401
    assert client.post(reverse("login"), {
        "identifier": "student", "password": "NewHardToGuess#2026",
    }).status_code == 200
