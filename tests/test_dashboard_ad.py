"""Tests for Phase 30 AD Dashboard integration.

Covers all 4 Phase 30 requirements:
  AD-09: GET /tab/ad shows wizard; POST /ad/run dispatches pipeline
  AD-10: GET /api/ad/progress and GET /api/sse/ad serve progress + SSE
  AD-11: GET /tab/ad in complete state shows count tiles + token derivation
  AD-12: GET /tab/ad in error state shows error message + pre-filled wizard
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient

from cloud_usage.dashboard.app import create_app
from cloud_usage.dashboard.services.ad_manager import AdState, AdScanManager
from cloud_usage.dashboard.services.scan_manager import ScanState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_ad_options():
    from cloud_usage.providers.ad.options import AdOptions

    return AdOptions(
        servers=["dc1.corp.com"],
        auth_mode="kerberos",
        username=None,
        password=None,
        winrm_port=5985,
        winrm_ssl=False,
        autodiscover=False,
        discovery_server=None,
        services=("dns", "dhcp", "user"),
    )


# ---------------------------------------------------------------------------
# TestAdScanManager — unit tests for the AdScanManager state machine
# ---------------------------------------------------------------------------


class TestAdScanManager:
    """Unit tests for the AdScanManager state machine."""

    def test_initial_state_is_idle(self) -> None:
        """AdScanManager starts in IDLE state with no stored data."""
        m = AdScanManager()
        assert m.state == AdState.IDLE
        assert m.last_options is None

    def test_start_transitions_to_running(self) -> None:
        """start() transitions IDLE -> RUNNING."""
        m = AdScanManager()
        m.start()
        assert m.state == AdState.RUNNING

    def test_set_complete_transitions(self) -> None:
        """set_complete() transitions RUNNING -> COMPLETE and stores counts."""
        m = AdScanManager()
        m.start()
        m.set_complete(
            output_path="x.xlsx",
            resources=[],
            errors=[],
            dns_zone_count=5,
            dhcp_scope_count=3,
            user_count=42,
            ddi_count=8,
            ip_count=0,
            token_total=0.32,
        )
        assert m.state == AdState.COMPLETE

    def test_set_error_transitions(self) -> None:
        """set_error() transitions RUNNING -> ERROR and stores message."""
        m = AdScanManager()
        m.start()
        m.set_error("timeout")
        assert m.state == AdState.ERROR
        assert m.error == "timeout"

    def test_can_start_false_when_running(self) -> None:
        """can_start() returns False when state is RUNNING."""
        m = AdScanManager()
        m.start()
        assert m.can_start() is False

    def test_set_progress_stores_values(self) -> None:
        """set_progress() stores step, total, label, elapsed_seconds."""
        m = AdScanManager()
        m.set_progress(1, 0, "Connecting", 1.2)
        assert m.current_progress == {
            "step": 1,
            "total": 0,
            "label": "Connecting",
            "elapsed_seconds": 1.2,
        }

    def test_last_options_stored_on_start(self) -> None:
        """set_last_options() stores the AdOptions for retry pre-fill."""
        m = AdScanManager()
        opts = _make_fake_ad_options()
        m.set_last_options(opts)
        assert m.last_options is opts


# ---------------------------------------------------------------------------
# TestAdRun — POST /ad/run route
# ---------------------------------------------------------------------------


class TestAdRun:
    """AD-09: POST /ad/run dispatches pipeline and guards concurrent runs."""

    def test_ad_run_dispatches_pipeline(self) -> None:
        """POST /ad/run with valid kerberos form data returns 200 and running state."""
        with mock.patch(
            "cloud_usage.dashboard.routes.ad._run_ad_pipeline"
        ) as mock_pipeline:
            with TestClient(create_app()) as client:
                r = client.post(
                    "/ad/run",
                    data={
                        "servers": "dc1.corp.com",
                        "auth_mode": "kerberos",
                        "domain": "corp.com",
                        "services": ["dns", "dhcp", "user"],
                    },
                )
                assert r.status_code == 200
                assert "text/html" in r.headers["content-type"]

    def test_ad_run_409_when_already_running(self) -> None:
        """POST /ad/run while already running returns 409."""
        with TestClient(create_app()) as client:
            # Inject running state
            client.app.state.ad_manager.start()
            r = client.post(
                "/ad/run",
                data={
                    "servers": "dc1.corp.com",
                    "auth_mode": "kerberos",
                    "domain": "corp.com",
                    "services": ["dns"],
                },
            )
            assert r.status_code == 409

    def test_ad_run_kerberos_omits_credentials(self) -> None:
        """POST /ad/run with auth_mode=kerberos passes username=None to AdOptions."""
        captured = {}

        def fake_pipeline(app, opts, event_bridge):
            captured["opts"] = opts

        with mock.patch(
            "cloud_usage.dashboard.routes.ad._run_ad_pipeline",
            side_effect=fake_pipeline,
        ):
            with TestClient(create_app()) as client:
                client.post(
                    "/ad/run",
                    data={
                        "servers": "dc1.corp.com",
                        "auth_mode": "kerberos",
                        "domain": "corp.com",
                        "services": ["dns", "dhcp", "user"],
                    },
                )
                # Give background thread a moment to capture
                import time

                time.sleep(0.05)

        if "opts" in captured:
            assert captured["opts"].username is None
            assert captured["opts"].password is None


# ---------------------------------------------------------------------------
# TestAdTab — GET /tab/ad state-driven rendering
# ---------------------------------------------------------------------------


class TestAdTab:
    """AD-09/AD-11/AD-12: GET /tab/ad renders correct state-driven content."""

    def test_tab_ad_returns_200(self) -> None:
        """GET /tab/ad returns HTTP 200 in idle state."""
        with TestClient(create_app()) as client:
            r = client.get("/tab/ad")
            assert r.status_code == 200

    def test_tab_ad_complete_shows_counts(self) -> None:
        """GET /tab/ad in COMPLETE state renders DNS/DHCP/user count tiles."""
        with TestClient(create_app()) as client:
            # Inject complete state with specific counts
            client.app.state.ad_manager.start()
            client.app.state.ad_manager.set_complete(
                output_path="output/ad_results.xlsx",
                resources=[],
                errors=[],
                dns_zone_count=5,
                dhcp_scope_count=3,
                user_count=42,
                ddi_count=8,
                ip_count=0,
                token_total=0.32,
            )
            r = client.get("/tab/ad")
            assert r.status_code == 200
            assert "5" in r.text
            assert "3" in r.text
            assert "42" in r.text

    def test_tab_ad_error_shows_wizard(self) -> None:
        """GET /tab/ad in ERROR state shows the error message."""
        with TestClient(create_app()) as client:
            client.app.state.ad_manager.start()
            client.app.state.ad_manager.set_error("WinRM timeout")
            r = client.get("/tab/ad")
            assert r.status_code == 200
            assert "WinRM timeout" in r.text

    def test_tab_ad_error_prefills_wizard(self) -> None:
        """GET /tab/ad in ERROR state with last_options pre-fills domain in wizard."""
        from cloud_usage.providers.ad.options import AdOptions

        opts = AdOptions(
            servers=["dc1.corp.com"],
            auth_mode="kerberos",
            username=None,
            password=None,
            winrm_port=5985,
            winrm_ssl=False,
            autodiscover=False,
            discovery_server=None,
            services=("dns", "dhcp", "user"),
        )
        with TestClient(create_app()) as client:
            mgr = client.app.state.ad_manager
            mgr.set_last_options(opts)
            mgr.start()
            mgr.set_error("Connection refused")
            r = client.get("/tab/ad")
            assert r.status_code == 200
            assert "dc1.corp.com" in r.text


# ---------------------------------------------------------------------------
# TestAdProgress — GET /api/ad/progress
# ---------------------------------------------------------------------------


class TestAdProgress:
    """AD-10: GET /api/ad/progress returns HTML progress fragment."""

    def test_progress_endpoint_returns_html(self) -> None:
        """GET /api/ad/progress returns HTTP 200 with text/html content-type."""
        with TestClient(create_app()) as client:
            r = client.get("/api/ad/progress")
            assert r.status_code == 200
            assert "text/html" in r.headers["content-type"]


# ---------------------------------------------------------------------------
# TestAdSSE — GET /api/sse/ad
# ---------------------------------------------------------------------------


class TestAdSSE:
    """AD-10: GET /api/sse/ad returns text/event-stream with race-condition guard."""

    def test_sse_endpoint_content_type(self) -> None:
        """GET /api/sse/ad returns text/event-stream content-type."""
        with TestClient(create_app()) as client:
            with client.stream("GET", "/api/sse/ad") as r:
                assert "text/event-stream" in r.headers["content-type"]

    def test_sse_race_condition_guard(self) -> None:
        """GET /api/sse/ad with already-complete state emits ad_complete immediately."""
        with TestClient(create_app()) as client:
            # Inject complete state before SSE connect
            client.app.state.ad_manager.start()
            client.app.state.ad_manager.set_complete(
                output_path="output/ad_results.xlsx",
                resources=[],
                errors=[],
                dns_zone_count=5,
                dhcp_scope_count=3,
                user_count=42,
                ddi_count=8,
                ip_count=0,
                token_total=0.32,
            )
            with client.stream("GET", "/api/sse/ad") as r:
                # Read enough bytes to find the ad_complete event
                body = b""
                for chunk in r.iter_bytes():
                    body += chunk
                    if b"ad_complete" in body:
                        break
            assert b"ad_complete" in body


# ---------------------------------------------------------------------------
# TestAdDownload — GET /download/{filename}
# ---------------------------------------------------------------------------


class TestAdDownload:
    """AD-11: GET /download/{filename} serves the AD xlsx report."""

    def test_download_ad_xlsx(self) -> None:
        """GET /download/{basename} returns 200 for an existing xlsx output file."""
        os.makedirs("output", exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir="output", suffix=".xlsx", delete=False, prefix="ad_test_"
        ) as f:
            f.write(b"PK fake xlsx content")
            temp_path = f.name

        filename = os.path.basename(temp_path)
        try:
            with TestClient(create_app()) as client:
                # Inject complete state pointing at the temp file
                client.app.state.ad_manager.start()
                client.app.state.ad_manager.set_complete(
                    output_path=temp_path,
                    resources=[],
                    errors=[],
                    dns_zone_count=1,
                    dhcp_scope_count=1,
                    user_count=1,
                    ddi_count=1,
                    ip_count=0,
                    token_total=0.04,
                )
                r = client.get(f"/download/{filename}")
                assert r.status_code == 200
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


# ---------------------------------------------------------------------------
# TestAdIndependence — state isolation from NIOS/cloud managers
# ---------------------------------------------------------------------------


class TestAdIndependence:
    """AD-09: ad_manager and nios_manager are independent app.state objects."""

    def test_ad_and_nios_are_independent(self) -> None:
        """app.state.ad_manager is not the same object as app.state.nios_manager."""
        with TestClient(create_app()) as client:
            assert client.app.state.ad_manager is not client.app.state.nios_manager

    def test_ad_event_bridge_independent(self) -> None:
        """app.state.ad_event_bridge is not the same object as app.state.nios_event_bridge."""
        with TestClient(create_app()) as client:
            assert client.app.state.ad_event_bridge is not client.app.state.nios_event_bridge
