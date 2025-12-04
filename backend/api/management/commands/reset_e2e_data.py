"""Utilities for Playwright runs to keep the database pristine."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import ProgrammingError, connection, transaction
from django_tenants.utils import get_public_schema_name
from tenants.models import Client, Domain

logger = logging.getLogger("api.management.reset_e2e_data")

_RESERVED_SCHEMA_NAMES: set[str] = {
    "information_schema",
    "public",
    "postgis",
    "tiger",
    "tiger_data",
    "topology",
}
_RESERVED_SCHEMA_PREFIXES: tuple[str, ...] = ("pg_",)


class Command(BaseCommand):
    help = (
        "Delete all tenant data so E2E tests always start from a clean slate. "
        "Drops tenant schemas, removes orphan domains, and leaves the public schema untouched."
    )

    def add_arguments(self, parser) -> None:  # pragma: no cover - CLI plumbing
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow running even when DEBUG=False (intended for CI only).",
        )

    def handle(self, *args, **options):  # pragma: no cover - exercised via management command
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "reset_e2e_data is only permitted in DEBUG/test environments. "
                "Use --force to override inside CI sandboxes."
            )

        connection.set_schema_to_public()
        public_schema = get_public_schema_name()

        self.stdout.write(self.style.WARNING("Resetting tenant data for Playwright E2E tests…"))

        tenants_deleted = self._drop_tenants(public_schema)
        domains_deleted = self._delete_orphan_domains()
        schemas_dropped = self._drop_orphan_schemas()

        connection.set_schema_to_public()

        self.stdout.write(
            self.style.SUCCESS(
                "reset_e2e_data complete: "
                f"deleted {tenants_deleted} tenant(s), "
                f"removed {domains_deleted} orphan domain(s), "
                f"dropped {schemas_dropped} schema(s)."
            )
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _drop_tenants(self, public_schema: str) -> int:
        deleted = 0
        tenants = list(Client.objects.exclude(schema_name=public_schema))
        for tenant in tenants:
            schema = tenant.schema_name
            name = tenant.name
            try:
                tenant.delete(force_drop=True)
            except ProgrammingError as exc:
                self.stdout.write(
                    self.style.NOTICE(
                        f" ! Schema '{schema}' has missing tables ({exc.__class__.__name__}); forcing a manual drop"
                    )
                )
                self._force_drop_schema(schema)
                Domain.objects.filter(tenant_id=tenant.id).delete()
                self._hard_delete_tenant_row(tenant.id)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Failed to delete tenant %s (%s)", name, schema)
                raise CommandError(f"Failed to drop tenant schema '{schema}'") from exc
            deleted += 1
            self.stdout.write(f" • Dropped tenant '{name}' ({schema})")
        return deleted

    def _delete_orphan_domains(self) -> int:
        orphans = Domain.objects.filter(tenant__isnull=True)
        count = orphans.count()
        if count:
            orphans.delete()
        return count

    def _drop_orphan_schemas(self) -> int:
        if connection.vendor != "postgresql":
            return 0

        active_schemas = set(Client.objects.values_list("schema_name", flat=True))
        protected = active_schemas | _RESERVED_SCHEMA_NAMES

        with connection.cursor() as cursor:
            cursor.execute("SELECT schema_name FROM information_schema.schemata")
            rows: Iterable[tuple[str]] = cursor.fetchall()

        dropped = 0
        for (schema_name,) in rows:
            if schema_name in protected:
                continue
            if schema_name.startswith(_RESERVED_SCHEMA_PREFIXES):
                continue

            safe_schema = schema_name.replace('"', '""')

            try:
                with connection.cursor() as cursor:
                    cursor.execute(f'DROP SCHEMA IF EXISTS "{safe_schema}" CASCADE')
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Failed to drop schema %s", schema_name)
                raise CommandError(f"Could not drop orphan schema '{schema_name}'") from exc

            dropped += 1
            self.stdout.write(f" • Dropped orphan schema '{schema_name}'")

        return dropped

    def _force_drop_schema(self, schema_name: str) -> None:
        safe_schema = schema_name.replace('"', '""')
        with connection.cursor() as cursor:
            cursor.execute(f'DROP SCHEMA IF EXISTS "{safe_schema}" CASCADE')

    def _hard_delete_tenant_row(self, tenant_id: int) -> None:
        connection.set_schema_to_public()
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM tenants_client WHERE id = %s", [tenant_id])
