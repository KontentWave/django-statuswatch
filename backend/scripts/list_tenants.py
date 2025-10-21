"""Quick helper script to list tenants, their domains, and owner users.

Usage:
    python manage.py shell -c "exec(open('scripts/list_tenants.py').read())"
"""

from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")


def main() -> None:
    import django

    django.setup()

    from django.contrib.auth import get_user_model
    from django_tenants.utils import schema_context
    from tenants.models import Client, Domain

    User = get_user_model()

    tenants = Client.objects.order_by("-created_on").all()
    if not tenants:
        print("No tenants found.")
        return

    for tenant in tenants:
        domains = Domain.objects.filter(tenant=tenant).values_list("domain", flat=True)
        print("=" * 72)
        print(f"Tenant: {tenant.name} (schema={tenant.schema_name})")
        print(f"Created on: {tenant.created_on}")
        if domains:
            print("Domains: " + ", ".join(sorted(domains)))
        else:
            print("Domains: -- none --")

        if tenant.schema_name == "public":
            continue

        with schema_context(tenant.schema_name):
            owners = (
                User.objects.filter(groups__name="Owner")
                .order_by("-date_joined")
                .values("id", "email", "date_joined")
            )
            total_users = User.objects.count()

        print(f"Users in schema: {total_users}")
        if owners:
            print("Owner group members:")
            for owner in owners:
                print(f"  - id={owner['id']} email={owner['email']} joined={owner['date_joined']}")
        else:
            print("Owner group members: none")
    print("=" * 72)


main()
