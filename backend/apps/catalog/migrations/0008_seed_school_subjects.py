"""Add the subjects and educational activities in the 2018 general curriculum.

Source: Ministry of Education and Training, consolidated general curriculum,
section IV (primary, lower secondary and upper secondary study plans).
"""

from typing import ClassVar

from django.db import migrations

SUBJECTS = (
    ("tieng-viet", "Tiếng Việt", ["TIEU_HOC"], False),
    ("dao-duc", "Đạo đức", ["TIEU_HOC"], False),
    ("tu-nhien-va-xa-hoi", "Tự nhiên và Xã hội", ["TIEU_HOC"], False),
    ("khoa-hoc", "Khoa học", ["TIEU_HOC"], False),
    ("lich-su-va-dia-li", "Lịch sử và Địa lí", ["TIEU_HOC", "THCS"], False),
    ("tin-hoc-va-cong-nghe", "Tin học và Công nghệ", ["TIEU_HOC"], False),
    ("giao-duc-the-chat", "Giáo dục thể chất", ["TIEU_HOC", "THCS", "THPT"], False),
    ("am-nhac", "Âm nhạc", ["TIEU_HOC", "THCS", "THPT"], False),
    ("mi-thuat", "Mĩ thuật", ["TIEU_HOC", "THCS", "THPT"], False),
    ("hoat-dong-trai-nghiem", "Hoạt động trải nghiệm", ["TIEU_HOC"], False),
    (
        "hoat-dong-trai-nghiem-huong-nghiep",
        "Hoạt động trải nghiệm, hướng nghiệp",
        ["THCS", "THPT"],
        False,
    ),
    ("giao-duc-dia-phuong", "Nội dung giáo dục của địa phương", ["THCS", "THPT"], False),
    ("tieng-dan-toc-thieu-so", "Tiếng dân tộc thiểu số", ["TIEU_HOC", "THCS"], False),
    ("ngoai-ngu-1", "Ngoại ngữ 1", ["TIEU_HOC", "THCS", "THPT"], False),
    ("ngoai-ngu-2", "Ngoại ngữ 2", ["THCS", "THPT"], False),
    ("giao-duc-cong-dan", "Giáo dục công dân", ["THCS"], False),
    ("khoa-hoc-tu-nhien", "Khoa học tự nhiên", ["THCS"], True),
    ("cong-nghe", "Công nghệ", ["THCS", "THPT"], True),
    ("lich-su", "Lịch sử", ["THPT"], False),
    ("dia-li", "Địa lí", ["THPT"], False),
    ("giao-duc-kinh-te-va-phap-luat", "Giáo dục kinh tế và pháp luật", ["THPT"], False),
    ("sinh-hoc", "Sinh học", ["THPT"], True),
    ("giao-duc-quoc-phong-va-an-ninh", "Giáo dục quốc phòng và an ninh", ["THPT"], False),
    ("tieng-nga", "Tiếng Nga", ["TIEU_HOC", "THCS", "THPT"], False),
    ("tieng-phap", "Tiếng Pháp", ["TIEU_HOC", "THCS", "THPT"], False),
    ("tieng-duc", "Tiếng Đức", ["TIEU_HOC", "THCS", "THPT"], False),
    ("tieng-trung-quoc", "Tiếng Trung Quốc", ["TIEU_HOC", "THCS", "THPT"], False),
    ("tieng-nhat", "Tiếng Nhật", ["TIEU_HOC", "THCS", "THPT"], False),
    ("tieng-han", "Tiếng Hàn", ["TIEU_HOC", "THCS", "THPT"], False),
)


def seed_school_subjects(apps, schema_editor):
    Subject = apps.get_model("catalog", "Subject")
    for code, name, levels, has_formula in SUBJECTS:
        if Subject.objects.using(schema_editor.connection.alias).filter(name=name).exists():
            continue
        Subject.objects.using(schema_editor.connection.alias).get_or_create(
            code=code,
            defaults={"name": name, "levels": levels, "has_formula": has_formula},
        )


class Migration(migrations.Migration):
    dependencies: ClassVar[list[tuple[str, str]]] = [("catalog", "0007_self_service_taxonomy")]
    operations: ClassVar[list[migrations.RunPython]] = [
        migrations.RunPython(seed_school_subjects, migrations.RunPython.noop)
    ]
