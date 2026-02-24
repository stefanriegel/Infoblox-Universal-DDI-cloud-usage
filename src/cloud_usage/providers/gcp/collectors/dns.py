"""GCP Cloud DNS resource collectors.

Discovers Cloud DNS zones (per-project) and DNS records (per-zone) with
full record type enumeration including SOA and NS. A/AAAA record IP
addresses are extracted into the ip_addresses field. Per-zone error
isolation prevents single zone failure from blocking entire project.
"""

from __future__ import annotations

import logging

from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


@retry_with_backoff(max_retries=3)
def collect_gcp_dns_zones(
    dns_client,
    project_id: str,
) -> list[CloudResource]:
    """Discover all Cloud DNS zones in a GCP project.

    Uses dns_client.list_zones() for per-project enumeration. DNS zones
    are global resources. The dns_client is created per-project (Pitfall 1:
    dns.Client requires project= at init).

    Args:
        dns_client: google.cloud.dns.Client bound to the project.
        project_id: GCP project ID.

    Returns:
        List of CloudResource with resource_type="gcp-dns-zone".
    """
    resources: list[CloudResource] = []

    for zone in dns_client.list_zones():
        resources.append(
            CloudResource(
                resource_id=f"projects/{project_id}/managedZones/{zone.name}",
                resource_type="gcp-dns-zone",
                provider="gcp",
                account_id=project_id,
                region="global",
                name=zone.dns_name,
                ip_addresses=[],
                tags={},
                details={
                    "zone_name": zone.name,
                    "dns_name": zone.dns_name,
                    "visibility": getattr(zone, "visibility", "public"),
                },
            )
        )

    return resources


@retry_with_backoff(max_retries=3)
def collect_gcp_dns_records(
    dns_client,
    project_id: str,
    zones: list[CloudResource],
) -> list[CloudResource]:
    """Discover all DNS records across discovered zones.

    Iterates over discovered zones and enumerates all record sets per zone
    via zone_obj.list_resource_record_sets(). All record types are included
    (SOA, NS, A, AAAA, CNAME, MX, TXT, SRV, etc.) per CONTEXT.md decision.

    A/AAAA records have their IP addresses extracted into the ip_addresses
    field. Per-zone error isolation ensures one zone failure does not block
    other zones from being collected.

    Args:
        dns_client: google.cloud.dns.Client bound to the project.
        project_id: GCP project ID.
        zones: Previously discovered DNS zone CloudResource list.

    Returns:
        List of CloudResource with resource_type="gcp-dns-record".
    """
    resources: list[CloudResource] = []

    for zone in zones:
        zone_name = zone.details.get("zone_name", "")
        if not zone_name:
            continue

        try:
            zone_obj = dns_client.zone(zone_name)

            for record_set in zone_obj.list_resource_record_sets():
                record_type = record_set.record_type

                # Extract IPs from A and AAAA records
                ip_addresses: list[str] = []
                if record_type in ("A", "AAAA") and record_set.rrdatas:
                    ip_addresses = list(record_set.rrdatas)

                resources.append(
                    CloudResource(
                        resource_id=f"projects/{project_id}/managedZones/{zone_name}/{record_set.name}/{record_type}",
                        resource_type="gcp-dns-record",
                        provider="gcp",
                        account_id=project_id,
                        region="global",
                        name=record_set.name,
                        ip_addresses=ip_addresses,
                        tags={},
                        details={
                            "record_type": record_type,
                            "ttl": record_set.ttl,
                            "zone_name": zone_name,
                        },
                    )
                )
        except Exception as exc:
            logger.warning(
                "Failed to list records for DNS zone %s in project %s: %s",
                zone_name,
                project_id,
                exc,
            )
            continue

    return resources
