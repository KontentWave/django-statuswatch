from django.db import migrations


DEV_HOSTS = [
    "localhost",
    "127.0.0.1",
    "statuswatch.local",
    "acme.statuswatch.local",
]


def ensure_dev_domains(apps, schema_editor):
    Client = apps.get_model("tenants", "Client")
    Domain = apps.get_model("tenants", "Domain")

    try:
        tenant = Client.objects.get(schema_name="public")
    except Client.DoesNotExist:
        tenant = Client(schema_name="public", name="Public Tenant")
        # Avoid schema creation attempts for the public schema on existing DBs
        tenant.auto_create_schema = False
        tenant.save()

    if not tenant.name:
        tenant.name = "Public Tenant"
        tenant.save(update_fields=["name"])

    for idx, host in enumerate(DEV_HOSTS):
        Domain.objects.update_or_create(
            domain=host,
            defaults={
                "tenant": tenant,
                "is_primary": idx == 0,
            },
        )


def remove_dev_domains(apps, schema_editor):
    Domain = apps.get_model("tenants", "Domain")
    Domain.objects.filter(domain__in=DEV_HOSTS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0002_add_localhost_domain"),
    ]

    operations = [
        migrations.RunPython(ensure_dev_domains, remove_dev_domains),
    ]
