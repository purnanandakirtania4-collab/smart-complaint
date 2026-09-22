from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "complaints",
            "0029_worker_ai_checklist_feature",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="workersubscription",
            name="cancel_at_period_end",
            field=models.BooleanField(
                default=False,
            ),
        ),
        migrations.AddField(
            model_name="workersubscription",
            name="last_gateway_status",
            field=models.CharField(
                blank=True,
                default="",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="workersubscription",
            name="last_synced_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
            ),
        ),
    ]
