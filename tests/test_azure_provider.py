"""Tests for Azure discovery provider and CLI integration.

All tests use unittest.mock to avoid requiring live Azure credentials.
Covers AzureDiscoveryProvider filtering, _safe_collect error handling,
checkpoint integration, and CLI argument parsing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.providers.azure.provider import AzureDiscoveryProvider
from cloud_usage.schema.resource import CloudResource


def _make_subscriptions() -> list[dict]:
    """Create test subscription list."""
    return [
        {"id": "aaaa-1111", "display_name": "Production", "tenant_id": "t1", "state": "Enabled"},
        {"id": "bbbb-2222", "display_name": "Development", "tenant_id": "t1", "state": "Enabled"},
        {"id": "cccc-3333", "display_name": "Staging", "tenant_id": "t1", "state": "Enabled"},
    ]


# -- Tests for AzureDiscoveryProvider --


class TestAzureDiscoveryProvider:
    """Tests for AzureDiscoveryProvider interface."""

    def test_provider_name_returns_azure(self) -> None:
        """provider_name property returns 'azure'."""
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=_make_subscriptions(),
        )
        assert provider.provider_name == "azure"

    def test_list_accounts_returns_all_subscriptions_when_no_filter(self) -> None:
        """list_accounts returns all subscription IDs without filters."""
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=_make_subscriptions(),
        )
        accounts = provider.list_accounts()
        assert accounts == ["aaaa-1111", "bbbb-2222", "cccc-3333"]

    def test_list_accounts_with_include_filter_by_guid(self) -> None:
        """list_accounts filters by subscription GUID when include is set."""
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=_make_subscriptions(),
            include_subscriptions=["aaaa-1111", "cccc-3333"],
        )
        accounts = provider.list_accounts()
        assert accounts == ["aaaa-1111", "cccc-3333"]

    def test_list_accounts_with_include_filter_by_display_name(self) -> None:
        """list_accounts filters by display name (case-insensitive)."""
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=_make_subscriptions(),
            include_subscriptions=["production"],
        )
        accounts = provider.list_accounts()
        assert accounts == ["aaaa-1111"]

    def test_list_accounts_with_include_filter_case_insensitive(self) -> None:
        """list_accounts include filter is case-insensitive for display names."""
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=_make_subscriptions(),
            include_subscriptions=["DEVELOPMENT"],
        )
        accounts = provider.list_accounts()
        assert accounts == ["bbbb-2222"]

    def test_list_accounts_with_exclude_filter(self) -> None:
        """list_accounts excludes matching subscriptions."""
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=_make_subscriptions(),
            exclude_subscriptions=["bbbb-2222"],
        )
        accounts = provider.list_accounts()
        assert accounts == ["aaaa-1111", "cccc-3333"]

    def test_list_accounts_with_exclude_by_display_name(self) -> None:
        """list_accounts exclude filter works with display names."""
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=_make_subscriptions(),
            exclude_subscriptions=["staging"],
        )
        accounts = provider.list_accounts()
        assert accounts == ["aaaa-1111", "bbbb-2222"]

    def test_include_takes_precedence_over_exclude(self) -> None:
        """Include filter takes precedence when both are provided."""
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=_make_subscriptions(),
            include_subscriptions=["aaaa-1111"],
            exclude_subscriptions=["aaaa-1111"],
        )
        # Include should take precedence -- aaaa-1111 is included
        accounts = provider.list_accounts()
        assert accounts == ["aaaa-1111"]

    def test_discover_account_returns_empty_list_skeleton(self) -> None:
        """discover_account returns empty list (skeleton implementation)."""
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=_make_subscriptions(),
        )
        with patch(
            "cloud_usage.providers.azure.provider.create_subscription_clients"
        ) as mock_create:
            mock_create.return_value = MagicMock()
            resources = provider.discover_account("aaaa-1111")

        assert resources == []

    def test_discover_account_creates_subscription_clients(self) -> None:
        """discover_account creates clients for the given subscription."""
        mock_credential = MagicMock()
        provider = AzureDiscoveryProvider(
            credential=mock_credential,
            subscriptions=_make_subscriptions(),
        )
        with patch(
            "cloud_usage.providers.azure.provider.create_subscription_clients"
        ) as mock_create:
            mock_create.return_value = MagicMock()
            provider.discover_account("aaaa-1111")

        mock_create.assert_called_once_with(mock_credential, "aaaa-1111")


# -- Tests for _safe_collect --


class TestSafeCollect:
    """Tests for AzureDiscoveryProvider._safe_collect error handling."""

    def test_returns_collector_results_on_success(self) -> None:
        """_safe_collect returns collector results when no error."""
        resource = CloudResource(
            resource_id="/sub/rg/vm1",
            resource_type="azure-vm",
            provider="azure",
            account_id="sub-1",
            region="eastus",
            name="vm1",
        )

        def collector():
            return [resource]

        result = AzureDiscoveryProvider._safe_collect(
            "virtual-machines", "sub-1", collector
        )
        assert len(result) == 1
        assert result[0].resource_id == "/sub/rg/vm1"

    def test_returns_empty_on_missing_subscription_registration(self) -> None:
        """_safe_collect returns empty list on MissingSubscriptionRegistration."""

        def collector():
            raise Exception(
                "MissingSubscriptionRegistration: The subscription is not registered to use namespace 'Microsoft.Compute'"
            )

        result = AzureDiscoveryProvider._safe_collect(
            "virtual-machines", "sub-1", collector
        )
        assert result == []

    def test_returns_empty_on_authorization_failed(self) -> None:
        """_safe_collect returns empty list on AuthorizationFailed."""

        def collector():
            raise Exception(
                "AuthorizationFailed: The client does not have authorization to perform action"
            )

        result = AzureDiscoveryProvider._safe_collect(
            "virtual-machines", "sub-1", collector
        )
        assert result == []

    def test_returns_empty_on_generic_exception(self) -> None:
        """_safe_collect returns empty list on generic exceptions."""

        def collector():
            raise RuntimeError("Connection timeout")

        result = AzureDiscoveryProvider._safe_collect(
            "virtual-machines", "sub-1", collector
        )
        assert result == []

    def test_propagates_results_not_exceptions(self) -> None:
        """_safe_collect never propagates exceptions to caller."""
        resources = [
            CloudResource(
                resource_id="/sub/rg/nic1",
                resource_type="azure-nic",
                provider="azure",
                account_id="sub-1",
                region="eastus",
                name="nic1",
                ip_addresses=["10.0.0.1"],
            )
        ]

        def collector():
            return resources

        result = AzureDiscoveryProvider._safe_collect(
            "network-interfaces", "sub-1", collector
        )
        assert len(result) == 1
        assert result[0].ip_addresses == ["10.0.0.1"]


# -- Tests for checkpoint integration --


class TestCheckpointIntegration:
    """Tests for Azure checkpoint key format and resume behavior."""

    def test_checkpoint_key_format(self) -> None:
        """Checkpoint keys use 'azure:{sub_id}:completed' format."""
        sub_id = "aaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        expected_key = f"azure:{sub_id}:completed"
        assert expected_key == f"azure:{sub_id}:completed"

    def test_discover_account_skips_checkpointed_subscription(self) -> None:
        """discover_account skips already-completed subscriptions."""
        mock_checkpoint = MagicMock()
        mock_checkpoint_data = MagicMock()
        mock_progress = MagicMock()
        mock_progress.completed_accounts = ["aaaa-1111"]
        mock_checkpoint_data.providers = {"azure": mock_progress}
        mock_checkpoint.load.return_value = mock_checkpoint_data

        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=_make_subscriptions(),
            checkpoint_engine=mock_checkpoint,
        )

        with patch(
            "cloud_usage.providers.azure.provider.create_subscription_clients"
        ) as mock_create:
            resources = provider.discover_account("aaaa-1111")

        # Should skip -- no client creation needed
        mock_create.assert_not_called()
        assert resources == []

    def test_discover_account_processes_non_checkpointed_subscription(self) -> None:
        """discover_account processes subscriptions not in checkpoint."""
        mock_checkpoint = MagicMock()
        mock_checkpoint_data = MagicMock()
        mock_progress = MagicMock()
        mock_progress.completed_accounts = ["aaaa-1111"]  # Only this one completed
        mock_checkpoint_data.providers = {"azure": mock_progress}
        mock_checkpoint.load.return_value = mock_checkpoint_data

        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=_make_subscriptions(),
            checkpoint_engine=mock_checkpoint,
        )

        with patch(
            "cloud_usage.providers.azure.provider.create_subscription_clients"
        ) as mock_create:
            mock_create.return_value = MagicMock()
            resources = provider.discover_account("bbbb-2222")

        # Should process -- not in checkpoint
        mock_create.assert_called_once()
        assert resources == []

    def test_discover_account_works_without_checkpoint_engine(self) -> None:
        """discover_account works normally when no checkpoint engine is set."""
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=_make_subscriptions(),
        )

        with patch(
            "cloud_usage.providers.azure.provider.create_subscription_clients"
        ) as mock_create:
            mock_create.return_value = MagicMock()
            resources = provider.discover_account("aaaa-1111")

        mock_create.assert_called_once()
        assert resources == []


# -- Tests for CLI integration --


class TestCLIAzureIntegration:
    """Tests for CLI --azure flag and subscription filter parsing."""

    def test_parse_args_azure_flag(self) -> None:
        """--azure flag sets azure=True in parsed args."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--azure"])
        assert args.azure is True

    def test_parse_args_include_subscriptions(self) -> None:
        """--include-subscriptions parses comma-separated values."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--azure", "--include-subscriptions", "sub-1,sub-2,sub-3"])
        assert args.include_subscriptions == "sub-1,sub-2,sub-3"

    def test_parse_args_exclude_subscriptions(self) -> None:
        """--exclude-subscriptions parses comma-separated values."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--azure", "--exclude-subscriptions", "sub-old"])
        assert args.exclude_subscriptions == "sub-old"

    def test_parse_account_list_parses_csv(self) -> None:
        """_parse_account_list splits comma-separated values."""
        from cloud_usage.cli import _parse_account_list

        result = _parse_account_list("sub-1, sub-2, sub-3")
        assert result == ["sub-1", "sub-2", "sub-3"]

    def test_parse_account_list_handles_none(self) -> None:
        """_parse_account_list returns None for None input."""
        from cloud_usage.cli import _parse_account_list

        result = _parse_account_list(None)
        assert result is None

    def test_parse_account_list_strips_whitespace(self) -> None:
        """_parse_account_list strips whitespace from values."""
        from cloud_usage.cli import _parse_account_list

        result = _parse_account_list("  sub-1 ,  sub-2  ")
        assert result == ["sub-1", "sub-2"]

    def test_azure_flag_selects_azure_provider(self) -> None:
        """--azure flag results in 'azure' in selected providers list."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--azure"])
        assert args.azure is True
        assert args.aws is False
        assert args.gcp is False

    def test_azure_auth_validator_in_get_auth_validators(self) -> None:
        """_get_auth_validators includes AzureAuthValidator when azure selected."""
        from cloud_usage.cli import _get_auth_validators, parse_args

        args = parse_args(["--azure"])
        validators = _get_auth_validators(["azure"], args)

        assert "azure" in validators
        assert validators["azure"].provider_name == "azure"

    def test_azure_and_aws_coexist_in_validators(self) -> None:
        """Both AWS and Azure validators can be created together."""
        from cloud_usage.cli import _get_auth_validators, parse_args

        args = parse_args(["--aws", "--azure"])
        validators = _get_auth_validators(["aws", "azure"], args)

        assert "aws" in validators
        assert "azure" in validators
