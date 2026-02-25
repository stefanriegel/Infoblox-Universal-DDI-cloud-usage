"""Tests for adaptive per-provider rate limiter."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.resilience.rate_limiter import RateLimiter


class TestInitialState:
    """Test that new providers start with zero delay."""

    def test_zero_delay_for_unknown_provider(self):
        """get_delay returns 0.0 for a provider with no recorded state."""
        limiter = RateLimiter()
        assert limiter.get_delay("aws") == 0.0

    def test_not_throttled_initially(self):
        """is_throttled returns False for a provider with no recorded state."""
        limiter = RateLimiter()
        assert limiter.is_throttled("aws") is False

    def test_multiple_providers_independent(self):
        """Different providers have independent state."""
        limiter = RateLimiter()
        assert limiter.get_delay("aws") == 0.0
        assert limiter.get_delay("azure") == 0.0
        assert limiter.get_delay("gcp") == 0.0


class TestRecordRateLimit:
    """Test that recording rate limits increases delay."""

    def test_first_rate_limit_increases_delay(self):
        """After one rate-limit hit, delay should be > 0."""
        limiter = RateLimiter()
        limiter.record_rate_limit("aws")
        assert limiter.get_delay("aws") > 0.0

    def test_consecutive_rate_limits_increase_delay(self):
        """Consecutive rate-limit hits should increase delay exponentially."""
        limiter = RateLimiter()
        limiter.record_rate_limit("aws")
        delay_1 = limiter.get_delay("aws")

        limiter.record_rate_limit("aws")
        delay_2 = limiter.get_delay("aws")

        assert delay_2 > delay_1

    def test_rate_limit_does_not_affect_other_providers(self):
        """Rate-limiting AWS should not affect Azure delay."""
        limiter = RateLimiter()
        limiter.record_rate_limit("aws")
        assert limiter.get_delay("azure") == 0.0


class TestRecordSuccess:
    """Test that successful calls immediately reset delay to zero."""

    def test_success_decreases_delay(self):
        """After rate-limit + single success, delay resets immediately to 0.0."""
        limiter = RateLimiter()
        limiter.record_rate_limit("aws")

        limiter.record_success("aws")

        assert limiter.get_delay("aws") == 0.0

    def test_multiple_successes_return_to_zero(self):
        """A single record_success() call is enough to bring delay to zero."""
        limiter = RateLimiter()
        limiter.record_rate_limit("aws")

        # A single success is sufficient for immediate reset
        limiter.record_success("aws")

        assert limiter.get_delay("aws") == 0.0

        # Calling record_success() again on already-zero state keeps it at zero
        limiter.record_success("aws")
        assert limiter.get_delay("aws") == 0.0

    def test_success_on_clean_provider_stays_zero(self):
        """Calling record_success on a provider with no backoff keeps delay at 0."""
        limiter = RateLimiter()
        limiter.record_success("aws")
        assert limiter.get_delay("aws") == 0.0


class TestRetryAfterHeader:
    """Test that Retry-After header values are respected."""

    def test_retry_after_sets_exact_delay(self):
        """Retry-After value should set the delay directly."""
        limiter = RateLimiter()
        limiter.record_rate_limit("aws", retry_after=10.0)
        assert limiter.get_delay("aws") == 10.0

    def test_retry_after_overrides_calculated_delay(self):
        """Retry-After value overrides the internally calculated delay."""
        limiter = RateLimiter()
        # Build up some internal backoff
        limiter.record_rate_limit("aws")
        limiter.record_rate_limit("aws")

        # Now provide explicit Retry-After
        limiter.record_rate_limit("aws", retry_after=30.0)
        assert limiter.get_delay("aws") == 30.0

    def test_retry_after_zero(self):
        """Retry-After of 0 sets delay to 0."""
        limiter = RateLimiter()
        limiter.record_rate_limit("aws")
        limiter.record_rate_limit("aws", retry_after=0.0)
        assert limiter.get_delay("aws") == 0.0


class TestIsThrottled:
    """Test heavy throttling detection."""

    def test_not_throttled_after_one_rate_limit(self):
        """One rate-limit hit is not enough for heavy throttling."""
        limiter = RateLimiter()
        limiter.record_rate_limit("aws")
        assert limiter.is_throttled("aws") is False

    def test_throttled_after_multiple_consecutive_rate_limits(self):
        """Reaching the threshold of consecutive rate-limits triggers throttled state."""
        limiter = RateLimiter()
        limiter.record_rate_limit("aws")
        limiter.record_rate_limit("aws")
        limiter.record_rate_limit("aws")
        assert limiter.is_throttled("aws") is True

    def test_success_reduces_throttle_state(self):
        """A single record_success() immediately clears throttled state (consecutive_rate_limits=0)."""
        limiter = RateLimiter()
        # Hit the threshold multiple times
        for _ in range(3):
            limiter.record_rate_limit("aws")
        assert limiter.is_throttled("aws") is True

        # A single success resets consecutive_rate_limits to 0, clearing throttled state
        limiter.record_success("aws")
        assert limiter.get_delay("aws") == 0.0
        assert limiter.is_throttled("aws") is False


class TestThreadSafety:
    """Test that concurrent access to the rate limiter is safe."""

    def test_concurrent_record_operations(self):
        """Multiple threads recording rate limits and successes simultaneously."""
        limiter = RateLimiter()
        errors: list[Exception] = []
        iterations = 100

        def rate_limit_worker():
            try:
                for _ in range(iterations):
                    limiter.record_rate_limit("aws")
            except Exception as e:
                errors.append(e)

        def success_worker():
            try:
                for _ in range(iterations):
                    limiter.record_success("aws")
            except Exception as e:
                errors.append(e)

        def read_worker():
            try:
                for _ in range(iterations):
                    limiter.get_delay("aws")
                    limiter.is_throttled("aws")
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=rate_limit_worker))
            threads.append(threading.Thread(target=success_worker))
            threads.append(threading.Thread(target=read_worker))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_concurrent_multiple_providers(self):
        """Multiple threads accessing different providers simultaneously."""
        limiter = RateLimiter()
        errors: list[Exception] = []
        iterations = 100
        providers = ["aws", "azure", "gcp"]

        def worker(provider: str):
            try:
                for _ in range(iterations):
                    limiter.record_rate_limit(provider)
                    limiter.get_delay(provider)
                    limiter.record_success(provider)
                    limiter.is_throttled(provider)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(p,)) for p in providers]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"
