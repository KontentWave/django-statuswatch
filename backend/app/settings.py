"""Settings router for StatusWatch project."""

import os

from modules.core.settings import setup_settings_logging

# -------------------------------------------------------------------
# Environment Detection + Logging (shared helper)
# -------------------------------------------------------------------
logging_context = setup_settings_logging()
settings_logger = logging_context.logger
environment = logging_context.environment

if environment == "development":
    from app.settings_development import *  # noqa: F403, F401

    settings_logger.info("✅ Development settings loaded successfully")
    settings_logger.info("   - DEBUG: True")
    settings_logger.info("   - ALLOWED_HOSTS: Permissive (localhost, *.local)")
    settings_logger.info("   - CORS: Permissive (localhost:5173)")
    settings_logger.info("   - HTTPS: Disabled")
    settings_logger.info("   - Email: Console backend")
    settings_logger.info("   - Stripe: Validation disabled")
    settings_logger.info("   - Sentry: Disabled")
elif environment == "production":
    from app.settings_production import *  # noqa: F403, F401

    settings_logger.info("✅ Production settings loaded successfully")
    settings_logger.info("   - DEBUG: False")
    settings_logger.info("   - ALLOWED_HOSTS: From env (strict)")
    settings_logger.info("   - CORS: From env (strict)")
    settings_logger.info("   - HTTPS: Enforced")
    settings_logger.info("   - Email: SMTP backend")
    settings_logger.info("   - Stripe: Validation enabled")

    # Only log Sentry status if DSN is set
    sentry_dsn = os.environ.get("SENTRY_DSN", "")
    if sentry_dsn:
        settings_logger.info(
            f"   - Sentry: Enabled ({os.environ.get('SENTRY_ENVIRONMENT', 'production')})"
        )
    else:
        settings_logger.info("   - Sentry: Disabled (no DSN)")

settings_logger.info("=" * 70)
