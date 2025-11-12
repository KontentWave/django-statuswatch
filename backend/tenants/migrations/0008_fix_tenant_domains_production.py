"""
Migration to fix tenant domains from .localhost to production domain.

This migration updates all tenant domains that end with .localhost to use
the production domain suffix (statuswatch.kontentwave.digital).

Note: This only affects non-public schemas. The public schema domains are left untouched.
"""

from django.db import migrations


def fix_tenant_domains(apps, schema_editor):
    """
    Update tenant domains from .localhost to .statuswatch.kontentwave.digital
    """
    Domain = apps.get_model("tenants", "Domain")
    Client = apps.get_model("tenants", "Client")

    # Get all domains that end with .localhost (excluding public/main tenants)
    localhost_domains = Domain.objects.filter(domain__endswith=".localhost").exclude(
        tenant__schema_name__in=["public", "main"]
    )

    updated_count = 0
    skipped_count = 0
    for domain in localhost_domains:
        old_domain = domain.domain
        # Replace .localhost with .statuswatch.kontentwave.digital
        new_domain = old_domain.replace(".localhost", ".statuswatch.kontentwave.digital")

        # Check if the new domain already exists (avoid duplicate key error)
        if Domain.objects.filter(domain=new_domain).exists():
            print(f"⏭️  Skipping {old_domain} - {new_domain} already exists")
            skipped_count += 1
            continue

        # Update the domain
        domain.domain = new_domain
        domain.save()
        updated_count += 1

        print(f"✅ Updated domain: {old_domain} → {new_domain}")

    if updated_count > 0:
        print(f"\n✅ Successfully updated {updated_count} tenant domain(s)")
    if skipped_count > 0:
        print(f"⏭️  Skipped {skipped_count} domain(s) (already exist)")
    if updated_count == 0 and skipped_count == 0:
        print("ℹ️  No .localhost domains found to update")


def reverse_fix(apps, schema_editor):
    """
    Reverse migration: change back to .localhost (for rollback scenarios)
    """
    Domain = apps.get_model("tenants", "Domain")

    # Get all domains that end with .statuswatch.kontentwave.digital
    production_domains = Domain.objects.filter(
        domain__endswith=".statuswatch.kontentwave.digital"
    ).exclude(tenant__schema_name__in=["public", "main"])

    for domain in production_domains:
        old_domain = domain.domain
        new_domain = old_domain.replace(".statuswatch.kontentwave.digital", ".localhost")
        domain.domain = new_domain
        domain.save()
        print(f"⏪ Reverted domain: {old_domain} → {new_domain}")


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0007_add_loopback_domains"),
    ]

    operations = [
        migrations.RunPython(fix_tenant_domains, reverse_code=reverse_fix),
    ]
