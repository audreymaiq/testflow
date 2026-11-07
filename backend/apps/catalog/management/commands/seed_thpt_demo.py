"""Create a self-authored, three-section THPT exam for local acceptance."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from testflow_contracts.exam import ExamDraft

from apps.catalog.models import Exam, Subject
from apps.catalog.services import create_exam

TITLE = "TestFlow: đề mẫu Toán THPT ba phần"


def demo_draft() -> ExamDraft:
    return ExamDraft.model_validate(
        {
            "schema_version": 1,
            "metadata": {
                "title": TITLE,
                "subtitle": "Nội dung tự biên soạn để kiểm tra hệ thống",
                "level": "THPT",
                "grade": 12,
                "subject": "toan",
                "exam_type": "ON_TAP",
                "duration_minutes": 15,
                "scoring_preset": "THPT_2025",
                "max_score": "10.00",
                "source": "TestFlow synthetic demo",
            },
            "chapters": [
                {"code": "C1", "name": "Số học", "order": 1},
                {"code": "C2", "name": "Lập luận", "order": 2},
            ],
            "sections": [
                {
                    "order": 1,
                    "title": "Phần I: Trắc nghiệm",
                    "kind": "MCQ",
                    "scoring": {"type": "per_question", "points": "4.00"},
                    "questions": [
                        {
                            "tmp_id": "s1q1",
                            "order": 1,
                            "number_label": "Câu 1",
                            "kind": "MCQ",
                            "chapter": "C1",
                            "text": "Hai cộng hai bằng bao nhiêu?",
                            "explanation": "2 + 2 = 4.",
                            "choices": [
                                {"label": "A", "text": "3", "is_correct": False},
                                {"label": "B", "text": "4", "is_correct": True},
                                {"label": "C", "text": "5", "is_correct": False},
                                {"label": "D", "text": "6", "is_correct": False},
                            ],
                            "provenance": {"kind": "manual"},
                        }
                    ],
                },
                {
                    "order": 2,
                    "title": "Phần II: Đúng sai",
                    "kind": "TF_GROUP",
                    "scoring": {
                        "type": "tf_ladder",
                        "ladder": {
                            "0": "0",
                            "1": "0.50",
                            "2": "1.00",
                            "3": "2.00",
                            "4": "4.00",
                        },
                    },
                    "questions": [
                        {
                            "tmp_id": "s2q1",
                            "order": 1,
                            "number_label": "Câu 2",
                            "kind": "TF_GROUP",
                            "chapter": "C2",
                            "text": "Xác định đúng hoặc sai cho từng mệnh đề.",
                            "statements": [
                                {"label": "a", "text": "2 là số chẵn.", "is_true": True},
                                {"label": "b", "text": "3 là số chẵn.", "is_true": False},
                                {"label": "c", "text": "5 là số nguyên tố.", "is_true": True},
                                {"label": "d", "text": "9 là số nguyên tố.", "is_true": False},
                            ],
                            "provenance": {"kind": "manual"},
                        }
                    ],
                },
                {
                    "order": 3,
                    "title": "Phần III: Trả lời ngắn",
                    "kind": "SHORT",
                    "scoring": {"type": "per_question", "points": "2.00"},
                    "questions": [
                        {
                            "tmp_id": "s3q1",
                            "order": 1,
                            "number_label": "Câu 3",
                            "kind": "SHORT",
                            "chapter": "C1",
                            "text": "Mười chia hai bằng bao nhiêu?",
                            "short_answer": "5",
                            "explanation": "10 / 2 = 5.",
                            "provenance": {"kind": "manual"},
                        }
                    ],
                },
            ],
        }
    )


class Command(BaseCommand):
    help = "Create an idempotent synthetic three-section THPT demo for an existing owner."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="Existing username")

    @transaction.atomic
    def handle(self, *args, **options):
        owner = (
            get_user_model().objects.select_for_update().filter(username=options["owner"]).first()
        )
        if owner is None:
            raise CommandError("Owner does not exist; create an account first.")
        Subject.objects.update_or_create(
            code="toan", defaults={"name": "Toán", "levels": ["THCS", "THPT"]}
        )
        exam = Exam.objects.filter(
            owner=owner, title=TITLE, source="TestFlow synthetic demo"
        ).first()
        if exam is None:
            exam = create_exam(demo_draft(), owner=owner, allow_schoolless_demo=True)
        self.stdout.write(str(exam.id))
