"""AWS Direct Connect resource collectors.

Discovers Direct Connect Gateways. Direct Connect is a global service
(not per-region). The directconnect client should be created with
region_name="us-east-1".

IMPORTANT: Direct Connect API uses camelCase response keys (not PascalCase
like EC2). For example: directConnectGateways, directConnectGatewayId,
directConnectGatewayState, amazonSideAsn, ownerAccount. See Pitfall 3
in RESEARCH.md.
"""

from __future__ import annotations

from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource


@retry_with_backoff(max_retries=3)
def collect_direct_connect_gateways(
    dx_client,
    account_id: str,
) -> list[CloudResource]:
    """Discover all Direct Connect Gateways in an account (AWSG-06).

    Uses the directconnect service client (not EC2). Direct Connect is global
    so this is called once per account in the global section of discover_account().
    The dx_client should be created with region_name="us-east-1".

    NOTE: The Direct Connect API uses camelCase response keys. Access fields as
    gw["directConnectGatewayId"], gw["directConnectGatewayName"], etc. — NOT
    PascalCase like EC2 responses.

    Args:
        dx_client: boto3 directconnect client (created with us-east-1).
        account_id: AWS account ID owning these resources.

    Returns:
        List of CloudResource with resource_type="aws-direct-connect-gateway".
    """
    resources: list[CloudResource] = []
    paginator = dx_client.get_paginator("describe_direct_connect_gateways")

    for page in paginator.paginate():
        for gw in page.get("directConnectGateways", []):
            resources.append(
                CloudResource(
                    resource_id=gw["directConnectGatewayId"],
                    resource_type="aws-direct-connect-gateway",
                    provider="aws",
                    account_id=account_id,
                    region="global",
                    name=gw.get("directConnectGatewayName", ""),
                    ip_addresses=[],
                    tags={},
                    details={
                        "state": gw.get("directConnectGatewayState", ""),
                        "amazon_side_asn": gw.get("amazonSideAsn", 0),
                        "owner_account": gw.get("ownerAccount", ""),
                    },
                )
            )
    return resources
