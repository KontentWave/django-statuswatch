"""Custom logging filters for the StatusWatch project."""

import logging


class MaxLevelFilter(logging.Filter):
    """Allow log records up to and including the configured level."""

    def __init__(self, level: str | int) -> None:
        super().__init__()
        if isinstance(level, str):
            resolved = logging.getLevelName(level.upper())
            if not isinstance(resolved, int):  # pragma: no cover - defensive
                raise ValueError(f"Unknown logging level: {level}")
            self.levelno = resolved
        else:
            self.levelno = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= self.levelno
