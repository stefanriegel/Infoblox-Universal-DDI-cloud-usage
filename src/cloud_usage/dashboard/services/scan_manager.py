"""Singleton scan state manager with thread-safe state transitions.

Manages the lifecycle of a cloud discovery scan for the dashboard.
Tracks scan state (idle/running/complete/cancelled/error), discovered
resources, errors, output file paths, and scan configuration.

Also provides DashboardProgressTracker, a ProgressTracker subclass
that emits SSE events via EventBridge when accounts complete,
bridging the sync orchestrator to the async SSE stream.

All state access is protected by a threading lock for safe concurrent
access from both async route handlers and sync worker threads.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from cloud_usage.discovery.progress import ProgressTracker

if TYPE_CHECKING:
    from cloud_usage.dashboard.services.event_bridge import EventBridge


class ScanState(Enum):
    """Possible states for a scan lifecycle.

    Transitions:
        IDLE -> RUNNING (start)
        RUNNING -> COMPLETE (success)
        RUNNING -> CANCELLED (user cancel)
        RUNNING -> ERROR (failure)
        COMPLETE -> RUNNING (new scan)
        CANCELLED -> RUNNING (new scan)
        ERROR -> RUNNING (new scan)
    """

    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class ScanConfig:
    """Configuration for a scan run.

    Attributes:
        providers: List of provider names to scan (e.g., ["aws", "azure"]).
        include_accounts: Per-provider include filters.
        exclude_accounts: Per-provider exclude filters.
    """

    providers: list[str] = field(default_factory=list)
    include_accounts: dict[str, list[str] | None] = field(default_factory=dict)
    exclude_accounts: dict[str, list[str] | None] = field(default_factory=dict)


# Default path for persisting last scan config
_CONFIG_PATH = Path("output") / ".last_scan_config.json"


class ScanManager:
    """Singleton managing scan lifecycle for the dashboard.

    Thread-safe: all state access is protected by a threading lock.
    Only one scan can run at a time; can_start() returns False while
    state is RUNNING.

    Attributes:
        _state: Current scan state.
        _lock: Threading lock for state protection.
        _resources: Discovered cloud resources from last/current scan.
        _errors: Errors encountered during last/current scan.
        _output_paths: Paths to generated output files.
        _config: Current scan configuration.
        _last_config_path: Path for persisting scan config.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._state = ScanState.IDLE
        self._lock = threading.Lock()
        self._resources: list = []
        self._errors: list = []
        self._output_paths: dict[str, str] = {}
        self._config: ScanConfig | None = None
        self._last_config_path = config_path or _CONFIG_PATH

    @property
    def state(self) -> ScanState:
        """Current scan state. Thread-safe read."""
        with self._lock:
            return self._state

    @property
    def resources(self) -> list:
        """Discovered resources. Thread-safe read."""
        with self._lock:
            return list(self._resources)

    @property
    def errors(self) -> list:
        """Scan errors. Thread-safe read."""
        with self._lock:
            return list(self._errors)

    @property
    def output_paths(self) -> dict[str, str]:
        """Output file paths. Thread-safe read."""
        with self._lock:
            return dict(self._output_paths)

    @property
    def config(self) -> ScanConfig | None:
        """Current scan configuration. Thread-safe read."""
        with self._lock:
            return self._config

    def can_start(self) -> bool:
        """Check if a new scan can be started.

        Returns True when state is IDLE, COMPLETE, CANCELLED, or ERROR.
        Returns False when a scan is RUNNING.

        Returns:
            True if a new scan can be started.
        """
        with self._lock:
            return self._state in (
                ScanState.IDLE,
                ScanState.COMPLETE,
                ScanState.CANCELLED,
                ScanState.ERROR,
            )

    def start(self, config: ScanConfig) -> None:
        """Start a new scan with the given configuration.

        Clears previous results and transitions to RUNNING state.

        Args:
            config: Scan configuration with providers and filters.

        Raises:
            RuntimeError: If a scan is already running.
        """
        with self._lock:
            if self._state == ScanState.RUNNING:
                msg = "Cannot start scan: already running"
                raise RuntimeError(msg)
            self._state = ScanState.RUNNING
            self._config = config
            self._resources = []
            self._errors = []
            self._output_paths = {}

    def set_resources(self, resources: list) -> None:
        """Set discovered resources. Thread-safe.

        Args:
            resources: List of CloudResource objects.
        """
        with self._lock:
            self._resources = resources

    def set_errors(self, errors: list) -> None:
        """Set scan errors. Thread-safe.

        Args:
            errors: List of error objects.
        """
        with self._lock:
            self._errors = errors

    def set_output_paths(self, paths: dict[str, str]) -> None:
        """Set output file paths. Thread-safe.

        Args:
            paths: Dict mapping file type to file path.
        """
        with self._lock:
            self._output_paths = paths

    def set_state(self, state: ScanState) -> None:
        """Set scan state directly. Thread-safe.

        Args:
            state: New scan state.
        """
        with self._lock:
            self._state = state

    def cancel(self) -> None:
        """Cancel the current scan. Thread-safe.

        Only transitions from RUNNING to CANCELLED.
        """
        with self._lock:
            if self._state == ScanState.RUNNING:
                self._state = ScanState.CANCELLED

    def save_scan_config(self, config: ScanConfig) -> None:
        """Persist scan config to disk for next-session defaults.

        Saves to output/.last_scan_config.json per user constraint
        "save last scan config".

        Args:
            config: Scan configuration to persist.
        """
        os.makedirs(self._last_config_path.parent, exist_ok=True)
        with open(self._last_config_path, "w") as f:
            json.dump(asdict(config), f, indent=2)

    def load_scan_config(self) -> ScanConfig | None:
        """Load previously saved scan config from disk.

        Returns:
            ScanConfig if a saved config exists, None otherwise.
        """
        if not self._last_config_path.is_file():
            return None
        with open(self._last_config_path) as f:
            data = json.load(f)
        return ScanConfig(**data)


class DashboardProgressTracker(ProgressTracker):
    """ProgressTracker subclass that emits SSE events via EventBridge.

    Bridges the synchronous discovery orchestrator to the async SSE
    stream. When complete_account() is called by worker threads, this
    class calls super() to maintain existing behavior (stderr output,
    state tracking) and then emits a progress event via EventBridge
    for real-time dashboard updates.

    Args:
        event_bridge: The EventBridge instance for SSE event delivery.
    """

    def __init__(self, event_bridge: EventBridge) -> None:
        super().__init__()
        self._event_bridge = event_bridge

    def complete_account(self, provider: str, resources_found: int) -> None:
        """Record account completion and emit SSE progress event.

        Calls super() to maintain existing ProgressTracker behavior
        (thread-safe state update, stderr output), then emits a
        progress event to EventBridge with current provider state.

        Args:
            provider: Provider display name (must match register_provider name).
            resources_found: Number of resources discovered in this account.
        """
        super().complete_account(provider, resources_found)
        summary = self.get_summary()
        state = summary.get(provider)
        if state:
            self._event_bridge.emit(f"progress_{provider.lower()}", {
                "completed": state.completed,
                "total": state.total,
                "resources": state.resources,
                "unit_label": state.unit_label,
            })

    def finish(self) -> None:
        """Write completion summary and emit scan_complete SSE event.

        Calls super() to maintain existing finish behavior (stderr
        output), then signals scan completion to all SSE subscribers
        via EventBridge.emit_done().
        """
        super().finish()
        self._event_bridge.emit_done()
