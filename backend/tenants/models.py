from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Client(TenantMixin):
    name: models.CharField = models.CharField(max_length=100)
    paid_until: models.DateField = models.DateField(null=True, blank=True)
    on_trial: models.BooleanField = models.BooleanField(default=True)
    created_on: models.DateField = models.DateField(auto_now_add=True)

    # auto-create the schema when saving this tenant
    auto_create_schema = True


class Domain(DomainMixin):
    pass
