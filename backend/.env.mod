# Dedicated environment for the modular monolith stack
DJANGO_ENV=development
DEBUG=1
SECRET_KEY=django-insecure-mod-stack-only
DATABASE_URL=postgresql://postgres:devpass@mod_db:5432/statuswatch_mod
REDIS_URL=redis://mod_redis:6379/0
CELERY_BROKER_URL=redis://mod_redis:6379/0
CELERY_RESULT_BACKEND=redis://mod_redis:6379/1
DEFAULT_TENANT_DOMAIN_SUFFIX=localhost
FRONTEND_URL=http://localhost:8081
ADMIN_URL=admin/

# Stripe test credentials (safe defaults)
STRIPE_PUBLIC_KEY=pk_test_statuswatch_mod
STRIPE_SECRET_KEY=sk_test_statuswatch_mod
STRIPE_PRO_PRICE_ID=price_test_statuswatch_mod
STRIPE_WEBHOOK_SECRET=whsec_test_statuswatch_mod
