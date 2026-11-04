"""Seed generic subjects without adding copyrighted exam content."""

from django.db import migrations


def seed_subjects(apps, schema_editor):
    Subject = apps.get_model("catalog", "Subject")
    common = ["TIEU_HOC", "THCS", "THPT", "DAI_HOC"]
    data = (
        ("toan", "Toán", common, True),
        ("vat-ly", "Vật lý", ["THCS", "THPT", "DAI_HOC"], True),
        ("hoa-hoc", "Hóa học", ["THCS", "THPT", "DAI_HOC"], True),
        ("ngu-van", "Ngữ văn", common, False),
        ("tieng-anh", "Tiếng Anh", common, False),
        ("tin-hoc", "Tin học", common, True),
        ("khac", "Khác", [], False),
    )
    for code, name, levels, has_formula in data:
        Subject.objects.using(schema_editor.connection.alias).get_or_create(
            code=code,
            defaults={"name": name, "levels": levels, "has_formula": has_formula},
        )


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_passage_source_tmp_id_question_provenance_and_more")]
    operations = [migrations.RunPython(seed_subjects, migrations.RunPython.noop)]
