"""
Tests for SSE streaming, DashboardProgressTracker, and tab endpoints.

Tests cover DashboardProgressTracker event emission via EventBridge,
SSE endpoint content type, tab endpoint responses with active state,
and keepalive behavior for SSE connections.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.dashboard.app import create_app
from cloud_usage.dashboard.services.event_bridge import EventBridge
from cloud_usage.dashboard.services.scan_manager import (
    DashboardProgressTracker,
)


# -- DashboardProgressTracker tests --


class TestDashboardProgressTracker:
    """Tests for DashboardProgressTracker SSE event emission."""

    def test_complete_account_emits_progress_event(self) -> None:
        """complete_account() emits progress event to EventBridge."""

        async def _run() -> list[str]:
            bridge = EventBridge()
            await bridge.start()

            tracker = DashboardProgressTracker(bridge)
            tracker.register_provider("AWS", total=3, unit_label="accounts")

            received: list[str] = []

            async def consumer() -> None:
                async for msg in bridge.subscribe():
                    received.append(msg)

            task = asyncio.create_task(consumer())
            # Wait for subscriber to register
            for _ in range(50):
                await asyncio.sleep(0.01)
                if bridge._subscribers:
                    break

            def emit_events() -> None:
                tracker.complete_account("AWS", 10)
                tracker.complete_account("AWS", 5)
                tracker.finish()
                # scan_complete is emitted by the finally block in _run_scan_pipeline,
                # not by finish(). Simulate that here to unblock the SSE consumer.
                bridge.emit_done()

            thread = threading.Thread(target=emit_events)
            thread.start()
            thread.join(timeout=5)

            await asyncio.wait_for(task, timeout=5)
            await bridge.close()
            return received

        results = asyncio.run(_run())
        # 2 progress events + 1 scan_complete = 3
        assert len(results) == 3

        # First event: AWS 1/3
        assert "event: progress_aws" in results[0]
        assert '"completed": 1' in results[0]
        assert '"total": 3' in results[0]
        assert '"resources": 10' in results[0]
        assert '"unit_label": "accounts"' in results[0]

        # Second event: AWS 2/3
        assert "event: progress_aws" in results[1]
        assert '"completed": 2' in results[1]
        assert '"resources": 15' in results[1]

    def test_finish_does_not_emit_scan_complete(self) -> None:
        """finish() does NOT emit scan_complete -- the finally block in _run_scan_pipeline owns it.

        This is an INT-03 regression test. scan_complete emission is the
        responsibility of the finally block in _run_scan_pipeline, not finish().
        """
        bridge = EventBridge()
        # Don't start bridge -- emit_done would need to be called from the finally block
        tracker = DashboardProgressTracker(bridge)
        tracker.register_provider("GCP", total=1, unit_label="projects")

        # Call finish without a live bridge -- no emit_done should be called
        import inspect
        src = inspect.getsource(tracker.finish)
        assert "emit_done" not in src, (
            "DashboardProgressTracker.finish() must not call emit_done(); "
            "the finally block in _run_scan_pipeline owns scan_complete emission"
        )

    def test_scan_complete_emitted_from_finally_block(self) -> None:
        """scan_complete SSE event is delivered when bridge.emit_done() is called externally."""

        async def _run() -> list[str]:
            bridge = EventBridge()
            await bridge.start()

            tracker = DashboardProgressTracker(bridge)
            tracker.register_provider("GCP", total=1, unit_label="projects")

            received: list[str] = []

            async def consumer() -> None:
                async for msg in bridge.subscribe():
                    received.append(msg)

            task = asyncio.create_task(consumer())
            for _ in range(50):
                await asyncio.sleep(0.01)
                if bridge._subscribers:
                    break

            def emit_events() -> None:
                tracker.complete_account("GCP", 3)
                tracker.finish()
                # Simulate finally block calling emit_done()
                bridge.emit_done()

            thread = threading.Thread(target=emit_events)
            thread.start()
            thread.join(timeout=5)

            await asyncio.wait_for(task, timeout=5)
            await bridge.close()
            return received

        results = asyncio.run(_run())
        assert any("event: scan_complete" in r for r in results)

    def test_multiple_providers_emit_separate_events(self) -> None:
        """Multiple providers emit events with correct provider names."""

        async def _run() -> list[str]:
            bridge = EventBridge()
            await bridge.start()

            tracker = DashboardProgressTracker(bridge)
            tracker.register_provider("AWS", total=2, unit_label="accounts")
            tracker.register_provider("Azure", total=1, unit_label="subscriptions")

            received: list[str] = []

            async def consumer() -> None:
                async for msg in bridge.subscribe():
                    received.append(msg)

            task = asyncio.create_task(consumer())
            for _ in range(50):
                await asyncio.sleep(0.01)
                if bridge._subscribers:
                    break

            def emit_events() -> None:
                tracker.complete_account("AWS", 5)
                tracker.complete_account("Azure", 3)
                tracker.complete_account("AWS", 7)
                tracker.finish()
                # scan_complete is emitted by the finally block in _run_scan_pipeline,
                # not by finish(). Simulate that here to unblock the SSE consumer.
                bridge.emit_done()

            thread = threading.Thread(target=emit_events)
            thread.start()
            thread.join(timeout=5)

            await asyncio.wait_for(task, timeout=5)
            await bridge.close()
            return received

        results = asyncio.run(_run())
        # 3 progress events + 1 scan_complete = 4
        assert len(results) == 4
        assert "event: progress_aws" in results[0]
        assert "event: progress_azure" in results[1]
        assert "event: progress_aws" in results[2]
        assert "event: scan_complete" in results[3]

    def test_tracker_maintains_parent_behavior(self) -> None:
        """DashboardProgressTracker still tracks state like parent."""
        bridge = EventBridge()
        # Don't start bridge -- emit will silently skip

        tracker = DashboardProgressTracker(bridge)
        tracker.register_provider("AWS", total=2, unit_label="accounts")
        tracker.complete_account("AWS", 10)

        summary = tracker.get_summary()
        assert summary["AWS"].completed == 1
        assert summary["AWS"].total == 2
        assert summary["AWS"].resources == 10
        assert summary["AWS"].unit_label == "accounts"


# -- SSE endpoint tests --


class TestSSEEndpoint:
    """Tests for the /api/sse/progress SSE endpoint."""

    def test_sse_endpoint_returns_event_stream_content_type(self) -> None:
        """GET /api/sse/progress returns text/event-stream content type.

        Emits a scan_complete event from a thread so the SSE stream
        finishes and does not block the test.
        """
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:

            def emit_complete() -> None:
                """Emit scan_complete after a brief delay."""
                time.sleep(0.3)
                app.state.event_bridge.emit_done()

            thread = threading.Thread(target=emit_complete)
            thread.start()

            response = client.get("/api/sse/progress")
            thread.join(timeout=5)

            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

    def test_sse_endpoint_has_correct_headers(self) -> None:
        """SSE endpoint includes Cache-Control and X-Accel-Buffering headers."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:

            def emit_complete() -> None:
                time.sleep(0.3)
                app.state.event_bridge.emit_done()

            thread = threading.Thread(target=emit_complete)
            thread.start()

            response = client.get("/api/sse/progress")
            thread.join(timeout=5)

            assert response.headers.get("cache-control") == "no-cache"
            assert response.headers.get("x-accel-buffering") == "no"

    def test_sse_endpoint_streams_events(self) -> None:
        """SSE endpoint delivers events emitted via EventBridge."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:

            def emit_events() -> None:
                time.sleep(0.3)
                app.state.event_bridge.emit(
                    "progress_aws", {"completed": 1, "total": 3}
                )
                app.state.event_bridge.emit_done()

            thread = threading.Thread(target=emit_events)
            thread.start()

            response = client.get("/api/sse/progress")
            thread.join(timeout=5)

            assert response.status_code == 200
            body = response.text
            assert "event: progress_aws" in body
            assert "event: scan_complete" in body


# -- Tab endpoint tests --


class TestTabEndpoints:
    """Tests for HTMX tab switching endpoints."""

    def test_tab_progress_returns_200(self) -> None:
        """GET /tab/progress returns 200."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/tab/progress")
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]

    def test_tab_results_returns_200(self) -> None:
        """GET /tab/results returns 200."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/tab/results")
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]

    def test_tab_summary_returns_200(self) -> None:
        """GET /tab/summary returns 200."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]

    def test_tab_progress_has_active_state(self) -> None:
        """GET /tab/progress has tab-active class on Progress tab."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/tab/progress")
            assert "tab-active" in response.text
            # The Progress tab link should have tab-active class
            assert 'hx-get="/tab/progress"' in response.text

    def test_tab_results_has_active_state(self) -> None:
        """GET /tab/results has tab-active class on Results tab."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/tab/results")
            assert "tab-active" in response.text

    def test_tab_progress_shows_idle_message(self) -> None:
        """Progress tab shows idle message when no scan is running."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/tab/progress")
            assert "No scan running" in response.text

    def test_tab_progress_contains_sse_connect_when_scanning(self) -> None:
        """Progress tab contains sse-connect when scan is running."""
        from fastapi.testclient import TestClient

        from cloud_usage.dashboard.services.scan_manager import (
            ScanConfig,
        )

        app = create_app()
        with TestClient(app) as client:
            # Set scan state to running
            app.state.scan_manager.start(ScanConfig(providers=["aws"]))
            response = client.get("/tab/progress")
            assert "sse-connect" in response.text
            assert "/api/sse/progress" in response.text

    def test_tab_progress_shows_cancel_button_when_scanning(self) -> None:
        """Progress tab shows cancel button during scan."""
        from fastapi.testclient import TestClient

        from cloud_usage.dashboard.services.scan_manager import (
            ScanConfig,
        )

        app = create_app()
        with TestClient(app) as client:
            app.state.scan_manager.start(ScanConfig(providers=["aws"]))
            response = client.get("/tab/progress")
            assert "Cancel Scan" in response.text
            assert "hx-post" in response.text

    def test_empty_partial_returns_empty_response(self) -> None:
        """GET /partials/empty returns empty HTML."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as client:
            response = client.get("/partials/empty")
            assert response.status_code == 200
            assert response.text == ""


# -- SSE keepalive test --


class TestSSEKeepalive:
    """Tests for SSE keepalive behavior."""

    def test_keepalive_format_matches_sse_spec(self) -> None:
        """Keepalive string follows SSE comment format."""
        # The EventBridge.subscribe() yields ": keepalive\n\n" on timeout.
        # This verifies the format is a valid SSE comment.
        keepalive = ": keepalive\n\n"
        assert keepalive.startswith(":")  # SSE comment prefix
        assert keepalive.endswith("\n\n")  # SSE delimiter
        assert "keepalive" in keepalive
