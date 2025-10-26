from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0003_add_dev_domains"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="subscription_status",
            field=models.CharField(
                choices=[
                    ("free", "Free"),
                    ("pro", "Pro"),
                    ("canceled", "Canceled"),
                ],
                default="free",
                max_length=20,
            ),
        ),
    ]
