"""Graceful shutdown handler with checkpoint save on SIGINT/SIGTERM.

Captures interrupt signals during discovery scans and saves the current
checkpoint state before exiting. The orchestrator updates the handler's
state after each account completes, so the most recent progress is always
available for checkpoint save.
"""

from __future__ import annotations

import signal
import sys
import threading

from cloud_usage.resilience.checkpoint import CheckpointData, CheckpointEngine


class GracefulShutdown:
    """Signal handler that saves checkpoint on SIGINT/SIGTERM.

    The orchestrator calls update_state() after each account completes,
    keeping the handler's snapshot of scan progress current. If a signal
    is received, the handler saves the latest state to the checkpoint
    engine before exiting.

    Args:
        checkpoint_engine: The checkpoint engine to save state to.
    """

    def __init__(self, checkpoint_engine: CheckpointEngine) -> None:
        """Initialize the shutdown handler and register signal handlers.

        Args:
            checkpoint_engine: Engine used to persist checkpoint on signal.
        """
        self._checkpoint = checkpoint_engine
        self._scan_state: CheckpointData | None = None
        self._lock = threading.Lock()
        signal.signal(signal.SIGINT, self._handler)
        if sys.platform != "win32":
            # SIGTERM is unreliable on Windows — Ctrl+C (SIGINT) is the primary interrupt
            signal.signal(signal.SIGTERM, self._handler)

    def update_state(self, state: CheckpointData) -> None:
        """Update the current scan state snapshot.

        Called by the orchestrator after each account completes so that
        the most recent progress is available if a signal arrives.

        Args:
            state: The current checkpoint data to store.
        """
        with self._lock:
            self._scan_state = state

    def _handler(self, signum: int, frame: object) -> None:
        """Handle SIGINT/SIGTERM by saving checkpoint and exiting.

        Args:
            signum: Signal number received.
            frame: Current stack frame (unused).
        """
        sys.stderr.write("\nInterrupted -- saving checkpoint...\n")
        with self._lock:
            if self._scan_state is not None:
                self._checkpoint.save(self._scan_state)
        sys.stderr.write("Checkpoint saved. Resume with next run.\n")
        sys.exit(130)
