"""Route53 resource collectors.

Discovers Route53 hosted zones and DNS records. Route53 is a global service
(not per-region), so these collectors set region="global" on all resources.
The route53_client should be created with region_name="us-east-1".
"""

from __future__ import annotations

from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource


@retry_with_backoff(max_retries=3)
def collect_route53_zones(
    route53_client,
    account_id: str,
) -> list[CloudResource]:
    """Discover all Route53 hosted zones in an account.

    Route53 is account-global (not per-region, per Pitfall 1). Each zone
    is classified as public or private based on Config.PrivateZone.

    Args:
        route53_client: boto3 Route53 client (created with us-east-1).
        account_id: AWS account ID owning these zones.

    Returns:
        List of CloudResource with resource_type="route53-zone".
    """
    resources: list[CloudResource] = []
    paginator = route53_client.get_paginator("list_hosted_zones")

    for page in paginator.paginate():
        for zone in page.get("HostedZones", []):
            # Zone ID comes as "/hostedzone/Z1234..." -- strip prefix
            raw_id = zone.get("Id", "")
            zone_id = raw_id.split("/")[-1] if "/" in raw_id else raw_id

            # Zone name has trailing dot -- strip it
            zone_name = zone.get("Name", "").rstrip(".")

            is_private = zone.get("Config", {}).get("PrivateZone", False)

            resources.append(
                CloudResource(
                    resource_id=zone_id,
                    resource_type="route53-zone",
                    provider="aws",
                    account_id=account_id,
                    region="global",
                    name=zone_name,
                    ip_addresses=[],
                    tags={},
                    details={
                        "zone_type": "private" if is_private else "public",
                        "record_count": zone.get("ResourceRecordSetCount", 0),
                    },
                )
            )

    return resources


@retry_with_backoff(max_retries=3)
def collect_route53_records(
    route53_client,
    account_id: str,
    zone_id: str,
    zone_name: str,
) -> list[CloudResource]:
    """Discover all DNS records in a Route53 hosted zone.

    All record types are included (A, AAAA, CNAME, MX, NS, SOA, TXT, SRV,
    etc.) per CONTEXT decision. A records have IPv4 IPs extracted; AAAA
    records have IPv6 IPs extracted. Other types have empty ip_addresses.

    Args:
        route53_client: boto3 Route53 client (created with us-east-1).
        account_id: AWS account ID owning these records.
        zone_id: Route53 hosted zone ID (without /hostedzone/ prefix).
        zone_name: Human-readable zone name (without trailing dot).

    Returns:
        List of CloudResource with resource_type="route53-record".
    """
    resources: list[CloudResource] = []
    paginator = route53_client.get_paginator("list_resource_record_sets")

    for page in paginator.paginate(HostedZoneId=zone_id):
        for record_set in page.get("ResourceRecordSets", []):
            record_name = record_set.get("Name", "").rstrip(".")
            record_type = record_set.get("Type", "")

            # Build unique resource ID from zone, name, and type
            resource_id = f"{zone_id}/{record_name}/{record_type}"

            # Extract IPs for A and AAAA records
            ip_addresses: list[str] = []
            if record_type in ("A", "AAAA"):
                for rr in record_set.get("ResourceRecords", []):
                    value = rr.get("Value", "")
                    if value:
                        ip_addresses.append(value)

            # Check for alias
            has_alias = "AliasTarget" in record_set

            resources.append(
                CloudResource(
                    resource_id=resource_id,
                    resource_type="route53-record",
                    provider="aws",
                    account_id=account_id,
                    region="global",
                    name=record_name,
                    ip_addresses=ip_addresses,
                    tags={},
                    details={
                        "zone_id": zone_id,
                        "zone_name": zone_name,
                        "record_type": record_type,
                        "ttl": record_set.get("TTL"),
                        "alias": has_alias,
                    },
                )
            )

    return resources
