"""S1b ownership and reviewer publication transitions."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework.test import APIClient
from testflow_contracts.exam import ExamDraft

from apps.catalog.models import (
    Exam,
    PublishRequest,
    PublishRequestStatus,
    School,
    Subject,
    Visibility,
)
from apps.catalog.services import create_exam
from tests.test_catalog import draft_data


@pytest.fixture
def publication_users(db):
    Subject.objects.update_or_create(code="toan", defaults={"name": "Toán", "levels": ["THPT"]})
    School.objects.get_or_create(name="Trường Mẫu")
    model = get_user_model()
    owner = model.objects.create_user("owner", "owner@example.test", "HardToGuess#2026")
    other = model.objects.create_user("other", "other@example.test", "HardToGuess#2026")
    reviewer = model.objects.create_user("reviewer", "reviewer@example.test", "HardToGuess#2026")
    reviewer.groups.add(Group.objects.get(name="Reviewer"))
    admin = model.objects.create_user(
        "admin", "admin@example.test", "HardToGuess#2026", is_staff=True
    )
    admin.groups.add(Group.objects.get(name="Admin"))
    exam = create_exam(ExamDraft.model_validate(draft_data()), owner=owner)
    return exam, owner, other, reviewer, admin


@pytest.mark.django_db
def test_publication_requires_reviewer_and_private_visibility_is_immediate(publication_users):
    exam, owner, other, reviewer, _ = publication_users
    client = APIClient()
    visibility_url = reverse("exam-visibility", kwargs={"exam_id": exam.id})
    detail_url = reverse("exam-detail", kwargs={"exam_id": exam.id})
    client.force_authenticate(user=other)
    assert client.post(visibility_url, {"visibility": "PUBLIC"}).status_code == 404
    assert client.get(reverse("publish-request-list")).status_code == 403

    client.force_authenticate(user=owner)
    requested = client.post(visibility_url, {"visibility": "PUBLIC"}, format="json")
    assert requested.status_code == 200
    request_id = requested.data["request_id"]
    assert client.post(visibility_url, {"visibility": "PUBLIC"}).data["request_id"] == request_id
    assert (
        PublishRequest.objects.filter(exam=exam, status=PublishRequestStatus.PENDING).count() == 1
    )
    exam.refresh_from_db()
    assert exam.visibility == Visibility.PRIVATE

    client.force_authenticate(user=reviewer)
    queue = client.get(reverse("publish-request-list"))
    assert queue.data["count"] == 1
    review = client.get(reverse("publish-request-detail", kwargs={"request_id": request_id}))
    assert review.data["draft"]["sections"][0]["questions"][0]["choices"][1]["is_correct"]
    approved = client.post(reverse("publish-request-approve", kwargs={"request_id": request_id}))
    assert approved.status_code == 200
    assert approved.data["status"] == "APPROVED"
    exam.refresh_from_db()
    assert exam.visibility == Visibility.PUBLIC

    client.force_authenticate(user=other)
    assert client.get(detail_url).status_code == 200
    assert client.get(reverse("exam-list")).data["count"] == 1
    client.force_authenticate(user=owner)
    assert client.post(visibility_url, {"visibility": "PRIVATE"}).status_code == 200
    client.force_authenticate(user=other)
    assert client.get(detail_url).status_code == 404
    assert client.get(reverse("exam-list")).data["count"] == 0
    client.force_authenticate(user=reviewer)
    assert (
        client.post(
            reverse("publish-request-approve", kwargs={"request_id": request_id})
        ).status_code
        == 409
    )
    assert (
        client.get(reverse("publish-request-detail", kwargs={"request_id": request_id})).status_code
        == 404
    )


@pytest.mark.django_db
def test_rejection_soft_delete_and_admin_hide(publication_users):
    exam, owner, other, reviewer, admin = publication_users
    client = APIClient()
    visibility_url = reverse("exam-visibility", kwargs={"exam_id": exam.id})
    detail_url = reverse("exam-detail", kwargs={"exam_id": exam.id})
    client.force_authenticate(user=owner)
    request_id = client.post(visibility_url, {"visibility": "PUBLIC"}).data["request_id"]
    client.force_authenticate(user=reviewer)
    reject_url = reverse("publish-request-reject", kwargs={"request_id": request_id})
    assert client.post(reject_url, {"reason": ""}).status_code == 400
    assert client.post(reject_url, {"reason": "Chưa rõ quyền sử dụng."}).status_code == 200
    exam.refresh_from_db()
    assert exam.visibility == Visibility.PRIVATE
    client.force_authenticate(user=owner)
    next_id = client.post(visibility_url, {"visibility": "PUBLIC"}).data["request_id"]
    assert next_id != request_id
    assert client.post(visibility_url, {"visibility": "PRIVATE"}).status_code == 200
    assert PublishRequest.objects.get(pk=next_id).status == PublishRequestStatus.REJECTED
    final_id = client.post(visibility_url, {"visibility": "PUBLIC"}).data["request_id"]
    client.force_authenticate(user=admin)
    assert (
        client.post(reverse("publish-request-approve", kwargs={"request_id": final_id})).status_code
        == 200
    )
    client.force_authenticate(user=other)
    assert client.post(reverse("exam-hide", kwargs={"exam_id": exam.id})).status_code == 403
    client.force_authenticate(user=admin)
    assert client.post(reverse("exam-hide", kwargs={"exam_id": exam.id})).status_code == 200
    client.force_authenticate(user=other)
    assert client.get(detail_url).status_code == 404
    client.force_authenticate(user=owner)
    assert client.post(visibility_url, {"visibility": "PRIVATE"}).status_code == 409

    # A separate owned exam can be soft-deleted without erasing historical rows.
    private = create_exam(ExamDraft.model_validate(draft_data()), owner=owner)
    private_url = reverse("exam-detail", kwargs={"exam_id": private.id})
    assert client.delete(private_url).status_code == 204
    assert Exam.objects.filter(pk=private.id, deleted_at__isnull=False).exists()
    assert client.get(private_url).status_code == 404


@pytest.mark.django_db
def test_source_is_required_and_owner_cannot_review_own_request(publication_users):
    exam, owner, _, reviewer, _ = publication_users
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse("exam-visibility", kwargs={"exam_id": exam.id})
    exam.source = ""
    exam.save(update_fields=("source",))
    assert client.post(url, {"visibility": "PUBLIC"}).status_code == 400
    assert not PublishRequest.objects.filter(exam=exam).exists()
    exam.source = "Tự biên soạn"
    exam.save(update_fields=("source",))
    request_id = client.post(url, {"visibility": "PUBLIC"}).data["request_id"]
    owner.groups.add(Group.objects.get(name="Reviewer"))
    assert (
        client.post(
            reverse("publish-request-approve", kwargs={"request_id": request_id})
        ).status_code
        == 403
    )
    client.force_authenticate(user=reviewer)
    assert (
        client.post(
            reverse("publish-request-approve", kwargs={"request_id": request_id})
        ).status_code
        == 200
    )
