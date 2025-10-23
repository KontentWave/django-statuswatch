from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitors", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="endpoint",
            name="last_enqueued_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
