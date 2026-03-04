"""AWS IPAM resource collectors.

Discovers all 5 IPAM sub-types from the reference implementation:
IPAMs, IPAM Scopes, IPAM Pools, IPAM Resource Discoveries, and
IPAM Resource Discovery Associations.

IPAM is an account-global feature (not per-region). All collectors use an EC2
client created with region_name="us-east-1" and set region="global" on all
returned resources. Callers must pass a global EC2 client — NOT a per-region
ec2 client — to avoid getting empty results (see Pitfall 4 in RESEARCH.md).

If the account has not enabled IPAM, the API calls return empty pages.
_safe_collect() in provider.py handles ClientError gracefully.
"""

from __future__ import annotations

from cloud_usage.providers.aws.collectors.ec2 import _get_name_tag, _tags_to_dict
from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource


@retry_with_backoff(max_retries=3)
def collect_ipams(
    ec2_client,
    account_id: str,
) -> list[CloudResource]:
    """Discover all IPAMs in an account (AWSG-03).

    Args:
        ec2_client: boto3 EC2 client created with region_name="us-east-1" (global).
        account_id: AWS account ID owning these resources.

    Returns:
        List of CloudResource with resource_type="aws-ipam".
    """
    resources: list[CloudResource] = []
    paginator = ec2_client.get_paginator("describe_ipams")

    for page in paginator.paginate():
        for ipam in page.get("Ipams", []):
            tags = ipam.get("Tags", [])
            resources.append(
                CloudResource(
                    resource_id=ipam["IpamId"],
                    resource_type="aws-ipam",
                    provider="aws",
                    account_id=account_id,
                    region="global",
                    name=_get_name_tag(tags),
                    ip_addresses=[],
                    tags=_tags_to_dict(tags),
                    details={
                        "state": ipam.get("State", ""),
                        "scope_count": ipam.get("ScopeCount", 0),
                        "operating_regions": [
                            r["RegionName"]
                            for r in ipam.get("OperatingRegions", [])
                        ],
                    },
                )
            )
    return resources


@retry_with_backoff(max_retries=3)
def collect_ipam_scopes(
    ec2_client,
    account_id: str,
) -> list[CloudResource]:
    """Discover all IPAM Scopes in an account (AWSG-03).

    Args:
        ec2_client: boto3 EC2 client created with region_name="us-east-1" (global).
        account_id: AWS account ID owning these resources.

    Returns:
        List of CloudResource with resource_type="aws-ipam-scope".
    """
    resources: list[CloudResource] = []
    paginator = ec2_client.get_paginator("describe_ipam_scopes")

    for page in paginator.paginate():
        for scope in page.get("IpamScopes", []):
            tags = scope.get("Tags", [])
            resources.append(
                CloudResource(
                    resource_id=scope["IpamScopeId"],
                    resource_type="aws-ipam-scope",
                    provider="aws",
                    account_id=account_id,
                    region="global",
                    name=_get_name_tag(tags),
                    ip_addresses=[],
                    tags=_tags_to_dict(tags),
                    details={
                        "ipam_scope_type": scope.get("IpamScopeType", ""),
                        "state": scope.get("State", ""),
                    },
                )
            )
    return resources


@retry_with_backoff(max_retries=3)
def collect_ipam_pools(
    ec2_client,
    account_id: str,
) -> list[CloudResource]:
    """Discover all IPAM Pools in an account (AWSG-03).

    Args:
        ec2_client: boto3 EC2 client created with region_name="us-east-1" (global).
        account_id: AWS account ID owning these resources.

    Returns:
        List of CloudResource with resource_type="aws-ipam-pool".
    """
    resources: list[CloudResource] = []
    paginator = ec2_client.get_paginator("describe_ipam_pools")

    for page in paginator.paginate():
        for pool in page.get("IpamPools", []):
            tags = pool.get("Tags", [])
            resources.append(
                CloudResource(
                    resource_id=pool["IpamPoolId"],
                    resource_type="aws-ipam-pool",
                    provider="aws",
                    account_id=account_id,
                    region="global",
                    name=_get_name_tag(tags),
                    ip_addresses=[],
                    tags=_tags_to_dict(tags),
                    details={
                        "address_family": pool.get("AddressFamily", ""),
                        "state": pool.get("State", ""),
                    },
                )
            )
    return resources


@retry_with_backoff(max_retries=3)
def collect_ipam_resource_discoveries(
    ec2_client,
    account_id: str,
) -> list[CloudResource]:
    """Discover all IPAM Resource Discoveries in an account (AWSG-03).

    Args:
        ec2_client: boto3 EC2 client created with region_name="us-east-1" (global).
        account_id: AWS account ID owning these resources.

    Returns:
        List of CloudResource with resource_type="aws-ipam-resource-discovery".
    """
    resources: list[CloudResource] = []
    paginator = ec2_client.get_paginator("describe_ipam_resource_discoveries")

    for page in paginator.paginate():
        for rd in page.get("IpamResourceDiscoveries", []):
            tags = rd.get("Tags", [])
            resources.append(
                CloudResource(
                    resource_id=rd["IpamResourceDiscoveryId"],
                    resource_type="aws-ipam-resource-discovery",
                    provider="aws",
                    account_id=account_id,
                    region="global",
                    name=_get_name_tag(tags),
                    ip_addresses=[],
                    tags=_tags_to_dict(tags),
                    details={
                        "is_default": rd.get("IsDefault", False),
                        "state": rd.get("State", ""),
                    },
                )
            )
    return resources


@retry_with_backoff(max_retries=3)
def collect_ipam_resource_discovery_associations(
    ec2_client,
    account_id: str,
) -> list[CloudResource]:
    """Discover all IPAM Resource Discovery Associations in an account (AWSG-03).

    Args:
        ec2_client: boto3 EC2 client created with region_name="us-east-1" (global).
        account_id: AWS account ID owning these resources.

    Returns:
        List of CloudResource with resource_type="aws-ipam-resource-discovery-association".
    """
    resources: list[CloudResource] = []
    paginator = ec2_client.get_paginator(
        "describe_ipam_resource_discovery_associations"
    )

    for page in paginator.paginate():
        for assoc in page.get("IpamResourceDiscoveryAssociations", []):
            tags = assoc.get("Tags", [])
            resources.append(
                CloudResource(
                    resource_id=assoc["IpamResourceDiscoveryAssociationId"],
                    resource_type="aws-ipam-resource-discovery-association",
                    provider="aws",
                    account_id=account_id,
                    region="global",
                    name=_get_name_tag(tags),
                    ip_addresses=[],
                    tags=_tags_to_dict(tags),
                    details={
                        "ipam_id": assoc.get("IpamId", ""),
                        "state": assoc.get("State", ""),
                    },
                )
            )
    return resources
