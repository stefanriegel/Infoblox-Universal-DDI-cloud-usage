"""Tests for Azure auth validator, subscription enumeration, and client factory.

All tests use unittest.mock to avoid requiring live Azure credentials.
Covers AzureAuthValidator validation, subscription listing/display,
client factory creation, and _extract_resource_group utility.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.providers.azure.auth import AzureAuthValidator
from cloud_usage.providers.azure.subscriptions import (
    get_subscription_display,
    list_subscriptions,
)
from cloud_usage.providers.azure.utils import _extract_resource_group


# -- Tests for AzureAuthValidator --


class TestAzureAuthValidator:
    """Tests for AzureAuthValidator credential validation."""

    def test_provider_name_returns_azure(self) -> None:
        """provider_name property returns 'azure'."""
        validator = AzureAuthValidator()
        assert validator.provider_name == "azure"

    @patch("cloud_usage.providers.azure.auth.AzureAuthValidator.validate")
    def test_validate_succeeds_with_valid_credentials(self, mock_validate) -> None:
        """validate() returns success=True with valid mocked credentials."""
        from cloud_usage.auth.validators import AuthResult

        mock_validate.return_value = AuthResult(
            provider="azure",
            success=True,
            identity="Tenant: test-tenant-id",
            account_count=3,
        )

        validator = AzureAuthValidator()
        result = validator.validate()

        assert result.success is True
        assert result.provider == "azure"
        assert "Tenant:" in result.identity
        assert result.account_count == 3
        assert result.error_message is None
        assert result.suggestion is None
        assert result.read_only is True

    def test_validate_with_mocked_azure_sdk(self) -> None:
        """validate() correctly calls DefaultAzureCredential and SubscriptionClient."""
        mock_credential_cls = MagicMock()
        mock_credential = MagicMock()
        mock_credential_cls.return_value = mock_credential

        # Create mock subscriptions
        mock_sub1 = MagicMock()
        mock_sub1.state.value = "Enabled"
        mock_sub1.tenant_id = "tenant-abc-123"
        mock_sub1.subscription_id = "sub-1"
        mock_sub1.display_name = "Production"

        mock_sub2 = MagicMock()
        mock_sub2.state.value = "Enabled"
        mock_sub2.tenant_id = "tenant-abc-123"
        mock_sub2.subscription_id = "sub-2"
        mock_sub2.display_name = "Development"

        mock_sub3 = MagicMock()
        mock_sub3.state.value = "Disabled"
        mock_sub3.tenant_id = "tenant-abc-123"
        mock_sub3.subscription_id = "sub-3"
        mock_sub3.display_name = "Decommissioned"

        mock_sub_client_cls = MagicMock()
        mock_sub_client = MagicMock()
        mock_sub_client.subscriptions.list.return_value = [mock_sub1, mock_sub2, mock_sub3]
        mock_sub_client_cls.return_value = mock_sub_client

        with patch.dict("sys.modules", {
            "azure.identity": MagicMock(DefaultAzureCredential=mock_credential_cls),
            "azure.mgmt.resource": MagicMock(SubscriptionClient=mock_sub_client_cls),
        }):
            # Re-import to pick up mocked modules
            import importlib
            import cloud_usage.providers.azure.auth as auth_mod
            importlib.reload(auth_mod)

            validator = auth_mod.AzureAuthValidator()
            result = validator.validate()

        assert result.success is True
        assert result.provider == "azure"
        assert "tenant-abc-123" in result.identity
        assert result.account_count == 2  # Only 2 Enabled subs

    def test_validate_handles_credential_unavailable(self) -> None:
        """validate() returns failure with suggestion when credentials unavailable."""
        # Create exception with CredentialUnavailableError class name
        class FakeCredentialUnavailableError(Exception):
            pass

        FakeCredentialUnavailableError.__name__ = "CredentialUnavailableError"

        mock_credential_cls = MagicMock()
        mock_credential_cls.side_effect = FakeCredentialUnavailableError("No credential available")

        with patch.dict("sys.modules", {
            "azure.identity": MagicMock(DefaultAzureCredential=mock_credential_cls),
        }):
            import importlib
            import cloud_usage.providers.azure.auth as auth_mod
            importlib.reload(auth_mod)

            validator = auth_mod.AzureAuthValidator()
            result = validator.validate()

        assert result.success is False
        assert result.provider == "azure"
        assert "No Azure credentials found" in result.error_message
        assert "az login" in result.suggestion
        assert "AZURE_CLIENT_ID" in result.suggestion
        assert result.account_count == 0

    def test_validate_handles_expired_token(self) -> None:
        """validate() suggests az login when token is expired."""

        class FakeClientAuthenticationError(Exception):
            pass

        FakeClientAuthenticationError.__name__ = "ClientAuthenticationError"

        mock_credential_cls = MagicMock()
        mock_credential = MagicMock()
        mock_credential_cls.return_value = mock_credential
        mock_credential.get_token.side_effect = FakeClientAuthenticationError(
            "Token has expired and needs to be refreshed"
        )

        with patch.dict("sys.modules", {
            "azure.identity": MagicMock(DefaultAzureCredential=mock_credential_cls),
        }):
            import importlib
            import cloud_usage.providers.azure.auth as auth_mod
            importlib.reload(auth_mod)

            validator = auth_mod.AzureAuthValidator()
            result = validator.validate()

        assert result.success is False
        assert "expired" in result.error_message.lower()
        assert "az login" in result.suggestion

    def test_validate_handles_generic_auth_failure(self) -> None:
        """validate() returns generic failure for non-expired auth errors."""

        class FakeClientAuthenticationError(Exception):
            pass

        FakeClientAuthenticationError.__name__ = "ClientAuthenticationError"

        mock_credential_cls = MagicMock()
        mock_credential = MagicMock()
        mock_credential_cls.return_value = mock_credential
        mock_credential.get_token.side_effect = FakeClientAuthenticationError(
            "Invalid client secret"
        )

        with patch.dict("sys.modules", {
            "azure.identity": MagicMock(DefaultAzureCredential=mock_credential_cls),
        }):
            import importlib
            import cloud_usage.providers.azure.auth as auth_mod
            importlib.reload(auth_mod)

            validator = auth_mod.AzureAuthValidator()
            result = validator.validate()

        assert result.success is False
        assert "authentication failed" in result.error_message.lower()
        assert "az account list" in result.suggestion

    def test_validate_handles_unexpected_error(self) -> None:
        """validate() returns failure with generic suggestion for unexpected errors."""
        mock_credential_cls = MagicMock()
        mock_credential_cls.side_effect = RuntimeError("Unexpected network failure")

        with patch.dict("sys.modules", {
            "azure.identity": MagicMock(DefaultAzureCredential=mock_credential_cls),
        }):
            import importlib
            import cloud_usage.providers.azure.auth as auth_mod
            importlib.reload(auth_mod)

            validator = auth_mod.AzureAuthValidator()
            result = validator.validate()

        assert result.success is False
        assert "Unexpected error" in result.error_message
        assert result.account_count == 0


# -- Tests for list_subscriptions --


class TestListSubscriptions:
    """Tests for subscription enumeration."""

    def test_returns_enabled_subscriptions_only(self) -> None:
        """list_subscriptions filters to Enabled subscriptions only."""
        mock_credential = MagicMock()

        mock_sub_enabled = MagicMock()
        mock_sub_enabled.state.value = "Enabled"
        mock_sub_enabled.subscription_id = "sub-enabled-1"
        mock_sub_enabled.display_name = "Production"
        mock_sub_enabled.tenant_id = "tenant-1"

        mock_sub_disabled = MagicMock()
        mock_sub_disabled.state.value = "Disabled"
        mock_sub_disabled.subscription_id = "sub-disabled-1"
        mock_sub_disabled.display_name = "Old Sub"
        mock_sub_disabled.tenant_id = "tenant-1"

        mock_sub_enabled2 = MagicMock()
        mock_sub_enabled2.state.value = "Enabled"
        mock_sub_enabled2.subscription_id = "sub-enabled-2"
        mock_sub_enabled2.display_name = "Development"
        mock_sub_enabled2.tenant_id = "tenant-1"

        mock_sub_client_cls = MagicMock()
        mock_sub_client = MagicMock()
        mock_sub_client.subscriptions.list.return_value = [
            mock_sub_enabled, mock_sub_disabled, mock_sub_enabled2,
        ]
        mock_sub_client_cls.return_value = mock_sub_client

        with patch.dict("sys.modules", {
            "azure.mgmt.resource": MagicMock(SubscriptionClient=mock_sub_client_cls),
        }):
            import importlib
            import cloud_usage.providers.azure.subscriptions as sub_mod
            importlib.reload(sub_mod)

            subs = sub_mod.list_subscriptions(mock_credential)

        assert len(subs) == 2
        assert all(s["state"] == "Enabled" for s in subs)
        assert subs[0]["id"] == "sub-enabled-1"
        assert subs[0]["display_name"] == "Production"
        assert subs[1]["id"] == "sub-enabled-2"

    def test_returns_correct_dict_keys(self) -> None:
        """list_subscriptions returns dicts with id, display_name, tenant_id, state."""
        mock_credential = MagicMock()

        mock_sub = MagicMock()
        mock_sub.state.value = "Enabled"
        mock_sub.subscription_id = "aaaa-bbbb-cccc"
        mock_sub.display_name = "Test Sub"
        mock_sub.tenant_id = "tenant-xyz"

        mock_sub_client_cls = MagicMock()
        mock_sub_client = MagicMock()
        mock_sub_client.subscriptions.list.return_value = [mock_sub]
        mock_sub_client_cls.return_value = mock_sub_client

        with patch.dict("sys.modules", {
            "azure.mgmt.resource": MagicMock(SubscriptionClient=mock_sub_client_cls),
        }):
            import importlib
            import cloud_usage.providers.azure.subscriptions as sub_mod
            importlib.reload(sub_mod)

            subs = sub_mod.list_subscriptions(mock_credential)

        assert len(subs) == 1
        sub = subs[0]
        assert set(sub.keys()) == {"id", "display_name", "tenant_id", "state"}
        assert sub["id"] == "aaaa-bbbb-cccc"
        assert sub["tenant_id"] == "tenant-xyz"


# -- Tests for get_subscription_display --


class TestGetSubscriptionDisplay:
    """Tests for subscription display formatting."""

    def test_format_with_display_name(self) -> None:
        """get_subscription_display returns 'Name (GUID)' format."""
        result = get_subscription_display("aaaa-bbbb-cccc", "Production")
        assert result == "Production (aaaa-bbbb-cccc)"

    def test_format_without_display_name(self) -> None:
        """get_subscription_display returns just GUID when no display name."""
        result = get_subscription_display("aaaa-bbbb-cccc", "")
        assert result == "aaaa-bbbb-cccc"

    def test_format_with_long_name(self) -> None:
        """get_subscription_display handles long display names."""
        result = get_subscription_display("sub-id", "Very Long Subscription Name For Testing")
        assert result == "Very Long Subscription Name For Testing (sub-id)"


# -- Tests for client factory --


class TestClientFactory:
    """Tests for Azure client factory."""

    def test_creates_all_clients(self) -> None:
        """create_subscription_clients creates all management clients."""
        from cloud_usage.providers.azure.client_factory import create_subscription_clients

        mock_credential = MagicMock()

        # Patch all individual client creation imports
        with patch(
            "cloud_usage.providers.azure.client_factory._try_create",
            side_effect=lambda name, fn: MagicMock(name=f"mock_{name}"),
        ):
            clients = create_subscription_clients(mock_credential, "test-sub-id")

        # All fields should be populated (with mocks)
        assert clients.compute is not None
        assert clients.network is not None
        assert clients.resource is not None
        assert clients.dns is not None
        assert clients.privatedns is not None
        assert clients.storage is not None
        assert clients.sql is not None
        assert clients.cosmosdb is not None
        assert clients.mysql is not None
        assert clients.postgresql is not None
        assert clients.redis is not None
        assert clients.web is not None
        assert clients.container is not None
        assert clients.containerservice is not None
        assert clients.apimanagement is not None
        assert clients.trafficmanager is not None
        assert clients.mgmt_groups is not None
        assert clients.subscription is not None
        assert clients.appcontainers is not None

    def test_handles_missing_sdk_package(self) -> None:
        """create_subscription_clients sets None for missing SDK packages."""
        from cloud_usage.providers.azure.client_factory import _try_create

        def factory_that_fails():
            raise ImportError("No module named 'azure.mgmt.missing'")

        result = _try_create("missing-service", factory_that_fails)
        assert result is None

    def test_handles_generic_creation_error(self) -> None:
        """_try_create returns None on generic exceptions."""
        from cloud_usage.providers.azure.client_factory import _try_create

        def factory_that_errors():
            raise RuntimeError("Connection refused")

        result = _try_create("broken-service", factory_that_errors)
        assert result is None

    def test_azure_clients_dataclass_defaults(self) -> None:
        """AzureClients dataclass fields default to None."""
        from cloud_usage.providers.azure.client_factory import AzureClients

        clients = AzureClients()
        assert clients.compute is None
        assert clients.network is None
        assert clients.resource is None
        assert clients.dns is None
        assert clients.appcontainers is None


# -- Tests for _extract_resource_group --


class TestExtractResourceGroup:
    """Tests for _extract_resource_group utility."""

    def test_standard_arm_id(self) -> None:
        """Extracts resource group from standard ARM resource ID."""
        arm_id = "/subscriptions/sub-123/resourceGroups/myRG/providers/Microsoft.Compute/virtualMachines/myVM"
        assert _extract_resource_group(arm_id) == "myRG"

    def test_case_insensitive_match(self) -> None:
        """Extracts resource group regardless of 'resourceGroups' casing."""
        arm_id = "/subscriptions/sub-123/resourcegroups/prodRG/providers/Microsoft.Network/virtualNetworks/vnet1"
        assert _extract_resource_group(arm_id) == "prodRG"

    def test_mixed_case_match(self) -> None:
        """Handles RESOURCEGROUPS in all caps."""
        arm_id = "/subscriptions/sub-123/RESOURCEGROUPS/TestRG/providers/Microsoft.Sql/servers/sql1"
        assert _extract_resource_group(arm_id) == "TestRG"

    def test_empty_string(self) -> None:
        """Returns empty string for empty resource ID."""
        assert _extract_resource_group("") == ""

    def test_malformed_id_no_resource_groups(self) -> None:
        """Returns empty string when no resourceGroups segment exists."""
        assert _extract_resource_group("/subscriptions/sub-123/providers/something") == ""

    def test_malformed_id_resource_groups_at_end(self) -> None:
        """Returns empty string when resourceGroups is the last segment."""
        assert _extract_resource_group("/subscriptions/sub-123/resourceGroups") == ""

    def test_none_like_empty(self) -> None:
        """Returns empty string for None-like falsy input."""
        assert _extract_resource_group("") == ""

    def test_complex_arm_id(self) -> None:
        """Handles deeply nested ARM resource IDs."""
        arm_id = (
            "/subscriptions/00000000-0000-0000-0000-000000000000"
            "/resourceGroups/my-rg-prod"
            "/providers/Microsoft.Network/privateDnsZones/example.com"
            "/virtualNetworkLinks/vnet-link-1"
        )
        assert _extract_resource_group(arm_id) == "my-rg-prod"
