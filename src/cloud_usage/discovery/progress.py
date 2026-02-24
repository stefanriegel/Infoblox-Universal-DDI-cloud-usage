"""
Thread-safe progress tracker with stderr counter-line output.

Provides real-time feedback during cloud resource discovery scans.
Writes a counter-line to stderr showing per-provider progress and
a running total of discovered resources. Uses carriage return on TTY
for in-place updates, newlines on non-TTY for piped output.
"""

from __future__ import annotations

import copy
import sys
import threading
from dataclasses import dataclass, field


@dataclass
class ProviderProgressState:
    """Per-provider progress tracking state.

    Args:
        total: Total accounts/subscriptions/projects for this provider.
        completed: Number completed so far.
        resources: Total resources discovered so far for this provider.
        unit_label: Display label for accounts unit
            ("accounts", "subscriptions", "projects").
    """

    total: int = 0
    completed: int = 0
    resources: int = 0
    unit_label: str = "accounts"


class ProgressTracker:
    """Thread-safe progress tracker writing counter-line to stderr.

    Designed for concurrent use: multiple worker threads can call
    complete_account() simultaneously. All state mutations are
    protected by a threading lock.

    Counter-line format per CONTEXT.md:
        AWS [3/12 accounts] | Azure [1/5 subscriptions] | 127 resources found so far
    """

    def __init__(self) -> None:
        self._providers: dict[str, ProviderProgressState] = {}
        self._lock = threading.Lock()
        self._is_tty: bool = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
        self._total_resources: int = 0
        self._throttle_events: dict[str, list[float]] = {}

    def register_provider(self, name: str, total: int, unit_label: str = "accounts") -> None:
        """Register a provider for progress tracking.

        Args:
            name: Display name for the provider ("AWS", "Azure", "GCP").
            total: Total number of accounts/subscriptions/projects to scan.
            unit_label: Unit label for display
                ("accounts", "subscriptions", "projects").
        """
        with self._lock:
            self._providers[name] = ProviderProgressState(
                total=total, unit_label=unit_label
            )

    def complete_account(self, provider: str, resources_found: int) -> None:
        """Record completion of one account/subscription/project scan.

        Thread-safe: can be called concurrently from multiple worker threads.

        Args:
            provider: Provider display name (must match register_provider name).
            resources_found: Number of resources discovered in this account.
        """
        with self._lock:
            state = self._providers[provider]
            state.completed += 1
            state.resources += resources_found
            self._total_resources += resources_found
            self._render()

    def _render(self) -> None:
        """Build and write counter-line to stderr.

        Called while lock is held. Uses carriage return on TTY for
        in-place updates, newlines on non-TTY for piped output.
        """
        segments: list[str] = []
        for name, state in self._providers.items():
            segments.append(f"{name} [{state.completed}/{state.total} {state.unit_label}]")

        line = " | ".join(segments)
        if segments:
            line += f" | {self._total_resources} resources found so far"

        if self._is_tty:
            sys.stderr.write(f"\r{line}  ")
            sys.stderr.flush()
        else:
            sys.stderr.write(f"{line}\n")

    def report_throttle(self, provider: str, delay: float) -> None:
        """Report a rate-limit delay to stderr.

        Called by the orchestrator when it applies a delay before dispatching
        a worker. Shows provider name and delay duration.

        Args:
            provider: Provider display name (e.g., "AWS").
            delay: Delay in seconds being applied.
        """
        with self._lock:
            msg = f"{provider}: rate limited, backing off {delay:.1f}s"
            if self._is_tty:
                sys.stderr.write(f"\r{msg}  \n")
            else:
                sys.stderr.write(f"{msg}\n")

    def record_throttle_event(self, provider: str, delay: float) -> None:
        """Record a throttle event for summary reporting.

        Thread-safe. Tracks throttle count and delays per provider for
        the post-scan summary.

        Args:
            provider: Provider display name.
            delay: Delay in seconds applied.
        """
        with self._lock:
            if provider not in self._throttle_events:
                self._throttle_events[provider] = []
            self._throttle_events[provider].append(delay)

    def throttle_summary(self) -> str | None:
        """Return a brief throttle summary for post-scan display.

        Returns None if no throttle events occurred. Otherwise returns a
        string like: "Rate limiting: AWS throttled 4 times (max delay 5.1s)"

        Returns:
            Summary string or None if no throttle events.
        """
        with self._lock:
            if not self._throttle_events:
                return None
            parts = []
            for provider, delays in self._throttle_events.items():
                max_delay = max(delays)
                parts.append(f"{provider} throttled {len(delays)} times (max delay {max_delay:.1f}s)")
            return "Rate limiting: " + ", ".join(parts)

    def finish(self) -> None:
        """Write final newline and summary to stderr.

        Clears the carriage-return line on TTY and writes a
        completion summary with total resource count.
        """
        with self._lock:
            provider_count = len(self._providers)
            total = self._total_resources

        if self._is_tty:
            sys.stderr.write("\n")
        sys.stderr.write(
            f"Scan complete: {total} resources found across {provider_count} providers\n"
        )

    def get_summary(self) -> dict[str, ProviderProgressState]:
        """Return a copy of the current provider progress state.

        Thread-safe: returns a deep copy so callers can inspect
        without holding the lock.

        Returns:
            Dict mapping provider name to a copy of its ProviderProgressState.
        """
        with self._lock:
            return copy.deepcopy(self._providers)
