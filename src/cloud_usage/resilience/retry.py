"""Retry decorator with exponential backoff and full jitter.

Applies category-aware retry logic: retries on rate-limit and network errors
with exponential backoff + full jitter, skips immediately on auth errors.

Full jitter formula: sleep = random.uniform(0, min(max_delay, base_delay * 2^attempt))
Source: AWS Builders Library -- Timeouts, retries, and backoff with jitter.
"""

from __future__ import annotations

import functools
import logging
import random
import threading
import time
from typing import Callable

from cloud_usage.errors.taxonomy import ErrorCategory, classify_error

logger = logging.getLogger(__name__)

_DEFAULT_RETRYABLE = frozenset({ErrorCategory.RATE_LIMIT, ErrorCategory.NETWORK})

_retry_context = threading.local()


def set_rate_limit_callback(callback: Callable[[int, Exception, float], None]) -> None:
    """Set a rate-limit callback for the current thread.

    The retry decorator will call this callback on each retry in addition
    to any static on_retry parameter. Used by the orchestrator to inject
    provider-scoped RateLimiter callbacks without modifying the 20+
    collector decorator applications.

    Args:
        callback: Function receiving (attempt, exception, sleep_time).
    """
    _retry_context.on_retry = callback


def clear_rate_limit_callback() -> None:
    """Clear the rate-limit callback for the current thread."""
    _retry_context.on_retry = None


def retry_with_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_categories: set[ErrorCategory] | None = None,
    on_retry: Callable[[int, Exception, float], None] | None = None,
) -> Callable:
    """Decorator: retry with exponential backoff and full jitter.

    Wraps a function so that transient failures (rate-limit, network) are
    retried with increasing random delays. Non-retryable errors (auth) are
    raised immediately.

    Args:
        max_retries: Maximum number of retry attempts (total calls = max_retries + 1).
        base_delay: Base delay in seconds for backoff calculation.
        max_delay: Upper cap on the backoff delay in seconds.
        retryable_categories: Set of ErrorCategory values eligible for retry.
            Defaults to {RATE_LIMIT, NETWORK}.
        on_retry: Optional callback invoked on each retry with
            (attempt_number, exception, sleep_time) for rate limiter integration.

    Returns:
        Decorated function with retry behavior.
    """
    if retryable_categories is None:
        retryable_categories = set(_DEFAULT_RETRYABLE)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    category = classify_error("unknown", exc)

                    if category not in retryable_categories or attempt == max_retries:
                        raise

                    # Full jitter: sleep = random(0, min(cap, base * 2^attempt))
                    exp_delay = min(max_delay, base_delay * (2 ** attempt))
                    sleep_time = random.uniform(0, exp_delay)

                    logger.warning(
                        "Retry %d/%d for %s (category=%s, sleeping %.2fs): %s",
                        attempt + 1,
                        max_retries,
                        func.__name__,
                        category.value,
                        sleep_time,
                        exc,
                    )

                    if on_retry is not None:
                        on_retry(attempt + 1, exc, sleep_time)

                    runtime_callback = getattr(_retry_context, "on_retry", None)
                    if runtime_callback is not None:
                        runtime_callback(attempt + 1, exc, sleep_time)

                    time.sleep(sleep_time)

            # Unreachable but satisfies the type checker
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator
