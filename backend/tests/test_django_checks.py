from django.core.management import call_command


def test_django_system_checks_ok():
    # Fails loudly if settings/apps are misconfigured
    call_command("check")
