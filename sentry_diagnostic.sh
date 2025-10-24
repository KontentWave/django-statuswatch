#!/bin/bash
# Sentry Integration Diagnostic Script
# Run from project root: bash sentry_diagnostic.sh

echo "=========================================="
echo "1. CHECK DJANGO SERVER LOGS"
echo "=========================================="
cd /home/marcel/projects/statuswatch-project/backend
python manage.py check --deploy 2>&1 | head -100

echo ""
echo "=========================================="
echo "2. CHECK SENTRY SDK INSTALLATION"
echo "=========================================="
pip show sentry-sdk 2>&1

echo ""
echo "=========================================="
echo "3. TEST SENTRY IMPORTS"
echo "=========================================="
python -c "
import sys
try:
    import sentry_sdk
    print('✓ sentry_sdk imported successfully')
    print(f'  Version: {sentry_sdk.VERSION}')
except ImportError as e:
    print(f'✗ Failed to import sentry_sdk: {e}')
    sys.exit(1)

try:
    from sentry_sdk.integrations.django import DjangoIntegration
    print('✓ DjangoIntegration imported')
except ImportError as e:
    print(f'✗ Failed to import DjangoIntegration: {e}')

try:
    from sentry_sdk.integrations.celery import CeleryIntegration
    print('✓ CeleryIntegration imported')
except ImportError as e:
    print(f'✗ Failed to import CeleryIntegration: {e}')

try:
    from sentry_sdk.integrations.redis import RedisIntegration
    print('✓ RedisIntegration imported')
except ImportError as e:
    print(f'✗ Failed to import RedisIntegration: {e}')

try:
    from sentry_sdk.integrations.logging import LoggingIntegration
    print('✓ LoggingIntegration imported')
except ImportError as e:
    print(f'✗ Failed to import LoggingIntegration: {e}')
" 2>&1

echo ""
echo "=========================================="
echo "4. CHECK SETTINGS.PY SYNTAX"
echo "=========================================="
python -m py_compile app/settings.py 2>&1
if [ $? -eq 0 ]; then
    echo "✓ settings.py syntax is valid"
else
    echo "✗ settings.py has syntax errors"
fi

echo ""
echo "=========================================="
echo "5. CHECK HEALTH.PY SYNTAX"
echo "=========================================="
python -m py_compile api/health.py 2>&1
if [ $? -eq 0 ]; then
    echo "✓ api/health.py syntax is valid"
else
    echo "✗ api/health.py has syntax errors"
fi

echo ""
echo "=========================================="
echo "6. TEST DJANGO SETTINGS IMPORT"
echo "=========================================="
python manage.py shell -c "
from django.conf import settings
print('✓ Django settings loaded')
print(f'  DEBUG: {settings.DEBUG}')
print(f'  SENTRY_DSN configured: {bool(getattr(settings, \"SENTRY_DSN\", None))}')
" 2>&1

echo ""
echo "=========================================="
echo "7. CHECK ENVIRONMENT VARIABLES"
echo "=========================================="
if [ -f .env ]; then
    echo "✓ .env file exists"
    echo "Checking Sentry-related variables:"
    grep -E "^SENTRY_" .env 2>&1 || echo "  (no SENTRY_* variables found)"
else
    echo "✗ .env file not found"
fi

echo ""
echo "=========================================="
echo "8. TEST HEALTH ENDPOINTS IMPORTS"
echo "=========================================="
python manage.py shell -c "
try:
    from api.health import health_check, readiness_check, metrics
    print('✓ Health endpoints imported successfully')
except ImportError as e:
    print(f'✗ Failed to import health endpoints: {e}')
except Exception as e:
    print(f'✗ Error importing health endpoints: {e}')
" 2>&1

echo ""
echo "=========================================="
echo "9. TEST URL CONFIGURATION"
echo "=========================================="
python manage.py show_urls 2>&1 | grep -E "(health|metrics)" || echo "(show_urls command not available, checking urls manually...)"
python manage.py shell -c "
from django.urls import resolve
try:
    resolve('/health/')
    print('✓ /health/ route exists')
except Exception as e:
    print(f'✗ /health/ route error: {e}')

try:
    resolve('/health/ready/')
    print('✓ /health/ready/ route exists')
except Exception as e:
    print(f'✗ /health/ready/ route error: {e}')

try:
    resolve('/metrics/')
    print('✓ /metrics/ route exists')
except Exception as e:
    print(f'✗ /metrics/ route error: {e}')
" 2>&1

echo ""
echo "=========================================="
echo "10. TRY STARTING DJANGO (DRY RUN)"
echo "=========================================="
timeout 5 python manage.py runserver --noreload 2>&1 || echo "(Server start test completed)"

echo ""
echo "=========================================="
echo "DIAGNOSTIC COMPLETE"
echo "=========================================="
echo "Please paste the full output above into the chat."
