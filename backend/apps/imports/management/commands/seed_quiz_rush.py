"""Import the owner-authorized Quiz Rush built-in deck without a legacy runtime dependency."""

import hashlib
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from testflow_contracts.exam import ExamDraft

from apps.catalog.models import Exam, Subject, Visibility
from apps.catalog.services import (
    create_exam,
    decide_publication,
    is_admin,
    is_reviewer,
    request_publication,
)
from apps.imports.txt_parser import parse_txt

SOURCE_PREFIX = "Quiz Rush built-in (owner-authorized); SHA-256: "
FIXTURE = Path(__file__).resolve().parents[5] / "data" / "seed" / "quiz-rush-cv.txt"
CHAPTER_DETAILS = {
    "C12": ("Số hóa, lọc, histogram, Canny, hình thái học, toán tử điểm", "#c9a84b"),
    "C3": ("Phát hiện đặc trưng và đối sánh ảnh", "#84c9a8"),
    "C4": ("Phân đoạn ảnh", "#84a8c9"),
    "C5": ("Phát hiện đối tượng", "#c984a8"),
}


def seed_draft() -> ExamDraft:
    raw = FIXTURE.read_bytes()
    outcome = parse_txt(raw.decode("utf-8"))
    questions = [question for section in outcome.draft.sections for question in section.questions]
    if (
        len(questions) != 300
        or len(outcome.draft.chapters) != 4
        or outcome.skipped
        or outcome.issues
    ):
        raise CommandError("Quiz Rush fixture failed the 300-question golden check.")
    data = outcome.draft.model_dump(mode="json")
    data["metadata"].update(
        title="Thị Giác Máy Tính",
        subtitle="Xử lý ảnh & Computer Vision — 300 câu",
        icon="👁️",
        color="#c9a84b",
        level="DAI_HOC",
        grade=None,
        subject="thi-giac-may-tinh",
        exam_type="ON_TAP",
        schools=["ĐH Bách Khoa HN", "ĐH Khoa Học Tự Nhiên TP.HCM", "ĐH Giao Thông Vận Tải TP.HCM"],
        majors=["CNTT & AI", "Kỹ thuật"],
        scoring_preset="PRACTICE_NO_SCORE",
        duration_minutes=None,
        source=f"{SOURCE_PREFIX}{hashlib.sha256(raw).hexdigest()}",
    )
    for chapter in data["chapters"]:
        chapter["description"], chapter["color"] = CHAPTER_DETAILS[chapter["code"]]
    return ExamDraft.model_validate(data)


class Command(BaseCommand):
    help = (
        "Seed the licensed 300-question Quiz Rush deck for an existing Admin; "
        "optionally publish through a distinct Reviewer."
    )

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="Existing Admin username")
        parser.add_argument(
            "--reviewer", help="Distinct existing Reviewer username; approves publication"
        )

    @transaction.atomic
    def handle(self, *args, **options):
        users = get_user_model().objects
        owner = users.select_for_update().filter(username=options["owner"]).first()
        if owner is None or not is_admin(owner):
            raise CommandError("Owner must be an existing Admin.")
        reviewer = None
        if options["reviewer"]:
            reviewer = users.filter(username=options["reviewer"]).first()
            if reviewer is None or reviewer.pk == owner.pk or not is_reviewer(reviewer):
                raise CommandError("Reviewer must be an existing, distinct Reviewer or Admin.")
        draft = seed_draft()
        Subject.objects.update_or_create(
            code="thi-giac-may-tinh",
            defaults={"name": "Thị giác máy tính", "levels": ["DAI_HOC"], "has_formula": True},
        )
        Subject.objects.select_for_update().get(code="thi-giac-may-tinh")
        existing = Exam.objects.filter(
            is_system_sample=True, source__startswith=SOURCE_PREFIX
        ).first()
        if existing:
            if (
                existing.owner_id != owner.pk
                or existing.source != draft.metadata.source
                or existing.deleted_at
                or existing.visibility == Visibility.HIDDEN
            ):
                raise CommandError(
                    "Existing Quiz Rush seed differs or was deleted; inspect it manually."
                )
            exam = existing
        else:
            exam = create_exam(draft, owner=owner, source_kind="TXT")
            exam.is_system_sample = True
            exam.save(update_fields=("is_system_sample", "updated_at"))
        if reviewer and exam.visibility == Visibility.PRIVATE:
            request = request_publication(exam.id, owner=owner)
            decide_publication(request.id, reviewer=reviewer, approve=True)
        self.stdout.write(str(exam.id))
