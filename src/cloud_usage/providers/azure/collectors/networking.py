"""Azure networking resource collectors.

Discovers VNets, subnets, DHCP configs (extracted from VNet properties),
NICs, and public IPs. All functions return list[CloudResource] and use
subscription-level list_all() where available. Subnets require per-VNet
iteration (no subscription-level list method).
"""

from __future__ import annotations

from cloud_usage.providers.azure.utils import _extract_resource_group
from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource


@retry_with_backoff(max_retries=3)
def collect_azure_vnets(
    network_client,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all VNets in a subscription.

    Uses network_client.virtual_networks.list_all() for subscription-level
    enumeration. Extracts address prefixes and DHCP DNS servers from VNet
    properties for downstream DHCP config extraction.

    Args:
        network_client: Azure NetworkManagementClient for the subscription.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-vnet".
    """
    resources: list[CloudResource] = []

    for vnet in network_client.virtual_networks.list_all():
        rg = _extract_resource_group(vnet.id)

        address_prefixes: list[str] = []
        if vnet.address_space and vnet.address_space.address_prefixes:
            address_prefixes = list(vnet.address_space.address_prefixes)

        dhcp_dns_servers: list[str] = []
        if vnet.dhcp_options and vnet.dhcp_options.dns_servers:
            dhcp_dns_servers = list(vnet.dhcp_options.dns_servers)

        resources.append(
            CloudResource(
                resource_id=vnet.id,
                resource_type="azure-vnet",
                provider="azure",
                account_id=subscription_id,
                region=vnet.location,
                name=vnet.name,
                ip_addresses=[],
                tags=dict(vnet.tags) if vnet.tags else {},
                details={
                    "resource_group": rg,
                    "address_prefixes": address_prefixes,
                    "dhcp_dns_servers": dhcp_dns_servers,
                },
            )
        )

    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_subnets(
    network_client,
    subscription_id: str,
    vnets: list[CloudResource],
) -> list[CloudResource]:
    """Discover all subnets within discovered VNets.

    Subnets have no subscription-level list method (Pitfall 1). Iterates
    over discovered VNets and calls subnets.list(rg, vnet_name) per VNet.
    Skips VNets with missing resource_group.

    Args:
        network_client: Azure NetworkManagementClient for the subscription.
        subscription_id: Azure subscription ID.
        vnets: Previously discovered VNet CloudResource list.

    Returns:
        List of CloudResource with resource_type="azure-subnet".
    """
    resources: list[CloudResource] = []

    for vnet in vnets:
        rg = vnet.details.get("resource_group", "")
        vnet_name = vnet.name
        if not rg or not vnet_name:
            continue

        for subnet in network_client.subnets.list(rg, vnet_name):
            resources.append(
                CloudResource(
                    resource_id=subnet.id,
                    resource_type="azure-subnet",
                    provider="azure",
                    account_id=subscription_id,
                    region=vnet.region,
                    name=subnet.name,
                    ip_addresses=[],
                    tags={},
                    details={
                        "resource_group": rg,
                        "vnet_id": vnet.resource_id,
                        "address_prefix": subnet.address_prefix or "",
                    },
                )
            )

    return resources


def collect_azure_dhcp_configs(
    vnets: list[CloudResource],
) -> list[CloudResource]:
    """Extract DHCP configurations from VNets with custom DNS servers.

    Azure has no standalone DHCP resource. DHCP options are embedded in
    VNet properties. This function creates separate CloudResource instances
    for VNets that have dhcp_options.dns_servers configured.

    No @retry_with_backoff needed -- pure data extraction, no API call.

    Args:
        vnets: Previously discovered VNet CloudResource list.

    Returns:
        List of CloudResource with resource_type="azure-dhcp-config".
    """
    resources: list[CloudResource] = []

    for vnet in vnets:
        dns_servers = vnet.details.get("dhcp_dns_servers", [])
        if not dns_servers:
            continue

        resources.append(
            CloudResource(
                resource_id=f"{vnet.resource_id}/dhcpOptions",
                resource_type="azure-dhcp-config",
                provider="azure",
                account_id=vnet.account_id,
                region=vnet.region,
                name=f"{vnet.name}-dhcp",
                ip_addresses=[],
                tags={},
                details={
                    "resource_group": vnet.details.get("resource_group", ""),
                    "vnet_id": vnet.resource_id,
                    "dns_servers": list(dns_servers),
                },
            )
        )

    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_nics(
    network_client,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all NICs in a subscription.

    Uses network_client.network_interfaces.list_all() for subscription-level
    enumeration. Extracts private IPs from ip_configurations. Public IPs
    are NOT resolved inline (Pitfall 4) -- collected separately.

    NICs are standalone managed assets. Unattached NICs with IPs count
    toward token estimation.

    Args:
        network_client: Azure NetworkManagementClient for the subscription.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-nic".
    """
    resources: list[CloudResource] = []

    for nic in network_client.network_interfaces.list_all():
        rg = _extract_resource_group(nic.id)

        # Extract private IPs from ip_configurations
        ip_addresses: list[str] = []
        ip_config_count = 0
        for ip_config in (nic.ip_configurations or []):
            ip_config_count += 1
            if ip_config.private_ip_address:
                ip_addresses.append(ip_config.private_ip_address)

        # Get attached VM ID if present
        vm_id = nic.virtual_machine.id if nic.virtual_machine else None

        resources.append(
            CloudResource(
                resource_id=nic.id,
                resource_type="azure-nic",
                provider="azure",
                account_id=subscription_id,
                region=nic.location,
                name=nic.name,
                ip_addresses=ip_addresses,
                tags=dict(nic.tags) if nic.tags else {},
                details={
                    "resource_group": rg,
                    "vm_id": vm_id,
                    "ip_configuration_count": ip_config_count,
                },
            )
        )

    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_public_ips(
    network_client,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all public IP addresses in a subscription.

    Uses network_client.public_ip_addresses.list_all() for subscription-level
    enumeration. Public IPs are standalone managed assets.

    Args:
        network_client: Azure NetworkManagementClient for the subscription.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-public-ip".
    """
    resources: list[CloudResource] = []

    for pip in network_client.public_ip_addresses.list_all():
        rg = _extract_resource_group(pip.id)

        ip_addresses: list[str] = []
        if pip.ip_address:
            ip_addresses.append(pip.ip_address)

        # Get ip_configuration ID for cross-reference to NIC
        ip_config_id = None
        if pip.ip_configuration:
            ip_config_id = pip.ip_configuration.id

        resources.append(
            CloudResource(
                resource_id=pip.id,
                resource_type="azure-public-ip",
                provider="azure",
                account_id=subscription_id,
                region=pip.location,
                name=pip.name,
                ip_addresses=ip_addresses,
                tags=dict(pip.tags) if pip.tags else {},
                details={
                    "resource_group": rg,
                    "allocation_method": pip.public_ip_allocation_method or "",
                    "ip_configuration_id": ip_config_id,
                },
            )
        )

    return resources
