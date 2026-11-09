"""Reviewer access to pending imports without changing exam ownership."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.catalog.models import Exam, School, Subject
from apps.imports.models import Draft


def client(user=None):
    api = APIClient()
    if user:
        api.force_authenticate(user)
    return api


def upload(api, title):
    text = (
        f"#TITLE: {title}\n#SUBJECT: toan\n#LEVEL: THPT\n#GRADE: 12\n"
        "#TYPE: ON_TAP\n#TRUONG: Trường Mẫu\n[CH1] Số học\n"
        "Hai cộng hai bằng mấy?\nA. Ba\nB. Bốn\n=>B\n"
    )
    return api.post(
        "/api/v1/imports/txt/",
        {"file": SimpleUploadedFile("questions.txt", text.encode("utf-8"))},
        format="multipart",
    )


@pytest.fixture
def users(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    Subject.objects.update_or_create(code="toan", defaults={"name": "Toán", "levels": ["THPT"]})
    School.objects.get_or_create(name="Trường Mẫu")
    User = get_user_model()
    owner = User.objects.create_user(
        "queue_owner", email="queue_owner@example.com", password="HardToGuess#2026"
    )
    other = User.objects.create_user(
        "queue_other", email="queue_other@example.com", password="HardToGuess#2026"
    )
    reviewer = User.objects.create_user(
        "queue_reviewer", email="queue_reviewer@example.com", password="HardToGuess#2026"
    )
    reviewer.groups.add(Group.objects.get_or_create(name="Reviewer")[0])
    return owner, other, reviewer


@pytest.mark.django_db
def test_review_queue_is_role_scoped_and_priority_ordered(users):
    owner, other, reviewer = users
    first = upload(client(owner), "Đề thứ nhất")
    second = upload(client(other), "Đề thứ hai")
    assert first.status_code == second.status_code == 201
    Draft.objects.filter(job_id=first.data["id"]).update(priority_score=2)
    Draft.objects.filter(job_id=second.data["id"]).update(priority_score=5)

    url = "/api/v1/imports/review-queue/"
    assert client().get(url).status_code == 401
    assert client(owner).get(url).status_code == 403
    queue = client(reviewer).get(url)
    assert queue.status_code == 200
    assert [item["id"] for item in queue.data["results"]] == [second.data["id"], first.data["id"]]
    assert client(other).get(f"/api/v1/imports/{first.data['id']}/").status_code == 404
    assert client(reviewer).get(f"/api/v1/imports/{first.data['id']}/").status_code == 200


@pytest.mark.django_db
def test_reviewer_confirm_keeps_uploader_as_private_exam_owner(users):
    owner, other, reviewer = users
    response = upload(client(owner), "Đề người học")
    assert response.status_code == 201
    job_id = response.data["id"]

    assert client(other).post(f"/api/v1/imports/{job_id}/confirm/").status_code == 404
    confirmed = client(reviewer).post(f"/api/v1/imports/{job_id}/confirm/")
    assert confirmed.status_code == 200, confirmed.data
    exam = Exam.objects.get(pk=confirmed.data["exam_id"])
    assert exam.owner_id == owner.id
    assert exam.visibility == "PRIVATE"
    assert client(reviewer).post(f"/api/v1/imports/{job_id}/confirm/").status_code == 409
    assert client(reviewer).get("/api/v1/imports/review-queue/").data["count"] == 0
