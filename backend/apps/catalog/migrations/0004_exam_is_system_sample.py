from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0003_seed_subjects")]

    operations = [
        migrations.AddField(
            model_name="exam",
            name="is_system_sample",
            field=models.BooleanField(default=False),
        ),
    ]
