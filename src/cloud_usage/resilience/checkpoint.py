"""Atomic checkpoint engine with TTL expiry.

Saves scan progress atomically via temp-file + fsync + os.replace() to ensure
no partial or corrupt checkpoints are possible. Loads checkpoints with
configurable TTL expiry (default 48h). Stores only progress metadata
(completed account IDs, resource counts, errors) -- NOT full resource lists.

Atomic write pattern:
  1. tempfile.mkstemp() in the same directory
  2. os.write() the serialized JSON
  3. os.fsync() to flush to disk
  4. os.close() the file descriptor
  5. os.replace() for atomic move (works on POSIX and Windows)

On any failure, the temp file is cleaned up and the original checkpoint
remains intact.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ProviderProgress:
    """Progress metadata for a single cloud provider.

    Stores only lightweight progress data -- completed account IDs and
    resource counts, NOT full resource lists (per Research recommendation,
    avoids unbounded checkpoint growth).

    Args:
        total_accounts: Total number of accounts/subscriptions/projects to scan.
        completed_accounts: List of account IDs that have been fully scanned.
        resources_found: Count of resources discovered so far (count only, not data).
        errors: List of serialized ErrorRecord dicts for failed accounts.
    """

    total_accounts: int
    completed_accounts: list[str] = field(default_factory=list)
    resources_found: int = 0
    errors: list[dict] = field(default_factory=list)


@dataclass
class CheckpointData:
    """Complete checkpoint state for a scan run.

    Args:
        timestamp: ISO timestamp of when the checkpoint was last saved.
        ttl_hours: TTL in hours for checkpoint expiry (default 48).
        providers: Per-provider progress data keyed by provider name.
        scan_id: Unique identifier for this scan run.
    """

    timestamp: str
    ttl_hours: int
    providers: dict[str, ProviderProgress]
    scan_id: str


class CheckpointEngine:
    """Atomic checkpoint save/load engine with TTL-based expiry.

    Checkpoints are written atomically using a temp-file + fsync + os.replace()
    pattern, ensuring no partial or corrupt checkpoints are possible even if
    the process is interrupted during a save.

    Args:
        checkpoint_dir: Directory for checkpoint files.
            Defaults to "./output/.checkpoints".
        ttl_hours: Hours before a checkpoint expires. Defaults to 48.
    """

    def __init__(self, checkpoint_dir: str = "./output/.checkpoints", ttl_hours: int = 48) -> None:
        """Initialize the checkpoint engine.

        Creates the checkpoint directory if it does not exist.

        Args:
            checkpoint_dir: Path to the directory for checkpoint storage.
            ttl_hours: Time-to-live in hours for checkpoints. Set to 0 to disable TTL.
        """
        self._checkpoint_dir = Path(checkpoint_dir)
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._ttl_hours = ttl_hours
        self._filepath = self._checkpoint_dir / "scan_checkpoint.json"

    def save(self, data: CheckpointData) -> None:
        """Atomically save checkpoint data to disk.

        Uses temp-file + fsync + os.replace() for atomic writes. If any step
        fails, the temp file is cleaned up and the existing checkpoint (if any)
        remains intact.

        Args:
            data: The checkpoint data to persist.

        Raises:
            OSError: If the atomic write fails after cleanup.
        """
        payload = json.dumps(asdict(data), indent=2).encode("utf-8")
        fd = None
        tmp_path = None

        try:
            fd, tmp_path = tempfile.mkstemp(dir=str(self._checkpoint_dir), suffix=".tmp")
            os.write(fd, payload)
            os.fsync(fd)
            os.close(fd)
            fd = None  # Mark as closed so cleanup doesn't double-close
            os.replace(tmp_path, str(self._filepath))
            tmp_path = None  # Mark as moved so cleanup doesn't remove it
        except Exception:
            # Cleanup on failure
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if tmp_path is not None and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    def load(self) -> CheckpointData | None:
        """Load checkpoint if it exists and has not expired.

        Returns None if:
          - No checkpoint file exists
          - The checkpoint has expired (age > TTL)
          - The checkpoint file is corrupt (invalid JSON or missing keys)

        Returns:
            CheckpointData if a valid, non-expired checkpoint exists, else None.
        """
        if not self._filepath.exists():
            return None

        try:
            raw = json.loads(self._filepath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Corrupt checkpoint file, ignoring: %s", exc)
            return None

        try:
            timestamp_str = raw["timestamp"]
            ts = datetime.fromisoformat(timestamp_str)

            # Check TTL expiry (ttl_hours=0 disables TTL check)
            if self._ttl_hours > 0 and datetime.now() - ts > timedelta(hours=self._ttl_hours):
                logger.info(
                    "Stale checkpoint found (%s old, TTL %dh). Starting fresh scan.",
                    _format_age(ts),
                    self._ttl_hours,
                )
                return None

            # Reconstruct dataclasses from dicts
            providers = {}
            for name, pdata in raw["providers"].items():
                providers[name] = ProviderProgress(
                    total_accounts=pdata["total_accounts"],
                    completed_accounts=pdata.get("completed_accounts", []),
                    resources_found=pdata.get("resources_found", 0),
                    errors=pdata.get("errors", []),
                )

            return CheckpointData(
                timestamp=timestamp_str,
                ttl_hours=raw.get("ttl_hours", self._ttl_hours),
                providers=providers,
                scan_id=raw["scan_id"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Checkpoint has invalid structure, ignoring: %s", exc)
            return None

    def delete(self) -> None:
        """Remove the checkpoint file if it exists."""
        if self._filepath.exists():
            self._filepath.unlink()

    def format_resume_prompt(self, data: CheckpointData) -> str:
        """Generate a human-readable resume prompt for a detected checkpoint.

        Produces the auto-detect prompt per CONTEXT.md:
        "Checkpoint from 2h ago: AWS 8/12 accounts complete, Azure not started. Resume? [Y/n]"

        Args:
            data: The loaded checkpoint data to summarize.

        Returns:
            A formatted string summarizing checkpoint state and asking to resume.
        """
        ts = datetime.fromisoformat(data.timestamp)
        age = _format_age(ts)

        parts = []
        for name, progress in data.providers.items():
            completed = len(progress.completed_accounts)
            total = progress.total_accounts
            if completed == 0:
                parts.append(f"{name} not started")
            elif completed >= total:
                parts.append(f"{name} complete ({progress.resources_found} resources)")
            else:
                parts.append(f"{name} {completed}/{total} accounts complete")

        provider_summary = ", ".join(parts) if parts else "no provider data"
        return f"Checkpoint from {age}: {provider_summary}. Resume? [Y/n]"


def _format_age(ts: datetime) -> str:
    """Format the age of a timestamp as a human-readable string.

    Args:
        ts: The timestamp to calculate age from.

    Returns:
        A string like "2h ago", "1d ago", "30m ago", or "just now".
    """
    delta = datetime.now() - ts
    total_seconds = int(delta.total_seconds())

    if total_seconds < 60:
        return "just now"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes}m ago"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours}h ago"
    else:
        days = total_seconds // 86400
        return f"{days}d ago"
