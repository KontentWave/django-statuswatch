import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenants", "0003_add_dev_domains"),
    ]

    operations = [
        migrations.CreateModel(
            name="Endpoint",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.CharField(blank=True, max_length=120)),
                ("url", models.URLField(max_length=500)),
                ("interval_minutes", models.PositiveIntegerField(default=5)),
                ("last_status", models.CharField(default="pending", max_length=32)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("last_latency_ms", models.FloatField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="endpoints",
                        to="tenants.client",
                    ),
                ),
            ],
            options={
                "ordering": ("url",),
                "unique_together": {("tenant", "url")},
            },
        ),
    ]
