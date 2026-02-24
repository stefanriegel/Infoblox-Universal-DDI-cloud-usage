"""Azure hybrid networking and infrastructure resource collectors.

Discovers load balancers, application gateways, firewalls, NAT gateways,
private endpoints, VNet peerings, ExpressRoute circuits, VPN gateways,
Virtual WAN hubs, and Bastion hosts. All collectors use @retry_with_backoff
and return list[CloudResource].
"""

from __future__ import annotations

import logging
from typing import Any

from cloud_usage.providers.azure.utils import _extract_resource_group
from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


@retry_with_backoff(max_retries=3)
def collect_azure_load_balancers(
    network_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all load balancers in a subscription.

    Uses network_client.load_balancers.list_all() for subscription-level
    enumeration. Extracts IPs from frontend_ip_configurations. Detects
    public vs internal LB type based on frontend config.

    Args:
        network_client: Azure NetworkManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-lb".
    """
    resources: list[CloudResource] = []

    for lb in network_client.load_balancers.list_all():
        rg = _extract_resource_group(lb.id)

        ip_addresses: list[str] = []
        lb_type = "internal"

        for fe_config in (lb.frontend_ip_configurations or []):
            if fe_config.private_ip_address:
                ip_addresses.append(fe_config.private_ip_address)
            if fe_config.public_ip_address:
                lb_type = "public"

        resources.append(
            CloudResource(
                resource_id=lb.id,
                resource_type="azure-lb",
                provider="azure",
                account_id=subscription_id,
                region=lb.location,
                name=lb.name,
                ip_addresses=ip_addresses,
                tags=dict(lb.tags) if lb.tags else {},
                details={
                    "resource_group": rg,
                    "lb_type": lb_type,
                },
            )
        )

    logger.debug(
        "Discovered %d load balancers in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_app_gateways(
    network_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all application gateways in a subscription.

    Uses network_client.application_gateways.list_all() for subscription-level
    enumeration. Extracts private IPs from frontend_ip_configurations.

    Args:
        network_client: Azure NetworkManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-app-gateway".
    """
    resources: list[CloudResource] = []

    for agw in network_client.application_gateways.list_all():
        rg = _extract_resource_group(agw.id)

        ip_addresses: list[str] = []
        for fe_config in (agw.frontend_ip_configurations or []):
            if fe_config.private_ip_address:
                ip_addresses.append(fe_config.private_ip_address)

        sku_name = ""
        if agw.sku:
            sku_name = agw.sku.name or ""

        resources.append(
            CloudResource(
                resource_id=agw.id,
                resource_type="azure-app-gateway",
                provider="azure",
                account_id=subscription_id,
                region=agw.location,
                name=agw.name,
                ip_addresses=ip_addresses,
                tags=dict(agw.tags) if agw.tags else {},
                details={
                    "resource_group": rg,
                    "sku_name": sku_name,
                },
            )
        )

    logger.debug(
        "Discovered %d application gateways in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_firewalls(
    network_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all Azure firewalls in a subscription.

    Uses network_client.azure_firewalls.list_all() for subscription-level
    enumeration. Extracts IPs from ip_configurations.

    Args:
        network_client: Azure NetworkManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-firewall".
    """
    resources: list[CloudResource] = []

    for fw in network_client.azure_firewalls.list_all():
        rg = _extract_resource_group(fw.id)

        ip_addresses: list[str] = []
        for ip_config in (fw.ip_configurations or []):
            if ip_config.private_ip_address:
                ip_addresses.append(ip_config.private_ip_address)

        firewall_policy_id = None
        if fw.firewall_policy:
            firewall_policy_id = fw.firewall_policy.id

        resources.append(
            CloudResource(
                resource_id=fw.id,
                resource_type="azure-firewall",
                provider="azure",
                account_id=subscription_id,
                region=fw.location,
                name=fw.name,
                ip_addresses=ip_addresses,
                tags=dict(fw.tags) if fw.tags else {},
                details={
                    "resource_group": rg,
                    "firewall_policy_id": firewall_policy_id,
                },
            )
        )

    logger.debug(
        "Discovered %d firewalls in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_nat_gateways(
    network_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all NAT gateways in a subscription.

    Uses network_client.nat_gateways.list_all() for subscription-level
    enumeration. NAT gateways reference public IPs by ID; ip_addresses
    is set to empty.

    Args:
        network_client: Azure NetworkManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-nat-gateway".
    """
    resources: list[CloudResource] = []

    for nat_gw in network_client.nat_gateways.list_all():
        rg = _extract_resource_group(nat_gw.id)

        # Extract public IP address IDs for cross-reference
        public_ip_ids: list[str] = []
        for pip_ref in (nat_gw.public_ip_addresses or []):
            if pip_ref.id:
                public_ip_ids.append(pip_ref.id)

        resources.append(
            CloudResource(
                resource_id=nat_gw.id,
                resource_type="azure-nat-gateway",
                provider="azure",
                account_id=subscription_id,
                region=nat_gw.location,
                name=nat_gw.name,
                ip_addresses=[],
                tags=dict(nat_gw.tags) if nat_gw.tags else {},
                details={
                    "resource_group": rg,
                    "public_ip_address_ids": public_ip_ids,
                },
            )
        )

    logger.debug(
        "Discovered %d NAT gateways in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_private_endpoints(
    network_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all private endpoints in a subscription.

    Uses network_client.private_endpoints.list_all() for subscription-level
    enumeration. Per CONTEXT.md: private endpoints are standalone managed
    assets with their own IPs (not deduplicated against linked PaaS resource).

    Extracts IPs from custom_dns_configs or network_interfaces.

    Args:
        network_client: Azure NetworkManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-private-endpoint".
    """
    resources: list[CloudResource] = []

    for pe in network_client.private_endpoints.list_all():
        rg = _extract_resource_group(pe.id)

        ip_addresses: list[str] = []

        # Try custom_dns_configs first for IPs
        for dns_config in (pe.custom_dns_configs or []):
            for ip in (dns_config.ip_addresses or []):
                if ip and ip not in ip_addresses:
                    ip_addresses.append(ip)

        # If no custom DNS configs, try network interfaces
        if not ip_addresses:
            for nic_ref in (pe.network_interfaces or []):
                # NIC IPs are not inline -- reference only
                pass

        # Extract private link service connection ID
        private_link_service_id = None
        for conn in (pe.private_link_service_connections or []):
            if conn.private_link_service_id:
                private_link_service_id = conn.private_link_service_id
                break

        resources.append(
            CloudResource(
                resource_id=pe.id,
                resource_type="azure-private-endpoint",
                provider="azure",
                account_id=subscription_id,
                region=pe.location,
                name=pe.name,
                ip_addresses=ip_addresses,
                tags=dict(pe.tags) if pe.tags else {},
                details={
                    "resource_group": rg,
                    "private_link_service_id": private_link_service_id,
                },
            )
        )

    logger.debug(
        "Discovered %d private endpoints in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_vnet_peerings(
    network_client: Any,
    subscription_id: str,
    vnets: list[CloudResource],
) -> list[CloudResource]:
    """Discover VNet peerings across all VNets.

    Per RESEARCH.md: VNet peerings require per-VNet listing (no
    subscription-level endpoint). Iterates discovered VNets and calls
    virtual_network_peerings.list(rg, vnet_name) per VNet.

    Args:
        network_client: Azure NetworkManagementClient.
        subscription_id: Azure subscription ID.
        vnets: Previously discovered VNet CloudResource list.

    Returns:
        List of CloudResource with resource_type="azure-vnet-peering".
    """
    resources: list[CloudResource] = []

    for vnet in vnets:
        rg = vnet.details.get("resource_group", "")
        vnet_name = vnet.name
        if not rg or not vnet_name:
            continue

        try:
            for peering in network_client.virtual_network_peerings.list(
                rg, vnet_name
            ):
                remote_vnet_id = None
                if peering.remote_virtual_network:
                    remote_vnet_id = peering.remote_virtual_network.id

                resources.append(
                    CloudResource(
                        resource_id=peering.id,
                        resource_type="azure-vnet-peering",
                        provider="azure",
                        account_id=subscription_id,
                        region=vnet.region,
                        name=peering.name,
                        ip_addresses=[],
                        tags={},
                        details={
                            "resource_group": rg,
                            "vnet_id": vnet.resource_id,
                            "remote_vnet_id": remote_vnet_id,
                            "peering_state": peering.peering_state or "",
                        },
                    )
                )
        except Exception:
            logger.warning(
                "Failed to list VNet peerings for %s/%s",
                rg,
                vnet_name,
                exc_info=True,
            )

    logger.debug(
        "Discovered %d VNet peerings in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_express_route_circuits(
    network_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all ExpressRoute circuits in a subscription.

    Uses network_client.express_route_circuits.list_all() for
    subscription-level enumeration.

    Args:
        network_client: Azure NetworkManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-express-route".
    """
    resources: list[CloudResource] = []

    for circuit in network_client.express_route_circuits.list_all():
        rg = _extract_resource_group(circuit.id)

        service_provider_name = ""
        peering_location = ""
        bandwidth = 0
        if circuit.service_provider_properties:
            service_provider_name = circuit.service_provider_properties.service_provider_name or ""
            peering_location = circuit.service_provider_properties.peering_location or ""
            bandwidth = circuit.service_provider_properties.bandwidth_in_mbps or 0

        resources.append(
            CloudResource(
                resource_id=circuit.id,
                resource_type="azure-express-route",
                provider="azure",
                account_id=subscription_id,
                region=circuit.location,
                name=circuit.name,
                ip_addresses=[],
                tags=dict(circuit.tags) if circuit.tags else {},
                details={
                    "resource_group": rg,
                    "service_provider_name": service_provider_name,
                    "peering_location": peering_location,
                    "bandwidth_in_mbps": bandwidth,
                },
            )
        )

    logger.debug(
        "Discovered %d ExpressRoute circuits in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_vpn_gateways(
    network_client: Any,
    subscription_id: str,
    vnets: list[CloudResource],
) -> list[CloudResource]:
    """Discover VPN gateways across unique resource groups.

    Per RESEARCH.md: VPN gateways (virtual_network_gateways) require
    per-resource-group listing. Iterates unique resource groups from
    discovered VNets.

    Args:
        network_client: Azure NetworkManagementClient.
        subscription_id: Azure subscription ID.
        vnets: Previously discovered VNet CloudResource list (used to
            derive unique resource groups).

    Returns:
        List of CloudResource with resource_type="azure-vpn-gateway".
    """
    resources: list[CloudResource] = []

    # Get unique resource groups from VNets
    seen_rgs: set[str] = set()
    for vnet in vnets:
        rg = vnet.details.get("resource_group", "")
        if rg:
            seen_rgs.add(rg)

    for rg in sorted(seen_rgs):
        try:
            for gw in network_client.virtual_network_gateways.list(rg):
                ip_addresses: list[str] = []
                for ip_config in (gw.ip_configurations or []):
                    if ip_config.private_ip_address:
                        ip_addresses.append(ip_config.private_ip_address)

                resources.append(
                    CloudResource(
                        resource_id=gw.id,
                        resource_type="azure-vpn-gateway",
                        provider="azure",
                        account_id=subscription_id,
                        region=gw.location,
                        name=gw.name,
                        ip_addresses=ip_addresses,
                        tags=dict(gw.tags) if gw.tags else {},
                        details={
                            "resource_group": rg,
                            "gateway_type": gw.gateway_type or "",
                            "vpn_type": gw.vpn_type or "",
                        },
                    )
                )
        except Exception:
            logger.warning(
                "Failed to list VPN gateways in resource group %s",
                rg,
                exc_info=True,
            )

    logger.debug(
        "Discovered %d VPN gateways in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_virtual_wan_hubs(
    network_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all Virtual WAN hubs in a subscription.

    Uses network_client.virtual_hubs.list() for subscription-level
    enumeration. Per CONTEXT.md locked decision: discover Virtual WAN hubs
    for complete hybrid networking topology.

    Args:
        network_client: Azure NetworkManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-vwan-hub".
    """
    resources: list[CloudResource] = []

    for hub in network_client.virtual_hubs.list():
        rg = _extract_resource_group(hub.id)

        virtual_wan_id = None
        if hub.virtual_wan:
            virtual_wan_id = hub.virtual_wan.id

        resources.append(
            CloudResource(
                resource_id=hub.id,
                resource_type="azure-vwan-hub",
                provider="azure",
                account_id=subscription_id,
                region=hub.location,
                name=hub.name,
                ip_addresses=[],
                tags=dict(hub.tags) if hub.tags else {},
                details={
                    "resource_group": rg,
                    "virtual_wan_id": virtual_wan_id,
                    "address_prefix": hub.address_prefix or "",
                    "routing_state": hub.routing_state or "",
                    "provisioning_state": hub.provisioning_state or "",
                },
            )
        )

    logger.debug(
        "Discovered %d Virtual WAN hubs in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_bastion_hosts(
    network_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all Bastion hosts in a subscription.

    Uses network_client.bastion_hosts.list() for subscription-level
    enumeration. Extracts IPs from ip_configurations.

    Args:
        network_client: Azure NetworkManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-bastion".
    """
    resources: list[CloudResource] = []

    for bastion in network_client.bastion_hosts.list():
        rg = _extract_resource_group(bastion.id)

        ip_addresses: list[str] = []
        for ip_config in (bastion.ip_configurations or []):
            if hasattr(ip_config, "private_ip_address") and ip_config.private_ip_address:
                ip_addresses.append(ip_config.private_ip_address)

        resources.append(
            CloudResource(
                resource_id=bastion.id,
                resource_type="azure-bastion",
                provider="azure",
                account_id=subscription_id,
                region=bastion.location,
                name=bastion.name,
                ip_addresses=ip_addresses,
                tags=dict(bastion.tags) if bastion.tags else {},
                details={
                    "resource_group": rg,
                    "dns_name": bastion.dns_name or "" if hasattr(bastion, "dns_name") else "",
                },
            )
        )

    logger.debug(
        "Discovered %d Bastion hosts in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources
