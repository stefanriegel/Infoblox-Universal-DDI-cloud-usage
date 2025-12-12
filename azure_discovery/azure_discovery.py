#!/usr/bin/env python3
"""
Azure Cloud Discovery for Infoblox Universal DDI Resource Counter.
Discovers Azure Native Objects and calculates Management Token requirements.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.privatedns import PrivateDnsManagementClient
from azure.mgmt.resource import ResourceManagementClient
from tqdm import tqdm

from shared.base_discovery import BaseDiscovery, DiscoveryConfig
from shared.output_utils import format_azure_resource

from .config import AzureConfig, get_azure_credential

# Configure logging - suppress INFO messages and Azure SDK logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Suppress Azure SDK logging (be quiet like AWS)
logging.getLogger("azure").setLevel(logging.ERROR)
logging.getLogger("azure.core").setLevel(logging.ERROR)
logging.getLogger("azure.mgmt").setLevel(logging.ERROR)


class AzureDiscovery(BaseDiscovery):
    """Azure Cloud Discovery implementation."""

    def __init__(self, config: AzureConfig):
        """
        Initialize Azure discovery.

        Args:
            config: Azure configuration
        """
        # Convert AzureConfig to DiscoveryConfig
        discovery_config = DiscoveryConfig(
            regions=config.regions or [],
            output_directory=config.output_directory,
            output_format=config.output_format,
            provider="azure",
        )
        super().__init__(discovery_config)

        # Store original Azure config for Azure-specific functionality
        self.azure_config = config

        # Initialize Azure clients
        self._init_azure_clients()

    def _init_azure_clients(self):
        """Initialize Azure clients for different services."""
        self.credential = get_azure_credential()
        self.subscription_id = self.azure_config.subscription_id or ""

        if not self.subscription_id:
            raise ValueError("Azure subscription ID is required")

        self.compute_client = ComputeManagementClient(self.credential, self.subscription_id)
        self.network_client = NetworkManagementClient(self.credential, self.subscription_id)
        self.resource_client = ResourceManagementClient(self.credential, self.subscription_id)
        self.dns_client = DnsManagementClient(self.credential, self.subscription_id)
        self.privatedns_client = PrivateDnsManagementClient(self.credential, self.subscription_id)

    def discover_native_objects(self, max_workers: int = 8) -> List[Dict]:
        """
        Discover all Native Objects across all Azure resource groups.

        Args:
            max_workers: Maximum number of parallel workers

        Returns:
            List of discovered resources
        """
        if self._discovered_resources is not None:
            return self._discovered_resources

        self.logger.info("Starting Azure discovery across all resource groups...")

        all_resources = []

        # Get all resource groups
        resource_groups = list(self.resource_client.resource_groups.list())

        # Discover resources in resource groups in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_rg = {executor.submit(self._discover_resource_group_resources, rg): rg for rg in resource_groups}

            # Use tqdm for progress tracking (match AWS label)
            with tqdm(total=len(resource_groups), desc="Completed") as pbar:
                for future in as_completed(future_to_rg):
                    resource_group = future_to_rg[future]
                    try:
                        rg_resources = future.result()
                        all_resources.extend(rg_resources)
                        self.logger.debug(f"Discovered {len(rg_resources)} resources in {resource_group.name}")
                    except Exception as e:
                        self.logger.error(f"Error discovering resource group {resource_group.name}: {e}")
                    finally:
                        pbar.update(1)

        # Discover global resources (DNS zones)
        dns_resources = self._discover_azure_dns_zones_and_records()
        all_resources.extend(dns_resources)

        self.logger.info(f"Discovery complete. Found {len(all_resources)} Native Objects")

        # Cache the results
        self._discovered_resources = all_resources
        return all_resources

    def _discover_resource_group_resources(self, resource_group) -> List[Dict]:
        """
        Discover resources in a specific Azure resource group.

        Args:
            resource_group: ResourceGroup object

        Returns:
            List of resources found in the resource group
        """
        rg_name = getattr(resource_group, "name", None)
        if not rg_name:
            self.logger.warning("Resource group with no name encountered, skipping.")
            return []

        resources = []

        # VMs
        try:
            for vm in self.compute_client.virtual_machines.list(rg_name):
                vm_name = getattr(vm, "name", None)
                if not vm_name:
                    continue

                region = getattr(vm, "location", "unknown")

                try:
                    # Get detailed VM info including network interfaces
                    vm_detail = self.compute_client.virtual_machines.get(rg_name, vm_name, expand="instanceView")

                    # Extract IP addresses
                    private_ips = []
                    public_ips = []

                    if (
                        hasattr(vm_detail, "network_profile")
                        and vm_detail.network_profile
                        and vm_detail.network_profile.network_interfaces
                    ):
                        for nic_ref in vm_detail.network_profile.network_interfaces:
                            if hasattr(nic_ref, "id") and nic_ref.id:
                                # Parse the NIC ID to get resource group and name
                                nic_id_parts = nic_ref.id.split("/")
                                if len(nic_id_parts) >= 9:
                                    nic_rg = nic_id_parts[4]  # Resource group
                                    nic_name = nic_id_parts[8]  # NIC name

                                    try:
                                        # Get the network interface details
                                        nic = self.network_client.network_interfaces.get(nic_rg, nic_name)

                                        # Extract private IPs
                                        if hasattr(nic, "ip_configurations") and nic.ip_configurations:
                                            for ip_config in nic.ip_configurations:
                                                if (
                                                    hasattr(
                                                        ip_config,
                                                        "private_ip_address",
                                                    )
                                                    and ip_config.private_ip_address
                                                ):
                                                    private_ips.append(ip_config.private_ip_address)

                                                # Extract public IP if present
                                                if (
                                                    hasattr(
                                                        ip_config,
                                                        "public_ip_address",
                                                    )
                                                    and ip_config.public_ip_address
                                                ):
                                                    if (
                                                        hasattr(
                                                            ip_config.public_ip_address,
                                                            "ip_address",
                                                        )
                                                        and ip_config.public_ip_address.ip_address
                                                    ):
                                                        public_ips.append(ip_config.public_ip_address.ip_address)
                                    except Exception as e:
                                        self.logger.warning(
                                            f"Error getting network interface {nic_name} for VM {vm_name}: {e}"
                                        )

                    # Determine if Management Token is required
                    has_network_interfaces = len(private_ips) > 0 or len(public_ips) > 0
                    is_managed = self._is_managed_service(getattr(vm, "tags", {}))
                    requires_token = has_network_interfaces and not is_managed

                    # Use vars() to convert Azure SDK model to dict
                    vm_dict = vars(vm)
                    formatted_vm = format_azure_resource(vm_dict, "vm", region, requires_token)

                    # Add IP addresses to details
                    if private_ips or public_ips:
                        formatted_vm["details"].update(
                            {
                                "private_ip": (private_ips[0] if private_ips else None),
                                "public_ip": (public_ips[0] if public_ips else None),
                                "private_ips": private_ips,
                                "public_ips": public_ips,
                            }
                        )

                    resources.append(formatted_vm)

                except Exception as e:
                    self.logger.warning(f"Error getting detailed VM info for {vm_name}: {e}")
                    # Fallback to basic VM info without IP addresses
                    vm_dict = vars(vm)
                    formatted_vm = format_azure_resource(vm_dict, "vm", region)
                    resources.append(formatted_vm)

        except Exception as e:
            self.logger.warning(f"Error discovering VMs in {rg_name}: {e}")

        # VNets
        try:
            for vnet in self.network_client.virtual_networks.list(rg_name):
                region = getattr(vnet, "location", "unknown")
                vnet_name = getattr(vnet, "name", None)
                if not vnet_name:
                    self.logger.warning(f"VNet with no name in {rg_name}, skipping subnets.")
                    continue

                vnet_dict = vars(vnet)
                formatted_vnet = format_azure_resource(vnet_dict, "vnet", region)
                resources.append(formatted_vnet)

                # Subnets for this VNet
                try:
                    for subnet in self.network_client.subnets.list(rg_name, vnet_name):
                        subnet_dict = vars(subnet)
                        formatted_subnet = format_azure_resource(subnet_dict, "subnet", region)
                        resources.append(formatted_subnet)
                except Exception as e:
                    self.logger.warning(f"Error discovering subnets in VNet {vnet_name} in {rg_name}: {e}")
        except Exception as e:
            self.logger.warning(f"Error discovering VNets in {rg_name}: {e}")

        # Load Balancers
        try:
            for lb in self.network_client.load_balancers.list(rg_name):
                region = getattr(lb, "location", "unknown")
                lb_dict = vars(lb)
                formatted_lb = format_azure_resource(lb_dict, "load_balancer", region)
                resources.append(formatted_lb)
        except Exception as e:
            self.logger.warning(f"Error discovering Load Balancers in {rg_name}: {e}")

        # VPN Gateways
        try:
            for vpngw in self.network_client.virtual_network_gateways.list(rg_name):
                region = getattr(vpngw, "location", "unknown")
                vpngw_dict = vars(vpngw)
                formatted_vpngw = format_azure_resource(vpngw_dict, "gateway", region)
                resources.append(formatted_vpngw)
        except Exception as e:
            self.logger.warning(f"Error discovering VPN Gateways in {rg_name}: {e}")

        # Application Gateways
        try:
            for appgw in self.network_client.application_gateways.list(rg_name):
                region = getattr(appgw, "location", "unknown")
                appgw_dict = vars(appgw)
                formatted_appgw = format_azure_resource(appgw_dict, "gateway", region)
                resources.append(formatted_appgw)
        except Exception as e:
            self.logger.warning(f"Error discovering Application Gateways in {rg_name}: {e}")

        # Azure Firewalls
        try:
            for fw in self.network_client.azure_firewalls.list(rg_name):
                region = getattr(fw, "location", "unknown")
                fw_dict = vars(fw)
                formatted_fw = format_azure_resource(fw_dict, "firewall", region)
                resources.append(formatted_fw)
        except Exception as e:
            self.logger.warning(f"Error discovering Azure Firewalls in {rg_name}: {e}")

        # Private Endpoints
        try:
            for pe in self.network_client.private_endpoints.list(rg_name):
                region = getattr(pe, "location", "unknown")
                pe_dict = vars(pe)
                formatted_pe = format_azure_resource(pe_dict, "endpoint", region)
                resources.append(formatted_pe)
        except Exception as e:
            self.logger.warning(f"Error discovering Private Endpoints in {rg_name}: {e}")

        # NAT Gateways
        try:
            for natgw in self.network_client.nat_gateways.list(rg_name):
                region = getattr(natgw, "location", "unknown")
                natgw_dict = vars(natgw)
                formatted_natgw = format_azure_resource(natgw_dict, "gateway", region)
                resources.append(formatted_natgw)
        except Exception as e:
            self.logger.warning(f"Error discovering NAT Gateways in {rg_name}: {e}")

        # Route Tables
        try:
            for rt in self.network_client.route_tables.list(rg_name):
                region = getattr(rt, "location", "unknown")
                rt_dict = vars(rt)
                formatted_rt = format_azure_resource(rt_dict, "router", region)
                resources.append(formatted_rt)
        except Exception as e:
            self.logger.warning(f"Error discovering Route Tables in {rg_name}: {e}")

        # Public IP Addresses
        try:
            for pip in self.network_client.public_ip_addresses.list(rg_name):
                region = getattr(pip, "location", "unknown")
                pip_dict = vars(pip)
                formatted_pip = format_azure_resource(pip_dict, "endpoint", region)
                resources.append(formatted_pip)
        except Exception as e:
            self.logger.warning(f"Error discovering Public IP Addresses in {rg_name}: {e}")

        # Network Security Groups
        try:
            for nsg in self.network_client.network_security_groups.list(rg_name):
                region = getattr(nsg, "location", "unknown")
                nsg_dict = vars(nsg)
                formatted_nsg = format_azure_resource(nsg_dict, "switch", region)
                resources.append(formatted_nsg)
        except Exception as e:
            self.logger.warning(f"Error discovering Network Security Groups in {rg_name}: {e}")

        # ExpressRoute Circuits
        try:
            for erc in self.network_client.express_route_circuits.list(rg_name):
                region = getattr(erc, "location", "unknown")
                erc_dict = vars(erc)
                formatted_erc = format_azure_resource(erc_dict, "switch", region)
                resources.append(formatted_erc)
        except Exception as e:
            self.logger.warning(f"Error discovering ExpressRoute Circuits in {rg_name}: {e}")

        # Dedicated Hosts
        try:
            for host_group in self.compute_client.dedicated_host_groups.list_by_resource_group(rg_name):
                region = getattr(host_group, "location", "unknown")
                host_group_name = getattr(host_group, "name", None)
                if not host_group_name:
                    continue
                for host in self.compute_client.dedicated_hosts.list_by_host_group(rg_name, host_group_name):
                    host_dict = vars(host)
                    formatted_host = format_azure_resource(host_dict, "server", region)
                    resources.append(formatted_host)
        except Exception as e:
            self.logger.warning(f"Error discovering Dedicated Hosts in {rg_name}: {e}")

        return resources

    def _discover_azure_dns_zones_and_records(self) -> List[Dict]:
        """Discover Azure DNS zones and records (public and private)."""
        resources = []

        try:
            # Discover all public DNS zones
            zones = list(self.dns_client.zones.list())
            self.logger.debug(f"Found {len(zones)} public DNS zones in subscription.")
            for zone in zones:
                zone_name = getattr(zone, "name", None)
                zone_type = getattr(zone, "zone_type", None)
                zone_id = getattr(zone, "id", None)
                self.logger.debug(f"Public Zone: name={zone_name}, type={zone_type}, id={zone_id}")

                if not zone_name:
                    continue

                region = getattr(zone, "location", "global")
                state = str(zone_type).lower() if zone_type else "public"
                resource_group = None
                if zone_id:
                    parts = zone_id.split("/")
                    try:
                        rg_index = parts.index("resourceGroups") + 1
                        resource_group = parts[rg_index]
                    except Exception:
                        resource_group = None

                # Add the public zone as a resource
                zone_resource = self._format_resource(
                    resource_data=vars(zone),
                    resource_type="dns-zone",
                    region=region,
                    name=zone_name,
                    requires_management_token=True,
                    state=state,
                    tags=getattr(zone, "tags", {}),
                )
                resources.append(zone_resource)

                # Discover records in the public zone
                if resource_group:
                    try:
                        for record_set in self.dns_client.record_sets.list_by_dns_zone(
                            resource_group_name=resource_group,
                            zone_name=zone_name,
                        ):
                            record_name = getattr(record_set, "name", None)
                            record_type = getattr(record_set, "type", None)
                            if not record_name or not record_type:
                                continue
                            if record_type == "SOA":
                                continue
                            record_resource = self._format_resource(
                                resource_data=vars(record_set),
                                resource_type="dns-record",
                                region=region,
                                name=record_name,
                                requires_management_token=True,
                                state=record_type,
                                tags=getattr(record_set, "tags", {}),
                            )
                            resources.append(record_resource)
                    except Exception as e:
                        self.logger.warning(
                            f"Error discovering records in DNS zone {zone_name} (resource group {resource_group}): {e}"
                        )
                else:
                    self.logger.warning(
                        f"Could not determine resource group for DNS zone {zone_name}, skipping record discovery."
                    )

            # Discover all private DNS zones
            private_zones = list(self.privatedns_client.private_zones.list())
            self.logger.debug(f"Found {len(private_zones)} private DNS zones in subscription.")
            for pzone in private_zones:
                pzone_name = getattr(pzone, "name", None)
                pzone_id = getattr(pzone, "id", None)
                self.logger.debug(f"Private Zone: name={pzone_name}, id={pzone_id}")

                if not pzone_name:
                    continue

                region = getattr(pzone, "location", "global")
                state = "private"
                resource_group = None
                if pzone_id:
                    parts = pzone_id.split("/")
                    try:
                        rg_index = parts.index("resourceGroups") + 1
                        resource_group = parts[rg_index]
                    except Exception:
                        resource_group = None

                # Add the private zone as a resource
                pzone_resource = self._format_resource(
                    resource_data=vars(pzone),
                    resource_type="dns-zone",
                    region=region,
                    name=pzone_name,
                    requires_management_token=True,
                    state=state,
                    tags=getattr(pzone, "tags", {}),
                )
                resources.append(pzone_resource)

                # Discover records in the private zone
                if resource_group:
                    try:
                        for record_set in self.privatedns_client.record_sets.list(
                            resource_group_name=resource_group,
                            private_zone_name=pzone_name,
                        ):
                            record_name = getattr(record_set, "name", None)
                            record_type = getattr(record_set, "type", None)
                            if not record_name or not record_type:
                                continue
                            if record_type == "SOA":
                                continue
                            record_resource = self._format_resource(
                                resource_data=vars(record_set),
                                resource_type="dns-record",
                                region=region,
                                name=record_name,
                                requires_management_token=True,
                                state=record_type,
                                tags=getattr(record_set, "tags", {}),
                            )
                            resources.append(record_resource)
                    except Exception as e:
                        self.logger.warning(
                            f"Error discovering records in Private DNS zone "
                            f"{pzone_name} (resource group {resource_group}): {e}"
                        )
                else:
                    self.logger.warning(
                        f"Could not determine resource group for Private DNS zone {pzone_name}, skipping record discovery."
                    )

        except Exception as e:
            self.logger.error(f"Error discovering Azure DNS zones/records: {e}")

        return resources

    def _is_managed_service(self, tags: Dict[str, str]) -> bool:
        """Check if a resource is a managed service (Management Token-free)."""
        if not tags:
            return False

        for key, value in tags.items():
            key_lower = key.lower()
            value_lower = value.lower()

            # Common managed service indicators
            if any(
                indicator in key_lower
                for indicator in [
                    "managed",
                    "service",
                    "azure",
                    "aks",
                    "appservice",
                ]
            ):
                return True
            if any(
                indicator in value_lower
                for indicator in [
                    "managed",
                    "service",
                    "azure",
                    "aks",
                    "appservice",
                ]
            ):
                return True

        return False

    def get_scanned_subscription_ids(self) -> list:
        """Return the Azure Subscription ID(s) scanned."""
        return [self.subscription_id] if self.subscription_id else []
