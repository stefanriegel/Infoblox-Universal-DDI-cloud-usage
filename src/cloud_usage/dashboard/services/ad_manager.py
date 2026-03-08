"""AD analysis state manager with thread-safe state transitions.

Mirrors NiosScanManager from nios_manager.py for AD analysis lifecycle.
Tracks AD analysis state (idle/running/complete/error), output XLS path,
analysis error, AD-specific resource counts (DNS zones, DHCP scopes,
AD users), DDI/IP counts, token total, and last AdOptions for retry pre-fill.

All state access is protected by a threading lock for safe concurrent
access from both async route handlers and sync background threads.

Independent of cloud ScanManager and NiosScanManager — no shared state (SC-5).
"""

from __future__ import annotations

import threading
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from cloud_usage.providers.ad.options import AdOptions


class AdState(Enum):
    """Possible states for an AD analysis lifecycle."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


class AdScanManager:
    """Thread-safe state manager for Microsoft AD analysis.

    Independent of cloud ScanManager and NiosScanManager — registered
    separately on app.state. Only one AD analysis can run at a time;
    can_start() returns False while state is RUNNING.

    Progress total=0 initially (indeterminate — DC count is unknown at
    pipeline start, unlike NIOS which knows its step count up front).

    Attributes:
        _state: Current analysis state.
        _lock: Threading lock for state protection.
        _last_options: Last submitted AdOptions, used for retry pre-fill.
        _output_path: Path to generated .xlsx output file.
        _error: Error message if state is ERROR.
        _dns_zone_count: DNS zone count from last complete analysis.
        _dhcp_scope_count: DHCP scope count from last complete analysis.
        _user_count: AD user count from last complete analysis.
        _ddi_count: DDI-counted resource count from last complete analysis.
        _ip_count: IP-counted resource count from last complete analysis.
        _token_total: Total token estimate from last complete analysis.
        _current_progress: Latest progress step dict from the pipeline.
    """

    def __init__(self) -> None:
        self._state = AdState.IDLE
        self._lock = threading.Lock()
        self._last_options: Optional["AdOptions"] = None
        self._output_path: Optional[str] = None
        self._error: Optional[str] = None
        self._dns_zone_count: int = 0
        self._dhcp_scope_count: int = 0
        self._user_count: int = 0
        self._ddi_count: int = 0
        self._ip_count: int = 0
        self._token_total: float = 0.0
        self._top_dns_zones: list = []
        self._current_progress: dict = {
            "step": 0,
            "total": 0,      # 0 = indeterminate — DC count unknown at start
            "label": "Starting\u2026",
            "elapsed_seconds": 0.0,
        }

    @property
    def state(self) -> AdState:
        """Current analysis state. Thread-safe read."""
        with self._lock:
            return self._state

    @property
    def output_path(self) -> Optional[str]:
        """Path to the generated .xlsx file. Thread-safe read."""
        with self._lock:
            return self._output_path

    @property
    def error(self) -> Optional[str]:
        """Error message if state is ERROR. Thread-safe read."""
        with self._lock:
            return self._error

    @property
    def current_progress(self) -> dict:
        """Latest progress step dict. Thread-safe read (returns a copy)."""
        with self._lock:
            return dict(self._current_progress)

    @property
    def last_options(self) -> Optional["AdOptions"]:
        """Last submitted AdOptions for retry pre-fill. Thread-safe read."""
        with self._lock:
            return self._last_options

    @property
    def dns_zone_count(self) -> int:
        """DNS zone count from last complete analysis. Thread-safe read."""
        with self._lock:
            return self._dns_zone_count

    @property
    def dhcp_scope_count(self) -> int:
        """DHCP scope count from last complete analysis. Thread-safe read."""
        with self._lock:
            return self._dhcp_scope_count

    @property
    def user_count(self) -> int:
        """AD user count from last complete analysis. Thread-safe read."""
        with self._lock:
            return self._user_count

    @property
    def ddi_count(self) -> int:
        """DDI-counted resource count from last complete analysis. Thread-safe read."""
        with self._lock:
            return self._ddi_count

    @property
    def ip_count(self) -> int:
        """IP-counted resource count from last complete analysis. Thread-safe read."""
        with self._lock:
            return self._ip_count

    @property
    def token_total(self) -> float:
        """Total token estimate from last complete analysis. Thread-safe read."""
        with self._lock:
            return self._token_total

    @property
    def top_dns_zones(self) -> list:
        """Top 5 AD DNS zones by record count. Thread-safe read."""
        with self._lock:
            return list(self._top_dns_zones)

    def can_start(self) -> bool:
        """True when not RUNNING. Thread-safe.

        Returns:
            True if a new analysis can be started.
        """
        with self._lock:
            return self._state != AdState.RUNNING

    def start(self) -> None:
        """Transition to RUNNING. Thread-safe.

        Raises:
            RuntimeError: If already RUNNING.
        """
        with self._lock:
            if self._state == AdState.RUNNING:
                msg = "Cannot start analysis: already running"
                raise RuntimeError(msg)
            self._state = AdState.RUNNING

    def set_progress(
        self,
        step: int,
        total: int,
        label: str,
        elapsed_seconds: float,
    ) -> None:
        """Store the latest pipeline progress step. Thread-safe.

        Called from the background pipeline thread before each
        ad_progress SSE emit. Route handler reads this via
        current_progress property to render the progress display.

        Args:
            step: Current step number (0-based for indeterminate phase).
            total: Total number of steps (0 = indeterminate).
            label: Human-readable step name.
            elapsed_seconds: Seconds elapsed since pipeline start.
        """
        with self._lock:
            self._current_progress = {
                "step": step,
                "total": total,
                "label": label,
                "elapsed_seconds": elapsed_seconds,
            }

    def set_complete(
        self,
        output_path: str,
        resources: list,
        errors: list[str],
        dns_zone_count: int,
        dhcp_scope_count: int,
        user_count: int,
        ddi_count: int,
        ip_count: int,
        token_total: float,
        top_dns_zones: list | None = None,
    ) -> None:
        """Transition to COMPLETE with output path and AD-specific counts. Thread-safe.

        Args:
            output_path: Path to the generated .xlsx file.
            resources: List of CloudResource objects from run_ad_analysis().
            errors: List of error strings from run_ad_analysis().
            dns_zone_count: Number of AD DNS zones discovered.
            dhcp_scope_count: Number of AD DHCP scopes discovered.
            user_count: Number of AD users discovered.
            ddi_count: Number of DDI-counted resources (category=="ddi").
            ip_count: Number of IP-counted resources (category in "ip"/"asset").
            token_total: Total token estimate from calculate_tokens().
            top_dns_zones: Top 5 DNS zones as list of (zone_name, count) tuples. Defaults to None.
        """
        with self._lock:
            self._state = AdState.COMPLETE
            self._output_path = output_path
            self._dns_zone_count = dns_zone_count
            self._dhcp_scope_count = dhcp_scope_count
            self._user_count = user_count
            self._ddi_count = ddi_count
            self._ip_count = ip_count
            self._token_total = token_total
            self._top_dns_zones = top_dns_zones or []

    def set_error(self, error: str) -> None:
        """Transition to ERROR with message. Thread-safe.

        Args:
            error: Human-readable error message.
        """
        with self._lock:
            self._state = AdState.ERROR
            self._error = error

    def set_last_options(self, options: "AdOptions") -> None:
        """Store the last submitted AdOptions for retry pre-fill. Thread-safe.

        Args:
            options: The AdOptions used in the most recent run attempt.
        """
        with self._lock:
            self._last_options = options
