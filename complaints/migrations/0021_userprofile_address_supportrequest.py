from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("complaints", "0020_workerpayoutdetails"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="address",
            field=models.TextField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="city",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="state",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="pincode",
            field=models.CharField(blank=True, default="", max_length=6),
        ),
        migrations.CreateModel(
            name="SupportRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("issue_type", models.CharField(choices=[("Complaint Issue", "Complaint Issue"), ("Worker Issue", "Worker Issue"), ("Payment Issue", "Payment Issue"), ("Account Issue", "Account Issue"), ("Technical Problem", "Technical Problem"), ("Other", "Other")], max_length=50)),
                ("subject", models.CharField(max_length=150)),
                ("message", models.TextField(max_length=2000)),
                ("is_resolved", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="support_requests", to="auth.user")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
