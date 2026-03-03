"""
Tests for the FastAPI dashboard foundation.

Tests cover app creation, page serving, static file serving,
EventBridge sync-to-async round-trip, and ScanManager state
machine with thread-safe transitions and config persistence.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.dashboard.app import create_app
from cloud_usage.dashboard.services.event_bridge import EventBridge
from cloud_usage.dashboard.services.scan_manager import (
    ScanConfig,
    ScanManager,
    ScanState,
)


# -- App factory tests --


class TestAppFactory:
    """Tests for create_app() and basic route serving."""

    def test_create_app_returns_fastapi_instance(self) -> None:
        """create_app() returns a FastAPI instance with correct title."""
        app = create_app()
        assert app.title == "UDDI Estimator"

    def test_index_returns_200_with_title(self) -> None:
        """GET / returns 200 with HTML containing the tool name."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/")
            assert response.status_code == 200
            assert "UDDI Estimator" in response.text
            assert "text/html" in response.headers["content-type"]

    def test_static_app_css_served(self) -> None:
        """GET /static/app.css returns 200."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/static/app.css")
            assert response.status_code == 200
            assert "text/css" in response.headers["content-type"]

    def test_static_htmx_served(self) -> None:
        """GET /static/htmx.min.js returns 200."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/static/htmx.min.js")
            assert response.status_code == 200

    def test_static_pico_css_served(self) -> None:
        """GET /static/pico.min.css returns 200."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/static/pico.min.css")
            assert response.status_code == 200

    def test_static_sse_js_served(self) -> None:
        """GET /static/sse.js returns 200."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/static/sse.js")
            assert response.status_code == 200


# -- EventBridge tests --


class TestEventBridge:
    """Tests for EventBridge sync-to-async bridge."""

    def test_emit_and_subscribe_round_trip(self) -> None:
        """Sync emit() delivers events to async subscribe()."""

        async def _run() -> list[str]:
            bridge = EventBridge()
            await bridge.start()

            received: list[str] = []

            async def consumer() -> None:
                async for msg in bridge.subscribe():
                    received.append(msg)

            task = asyncio.create_task(consumer())
            # Wait for subscriber to register its queue
            for _ in range(50):
                await asyncio.sleep(0.01)
                if bridge._subscribers:
                    break

            # Emit from a thread (simulating sync worker)
            def emit_events() -> None:
                bridge.emit("progress_aws", {"completed": 1, "total": 5})
                bridge.emit("progress_aws", {"completed": 2, "total": 5})
                bridge.emit_done()

            thread = threading.Thread(target=emit_events)
            thread.start()
            thread.join(timeout=5)

            await asyncio.wait_for(task, timeout=5)
            await bridge.close()
            return received

        results = asyncio.run(_run())
        assert len(results) == 3
        assert 'event: progress_aws\ndata: {"completed": 1, "total": 5}\n\n' in results[0]
        assert 'event: progress_aws\ndata: {"completed": 2, "total": 5}\n\n' in results[1]
        assert "event: scan_complete" in results[2]

    def test_subscribe_breaks_on_scan_complete(self) -> None:
        """subscribe() generator exits after scan_complete event."""

        async def _run() -> int:
            bridge = EventBridge()
            await bridge.start()

            count = 0

            async def consumer() -> None:
                nonlocal count
                async for _ in bridge.subscribe():
                    count += 1

            task = asyncio.create_task(consumer())
            # Wait for subscriber to register its queue
            for _ in range(50):
                await asyncio.sleep(0.01)
                if bridge._subscribers:
                    break

            def emit_events() -> None:
                bridge.emit("test_event", {"x": 1})
                bridge.emit_done()
                # Events after done should not be received
                bridge.emit("after_done", {"x": 2})

            thread = threading.Thread(target=emit_events)
            thread.start()
            thread.join(timeout=5)

            await asyncio.wait_for(task, timeout=5)
            await bridge.close()
            return count

        count = asyncio.run(_run())
        # test_event + scan_complete = 2 (after_done should not be received)
        assert count == 2

    def test_emit_before_start_is_safe(self) -> None:
        """Calling emit() before start() does not raise."""
        bridge = EventBridge()
        # Should not raise even though queue is None
        bridge.emit("test", {"data": 1})
        bridge.emit_done()


# -- ScanManager tests --


class TestScanManager:
    """Tests for ScanManager state machine."""

    def test_initial_state_is_idle(self) -> None:
        """ScanManager starts in IDLE state."""
        mgr = ScanManager()
        assert mgr.state == ScanState.IDLE

    def test_can_start_in_idle(self) -> None:
        """can_start() returns True when IDLE."""
        mgr = ScanManager()
        assert mgr.can_start() is True

    def test_cannot_start_when_running(self) -> None:
        """can_start() returns False when RUNNING."""
        mgr = ScanManager()
        config = ScanConfig(providers=["aws"])
        mgr.start(config)
        assert mgr.can_start() is False

    def test_can_start_after_complete(self) -> None:
        """can_start() returns True after scan completes."""
        mgr = ScanManager()
        config = ScanConfig(providers=["aws"])
        mgr.start(config)
        mgr.set_state(ScanState.COMPLETE)
        assert mgr.can_start() is True

    def test_can_start_after_cancelled(self) -> None:
        """can_start() returns True after scan is cancelled."""
        mgr = ScanManager()
        config = ScanConfig(providers=["aws"])
        mgr.start(config)
        mgr.cancel()
        assert mgr.state == ScanState.CANCELLED
        assert mgr.can_start() is True

    def test_can_start_after_error(self) -> None:
        """can_start() returns True after scan errors."""
        mgr = ScanManager()
        config = ScanConfig(providers=["aws"])
        mgr.start(config)
        mgr.set_state(ScanState.ERROR)
        assert mgr.can_start() is True

    def test_full_lifecycle_idle_running_complete(self) -> None:
        """Full lifecycle: IDLE -> RUNNING -> COMPLETE."""
        mgr = ScanManager()
        config = ScanConfig(providers=["aws", "azure"])

        assert mgr.state == ScanState.IDLE
        mgr.start(config)
        assert mgr.state == ScanState.RUNNING
        assert mgr.config == config

        mgr.set_resources(["r1", "r2"])
        mgr.set_errors(["e1"])
        mgr.set_output_paths({"xlsx": "/tmp/out.xlsx"})
        mgr.set_state(ScanState.COMPLETE)

        assert mgr.state == ScanState.COMPLETE
        assert mgr.resources == ["r1", "r2"]
        assert mgr.errors == ["e1"]
        assert mgr.output_paths == {"xlsx": "/tmp/out.xlsx"}

    def test_idle_running_cancelled(self) -> None:
        """Lifecycle: IDLE -> RUNNING -> CANCELLED."""
        mgr = ScanManager()
        mgr.start(ScanConfig(providers=["gcp"]))
        assert mgr.state == ScanState.RUNNING
        mgr.cancel()
        assert mgr.state == ScanState.CANCELLED

    def test_cancel_only_from_running(self) -> None:
        """cancel() only transitions from RUNNING; no-op otherwise."""
        mgr = ScanManager()
        mgr.cancel()  # No-op in IDLE
        assert mgr.state == ScanState.IDLE

    def test_start_raises_if_already_running(self) -> None:
        """start() raises RuntimeError if scan is already running."""
        mgr = ScanManager()
        mgr.start(ScanConfig(providers=["aws"]))
        with pytest.raises(RuntimeError, match="already running"):
            mgr.start(ScanConfig(providers=["azure"]))

    def test_start_clears_previous_results(self) -> None:
        """Starting a new scan clears resources, errors, and output paths."""
        mgr = ScanManager()
        mgr.start(ScanConfig(providers=["aws"]))
        mgr.set_resources(["r1"])
        mgr.set_errors(["e1"])
        mgr.set_output_paths({"xlsx": "/tmp/out.xlsx"})
        mgr.set_state(ScanState.COMPLETE)

        # Start a new scan
        mgr.start(ScanConfig(providers=["azure"]))
        assert mgr.resources == []
        assert mgr.errors == []
        assert mgr.output_paths == {}

    def test_save_and_load_config(self, tmp_path: Path) -> None:
        """save_scan_config() persists and load_scan_config() restores."""
        config_path = tmp_path / ".last_scan_config.json"
        mgr = ScanManager(config_path=config_path)

        config = ScanConfig(
            providers=["aws", "gcp"],
            include_accounts={"aws": ["111111111111"]},
            exclude_accounts={},
        )
        mgr.save_scan_config(config)

        loaded = mgr.load_scan_config()
        assert loaded is not None
        assert loaded.providers == ["aws", "gcp"]
        assert loaded.include_accounts == {"aws": ["111111111111"]}
        assert loaded.exclude_accounts == {}

    def test_load_config_returns_none_when_missing(self, tmp_path: Path) -> None:
        """load_scan_config() returns None when no saved config exists."""
        config_path = tmp_path / "nonexistent" / ".last_scan_config.json"
        mgr = ScanManager(config_path=config_path)
        assert mgr.load_scan_config() is None

    def test_thread_safety(self) -> None:
        """ScanManager handles concurrent state access safely."""
        mgr = ScanManager()
        mgr.start(ScanConfig(providers=["aws"]))
        errors: list[Exception] = []

        def reader() -> None:
            try:
                for _ in range(100):
                    _ = mgr.state
                    _ = mgr.can_start()
                    _ = mgr.resources
            except Exception as exc:
                errors.append(exc)

        def writer() -> None:
            try:
                for i in range(100):
                    mgr.set_resources([f"r{i}"])
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Thread safety errors: {errors}"
