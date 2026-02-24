"""Azure public and private DNS resource collectors.

Discovers Azure DNS zones (public) and Private DNS zones with full
record enumeration. DNS zones are listed at subscription level; records
require per-zone iteration with resource group context. All DNS resources
use region="global" since DNS is a global service.
"""

from __future__ import annotations

import logging

from cloud_usage.providers.azure.utils import _extract_resource_group
from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


@retry_with_backoff(max_retries=3)
def collect_azure_dns_zones(
    dns_client,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all public DNS zones in a subscription.

    Uses dns_client.zones.list() for subscription-level enumeration.
    DNS zones are global resources.

    Args:
        dns_client: Azure DnsManagementClient for the subscription.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-dns-zone".
    """
    resources: list[CloudResource] = []

    for zone in dns_client.zones.list():
        rg = _extract_resource_group(zone.id)

        record_count = 0
        if hasattr(zone, "number_of_record_sets") and zone.number_of_record_sets is not None:
            record_count = zone.number_of_record_sets

        resources.append(
            CloudResource(
                resource_id=zone.id,
                resource_type="azure-dns-zone",
                provider="azure",
                account_id=subscription_id,
                region="global",
                name=zone.name,
                ip_addresses=[],
                tags=dict(zone.tags) if zone.tags else {},
                details={
                    "resource_group": rg,
                    "zone_type": "public",
                    "record_count": record_count,
                },
            )
        )

    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_dns_records(
    dns_client,
    subscription_id: str,
    zones: list[CloudResource],
) -> list[CloudResource]:
    """Discover all DNS records in public DNS zones.

    Iterates over discovered zones and calls record_sets.list_by_dns_zone()
    per zone (Pitfall 7 -- records require zone context). Uses full ARM
    resource ID for globally unique resource_id. Per-zone error isolation
    ensures one zone failure does not block others.

    Args:
        dns_client: Azure DnsManagementClient for the subscription.
        subscription_id: Azure subscription ID.
        zones: Previously discovered public DNS zone CloudResource list.

    Returns:
        List of CloudResource with resource_type="azure-dns-record".
    """
    resources: list[CloudResource] = []

    for zone in zones:
        rg = zone.details.get("resource_group", "")
        if not rg:
            continue

        try:
            for record_set in dns_client.record_sets.list_by_dns_zone(rg, zone.name):
                # Parse record type from ARM type path
                # e.g., "Microsoft.Network/dnszones/A" -> "A"
                record_type = ""
                if record_set.type:
                    record_type = record_set.type.split("/")[-1]

                resources.append(
                    CloudResource(
                        resource_id=record_set.id,
                        resource_type="azure-dns-record",
                        provider="azure",
                        account_id=subscription_id,
                        region="global",
                        name=record_set.name,
                        ip_addresses=[],
                        tags={},
                        details={
                            "resource_group": rg,
                            "zone_name": zone.name,
                            "record_type": record_type,
                            "ttl": record_set.ttl or 0,
                        },
                    )
                )
        except Exception as exc:
            logger.warning(
                "Failed to list records for DNS zone %s in resource group %s: %s",
                zone.name,
                rg,
                exc,
            )
            continue

    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_private_dns_zones(
    privatedns_client,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all private DNS zones in a subscription.

    Uses privatedns_client.private_zones.list() for subscription-level
    enumeration. Private DNS zones are global resources.

    Args:
        privatedns_client: Azure PrivateDnsManagementClient for the subscription.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-private-dns-zone".
    """
    resources: list[CloudResource] = []

    for zone in privatedns_client.private_zones.list():
        rg = _extract_resource_group(zone.id)

        record_count = 0
        if hasattr(zone, "number_of_record_sets") and zone.number_of_record_sets is not None:
            record_count = zone.number_of_record_sets

        resources.append(
            CloudResource(
                resource_id=zone.id,
                resource_type="azure-private-dns-zone",
                provider="azure",
                account_id=subscription_id,
                region="global",
                name=zone.name,
                ip_addresses=[],
                tags=dict(zone.tags) if zone.tags else {},
                details={
                    "resource_group": rg,
                    "zone_type": "private",
                    "record_count": record_count,
                },
            )
        )

    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_private_dns_records(
    privatedns_client,
    subscription_id: str,
    zones: list[CloudResource],
) -> list[CloudResource]:
    """Discover all DNS records in private DNS zones.

    Iterates over discovered private zones and calls record_sets.list()
    per zone. Uses full ARM resource ID for globally unique resource_id.
    Per-zone error isolation ensures one zone failure does not block others.

    Args:
        privatedns_client: Azure PrivateDnsManagementClient for the subscription.
        subscription_id: Azure subscription ID.
        zones: Previously discovered private DNS zone CloudResource list.

    Returns:
        List of CloudResource with resource_type="azure-private-dns-record".
    """
    resources: list[CloudResource] = []

    for zone in zones:
        rg = zone.details.get("resource_group", "")
        if not rg:
            continue

        try:
            for record_set in privatedns_client.record_sets.list(rg, zone.name):
                # Parse record type from ARM type path
                # e.g., "Microsoft.Network/privateDnsZones/A" -> "A"
                record_type = ""
                if record_set.type:
                    record_type = record_set.type.split("/")[-1]

                resources.append(
                    CloudResource(
                        resource_id=record_set.id,
                        resource_type="azure-private-dns-record",
                        provider="azure",
                        account_id=subscription_id,
                        region="global",
                        name=record_set.name,
                        ip_addresses=[],
                        tags={},
                        details={
                            "resource_group": rg,
                            "zone_name": zone.name,
                            "record_type": record_type,
                            "ttl": record_set.ttl or 0,
                        },
                    )
                )
        except Exception as exc:
            logger.warning(
                "Failed to list records for private DNS zone %s in resource group %s: %s",
                zone.name,
                rg,
                exc,
            )
            continue

    return resources
