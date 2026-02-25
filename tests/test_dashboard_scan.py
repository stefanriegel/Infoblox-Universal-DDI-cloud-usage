"""Tests for dashboard scan routes, focusing on checkpoint_engine wiring.

Verifies that _build_discovery_providers() correctly threads the
checkpoint_engine into AzureDiscoveryProvider and GCPDiscoveryProvider
constructors, proving the dashboard code path (scan.py) independently
from the CLI code path (cli.py).

Also covers regression tests for all 4 bug fixes:
- GCP 6-arg call signature in _enumerate_accounts
- ProjectInfo.project_id extraction (not raw object)
- GCP 6-arg call signature in _build_discovery_providers with include/exclude
- Azure 'id' key access (not dead 'subscription_id' fallback)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.dashboard.routes.scan import _build_discovery_providers
from cloud_usage.dashboard.services.scan_manager import ScanConfig


# -- Shared helper factories --

def _make_project_info(project_id="proj-1", **flags):
    """Create a ProjectInfo with sensible defaults."""
    from cloud_usage.providers.gcp.projects import ProjectInfo

    return ProjectInfo(
        project_id=project_id,
        compute_enabled=flags.get("compute_enabled", True),
        dns_enabled=flags.get("dns_enabled", True),
        sqladmin_enabled=flags.get("sqladmin_enabled", True),
        container_enabled=flags.get("container_enabled", True),
    )


def _make_subscription_dict(sub_id="sub-001", display_name="Test Sub"):
    """Create an Azure subscription dict matching list_subscriptions() structure."""
    return {
        "id": sub_id,
        "display_name": display_name,
        "tenant_id": "tenant-1",
        "state": "Enabled",
    }


class TestBuildDiscoveryProvidersCheckpointEngine:
    """Tests proving checkpoint_engine is passed through to provider constructors."""

    def test_build_discovery_providers_passes_checkpoint_to_azure(self):
        """_build_discovery_providers() passes checkpoint_engine kwarg to AzureDiscoveryProvider."""
        # Pre-import Azure provider module so it is in sys.modules for mock.patch
        import cloud_usage.providers.azure.provider
        import cloud_usage.providers.azure.subscriptions

        mock_checkpoint = mock.MagicMock()
        mock_azure_cls = mock.MagicMock()
        mock_credential = mock.MagicMock()
        mock_subscriptions = [
            {
                "subscription_id": "sub-1",
                "tenant_id": "tenant-1",
                "display_name": "Sub 1",
            }
        ]

        config = ScanConfig(
            providers=["azure"],
            include_accounts={},
            exclude_accounts={},
        )

        # Inject stub azure.identity module so the import inside _build_discovery_providers
        # succeeds without the Azure SDK installed
        mock_azure_identity = mock.MagicMock()
        mock_azure_identity.DefaultAzureCredential.return_value = mock_credential
        mock_azure_mod = mock.MagicMock()
        mock_azure_mod.identity = mock_azure_identity

        with mock.patch.dict(sys.modules, {
            "azure": mock_azure_mod,
            "azure.identity": mock_azure_identity,
        }), \
             mock.patch(
                 "cloud_usage.providers.azure.subscriptions.list_subscriptions",
                 return_value=mock_subscriptions,
             ), \
             mock.patch(
                 "cloud_usage.providers.azure.provider.AzureDiscoveryProvider",
                 mock_azure_cls,
             ):
            _build_discovery_providers(config, mock_checkpoint)

        mock_azure_cls.assert_called_once()
        call_kwargs = mock_azure_cls.call_args[1]
        assert call_kwargs.get("checkpoint_engine") is mock_checkpoint

    def test_build_discovery_providers_passes_checkpoint_to_gcp(self):
        """_build_discovery_providers() passes checkpoint_engine kwarg to GCPDiscoveryProvider."""
        # Pre-import GCP provider modules so they are in sys.modules for mock.patch
        import cloud_usage.providers.gcp.provider
        import cloud_usage.providers.gcp.projects
        import cloud_usage.providers.gcp.client_factory

        mock_checkpoint = mock.MagicMock()
        mock_gcp_cls = mock.MagicMock()
        mock_credentials = mock.MagicMock()
        mock_projects = ["project-1", "project-2"]
        mock_clients = mock.MagicMock()

        config = ScanConfig(
            providers=["gcp"],
            include_accounts={},
            exclude_accounts={},
        )

        # Inject stub google.auth module so the import inside _build_discovery_providers
        # succeeds without the Google SDK installed
        mock_google = mock.MagicMock()
        mock_google_auth = mock.MagicMock()
        mock_google_auth.default.return_value = (mock_credentials, "project-1")
        mock_google.auth = mock_google_auth

        with mock.patch.dict(sys.modules, {
            "google": mock_google,
            "google.auth": mock_google_auth,
        }), \
             mock.patch(
                 "cloud_usage.providers.gcp.projects.enumerate_gcp_projects",
                 return_value=mock_projects,
             ), \
             mock.patch(
                 "cloud_usage.providers.gcp.client_factory.create_shared_clients",
                 return_value=mock_clients,
             ), \
             mock.patch(
                 "cloud_usage.providers.gcp.provider.GCPDiscoveryProvider",
                 mock_gcp_cls,
             ):
            _build_discovery_providers(config, mock_checkpoint)

        mock_gcp_cls.assert_called_once()
        call_kwargs = mock_gcp_cls.call_args[1]
        assert call_kwargs.get("checkpoint_engine") is mock_checkpoint


# -- _enumerate_accounts regression tests --


class TestEnumerateAccountsGCP:
    """Regression tests for _enumerate_accounts GCP path.

    Tests verify:
    - enumerate_gcp_projects called with exactly 6 positional args
    - ProjectInfo.project_id extracted (not raw object)
    - Exception is captured and surfaced in error key
    """

    def _setup_google_auth_stub(self):
        """Return sys.modules stubs for google.auth."""
        mock_credentials = mock.MagicMock()
        mock_google = mock.MagicMock()
        mock_google_auth = mock.MagicMock()
        mock_google_auth.default.return_value = (mock_credentials, "adc-project-1")
        mock_google.auth = mock_google_auth
        return mock_credentials, {
            "google": mock_google,
            "google.auth": mock_google_auth,
        }

    def test_enumerate_gcp_calls_with_six_args(self):
        """_enumerate_accounts GCP calls enumerate_gcp_projects with 6 positional args."""
        import cloud_usage.providers.gcp.projects

        from cloud_usage.dashboard.routes.scan import _enumerate_accounts

        mock_credentials, stub_modules = self._setup_google_auth_stub()
        # credentials returned by gcp_default() from the stub
        mock_credentials = stub_modules["google.auth"].default.return_value[0]
        adc_project = stub_modules["google.auth"].default.return_value[1]

        mock_project = _make_project_info("proj-alpha")

        with mock.patch.dict(sys.modules, stub_modules), \
             mock.patch(
                 "cloud_usage.providers.gcp.projects.enumerate_gcp_projects",
                 return_value=[mock_project],
             ) as mock_enum:
            _enumerate_accounts(["gcp"])

        # Must be called once with exactly 6 positional args
        mock_enum.assert_called_once()
        call_args = mock_enum.call_args
        # All 6 args must be positional (args tuple length == 6)
        assert len(call_args.args) == 6, (
            f"enumerate_gcp_projects must be called with 6 positional args, "
            f"got {len(call_args.args)}: {call_args}"
        )
        # args[0] = credentials, args[1] = adc_project, args[2..5] = None, None, None, None
        assert call_args.args[2] is None  # project
        assert call_args.args[3] is None  # org_id
        assert call_args.args[4] is None  # include_patterns
        assert call_args.args[5] is None  # exclude_patterns

    def test_enumerate_gcp_extracts_project_id_from_project_info(self):
        """_enumerate_accounts extracts .project_id string, not raw ProjectInfo object."""
        import cloud_usage.providers.gcp.projects

        from cloud_usage.dashboard.routes.scan import _enumerate_accounts

        _, stub_modules = self._setup_google_auth_stub()
        projects = [_make_project_info("my-proj"), _make_project_info("other-proj")]

        with mock.patch.dict(sys.modules, stub_modules), \
             mock.patch(
                 "cloud_usage.providers.gcp.projects.enumerate_gcp_projects",
                 return_value=projects,
             ):
            result = _enumerate_accounts(["gcp"])

        accounts = result["gcp"]["accounts"]
        assert len(accounts) == 2
        ids = [a["id"] for a in accounts]
        assert ids == ["my-proj", "other-proj"], (
            "Expected project_id strings, not raw ProjectInfo objects"
        )
        # Verify each entry has proper structure
        for acct in accounts:
            assert isinstance(acct["id"], str)
            assert isinstance(acct["display_name"], str)

    def test_enumerate_gcp_returns_error_on_exception(self):
        """_enumerate_accounts captures exception and returns error key for GCP."""
        import cloud_usage.providers.gcp.projects

        from cloud_usage.dashboard.routes.scan import _enumerate_accounts

        _, stub_modules = self._setup_google_auth_stub()

        with mock.patch.dict(sys.modules, stub_modules), \
             mock.patch(
                 "cloud_usage.providers.gcp.projects.enumerate_gcp_projects",
                 side_effect=Exception("Permission denied: projects.list"),
             ):
            result = _enumerate_accounts(["gcp"])

        assert result["gcp"]["accounts"] == []
        assert "Permission denied" in result["gcp"]["error"]


class TestEnumerateAccountsAzure:
    """Regression tests for _enumerate_accounts Azure path.

    Tests verify:
    - Azure account dict uses 'id' key (not 'subscription_id')
    - display_name fallback works when display_name is empty string
    - Exception is captured and surfaced in error key
    """

    def _setup_azure_stub(self):
        """Return sys.modules stubs for azure.identity."""
        mock_credential = mock.MagicMock()
        mock_azure_identity = mock.MagicMock()
        mock_azure_identity.DefaultAzureCredential.return_value = mock_credential
        mock_azure_mod = mock.MagicMock()
        mock_azure_mod.identity = mock_azure_identity
        return mock_credential, {
            "azure": mock_azure_mod,
            "azure.identity": mock_azure_identity,
        }

    def test_enumerate_azure_uses_id_key(self):
        """_enumerate_accounts Azure uses 'id' key from subscription dict."""
        import cloud_usage.providers.azure.subscriptions

        from cloud_usage.dashboard.routes.scan import _enumerate_accounts

        _, stub_modules = self._setup_azure_stub()
        subs = [_make_subscription_dict("sub-001", "My Sub")]

        with mock.patch.dict(sys.modules, stub_modules), \
             mock.patch(
                 "cloud_usage.providers.azure.subscriptions.list_subscriptions",
                 return_value=subs,
             ):
            result = _enumerate_accounts(["azure"])

        accounts = result["azure"]["accounts"]
        assert len(accounts) == 1
        assert accounts[0]["id"] == "sub-001", (
            "Azure account must use 'id' key, not 'subscription_id'"
        )

    def test_enumerate_azure_display_name_fallback_uses_id(self):
        """When display_name is empty string, display_name falls back to id."""
        import cloud_usage.providers.azure.subscriptions

        from cloud_usage.dashboard.routes.scan import _enumerate_accounts

        _, stub_modules = self._setup_azure_stub()
        # Subscription with empty display_name — should fall back to id
        subs = [{"id": "sub-001", "display_name": "", "tenant_id": "t", "state": "Enabled"}]

        with mock.patch.dict(sys.modules, stub_modules), \
             mock.patch(
                 "cloud_usage.providers.azure.subscriptions.list_subscriptions",
                 return_value=subs,
             ):
            result = _enumerate_accounts(["azure"])

        accounts = result["azure"]["accounts"]
        assert accounts[0]["id"] == "sub-001"
        # display_name should fall back to id when empty string
        assert accounts[0]["display_name"] == "sub-001", (
            "Empty display_name should fall back to id value"
        )

    def test_enumerate_azure_returns_error_on_exception(self):
        """_enumerate_accounts captures exception and returns error key for Azure."""
        import cloud_usage.providers.azure.subscriptions

        from cloud_usage.dashboard.routes.scan import _enumerate_accounts

        _, stub_modules = self._setup_azure_stub()

        with mock.patch.dict(sys.modules, stub_modules), \
             mock.patch(
                 "cloud_usage.providers.azure.subscriptions.list_subscriptions",
                 side_effect=Exception("ClientAuthenticationError: no credentials"),
             ):
            result = _enumerate_accounts(["azure"])

        assert result["azure"]["accounts"] == []
        assert "ClientAuthenticationError" in result["azure"]["error"]


# -- _build_discovery_providers GCP call signature regression tests --


class TestBuildDiscoveryProvidersGCPCallSignature:
    """Regression tests for _build_discovery_providers GCP call signature.

    Tests verify:
    - enumerate_gcp_projects called with 6 positional args in _build_discovery_providers
    - include/exclude patterns passed as args 5 and 6 (not keyword args)
    """

    def _gcp_base_stubs(self):
        """Build sys.modules stubs for google.auth."""
        mock_credentials = mock.MagicMock()
        mock_google = mock.MagicMock()
        mock_google_auth = mock.MagicMock()
        mock_google_auth.default.return_value = (mock_credentials, "proj-adc")
        mock_google.auth = mock_google_auth
        return mock_credentials, {
            "google": mock_google,
            "google.auth": mock_google_auth,
        }

    def test_build_gcp_calls_enumerate_with_six_args(self):
        """_build_discovery_providers calls enumerate_gcp_projects with 6 positional args."""
        import cloud_usage.providers.gcp.client_factory
        import cloud_usage.providers.gcp.projects
        import cloud_usage.providers.gcp.provider

        mock_credentials, stub_modules = self._gcp_base_stubs()
        mock_projects = [_make_project_info("proj-1")]
        mock_clients = mock.MagicMock()
        mock_gcp_cls = mock.MagicMock()

        config = ScanConfig(
            providers=["gcp"],
            include_accounts={},
            exclude_accounts={},
        )

        with mock.patch.dict(sys.modules, stub_modules), \
             mock.patch(
                 "cloud_usage.providers.gcp.projects.enumerate_gcp_projects",
                 return_value=mock_projects,
             ) as mock_enum, \
             mock.patch(
                 "cloud_usage.providers.gcp.client_factory.create_shared_clients",
                 return_value=mock_clients,
             ), \
             mock.patch(
                 "cloud_usage.providers.gcp.provider.GCPDiscoveryProvider",
                 mock_gcp_cls,
             ):
            _build_discovery_providers(config, None)

        mock_enum.assert_called_once()
        call_args = mock_enum.call_args
        assert len(call_args.args) == 6, (
            f"enumerate_gcp_projects must be called with 6 positional args, "
            f"got {len(call_args.args)}: {call_args}"
        )

    def test_build_gcp_passes_include_exclude_patterns(self):
        """_build_discovery_providers passes include/exclude as args 5 and 6."""
        import cloud_usage.providers.gcp.client_factory
        import cloud_usage.providers.gcp.projects
        import cloud_usage.providers.gcp.provider

        mock_credentials, stub_modules = self._gcp_base_stubs()
        mock_projects = [_make_project_info("proj-production")]
        mock_clients = mock.MagicMock()
        mock_gcp_cls = mock.MagicMock()

        include_list = ["proj-*"]
        exclude_list = ["proj-test"]

        config = ScanConfig(
            providers=["gcp"],
            include_accounts={"gcp": include_list},
            exclude_accounts={"gcp": exclude_list},
        )

        with mock.patch.dict(sys.modules, stub_modules), \
             mock.patch(
                 "cloud_usage.providers.gcp.projects.enumerate_gcp_projects",
                 return_value=mock_projects,
             ) as mock_enum, \
             mock.patch(
                 "cloud_usage.providers.gcp.client_factory.create_shared_clients",
                 return_value=mock_clients,
             ), \
             mock.patch(
                 "cloud_usage.providers.gcp.provider.GCPDiscoveryProvider",
                 mock_gcp_cls,
             ):
            _build_discovery_providers(config, None)

        mock_enum.assert_called_once()
        call_args = mock_enum.call_args
        # args[4] = include_patterns, args[5] = exclude_patterns
        assert call_args.args[4] == include_list, (
            f"Expected include_patterns={include_list!r} as arg 5, got {call_args.args[4]!r}"
        )
        assert call_args.args[5] == exclude_list, (
            f"Expected exclude_patterns={exclude_list!r} as arg 6, got {call_args.args[5]!r}"
        )
