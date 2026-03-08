"""Tests for Phase 37: Cloud Provider Switcher (CLOUD-08, CLOUD-09)."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from cloud_usage.dashboard.app import create_app


# ---------------------------------------------------------------------------
# CLOUD-08: Provider selector UI (4 tests)
# ---------------------------------------------------------------------------


def test_cloud_page_has_provider_selector() -> None:
    """GET /cloud response must contain 'provider-selector' element."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/cloud")
    assert response.status_code == 200
    assert "provider-selector" in response.text


def test_base_html_has_provider_pills() -> None:
    """base.html must contain 'provider-pill' CSS class."""
    content = Path(
        "src/cloud_usage/dashboard/templates/base.html"
    ).read_text()
    assert "provider-pill" in content


def test_css_has_provider_pill_styles() -> None:
    """app.css must define .provider-pill and .provider-pill.active rules."""
    content = Path("src/cloud_usage/dashboard/static/app.css").read_text()
    assert ".provider-pill" in content
    assert ".provider-pill.active" in content


def test_cloud_default_aws_pill_active() -> None:
    """GET /cloud response must contain 'provider-pill' with 'active' highlight."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/cloud")
    assert response.status_code == 200
    assert "provider-pill" in response.text
    assert "active" in response.text


# ---------------------------------------------------------------------------
# CLOUD-09: Per-provider routing, state isolation, scan lifecycle, SSE (10 tests)
# ---------------------------------------------------------------------------


def test_aws_tab_progress_returns_200() -> None:
    """GET /cloud/aws/tab/progress must return 200 with tab-container content."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/cloud/aws/tab/progress")
    assert response.status_code == 200
    assert "tab-container" in response.text


def test_azure_tab_progress_returns_200() -> None:
    """GET /cloud/azure/tab/progress must return 200."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/cloud/azure/tab/progress")
    assert response.status_code == 200


def test_gcp_tab_progress_returns_200() -> None:
    """GET /cloud/gcp/tab/progress must return 200."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/cloud/gcp/tab/progress")
    assert response.status_code == 200


def test_invalid_provider_returns_404() -> None:
    """GET /cloud/invalid/tab/progress must return 404."""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/cloud/invalid/tab/progress")
    assert response.status_code == 404


def test_three_provider_managers_on_app_state() -> None:
    """app.state must have aws_scan_manager, azure_scan_manager, gcp_scan_manager after lifespan."""
    app = create_app()
    with TestClient(app) as client:
        _ = client  # ensure lifespan startup runs
        assert hasattr(app.state, "aws_scan_manager")
        assert hasattr(app.state, "azure_scan_manager")
        assert hasattr(app.state, "gcp_scan_manager")


def test_provider_scan_state_independent() -> None:
    """aws_scan_manager and azure_scan_manager must be distinct objects (not the same instance)."""
    app = create_app()
    with TestClient(app) as client:
        _ = client  # ensure lifespan startup runs
        assert app.state.aws_scan_manager is not app.state.azure_scan_manager


def test_aws_scan_start_route_exists() -> None:
    """POST /api/scan/aws/start must return non-404 (409 or 422 both acceptable)."""
    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/scan/aws/start")
    assert response.status_code != 404


def test_azure_scan_start_route_exists() -> None:
    """POST /api/scan/azure/start must return non-404 (409 or 422 both acceptable)."""
    app = create_app()
    with TestClient(app) as client:
        response = client.post("/api/scan/azure/start")
    assert response.status_code != 404


def test_aws_sse_progress_endpoint_exists() -> None:
    """GET /api/sse/progress/aws must return 200 streaming response."""
    app = create_app()
    with TestClient(app) as client:

        def emit_complete() -> None:
            """Emit scan_complete after a brief delay to close the SSE stream."""
            time.sleep(0.3)
            app.state.aws_event_bridge.emit_done()

        thread = threading.Thread(target=emit_complete)
        thread.start()

        response = client.get("/api/sse/progress/aws")
        thread.join(timeout=5)

    assert response.status_code == 200


def test_cloud_wizard_bypasses_step2_providers() -> None:
    """routes/scan.py must contain '/cloud/aws/wizard' route."""
    content = Path("src/cloud_usage/dashboard/routes/scan.py").read_text()
    assert "/cloud/aws/wizard" in content
