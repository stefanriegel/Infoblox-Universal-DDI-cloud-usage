"""AWS discovery provider implementing the DiscoveryProvider ABC.

Connects to the Phase 1 orchestrator by implementing list_accounts()
and discover_account(). Supports multi-account discovery via Organizations
with include/exclude filtering and single-account fallback.
"""

from __future__ import annotations

import sys

import boto3

from cloud_usage.discovery.provider import DiscoveryProvider
from cloud_usage.providers.aws.organizations import (
    assume_cross_account_role,
    list_organization_accounts,
)
from cloud_usage.providers.aws.regions import get_enabled_regions
from cloud_usage.schema.resource import CloudResource


class AWSDiscoveryProvider(DiscoveryProvider):
    """AWS implementation of the discovery provider interface.

    Lists accounts via Organizations (with single-account fallback),
    applies include/exclude filtering, and discovers resources across
    all enabled regions per account.

    Args:
        session: Authenticated boto3 session (management account or single account).
        role_name: Name of the cross-account role for Organizations mode.
        include_accounts: If provided, only scan these account IDs.
        exclude_accounts: If provided, exclude these account IDs from scan.
    """

    def __init__(
        self,
        session: boto3.Session,
        role_name: str = "OrganizationAccountAccessRole",
        include_accounts: list[str] | None = None,
        exclude_accounts: list[str] | None = None,
    ) -> None:
        self._session = session
        self._role_name = role_name
        self._include = include_accounts
        self._exclude = exclude_accounts

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "aws"

    def list_accounts(self) -> list[str]:
        """List all accounts to scan, with include/exclude filtering.

        Attempts Organizations API first. If empty (Organizations unavailable),
        falls back to the single current account via STS get_caller_identity.
        Then applies include/exclude filtering (include takes precedence).

        Returns:
            Filtered list of AWS account ID strings.
        """
        org_accounts = list_organization_accounts(self._session)

        if org_accounts:
            account_ids = [a["Id"] for a in org_accounts]
        else:
            # Fallback to single account
            sys.stderr.write(
                "WARNING: Organizations API unavailable, scanning single account only\n"
            )
            sts = self._session.client("sts")
            identity = sts.get_caller_identity()
            account_ids = [identity["Account"]]

        # Apply filtering: include takes precedence over exclude
        if self._include is not None:
            include_set = set(self._include)
            account_ids = [a for a in account_ids if a in include_set]
        elif self._exclude is not None:
            exclude_set = set(self._exclude)
            account_ids = [a for a in account_ids if a not in exclude_set]

        return account_ids

    def discover_account(self, account_id: str) -> list[CloudResource]:
        """Discover all resources in a single AWS account.

        Creates an account-specific session (assumes cross-account role if
        the account differs from the current session's account), discovers
        all enabled regions, and runs collectors. Currently returns an
        empty list -- resource collectors will be wired in Plan 06.

        Args:
            account_id: AWS account ID to scan.

        Returns:
            List of discovered CloudResource instances (empty until Plan 06
            wires collectors).
        """
        # Determine if we need cross-account role assumption
        sts = self._session.client("sts")
        current_account = sts.get_caller_identity()["Account"]

        if account_id != current_account:
            account_session = assume_cross_account_role(
                sts, account_id, role_name=self._role_name
            )
        else:
            account_session = self._session

        # Get all enabled regions for this account
        _regions = get_enabled_regions(account_session)

        # TODO(Plan 06): Wire resource collectors here.
        # Each collector will be called per-region and results merged.
        # Collectors: ec2, route53, dhcp, rds, elasticache, ecs, eks,
        #             lambda, redshift, elb, s3, ebs
        return []
