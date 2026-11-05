"""The licensed legacy deck is portable, exact, public only after review, and idempotent."""

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from apps.catalog.models import Choice, Exam, PublishRequest, Visibility
from apps.imports.management.commands.seed_quiz_rush import seed_draft


def test_quiz_rush_fixture_has_expected_structure():
    draft = seed_draft()
    assert draft.metadata.level == "DAI_HOC"
    assert draft.metadata.scoring_preset == "PRACTICE_NO_SCORE"
    assert len(draft.chapters) == 4
    assert [len([q for q in draft.sections[0].questions if q.chapter == code]) for code in
            ("C12", "C3", "C4", "C5")] == [80, 90, 70, 60]
    assert all(sum(choice.is_correct for choice in question.choices) == 1
               for question in draft.sections[0].questions)


@pytest.mark.django_db
def test_quiz_rush_seed_requires_distinct_reviewer_and_is_idempotent():
    users = get_user_model().objects
    owner = users.create_superuser(
        "seed_owner", email="seed_owner@example.test", password="HardToGuess#2026"
    )
    reviewer = users.create_superuser(
        "seed_reviewer", email="seed_reviewer@example.test", password="HardToGuess#2026"
    )
    with pytest.raises(CommandError):
        call_command("seed_quiz_rush", owner=owner.username, reviewer=owner.username)
    assert Exam.objects.count() == 0

    output = StringIO()
    call_command("seed_quiz_rush", owner=owner.username, stdout=output)
    exam = Exam.objects.get(pk=output.getvalue().strip())
    assert exam.visibility == Visibility.PRIVATE
    assert PublishRequest.objects.count() == 0
    assert exam.is_system_sample
    assert exam.question_count == 300
    assert exam.chapters.count() == 4
    assert exam.sections.count() == 1
    assert Choice.objects.filter(question__section__exam=exam).count() == 1200
    assert exam.subject.code == "thi-giac-may-tinh"
    assert exam.max_score is None
    visitor = APIClient()
    private_list = visitor.get("/api/v1/exams/?q=Thị Giác Máy Tính")
    assert private_list.status_code == 200
    assert not private_list.data["results"]

    call_command("seed_quiz_rush", owner=owner.username, reviewer=reviewer.username)
    exam.refresh_from_db()
    assert exam.visibility == Visibility.PUBLIC
    approval = PublishRequest.objects.get(exam=exam)
    assert approval.requested_by == owner and approval.reviewed_by == reviewer
    assert approval.status == "APPROVED"
    found = visitor.get("/api/v1/exams/?q=Thị Giác Máy Tính")
    assert found.status_code == 200
    assert any(
        item["id"] == str(exam.id) and item["is_system_sample"]
        for item in found.data["results"]
    )

    call_command("seed_quiz_rush", owner=owner.username, reviewer=reviewer.username)
    assert Exam.objects.count() == 1
    assert PublishRequest.objects.count() == 1
