"""Shared settings-logging helpers for environment routing."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path

_ENV_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class SettingsLoggingContext:
    """Metadata about the selected environment and logger state."""

    logger: logging.Logger
    base_dir: Path
    log_dir: Path
    environment: str
    source: str


def setup_settings_logging(
    *,
    env: Mapping[str, str] | None = None,
    logger_name: str = "app.settings_loader",
    log_filename: str = "settings.log",
) -> SettingsLoggingContext:
    """Configure the settings loader logger and resolve environment."""

    environ = env or os.environ
    base_dir = Path(__file__).resolve().parents[3]
    log_dir = base_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    _ensure_handlers(logger, log_dir / log_filename)

    environment, source = _resolve_environment(environ)
    _log_routing_banner(logger, base_dir, log_dir, environment, source)

    return SettingsLoggingContext(
        logger=logger,
        base_dir=base_dir,
        log_dir=log_dir,
        environment=environment,
        source=source,
    )


def _ensure_handlers(logger: logging.Logger, log_path: Path) -> None:
    has_file_handler = any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", None) == str(log_path)
        for handler in logger.handlers
    )
    if not has_file_handler:
        file_handler = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=5)
        file_handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(asctime)s %(name)s - %(message)s")
        )
        logger.addHandler(file_handler)

    has_console_handler = any(
        isinstance(handler, logging.StreamHandler) for handler in logger.handlers
    )
    if not has_console_handler:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s - %(message)s"))
        logger.addHandler(console_handler)


def _resolve_environment(environ: Mapping[str, str]) -> tuple[str, str]:
    django_env = environ.get("DJANGO_ENV", "").strip().lower()
    debug_flag = environ.get("DEBUG", "false").strip().lower() in _ENV_TRUE_VALUES

    if django_env == "production":
        return "production", "DJANGO_ENV=production"
    if django_env == "development":
        return "development", "DJANGO_ENV=development"
    if debug_flag:
        return "development", "DEBUG override"
    return "production", "default fail-safe"


def _log_routing_banner(
    logger: logging.Logger,
    base_dir: Path,
    log_dir: Path,
    environment: str,
    source: str,
) -> None:
    if environment == "production":
        logger.info("PROD mode selected via %s", source)
    else:
        logger.info("DEV mode selected via %s", source)

    logger.info("Loading settings from: app.settings_%s", environment)
    logger.info("BASE_DIR: %s", base_dir)
    logger.info("LOG_DIR: %s", log_dir)
