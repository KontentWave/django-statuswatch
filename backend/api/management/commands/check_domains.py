"""Inspect tenant and domain mappings from the Django CLI."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import connection
from django_tenants.utils import get_public_schema_name
from tenants.models import Client, Domain


class Command(BaseCommand):
    help = "Print tenants and domain mappings for quick local diagnostics."

    def add_arguments(self, parser) -> None:  # pragma: no cover - CLI plumbing
        parser.add_argument(
            "--domains-only",
            action="store_true",
            help="Skip the tenant summary and print only domain mappings.",
        )

    def handle(
        self, *args, **options
    ) -> None:  # pragma: no cover - exercised via management command
        connection.set_schema_to_public()

        if not options["domains_only"]:
            self._print_tenants()
            self.stdout.write("")

        self._print_domains()

    def _print_tenants(self) -> None:
        public_schema = get_public_schema_name()
        tenants = Client.objects.order_by("schema_name")

        self.stdout.write(self.style.MIGRATE_HEADING("Clients"))
        for tenant in tenants:
            marker = " (public)" if tenant.schema_name == public_schema else ""
            self.stdout.write(f"  {tenant.schema_name} ({tenant.name}){marker}")

        if not tenants.exists():
            self.stdout.write("  <none>")

    def _print_domains(self) -> None:
        domains = Domain.objects.select_related("tenant").order_by("domain")

        self.stdout.write(self.style.MIGRATE_HEADING("Domains"))
        for domain in domains:
            primary_marker = " [primary]" if domain.is_primary else ""
            self.stdout.write(f"  {domain.domain} -> {domain.tenant.schema_name}{primary_marker}")

        if not domains.exists():
            self.stdout.write("  <none>")
