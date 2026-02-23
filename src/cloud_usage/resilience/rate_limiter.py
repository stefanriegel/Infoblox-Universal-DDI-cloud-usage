"""Adaptive per-provider rate limiter.

Tracks per-provider backoff state and respects Retry-After headers from API
responses. Starts aggressive (full speed), backs off when rate limits hit,
and gradually recovers as successful calls are made.

Thread-safe: all mutable state access is protected by a threading lock.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Number of consecutive rate limits before a provider is considered heavily throttled.
_HEAVY_THROTTLE_THRESHOLD = 3

# Factor by which delay decreases on each successful call.
_DECAY_FACTOR = 0.5

# Minimum delay before it is rounded down to zero.
_MIN_DELAY = 0.05


@dataclass
class _ProviderState:
    """Internal state for a single provider's backoff tracking.

    Attributes:
        delay: Current recommended delay in seconds.
        consecutive_rate_limits: Number of consecutive rate-limit responses.
        last_rate_limit_time: Monotonic timestamp of most recent rate limit.
        warned: Whether the sustained-throttling warning has been emitted.
    """

    delay: float = 0.0
    consecutive_rate_limits: int = 0
    last_rate_limit_time: float = 0.0
    warned: bool = False


class RateLimiter:
    """Adaptive rate limiter that tracks per-provider backoff state.

    Fully self-tuning: adapts based on API responses (429s, Retry-After headers).
    Starts aggressive (full speed), backs off when rate limits hit, and warns
    once on sustained throttling.
    """

    def __init__(self) -> None:
        """Initialize the rate limiter with empty per-provider state."""
        self._providers: dict[str, _ProviderState] = {}
        self._lock = threading.Lock()

    def _get_state(self, provider: str) -> _ProviderState:
        """Get or create state for a provider. Must be called under lock."""
        if provider not in self._providers:
            self._providers[provider] = _ProviderState()
        return self._providers[provider]

    def record_rate_limit(self, provider: str, retry_after: float | None = None) -> None:
        """Record that a provider returned a rate-limit response.

        If a Retry-After header value is provided, it is used directly.
        Otherwise, the internal backoff counter is incremented with exponential
        growth based on consecutive rate-limit hits.

        Args:
            provider: Cloud provider identifier (e.g., "aws", "azure", "gcp").
            retry_after: Retry-After header value in seconds, or None.
        """
        with self._lock:
            state = self._get_state(provider)
            state.consecutive_rate_limits += 1
            state.last_rate_limit_time = time.monotonic()

            if retry_after is not None:
                state.delay = retry_after
            else:
                # Exponential backoff: 1s, 2s, 4s, 8s, ... capped at 60s
                state.delay = min(60.0, 1.0 * (2 ** (state.consecutive_rate_limits - 1)))

            if state.consecutive_rate_limits >= _HEAVY_THROTTLE_THRESHOLD and not state.warned:
                state.warned = True
                logger.warning(
                    "%s rate limiting is heavy -- scan will take longer than usual",
                    provider,
                )

    def get_delay(self, provider: str) -> float:
        """Return the current recommended delay for a provider.

        Returns 0.0 if the provider has no active backoff. The delay represents
        how long the caller should wait before the next API call.

        Args:
            provider: Cloud provider identifier.

        Returns:
            Recommended delay in seconds (0.0 if no backoff active).
        """
        with self._lock:
            state = self._get_state(provider)
            return state.delay

    def record_success(self, provider: str) -> None:
        """Record a successful API call, gradually reducing backoff.

        Halves the current delay and resets the consecutive rate-limit counter.
        Once delay drops below the minimum threshold, it resets to zero.

        Args:
            provider: Cloud provider identifier.
        """
        with self._lock:
            state = self._get_state(provider)
            state.consecutive_rate_limits = max(0, state.consecutive_rate_limits - 1)
            state.delay *= _DECAY_FACTOR
            if state.delay < _MIN_DELAY:
                state.delay = 0.0

    def is_throttled(self, provider: str) -> bool:
        """Check if a provider is currently in a heavy throttling state.

        Returns True if the provider has hit the rate-limit threshold for
        consecutive failures, indicating the "scan will take longer than usual"
        warning should be displayed.

        Args:
            provider: Cloud provider identifier.

        Returns:
            True if the provider is heavily throttled.
        """
        with self._lock:
            state = self._get_state(provider)
            return state.consecutive_rate_limits >= _HEAVY_THROTTLE_THRESHOLD
