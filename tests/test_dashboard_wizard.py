"""
Tests for scan wizard, download endpoints, CLI --web flag, and scan lifecycle.

Tests cover wizard auth check, provider selection, scan start/cancel lifecycle,
download path traversal prevention, CLI argument parsing for --web/--port,
saved scan config round-trip, wizard error UX paths, and CLI-vs-dashboard parity.
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
        # Failed providers show "Not connected" without CLI commands
        assert "Not connected" in response.text
        assert "az login" not in response.text

    @patch("cloud_usage.dashboard.routes.scan._run_auth_check")
    def test_auth_check_failed_provider_no_cli_commands(self, mock_check, client) -> None:
        """Failed auth providers show 'Not connected' — no CLI commands are rendered."""
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
        assert "Not connected" in response.text
        # CLI commands must NOT appear — user is directed to the setup wizard instead
        assert "aws sso login" not in response.text

    @patch("cloud_usage.dashboard.routes.scan._run_auth_check")
    def test_auth_check_all_fail_shows_setup_cta(
        self, mock_check, client
    ) -> None:
        """When all providers fail, a friendly setup CTA is shown (no CLI commands).

        The block must NOT contain CLI commands and must show a link to the
        credential setup assistant.  The Next button must be disabled.
        """
        mock_check.return_value = [
            {
                "provider": "aws",
                "success": False,
                "identity": "",
                "account_count": 0,
                "error_message": "Unable to locate credentials",
                "suggestion": None,
            },
            {
                "provider": "azure",
                "success": False,
                "identity": "",
                "account_count": 0,
                "error_message": "No subscription found",
                "suggestion": None,
            },
            {
                "provider": "gcp",
                "success": False,
                "identity": "",
                "account_count": 0,
                "error_message": "Could not load credentials",
                "suggestion": None,
            },
        ]
        response = client.post("/wizard/auth-check")
        assert response.status_code == 200
        # Friendly setup CTA must appear
        assert "No cloud providers connected yet" in response.text
        assert "Connect a cloud provider" in response.text
        assert "/wizard/setup-credentials" in response.text
        # Must NOT show CLI commands
        assert "aws configure" not in response.text
        assert "gcloud auth application-default login" not in response.text
        # Next button must be disabled
        assert 'type="submit" disabled' in response.text

    @patch("cloud_usage.dashboard.routes.scan._run_auth_check")
    def test_setup_cta_uses_hx_get_button_not_href_anchor(
        self, mock_check, client
    ) -> None:
        """The 'Connect a cloud provider' CTA must be a button with hx-get, not an anchor with href="#".

        An <a href="#"> inside a <form> suppresses HTMX navigation in some browsers.
        The correct pattern is <button type="button" hx-get="/wizard/setup-credentials">.
        """
        mock_check.return_value = [
            {
                "provider": "aws",
                "success": False,
                "identity": "",
                "account_count": 0,
                "error_message": "No credentials",
                "suggestion": None,
            },
            {
                "provider": "azure",
                "success": False,
                "identity": "",
                "account_count": 0,
                "error_message": "No credentials",
                "suggestion": None,
            },
            {
                "provider": "gcp",
                "success": False,
                "identity": "",
                "account_count": 0,
                "error_message": "No credentials",
                "suggestion": None,
            },
        ]
        response = client.post("/wizard/auth-check")
        assert response.status_code == 200
        # Must be rendered as an HTMX button — href="#" anchor must NOT appear
        assert 'hx-get="/wizard/setup-credentials"' in response.text
        assert 'href="#"' not in response.text

    @patch("cloud_usage.dashboard.routes.scan._run_auth_check")
    def test_auth_check_partial_success_no_setup_cta(
        self, mock_check, client
    ) -> None:
        """When at least one provider passes, the setup CTA is NOT shown."""
        mock_check.return_value = [
            {
                "provider": "aws",
                "success": True,
                "identity": "test-user",
                "account_count": 1,
                "error_message": None,
                "suggestion": None,
            },
            {
                "provider": "azure",
                "success": False,
                "identity": "",
                "account_count": 0,
                "error_message": "Not authenticated",
                "suggestion": None,
            },
        ]
        response = client.post("/wizard/auth-check")
        assert response.status_code == 200
        # Setup CTA must NOT appear when at least one provider passes
        assert "No cloud providers connected yet" not in response.text
        assert "Connect a cloud provider" not in response.text
        # Next button must NOT be disabled
        assert 'type="submit" disabled' not in response.text


# -- Credential setup assistant tests --


class TestWizardSetupCredentials:
    """Tests for the credential setup assistant (/wizard/setup-credentials)."""

    def test_setup_get_returns_200(self, client) -> None:
        """GET /wizard/setup-credentials returns 200 with the setup form."""
        response = client.get("/wizard/setup-credentials")
        assert response.status_code == 200
        assert "Connect Your Cloud Providers" in response.text
        # All three provider sections must be present
        assert "AWS" in response.text
        assert "Azure" in response.text
        assert "GCP" in response.text
        # Must NOT contain CLI commands
        assert "aws configure" not in response.text
        assert "az login" not in response.text
        assert "gcloud auth" not in response.text

    def test_setup_post_aws_writes_credentials_file(self, client, tmp_path) -> None:
        """POST with AWS fields writes ~/.aws/credentials."""
        fake_home = tmp_path
        with patch("pathlib.Path.home", return_value=fake_home):
            response = client.post(
                "/wizard/setup-credentials",
                data={
                    "clouds": "aws",
                    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
                    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "aws_region": "us-east-1",
                },
            )
        assert response.status_code == 200
        assert "Saved" in response.text
        assert "AWS" in response.text
        # Verify the credentials file was created
        creds_file = fake_home / ".aws" / "credentials"
        assert creds_file.exists()
        content = creds_file.read_text()
        assert "AKIAIOSFODNN7EXAMPLE" in content

    def test_setup_post_azure_sets_env_vars(self, client, tmp_path) -> None:
        """POST with Azure fields writes the env file and shows a Saved banner."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            response = client.post(
                "/wizard/setup-credentials",
                data={
                    "clouds": "azure",
                    "azure_client_id": "test-client-id",
                    "azure_client_secret": "test-secret",
                    "azure_tenant_id": "test-tenant-id",
                },
            )
        assert response.status_code == 200
        assert "Saved" in response.text
        assert "Azure" in response.text
        # Verify the env file was written
        env_file = tmp_path / ".cloud-usage-azure.env"
        assert env_file.exists()
        content = env_file.read_text()
        assert "test-client-id" in content
        assert "test-tenant-id" in content

    def test_setup_post_gcp_invalid_json_shows_error(self, client) -> None:
        """POST with invalid GCP JSON shows an error message."""
        response = client.post(
            "/wizard/setup-credentials",
            data={
                "clouds": "gcp",
                "gcp_service_account_json": "not valid json {{{",
            },
        )
        assert response.status_code == 200
        assert "Could not save credentials" in response.text
        assert "GCP" in response.text

    def test_setup_post_gcp_valid_json_writes_adc(self, client, tmp_path) -> None:
        """POST with valid GCP service account JSON writes the ADC file."""
        import json

        fake_sa = json.dumps(
            {
                "type": "service_account",
                "project_id": "my-project",
                "private_key_id": "key-id",
                "private_key": "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n",
                "client_email": "sa@my-project.iam.gserviceaccount.com",
                "client_id": "123456789",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
        fake_home = tmp_path
        with patch("pathlib.Path.home", return_value=fake_home):
            response = client.post(
                "/wizard/setup-credentials",
                data={
                    "clouds": "gcp",
                    "gcp_service_account_json": fake_sa,
                },
            )
        assert response.status_code == 200
        assert "Saved" in response.text
        adc_path = fake_home / ".config" / "gcloud" / "application_default_credentials.json"
        assert adc_path.exists()

    def test_setup_post_empty_fields_saves_nothing(self, client) -> None:
        """POST with clouds selected but all fields empty saves nothing."""
        response = client.post(
            "/wizard/setup-credentials",
            data={
                "clouds": ["aws", "azure", "gcp"],
                "aws_access_key_id": "",
                "aws_secret_access_key": "",
                "azure_client_id": "",
                "azure_client_secret": "",
                "azure_tenant_id": "",
                "gcp_service_account_json": "",
            },
        )
        assert response.status_code == 200
        # No "Saved" banner when nothing was saved
        assert "Saved:" not in response.text

    def test_setup_page_has_back_to_auth_check_button(self, client) -> None:
        """Setup page has a 'Back to Auth Check' button that links to /wizard/auth-check."""
        response = client.get("/wizard/setup-credentials")
        assert response.status_code == 200
        assert "Back to Auth Check" in response.text
        assert "/wizard/auth-check" in response.text


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
            "aws": {
                "accounts": [
                    {"id": "111111111111", "display_name": "Account 111111111111"},
                    {"id": "222222222222", "display_name": "Account 222222222222"},
                ],
                "error": None,
            },
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


# -- Wizard error UX tests --


class TestWizardErrorUX:
    """Tests for wizard step 3 error display and blocking behavior."""

    @patch("cloud_usage.dashboard.routes.scan._enumerate_accounts")
    def test_wizard_accounts_shows_inline_error_for_failed_provider(
        self, mock_enum, client
    ) -> None:
        """When GCP fails, its inline error is shown but AWS accounts still appear."""
        mock_enum.return_value = {
            "aws": {
                "accounts": [{"id": "111", "display_name": "Acct 111"}],
                "error": None,
            },
            "gcp": {
                "accounts": [],
                "error": "Permission denied: resourcemanager.projects.list",
            },
        }
        response = client.post(
            "/wizard/accounts",
            data={"providers": ["aws", "gcp"]},
        )
        assert response.status_code == 200
        # GCP inline error must appear
        assert "Permission denied" in response.text
        # AWS accounts must still be shown
        assert "111" in response.text

    @patch("cloud_usage.dashboard.routes.scan._enumerate_accounts")
    def test_wizard_accounts_shows_blocking_when_all_fail(
        self, mock_enum, client
    ) -> None:
        """When all providers fail, the blocking message is rendered."""
        mock_enum.return_value = {
            "aws": {
                "accounts": [],
                "error": "NoCredentialsError: Unable to locate credentials",
            },
            "gcp": {
                "accounts": [],
                "error": "DefaultCredentialsError: could not load credentials",
            },
        }
        response = client.post(
            "/wizard/accounts",
            data={"providers": ["aws", "gcp"]},
        )
        assert response.status_code == 200
        # Blocking message must appear when all providers fail
        assert "No providers available" in response.text

    @patch("cloud_usage.dashboard.routes.scan._enumerate_accounts")
    def test_wizard_accounts_working_provider_not_blocked_by_failed(
        self, mock_enum, client
    ) -> None:
        """When AWS succeeds and GCP fails, Next button is NOT disabled."""
        mock_enum.return_value = {
            "aws": {
                "accounts": [
                    {"id": "111111111111", "display_name": "Account 111111111111"},
                    {"id": "222222222222", "display_name": "Account 222222222222"},
                ],
                "error": None,
            },
            "gcp": {
                "accounts": [],
                "error": "Permission denied",
            },
        }
        response = client.post(
            "/wizard/accounts",
            data={"providers": ["aws", "gcp"]},
        )
        assert response.status_code == 200
        # AWS accounts are rendered
        assert "111111111111" in response.text
        assert "222222222222" in response.text
        # The "disabled" attribute must NOT appear on the Next button
        # (submit button is disabled only when all providers fail)
        # Check: the button block does NOT have disabled on submit when AWS succeeds
        assert 'type="submit" disabled' not in response.text
        assert "No providers available" not in response.text

    @patch("cloud_usage.dashboard.routes.scan._enumerate_accounts")
    def test_wizard_filter_accounts_uses_new_return_structure(
        self, mock_enum, client
    ) -> None:
        """GET /wizard/filter-accounts works with the new dict return structure."""
        mock_enum.return_value = {
            "aws": {
                "accounts": [
                    {"id": "111111111111", "display_name": "Account 111111111111"},
                    {"id": "999999999999", "display_name": "Account 999999999999"},
                ],
                "error": None,
            },
        }
        response = client.get("/wizard/filter-accounts?provider=aws&q=111")
        assert response.status_code == 200
        assert "111111111111" in response.text
        # Account 999 does not match the filter
        assert "999999999999" not in response.text


# -- CLI-vs-dashboard parity tests --


class TestCLIDashboardParity:
    """Tests proving dashboard _enumerate_accounts produces identical project ID results
    to what the CLI path would see from the same enumerate_gcp_projects output."""

    def test_dashboard_and_cli_gcp_enumeration_parity(self) -> None:
        """Dashboard extracts the same project_id strings the CLI would receive.

        Mocks enumerate_gcp_projects at the SDK level (not wrapping _enumerate_accounts)
        so the real _enumerate_accounts code path runs. Verifies the resulting IDs
        match the ProjectInfo.project_id values the CLI would also read.
        """
        import cloud_usage.providers.gcp.projects

        from cloud_usage.dashboard.routes.scan import _enumerate_accounts
        from cloud_usage.providers.gcp.projects import ProjectInfo

        # Create ProjectInfo objects — what the CLI would receive from enumerate_gcp_projects
        cli_projects = [
            ProjectInfo(
                project_id="proj-1",
                compute_enabled=True,
                dns_enabled=True,
                sqladmin_enabled=True,
                container_enabled=True,
            ),
            ProjectInfo(
                project_id="proj-2",
                compute_enabled=True,
                dns_enabled=False,
                sqladmin_enabled=True,
                container_enabled=False,
            ),
        ]

        # CLI would use: [p.project_id for p in cli_projects]
        cli_project_ids = [p.project_id for p in cli_projects]

        # Stub google.auth so _enumerate_accounts can call gcp_default()
        mock_google = MagicMock()
        mock_google_auth = MagicMock()
        mock_google_auth.default.return_value = (MagicMock(), "adc-project")
        mock_google.auth = mock_google_auth

        with patch.dict(sys.modules, {
            "google": mock_google,
            "google.auth": mock_google_auth,
        }), patch(
            "cloud_usage.providers.gcp.projects.enumerate_gcp_projects",
            return_value=cli_projects,
        ):
            result = _enumerate_accounts(["gcp"])

        # Extract IDs from dashboard path
        dashboard_ids = [a["id"] for a in result["gcp"]["accounts"]]

        # Dashboard and CLI must produce identical project ID lists
        assert dashboard_ids == cli_project_ids, (
            f"Dashboard IDs {dashboard_ids!r} differ from CLI IDs {cli_project_ids!r}"
        )
        assert dashboard_ids == ["proj-1", "proj-2"]
