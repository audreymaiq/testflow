"""S1 session integration and answer confidentiality against PostgreSQL."""

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from testflow_contracts.exam import ExamDraft

from apps.catalog.management.commands.seed_thpt_demo import TITLE
from apps.catalog.models import Exam, School, Subject, Visibility
from apps.catalog.services import create_exam, hide_exam, make_private, soft_delete_exam
from apps.practice.models import Answer, Session, SessionStatus, WrongQuestion
from apps.practice.schemas import SessionConfig
from apps.practice.selection import build_question_set
from apps.practice.services import create_session
from tests.test_catalog import draft_data


@pytest.fixture
def exam_users(db):
    Subject.objects.update_or_create(code="toan", defaults={"name": "Toán", "levels": ["THPT"]})
    School.objects.get_or_create(name="Trường Mẫu")
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
def test_active_session_reuse_does_not_silently_switch_modes(exam_users):
    exam, _, owner, _ = exam_users
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse("practice-sessions")
    first = client.post(url, {"exam_id": str(exam.id), "mode": "TIMED"}, format="json")
    assert first.status_code == 201
    same_mode = client.post(url, {"exam_id": str(exam.id), "mode": "TIMED"}, format="json")
    assert same_mode.status_code == 201
    assert same_mode.data["id"] == first.data["id"]
    other_mode = client.post(url, {"exam_id": str(exam.id), "mode": "PRACTICE"}, format="json")
    assert other_mode.status_code == 409
    assert other_mode.data["error"]["code"] == "SESSION_MODE_CONFLICT"
    assert Session.objects.filter(user=owner, exam=exam).count() == 1


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


@pytest.mark.django_db
def test_personal_history_stats_and_wrong_summary_are_scoped(exam_users):
    exam, question_id, owner, other = exam_users
    client = APIClient()
    client.force_authenticate(user=owner)
    created = client.post(
        reverse("practice-sessions"), {"exam_id": str(exam.id), "mode": "PRACTICE"}, format="json"
    )
    client.put(
        reverse(
            "practice-answer", kwargs={"session_id": created.data["id"], "question_id": question_id}
        ),
        {"value": {"choice": "A"}},
        format="json",
    )
    client.post(reverse("practice-submit", kwargs={"session_id": created.data["id"]}))
    summary_url = reverse("practice-exam-summary", kwargs={"exam_id": exam.id})
    assert client.get(summary_url).data == {"wrong_question_count": 1, "session_count": 1}
    history = client.get(reverse("practice-history"))
    assert history.data["count"] == 1
    assert history.data["results"][0]["exam_title"] == exam.title
    assert history.data["results"][0]["total_questions"] == 1
    assert history.data["results"][0]["answered_questions"] == 1
    assert client.get(reverse("practice-history"), {"status": "IN_PROGRESS"}).data["count"] == 0
    assert client.get(reverse("practice-history"), {"status": "INVALID"}).status_code == 400
    assert client.get(reverse("practice-stats")).data == {
        "total_sessions": 1,
        "completed_sessions": 1,
        "timed_sessions": 0,
        "practice_sessions": 1,
    }

    client.force_authenticate(user=other)
    assert client.get(summary_url).status_code == 404
    assert client.get(reverse("practice-history")).data["count"] == 0
    assert client.get(reverse("practice-stats")).data["total_sessions"] == 0
    client.force_authenticate(user=None)
    assert client.get(reverse("practice-history")).status_code == 401
    assert client.get(summary_url).status_code == 401


@pytest.mark.django_db
def test_withdrawn_public_exam_preserves_only_existing_student_sessions(exam_users):
    exam, question_id, owner, student = exam_users
    Exam.objects.filter(pk=exam.pk).update(visibility=Visibility.PUBLIC)
    client = APIClient()
    client.force_authenticate(user=student)
    created = client.post(
        reverse("practice-sessions"), {"exam_id": str(exam.id), "mode": "TIMED"}, format="json"
    )
    assert created.status_code == 201
    session_id = created.data["id"]

    make_private(exam.id, owner=owner)
    assert client.get(reverse("exam-detail", kwargs={"exam_id": exam.id})).status_code == 404
    assert (
        client.post(
            reverse("practice-sessions"), {"exam_id": str(exam.id), "mode": "TIMED"}, format="json"
        ).status_code
        == 404
    )
    resumed = client.get(reverse("practice-session", kwargs={"session_id": session_id}))
    assert resumed.status_code == 200
    assert "correct_answer" not in str(resumed.data)
    assert client.get(reverse("practice-history")).data["count"] == 1
    assert client.get(reverse("practice-stats")).data["total_sessions"] == 1
    assert (
        client.get(reverse("practice-exam-summary", kwargs={"exam_id": exam.id})).status_code == 404
    )

    answer_url = reverse(
        "practice-answer", kwargs={"session_id": session_id, "question_id": question_id}
    )
    assert client.put(answer_url, {"value": {"choice": "B"}}, format="json").status_code == 200
    submitted = client.post(reverse("practice-submit", kwargs={"session_id": session_id}))
    assert submitted.status_code == 200
    assert submitted.data["total_score"] == "10.00"
    assert (
        client.get(reverse("practice-result", kwargs={"session_id": session_id})).status_code == 200
    )
    assert client.get(reverse("practice-stats")).data["completed_sessions"] == 1

    client.force_authenticate(user=owner)
    assert (
        client.get(reverse("practice-session", kwargs={"session_id": session_id})).status_code
        == 404
    )
    client.force_authenticate(user=get_user_model().objects.create_user("stranger"))
    assert (
        client.get(reverse("practice-session", kwargs={"session_id": session_id})).status_code
        == 404
    )
    assert client.get(reverse("practice-history")).data["count"] == 0


@pytest.mark.django_db
def test_admin_hidden_exam_revokes_practice_access(exam_users):
    exam, _, owner, student = exam_users
    Exam.objects.filter(pk=exam.pk).update(visibility=Visibility.PUBLIC)
    client = APIClient()
    client.force_authenticate(user=student)
    created = client.post(
        reverse("practice-sessions"), {"exam_id": str(exam.id), "mode": "TIMED"}, format="json"
    )
    session_id = created.data["id"]
    admin = get_user_model().objects.create_superuser(
        username="admin", email="admin@example.com", password="HardToGuess#2026"
    )
    hide_exam(exam.id, admin=admin)
    assert (
        client.get(reverse("practice-session", kwargs={"session_id": session_id})).status_code
        == 404
    )
    assert client.get(reverse("practice-history")).data["count"] == 0
    assert client.get(reverse("practice-stats")).data["total_sessions"] == 0
    client.force_authenticate(user=admin)
    assert (
        client.post(
            reverse("practice-sessions"), {"exam_id": str(exam.id), "mode": "TIMED"}, format="json"
        ).status_code
        == 404
    )
    client.force_authenticate(user=owner)
    assert (
        client.get(reverse("practice-session", kwargs={"session_id": session_id})).status_code
        == 404
    )


@pytest.mark.django_db
def test_deleted_exam_revokes_existing_practice_access(exam_users):
    exam, _, owner, student = exam_users
    Exam.objects.filter(pk=exam.pk).update(visibility=Visibility.PUBLIC)
    client = APIClient()
    client.force_authenticate(user=student)
    created = client.post(
        reverse("practice-sessions"), {"exam_id": str(exam.id), "mode": "TIMED"}, format="json"
    )
    session_id = created.data["id"]
    soft_delete_exam(exam.id, owner=owner)
    assert (
        client.get(reverse("practice-session", kwargs={"session_id": session_id})).status_code
        == 404
    )
    assert client.get(reverse("practice-history")).data["count"] == 0
    assert client.get(reverse("practice-stats")).data["total_sessions"] == 0


@pytest.mark.django_db
def test_synthetic_three_section_thpt_seed_and_complete_session(exam_users):
    _, _, owner, _ = exam_users
    output = StringIO()
    call_command("seed_thpt_demo", owner=owner.username, stdout=output)
    first_id = output.getvalue().strip()
    output = StringIO()
    call_command("seed_thpt_demo", owner=owner.username, stdout=output)
    assert output.getvalue().strip() == first_id
    exam = Exam.objects.get(pk=first_id)
    assert exam.title == TITLE
    assert exam.sections.count() == 3
    assert exam.question_count == 3
    assert exam.has_answer_key

    client = APIClient()
    client.force_authenticate(user=owner)
    created = client.post(
        reverse("practice-sessions"), {"exam_id": first_id, "mode": "TIMED"}, format="json"
    )
    assert created.status_code == 201
    assert len(created.data["sections"]) == 3
    answers = [
        {"choice": "B"},
        {"a": True, "b": False, "c": True, "d": False},
        {"text": "5"},
    ]
    for section, value in zip(created.data["sections"], answers, strict=True):
        question_id = section["questions"][0]["id"]
        response = client.put(
            reverse(
                "practice-answer",
                kwargs={"session_id": created.data["id"], "question_id": question_id},
            ),
            {"value": value},
            format="json",
        )
        assert response.status_code == 200
        assert "feedback" not in response.data
    result = client.post(reverse("practice-submit", kwargs={"session_id": created.data["id"]}))
    assert result.status_code == 200
    assert result.data["total_score"] == "10.00"
    assert result.data["max_score"] == "10.00"
    assert [item["status"] for item in result.data["questions"]] == ["CORRECT"] * 3
