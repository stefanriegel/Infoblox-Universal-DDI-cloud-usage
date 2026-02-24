"""Tests for retry decorator with exponential backoff and full jitter."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.errors.taxonomy import ErrorCategory
from cloud_usage.resilience.retry import (
    _retry_context,
    clear_rate_limit_callback,
    retry_with_backoff,
    set_rate_limit_callback,
)


# -- Custom exception classes for testing retry behavior --


class RateLimitError(Exception):
    """Simulates a 429 rate-limit error."""

    def __init__(self):
        super().__init__("429 Too Many Requests")


class NetworkTimeoutError(Exception):
    """Simulates a network timeout."""

    def __init__(self):
        super().__init__("Connection timed out")


class CredentialError(Exception):
    """Simulates an auth credential failure."""

    def __init__(self):
        super().__init__("AccessDenied: insufficient permissions")


class UnknownError(Exception):
    """Simulates an unclassified error."""

    def __init__(self):
        super().__init__("Something completely unexpected")


# -- Tests --


class TestRetrySuccessOnFirstAttempt:
    """Test that functions succeeding immediately are not retried."""

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_no_retry_needed(self, mock_sleep):
        """Function succeeds on first call -- no retries, no sleep."""

        @retry_with_backoff(max_retries=3)
        def always_succeeds():
            return "ok"

        result = always_succeeds()

        assert result == "ok"
        mock_sleep.assert_not_called()


class TestRetryOnRateLimitErrors:
    """Test retry behavior for rate-limit category errors."""

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_retries_on_rate_limit_then_succeeds(self, mock_sleep):
        """Retries on rate-limit error and succeeds on second attempt."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def fails_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError()
            return "recovered"

        result = fails_once()

        assert result == "recovered"
        assert call_count == 2
        assert mock_sleep.call_count == 1

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_retries_multiple_rate_limits(self, mock_sleep):
        """Retries multiple consecutive rate-limit errors."""
        call_count = 0

        @retry_with_backoff(max_retries=5, base_delay=1.0)
        def fails_thrice():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise RateLimitError()
            return "recovered"

        result = fails_thrice()

        assert result == "recovered"
        assert call_count == 4
        assert mock_sleep.call_count == 3


class TestRetryOnNetworkErrors:
    """Test retry behavior for network category errors."""

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_retries_on_network_error(self, mock_sleep):
        """Retries on network timeout error and succeeds on second attempt."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def flaky_network():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise NetworkTimeoutError()
            return "connected"

        result = flaky_network()

        assert result == "connected"
        assert call_count == 2
        assert mock_sleep.call_count == 1


class TestNoRetryOnAuthErrors:
    """Test that auth errors are raised immediately without retry."""

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_auth_error_raises_immediately(self, mock_sleep):
        """Auth errors should never be retried -- raised on first attempt."""
        call_count = 0

        @retry_with_backoff(max_retries=5)
        def auth_failure():
            nonlocal call_count
            call_count += 1
            raise CredentialError()

        try:
            auth_failure()
            assert False, "Should have raised CredentialError"
        except CredentialError:
            pass

        assert call_count == 1
        mock_sleep.assert_not_called()


class TestMaxRetriesExhausted:
    """Test behavior when all retry attempts are exhausted."""

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_raises_after_max_retries(self, mock_sleep):
        """Raises the original exception after exhausting all retries."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise RateLimitError()

        try:
            always_fails()
            assert False, "Should have raised RateLimitError"
        except RateLimitError:
            pass

        # 1 initial + 3 retries = 4 total calls
        assert call_count == 4
        # 3 sleeps (one before each retry)
        assert mock_sleep.call_count == 3


class TestExponentialBackoff:
    """Test that backoff delay increases exponentially with full jitter."""

    @patch("cloud_usage.resilience.retry.random.uniform")
    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_backoff_increases_exponentially(self, mock_sleep, mock_uniform):
        """Sleep delays should increase exponentially: base*2^0, base*2^1, base*2^2, ..."""
        # Make random.uniform return the max of the range (deterministic for testing)
        mock_uniform.side_effect = lambda low, high: high

        call_count = 0

        @retry_with_backoff(max_retries=4, base_delay=1.0, max_delay=60.0)
        def always_rate_limited():
            nonlocal call_count
            call_count += 1
            raise RateLimitError()

        try:
            always_rate_limited()
        except RateLimitError:
            pass

        # Verify the upper bounds passed to random.uniform increase exponentially
        # attempt 0: min(60, 1.0 * 2^0) = 1.0
        # attempt 1: min(60, 1.0 * 2^1) = 2.0
        # attempt 2: min(60, 1.0 * 2^2) = 4.0
        # attempt 3: min(60, 1.0 * 2^3) = 8.0
        assert mock_uniform.call_count == 4
        expected_caps = [1.0, 2.0, 4.0, 8.0]
        for i, expected_cap in enumerate(expected_caps):
            _, actual_high = mock_uniform.call_args_list[i][0]
            assert actual_high == expected_cap, f"Attempt {i}: expected cap {expected_cap}, got {actual_high}"

    @patch("cloud_usage.resilience.retry.random.uniform")
    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_backoff_capped_at_max_delay(self, mock_sleep, mock_uniform):
        """Backoff delay is capped at max_delay even with many retries."""
        mock_uniform.side_effect = lambda low, high: high

        call_count = 0

        @retry_with_backoff(max_retries=10, base_delay=1.0, max_delay=5.0)
        def always_rate_limited():
            nonlocal call_count
            call_count += 1
            raise RateLimitError()

        try:
            always_rate_limited()
        except RateLimitError:
            pass

        # After attempt 2 (cap = 4.0), attempt 3+ should be capped at max_delay=5.0
        for i in range(3, mock_uniform.call_count):
            _, actual_high = mock_uniform.call_args_list[i][0]
            assert actual_high == 5.0, f"Attempt {i}: expected cap 5.0, got {actual_high}"

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_jitter_produces_values_in_range(self, mock_sleep):
        """Sleep times should be between 0 and the exponential cap (full jitter)."""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=2.0, max_delay=60.0)
        def always_rate_limited():
            nonlocal call_count
            call_count += 1
            raise RateLimitError()

        try:
            always_rate_limited()
        except RateLimitError:
            pass

        for i, call_args in enumerate(mock_sleep.call_args_list):
            sleep_time = call_args[0][0]
            exp_cap = min(60.0, 2.0 * (2 ** i))
            assert 0.0 <= sleep_time <= exp_cap, (
                f"Attempt {i}: sleep_time {sleep_time} not in [0, {exp_cap}]"
            )


class TestOnRetryCallback:
    """Test the on_retry callback mechanism."""

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_on_retry_called_with_correct_args(self, mock_sleep):
        """on_retry receives (attempt_number, exception, sleep_time)."""
        callback = MagicMock()
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=1.0, on_retry=callback)
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RateLimitError()
            return "ok"

        result = fails_twice()

        assert result == "ok"
        assert callback.call_count == 2

        # First retry: attempt=1
        first_call = callback.call_args_list[0]
        assert first_call[0][0] == 1  # attempt number
        assert isinstance(first_call[0][1], RateLimitError)  # exception
        assert isinstance(first_call[0][2], float)  # sleep_time

        # Second retry: attempt=2
        second_call = callback.call_args_list[1]
        assert second_call[0][0] == 2  # attempt number
        assert isinstance(second_call[0][1], RateLimitError)  # exception

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_on_retry_not_called_on_success(self, mock_sleep):
        """on_retry is never called when the function succeeds first try."""
        callback = MagicMock()

        @retry_with_backoff(max_retries=3, on_retry=callback)
        def always_succeeds():
            return "ok"

        always_succeeds()
        callback.assert_not_called()


class TestCustomRetryableCategories:
    """Test custom retryable category sets."""

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_only_specified_categories_retried(self, mock_sleep):
        """When custom categories are set, only those trigger retries."""
        call_count = 0

        # Only retry NETWORK, not RATE_LIMIT
        @retry_with_backoff(
            max_retries=3,
            retryable_categories={ErrorCategory.NETWORK},
        )
        def rate_limited():
            nonlocal call_count
            call_count += 1
            raise RateLimitError()

        try:
            rate_limited()
        except RateLimitError:
            pass

        # Should raise immediately without retry since RATE_LIMIT is not in custom set
        assert call_count == 1
        mock_sleep.assert_not_called()

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_unknown_errors_not_retried_by_default(self, mock_sleep):
        """Unknown errors are not retried with default categories."""
        call_count = 0

        @retry_with_backoff(max_retries=3)
        def unknown_failure():
            nonlocal call_count
            call_count += 1
            raise UnknownError()

        try:
            unknown_failure()
        except UnknownError:
            pass

        assert call_count == 1
        mock_sleep.assert_not_called()


class TestRetryPreservesFunctionMetadata:
    """Test that functools.wraps preserves decorated function metadata."""

    def test_preserves_function_name(self):
        """Decorated function retains its original __name__."""

        @retry_with_backoff()
        def my_function():
            """My docstring."""
            return 42

        assert my_function.__name__ == "my_function"

    def test_preserves_docstring(self):
        """Decorated function retains its original __doc__."""

        @retry_with_backoff()
        def my_function():
            """My docstring."""
            return 42

        assert my_function.__doc__ == "My docstring."


class TestThreadLocalCallback:
    """Tests for thread-local rate-limit callback injection."""

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_thread_local_callback_called_on_retry(self, mock_sleep):
        """Thread-local callback is called on each retry with correct args."""
        callback = MagicMock()
        set_rate_limit_callback(callback)
        try:
            call_count = 0

            @retry_with_backoff(max_retries=3, base_delay=1.0)
            def fails_once():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RateLimitError()
                return "ok"

            result = fails_once()

            assert result == "ok"
            assert callback.call_count == 1
            first_call = callback.call_args_list[0]
            assert first_call[0][0] == 1  # attempt number
            assert isinstance(first_call[0][1], RateLimitError)  # exception
            assert isinstance(first_call[0][2], float)  # sleep_time
        finally:
            clear_rate_limit_callback()

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_thread_local_callback_cleared(self, mock_sleep):
        """After clearing, thread-local callback is not called on retry."""
        callback = MagicMock()
        set_rate_limit_callback(callback)
        clear_rate_limit_callback()

        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def fails_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError()
            return "ok"

        result = fails_once()

        assert result == "ok"
        callback.assert_not_called()

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_thread_local_and_static_both_called(self, mock_sleep):
        """Both static on_retry and thread-local callback are called on each retry."""
        static_callback = MagicMock()
        thread_local_callback = MagicMock()
        set_rate_limit_callback(thread_local_callback)
        try:
            call_count = 0

            @retry_with_backoff(max_retries=3, base_delay=1.0, on_retry=static_callback)
            def fails_once():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RateLimitError()
                return "ok"

            fails_once()

            assert static_callback.call_count == 1
            assert thread_local_callback.call_count == 1
        finally:
            clear_rate_limit_callback()

    @patch("cloud_usage.resilience.retry.time.sleep")
    def test_thread_local_isolated_per_thread(self, mock_sleep):
        """Setting a callback in one thread does not affect another thread."""
        import threading

        callback = MagicMock()
        set_rate_limit_callback(callback)
        try:
            other_thread_value = []

            def check_other_thread():
                val = getattr(_retry_context, "on_retry", None)
                other_thread_value.append(val)

            t = threading.Thread(target=check_other_thread)
            t.start()
            t.join()

            # The other thread should not see our callback
            assert other_thread_value[0] is None
        finally:
            clear_rate_limit_callback()
