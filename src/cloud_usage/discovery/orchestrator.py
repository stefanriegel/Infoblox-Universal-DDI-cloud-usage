"""Concurrent discovery orchestrator with provider-scoped semaphores.

Dispatches cloud resource discovery work to a ThreadPoolExecutor with
provider-scoped semaphores limiting concurrent account workers per provider.
Integrates checkpoint saving, progress tracking, and error isolation so
that a failure in one worker does not affect others.
"""

from __future__ import annotations

import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime

from cloud_usage.discovery.progress import ProgressTracker
from cloud_usage.discovery.provider import DiscoveryProvider
from cloud_usage.discovery.shutdown import GracefulShutdown
from cloud_usage.errors.taxonomy import ErrorRecord, create_error_record
from cloud_usage.resilience.checkpoint import (
    CheckpointData,
    CheckpointEngine,
    ProviderProgress,
)
from cloud_usage.resilience.rate_limiter import RateLimiter
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)

# Default per-provider concurrency limits per Research analysis.
_DEFAULT_PROVIDER_CONCURRENCY: dict[str, int] = {
    "aws": 10,
    "azure": 4,
    "gcp": 8,
}


class DiscoveryOrchestrator:
    """Concurrent discovery dispatcher with error isolation.

    Dispatches provider.discover_account() calls to a thread pool with
    per-provider semaphores controlling concurrency. Each worker is
    isolated: exceptions in one do not affect others (DISC-06).

    Args:
        providers: List of discovery provider implementations to scan.
        checkpoint_engine: Engine for saving/loading scan progress.
        progress_tracker: Tracker for real-time progress reporting.
        rate_limiter: Adaptive rate limiter for API throttling.
        max_workers: Maximum total concurrent workers across all providers.
        provider_concurrency: Per-provider concurrency limits. Defaults
            to AWS=10, Azure=4, GCP=8 if not specified.
    """

    def __init__(
        self,
        providers: list[DiscoveryProvider],
        checkpoint_engine: CheckpointEngine,
        progress_tracker: ProgressTracker,
        rate_limiter: RateLimiter,
        max_workers: int = 20,
        provider_concurrency: dict[str, int] | None = None,
    ) -> None:
        self._providers = providers
        self._checkpoint = checkpoint_engine
        self._progress = progress_tracker
        self._rate_limiter = rate_limiter
        self._max_workers = max_workers

        concurrency = provider_concurrency or {}
        self._semaphores: dict[str, threading.Semaphore] = {
            p.provider_name: threading.Semaphore(
                concurrency.get(p.provider_name, _DEFAULT_PROVIDER_CONCURRENCY.get(p.provider_name, 10))
            )
            for p in providers
        }

    def _discover_account(
        self,
        provider: DiscoveryProvider,
        account_id: str,
    ) -> tuple[str, str, list[CloudResource], ErrorRecord | None]:
        """Discover resources in a single account with semaphore control.

        Acquires the provider's semaphore before calling discover_account().
        Any exception is caught and converted to an ErrorRecord so that
        failures in one worker do not crash others (DISC-06).

        Args:
            provider: The discovery provider to use.
            account_id: The account/subscription/project to scan.

        Returns:
            Tuple of (provider_name, account_id, resources, error_record).
            error_record is None on success.
        """
        semaphore = self._semaphores[provider.provider_name]
        semaphore.acquire()
        try:
            resources = provider.discover_account(account_id)
            return (provider.provider_name, account_id, resources, None)
        except Exception as exc:
            error_record = create_error_record(provider.provider_name, account_id, exc)
            sys.stderr.write(
                f"WARNING: {provider.provider_name} account {account_id} failed "
                f"({type(exc).__name__}). Continuing with remaining accounts.\n"
            )
            logger.warning(
                "Discovery failed for %s account %s: %s",
                provider.provider_name,
                account_id,
                exc,
            )
            return (provider.provider_name, account_id, [], error_record)
        finally:
            semaphore.release()

    def _build_checkpoint_data(
        self,
        completed: dict[str, list[str]],
        totals: dict[str, int],
        resource_counts: dict[str, int],
        error_records: dict[str, list[dict]],
        scan_id: str,
    ) -> CheckpointData:
        """Build checkpoint data from current scan state.

        Args:
            completed: Mapping of provider name to completed account IDs.
            totals: Mapping of provider name to total account count.
            resource_counts: Mapping of provider name to resource count.
            error_records: Mapping of provider name to serialized error records.
            scan_id: Unique scan identifier.

        Returns:
            CheckpointData representing current scan progress.
        """
        providers: dict[str, ProviderProgress] = {}
        for name in totals:
            providers[name] = ProviderProgress(
                total_accounts=totals[name],
                completed_accounts=list(completed.get(name, [])),
                resources_found=resource_counts.get(name, 0),
                errors=list(error_records.get(name, [])),
            )

        return CheckpointData(
            timestamp=datetime.now().isoformat(),
            ttl_hours=48,
            providers=providers,
            scan_id=scan_id,
        )

    def run(
        self,
        resumed_checkpoint: CheckpointData | None = None,
    ) -> tuple[list[CloudResource], list[ErrorRecord]]:
        """Execute discovery across all providers concurrently.

        Builds work items from each provider's list_accounts(), optionally
        filtering out already-completed accounts from a resumed checkpoint.
        Dispatches work to a thread pool and processes results as they
        complete, updating checkpoint and progress after each account.

        Args:
            resumed_checkpoint: Optional checkpoint data to resume from.
                Already-completed accounts will be skipped.

        Returns:
            Tuple of (all_resources, all_errors) from the scan.
        """
        scan_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        all_resources: list[CloudResource] = []
        all_errors: list[ErrorRecord] = []

        # Build work items and track totals
        work_items: list[tuple[DiscoveryProvider, str]] = []
        totals: dict[str, int] = {}
        completed_accounts: dict[str, list[str]] = {}
        resource_counts: dict[str, int] = {}
        error_records: dict[str, list[dict]] = {}

        # Determine which accounts are already completed from checkpoint
        already_completed: dict[str, set[str]] = {}
        if resumed_checkpoint is not None:
            for name, progress in resumed_checkpoint.providers.items():
                already_completed[name] = set(progress.completed_accounts)
                completed_accounts[name] = list(progress.completed_accounts)
                resource_counts[name] = progress.resources_found
                error_records[name] = list(progress.errors)

        for provider in self._providers:
            name = provider.provider_name
            accounts = provider.list_accounts()
            totals[name] = len(accounts)

            if name not in completed_accounts:
                completed_accounts[name] = []
            if name not in resource_counts:
                resource_counts[name] = 0
            if name not in error_records:
                error_records[name] = []

            # Register provider with progress tracker
            unit_labels = {"azure": "subscriptions", "gcp": "projects"}
            unit_label = unit_labels.get(name, "accounts")
            already_done = len(already_completed.get(name, set()))
            self._progress.register_provider(name.upper(), len(accounts), unit_label)
            # Record already-completed accounts in progress tracker
            for _ in range(already_done):
                self._progress.complete_account(name.upper(), 0)

            # Filter out already-completed accounts
            skip_set = already_completed.get(name, set())
            for account_id in accounts:
                if account_id not in skip_set:
                    work_items.append((provider, account_id))

        # Set up graceful shutdown handler
        shutdown_handler = GracefulShutdown(self._checkpoint)

        # Lock for thread-safe state updates
        state_lock = threading.Lock()

        # Dispatch work to thread pool
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = {
                executor.submit(self._discover_account, provider, account_id): (provider, account_id)
                for provider, account_id in work_items
            }

            for future in as_completed(futures):
                provider_name, account_id, resources, error = future.result()

                with state_lock:
                    if error is None:
                        all_resources.extend(resources)
                        resource_counts[provider_name] = resource_counts.get(provider_name, 0) + len(resources)
                    else:
                        all_errors.append(error)
                        error_records[provider_name].append(asdict(error))

                    completed_accounts.setdefault(provider_name, []).append(account_id)

                    # Update progress tracker
                    self._progress.complete_account(provider_name.upper(), len(resources))

                    # Build and save checkpoint
                    checkpoint_data = self._build_checkpoint_data(
                        completed_accounts, totals, resource_counts, error_records, scan_id
                    )
                    self._checkpoint.save(checkpoint_data)

                    # Update shutdown handler with latest state
                    shutdown_handler.update_state(checkpoint_data)

        # Finish progress display
        self._progress.finish()

        return (all_resources, all_errors)
