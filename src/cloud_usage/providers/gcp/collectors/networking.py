"""GCP networking resource collectors.

Discovers VPC networks (global list), subnets (aggregatedList across all
regions), and reserved IPs (regional aggregatedList + global list). All
functions return list[CloudResource] and use @retry_with_backoff for
transient error resilience.
"""

from __future__ import annotations

from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource


@retry_with_backoff(max_retries=3)
def collect_gcp_vpcs(
    networks_client,
    project_id: str,
) -> list[CloudResource]:
    """Discover all VPC networks in a GCP project.

    Uses networks_client.list() for global enumeration (VPC networks are
    global resources, no aggregatedList available). Each VPC is a DDI
    container object with no associated IP addresses.

    Args:
        networks_client: compute_v1.NetworksClient for the project.
        project_id: GCP project ID.

    Returns:
        List of CloudResource with resource_type="gcp-vpc".
    """
    resources: list[CloudResource] = []

    for network in networks_client.list(project=project_id):
        resource_id = (
            network.self_link
            if getattr(network, "self_link", None)
            else f"projects/{project_id}/global/networks/{network.name}"
        )

        resources.append(
            CloudResource(
                resource_id=resource_id,
                resource_type="gcp-vpc",
                provider="gcp",
                account_id=project_id,
                region="global",
                name=network.name,
                ip_addresses=[],
                tags=dict(network.labels) if getattr(network, "labels", None) else {},
                details={
                    "auto_create_subnetworks": getattr(
                        network, "auto_create_subnetworks", None
                    ),
                },
            )
        )

    return resources


@retry_with_backoff(max_retries=3)
def collect_gcp_subnets(
    subnetworks_client,
    project_id: str,
) -> list[CloudResource]:
    """Discover all subnets across all regions in a GCP project.

    Uses subnetworks_client.aggregated_list() to enumerate all subnets
    across all regions in a single API call. Empty scoped lists (regions
    with no subnets) are skipped.

    Args:
        subnetworks_client: compute_v1.SubnetworksClient for the project.
        project_id: GCP project ID.

    Returns:
        List of CloudResource with resource_type="gcp-subnet".
    """
    resources: list[CloudResource] = []

    try:
        from google.cloud import compute_v1

        request = compute_v1.AggregatedListSubnetworksRequest(project=project_id)
    except ImportError:
        # Fall back to dict-based request if SDK not available
        request = {"project": project_id}

    for region_key, scoped_list in subnetworks_client.aggregated_list(request=request):
        if not scoped_list.subnetworks:
            continue

        # region_key format: "regions/us-central1"
        region = region_key.split("/")[-1]

        for subnetwork in scoped_list.subnetworks:
            resource_id = (
                subnetwork.self_link
                if getattr(subnetwork, "self_link", None)
                else f"projects/{project_id}/regions/{region}/subnetworks/{subnetwork.name}"
            )

            network_name = ""
            if getattr(subnetwork, "network", None):
                network_name = subnetwork.network.split("/")[-1]

            resources.append(
                CloudResource(
                    resource_id=resource_id,
                    resource_type="gcp-subnet",
                    provider="gcp",
                    account_id=project_id,
                    region=region,
                    name=subnetwork.name,
                    ip_addresses=[],
                    tags=dict(subnetwork.labels) if getattr(subnetwork, "labels", None) else {},
                    details={
                        "ip_cidr_range": getattr(subnetwork, "ip_cidr_range", ""),
                        "network": network_name,
                    },
                )
            )

    return resources


@retry_with_backoff(max_retries=3)
def collect_gcp_reserved_ips(
    addresses_client,
    global_addresses_client,
    project_id: str,
) -> list[CloudResource]:
    """Discover all reserved IP addresses (regional + global) in a GCP project.

    Combines two sources:
    - Regional addresses via addresses_client.aggregated_list() (one API call).
    - Global addresses via global_addresses_client.list() (one API call).

    DDI-only -- ip_addresses=[] per reference; Compute Addresses are
    Networking Basics, not Address Records. Address details are preserved
    in the details dict for audit/display purposes.

    Args:
        addresses_client: compute_v1.AddressesClient for regional addresses.
        global_addresses_client: compute_v1.GlobalAddressesClient for global addresses.
        project_id: GCP project ID.

    Returns:
        List of CloudResource with resource_type="gcp-reserved-ip".
    """
    resources: list[CloudResource] = []

    # Regional addresses via aggregatedList
    try:
        from google.cloud import compute_v1

        request = compute_v1.AggregatedListAddressesRequest(project=project_id)
    except ImportError:
        request = {"project": project_id}

    for region_key, scoped_list in addresses_client.aggregated_list(request=request):
        if not scoped_list.addresses:
            continue

        region = region_key.split("/")[-1]

        for address in scoped_list.addresses:
            resource_id = (
                address.self_link
                if getattr(address, "self_link", None)
                else f"projects/{project_id}/regions/{region}/addresses/{address.name}"
            )

            resources.append(
                CloudResource(
                    resource_id=resource_id,
                    resource_type="gcp-reserved-ip",
                    provider="gcp",
                    account_id=project_id,
                    region=region,
                    name=address.name,
                    ip_addresses=[],
                    tags=dict(address.labels) if getattr(address, "labels", None) else {},
                    details={
                        "address_type": getattr(address, "address_type", ""),
                        "status": getattr(address, "status", ""),
                        "purpose": getattr(address, "purpose", ""),
                    },
                )
            )

    # Global addresses via list
    for address in global_addresses_client.list(project=project_id):
        resource_id = (
            address.self_link
            if getattr(address, "self_link", None)
            else f"projects/{project_id}/global/addresses/{address.name}"
        )

        resources.append(
            CloudResource(
                resource_id=resource_id,
                resource_type="gcp-reserved-ip",
                provider="gcp",
                account_id=project_id,
                region="global",
                name=address.name,
                ip_addresses=[],
                tags=dict(address.labels) if getattr(address, "labels", None) else {},
                details={
                    "address_type": getattr(address, "address_type", ""),
                    "status": getattr(address, "status", ""),
                    "purpose": getattr(address, "purpose", ""),
                },
            )
        )

    return resources


@retry_with_backoff(max_retries=3)
def collect_gcp_router_nats(
    routers_client,
    project_id: str,
) -> list[CloudResource]:
    """Discover all Router NAT configs across all regions in a GCP project.

    Uses RoutersClient.aggregated_list() to enumerate all Cloud Routers.
    Each NAT configuration on a router produces one DDI object. Routers
    with no NAT configs are skipped. ip_addresses=[] -- DDI topology objects.

    Args:
        routers_client: compute_v1.RoutersClient for the project.
        project_id: GCP project ID.

    Returns:
        List of CloudResource with resource_type="gcp-router-nat".
    """
    resources: list[CloudResource] = []

    for region_key, scoped_list in routers_client.aggregated_list(project=project_id):
        if not scoped_list.routers:
            continue

        region = region_key.split("/")[-1]

        for router in scoped_list.routers:
            nats = getattr(router, "nats", None) or []
            for nat in nats:
                resource_id = (
                    f"projects/{project_id}/regions/{region}"
                    f"/routers/{router.name}/nats/{nat.name}"
                )
                resources.append(
                    CloudResource(
                        resource_id=resource_id,
                        resource_type="gcp-router-nat",
                        provider="gcp",
                        account_id=project_id,
                        region=region,
                        name=nat.name,
                        ip_addresses=[],
                        tags=dict(router.labels) if getattr(router, "labels", None) else {},
                        details={
                            "router_name": router.name,
                        },
                    )
                )

    return resources


@retry_with_backoff(max_retries=3)
def collect_gcp_target_vpn_gateways(
    target_vpn_gateways_client,
    project_id: str,
) -> list[CloudResource]:
    """Discover all Target VPN Gateways (legacy) across all regions in a GCP project.

    Uses TargetVpnGatewaysClient.aggregated_list() for all-region enumeration.
    These are legacy Target VPN Gateways (not HA VPN Gateways). ip_addresses=[]
    -- DDI topology objects in the Networking Basics category.

    Args:
        target_vpn_gateways_client: compute_v1.TargetVpnGatewaysClient.
        project_id: GCP project ID.

    Returns:
        List of CloudResource with resource_type="gcp-target-vpn-gateway".
    """
    resources: list[CloudResource] = []

    for region_key, scoped_list in target_vpn_gateways_client.aggregated_list(project=project_id):
        if not scoped_list.target_vpn_gateways:
            continue

        region = region_key.split("/")[-1]

        for gw in scoped_list.target_vpn_gateways:
            resource_id = (
                gw.self_link
                if getattr(gw, "self_link", None)
                else f"projects/{project_id}/regions/{region}/targetVpnGateways/{gw.name}"
            )
            resources.append(
                CloudResource(
                    resource_id=resource_id,
                    resource_type="gcp-target-vpn-gateway",
                    provider="gcp",
                    account_id=project_id,
                    region=region,
                    name=gw.name,
                    ip_addresses=[],
                    tags=dict(gw.labels) if getattr(gw, "labels", None) else {},
                    details={},
                )
            )

    return resources
