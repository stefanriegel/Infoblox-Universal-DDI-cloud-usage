"""
Tests for thread-safe progress tracker with stderr counter-line output.

Tests cover provider registration, account completion tracking,
counter-line format, TTY vs non-TTY output modes, thread safety
under concurrent access, finish summary, and custom unit labels.
"""

from __future__ import annotations

import io
import sys
import threading
from pathlib import Path
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.discovery.progress import ProgressTracker, ProviderProgressState


# -- Tests for register_provider --


class TestRegisterProvider:
    """Tests for ProgressTracker.register_provider()."""

    def test_creates_provider_entry_with_correct_total(self) -> None:
        """register_provider creates entry with specified total."""
        tracker = ProgressTracker()
        tracker.register_provider("AWS", 12)

        summary = tracker.get_summary()
        assert "AWS" in summary
        assert summary["AWS"].total == 12
        assert summary["AWS"].completed == 0
        assert summary["AWS"].resources == 0

    def test_creates_provider_with_default_unit_label(self) -> None:
        """register_provider defaults to 'accounts' unit label."""
        tracker = ProgressTracker()
        tracker.register_provider("AWS", 12)

        summary = tracker.get_summary()
        assert summary["AWS"].unit_label == "accounts"

    def test_creates_provider_with_custom_unit_label(self) -> None:
        """register_provider accepts custom unit label."""
        tracker = ProgressTracker()
        tracker.register_provider("Azure", 5, unit_label="subscriptions")

        summary = tracker.get_summary()
        assert summary["Azure"].unit_label == "subscriptions"

    def test_registers_multiple_providers(self) -> None:
        """register_provider can register multiple providers."""
        tracker = ProgressTracker()
        tracker.register_provider("AWS", 12)
        tracker.register_provider("Azure", 5, unit_label="subscriptions")
        tracker.register_provider("GCP", 3, unit_label="projects")

        summary = tracker.get_summary()
        assert len(summary) == 3
        assert summary["AWS"].total == 12
        assert summary["Azure"].total == 5
        assert summary["GCP"].total == 3


# -- Tests for complete_account --


class TestCompleteAccount:
    """Tests for ProgressTracker.complete_account()."""

    def test_increments_completed_and_resources(self) -> None:
        """complete_account increments completed count and resources."""
        tracker = ProgressTracker()
        tracker._is_tty = False  # Avoid TTY behavior in tests
        tracker.register_provider("AWS", 12)

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            tracker.complete_account("AWS", 25)

        summary = tracker.get_summary()
        assert summary["AWS"].completed == 1
        assert summary["AWS"].resources == 25

    def test_accumulates_resources_across_accounts(self) -> None:
        """complete_account accumulates resources across multiple calls."""
        tracker = ProgressTracker()
        tracker._is_tty = False
        tracker.register_provider("AWS", 12)

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            tracker.complete_account("AWS", 25)
            tracker.complete_account("AWS", 30)
            tracker.complete_account("AWS", 15)

        summary = tracker.get_summary()
        assert summary["AWS"].completed == 3
        assert summary["AWS"].resources == 70

    def test_updates_total_resources(self) -> None:
        """complete_account updates the global total resources counter."""
        tracker = ProgressTracker()
        tracker._is_tty = False
        tracker.register_provider("AWS", 12)
        tracker.register_provider("Azure", 5, unit_label="subscriptions")

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            tracker.complete_account("AWS", 25)
            tracker.complete_account("Azure", 10)

        assert tracker._total_resources == 35


# -- Tests for _render counter-line format --


class TestRender:
    """Tests for counter-line format output."""

    def test_produces_correct_counter_line_format(self) -> None:
        """_render produces CONTEXT.md-specified counter-line format."""
        tracker = ProgressTracker()
        tracker._is_tty = False
        tracker.register_provider("AWS", 12)
        tracker.register_provider("Azure", 5, unit_label="subscriptions")

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            tracker.complete_account("AWS", 25)
            tracker.complete_account("AWS", 30)
            tracker.complete_account("Azure", 10)

        output = stderr_capture.getvalue()
        lines = output.strip().split("\n")
        last_line = lines[-1]

        # Verify format: "AWS [2/12 accounts] | Azure [1/5 subscriptions] | 65 resources found so far"
        assert "AWS [2/12 accounts]" in last_line
        assert "Azure [1/5 subscriptions]" in last_line
        assert "65 resources found so far" in last_line

    def test_single_provider_format(self) -> None:
        """_render works correctly with a single provider."""
        tracker = ProgressTracker()
        tracker._is_tty = False
        tracker.register_provider("AWS", 12)

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            tracker.complete_account("AWS", 25)

        output = stderr_capture.getvalue()
        assert "AWS [1/12 accounts] | 25 resources found so far" in output

    def test_custom_unit_labels_in_output(self) -> None:
        """_render uses custom unit labels in counter-line."""
        tracker = ProgressTracker()
        tracker._is_tty = False
        tracker.register_provider("GCP", 3, unit_label="projects")

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            tracker.complete_account("GCP", 40)

        output = stderr_capture.getvalue()
        assert "GCP [1/3 projects]" in output


# -- Tests for TTY vs non-TTY output --


class TestTTYBehavior:
    """Tests for TTY carriage return vs non-TTY newline output."""

    def test_tty_mode_uses_carriage_return(self) -> None:
        """In TTY mode, _render uses carriage return for in-place update."""
        tracker = ProgressTracker()
        tracker._is_tty = True
        tracker.register_provider("AWS", 12)

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            tracker.complete_account("AWS", 25)

        output = stderr_capture.getvalue()
        assert output.startswith("\r")
        assert "\n" not in output

    def test_non_tty_mode_uses_newline(self) -> None:
        """In non-TTY mode, _render uses newline for each update."""
        tracker = ProgressTracker()
        tracker._is_tty = False
        tracker.register_provider("AWS", 12)

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            tracker.complete_account("AWS", 25)

        output = stderr_capture.getvalue()
        assert not output.startswith("\r")
        assert output.endswith("\n")

    def test_tty_detection_via_isatty(self) -> None:
        """ProgressTracker detects TTY mode from sys.stderr.isatty()."""
        mock_stderr = io.StringIO()
        mock_stderr.isatty = lambda: True  # type: ignore[attr-defined]
        with patch("sys.stderr", mock_stderr):
            tracker = ProgressTracker()
        assert tracker._is_tty is True

    def test_non_tty_detection_via_isatty(self) -> None:
        """ProgressTracker detects non-TTY mode from sys.stderr.isatty()."""
        mock_stderr = io.StringIO()
        mock_stderr.isatty = lambda: False  # type: ignore[attr-defined]
        with patch("sys.stderr", mock_stderr):
            tracker = ProgressTracker()
        assert tracker._is_tty is False


# -- Tests for thread safety --


class TestThreadSafety:
    """Tests for concurrent access to ProgressTracker."""

    def test_concurrent_complete_account_counts_correct(self) -> None:
        """10 threads calling complete_account produce correct final counts."""
        tracker = ProgressTracker()
        tracker._is_tty = False
        tracker.register_provider("AWS", 100)

        stderr_capture = io.StringIO()

        def worker(thread_id: int) -> None:
            for i in range(10):
                with patch("sys.stderr", stderr_capture):
                    tracker.complete_account("AWS", 1)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        summary = tracker.get_summary()
        assert summary["AWS"].completed == 100  # 10 threads * 10 calls each
        assert summary["AWS"].resources == 100  # 1 resource per call
        assert tracker._total_resources == 100

    def test_concurrent_multiple_providers(self) -> None:
        """Concurrent updates to different providers produce correct counts."""
        tracker = ProgressTracker()
        tracker._is_tty = False
        tracker.register_provider("AWS", 50)
        tracker.register_provider("Azure", 50, unit_label="subscriptions")

        stderr_capture = io.StringIO()

        def aws_worker() -> None:
            for _ in range(50):
                with patch("sys.stderr", stderr_capture):
                    tracker.complete_account("AWS", 2)

        def azure_worker() -> None:
            for _ in range(50):
                with patch("sys.stderr", stderr_capture):
                    tracker.complete_account("Azure", 3)

        threads = [
            threading.Thread(target=aws_worker),
            threading.Thread(target=azure_worker),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        summary = tracker.get_summary()
        assert summary["AWS"].completed == 50
        assert summary["AWS"].resources == 100  # 50 * 2
        assert summary["Azure"].completed == 50
        assert summary["Azure"].resources == 150  # 50 * 3
        assert tracker._total_resources == 250


# -- Tests for finish --


class TestFinish:
    """Tests for ProgressTracker.finish()."""

    def test_finish_writes_summary(self) -> None:
        """finish() writes final summary with total resources and providers."""
        tracker = ProgressTracker()
        tracker._is_tty = False
        tracker.register_provider("AWS", 12)
        tracker.register_provider("Azure", 5, unit_label="subscriptions")

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            tracker.complete_account("AWS", 25)
            tracker.complete_account("Azure", 10)
            tracker.finish()

        output = stderr_capture.getvalue()
        assert "Scan complete: 35 resources found across 2 providers" in output

    def test_finish_tty_writes_newline_before_summary(self) -> None:
        """finish() writes a newline before summary in TTY mode."""
        tracker = ProgressTracker()
        tracker._is_tty = True
        tracker.register_provider("AWS", 12)

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            tracker.complete_account("AWS", 25)
            tracker.finish()

        output = stderr_capture.getvalue()
        # In TTY mode, should have \r line, then \n, then summary
        assert "\n" in output
        assert "Scan complete:" in output

    def test_finish_no_providers(self) -> None:
        """finish() handles case with no registered providers."""
        tracker = ProgressTracker()
        tracker._is_tty = False

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            tracker.finish()

        output = stderr_capture.getvalue()
        assert "Scan complete: 0 resources found across 0 providers" in output


# -- Tests for get_summary --


class TestGetSummary:
    """Tests for ProgressTracker.get_summary()."""

    def test_returns_copy_of_state(self) -> None:
        """get_summary returns a deep copy, not a reference to internal state."""
        tracker = ProgressTracker()
        tracker.register_provider("AWS", 12)

        summary = tracker.get_summary()
        summary["AWS"].completed = 999  # Modify the copy

        # Original state should be unchanged
        original = tracker.get_summary()
        assert original["AWS"].completed == 0

    def test_returns_all_providers(self) -> None:
        """get_summary returns state for all registered providers."""
        tracker = ProgressTracker()
        tracker.register_provider("AWS", 12)
        tracker.register_provider("Azure", 5, unit_label="subscriptions")
        tracker.register_provider("GCP", 3, unit_label="projects")

        summary = tracker.get_summary()
        assert len(summary) == 3
        assert "AWS" in summary
        assert "Azure" in summary
        assert "GCP" in summary

    def test_returns_empty_dict_when_no_providers(self) -> None:
        """get_summary returns empty dict when no providers registered."""
        tracker = ProgressTracker()
        summary = tracker.get_summary()
        assert summary == {}


# -- Tests for throttle reporting --


class TestReportThrottle:
    """Tests for ProgressTracker.report_throttle()."""

    def test_report_throttle_writes_to_stderr(self) -> None:
        """report_throttle writes throttle message to stderr."""
        tracker = ProgressTracker()
        tracker._is_tty = False

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            tracker.report_throttle("AWS", 3.2)

        output = stderr_capture.getvalue()
        assert "AWS: rate limited, backing off 3.2s" in output

    def test_report_throttle_tty_uses_carriage_return(self) -> None:
        """report_throttle uses carriage return on TTY."""
        tracker = ProgressTracker()
        tracker._is_tty = True

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            tracker.report_throttle("AWS", 1.5)

        output = stderr_capture.getvalue()
        assert output.startswith("\r")
        assert "AWS: rate limited, backing off 1.5s" in output


class TestRecordThrottleEvent:
    """Tests for ProgressTracker.record_throttle_event()."""

    def test_record_throttle_event_tracks_counts(self) -> None:
        """record_throttle_event tracks events and throttle_summary returns correct info."""
        tracker = ProgressTracker()
        tracker.record_throttle_event("AWS", 2.0)
        tracker.record_throttle_event("AWS", 5.1)
        tracker.record_throttle_event("AWS", 3.0)
        tracker.record_throttle_event("AZURE", 1.5)

        summary = tracker.throttle_summary()
        assert summary is not None
        assert "AWS throttled 3 times (max delay 5.1s)" in summary
        assert "AZURE throttled 1 times (max delay 1.5s)" in summary
        assert summary.startswith("Rate limiting: ")

    def test_throttle_summary_returns_none_when_empty(self) -> None:
        """throttle_summary returns None when no throttle events occurred."""
        tracker = ProgressTracker()
        assert tracker.throttle_summary() is None
