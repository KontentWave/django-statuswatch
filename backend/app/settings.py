"""
Settings router for StatusWatch project.

Automatically loads the appropriate settings module based on the DJANGO_ENV
environment variable or DEBUG flag. Provides detailed logging of which
configuration is loaded for debugging purposes.

Environment Variables:
    DJANGO_ENV: Explicit environment selection ('development' or 'production')
    DEBUG: Falls back to DEBUG=True for development if DJANGO_ENV not set
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

# -------------------------------------------------------------------
# Settings Loading Logger
# -------------------------------------------------------------------
# Create dedicated logger for settings loading (before Django configuration)
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

settings_logger = logging.getLogger("app.settings_loader")
settings_logger.setLevel(logging.INFO)

# File handler for settings loading events
settings_log_handler = RotatingFileHandler(
    LOG_DIR / "settings.log",
    maxBytes=1024 * 1024 * 10,  # 10 MB
    backupCount=5,
)
settings_log_handler.setFormatter(
    logging.Formatter("[%(levelname)s] %(asctime)s %(name)s - %(message)s")
)
settings_logger.addHandler(settings_log_handler)

# Console handler for immediate visibility
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s - %(message)s"))
settings_logger.addHandler(console_handler)

# -------------------------------------------------------------------
# Environment Detection
# -------------------------------------------------------------------
# Explicit environment selection via DJANGO_ENV (recommended)
django_env = os.environ.get("DJANGO_ENV", "").lower()

# Fallback: detect from DEBUG flag if DJANGO_ENV not set
debug_flag = os.environ.get("DEBUG", "False").lower() in ("true", "1", "yes", "on")

if django_env == "production":
    environment = "production"
    settings_logger.info("🚀 DJANGO_ENV=production detected - Loading production settings")
elif django_env == "development":
    environment = "development"
    settings_logger.info("🔧 DJANGO_ENV=development detected - Loading development settings")
elif debug_flag:
    environment = "development"
    settings_logger.info(
        "🔧 DEBUG=True detected (DJANGO_ENV not set) - Loading development settings"
    )
else:
    # Default to production if nothing is set (fail-safe)
    environment = "production"
    settings_logger.warning(
        "⚠️  No DJANGO_ENV or DEBUG set - Defaulting to production settings for safety"
    )

# -------------------------------------------------------------------
# Load Environment-Specific Settings
# -------------------------------------------------------------------
settings_logger.info(f"📂 Loading settings from: app.settings_{environment}")
settings_logger.info(f"📍 BASE_DIR: {BASE_DIR}")
settings_logger.info(f"📝 LOG_DIR: {LOG_DIR}")

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
