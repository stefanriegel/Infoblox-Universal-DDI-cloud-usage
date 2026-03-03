"""GCP compute resource collectors.

Discovers Compute Engine VMs via aggregatedList with private IP extraction
from network_i_p and public IP from access_config nat_i_p (Pitfall 6).
Discovers forwarding rules (load balancers) via aggregatedList with IP
extraction.
"""

from __future__ import annotations

import logging
from typing import Any

from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


@retry_with_backoff(max_retries=3)
def collect_gcp_vms(
    instances_client: Any,
    project_id: str,
) -> list[CloudResource]:
    """Discover all Compute Engine instances in a project via aggregatedList.

    Uses instances_client.aggregated_list() to fetch all VMs across all
    zones in a single API call per project. Extracts private IPs from
    network_i_p and public IPs from access_config nat_i_p per Pitfall 6
    (CRITICAL: GCP SDK uses network_i_p not network_ip).

    Args:
        instances_client: compute_v1.InstancesClient instance.
        project_id: GCP project ID.

    Returns:
        List of CloudResource with resource_type="gcp-vm".
    """
    from google.cloud import compute_v1

    resources: list[CloudResource] = []

    request = compute_v1.AggregatedListInstancesRequest(project=project_id)
    for zone_key, scoped_list in instances_client.aggregated_list(request=request):
        # zone_key format: "zones/us-central1-a"
        if not scoped_list.instances:
            continue

        zone_name = zone_key.split("/")[-1]
        # Extract region from zone: "us-central1-a" -> "us-central1"
        region = zone_name.rsplit("-", 1)[0] if "-" in zone_name else "global"

        for instance in scoped_list.instances:
            # NIC count for reference algorithm (stored in details for counter)
            ifaces = list(instance.network_interfaces or [])
            iface_count = len(ifaces)

            # IP extraction per Pitfall 6: use network_i_p (not network_ip)
            ip_addresses: list[str] = []
            for iface in ifaces:
                if iface.network_i_p:
                    ip_addresses.append(iface.network_i_p)
                for ac in (iface.access_configs or []):
                    if ac.nat_i_p:
                        ip_addresses.append(ac.nat_i_p)

            resources.append(
                CloudResource(
                    resource_id=instance.self_link or f"projects/{project_id}/zones/{zone_name}/instances/{instance.name}",
                    resource_type="gcp-vm",
                    provider="gcp",
                    account_id=project_id,
                    region=region,
                    name=instance.name,
                    ip_addresses=ip_addresses,
                    tags=dict(instance.labels) if instance.labels else {},
                    details={
                        "zone": zone_name,
                        "machine_type": (instance.machine_type or "").split("/")[-1],
                        "status": instance.status,
                        "network_interface_count": iface_count,
                    },
                )
            )

    logger.debug(
        "Discovered %d VMs in project %s",
        len(resources),
        project_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_gcp_forwarding_rules(
    forwarding_rules_client: Any,
    project_id: str,
) -> list[CloudResource]:
    """Discover all forwarding rules in a project via aggregatedList.

    Uses forwarding_rules_client.aggregated_list() to fetch all forwarding
    rules across all regions in a single API call per project. Extracts
    IP address from the forwarding rule's IP field.

    Note: The GCP compute SDK field for IP address on forwarding rules is
    ``I_p_address`` (capital I, lowercase p, with underscores) -- this is
    the auto-generated Python name from the proto field ``IPAddress``.

    Args:
        forwarding_rules_client: compute_v1.ForwardingRulesClient instance.
        project_id: GCP project ID.

    Returns:
        List of CloudResource with resource_type="gcp-forwarding-rule".
    """
    from google.cloud import compute_v1

    resources: list[CloudResource] = []

    request = compute_v1.AggregatedListForwardingRulesRequest(project=project_id)
    for region_key, scoped_list in forwarding_rules_client.aggregated_list(request=request):
        if not scoped_list.forwarding_rules:
            continue

        # region_key format: "regions/us-central1" or "global"
        region = region_key.split("/")[-1]

        for rule in scoped_list.forwarding_rules:
            # IP extraction: I_p_address is the SDK field name (from proto IPAddress)
            ip_addresses: list[str] = []
            rule_ip = getattr(rule, "I_p_address", None) or getattr(rule, "i_p_address", None) or getattr(rule, "ip_address", None)
            if rule_ip:
                ip_addresses.append(rule_ip)

            resources.append(
                CloudResource(
                    resource_id=rule.self_link or f"projects/{project_id}/regions/{region}/forwardingRules/{rule.name}",
                    resource_type="gcp-forwarding-rule",
                    provider="gcp",
                    account_id=project_id,
                    region=region,
                    name=rule.name,
                    ip_addresses=ip_addresses,
                    tags=dict(rule.labels) if getattr(rule, "labels", None) else {},
                    details={
                        "load_balancing_scheme": getattr(rule, "load_balancing_scheme", "") or "",
                        "target": (getattr(rule, "target", "") or "").split("/")[-1],
                        "ip_protocol": getattr(rule, "ip_protocol", "") or "",
                    },
                )
            )

    logger.debug(
        "Discovered %d forwarding rules in project %s",
        len(resources),
        project_id,
    )
    return resources
