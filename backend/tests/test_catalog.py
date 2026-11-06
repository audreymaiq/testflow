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

from apps.catalog.models import Exam, Major, School, Subject, Visibility
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
        hidden_facets = client.get(reverse("facets")).data
        assert hidden_facets["levels"] == []
        assert hidden_facets["subject_counts"] == {}
        assert hidden_facets["school_counts"] == {}
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
        first_page = client.get(reverse("exam-list")).data
        assert first_page["count"] == 1
        assert first_page["results"][0]["chapter_count"] == 1
    for index in range(3):
        data = draft_data()
        data["metadata"]["title"] = f"Đề số {index}"
        create_exam(ExamDraft.model_validate(data), owner=owner)
    with CaptureQueriesContext(connection) as many:
        many_page = client.get(reverse("exam-list")).data
        assert many_page["count"] == 4
        assert all(item["chapter_count"] == 1 for item in many_page["results"])
    assert len(many) <= len(first) + 2


@pytest.mark.django_db
def test_school_and_major_filters_use_and_semantics(users):
    owner, other = users
    School.objects.create(name="Trường Khác")
    Major.objects.create(name="Ngành A")
    Major.objects.create(name="Ngành B")
    for title, school, major in (
        ("Đề A", "Trường Mẫu", "Ngành A"),
        ("Đề B", "Trường Khác", "Ngành B"),
    ):
        data = draft_data()
        data["metadata"].update(title=title, schools=[school], majors=[major])
        create_exam(ExamDraft.model_validate(data), owner=owner)
    assert list_exams(owner, {"school": "Trường Mẫu"}).count() == 1
    assert list_exams(owner, {"major": "Ngành B"}).count() == 1
    assert list_exams(owner, {"school": "Trường Mẫu", "major": "Ngành A"}).count() == 1
    assert list_exams(owner, {"school": "Trường Mẫu", "major": "Ngành B"}).count() == 0
    client = APIClient()
    client.force_authenticate(user=owner)
    facets = client.get(reverse("facets")).data
    assert facets["subject_counts"] == {"toan": 2}
    assert facets["school_counts"] == {"Trường Mẫu": 1, "Trường Khác": 1}
    assert facets["major_counts"] == {"Ngành A": 1, "Ngành B": 1}
    assert facets["level_counts"] == {"THPT": 2}
    assert facets["grade_counts"] == {12: 2}
    client.force_authenticate(user=other)
    assert client.get(reverse("facets")).data["subject_counts"] == {}


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
    assert error.value.code == "SCHOOL_UNKNOWN"
    assert Exam.objects.count() == 1


@pytest.mark.django_db
def test_taxonomy_self_service_creation_and_exact_reuse(users):
    from apps.catalog.models import Major, TaxonomyAlias, TaxonomyProposal

    owner, other = users
    client = APIClient()
    assert (
        client.post(reverse("taxonomy-create"), {"kind": "SUBJECT", "name": "Toán học"}).status_code
        == 401
    )
    client.force_authenticate(user=owner)
    lookup = client.get(reverse("taxonomy-lookup"), {"kind": "SUBJECT", "name": "toánn"})
    assert lookup.status_code == 200
    assert lookup.data["match"] is None
    assert lookup.data["suggestions"][0]["name"] == "Toán"
    accented = client.get(reverse("taxonomy-lookup"), {"kind": "SCHOOL", "name": "Trường Máu"})
    assert accented.status_code == 200
    assert accented.data["match"] is None
    assert accented.data["suggestions"][0]["name"] == "Trường Mẫu"
    first = client.post(
        reverse("taxonomy-create"),
        {"kind": "SUBJECT", "name": "Toán học", "has_formula": True},
    )
    assert first.status_code == 201, first.data
    assert first.data["match"]["name"] == "Toán học"
    assert Subject.objects.get(pk=first.data["match"]["id"]).has_formula
    client.force_authenticate(user=other)
    second = client.post(reverse("taxonomy-create"), {"kind": "SUBJECT", "name": "  toán  HỌC "})
    assert second.status_code == 200
    assert second.data["match"]["id"] == first.data["match"]["id"]
    assert Subject.objects.filter(name="Toán học").count() == 1
    assert TaxonomyAlias.objects.filter(kind="SUBJECT").count() == 1
    audit = TaxonomyProposal.objects.get(kind="SUBJECT", reason="SELF_SERVICE")
    assert audit.status == "APPROVED" and audit.reviewed_by is None
    school = client.post(reverse("taxonomy-create"), {"kind": "SCHOOL", "name": "Trường Mẫuu"})
    major = client.post(reverse("taxonomy-create"), {"kind": "MAJOR", "name": "Khoa học dữ liệu"})
    assert school.status_code == 201
    assert major.status_code == 201
    assert School.objects.count() == 2
    assert Major.objects.count() == 1
    data = draft_data()
    data["metadata"].update(
        subject="TOÁN HỌC", schools=["trường mẫUU"], majors=["KHOA HỌC DỮ LIỆU"]
    )
    exam = create_exam(ExamDraft.model_validate(data), owner=owner)
    assert exam.subject.name == "Toán học"
    assert list(exam.schools.values_list("name", flat=True)) == ["Trường Mẫuu"]
    assert list(exam.majors.values_list("name", flat=True)) == ["Khoa học dữ liệu"]


@pytest.mark.django_db
def test_old_pending_taxonomy_is_migrated_without_admin(users):
    from importlib import import_module

    from django.apps import apps

    from apps.catalog.models import TaxonomyProposal

    owner, _ = users
    proposal = TaxonomyProposal.objects.create(
        kind="SCHOOL", name="Trường Chờ Cũ", key="trường chờ cũ", requested_by=owner
    )
    import_module("apps.catalog.migrations.0007_self_service_taxonomy").migrate_pending(
        apps, connection.schema_editor()
    )
    proposal.refresh_from_db()
    assert proposal.status == "APPROVED"
    assert proposal.reason == "SELF_SERVICE_MIGRATED"
    assert School.objects.get(pk=proposal.target_id).name == "Trường Chờ Cũ"


@pytest.mark.django_db
def test_old_ambiguous_pending_taxonomy_requires_reentry(users):
    from importlib import import_module

    from django.apps import apps

    from apps.catalog.models import TaxonomyProposal

    owner, _ = users
    School.objects.create(name="Trường Cũ")
    School.objects.create(name="trường cũ")
    proposal = TaxonomyProposal.objects.create(
        kind="SCHOOL", name="TRƯỜNG CŨ", key="trường cũ", requested_by=owner
    )
    import_module("apps.catalog.migrations.0007_self_service_taxonomy").migrate_pending(
        apps, connection.schema_editor()
    )
    proposal.refresh_from_db()
    assert proposal.status == "REJECTED"
    assert proposal.reason == "SELF_SERVICE_REENTER_REQUIRED"
    assert School.objects.count() == 3


@pytest.mark.django_db
def test_profile_school_uses_same_canonical_catalog(users):
    owner, other = users
    client = APIClient()
    assert (
        client.post(reverse("taxonomy-profile-school"), {"name": "Trường Mẫu"}).status_code == 401
    )
    client.force_authenticate(user=owner)
    unknown = client.post(reverse("taxonomy-profile-school"), {"name": "Trường Máu"})
    assert unknown.status_code == 400
    assert unknown.data["error"]["code"] == "SCHOOL_UNKNOWN"
    assert owner.school == ""
    selected = client.post(reverse("taxonomy-profile-school"), {"name": "  TRƯỜNG   MẪU  "})
    assert selected.status_code == 200
    assert selected.data["school"] == "Trường Mẫu"
    assert client.patch(reverse("me"), {"school": "Trường Máu"}).status_code == 200
    owner.refresh_from_db()
    other.refresh_from_db()
    assert owner.school == "Trường Mẫu"
    assert other.school == ""
    assert client.post(reverse("taxonomy-profile-school"), {"name": ""}).data["school"] == ""
