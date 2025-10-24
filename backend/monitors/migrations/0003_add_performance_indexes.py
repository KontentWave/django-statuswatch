# Generated manually for Phase 1 performance optimization

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitors", "0002_endpoint_last_enqueued_at"),
    ]

    operations = [
        # Index for tenant-scoped queries (listing endpoints per tenant)
        # Used by: EndpointViewSet.get_queryset()
        migrations.AddIndex(
            model_name="endpoint",
            index=models.Index(
                fields=["tenant", "created_at"],
                name="monitors_endpoint_tenant_created_idx",
            ),
        ),
        # Index for scheduler query (finding due endpoints)
        # Used by: schedule_endpoint_checks task
        # Note: Using last_checked_at only since is_active field doesn't exist yet
        migrations.AddIndex(
            model_name="endpoint",
            index=models.Index(
                fields=["last_checked_at"],
                name="monitors_endpoint_schedule_idx",
            ),
        ),
        # Index for URL lookups within tenant scope
        # Used by: duplicate URL validation
        migrations.AddIndex(
            model_name="endpoint",
            index=models.Index(
                fields=["tenant", "url"],
                name="monitors_endpoint_tenant_url_idx",
            ),
        ),
    ]
