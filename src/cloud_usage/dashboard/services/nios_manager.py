"""NIOS analysis state manager with thread-safe state transitions.

Mirrors ScanManager from scan_manager.py for NIOS Grid analysis lifecycle.
Tracks NIOS analysis state (idle/running/complete/error), uploaded backup
path, original filename, output XLS path, analysis error, and ScenarioSuite
for summary card display in the dashboard.

All state access is protected by a threading lock for safe concurrent
access from both async route handlers and sync background threads.

Independent of cloud ScanManager — no shared state (SC-5).
"""

from __future__ import annotations

import threading
from enum import Enum
from typing import Optional


class NiosState(Enum):
    """Possible states for a NIOS analysis lifecycle."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


class NiosScanManager:
    """Thread-safe state manager for NIOS Grid analysis.

    Independent of cloud ScanManager — registered separately on app.state.
    Only one NIOS analysis can run at a time; can_start() returns False
    while state is RUNNING.

    Attributes:
        _state: Current analysis state.
        _lock: Threading lock for state protection.
        _upload_path: Path to saved .tar.gz backup file.
        _original_filename: Original filename from the upload.
        _output_path: Path to generated .xlsx output file.
        _error: Error message if state is ERROR.
        _scenario_suite: ScenarioSuite from completed analysis (for summary card).
        _current_progress: Latest progress step dict from the pipeline.
    """

    def __init__(self) -> None:
        self._state = NiosState.IDLE
        self._lock = threading.Lock()
        self._upload_path: Optional[str] = None
        self._original_filename: Optional[str] = None
        self._output_path: Optional[str] = None
        self._error: Optional[str] = None
        self._scenario_suite = None
        self._current_progress: dict = {
            "step": 0,
            "total": 6,
            "label": "Starting\u2026",
            "elapsed_seconds": 0.0,
        }

    @property
    def state(self) -> NiosState:
        """Current analysis state. Thread-safe read."""
        with self._lock:
            return self._state

    @property
    def upload_path(self) -> Optional[str]:
        """Path to the saved .tar.gz upload. Thread-safe read."""
        with self._lock:
            return self._upload_path

    @property
    def original_filename(self) -> Optional[str]:
        """Original filename from the upload. Thread-safe read."""
        with self._lock:
            return self._original_filename

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
    def scenario_suite(self):
        """ScenarioSuite from last complete analysis. Thread-safe read."""
        with self._lock:
            return self._scenario_suite

    @property
    def current_progress(self) -> dict:
        """Latest progress step dict. Thread-safe read."""
        with self._lock:
            return dict(self._current_progress)

    def set_upload(self, path: str, filename: str) -> None:
        """Store upload path and original filename. Thread-safe.

        Args:
            path: Path to saved .tar.gz file.
            filename: Original filename from the browser upload.
        """
        with self._lock:
            self._upload_path = path
            self._original_filename = filename

    def reset(self) -> None:
        """Reset analysis state to IDLE. Called on re-upload. Thread-safe.

        Clears output_path, error, scenario_suite, and current_progress.
        Does NOT clear upload_path or original_filename.
        """
        with self._lock:
            self._state = NiosState.IDLE
            self._output_path = None
            self._error = None
            self._scenario_suite = None
            self._current_progress = {
                "step": 0,
                "total": 6,
                "label": "Starting\u2026",
                "elapsed_seconds": 0.0,
            }

    def can_start(self) -> bool:
        """True when not RUNNING. Thread-safe.

        Returns:
            True if a new analysis can be started.
        """
        with self._lock:
            return self._state != NiosState.RUNNING

    def start(self) -> None:
        """Transition to RUNNING. Thread-safe.

        Raises:
            RuntimeError: If already RUNNING.
        """
        with self._lock:
            if self._state == NiosState.RUNNING:
                msg = "Cannot start analysis: already running"
                raise RuntimeError(msg)
            self._state = NiosState.RUNNING

    def set_progress(
        self,
        step: int,
        total: int,
        label: str,
        elapsed_seconds: float,
    ) -> None:
        """Store the latest pipeline progress step. Thread-safe.

        Called from the background pipeline thread before each
        nios_progress SSE emit. Route handler reads this via
        current_progress property to render the progress display.

        Args:
            step: Current step number (1-based).
            total: Total number of steps.
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

    def set_complete(self, output_path: str, scenario_suite=None) -> None:
        """Transition to COMPLETE with output path and ScenarioSuite. Thread-safe.

        Args:
            output_path: Path to the generated .xlsx file.
            scenario_suite: ScenarioSuite from compute_scenarios() for summary card.
        """
        with self._lock:
            self._state = NiosState.COMPLETE
            self._output_path = output_path
            self._scenario_suite = scenario_suite

    def set_error(self, error: str) -> None:
        """Transition to ERROR with message. Thread-safe.

        Args:
            error: Human-readable error message.
        """
        with self._lock:
            self._state = NiosState.ERROR
            self._error = error
