import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_userprofile_userprof_verified_idx_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="email_verification_token",
            field=models.UUIDField(
                blank=True,
                default=uuid.uuid4,
                editable=False,
                help_text="Token sent to user's email for verification",
                null=True,
            ),
        ),
    ]
