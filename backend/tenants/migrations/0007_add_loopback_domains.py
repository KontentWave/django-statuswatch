from django.db import migrations


LOOPBACK_HOSTS = [
    "127.0.0.1",
    "statuswatch.local",
]


def ensure_loopback_domains(apps, schema_editor):
    Client = apps.get_model("tenants", "Client")
    Domain = apps.get_model("tenants", "Domain")

    try:
        tenant = Client.objects.get(schema_name="public")
    except Client.DoesNotExist:
        tenant = Client(schema_name="public", name="Public Tenant")
        tenant.auto_create_schema = False
        tenant.save()

    if not tenant.name:
        tenant.name = "Public Tenant"
        tenant.save(update_fields=["name"])

    for idx, host in enumerate(LOOPBACK_HOSTS):
        Domain.objects.update_or_create(
            domain=host,
            defaults={
                "tenant": tenant,
                "is_primary": idx == 0,
            },
        )


def remove_loopback_domains(apps, schema_editor):
    Domain = apps.get_model("tenants", "Domain")
    Domain.objects.filter(domain__in=LOOPBACK_HOSTS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0006_alter_client_name"),
    ]

    operations = [
        migrations.RunPython(ensure_loopback_domains, remove_loopback_domains),
    ]
