from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "complaints",
            "0030_worker_subscription_trust_fields",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="workersubscription",
            name="plan_code",
            field=models.CharField(
                choices=[
                    ("monthly", "Worker Pro Monthly"),
                    ("four_month", "Worker Pro 4 Months"),
                    ("yearly", "Worker Pro Yearly"),
                ],
                default="monthly",
                max_length=20,
            ),
        ),
    ]
