"""AWS discovery provider implementing the DiscoveryProvider ABC.

Connects to the Phase 1 orchestrator by implementing list_accounts()
and discover_account(). Supports multi-account discovery via Organizations
with include/exclude filtering and single-account fallback.
"""

from __future__ import annotations

import logging
import sys

import boto3
from botocore.exceptions import ClientError

from cloud_usage.discovery.provider import DiscoveryProvider
from cloud_usage.providers.aws.collectors.compute import (
    collect_classic_load_balancers,
    collect_ec2_instances,
    collect_ecs_tasks,
    collect_eks_node_groups,
    collect_lambda_functions,
    collect_load_balancers_v2,
)
from cloud_usage.providers.aws.collectors.database import (
    collect_elasticache_clusters,
    collect_rds_instances,
    collect_redshift_clusters,
)
from cloud_usage.providers.aws.collectors.dhcp import collect_dhcp_option_sets
from cloud_usage.providers.aws.collectors.ec2 import (
    collect_eips,
    collect_enis,
    collect_nat_gateways,
    collect_subnets,
    collect_transit_gateways,
    collect_vpcs,
    collect_vpn_gateways,
)
from cloud_usage.providers.aws.collectors.route53 import (
    collect_route53_records,
    collect_route53_zones,
)
from cloud_usage.providers.aws.collectors.token_free import (
    collect_ebs_volumes,
    collect_s3_buckets,
)
from cloud_usage.providers.aws.organizations import (
    assume_cross_account_role,
    list_organization_accounts,
)
from cloud_usage.providers.aws.regions import get_enabled_regions
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


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

        # Cache the current account ID for cross-account role decisions
        sts = self._session.client("sts")
        self._current_account_id = sts.get_caller_identity()["Account"]

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
            account_ids = [self._current_account_id]

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
        all enabled regions, and runs all collectors per region with error
        isolation per resource type.

        Args:
            account_id: AWS account ID to scan.

        Returns:
            List of discovered CloudResource instances across all regions.

        Raises:
            ClientError: If cross-account role assumption fails.
        """
        # Determine if we need cross-account role assumption
        if account_id != self._current_account_id:
            try:
                sts = self._session.client("sts")
                account_session = assume_cross_account_role(
                    sts, account_id, role_name=self._role_name
                )
            except ClientError as exc:
                raise ClientError(
                    exc.response,
                    f"Failed to assume role in account {account_id}",
                ) from exc
        else:
            account_session = self._session

        # Get all enabled regions for this account
        regions = get_enabled_regions(account_session)

        all_resources: list[CloudResource] = []

        # -- Route53: global service, call ONCE per account (Pitfall 1) --
        route53_client = account_session.client("route53", region_name="us-east-1")
        zones = self._safe_collect(
            "route53-zones", account_id, "global",
            collect_route53_zones, route53_client, account_id,
        )
        all_resources.extend(zones)

        # Collect records for each zone
        for zone in zones:
            records = self._safe_collect(
                "route53-records", account_id, "global",
                collect_route53_records, route53_client, account_id,
                zone.resource_id, zone.name,
            )
            all_resources.extend(records)

        # -- S3: global service, call ONCE per account --
        s3_client = account_session.client("s3", region_name="us-east-1")
        s3_buckets = self._safe_collect(
            "s3-buckets", account_id, "global",
            collect_s3_buckets, s3_client, account_id, "us-east-1",
        )
        all_resources.extend(s3_buckets)

        # -- Per-region collectors --
        for region in regions:
            # Create service clients for this region
            ec2_client = account_session.client("ec2", region_name=region)
            ecs_client = account_session.client("ecs", region_name=region)
            eks_client = account_session.client("eks", region_name=region)
            lambda_client = account_session.client("lambda", region_name=region)
            elbv2_client = account_session.client("elbv2", region_name=region)
            elb_client = account_session.client("elb", region_name=region)
            rds_client = account_session.client("rds", region_name=region)
            elasticache_client = account_session.client(
                "elasticache", region_name=region
            )
            redshift_client = account_session.client("redshift", region_name=region)

            # EC2 networking: VPCs, subnets, ENIs, EIPs, gateways
            vpcs = self._safe_collect(
                "vpcs", account_id, region,
                collect_vpcs, ec2_client, account_id, region,
            )
            all_resources.extend(vpcs)

            subnets = self._safe_collect(
                "subnets", account_id, region,
                collect_subnets, ec2_client, account_id, region,
            )
            all_resources.extend(subnets)

            enis = self._safe_collect(
                "enis", account_id, region,
                collect_enis, ec2_client, account_id, region,
            )
            all_resources.extend(enis)

            eips = self._safe_collect(
                "elastic-ips", account_id, region,
                collect_eips, ec2_client, account_id, region,
            )
            all_resources.extend(eips)

            nat_gws = self._safe_collect(
                "nat-gateways", account_id, region,
                collect_nat_gateways, ec2_client, account_id, region,
            )
            all_resources.extend(nat_gws)

            vpn_gws = self._safe_collect(
                "vpn-gateways", account_id, region,
                collect_vpn_gateways, ec2_client, account_id, region,
            )
            all_resources.extend(vpn_gws)

            transit_gws = self._safe_collect(
                "transit-gateways", account_id, region,
                collect_transit_gateways, ec2_client, account_id, region,
            )
            all_resources.extend(transit_gws)

            # DHCP option sets: need VPC DhcpOptionsId set (Pitfall 4)
            vpc_dhcp_ids = {
                v.details.get("dhcp_options_id", "")
                for v in vpcs
                if v.details.get("dhcp_options_id")
            }
            dhcp_opts = self._safe_collect(
                "dhcp-option-sets", account_id, region,
                collect_dhcp_option_sets, ec2_client, account_id, region,
                vpc_dhcp_ids,
            )
            all_resources.extend(dhcp_opts)

            # Compute: EC2 instances
            ec2_instances = self._safe_collect(
                "ec2-instances", account_id, region,
                collect_ec2_instances, ec2_client, account_id, region,
            )
            all_resources.extend(ec2_instances)

            # ECS tasks (needs both ecs and ec2 clients)
            ecs_tasks = self._safe_collect(
                "ecs-tasks", account_id, region,
                collect_ecs_tasks, ecs_client, ec2_client, account_id, region,
            )
            all_resources.extend(ecs_tasks)

            # EKS node groups
            eks_ngs = self._safe_collect(
                "eks-nodegroups", account_id, region,
                collect_eks_node_groups, eks_client, account_id, region,
            )
            all_resources.extend(eks_ngs)

            # Lambda (VPC-attached only)
            lambdas = self._safe_collect(
                "lambda-functions", account_id, region,
                collect_lambda_functions, lambda_client, account_id, region,
            )
            all_resources.extend(lambdas)

            # Load balancers: ALB/NLB
            elbv2s = self._safe_collect(
                "load-balancers-v2", account_id, region,
                collect_load_balancers_v2, elbv2_client, account_id, region,
            )
            all_resources.extend(elbv2s)

            # Classic load balancers
            clbs = self._safe_collect(
                "classic-load-balancers", account_id, region,
                collect_classic_load_balancers, elb_client, account_id, region,
            )
            all_resources.extend(clbs)

            # Database: RDS
            rds_instances = self._safe_collect(
                "rds-instances", account_id, region,
                collect_rds_instances, rds_client, account_id, region,
            )
            all_resources.extend(rds_instances)

            # ElastiCache
            elasticache_clusters = self._safe_collect(
                "elasticache-clusters", account_id, region,
                collect_elasticache_clusters, elasticache_client, account_id, region,
            )
            all_resources.extend(elasticache_clusters)

            # Redshift
            redshift_clusters = self._safe_collect(
                "redshift-clusters", account_id, region,
                collect_redshift_clusters, redshift_client, account_id, region,
            )
            all_resources.extend(redshift_clusters)

            # Token-free: EBS volumes
            ebs_vols = self._safe_collect(
                "ebs-volumes", account_id, region,
                collect_ebs_volumes, ec2_client, account_id, region,
            )
            all_resources.extend(ebs_vols)

        logger.info(
            "Discovered %d resources in account %s across %d regions",
            len(all_resources),
            account_id,
            len(regions),
        )
        return all_resources

    @staticmethod
    def _safe_collect(
        resource_type: str,
        account_id: str,
        region: str,
        collector_fn,
        *args,
    ) -> list[CloudResource]:
        """Call a collector function with error isolation.

        If the collector raises an exception, logs a warning and returns
        an empty list instead of propagating the error. This ensures that
        a failure in one resource type for one region does not prevent
        discovery of other resource types.

        Args:
            resource_type: Human-readable resource type name for logging.
            account_id: AWS account ID being scanned.
            region: AWS region being scanned.
            collector_fn: The collector function to call.
            *args: Arguments to pass to the collector function.

        Returns:
            List of discovered CloudResource instances, or empty on failure.
        """
        try:
            return collector_fn(*args)
        except Exception:
            logger.warning(
                "Failed to collect %s in %s/%s",
                resource_type,
                account_id,
                region,
                exc_info=True,
            )
            sys.stderr.write(
                f"WARNING: Failed to collect {resource_type} "
                f"in {account_id}/{region}. Continuing.\n"
            )
            return []
