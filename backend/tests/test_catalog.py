"""S1 package 1: finalized exam writes and privacy across all catalog reads."""

import copy

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from pydantic import ValidationError as ContractValidationError
from rest_framework.test import APIClient
from testflow_contracts.exam import ExamDraft

from apps.catalog.models import Exam, School, Subject, Visibility
from apps.catalog.selectors import list_exams
from apps.catalog.services import create_exam, export_exam
from apps.common.errors import ValidationFailed


def draft_data():
    return {
        "schema_version": 1,
        "metadata": {
            "title": "Đề kiểm tra Toán 12",
            "subtitle": "Luyện tập",
            "level": "THPT",
            "grade": 12,
            "subject": "toan",
            "exam_type": "KIEM_TRA",
            "scoring_preset": "UNIFORM_10",
            "max_score": "10.00",
            "source": "Tự biên soạn",
            "year": 2026,
        },
        "chapters": [{"code": "C1", "name": "Đại số", "order": 1}],
        "sections": [
            {
                "order": 1,
                "title": "Phần I",
                "kind": "MCQ",
                "scoring": {"type": "per_question", "points": "10.00"},
                "passages": [],
                "questions": [
                    {
                        "tmp_id": "q1",
                        "order": 1,
                        "number_label": "Câu 1",
                        "kind": "MCQ",
                        "chapter": "C1",
                        "text": "2 + 2 bằng bao nhiêu?",
                        "choices": [
                            {"label": "A", "text": "3", "is_correct": False},
                            {"label": "B", "text": "4", "is_correct": True},
                        ],
                        "provenance": {"kind": "manual"},
                    }
                ],
            }
        ],
    }


@pytest.fixture
def users(db):
    Subject.objects.update_or_create(code="toan", defaults={"name": "Toán", "levels": ["THPT"]})
    School.objects.get_or_create(name="Trường Mẫu")
    owner = get_user_model().objects.create_user(
        username="owner", email="owner@example.com", password="HardToGuess#2026"
    )
    other = get_user_model().objects.create_user(
        username="other", email="other@example.com", password="HardToGuess#2026"
    )
    return owner, other


@pytest.mark.django_db
def test_atomic_private_creation_and_round_trip(users):
    owner, _ = users
    draft = ExamDraft.model_validate(draft_data())
    exam = create_exam(draft, owner=owner)
    assert exam.visibility == Visibility.PRIVATE
    assert exam.question_count == 1
    assert exam.has_answer_key
    assert exam.sections.count() == 1
    assert exam.sections.first().questions.first().choices.count() == 2
    exported = export_exam(exam)
    assert exported.model_dump() == draft.model_dump()
    clone = create_exam(exported, owner=owner)
    assert export_exam(clone).model_dump() == exported.model_dump()


@pytest.mark.django_db
def test_invalid_draft_never_creates_partial_exam(users):
    owner, _ = users
    invalid = draft_data()
    invalid["metadata"]["subject"] = "missing"
    with pytest.raises(ValidationFailed):
        create_exam(ExamDraft.model_validate(invalid), owner=owner)
    assert Exam.objects.count() == 0
    invalid = draft_data()
    invalid["sections"][0]["questions"][0]["text"] = "<script>alert(1)</script>"
    with pytest.raises(ContractValidationError):
        ExamDraft.model_validate(invalid)
    assert Exam.objects.count() == 0


@pytest.mark.django_db
def test_private_exam_is_absent_from_other_user_and_visitor_reads(users):
    owner, other = users
    exam = create_exam(ExamDraft.model_validate(draft_data()), owner=owner)
    assert "toan" in exam.search_text
    assert list_exams(owner, {"q": "toan"}).count() == 1
    assert list_exams(owner, {"q": "DE KIEM TRA TOAN"}).count() == 1
    client = APIClient()
    for actor in (None, other):
        client.force_authenticate(user=actor)
        assert client.get(reverse("exam-detail", kwargs={"exam_id": exam.id})).status_code == 404
        assert client.get(reverse("exam-preview", kwargs={"exam_id": exam.id})).status_code == 404
        assert client.get(reverse("exam-list")).data["count"] == 0
        assert client.get(reverse("exam-list"), {"q": "toan"}).data["count"] == 0
        assert client.get(reverse("facets")).data["levels"] == []
    client.force_authenticate(user=owner)
    assert client.get(reverse("exam-detail", kwargs={"exam_id": exam.id})).status_code == 200
    with CaptureQueriesContext(connection) as detail_queries:
        detail = client.get(reverse("exam-detail", kwargs={"exam_id": exam.id})).data
    assert len(detail_queries) <= 12
    assert detail["section_stats"][0]["count"] == 1
    assert detail["chapter_stats"][0]["count"] == 1
    assert client.get(reverse("exam-list"), {"q": "toan"}).data["count"] == 1
    preview = client.get(reverse("exam-preview", kwargs={"exam_id": exam.id}))
    assert preview.status_code == 200
    assert "is_correct" not in str(preview.data)


@pytest.mark.django_db
def test_manual_endpoint_requires_authentication_and_validates_input(users):
    owner, _ = users
    client = APIClient()
    assert (
        client.post(reverse("exam-manual"), {"draft": draft_data()}, format="json").status_code
        == 401
    )
    client.force_authenticate(user=owner)
    bad = copy.deepcopy(draft_data())
    bad["sections"][0]["questions"][0]["choices"] = []
    assert client.post(reverse("exam-manual"), {"draft": bad}, format="json").status_code == 400
    assert Exam.objects.count() == 0
    created = client.post(reverse("exam-manual"), {"draft": draft_data()}, format="json")
    assert created.status_code == 201
    assert created.data["visibility"] == "PRIVATE"
    assert Exam.objects.count() == 1


@pytest.mark.django_db
def test_catalog_list_query_count_does_not_grow_per_exam(users):
    owner, _ = users
    client = APIClient()
    client.force_authenticate(user=owner)
    create_exam(ExamDraft.model_validate(draft_data()), owner=owner)
    with CaptureQueriesContext(connection) as first:
        assert client.get(reverse("exam-list")).data["count"] == 1
    for index in range(3):
        data = draft_data()
        data["metadata"]["title"] = f"Đề số {index}"
        create_exam(ExamDraft.model_validate(data), owner=owner)
    with CaptureQueriesContext(connection) as many:
        assert client.get(reverse("exam-list")).data["count"] == 4
    assert len(many) <= len(first) + 2


@pytest.mark.django_db
def test_taxonomy_exact_variants_and_unknown_name_guard(users):
    owner, _ = users
    data = draft_data()
    data["metadata"].update(subject=" TOÁN  ", schools=["  trƯờng   mẫU "])
    exam = create_exam(ExamDraft.model_validate(data), owner=owner)
    assert exam.subject.name == "Toán"
    assert list(exam.schools.values_list("name", flat=True)) == ["Trường Mẫu"]
    assert School.objects.count() == 1
    data["metadata"]["schools"] = ["Trường Máu"]
    with pytest.raises(ValidationFailed) as error:
        create_exam(ExamDraft.model_validate(data), owner=owner)
    assert error.value.code == "SCHOOL_UNREVIEWED"
    assert Exam.objects.count() == 1


@pytest.mark.django_db
def test_taxonomy_proposal_review_alias_and_permissions(users):
    from django.contrib.auth.models import Group

    from apps.catalog.models import TaxonomyAlias, TaxonomyProposal

    owner, other = users
    admin = get_user_model().objects.create_user(
        username="taxonomy_admin", password="HardToGuess#2026", is_staff=True
    )
    admin.groups.add(Group.objects.get_or_create(name="Admin")[0])
    client = APIClient()
    client.force_authenticate(user=owner)
    lookup = client.get(reverse("taxonomy-lookup"), {"kind": "SUBJECT", "name": "toánn"})
    assert lookup.status_code == 200
    assert lookup.data["match"] is None
    assert lookup.data["suggestions"][0]["name"] == "Toán"
    first = client.post(reverse("taxonomy-propose"), {"kind": "SUBJECT", "name": "Toán học"})
    assert first.status_code == 201
    client.force_authenticate(user=other)
    second = client.post(reverse("taxonomy-propose"), {"kind": "SUBJECT", "name": "toán  HỌC"})
    assert second.status_code == 201
    assert first.data["id"] == second.data["id"]
    assert client.get(reverse("taxonomy-queue")).status_code == 403
    assert (
        client.post(
            reverse("taxonomy-decide", kwargs={"proposal_id": first.data["id"]}),
            {"action": "MAP", "target_id": 1},
        ).status_code
        == 403
    )
    client.force_authenticate(user=admin)
    assert client.get(reverse("taxonomy-queue")).data["count"] == 1
    decision = client.post(
        reverse("taxonomy-decide", kwargs={"proposal_id": first.data["id"]}),
        {"action": "CREATE", "canonical_name": "Toán học", "levels": ["THPT"]},
        format="json",
    )
    assert decision.status_code == 200, decision.data
    assert decision.data["status"] == "APPROVED"
    assert TaxonomyProposal.objects.get(pk=first.data["id"]).reviewed_by == admin
    assert TaxonomyAlias.objects.filter(kind="SUBJECT").count() == 1
    client.force_authenticate(user=owner)
    exact = client.get(reverse("taxonomy-lookup"), {"kind": "SUBJECT", "name": "toán HỌC"})
    assert exact.data["match"]["name"] == "Toán học"
    data = draft_data()
    data["metadata"]["subject"] = "TOÁN HỌC"
    assert create_exam(ExamDraft.model_validate(data), owner=owner).subject.name == "Toán học"


@pytest.mark.django_db
def test_taxonomy_school_typo_requires_mapping_and_major_creation(users):
    from django.contrib.auth.models import Group

    from apps.catalog.models import Major

    owner, _ = users
    admin = get_user_model().objects.create_user(
        username="taxonomy_admin2", password="HardToGuess#2026", is_staff=True
    )
    admin.groups.add(Group.objects.get_or_create(name="Admin")[0])
    client = APIClient()
    client.force_authenticate(user=owner)
    school = client.post(reverse("taxonomy-propose"), {"kind": "SCHOOL", "name": "Trường Mẫuu"})
    assert school.status_code == 201
    major = client.post(reverse("taxonomy-propose"), {"kind": "MAJOR", "name": "Khoa học dữ liệu"})
    assert major.status_code == 201
    client.force_authenticate(user=admin)
    mapped = client.post(
        reverse("taxonomy-decide", kwargs={"proposal_id": school.data["id"]}),
        {"action": "MAP", "target_id": School.objects.get(name="Trường Mẫu").pk},
    )
    assert mapped.status_code == 200
    created = client.post(
        reverse("taxonomy-decide", kwargs={"proposal_id": major.data["id"]}),
        {"action": "CREATE", "canonical_name": "Khoa học dữ liệu"},
    )
    assert created.status_code == 200
    assert Major.objects.count() == 1
    assert (
        client.post(
            reverse("taxonomy-decide", kwargs={"proposal_id": major.data["id"]}),
            {"action": "CREATE"},
        ).status_code
        == 409
    )
    data = draft_data()
    data["metadata"].update(schools=["trường mẫUU"], majors=["KHOA HỌC DỮ LIỆU"])
    exam = create_exam(ExamDraft.model_validate(data), owner=owner)
    assert list(exam.schools.values_list("name", flat=True)) == ["Trường Mẫu"]
    assert list(exam.majors.values_list("name", flat=True)) == ["Khoa học dữ liệu"]
