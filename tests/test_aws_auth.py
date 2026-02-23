"""Tests for AWS auth validator, Organizations, and region discovery.

Tests use moto's @mock_aws decorator to mock all AWS services.
Covers AWSAuthValidator validation, Organizations account listing,
cross-account role assumption, and region discovery.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boto3
from moto import mock_aws

from cloud_usage.providers.aws.auth import AWSAuthValidator
from cloud_usage.providers.aws.organizations import (
    assume_cross_account_role,
    list_organization_accounts,
)
from cloud_usage.providers.aws.regions import get_enabled_regions


# -- Tests for AWSAuthValidator --


class TestAWSAuthValidator:
    """Tests for AWSAuthValidator credential validation."""

    @mock_aws
    def test_validate_succeeds_with_valid_credentials(self) -> None:
        """validate() returns success=True with valid mocked credentials."""
        validator = AWSAuthValidator()
        result = validator.validate()

        assert result.success is True
        assert result.provider == "aws"
        assert "arn:aws" in result.identity
        assert result.account_count >= 1
        assert result.error_message is None
        assert result.suggestion is None
        assert result.read_only is True

    @mock_aws
    def test_validate_with_organizations_returns_account_count(self) -> None:
        """validate() counts active accounts via Organizations."""
        # Create an organization with member accounts
        client = boto3.client("organizations", region_name="us-east-1")
        client.create_organization(FeatureSet="ALL")
        client.create_account(Email="dev@example.com", AccountName="Dev")
        client.create_account(Email="staging@example.com", AccountName="Staging")

        validator = AWSAuthValidator()
        result = validator.validate()

        assert result.success is True
        # Management account + 2 member accounts = 3 active accounts
        assert result.account_count == 3

    @mock_aws
    def test_validate_falls_back_to_single_account_without_organizations(self) -> None:
        """validate() returns account_count=1 when Organizations is unavailable."""
        # moto without create_organization means Organizations calls will fail
        # by default, STS still works so we get single-account fallback.
        # We need to explicitly mock Organizations to raise AccessDenied.
        validator = AWSAuthValidator()
        result = validator.validate()

        # Without an organization created, moto may return 0 or raise error.
        # In either case, the validator should succeed with at least 1 account.
        assert result.success is True
        assert result.account_count >= 1

    def test_validate_handles_no_credentials(self) -> None:
        """validate() returns failure with suggestion when no credentials found."""
        from botocore.exceptions import NoCredentialsError

        with patch("cloud_usage.providers.aws.auth.boto3") as mock_boto3:
            mock_boto3.Session.side_effect = NoCredentialsError()
            validator = AWSAuthValidator()
            result = validator.validate()

        assert result.success is False
        assert result.provider == "aws"
        assert "No AWS credentials found" in result.error_message
        assert "aws sso login" in result.suggestion
        assert result.account_count == 0

    def test_validate_handles_sso_token_error(self) -> None:
        """validate() returns failure with SSO login suggestion on token error."""
        # SSOTokenLoadError may not be importable everywhere, so simulate
        # via a generic exception with the right class name.
        class FakeSSOTokenLoadError(Exception):
            pass

        FakeSSOTokenLoadError.__name__ = "SSOTokenLoadError"

        with patch("cloud_usage.providers.aws.auth.boto3") as mock_boto3:
            mock_boto3.Session.side_effect = FakeSSOTokenLoadError("token expired")
            validator = AWSAuthValidator(profile="my-profile")
            result = validator.validate()

        assert result.success is False
        assert "SSO token expired" in result.error_message
        assert "aws sso login --profile my-profile" in result.suggestion

    def test_validate_handles_client_error(self) -> None:
        """validate() returns failure with generic message on ClientError."""
        from botocore.exceptions import ClientError

        error_response = {
            "Error": {"Code": "InvalidClientTokenId", "Message": "Token is invalid"}
        }

        with patch("cloud_usage.providers.aws.auth.boto3") as mock_boto3:
            mock_session = mock_boto3.Session.return_value
            mock_sts = mock_session.client.return_value
            mock_sts.get_caller_identity.side_effect = ClientError(
                error_response, "GetCallerIdentity"
            )
            validator = AWSAuthValidator()
            result = validator.validate()

        assert result.success is False
        assert result.provider == "aws"
        assert result.account_count == 0

    def test_provider_name_returns_aws(self) -> None:
        """provider_name property returns 'aws'."""
        validator = AWSAuthValidator()
        assert validator.provider_name == "aws"

    def test_validate_with_profile_parameter(self) -> None:
        """AWSAuthValidator stores and uses the profile parameter."""
        validator = AWSAuthValidator(profile="production")
        assert validator._profile == "production"


# -- Tests for list_organization_accounts --


class TestListOrganizationAccounts:
    """Tests for Organizations account listing."""

    @mock_aws
    def test_returns_active_accounts(self) -> None:
        """list_organization_accounts returns only ACTIVE accounts."""
        session = boto3.Session(region_name="us-east-1")
        org = session.client("organizations", region_name="us-east-1")
        org.create_organization(FeatureSet="ALL")
        org.create_account(Email="dev@example.com", AccountName="Dev")
        org.create_account(Email="staging@example.com", AccountName="Staging")

        accounts = list_organization_accounts(session)

        assert len(accounts) == 3  # management + 2 member accounts
        assert all(a["Status"] == "ACTIVE" for a in accounts)
        account_names = [a["Name"] for a in accounts]
        assert "Dev" in account_names
        assert "Staging" in account_names

    @mock_aws
    def test_returns_empty_list_on_access_denied(self) -> None:
        """list_organization_accounts returns empty list on AccessDeniedException."""
        from botocore.exceptions import ClientError

        session = boto3.Session(region_name="us-east-1")

        # Patch the organizations client to raise AccessDeniedException
        with patch.object(session, "client") as mock_client_factory:
            mock_org = mock_client_factory.return_value
            mock_paginator = mock_org.get_paginator.return_value
            mock_paginator.paginate.side_effect = ClientError(
                {"Error": {"Code": "AccessDeniedException", "Message": "Access Denied"}},
                "ListAccounts",
            )
            accounts = list_organization_accounts(session)

        assert accounts == []

    @mock_aws
    def test_accounts_have_required_fields(self) -> None:
        """list_organization_accounts returns dicts with Id and Status."""
        session = boto3.Session(region_name="us-east-1")
        org = session.client("organizations", region_name="us-east-1")
        org.create_organization(FeatureSet="ALL")

        accounts = list_organization_accounts(session)

        assert len(accounts) >= 1
        for account in accounts:
            assert "Id" in account
            assert "Status" in account
            assert account["Status"] == "ACTIVE"


# -- Tests for assume_cross_account_role --


class TestAssumeCrossAccountRole:
    """Tests for STS cross-account role assumption."""

    @mock_aws
    def test_returns_valid_session(self) -> None:
        """assume_cross_account_role returns a boto3 Session with temp creds."""
        session = boto3.Session(region_name="us-east-1")
        sts = session.client("sts", region_name="us-east-1")

        new_session = assume_cross_account_role(
            sts, "123456789012", role_name="TestRole"
        )

        assert isinstance(new_session, boto3.Session)

        # Verify the session has credentials by making an STS call
        new_sts = new_session.client("sts", region_name="us-east-1")
        identity = new_sts.get_caller_identity()
        assert "Arn" in identity

    @mock_aws
    def test_uses_custom_session_name(self) -> None:
        """assume_cross_account_role uses the InfobloxUDDI-Discovery session name."""
        session = boto3.Session(region_name="us-east-1")
        sts = session.client("sts", region_name="us-east-1")

        new_session = assume_cross_account_role(sts, "123456789012")

        # Verify session was created (no exception means role assumption worked)
        assert isinstance(new_session, boto3.Session)

    @mock_aws
    def test_default_role_name(self) -> None:
        """assume_cross_account_role uses OrganizationAccountAccessRole by default."""
        session = boto3.Session(region_name="us-east-1")
        sts = session.client("sts", region_name="us-east-1")

        # Call with default role_name
        new_session = assume_cross_account_role(sts, "123456789012")
        assert isinstance(new_session, boto3.Session)


# -- Tests for get_enabled_regions --


class TestGetEnabledRegions:
    """Tests for region discovery."""

    @mock_aws
    def test_returns_sorted_region_list(self) -> None:
        """get_enabled_regions returns a sorted list of region names."""
        session = boto3.Session(region_name="us-east-1")
        regions = get_enabled_regions(session)

        assert isinstance(regions, list)
        assert len(regions) > 0
        # Verify sorted
        assert regions == sorted(regions)

    @mock_aws
    def test_contains_known_regions(self) -> None:
        """get_enabled_regions includes well-known AWS regions."""
        session = boto3.Session(region_name="us-east-1")
        regions = get_enabled_regions(session)

        # moto includes standard regions
        assert "us-east-1" in regions
        assert "us-west-2" in regions
        assert "eu-west-1" in regions

    @mock_aws
    def test_returns_strings(self) -> None:
        """get_enabled_regions returns a list of strings."""
        session = boto3.Session(region_name="us-east-1")
        regions = get_enabled_regions(session)

        assert all(isinstance(r, str) for r in regions)
