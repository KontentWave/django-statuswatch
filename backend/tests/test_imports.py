import pytest

def test_import_restframework():
    pytest.importorskip("rest_framework")

def test_import_django_tenants():
    pytest.importorskip("django_tenants")

def test_import_celery():
    pytest.importorskip("celery")

def test_import_redis():
    pytest.importorskip("redis")
