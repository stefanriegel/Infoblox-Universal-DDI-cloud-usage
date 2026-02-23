"""Tests for atomic checkpoint engine with TTL expiry."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.resilience.checkpoint import (
    CheckpointData,
    CheckpointEngine,
    ProviderProgress,
    _format_age,
)


def _make_checkpoint_data(
    timestamp: str | None = None,
    ttl_hours: int = 48,
    scan_id: str = "test-scan-001",
) -> CheckpointData:
    """Helper to create sample checkpoint data for tests."""
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    return CheckpointData(
        timestamp=timestamp,
        ttl_hours=ttl_hours,
        providers={
            "aws": ProviderProgress(
                total_accounts=12,
                completed_accounts=["111111111111", "222222222222", "333333333333"],
                resources_found=47,
                errors=[],
            ),
            "azure": ProviderProgress(
                total_accounts=5,
                completed_accounts=[],
                resources_found=0,
                errors=[{"provider": "azure", "account_id": "sub-1", "message": "test error"}],
            ),
        },
        scan_id=scan_id,
    )


class TestSaveCreatesValidJSON:
    """Test that save writes a valid, parseable JSON file."""

    def test_save_creates_file(self, tmp_path):
        """save() should create the checkpoint JSON file."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        data = _make_checkpoint_data()

        engine.save(data)

        filepath = tmp_path / "scan_checkpoint.json"
        assert filepath.exists()

    def test_save_writes_valid_json(self, tmp_path):
        """The saved file should contain valid, parseable JSON."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        data = _make_checkpoint_data()

        engine.save(data)

        filepath = tmp_path / "scan_checkpoint.json"
        raw = json.loads(filepath.read_text(encoding="utf-8"))
        assert "timestamp" in raw
        assert "providers" in raw
        assert "scan_id" in raw
        assert raw["scan_id"] == "test-scan-001"


class TestSaveLoadRoundTrip:
    """Test that save + load preserves all fields."""

    def test_round_trip_preserves_all_fields(self, tmp_path):
        """Saving then loading should reconstruct identical data."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        data = _make_checkpoint_data()

        engine.save(data)
        loaded = engine.load()

        assert loaded is not None
        assert loaded.timestamp == data.timestamp
        assert loaded.ttl_hours == data.ttl_hours
        assert loaded.scan_id == data.scan_id
        assert set(loaded.providers.keys()) == {"aws", "azure"}

        aws = loaded.providers["aws"]
        assert aws.total_accounts == 12
        assert aws.completed_accounts == ["111111111111", "222222222222", "333333333333"]
        assert aws.resources_found == 47
        assert aws.errors == []

        azure = loaded.providers["azure"]
        assert azure.total_accounts == 5
        assert azure.completed_accounts == []
        assert azure.resources_found == 0
        assert len(azure.errors) == 1

    def test_round_trip_with_empty_providers(self, tmp_path):
        """Saving and loading with no providers should work."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        data = CheckpointData(
            timestamp=datetime.now().isoformat(),
            ttl_hours=48,
            providers={},
            scan_id="empty-scan",
        )

        engine.save(data)
        loaded = engine.load()

        assert loaded is not None
        assert loaded.providers == {}
        assert loaded.scan_id == "empty-scan"


class TestAtomicSaveOnException:
    """Test that failed saves don't leave corrupt files."""

    def test_no_corrupt_file_on_write_error(self, tmp_path):
        """If os.write raises, no partial checkpoint should exist."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        data = _make_checkpoint_data()

        with patch("cloud_usage.resilience.checkpoint.os.write", side_effect=OSError("disk full")):
            try:
                engine.save(data)
            except OSError:
                pass

        # The checkpoint file should NOT exist (no partial writes)
        filepath = tmp_path / "scan_checkpoint.json"
        assert not filepath.exists()

    def test_existing_checkpoint_preserved_on_failure(self, tmp_path):
        """If a second save fails, the first checkpoint should still be intact."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        data1 = _make_checkpoint_data(scan_id="first-scan")
        data2 = _make_checkpoint_data(scan_id="second-scan")

        # First save succeeds
        engine.save(data1)

        # Second save fails during write
        with patch("cloud_usage.resilience.checkpoint.os.write", side_effect=OSError("disk full")):
            try:
                engine.save(data2)
            except OSError:
                pass

        # Original checkpoint should still be valid
        loaded = engine.load()
        assert loaded is not None
        assert loaded.scan_id == "first-scan"

    def test_no_temp_files_left_on_failure(self, tmp_path):
        """Failed saves should not leave .tmp files in the checkpoint directory."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        data = _make_checkpoint_data()

        with patch("cloud_usage.resilience.checkpoint.os.write", side_effect=OSError("disk full")):
            try:
                engine.save(data)
            except OSError:
                pass

        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0, f"Temp files left behind: {tmp_files}"


class TestLoadReturnsNoneWhenNoFile:
    """Test that load returns None when no checkpoint exists."""

    def test_returns_none_for_missing_file(self, tmp_path):
        """load() should return None if no checkpoint file exists."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        assert engine.load() is None


class TestLoadReturnsNoneWhenExpired:
    """Test TTL expiry logic."""

    def test_expired_checkpoint_returns_none(self, tmp_path):
        """load() should return None when the checkpoint has exceeded its TTL."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=1)
        # Create data with a timestamp 2 hours ago
        old_time = (datetime.now() - timedelta(hours=2)).isoformat()
        data = _make_checkpoint_data(timestamp=old_time, ttl_hours=1)

        engine.save(data)
        loaded = engine.load()

        assert loaded is None

    def test_non_expired_checkpoint_loads(self, tmp_path):
        """load() should return data when the checkpoint is within TTL."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        data = _make_checkpoint_data()

        engine.save(data)
        loaded = engine.load()

        assert loaded is not None

    def test_ttl_zero_disables_expiry(self, tmp_path):
        """TTL of 0 should disable expiry checks (checkpoint never expires)."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=0)
        old_time = (datetime.now() - timedelta(days=365)).isoformat()
        data = _make_checkpoint_data(timestamp=old_time)

        engine.save(data)
        loaded = engine.load()

        assert loaded is not None


class TestLoadReturnsNoneOnCorruptJSON:
    """Test that corrupt checkpoint files are handled gracefully."""

    def test_invalid_json_returns_none(self, tmp_path):
        """load() should return None for non-JSON content."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        filepath = tmp_path / "scan_checkpoint.json"
        filepath.write_text("this is not json{{{", encoding="utf-8")

        assert engine.load() is None

    def test_missing_keys_returns_none(self, tmp_path):
        """load() should return None when required keys are missing."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        filepath = tmp_path / "scan_checkpoint.json"
        filepath.write_text('{"incomplete": true}', encoding="utf-8")

        assert engine.load() is None

    def test_invalid_timestamp_returns_none(self, tmp_path):
        """load() should return None when timestamp is not valid ISO format."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        filepath = tmp_path / "scan_checkpoint.json"
        filepath.write_text(
            json.dumps({
                "timestamp": "not-a-timestamp",
                "ttl_hours": 48,
                "providers": {},
                "scan_id": "test",
            }),
            encoding="utf-8",
        )

        assert engine.load() is None


class TestDelete:
    """Test checkpoint deletion."""

    def test_delete_removes_file(self, tmp_path):
        """delete() should remove the checkpoint file."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        data = _make_checkpoint_data()
        engine.save(data)

        filepath = tmp_path / "scan_checkpoint.json"
        assert filepath.exists()

        engine.delete()
        assert not filepath.exists()

    def test_delete_no_error_when_missing(self, tmp_path):
        """delete() should not raise when no checkpoint file exists."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        engine.delete()  # Should not raise


class TestFormatResumePrompt:
    """Test human-readable checkpoint summary generation."""

    def test_generates_resume_prompt(self, tmp_path):
        """format_resume_prompt should produce a readable summary string."""
        data = _make_checkpoint_data()
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)

        prompt = engine.format_resume_prompt(data)

        assert "Resume? [Y/n]" in prompt
        assert "aws" in prompt.lower() or "AWS" in prompt

    def test_shows_partial_progress(self, tmp_path):
        """Shows X/Y accounts complete for in-progress providers."""
        data = _make_checkpoint_data()
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)

        prompt = engine.format_resume_prompt(data)

        assert "3/12" in prompt  # AWS has 3 of 12 complete
        assert "not started" in prompt.lower()  # Azure has 0 complete

    def test_shows_complete_provider(self, tmp_path):
        """Shows 'complete' for fully-scanned providers."""
        data = CheckpointData(
            timestamp=datetime.now().isoformat(),
            ttl_hours=48,
            providers={
                "aws": ProviderProgress(
                    total_accounts=3,
                    completed_accounts=["a", "b", "c"],
                    resources_found=100,
                ),
            },
            scan_id="test",
        )
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)

        prompt = engine.format_resume_prompt(data)

        assert "complete" in prompt.lower()
        assert "100 resources" in prompt

    def test_includes_age(self, tmp_path):
        """Prompt should include the checkpoint age."""
        old_time = (datetime.now() - timedelta(hours=2, minutes=30)).isoformat()
        data = _make_checkpoint_data(timestamp=old_time)
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)

        prompt = engine.format_resume_prompt(data)

        # Should say "2h ago" (2.5 hours rounds to 2h)
        assert "2h ago" in prompt


class TestUsesOsReplace:
    """Test that os.replace is used for cross-platform atomicity."""

    def test_uses_os_replace_not_os_rename(self, tmp_path):
        """The save method must use os.replace(), not os.rename()."""
        engine = CheckpointEngine(checkpoint_dir=str(tmp_path), ttl_hours=48)
        data = _make_checkpoint_data()

        with patch("cloud_usage.resilience.checkpoint.os.replace") as mock_replace:
            # We need fsync and write to work normally, only intercept replace
            engine.save(data)

            mock_replace.assert_called_once()
            # The destination should be the checkpoint file path
            dest = mock_replace.call_args[0][1]
            assert dest.endswith("scan_checkpoint.json")


class TestFormatAge:
    """Test the _format_age helper function."""

    def test_just_now(self):
        """Timestamps less than 60 seconds old show 'just now'."""
        ts = datetime.now() - timedelta(seconds=30)
        assert _format_age(ts) == "just now"

    def test_minutes(self):
        """Timestamps in the minutes range show 'Xm ago'."""
        ts = datetime.now() - timedelta(minutes=15)
        assert _format_age(ts) == "15m ago"

    def test_hours(self):
        """Timestamps in the hours range show 'Xh ago'."""
        ts = datetime.now() - timedelta(hours=5)
        assert _format_age(ts) == "5h ago"

    def test_days(self):
        """Timestamps in the days range show 'Xd ago'."""
        ts = datetime.now() - timedelta(days=3)
        assert _format_age(ts) == "3d ago"


class TestCheckpointDirectoryCreation:
    """Test that the checkpoint engine creates its directory."""

    def test_creates_nested_directory(self, tmp_path):
        """Constructor should create the checkpoint directory tree."""
        nested = tmp_path / "deep" / "nested" / "dir"
        engine = CheckpointEngine(checkpoint_dir=str(nested), ttl_hours=48)

        assert nested.exists()
        assert nested.is_dir()
