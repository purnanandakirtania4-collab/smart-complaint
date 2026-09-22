from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "complaints",
            "0028_user_premium_membership",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="aiusagelog",
            name="feature",
            field=models.CharField(
                choices=[
                    (
                        "complaint_analysis",
                        "Complaint Analysis",
                    ),
                    (
                        "translation",
                        "Translation",
                    ),
                    (
                        "category_suggestion",
                        "Category Suggestion",
                    ),
                    (
                        "detailed_analysis",
                        "Detailed Complaint Analysis",
                    ),
                    (
                        "worker_summary",
                        "Worker Complaint Summary",
                    ),
                    (
                        "worker_checklist",
                        "Worker Work Checklist",
                    ),
                    (
                        "worker_reply",
                        "Worker Reply Generator",
                    ),
                    (
                        "photo_analysis",
                        "Photo Analysis",
                    ),
                    (
                        "help_chat",
                        "AI Help Chat",
                    ),
                ],
                max_length=40,
            ),
        ),
    ]
