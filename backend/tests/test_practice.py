"""S1 session integration and answer confidentiality against PostgreSQL."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from testflow_contracts.exam import ExamDraft

from apps.catalog.models import Subject
from apps.catalog.services import create_exam
from apps.practice.models import Answer, Session, SessionStatus, WrongQuestion
from apps.practice.schemas import SessionConfig
from apps.practice.selection import build_question_set
from apps.practice.services import create_session
from tests.test_catalog import draft_data


@pytest.fixture
def exam_users(db):
    Subject.objects.update_or_create(code="toan", defaults={"name": "Toán", "levels": ["THPT"]})
    owner = get_user_model().objects.create_user(
        username="owner", email="owner@example.com", password="HardToGuess#2026"
    )
    other = get_user_model().objects.create_user(
        username="other", email="other@example.com", password="HardToGuess#2026"
    )
    draft = draft_data()
    draft["metadata"]["duration_minutes"] = 30
    exam = create_exam(ExamDraft.model_validate(draft), owner=owner)
    question_id = exam.sections.first().questions.first().id
    return exam, question_id, owner, other


@pytest.mark.django_db
def test_timed_session_never_leaks_answer_before_submit(exam_users):
    exam, question_id, owner, other = exam_users
    client = APIClient()
    client.force_authenticate(user=owner)
    created = client.post(
        reverse("practice-sessions"), {"exam_id": str(exam.id), "mode": "TIMED"}, format="json"
    )
    assert created.status_code == 201
    session_id = created.data["id"]
    assert created.data["deadline_at"]
    assert str(question_id) in str(created.data["question_order"])
    for secret in ("is_correct", "correct_answer", "explanation", "short_answer", "tf_answer"):
        assert secret not in str(created.data)
    assert (
        client.get(reverse("practice-result", kwargs={"session_id": session_id})).status_code == 409
    )

    client.force_authenticate(user=other)
    assert (
        client.get(reverse("practice-session", kwargs={"session_id": session_id})).status_code
        == 404
    )
    assert (
        client.put(
            reverse(
                "practice-answer", kwargs={"session_id": session_id, "question_id": question_id}
            ),
            {"value": {"choice": "B"}},
            format="json",
        ).status_code
        == 404
    )
    client.force_authenticate(user=owner)
    answer_url = reverse(
        "practice-answer", kwargs={"session_id": session_id, "question_id": question_id}
    )
    saved = client.put(answer_url, {"value": {"choice": "B"}}, format="json")
    assert saved.status_code == 200
    assert "feedback" not in saved.data
    reloaded = client.get(reverse("practice-session", kwargs={"session_id": session_id}))
    assert reloaded.data["answers"][0]["value"] == {"choice": "B"}
    assert "correct_answer" not in str(reloaded.data)
    submitted = client.post(reverse("practice-submit", kwargs={"session_id": session_id}))
    assert submitted.status_code == 200
    assert submitted.data["total_score"] == "10.00"
    assert submitted.data["questions"][0]["correct_answer"] == {"choice": "B"}
    assert (
        client.post(reverse("practice-submit", kwargs={"session_id": session_id})).data
        == submitted.data
    )
    assert (
        client.get(reverse("practice-result", kwargs={"session_id": session_id})).data
        == submitted.data
    )
    assert Answer.objects.filter(session_id=session_id).count() == 1


@pytest.mark.django_db
def test_deadline_is_server_owned_and_expiry_is_lazy(exam_users):
    exam, question_id, owner, _ = exam_users
    client = APIClient()
    client.force_authenticate(user=owner)
    session = create_session(
        user=owner, exam_id=exam.id, mode="TIMED", config=SessionConfig(seed=42)
    )
    Session.objects.filter(pk=session.id).update(deadline_at=timezone.now() - timedelta(seconds=1))
    answer_url = reverse(
        "practice-answer", kwargs={"session_id": session.id, "question_id": question_id}
    )
    assert client.put(answer_url, {"value": {"choice": "B"}}, format="json").status_code == 409
    assert Answer.objects.filter(session=session).count() == 0
    result = client.get(reverse("practice-result", kwargs={"session_id": session.id}))
    assert result.status_code == 200
    assert result.data["status"] == "EXPIRED"
    session.refresh_from_db()
    assert session.status == SessionStatus.EXPIRED


@pytest.mark.django_db
def test_practice_feedback_locks_answer_and_updates_wrong_bank(exam_users):
    exam, question_id, owner, _ = exam_users
    client = APIClient()
    client.force_authenticate(user=owner)
    created = client.post(
        reverse("practice-sessions"), {"exam_id": str(exam.id), "mode": "PRACTICE"}, format="json"
    )
    session_id = created.data["id"]
    answer_url = reverse(
        "practice-answer", kwargs={"session_id": session_id, "question_id": question_id}
    )
    wrong = client.put(answer_url, {"value": {"choice": "A"}}, format="json")
    assert wrong.status_code == 200
    assert wrong.data["feedback"]["status"] == "WRONG"
    assert wrong.data["feedback"]["correct_answer"] == {"choice": "B"}
    assert WrongQuestion.objects.get(user=owner, question_id=question_id).times_wrong == 1
    assert client.put(answer_url, {"value": {"choice": "A"}}, format="json").status_code == 200
    assert WrongQuestion.objects.get(user=owner, question_id=question_id).times_wrong == 1
    assert client.put(answer_url, {"value": {"choice": "B"}}, format="json").status_code == 409
    client.post(reverse("practice-submit", kwargs={"session_id": session_id}))
    second = client.post(
        reverse("practice-sessions"), {"exam_id": str(exam.id), "mode": "PRACTICE"}, format="json"
    )
    assert second.status_code == 201
    correct_url = reverse(
        "practice-answer", kwargs={"session_id": second.data["id"], "question_id": question_id}
    )
    correct = client.put(correct_url, {"value": {"choice": "B"}}, format="json")
    assert correct.data["feedback"]["status"] == "CORRECT"
    assert not WrongQuestion.objects.filter(user=owner, question_id=question_id).exists()


def test_question_shuffle_is_reproducible():
    questions = {"s1": [("q1", "c1", ("A", "B", "C")), ("q2", "c2", ("A", "B", "C"))]}
    config = SessionConfig(seed=42, shuffle_questions=True, shuffle_options=True)
    assert build_question_set(questions, config, set()) == build_question_set(
        questions, config, set()
    )
    only = SessionConfig(seed=42, only_wrong_bank=True)
    assert build_question_set(questions, only, {"q2"})[0] == {"s1": ["q2"]}
