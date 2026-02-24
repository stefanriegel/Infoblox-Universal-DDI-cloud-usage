"""Tests for the discovery orchestrator with provider-scoped semaphores.

Verifies concurrent discovery dispatch, error isolation (DISC-06),
checkpoint integration, progress tracking, and graceful shutdown.
"""

from __future__ import annotations

import signal
import sys
import threading
import time
from unittest import mock

sys.path.insert(0, "src")

from cloud_usage.discovery.orchestrator import (
    DiscoveryOrchestrator,
    _DEFAULT_PROVIDER_CONCURRENCY,
)
from cloud_usage.discovery.progress import ProgressTracker
from cloud_usage.discovery.provider import DiscoveryProvider
from cloud_usage.discovery.shutdown import GracefulShutdown
from cloud_usage.errors.taxonomy import ErrorRecord
from cloud_usage.resilience.checkpoint import (
    CheckpointData,
    CheckpointEngine,
    ProviderProgress,
)
from cloud_usage.resilience.rate_limiter import RateLimiter
from cloud_usage.schema.resource import CloudResource


class MockDiscoveryProvider(DiscoveryProvider):
    """Mock discovery provider for testing.

    Args:
        name: Provider name ("aws", "azure", "gcp").
        accounts: List of account IDs.
        resources_per_account: Number of resources to return per account.
        fail_accounts: Set of account IDs that should raise exceptions.
    """

    def __init__(
        self,
        name: str,
        accounts: list[str],
        resources_per_account: int = 2,
        fail_accounts: set[str] | None = None,
    ) -> None:
        self._name = name
        self._accounts = accounts
        self._resources_per_account = resources_per_account
        self._fail_accounts = fail_accounts or set()

    @property
    def provider_name(self) -> str:
        return self._name

    def list_accounts(self) -> list[str]:
        return self._accounts

    def discover_account(self, account_id: str) -> list[CloudResource]:
        if account_id in self._fail_accounts:
            raise RuntimeError(f"AccessDenied for account {account_id}")
        return [
            CloudResource(
                resource_id=f"{self._name}-{account_id}-{i}",
                resource_type="vm",
                provider=self._name,
                account_id=account_id,
                region="us-east-1",
                name=f"resource-{i}",
            )
            for i in range(self._resources_per_account)
        ]


def _make_orchestrator(
    providers: list[DiscoveryProvider],
    checkpoint_engine: CheckpointEngine | None = None,
    progress_tracker: ProgressTracker | None = None,
    rate_limiter: RateLimiter | None = None,
    max_workers: int = 5,
    provider_concurrency: dict[str, int] | None = None,
) -> DiscoveryOrchestrator:
    """Helper to create an orchestrator with mock dependencies."""
    if checkpoint_engine is None:
        checkpoint_engine = mock.MagicMock(spec=CheckpointEngine)
    if progress_tracker is None:
        progress_tracker = mock.MagicMock(spec=ProgressTracker)
        progress_tracker.throttle_summary.return_value = None
    if rate_limiter is None:
        rate_limiter = mock.MagicMock(spec=RateLimiter)
        rate_limiter.get_delay.return_value = 0.0

    return DiscoveryOrchestrator(
        providers=providers,
        checkpoint_engine=checkpoint_engine,
        progress_tracker=progress_tracker,
        rate_limiter=rate_limiter,
        max_workers=max_workers,
        provider_concurrency=provider_concurrency,
    )


class TestOrchestratorBasicExecution:
    """Tests for basic discovery orchestration."""

    def test_runs_all_work_items_and_collects_resources(self):
        """Orchestrator discovers resources from all accounts of all providers."""
        aws = MockDiscoveryProvider("aws", ["acc1", "acc2"], resources_per_account=3)
        azure = MockDiscoveryProvider("azure", ["sub1"], resources_per_account=2)
        orchestrator = _make_orchestrator([aws, azure])

        resources, errors = orchestrator.run()

        assert len(resources) == 3 * 2 + 2 * 1  # 3 per AWS account * 2 + 2 per Azure * 1
        assert len(errors) == 0
        providers_found = {r.provider for r in resources}
        assert providers_found == {"aws", "azure"}

    def test_returns_empty_for_no_providers(self):
        """Orchestrator returns empty results when no providers registered."""
        orchestrator = _make_orchestrator([])
        resources, errors = orchestrator.run()
        assert resources == []
        assert errors == []

    def test_returns_empty_for_providers_with_no_accounts(self):
        """Orchestrator handles providers with empty account lists."""
        aws = MockDiscoveryProvider("aws", [])
        orchestrator = _make_orchestrator([aws])
        resources, errors = orchestrator.run()
        assert resources == []
        assert errors == []


class TestErrorIsolation:
    """Tests for error isolation (DISC-06)."""

    def test_one_provider_failure_does_not_abort_other_providers(self):
        """DISC-06: Failure in one provider does not prevent other providers from completing."""
        aws = MockDiscoveryProvider("aws", ["acc1", "acc2"], fail_accounts={"acc1", "acc2"})
        azure = MockDiscoveryProvider("azure", ["sub1"], resources_per_account=5)
        orchestrator = _make_orchestrator([aws, azure])

        resources, errors = orchestrator.run()

        # Azure resources should be collected despite AWS failures
        assert len(resources) == 5
        assert all(r.provider == "azure" for r in resources)
        assert len(errors) == 2  # Both AWS accounts failed

    def test_one_account_failure_does_not_abort_other_accounts_in_same_provider(self):
        """DISC-06: Failure in one account does not prevent other accounts in same provider."""
        aws = MockDiscoveryProvider(
            "aws", ["acc1", "acc2", "acc3"],
            resources_per_account=2,
            fail_accounts={"acc2"},
        )
        orchestrator = _make_orchestrator([aws])

        resources, errors = orchestrator.run()

        # acc1 and acc3 should succeed, acc2 should fail
        assert len(resources) == 4  # 2 resources each from acc1 and acc3
        assert len(errors) == 1
        assert errors[0].account_id == "acc2"

    def test_error_record_contains_provider_and_account(self):
        """Error records have correct provider and account information."""
        aws = MockDiscoveryProvider("aws", ["acc1"], fail_accounts={"acc1"})
        orchestrator = _make_orchestrator([aws])

        _, errors = orchestrator.run()

        assert len(errors) == 1
        assert errors[0].provider == "aws"
        assert errors[0].account_id == "acc1"

    def test_all_providers_failing_returns_errors_not_exception(self):
        """When every provider fails, results contain errors instead of raising."""
        aws = MockDiscoveryProvider("aws", ["acc1"], fail_accounts={"acc1"})
        azure = MockDiscoveryProvider("azure", ["sub1"], fail_accounts={"sub1"})
        orchestrator = _make_orchestrator([aws, azure])

        resources, errors = orchestrator.run()

        assert len(resources) == 0
        assert len(errors) == 2


class TestProviderSemaphores:
    """Tests for provider-scoped semaphore concurrency limiting."""

    def test_semaphore_limits_concurrency_per_provider(self):
        """Provider semaphore prevents exceeding max concurrent workers per provider."""
        max_concurrent = 0
        current_concurrent = 0
        lock = threading.Lock()

        class SlowProvider(DiscoveryProvider):
            @property
            def provider_name(self) -> str:
                return "aws"

            def list_accounts(self) -> list[str]:
                return [f"acc{i}" for i in range(10)]

            def discover_account(self, account_id: str) -> list[CloudResource]:
                nonlocal max_concurrent, current_concurrent
                with lock:
                    current_concurrent += 1
                    if current_concurrent > max_concurrent:
                        max_concurrent = current_concurrent
                time.sleep(0.05)
                with lock:
                    current_concurrent -= 1
                return []

        provider = SlowProvider()
        orchestrator = _make_orchestrator(
            [provider],
            max_workers=10,
            provider_concurrency={"aws": 3},
        )

        orchestrator.run()

        # Semaphore should have limited concurrency to 3
        assert max_concurrent <= 3

    def test_default_concurrency_aws_10_azure_4_gcp_8(self):
        """Default concurrency limits match Research recommendations."""
        assert _DEFAULT_PROVIDER_CONCURRENCY["aws"] == 10
        assert _DEFAULT_PROVIDER_CONCURRENCY["azure"] == 4
        assert _DEFAULT_PROVIDER_CONCURRENCY["gcp"] == 8

    def test_custom_concurrency_overrides_defaults(self):
        """Custom provider_concurrency dict overrides default limits."""
        aws = MockDiscoveryProvider("aws", ["acc1"])
        orchestrator = _make_orchestrator(
            [aws],
            provider_concurrency={"aws": 2},
        )
        # Access internal semaphore to verify custom limit
        # Semaphore with value 2 should allow 2 acquires before blocking
        sem = orchestrator._semaphores["aws"]
        # Acquire twice (should succeed)
        assert sem.acquire(blocking=False) is True
        assert sem.acquire(blocking=False) is True
        # Third acquire should fail (non-blocking)
        assert sem.acquire(blocking=False) is False
        # Clean up
        sem.release()
        sem.release()


class TestCheckpointIntegration:
    """Tests for checkpoint saving after each account completes."""

    def test_checkpoint_updated_after_each_account(self):
        """Checkpoint engine.save() called once per completed account."""
        mock_checkpoint = mock.MagicMock(spec=CheckpointEngine)
        aws = MockDiscoveryProvider("aws", ["acc1", "acc2", "acc3"])
        orchestrator = _make_orchestrator([aws], checkpoint_engine=mock_checkpoint)

        orchestrator.run()

        assert mock_checkpoint.save.call_count == 3

    def test_checkpoint_contains_completed_accounts(self):
        """Checkpoint data includes all completed account IDs."""
        saved_checkpoints: list[CheckpointData] = []
        mock_checkpoint = mock.MagicMock(spec=CheckpointEngine)
        mock_checkpoint.save.side_effect = lambda data: saved_checkpoints.append(data)

        aws = MockDiscoveryProvider("aws", ["acc1", "acc2"])
        orchestrator = _make_orchestrator([aws], checkpoint_engine=mock_checkpoint)

        orchestrator.run()

        # Last checkpoint should have both accounts completed
        last_cp = saved_checkpoints[-1]
        assert set(last_cp.providers["aws"].completed_accounts) == {"acc1", "acc2"}

    def test_resumed_checkpoint_skips_already_completed_accounts(self):
        """Resuming from checkpoint does not re-discover completed accounts."""
        discover_calls: list[str] = []
        original_discover = MockDiscoveryProvider.discover_account

        class TrackingProvider(MockDiscoveryProvider):
            def discover_account(self, account_id: str) -> list[CloudResource]:
                discover_calls.append(account_id)
                return original_discover(self, account_id)

        aws = TrackingProvider("aws", ["acc1", "acc2", "acc3"])

        resumed = CheckpointData(
            timestamp="2026-02-23T10:00:00",
            ttl_hours=48,
            providers={
                "aws": ProviderProgress(
                    total_accounts=3,
                    completed_accounts=["acc1"],
                    resources_found=2,
                ),
            },
            scan_id="test_resume",
        )

        orchestrator = _make_orchestrator([aws])
        orchestrator.run(resumed_checkpoint=resumed)

        # Only acc2 and acc3 should be discovered (acc1 skipped)
        assert "acc1" not in discover_calls
        assert set(discover_calls) == {"acc2", "acc3"}


class TestProgressIntegration:
    """Tests for progress tracker integration."""

    def test_progress_complete_account_called_for_each_account(self):
        """progress_tracker.complete_account() called once per account."""
        mock_progress = mock.MagicMock(spec=ProgressTracker)
        aws = MockDiscoveryProvider("aws", ["acc1", "acc2"], resources_per_account=3)
        orchestrator = _make_orchestrator([aws], progress_tracker=mock_progress)

        orchestrator.run()

        # register_provider called once for aws
        mock_progress.register_provider.assert_called_once()
        # complete_account called twice (one per account)
        assert mock_progress.complete_account.call_count == 2
        # finish called once
        mock_progress.finish.assert_called_once()

    def test_progress_register_uses_correct_unit_labels(self):
        """Progress tracker uses 'subscriptions' for Azure, 'projects' for GCP."""
        mock_progress = mock.MagicMock(spec=ProgressTracker)
        azure = MockDiscoveryProvider("azure", ["sub1"])
        gcp = MockDiscoveryProvider("gcp", ["proj1"])
        orchestrator = _make_orchestrator([azure, gcp], progress_tracker=mock_progress)

        orchestrator.run()

        calls = mock_progress.register_provider.call_args_list
        call_args = {c[0][0]: c[0][2] if len(c[0]) > 2 else c[1].get("unit_label", "accounts") for c in calls}
        assert call_args["AZURE"] == "subscriptions"
        assert call_args["GCP"] == "projects"


class TestGracefulShutdown:
    """Tests for the GracefulShutdown handler."""

    def test_update_state_captures_current_scan_state(self):
        """GracefulShutdown.update_state() stores the latest checkpoint data."""
        mock_checkpoint = mock.MagicMock(spec=CheckpointEngine)
        # Avoid registering actual signal handlers in tests
        with mock.patch("signal.signal"):
            handler = GracefulShutdown(mock_checkpoint)

        state = CheckpointData(
            timestamp="2026-02-23T10:00:00",
            ttl_hours=48,
            providers={"aws": ProviderProgress(total_accounts=5, completed_accounts=["acc1"])},
            scan_id="test",
        )
        handler.update_state(state)

        assert handler._scan_state is state

    def test_handler_saves_checkpoint_on_signal(self):
        """Signal handler calls checkpoint_engine.save() with current state."""
        mock_checkpoint = mock.MagicMock(spec=CheckpointEngine)
        with mock.patch("signal.signal"):
            handler = GracefulShutdown(mock_checkpoint)

        state = CheckpointData(
            timestamp="2026-02-23T10:00:00",
            ttl_hours=48,
            providers={"aws": ProviderProgress(total_accounts=5)},
            scan_id="test",
        )
        handler.update_state(state)

        # Simulate signal by calling _handler directly, catch SystemExit
        with mock.patch("sys.stderr.write"):
            try:
                handler._handler(signal.SIGINT, None)
            except SystemExit as e:
                assert e.code == 130

        mock_checkpoint.save.assert_called_once_with(state)

    def test_handler_exits_without_save_when_no_state(self):
        """Signal handler exits cleanly even when no state has been set."""
        mock_checkpoint = mock.MagicMock(spec=CheckpointEngine)
        with mock.patch("signal.signal"):
            handler = GracefulShutdown(mock_checkpoint)

        with mock.patch("sys.stderr.write"):
            try:
                handler._handler(signal.SIGINT, None)
            except SystemExit as e:
                assert e.code == 130

        mock_checkpoint.save.assert_not_called()

    def test_handler_registers_sigint_and_sigterm(self):
        """GracefulShutdown registers handlers for both SIGINT and SIGTERM."""
        mock_checkpoint = mock.MagicMock(spec=CheckpointEngine)
        registered_signals = []

        def track_signal(signum, handler):
            registered_signals.append(signum)

        with mock.patch("signal.signal", side_effect=track_signal):
            GracefulShutdown(mock_checkpoint)

        assert signal.SIGINT in registered_signals
        assert signal.SIGTERM in registered_signals


class TestRateLimiterIntegration:
    """Tests for RateLimiter wiring into the orchestrator."""

    def test_dispatch_applies_rate_limit_delay(self):
        """Orchestrator applies delay from RateLimiter before dispatching workers."""
        rate_limiter = RateLimiter()
        # Pre-load a delay by recording rate limits
        rate_limiter.record_rate_limit("aws")  # Sets delay to 1.0s

        aws = MockDiscoveryProvider("aws", ["acc1"], resources_per_account=1)
        progress = mock.MagicMock(spec=ProgressTracker)
        progress.throttle_summary.return_value = None
        orchestrator = _make_orchestrator(
            [aws],
            rate_limiter=rate_limiter,
            progress_tracker=progress,
        )

        start = time.monotonic()
        with mock.patch("cloud_usage.discovery.orchestrator.time.sleep") as mock_sleep:
            mock_sleep.side_effect = lambda d: None  # Don't actually sleep
            resources, errors = orchestrator.run()

        # get_delay should have been consulted and time.sleep called with the delay
        assert mock_sleep.call_count >= 1
        delay_arg = mock_sleep.call_args_list[0][0][0]
        assert delay_arg > 0  # Should have applied the rate limiter delay

        assert len(resources) == 1
        assert len(errors) == 0

    def test_thread_local_callback_set_during_discovery(self):
        """Thread-local on_retry callback is set inside _discover_account."""
        from cloud_usage.resilience.retry import _retry_context

        callback_was_set = []

        class InspectingProvider(MockDiscoveryProvider):
            def discover_account(self, account_id):
                # Check that the thread-local callback is set
                val = getattr(_retry_context, "on_retry", None)
                callback_was_set.append(val is not None)
                return super().discover_account(account_id)

        aws = InspectingProvider("aws", ["acc1"], resources_per_account=1)
        rate_limiter = RateLimiter()
        progress = ProgressTracker()
        progress._is_tty = False

        orchestrator = _make_orchestrator(
            [aws],
            rate_limiter=rate_limiter,
            progress_tracker=progress,
        )

        orchestrator.run()

        assert len(callback_was_set) == 1
        assert callback_was_set[0] is True

    def test_throttle_callback_records_rate_limit(self):
        """_make_throttle_callback records rate-limit errors with the RateLimiter."""
        rate_limiter = RateLimiter()
        progress = mock.MagicMock(spec=ProgressTracker)

        callback = DiscoveryOrchestrator._make_throttle_callback(
            rate_limiter, "aws", progress
        )

        # Simulate a rate-limit exception (429 keyword triggers RATE_LIMIT category)
        exc = Exception("429 Too Many Requests")
        callback(1, exc, 1.0)

        assert rate_limiter.get_delay("aws") > 0

    def test_throttle_callback_ignores_network_errors(self):
        """_make_throttle_callback does NOT record network errors with RateLimiter."""
        rate_limiter = RateLimiter()
        progress = mock.MagicMock(spec=ProgressTracker)

        callback = DiscoveryOrchestrator._make_throttle_callback(
            rate_limiter, "aws", progress
        )

        # Simulate a network error (ConnectionError contains "connection" keyword)
        exc = ConnectionError("Connection timed out")
        callback(1, exc, 1.0)

        assert rate_limiter.get_delay("aws") == 0.0

    def test_throttle_summary_printed_after_scan(self):
        """Throttle summary is written to stderr after scan when throttle events exist."""
        import io

        aws = MockDiscoveryProvider("aws", ["acc1"], resources_per_account=1)
        rate_limiter = RateLimiter()
        progress = ProgressTracker()
        progress._is_tty = False

        # Pre-load a throttle event
        progress.record_throttle_event("AWS", 2.5)

        orchestrator = _make_orchestrator(
            [aws],
            rate_limiter=rate_limiter,
            progress_tracker=progress,
        )

        stderr_capture = io.StringIO()
        with mock.patch("sys.stderr", stderr_capture):
            orchestrator.run()

        output = stderr_capture.getvalue()
        assert "Rate limiting: AWS throttled 1 times (max delay 2.5s)" in output
