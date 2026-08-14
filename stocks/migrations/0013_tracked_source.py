# Phase 2: tracked (external fill) source

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stocks", "0012_tradereview_and_livetrade_desk"),
    ]

    operations = [
        migrations.AlterField(
            model_name="livetrade",
            name="source",
            field=models.CharField(
                choices=[
                    ("signal", "50MA signal"),
                    ("manual", "Manual order"),
                    ("tracked", "Tracked (external fill)"),
                ],
                default="signal",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="tradereview",
            name="source",
            field=models.CharField(
                choices=[
                    ("signal", "50MA status 8"),
                    ("manual", "Manual order"),
                    ("tracked", "Tracked (external fill)"),
                ],
                default="signal",
                max_length=16,
            ),
        ),
    ]
