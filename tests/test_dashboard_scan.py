"""Tests for dashboard scan routes, focusing on checkpoint_engine wiring.

Verifies that _build_discovery_providers() correctly threads the
checkpoint_engine into AzureDiscoveryProvider and GCPDiscoveryProvider
constructors, proving the dashboard code path (scan.py) independently
from the CLI code path (cli.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.dashboard.routes.scan import _build_discovery_providers
from cloud_usage.dashboard.services.scan_manager import ScanConfig


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
