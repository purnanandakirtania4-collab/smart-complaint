from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("complaints", "0021_userprofile_address_supportrequest"),
    ]

    operations = [
        migrations.AddField(
            model_name="workerprofile",
            name="availability_status",
            field=models.CharField(
                choices=[
                    ("available", "Available"),
                    ("busy", "Busy"),
                    ("offline", "Offline"),
                ],
                default="available",
                max_length=20,
            ),
        ),
    ]
