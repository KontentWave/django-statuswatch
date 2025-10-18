from django.db import migrations


def ensure_public_domain(apps, schema_editor):
    Client = apps.get_model("tenants", "Client")
    Domain = apps.get_model("tenants", "Domain")

    try:
        tenant = Client.objects.get(schema_name="public")
    except Client.DoesNotExist:
        tenant = Client(schema_name="public", name="Public Tenant")
        # Avoid schema creation attempts for the public schema on existing DBs
        tenant.auto_create_schema = False
        tenant.save()

    # Ensure the name is set for readability
    if not tenant.name:
        tenant.name = "Public Tenant"
        tenant.save(update_fields=["name"])

    for idx, host in enumerate(["localhost", "127.0.0.1"]):
        Domain.objects.update_or_create(
            domain=host,
            defaults={
                "tenant": tenant,
                "is_primary": idx == 0,
            },
        )


def remove_public_domain(apps, schema_editor):
    Domain = apps.get_model("tenants", "Domain")
    Domain.objects.filter(domain__in=["localhost", "127.0.0.1"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(ensure_public_domain, remove_public_domain),
    ]
