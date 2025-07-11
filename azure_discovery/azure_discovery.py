#!/usr/bin/env python3
"""
Azure Cloud Discovery for Infoblox Universal DDI Resource Counter.
Discovers Azure Native Objects and calculates Management Token requirements.
"""

import logging
import math
from datetime import datetime
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.dns import DnsManagementClient

from .config import AzureConfig, get_azure_credential, validate_azure_config
from shared.base_discovery import BaseDiscovery, DiscoveryConfig
from shared.output_utils import (
    format_azure_resource,
    save_discovery_results,
    save_resource_count_results,
)

# Configure logging - suppress INFO messages and Azure SDK logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Suppress Azure SDK logging
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.core").setLevel(logging.WARNING)
logging.getLogger("azure.mgmt").setLevel(logging.WARNING)


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

        self.compute_client = ComputeManagementClient(
            self.credential, self.subscription_id
        )
        self.network_client = NetworkManagementClient(
            self.credential, self.subscription_id
        )
        self.resource_client = ResourceManagementClient(
            self.credential, self.subscription_id
        )
        self.dns_client = DnsManagementClient(self.credential, self.subscription_id)

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
            future_to_rg = {
                executor.submit(self._discover_resource_group_resources, rg): rg
                for rg in resource_groups
            }

            # Use tqdm for progress tracking
            with tqdm(
                total=len(resource_groups), desc="Scanning resource groups"
            ) as pbar:
                for future in as_completed(future_to_rg):
                    resource_group = future_to_rg[future]
                    try:
                        rg_resources = future.result()
                        all_resources.extend(rg_resources)
                        self.logger.debug(
                            f"Discovered {len(rg_resources)} resources in {resource_group.name}"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Error discovering resource group {resource_group.name}: {e}"
                        )
                    finally:
                        pbar.update(1)

        # Discover global resources (DNS zones)
        dns_resources = self._discover_azure_dns_zones_and_records()
        all_resources.extend(dns_resources)

        self.logger.info(
            f"Discovery complete. Found {len(all_resources)} Native Objects"
        )

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
                    vm_detail = self.compute_client.virtual_machines.get(
                        rg_name, vm_name, expand="instanceView"
                    )

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
                                        nic = (
                                            self.network_client.network_interfaces.get(
                                                nic_rg, nic_name
                                            )
                                        )

                                        # Extract private IPs
                                        if (
                                            hasattr(nic, "ip_configurations")
                                            and nic.ip_configurations
                                        ):
                                            for ip_config in nic.ip_configurations:
                                                if (
                                                    hasattr(
                                                        ip_config, "private_ip_address"
                                                    )
                                                    and ip_config.private_ip_address
                                                ):
                                                    private_ips.append(
                                                        ip_config.private_ip_address
                                                    )

                                                # Extract public IP if present
                                                if (
                                                    hasattr(
                                                        ip_config, "public_ip_address"
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
                                                        public_ips.append(
                                                            ip_config.public_ip_address.ip_address
                                                        )
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
                    formatted_vm = format_azure_resource(
                        vm_dict, "vm", region, requires_token
                    )

                    # Add IP addresses to details
                    if private_ips or public_ips:
                        formatted_vm["details"].update(
                            {
                                "private_ip": private_ips[0] if private_ips else None,
                                "public_ip": public_ips[0] if public_ips else None,
                                "private_ips": private_ips,
                                "public_ips": public_ips,
                            }
                        )

                    resources.append(formatted_vm)

                except Exception as e:
                    self.logger.warning(
                        f"Error getting detailed VM info for {vm_name}: {e}"
                    )
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
                    self.logger.warning(
                        f"VNet with no name in {rg_name}, skipping subnets."
                    )
                    continue

                vnet_dict = vars(vnet)
                formatted_vnet = format_azure_resource(vnet_dict, "vnet", region)
                resources.append(formatted_vnet)

                # Subnets for this VNet
                try:
                    for subnet in self.network_client.subnets.list(rg_name, vnet_name):
                        subnet_dict = vars(subnet)
                        formatted_subnet = format_azure_resource(
                            subnet_dict, "subnet", region
                        )
                        resources.append(formatted_subnet)
                except Exception as e:
                    self.logger.warning(
                        f"Error discovering subnets in VNet {vnet_name} in {rg_name}: {e}"
                    )
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

        return resources

    def _discover_azure_dns_zones_and_records(self) -> List[Dict]:
        """Discover Azure DNS zones and records."""
        resources = []

        try:
            # Discover public DNS zones
            for zone in self.dns_client.zones.list():
                zone_name = getattr(zone, "name", None)
                if not zone_name:
                    continue

                region = getattr(zone, "location", "global")

                # Add the zone as a resource
                zone_resource = self._format_resource(
                    resource_data=vars(zone),
                    resource_type="dns-zone",
                    region=region,
                    name=zone_name,
                    requires_management_token=True,
                    state="public",
                    tags=getattr(zone, "tags", {}),
                )
                resources.append(zone_resource)

                # Discover records in the zone
                try:
                    for record_set in self.dns_client.record_sets.list_by_dns_zone(
                        resource_group_name=zone_name, zone_name=zone_name
                    ):
                        record_name = getattr(record_set, "name", None)
                        record_type = getattr(record_set, "type", None)
                        if not record_name or not record_type:
                            continue

                        # Skip SOA records as they are system records
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
                        f"Error discovering records in DNS zone {zone_name}: {e}"
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
                for indicator in ["managed", "service", "azure", "aks", "appservice"]
            ):
                return True
            if any(
                indicator in value_lower
                for indicator in ["managed", "service", "azure", "aks", "appservice"]
            ):
                return True

        return False

    def count_resources(self) -> Dict:
        resources = self.discover_native_objects()
        count = self.resource_counter.count_resources(resources)
        return {
            "total_objects": count.total_objects,
            "ddi_objects": count.ddi_objects,
            "ddi_breakdown": count.ddi_breakdown,
            "active_ips": count.active_ips,
            "ip_sources": count.ip_sources,
            "breakdown_by_region": count.breakdown_by_region,
            "timestamp": count.timestamp,
        }

    def save_discovery_results(self) -> Dict[str, str]:
        resources = self.discover_native_objects()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        native_objects_files = save_discovery_results(
            resources,
            self.config.output_directory,
            self.config.output_format,
            timestamp,
            "azure",
        )
        count_results = self.count_resources()
        count_files = save_resource_count_results(
            count_results,
            self.config.output_directory,
            self.config.output_format,
            timestamp,
            "azure",
        )
        saved_files = {**native_objects_files, **count_files}
        return saved_files
