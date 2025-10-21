"""
Performance logging utilities for StatusWatch.

Helps identify slow operations and performance bottlenecks.
"""

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

perf_logger = logging.getLogger("api.performance")


def log_performance(threshold_ms: float = 1000):
    """
    Decorator to log slow function executions.

    Logs a warning when function execution exceeds the threshold.
    Useful for identifying performance bottlenecks.

    Args:
        threshold_ms: Threshold in milliseconds. Functions taking longer
                     than this will be logged.

    Example:
        @log_performance(threshold_ms=500)
        def expensive_database_operation():
            # ... complex query ...
            pass

    Returns:
        Decorator function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start = time.time()
            result = func(*args, **kwargs)
            duration_ms = (time.time() - start) * 1000

            if duration_ms > threshold_ms:
                perf_logger.warning(
                    f"Slow execution: {func.__name__}",
                    extra={
                        "perf_function": func.__name__,
                        "perf_module": func.__module__,
                        "perf_duration_ms": round(duration_ms, 2),
                        "perf_threshold_ms": threshold_ms,
                        "perf_args_count": len(args),
                        "perf_kwargs_keys": list(kwargs.keys()) if kwargs else [],
                    },
                )

            return result

        return wrapper

    return decorator


class PerformanceMonitor:
    """
    Context manager for monitoring performance of code blocks.

    Example:
        with PerformanceMonitor('database_migration', threshold_ms=5000):
            # ... migration code ...
            pass
    """

    def __init__(self, operation_name: str, threshold_ms: float = 1000):
        """
        Initialize performance monitor.

        Args:
            operation_name: Name of the operation being monitored
            threshold_ms: Threshold in milliseconds for logging
        """
        self.operation_name = operation_name
        self.threshold_ms = threshold_ms
        self.start_time = None

    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and log if threshold exceeded."""
        duration_ms = (time.time() - self.start_time) * 1000

        if duration_ms > self.threshold_ms:
            perf_logger.warning(
                f"Slow operation: {self.operation_name}",
                extra={
                    "perf_operation": self.operation_name,
                    "perf_duration_ms": round(duration_ms, 2),
                    "perf_threshold_ms": self.threshold_ms,
                    "perf_exception": str(exc_type.__name__) if exc_type else None,
                },
            )

        return False  # Don't suppress exceptions


def log_query_count(func: Callable) -> Callable:
    """
    Decorator to log database query count for a function.

    Helps identify N+1 query problems and excessive database access.

    Example:
        @log_query_count
        def get_all_users_with_profiles():
            return User.objects.prefetch_related('profile').all()

    Returns:
        Decorated function
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as context:
            result = func(*args, **kwargs)

        query_count = len(context.captured_queries)

        # Log warning if query count is high
        if query_count > 10:
            perf_logger.warning(
                f"High query count: {func.__name__}",
                extra={
                    "perf_function": func.__name__,
                    "perf_module": func.__module__,
                    "perf_query_count": query_count,
                    "perf_queries": [
                        q["sql"][:100] for q in context.captured_queries[:5]
                    ],  # First 5 queries
                },
            )

        return result

    return wrapper
