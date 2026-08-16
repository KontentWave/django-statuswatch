"""Ensure Django's default test host maps to a tenant domain."""

from __future__ import annotations

from django.conf import settings
from django.db import connection
from django_tenants.utils import get_tenant_domain_model
from tenants.models import Client


class TestHostTenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.trigger_host = getattr(settings, "TEST_TENANT_TRIGGER_HOST", "testserver")
        self.override_host = getattr(settings, "TEST_TENANT_HTTP_HOST", "test.localhost")
        public_schema = getattr(settings, "PUBLIC_SCHEMA_NAME", "public")
        self.public_hosts = {
            "localhost",
            "127.0.0.1",
            f"{public_schema}.localhost",
        }

    def __call__(self, request):
        host_header = request.META.get("HTTP_HOST", "")
        hostname = host_header.split(":")[0].lower()
        original_hostname = hostname

        # Ensure domain resolution happens against public schema
        connection.set_schema_to_public()

        # If using Django's default test host, rewrite to a known tenant domain
        if hostname == self.trigger_host and self.override_host:
            hostname = self.override_host.split(":")[0]
            request.META["HTTP_HOST"] = self.override_host
            request.META["SERVER_NAME"] = hostname
            request._cached_get_host = self.override_host  # type: ignore[attr-defined]

        # Resolve tenant domain from public schema and bind the connection/request early
        Domain = get_tenant_domain_model()
        domain = Domain.objects.filter(domain=hostname).select_related("tenant").first()
        if domain and domain.tenant:
            connection.set_tenant(domain.tenant)
            request.tenant = domain.tenant  # type: ignore[attr-defined]
            request.urlconf = settings.ROOT_URLCONF
        elif original_hostname in self.public_hosts:
            # Explicit public hosts must remain on the public schema so centralized
            # login and public routes do not get rebound to the default test tenant.
            connection.set_schema_to_public()
            request.urlconf = settings.PUBLIC_SCHEMA_URLCONF
        else:
            # Fallback to known test tenant if domain lookup fails (e.g. in tests)
            fallback = Client.objects.filter(schema_name="test_tenant").first()
            if fallback:
                connection.set_tenant(fallback)
                request.tenant = fallback  # type: ignore[attr-defined]
                request.urlconf = settings.ROOT_URLCONF

        # Host is rewritten; let TenantMainMiddleware resolve/bind the tenant.

        return self.get_response(request)
