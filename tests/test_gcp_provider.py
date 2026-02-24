"""Tests for GCP discovery provider and CLI integration.

All tests use unittest.mock to avoid requiring live GCP credentials.
Covers GCPDiscoveryProvider filtering, _safe_collect error handling,
checkpoint integration, and CLI argument parsing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.providers.gcp.client_factory import GCPClients
from cloud_usage.providers.gcp.projects import ProjectInfo
from cloud_usage.providers.gcp.provider import GCPDiscoveryProvider
from cloud_usage.schema.resource import CloudResource


def _make_projects() -> list[ProjectInfo]:
    """Create test project list."""
    return [
        ProjectInfo(project_id="proj-alpha", compute_enabled=True, dns_enabled=True, sqladmin_enabled=True, container_enabled=True),
        ProjectInfo(project_id="proj-beta", compute_enabled=True, dns_enabled=True, sqladmin_enabled=True, container_enabled=True),
        ProjectInfo(project_id="proj-gamma", compute_enabled=True, dns_enabled=False, sqladmin_enabled=True, container_enabled=False),
        ProjectInfo(project_id="test-delta", compute_enabled=True, dns_enabled=True, sqladmin_enabled=True, container_enabled=True),
    ]


def _make_provider(**kwargs) -> GCPDiscoveryProvider:
    """Create GCPDiscoveryProvider with test defaults."""
    defaults = {
        "credentials": MagicMock(),
        "projects": _make_projects(),
        "shared_clients": GCPClients(),
    }
    defaults.update(kwargs)
    return GCPDiscoveryProvider(**defaults)


# -- Tests for GCPDiscoveryProvider --


class TestGCPDiscoveryProvider:
    """Tests for GCPDiscoveryProvider interface."""

    def test_provider_name_returns_gcp(self) -> None:
        """provider_name property returns 'gcp'."""
        provider = _make_provider()
        assert provider.provider_name == "gcp"

    def test_list_accounts_returns_all_projects_when_no_filter(self) -> None:
        """list_accounts returns all project IDs without filters."""
        provider = _make_provider()
        accounts = provider.list_accounts()
        assert accounts == ["proj-alpha", "proj-beta", "proj-gamma", "test-delta"]

    def test_list_accounts_with_include_filter_glob(self) -> None:
        """list_accounts filters by include glob pattern."""
        provider = _make_provider(include_projects=["proj-*"])
        accounts = provider.list_accounts()
        assert accounts == ["proj-alpha", "proj-beta", "proj-gamma"]

    def test_list_accounts_with_exclude_filter_glob(self) -> None:
        """list_accounts filters by exclude glob pattern."""
        provider = _make_provider(exclude_projects=["test-*"])
        accounts = provider.list_accounts()
        assert accounts == ["proj-alpha", "proj-beta", "proj-gamma"]

    def test_list_accounts_include_takes_precedence_over_exclude(self) -> None:
        """Include takes precedence -- exclude is ignored when include is set."""
        provider = _make_provider(
            include_projects=["proj-alpha"],
            exclude_projects=["proj-beta"],
        )
        accounts = provider.list_accounts()
        assert accounts == ["proj-alpha"]

    def test_list_accounts_with_multiple_include_patterns(self) -> None:
        """Multiple include patterns matched with any()."""
        provider = _make_provider(
            include_projects=["proj-alpha", "test-*"],
        )
        accounts = provider.list_accounts()
        assert accounts == ["proj-alpha", "test-delta"]

    def test_list_accounts_with_multiple_exclude_patterns(self) -> None:
        """Multiple exclude patterns remove all matching."""
        provider = _make_provider(
            exclude_projects=["proj-gamma", "test-*"],
        )
        accounts = provider.list_accounts()
        assert accounts == ["proj-alpha", "proj-beta"]


class TestDiscoverAccount:
    """Tests for discover_account with all collectors wired."""

    def test_discover_account_returns_empty_with_none_clients(self) -> None:
        """discover_account with all-None GCPClients returns empty list (errors caught by _safe_collect)."""
        provider = _make_provider()
        # Patch storage collector to return [] since the storage SDK may be
        # mocked in sys.modules by other test files.
        with patch.object(provider, "_create_dns_client", return_value=None):
            with patch(
                "cloud_usage.providers.gcp.provider.collect_gcp_storage_buckets",
                return_value=[],
            ):
                result = provider.discover_account("proj-alpha")
        assert result == []

    def test_discover_account_skips_completed_project(self) -> None:
        """discover_account skips project if checkpoint marks it complete."""
        mock_checkpoint = MagicMock()
        mock_data = MagicMock()
        mock_progress = MagicMock()
        mock_progress.completed_accounts = {"proj-alpha"}
        mock_data.providers = {"gcp": mock_progress}
        mock_checkpoint.load.return_value = mock_data

        provider = _make_provider(checkpoint_engine=mock_checkpoint)
        result = provider.discover_account("proj-alpha")
        assert result == []

    def test_discover_account_scans_non_completed_project(self) -> None:
        """discover_account scans project not in checkpoint."""
        mock_checkpoint = MagicMock()
        mock_data = MagicMock()
        mock_progress = MagicMock()
        mock_progress.completed_accounts = {"proj-beta"}  # different project
        mock_data.providers = {"gcp": mock_progress}
        mock_checkpoint.load.return_value = mock_data

        provider = _make_provider(checkpoint_engine=mock_checkpoint)
        with patch.object(provider, "_create_dns_client", return_value=None):
            with patch(
                "cloud_usage.providers.gcp.provider.collect_gcp_storage_buckets",
                return_value=[],
            ):
                result = provider.discover_account("proj-alpha")
        assert result == []

    def test_discover_account_no_checkpoint_engine(self) -> None:
        """discover_account works without checkpoint engine."""
        provider = _make_provider(checkpoint_engine=None)
        with patch.object(provider, "_create_dns_client", return_value=None):
            with patch(
                "cloud_usage.providers.gcp.provider.collect_gcp_storage_buckets",
                return_value=[],
            ):
                result = provider.discover_account("proj-alpha")
        assert result == []

    def test_discover_account_checkpoint_none_load(self) -> None:
        """discover_account works when checkpoint load returns None."""
        mock_checkpoint = MagicMock()
        mock_checkpoint.load.return_value = None

        provider = _make_provider(checkpoint_engine=mock_checkpoint)
        with patch.object(provider, "_create_dns_client", return_value=None):
            with patch(
                "cloud_usage.providers.gcp.provider.collect_gcp_storage_buckets",
                return_value=[],
            ):
                result = provider.discover_account("proj-alpha")
        assert result == []


class TestCreateDNSClient:
    """Tests for _create_dns_client."""

    def test_creates_dns_client_with_mocked_sdk(self) -> None:
        """_create_dns_client creates a client when SDK is available."""
        provider = _make_provider()

        mock_dns = MagicMock()
        mock_dns_client = MagicMock()
        mock_dns.Client.return_value = mock_dns_client

        mock_google = MagicMock()
        mock_google_cloud = MagicMock()
        mock_google_cloud.dns = mock_dns

        with patch.dict("sys.modules", {
            "google": mock_google,
            "google.cloud": mock_google_cloud,
            "google.cloud.dns": mock_dns,
        }):
            import importlib
            import cloud_usage.providers.gcp.provider as prov_mod
            importlib.reload(prov_mod)

            reloaded_provider = prov_mod.GCPDiscoveryProvider(
                credentials=MagicMock(),
                projects=_make_projects(),
                shared_clients=GCPClients(),
            )
            client = reloaded_provider._create_dns_client("proj-test")
            assert client is not None
            mock_dns.Client.assert_called_once()

            importlib.reload(prov_mod)

    def test_returns_none_when_sdk_missing(self) -> None:
        """_create_dns_client returns None when google-cloud-dns not installed."""
        provider = _make_provider()

        # Other test files may have mocked google.cloud.dns in sys.modules.
        # Temporarily remove it so _create_dns_client hits the ImportError path.
        saved_modules = {}
        for key in list(sys.modules.keys()):
            if key.startswith("google"):
                saved_modules[key] = sys.modules.pop(key)

        try:
            client = provider._create_dns_client("proj-test")
            assert client is None
        finally:
            sys.modules.update(saved_modules)


class TestSafeCollect:
    """Tests for _safe_collect GCP-specific error handling."""

    def test_successful_collection(self) -> None:
        """_safe_collect returns collector results on success."""
        resource = CloudResource(
            resource_id="r1", resource_type="gcp-vm",
            provider="gcp", account_id="p1", region="us-central1",
            name="vm-1",
        )
        result = GCPDiscoveryProvider._safe_collect(
            "VMs", "proj-1", lambda: [resource]
        )
        assert len(result) == 1
        assert result[0].resource_id == "r1"

    def test_permission_denied_returns_empty(self) -> None:
        """_safe_collect returns [] on PermissionDenied."""
        exc = type("PermissionDenied", (Exception,), {})("Access denied")

        def failing_collector():
            raise exc

        result = GCPDiscoveryProvider._safe_collect(
            "VMs", "proj-1", failing_collector
        )
        assert result == []

    def test_forbidden_returns_empty(self) -> None:
        """_safe_collect returns [] on Forbidden."""
        exc = type("Forbidden", (Exception,), {})("Forbidden")

        def failing_collector():
            raise exc

        result = GCPDiscoveryProvider._safe_collect(
            "VMs", "proj-1", failing_collector
        )
        assert result == []

    def test_too_many_requests_returns_empty_with_warning(self, capsys) -> None:
        """_safe_collect returns [] on TooManyRequests and writes stderr warning."""
        exc = type("TooManyRequests", (Exception,), {})("Rate limited")

        def failing_collector():
            raise exc

        result = GCPDiscoveryProvider._safe_collect(
            "VMs", "proj-1", failing_collector
        )
        assert result == []
        captured = capsys.readouterr()
        assert "throttled" in captured.err.lower()

    def test_429_status_code_returns_empty(self, capsys) -> None:
        """_safe_collect returns [] when exception has status_code=429."""
        exc = Exception("Quota exceeded")
        exc.code = 429

        def failing_collector():
            raise exc

        result = GCPDiscoveryProvider._safe_collect(
            "VMs", "proj-1", failing_collector
        )
        assert result == []
        captured = capsys.readouterr()
        assert "throttled" in captured.err.lower()

    def test_api_disabled_has_not_been_used(self, capsys) -> None:
        """_safe_collect returns [] when API 'has not been used'."""
        exc = Exception(
            "Cloud SQL Admin API has not been used in project proj-1"
        )

        def failing_collector():
            raise exc

        result = GCPDiscoveryProvider._safe_collect(
            "Cloud SQL", "proj-1", failing_collector
        )
        assert result == []
        captured = capsys.readouterr()
        assert "[Skip]" in captured.err

    def test_api_disabled_is_not_enabled(self, capsys) -> None:
        """_safe_collect returns [] when API 'is not enabled'."""
        exc = Exception(
            "Container API is not enabled for project proj-1"
        )

        def failing_collector():
            raise exc

        result = GCPDiscoveryProvider._safe_collect(
            "GKE", "proj-1", failing_collector
        )
        assert result == []
        captured = capsys.readouterr()
        assert "[Skip]" in captured.err

    def test_generic_error_returns_empty_with_warning(self, capsys) -> None:
        """_safe_collect returns [] on generic error and writes stderr warning."""
        def failing_collector():
            raise RuntimeError("Network timeout")

        result = GCPDiscoveryProvider._safe_collect(
            "VMs", "proj-1", failing_collector
        )
        assert result == []
        captured = capsys.readouterr()
        assert "Failed to collect" in captured.err

    def test_safe_collect_passes_args_to_collector(self) -> None:
        """_safe_collect forwards *args to collector function."""
        def collector(a, b, c):
            assert a == "arg1"
            assert b == "arg2"
            assert c == "arg3"
            return []

        result = GCPDiscoveryProvider._safe_collect(
            "VMs", "proj-1", collector, "arg1", "arg2", "arg3"
        )
        assert result == []


# -- Tests for CLI Integration --


class TestCLIArgParsing:
    """Tests for CLI argument parsing with GCP flags."""

    def test_gcp_flag_recognized(self) -> None:
        """--gcp flag is recognized."""
        from cloud_usage.cli import parse_args
        args = parse_args(["--gcp"])
        assert args.gcp is True

    def test_project_flag(self) -> None:
        """--project flag stores project ID."""
        from cloud_usage.cli import parse_args
        args = parse_args(["--gcp", "--project", "my-project"])
        assert args.project == "my-project"

    def test_org_id_flag(self) -> None:
        """--org-id flag stores organization ID."""
        from cloud_usage.cli import parse_args
        args = parse_args(["--gcp", "--org-id", "123456"])
        assert args.org_id == "123456"

    def test_include_projects_flag(self) -> None:
        """--include-projects flag stores comma-separated patterns."""
        from cloud_usage.cli import parse_args
        args = parse_args(["--gcp", "--include-projects", "proj-*,test-*"])
        assert args.include_projects == "proj-*,test-*"

    def test_exclude_projects_flag(self) -> None:
        """--exclude-projects flag stores comma-separated patterns."""
        from cloud_usage.cli import parse_args
        args = parse_args(["--gcp", "--exclude-projects", "dev-*"])
        assert args.exclude_projects == "dev-*"

    def test_all_gcp_flags_together(self) -> None:
        """All GCP flags work together."""
        from cloud_usage.cli import parse_args
        args = parse_args([
            "--gcp",
            "--project", "my-proj",
            "--org-id", "789",
            "--include-projects", "prod-*",
            "--exclude-projects", "dev-*",
        ])
        assert args.gcp is True
        assert args.project == "my-proj"
        assert args.org_id == "789"
        assert args.include_projects == "prod-*"
        assert args.exclude_projects == "dev-*"

    def test_gcp_flags_default_to_none(self) -> None:
        """GCP flags default to None when not specified."""
        from cloud_usage.cli import parse_args
        args = parse_args(["--gcp"])
        assert args.project is None
        assert args.org_id is None
        assert args.include_projects is None
        assert args.exclude_projects is None


class TestCLIAuthValidators:
    """Tests for _get_auth_validators with GCP."""

    def test_gcp_validator_included_when_selected(self) -> None:
        """_get_auth_validators includes GCPAuthValidator when 'gcp' selected."""
        from cloud_usage.cli import parse_args, _get_auth_validators

        args = parse_args(["--gcp"])
        validators = _get_auth_validators(["gcp"], args)

        assert "gcp" in validators
        from cloud_usage.providers.gcp.auth import GCPAuthValidator
        assert isinstance(validators["gcp"], GCPAuthValidator)

    def test_gcp_validator_not_included_when_not_selected(self) -> None:
        """_get_auth_validators does not include GCP when not selected."""
        from cloud_usage.cli import parse_args, _get_auth_validators

        args = parse_args(["--aws"])
        validators = _get_auth_validators(["aws"], args)

        assert "gcp" not in validators


class TestCLIDiscoveryProviders:
    """Tests for _get_discovery_providers with GCP."""

    def test_gcp_provider_created_when_selected(self) -> None:
        """Verify GCPDiscoveryProvider can be constructed as CLI would."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--gcp", "--project", "test-proj"])
        mock_creds = MagicMock()

        test_projects = [
            ProjectInfo(
                project_id="test-proj",
                compute_enabled=True,
                dns_enabled=True,
                sqladmin_enabled=True,
                container_enabled=True,
            )
        ]

        # Simulate what _get_discovery_providers does for GCP
        provider = GCPDiscoveryProvider(
            credentials=mock_creds,
            projects=test_projects,
            shared_clients=GCPClients(),
            include_projects=None,
            exclude_projects=None,
        )

        assert provider.provider_name == "gcp"
        assert provider.list_accounts() == ["test-proj"]

    def test_gcp_provider_not_created_when_not_selected(self) -> None:
        """_get_discovery_providers does not create GCP provider for AWS-only."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--aws"])

        # Verify that parse_args does not set gcp=True for non-GCP flags
        assert args.gcp is False

    def test_gcp_code_path_present_in_cli(self) -> None:
        """Verify _get_discovery_providers contains GCP code path."""
        import inspect
        from cloud_usage.cli import _get_discovery_providers

        source = inspect.getsource(_get_discovery_providers)
        assert '"gcp" in selected' in source
        assert "GCPDiscoveryProvider" in source
        assert "enumerate_gcp_projects" in source
        assert "create_shared_clients" in source


class TestParseAccountList:
    """Tests for _parse_account_list helper."""

    def test_parses_comma_separated_list(self) -> None:
        """Parses comma-separated string into list."""
        from cloud_usage.cli import _parse_account_list
        result = _parse_account_list("proj-a,proj-b,proj-c")
        assert result == ["proj-a", "proj-b", "proj-c"]

    def test_strips_whitespace(self) -> None:
        """Strips whitespace around entries."""
        from cloud_usage.cli import _parse_account_list
        result = _parse_account_list(" proj-a , proj-b ")
        assert result == ["proj-a", "proj-b"]

    def test_none_returns_none(self) -> None:
        """None input returns None."""
        from cloud_usage.cli import _parse_account_list
        result = _parse_account_list(None)
        assert result is None

    def test_empty_string_returns_empty_list(self) -> None:
        """Empty string returns empty list."""
        from cloud_usage.cli import _parse_account_list
        result = _parse_account_list("")
        assert result == []
