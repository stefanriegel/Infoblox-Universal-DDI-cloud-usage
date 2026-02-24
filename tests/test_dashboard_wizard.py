"""
Tests for scan wizard, download endpoints, CLI --web flag, and scan lifecycle.

Tests cover wizard auth check, provider selection, scan start/cancel lifecycle,
download path traversal prevention, CLI argument parsing for --web/--port,
and saved scan config round-trip.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.dashboard.app import create_app
from cloud_usage.dashboard.services.scan_manager import (
    ScanConfig,
    ScanManager,
    ScanState,
)


@pytest.fixture
def client():
    """Create a TestClient for the dashboard app."""
    from fastapi.testclient import TestClient

    app = create_app()
    with TestClient(app) as c:
        yield c


# -- Wizard auth check tests --


class TestWizardAuthCheck:
    """Tests for wizard auth check endpoint."""

    def test_wizard_get_returns_200(self, client) -> None:
        """GET /wizard returns 200 with wizard step 1."""
        response = client.get("/wizard")
        assert response.status_code == 200
        assert "Step 1" in response.text or "Auth" in response.text

    @patch("cloud_usage.dashboard.routes.scan._run_auth_check")
    def test_auth_check_returns_200(self, mock_check, client) -> None:
        """POST /wizard/auth-check returns 200 with auth results."""
        mock_check.return_value = [
            {
                "provider": "aws",
                "success": True,
                "identity": "test-user",
                "account_count": 3,
                "error_message": None,
                "suggestion": None,
            },
            {
                "provider": "azure",
                "success": False,
                "identity": "",
                "account_count": 0,
                "error_message": "Not authenticated",
                "suggestion": "Run az login",
            },
            {
                "provider": "gcp",
                "success": True,
                "identity": "gcp-user",
                "account_count": 2,
                "error_message": None,
                "suggestion": None,
            },
        ]
        response = client.post("/wizard/auth-check")
        assert response.status_code == 200
        assert "AWS" in response.text
        assert "Authenticated" in response.text
        assert "Not authenticated" in response.text

    @patch("cloud_usage.dashboard.routes.scan._run_auth_check")
    def test_auth_check_shows_cli_instructions(self, mock_check, client) -> None:
        """Auth check shows CLI instructions for failed providers."""
        mock_check.return_value = [
            {
                "provider": "aws",
                "success": False,
                "identity": "",
                "account_count": 0,
                "error_message": "No credentials",
                "suggestion": "Run aws sso login",
            },
        ]
        response = client.post("/wizard/auth-check")
        assert response.status_code == 200
        assert "aws sso login" in response.text


# -- Wizard provider selection tests --


class TestWizardProviders:
    """Tests for wizard provider selection endpoint."""

    def test_providers_step_returns_200(self, client) -> None:
        """POST /wizard/providers with auth data returns step 2."""
        response = client.post(
            "/wizard/providers",
            data={"auth_aws": "true", "auth_gcp": "true"},
        )
        assert response.status_code == 200
        assert "Step 2" in response.text or "Provider" in response.text


# -- Scan start/cancel lifecycle tests --


class TestScanLifecycle:
    """Tests for scan start and cancel endpoints."""

    def test_scan_start_when_idle_returns_200(self, client) -> None:
        """POST /api/scan/start when idle returns 200."""
        # Mock the scan pipeline to avoid real cloud calls
        with patch("cloud_usage.dashboard.routes.scan._run_scan_pipeline"):
            response = client.post(
                "/api/scan/start",
                data={"providers": "aws"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "started"

    def test_scan_start_when_running_returns_409(self, client) -> None:
        """POST /api/scan/start when already running returns 409."""
        # Start a scan first
        scan_manager = client.app.state.scan_manager
        scan_manager.start(ScanConfig(providers=["aws"]))

        response = client.post(
            "/api/scan/start",
            data={"providers": "azure"},
        )
        assert response.status_code == 409
        assert "already running" in response.json()["error"]

    def test_scan_cancel_when_running(self, client) -> None:
        """POST /api/scan/cancel when running returns 200 and cancels."""
        scan_manager = client.app.state.scan_manager
        scan_manager.start(ScanConfig(providers=["aws"]))

        response = client.post("/api/scan/cancel")
        assert response.status_code == 200
        assert scan_manager.state == ScanState.CANCELLED

    def test_scan_cancel_when_not_running(self, client) -> None:
        """POST /api/scan/cancel when not running returns 200 with not_running."""
        response = client.post("/api/scan/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "not_running"


# -- Download endpoint tests --


class TestDownloadEndpoints:
    """Tests for file download endpoints."""

    def test_download_existing_file(self, client, tmp_path) -> None:
        """GET /download/{filename} serves file content."""
        # Create a temp file in the output directory
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        test_file = output_dir / "test_report.xlsx"
        test_file.write_bytes(b"fake xlsx content")

        try:
            response = client.get("/download/test_report.xlsx")
            assert response.status_code == 200
            assert response.content == b"fake xlsx content"
        finally:
            test_file.unlink(missing_ok=True)

    def test_download_nonexistent_file_returns_404(self, client) -> None:
        """GET /download/{filename} returns 404 for missing files."""
        response = client.get("/download/nonexistent_report.xlsx")
        assert response.status_code == 404

    def test_download_path_traversal_rejected(self, client) -> None:
        """GET /download/../secret.txt returns 400 (path traversal)."""
        response = client.get("/download/..%2Fsecret.txt")
        assert response.status_code in (400, 404)

    def test_download_disallowed_extension_rejected(self, client) -> None:
        """GET /download/script.py returns 400 (disallowed ext)."""
        response = client.get("/download/script.py")
        assert response.status_code == 400

    def test_api_downloads_returns_list(self, client) -> None:
        """GET /api/downloads returns JSON list of available files."""
        # Set some output paths
        scan_manager = client.app.state.scan_manager
        scan_manager.set_output_paths({
            "aws_xlsx": "output/aws_discovery_20260224.xlsx",
            "aws_manifest": "output/aws_proof_20260224.json",
        })

        response = client.get("/api/downloads")
        assert response.status_code == 200
        data = response.json()
        assert "downloads" in data
        assert len(data["downloads"]) == 2
        filenames = [d["filename"] for d in data["downloads"]]
        assert "aws_discovery_20260224.xlsx" in filenames
        assert "aws_proof_20260224.json" in filenames


# -- CLI --web flag tests --


class TestCLIWebFlag:
    """Tests for CLI --web and --port argument parsing."""

    def test_web_flag_recognized(self) -> None:
        """parse_args(['--web']) sets args.web=True."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--web"])
        assert args.web is True

    def test_web_flag_default_false(self) -> None:
        """parse_args([]) sets args.web=False."""
        from cloud_usage.cli import parse_args

        args = parse_args([])
        assert args.web is False

    def test_web_port_default(self) -> None:
        """parse_args(['--web']) sets default port 8080."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--web"])
        assert args.port == 8080

    def test_web_port_custom(self) -> None:
        """parse_args(['--web', '--port', '9090']) sets port 9090."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--web", "--port", "9090"])
        assert args.port == 9090

    @patch("cloud_usage.cli.uvicorn", create=True)
    @patch("cloud_usage.cli.create_app", create=True)
    def test_web_flag_launches_uvicorn(self, mock_create_app, mock_uvicorn) -> None:
        """--web flag calls uvicorn.run with the app."""
        from cloud_usage.cli import main

        mock_app = MagicMock()
        # We need to patch at the right place - inside main's execution
        with patch.dict("sys.modules", {"uvicorn": mock_uvicorn}):
            with patch(
                "cloud_usage.dashboard.app.create_app",
                return_value=mock_app,
            ):
                result = main(["--web"])

        assert result == 0


# -- Saved scan config round-trip tests --


class TestSavedScanConfig:
    """Tests for scan config save/load round-trip."""

    def test_save_and_load_config_round_trip(self, tmp_path) -> None:
        """Save config, load it back, verify match."""
        config_path = tmp_path / ".last_scan_config.json"
        mgr = ScanManager(config_path=config_path)

        config = ScanConfig(
            providers=["aws", "azure"],
            include_accounts={"aws": ["111111111111", "222222222222"]},
            exclude_accounts={"azure": ["sub-001"]},
        )
        mgr.save_scan_config(config)

        loaded = mgr.load_scan_config()
        assert loaded is not None
        assert loaded.providers == ["aws", "azure"]
        assert loaded.include_accounts == {"aws": ["111111111111", "222222222222"]}
        assert loaded.exclude_accounts == {"azure": ["sub-001"]}

    def test_load_config_none_when_missing(self, tmp_path) -> None:
        """load_scan_config returns None when no config file exists."""
        config_path = tmp_path / "nonexistent" / ".last_scan_config.json"
        mgr = ScanManager(config_path=config_path)
        assert mgr.load_scan_config() is None


# -- Wizard account selection tests --


class TestWizardAccounts:
    """Tests for wizard account enumeration and selection."""

    @patch("cloud_usage.dashboard.routes.scan._enumerate_accounts")
    def test_accounts_step_returns_200(self, mock_enum, client) -> None:
        """POST /wizard/accounts returns step 3 with account lists."""
        mock_enum.return_value = {
            "aws": [
                {"id": "111111111111", "display_name": "Account 111111111111"},
                {"id": "222222222222", "display_name": "Account 222222222222"},
            ],
        }
        response = client.post(
            "/wizard/accounts",
            data={"providers": "aws"},
        )
        assert response.status_code == 200
        assert "111111111111" in response.text

    @patch("cloud_usage.dashboard.routes.scan._enumerate_accounts")
    def test_review_step_returns_200(self, mock_enum, client) -> None:
        """POST /wizard/review returns step 4 with config summary."""
        response = client.post(
            "/wizard/review",
            data={
                "selected_providers": "aws",
                "accounts_aws": ["111111111111"],
            },
        )
        assert response.status_code == 200
        assert "Review" in response.text or "Step 4" in response.text


# -- Tab endpoint tests with wizard integration --


class TestTabWithWizard:
    """Tests that tab endpoints work correctly with wizard state."""

    def test_progress_tab_shows_new_scan_button_when_idle(self, client) -> None:
        """Progress tab in idle state shows New Scan button."""
        response = client.get("/tab/progress")
        assert response.status_code == 200
        assert "New Scan" in response.text

    def test_progress_tab_shows_cancel_when_running(self, client) -> None:
        """Progress tab in running state shows cancel button, not New Scan."""
        scan_manager = client.app.state.scan_manager
        scan_manager.start(ScanConfig(providers=["aws"]))
        # Set progress data for rendering
        scan_manager._progress_data = {
            "aws": {
                "provider": "AWS",
                "completed": 0,
                "total": 3,
                "resources": 0,
                "unit_label": "accounts",
                "status": "running",
                "has_errors": False,
            }
        }

        response = client.get("/tab/progress")
        assert response.status_code == 200
        assert "Cancel" in response.text

    def test_summary_tab_shows_download_buttons_after_scan(self, client) -> None:
        """Summary tab shows download links when output paths exist."""
        scan_manager = client.app.state.scan_manager
        scan_manager.set_output_paths({
            "aws_xlsx": "output/aws_discovery_20260224.xlsx",
        })

        response = client.get("/tab/summary")
        assert response.status_code == 200
        assert "aws_discovery_20260224.xlsx" in response.text
