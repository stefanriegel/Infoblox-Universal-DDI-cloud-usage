"""Tests for AWS discovery provider with account filtering and CLI integration.

Tests use moto's @mock_aws decorator to mock all AWS services.
Covers AWSDiscoveryProvider account listing, filtering, skeleton
discover_account, and CLI argument parsing for AWS-specific flags.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boto3
from moto import mock_aws

from cloud_usage.providers.aws.provider import AWSDiscoveryProvider


# -- Tests for AWSDiscoveryProvider.list_accounts --


class TestListAccounts:
    """Tests for AWSDiscoveryProvider.list_accounts()."""

    @mock_aws
    def test_list_accounts_with_organizations(self) -> None:
        """list_accounts() returns all active accounts from Organizations."""
        session = boto3.Session(region_name="us-east-1")
        org = session.client("organizations", region_name="us-east-1")
        org.create_organization(FeatureSet="ALL")
        org.create_account(Email="dev@example.com", AccountName="Dev")
        org.create_account(Email="staging@example.com", AccountName="Staging")

        provider = AWSDiscoveryProvider(session=session)
        accounts = provider.list_accounts()

        # Management account + 2 member accounts = 3
        assert len(accounts) == 3
        assert all(isinstance(a, str) for a in accounts)

    @mock_aws
    def test_list_accounts_fallback_to_single_account(self) -> None:
        """list_accounts() falls back to single account when no Organizations."""
        session = boto3.Session(region_name="us-east-1")

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            provider = AWSDiscoveryProvider(session=session)
            accounts = provider.list_accounts()

        assert len(accounts) == 1
        assert accounts[0] == "123456789012"  # moto default account
        assert "Organizations API unavailable" in stderr_capture.getvalue()

    @mock_aws
    def test_include_accounts_filtering(self) -> None:
        """list_accounts() keeps only specified accounts when include_accounts set."""
        session = boto3.Session(region_name="us-east-1")
        org = session.client("organizations", region_name="us-east-1")
        org.create_organization(FeatureSet="ALL")
        resp1 = org.create_account(Email="dev@example.com", AccountName="Dev")
        resp2 = org.create_account(Email="staging@example.com", AccountName="Staging")

        dev_id = resp1["CreateAccountStatus"]["AccountId"]

        provider = AWSDiscoveryProvider(
            session=session, include_accounts=[dev_id]
        )
        accounts = provider.list_accounts()

        assert len(accounts) == 1
        assert accounts[0] == dev_id

    @mock_aws
    def test_exclude_accounts_filtering(self) -> None:
        """list_accounts() removes specified accounts when exclude_accounts set."""
        session = boto3.Session(region_name="us-east-1")
        org = session.client("organizations", region_name="us-east-1")
        org.create_organization(FeatureSet="ALL")
        resp1 = org.create_account(Email="dev@example.com", AccountName="Dev")
        org.create_account(Email="staging@example.com", AccountName="Staging")

        dev_id = resp1["CreateAccountStatus"]["AccountId"]

        provider = AWSDiscoveryProvider(
            session=session, exclude_accounts=[dev_id]
        )
        accounts = provider.list_accounts()

        # Management + Staging (Dev excluded)
        assert dev_id not in accounts
        assert len(accounts) == 2

    @mock_aws
    def test_include_takes_precedence_over_exclude(self) -> None:
        """When both include and exclude are provided, include takes precedence."""
        session = boto3.Session(region_name="us-east-1")
        org = session.client("organizations", region_name="us-east-1")
        org.create_organization(FeatureSet="ALL")
        resp1 = org.create_account(Email="dev@example.com", AccountName="Dev")
        resp2 = org.create_account(Email="staging@example.com", AccountName="Staging")

        dev_id = resp1["CreateAccountStatus"]["AccountId"]

        # Include dev, but also try to exclude dev -- include should win
        provider = AWSDiscoveryProvider(
            session=session,
            include_accounts=[dev_id],
            exclude_accounts=[dev_id],
        )
        accounts = provider.list_accounts()

        # Include takes precedence, so only dev_id
        assert len(accounts) == 1
        assert accounts[0] == dev_id


# -- Tests for AWSDiscoveryProvider.discover_account --


class TestDiscoverAccount:
    """Tests for AWSDiscoveryProvider.discover_account() with wired collectors."""

    @mock_aws
    def test_discover_account_returns_resources(self) -> None:
        """discover_account() returns resources from all collectors."""
        session = boto3.Session(region_name="us-east-1")
        provider = AWSDiscoveryProvider(session=session)
        resources = provider.discover_account("123456789012")

        # moto creates default VPCs and subnets, so we should have resources
        assert len(resources) > 0
        # Verify we get at least VPCs (moto creates default VPC per region)
        vpc_resources = [r for r in resources if r.resource_type == "vpc"]
        assert len(vpc_resources) > 0

    @mock_aws
    def test_discover_account_cross_account(self) -> None:
        """discover_account() works with cross-account role assumption."""
        session = boto3.Session(region_name="us-east-1")
        provider = AWSDiscoveryProvider(session=session)

        # Different account triggers assume_role -- moto handles it
        resources = provider.discover_account("999888777666")

        # Cross-account discovers resources in the assumed-role account
        assert isinstance(resources, list)


# -- Tests for AWSDiscoveryProvider properties --


class TestProviderProperties:
    """Tests for AWSDiscoveryProvider basic properties."""

    @mock_aws
    def test_provider_name_returns_aws(self) -> None:
        """provider_name returns 'aws'."""
        session = boto3.Session(region_name="us-east-1")
        provider = AWSDiscoveryProvider(session=session)
        assert provider.provider_name == "aws"


# -- Tests for CLI argument parsing --


class TestCLIAWSArgs:
    """Tests for AWS-specific CLI argument parsing."""

    def test_profile_argument(self) -> None:
        """--profile argument is parsed correctly."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--aws", "--profile", "production"])
        assert args.profile == "production"

    def test_profile_default_none(self) -> None:
        """--profile defaults to None."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--aws"])
        assert args.profile is None

    def test_role_name_argument(self) -> None:
        """--role-name argument is parsed correctly."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--aws", "--role-name", "CustomRole"])
        assert args.role_name == "CustomRole"

    def test_role_name_default(self) -> None:
        """--role-name defaults to OrganizationAccountAccessRole."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--aws"])
        assert args.role_name == "OrganizationAccountAccessRole"

    def test_include_accounts_argument(self) -> None:
        """--include-accounts argument is parsed correctly."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--aws", "--include-accounts", "111,222,333"])
        assert args.include_accounts == "111,222,333"

    def test_exclude_accounts_argument(self) -> None:
        """--exclude-accounts argument is parsed correctly."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--aws", "--exclude-accounts", "444,555"])
        assert args.exclude_accounts == "444,555"

    def test_dry_run_flag(self) -> None:
        """--dry-run flag is parsed correctly."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--aws", "--dry-run"])
        assert args.dry_run is True

    def test_dry_run_default_false(self) -> None:
        """--dry-run defaults to False."""
        from cloud_usage.cli import parse_args

        args = parse_args(["--aws"])
        assert args.dry_run is False


# -- Tests for _parse_account_list helper --


class TestParseAccountList:
    """Tests for _parse_account_list helper."""

    def test_none_returns_none(self) -> None:
        """None input returns None."""
        from cloud_usage.cli import _parse_account_list

        assert _parse_account_list(None) is None

    def test_comma_separated(self) -> None:
        """Comma-separated string returns list of trimmed strings."""
        from cloud_usage.cli import _parse_account_list

        result = _parse_account_list("111, 222, 333")
        assert result == ["111", "222", "333"]

    def test_single_value(self) -> None:
        """Single value returns list with one element."""
        from cloud_usage.cli import _parse_account_list

        result = _parse_account_list("111")
        assert result == ["111"]

    def test_empty_string_returns_empty_list(self) -> None:
        """Empty string returns empty list."""
        from cloud_usage.cli import _parse_account_list

        result = _parse_account_list("")
        assert result == []
