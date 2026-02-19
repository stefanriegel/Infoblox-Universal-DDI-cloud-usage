#!/usr/bin/env python3
"""
Azure Cloud Discovery for Infoblox Universal DDI Resource Counter.
Discovers Azure Native Objects and calculates Management Token requirements.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from azure.core.pipeline.policies import RetryPolicy
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.containerservice import ContainerServiceClient
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


class VisibleRetryPolicy(RetryPolicy):
    """RetryPolicy subclass that prints throttle events before sleeping.

    Honors Retry-After header from ARM 429 responses. Falls back to
    exponential backoff (2s, 4s, 8s) when the header is absent.
    Max 3 retries per API call.
    """

    def __init__(self, sub_name: str, print_lock: threading.Lock, **kwargs):
        super().__init__(**kwargs)
        self._sub_name = sub_name
        self._lock = print_lock

    def sleep(self, settings, transport, response=None):
        if response is not None:
            retry_after = self.get_retry_after(response)
            wait_secs = retry_after if retry_after is not None else self.get_backoff_time(settings)
            if wait_secs is not None:
                with self._lock:
                    print(f"  {self._sub_name}: throttled, retrying in {wait_secs:.0f}s")
        super().sleep(settings, transport, response)


def make_retry_policy(sub_name: str, print_lock: threading.Lock) -> VisibleRetryPolicy:
    """Build a VisibleRetryPolicy configured for ARM API scanning.

    Args:
        sub_name: Display name for this subscription (used in retry messages).
        print_lock: Threading lock for safe console output.
    """
    return VisibleRetryPolicy(
        sub_name=sub_name,
        print_lock=print_lock,
        retry_total=3,
        retry_connect=3,
        retry_read=3,
        retry_status=3,
        retry_backoff_factor=2.0,  # fallback: 2s, 4s, 8s when no Retry-After
        retry_backoff_max=60,  # cap fallback at 60s
        retry_on_status_codes=[429, 500, 502, 503, 504],
    )


class AzureDiscovery(BaseDiscovery):
    """Azure Cloud Discovery implementation."""

    _managed_key_prefixes = ("aks-managed-", "k8s-azure-", "ms-resource-usage:")
    _managed_key_exact = frozenset({"managed-by", "managed_by", "azure-managed"})
    _managed_value_exact = frozenset({"azure-managed", "aks", "appservice", "azure-functions"})

    def __init__(
        self,
        config: AzureConfig,
        retry_attempts: int = 3,  # Deprecated: no longer used; SDK RetryPolicy handles retries
        compute_client=None,
        network_client=None,
        resource_client=None,
        dns_client=None,
        privatedns_client=None,
        container_client=None,
    ):
        """
        Initialize Azure discovery.

        Args:
            config: Azure configuration
            retry_attempts: Deprecated. No longer used — SDK RetryPolicy handles retries.
                Retained for backward compatibility.
            compute_client: Optional pre-built ComputeManagementClient. When all six
                client kwargs are provided, _init_azure_clients() is skipped so the
                caller controls client lifecycle (create, scan, close).
            network_client: Optional pre-built NetworkManagementClient.
            resource_client: Optional pre-built ResourceManagementClient.
            dns_client: Optional pre-built DnsManagementClient.
            privatedns_client: Optional pre-built PrivateDnsManagementClient.
            container_client: Optional pre-built ContainerServiceClient.
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
        self.retry_attempts = retry_attempts  # Deprecated; kept for backward compat

        # When all five core clients are provided, use them directly and skip internal init.
        # This enables external lifecycle management (create → scan → close per subscription).
        if (
            compute_client is not None
            and network_client is not None
            and resource_client is not None
            and dns_client is not None
            and privatedns_client is not None
        ):
            self.compute_client = compute_client
            self.network_client = network_client
            self.resource_client = resource_client
            self.dns_client = dns_client
            self.privatedns_client = privatedns_client
            self.container_client = container_client
            self.credential = None
            self.subscription_id = config.subscription_id or ""
        else:
            # Initialize Azure clients internally (backward-compatible path)
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
        self.container_client = ContainerServiceClient(self.credential, self.subscription_id)

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

        # Discover resources by type
        resources.extend(self._discover_vms(rg_name))
        resources.extend(self._discover_vnets(rg_name))
        resources.extend(self._discover_load_balancers(rg_name))
        resources.extend(self._discover_vpn_gateways(rg_name))
        resources.extend(self._discover_application_gateways(rg_name))
        resources.extend(self._discover_azure_firewalls(rg_name))
        resources.extend(self._discover_private_endpoints(rg_name))
        resources.extend(self._discover_nat_gateways(rg_name))
        resources.extend(self._discover_route_tables(rg_name))
        resources.extend(self._discover_public_ip_addresses(rg_name))
        resources.extend(self._discover_network_security_groups(rg_name))
        resources.extend(self._discover_express_route_circuits(rg_name))
        resources.extend(self._discover_dedicated_hosts(rg_name))
        resources.extend(self._discover_vmss(rg_name))
        resources.extend(self._discover_aks_clusters(rg_name))

        # Resource groups are fully handled by the dedicated _discover_* methods above.
        return resources

    def _discover_vms(self, rg_name: str) -> List[Dict]:
        """Discover Virtual Machines in a resource group."""
        resources = []
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
                    subnet_ids = []

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

                                                # Capture subnet/vnet context for IP-space de-duplication
                                                subnet_ref = getattr(ip_config, "subnet", None)
                                                subnet_id = getattr(subnet_ref, "id", None) if subnet_ref else None
                                                if subnet_id:
                                                    subnet_ids.append(subnet_id)

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

                    subnet_id = subnet_ids[0] if subnet_ids else None
                    vnet_id = None
                    if isinstance(subnet_id, str) and "/subnets/" in subnet_id.lower():
                        vnet_id = subnet_id[: subnet_id.lower().rfind("/subnets/")]

                    # Determine if Management Token is required
                    has_network_interfaces = len(private_ips) > 0 or len(public_ips) > 0
                    is_managed = self._is_managed_service(getattr(vm, "tags", {}))
                    requires_token = has_network_interfaces and not is_managed

                    hw_profile = getattr(vm_detail, "hardware_profile", None)
                    os_profile = getattr(vm_detail, "os_profile", None)
                    vm_details = {
                        "vm_id": getattr(vm_detail, "id", None),
                        "vm_name": vm_name,
                        "vm_size": getattr(hw_profile, "vm_size", None) if hw_profile else None,
                        "os_type": getattr(os_profile, "computer_name", None) if os_profile else None,
                        "provisioning_state": getattr(vm_detail, "provisioning_state", None),
                        "name": vm_name,
                        "tags": getattr(vm, "tags", {}),
                    }
                    formatted_vm = format_azure_resource(vm_details, "vm", region, requires_token)

                    # Add IP addresses to details
                    if private_ips or public_ips:
                        formatted_vm["details"].update(
                            {
                                "private_ip": (private_ips[0] if private_ips else None),
                                "public_ip": (public_ips[0] if public_ips else None),
                                "private_ips": private_ips,
                                "public_ips": public_ips,
                                "subnet_id": subnet_id,
                                "subnet_ids": subnet_ids,
                                "vnet_id": vnet_id,
                            }
                        )

                    resources.append(formatted_vm)

                except Exception as e:
                    self.logger.warning(f"Error getting detailed VM info for {vm_name}: {e}")
                    # Fallback to basic VM info without IP addresses
                    vm_details = {
                        "vm_id": getattr(vm, "id", None),
                        "vm_name": vm_name,
                        "provisioning_state": getattr(vm, "provisioning_state", None),
                        "name": vm_name,
                        "tags": getattr(vm, "tags", {}),
                    }
                    formatted_vm = format_azure_resource(vm_details, "vm", region)
                    resources.append(formatted_vm)

        except Exception as e:
            self.logger.warning(f"Error discovering VMs in {rg_name}: {e}")
        return resources

    def _discover_vnets(self, rg_name: str) -> List[Dict]:
        """Discover Virtual Networks in a resource group."""
        resources = []
        try:
            vnets = list(self.network_client.virtual_networks.list(rg_name))
            for vnet in vnets:
                region = getattr(vnet, "location", "unknown")
                vnet_name = getattr(vnet, "name", None)
                if not vnet_name:
                    self.logger.warning(f"VNet with no name in {rg_name}, skipping subnets.")
                    continue

                vnet_id = getattr(vnet, "id", None)
                addr_space = getattr(vnet, "address_space", None)
                address_prefixes = getattr(addr_space, "address_prefixes", []) if addr_space else []

                details = {
                    "vnet_id": vnet_id,
                    "vnet_name": vnet_name,
                    "address_prefixes": address_prefixes,
                    "enable_ddos_protection": getattr(vnet, "enable_ddos_protection", None),
                    "provisioning_state": getattr(vnet, "provisioning_state", None),
                }

                formatted_vnet = format_azure_resource(details, "vnet", region)
                formatted_vnet["name"] = vnet_name
                resources.append(formatted_vnet)

                # Subnets for this VNet
                try:
                    subnets = list(self.network_client.subnets.list(rg_name, vnet_name))
                    for subnet in subnets:
                        subnet_name = getattr(subnet, "name", None)
                        subnet_id = getattr(subnet, "id", None)

                        details = {
                            "subnet_id": subnet_id,
                            "subnet_name": subnet_name,
                            "vnet_id": vnet_id,
                            "address_prefix": getattr(subnet, "address_prefix", None),
                            "address_prefixes": getattr(subnet, "address_prefixes", None),
                            "provisioning_state": getattr(subnet, "provisioning_state", None),
                            "private_endpoint_network_policies": getattr(subnet, "private_endpoint_network_policies", None),
                        }

                        formatted_subnet = format_azure_resource(details, "subnet", region)
                        formatted_subnet["name"] = subnet_name or ""
                        resources.append(formatted_subnet)
                except Exception as e:
                    self.logger.warning(f"Error discovering subnets in VNet {vnet_name} in {rg_name}: {e}")
        except Exception as e:
            self.logger.warning(f"Error discovering VNets in {rg_name}: {e}")
        return resources

    def _discover_load_balancers(self, rg_name: str) -> List[Dict]:
        """Discover Load Balancers in a resource group with frontend IP extraction."""
        resources = []
        try:
            for lb in self.network_client.load_balancers.list(rg_name):
                region = getattr(lb, "location", "unknown")
                lb_name = getattr(lb, "name", "")

                # Extract frontend private IPs (public IPs already captured by _discover_public_ip_addresses)
                private_ips = []
                if hasattr(lb, "frontend_ip_configurations") and lb.frontend_ip_configurations:
                    for frontend_config in lb.frontend_ip_configurations:
                        priv_ip = getattr(frontend_config, "private_ip_address", None)
                        if priv_ip:
                            private_ips.append(priv_ip)

                details = {
                    "lb_id": getattr(lb, "id", None),
                    "lb_name": lb_name,
                    "sku": str(getattr(getattr(lb, "sku", None), "name", "")) if getattr(lb, "sku", None) else None,
                    "provisioning_state": getattr(lb, "provisioning_state", None),
                    "private_ip": private_ips[0] if private_ips else None,
                    "private_ips": private_ips,
                }

                formatted_lb = format_azure_resource(details, "load-balancer", region)
                formatted_lb["name"] = lb_name
                resources.append(formatted_lb)
        except Exception as e:
            self.logger.warning(f"Error discovering Load Balancers in {rg_name}: {e}")
        return resources

    def _discover_vpn_gateways(self, rg_name: str) -> List[Dict]:
        """Discover VPN Gateways in a resource group."""
        resources = []
        try:
            for vpngw in self.network_client.virtual_network_gateways.list(rg_name):
                region = getattr(vpngw, "location", "unknown")
                details = {
                    "gateway_id": getattr(vpngw, "id", None),
                    "gateway_name": getattr(vpngw, "name", ""),
                    "gateway_type": str(getattr(vpngw, "gateway_type", "")) or None,
                    "vpn_type": str(getattr(vpngw, "vpn_type", "")) or None,
                    "sku": str(getattr(getattr(vpngw, "sku", None), "name", "")) if getattr(vpngw, "sku", None) else None,
                    "provisioning_state": getattr(vpngw, "provisioning_state", None),
                }
                formatted = format_azure_resource(details, "gateway", region)
                formatted["name"] = getattr(vpngw, "name", "")
                resources.append(formatted)
        except Exception as e:
            self.logger.warning(f"Error discovering VPN Gateways in {rg_name}: {e}")
        return resources

    def _discover_application_gateways(self, rg_name: str) -> List[Dict]:
        """Discover Application Gateways in a resource group."""
        resources = []
        try:
            for appgw in self.network_client.application_gateways.list(rg_name):
                region = getattr(appgw, "location", "unknown")
                details = {
                    "appgw_id": getattr(appgw, "id", None),
                    "appgw_name": getattr(appgw, "name", ""),
                    "sku": str(getattr(getattr(appgw, "sku", None), "name", "")) if getattr(appgw, "sku", None) else None,
                    "provisioning_state": getattr(appgw, "provisioning_state", None),
                }
                formatted = format_azure_resource(details, "gateway", region)
                formatted["name"] = getattr(appgw, "name", "")
                resources.append(formatted)
        except Exception as e:
            self.logger.warning(f"Error discovering Application Gateways in {rg_name}: {e}")
        return resources

    def _discover_azure_firewalls(self, rg_name: str) -> List[Dict]:
        """Discover Azure Firewalls in a resource group."""
        resources = []
        try:
            for fw in self.network_client.azure_firewalls.list(rg_name):
                region = getattr(fw, "location", "unknown")
                details = {
                    "firewall_id": getattr(fw, "id", None),
                    "firewall_name": getattr(fw, "name", ""),
                    "sku": str(getattr(getattr(fw, "sku", None), "name", "")) if getattr(fw, "sku", None) else None,
                    "provisioning_state": getattr(fw, "provisioning_state", None),
                    "threat_intel_mode": str(getattr(fw, "threat_intel_mode", "")) or None,
                }
                formatted = format_azure_resource(details, "firewall", region)
                formatted["name"] = getattr(fw, "name", "")
                resources.append(formatted)
        except Exception as e:
            self.logger.warning(f"Error discovering Azure Firewalls in {rg_name}: {e}")
        return resources

    def _discover_private_endpoints(self, rg_name: str) -> List[Dict]:
        """Discover Private Endpoints in a resource group."""
        resources = []
        try:
            for pe in self.network_client.private_endpoints.list(rg_name):
                region = getattr(pe, "location", "unknown")
                # Extract private IP from manual connection or NIC
                private_ips = []
                for iface in getattr(pe, "network_interfaces", []) or []:
                    iface_id = getattr(iface, "id", None)
                    if iface_id:
                        # NIC IPs are captured separately; record the association
                        pass
                for custom_dns in getattr(pe, "custom_dns_configs", []) or []:
                    for ip in getattr(custom_dns, "ip_addresses", []) or []:
                        if ip:
                            private_ips.append(ip)

                details = {
                    "endpoint_id": getattr(pe, "id", None),
                    "endpoint_name": getattr(pe, "name", ""),
                    "provisioning_state": getattr(pe, "provisioning_state", None),
                    "private_ips": private_ips,
                    "private_ip": private_ips[0] if private_ips else None,
                }
                formatted = format_azure_resource(details, "endpoint", region)
                formatted["name"] = getattr(pe, "name", "")
                resources.append(formatted)
        except Exception as e:
            self.logger.warning(f"Error discovering Private Endpoints in {rg_name}: {e}")
        return resources

    def _discover_nat_gateways(self, rg_name: str) -> List[Dict]:
        """Discover NAT Gateways in a resource group."""
        resources = []
        try:
            for natgw in self.network_client.nat_gateways.list(rg_name):
                region = getattr(natgw, "location", "unknown")
                details = {
                    "natgw_id": getattr(natgw, "id", None),
                    "natgw_name": getattr(natgw, "name", ""),
                    "sku": str(getattr(getattr(natgw, "sku", None), "name", "")) if getattr(natgw, "sku", None) else None,
                    "idle_timeout_in_minutes": getattr(natgw, "idle_timeout_in_minutes", None),
                    "provisioning_state": getattr(natgw, "provisioning_state", None),
                }
                formatted = format_azure_resource(details, "gateway", region)
                formatted["name"] = getattr(natgw, "name", "")
                resources.append(formatted)
        except Exception as e:
            self.logger.warning(f"Error discovering NAT Gateways in {rg_name}: {e}")
        return resources

    def _discover_route_tables(self, rg_name: str) -> List[Dict]:
        """Discover Route Tables in a resource group."""
        resources = []
        try:
            for rt in self.network_client.route_tables.list(rg_name):
                region = getattr(rt, "location", "unknown")
                details = {
                    "route_table_id": getattr(rt, "id", None),
                    "route_table_name": getattr(rt, "name", ""),
                    "provisioning_state": getattr(rt, "provisioning_state", None),
                    "disable_bgp_route_propagation": getattr(rt, "disable_bgp_route_propagation", None),
                }
                formatted = format_azure_resource(details, "router", region)
                formatted["name"] = getattr(rt, "name", "")
                resources.append(formatted)
        except Exception as e:
            self.logger.warning(f"Error discovering Route Tables in {rg_name}: {e}")
        return resources

    def _discover_public_ip_addresses(self, rg_name: str) -> List[Dict]:
        """Discover Public IP Addresses in a resource group."""
        resources = []
        try:
            for pip in self.network_client.public_ip_addresses.list(rg_name):
                region = getattr(pip, "location", "unknown")
                ip_addr = getattr(pip, "ip_address", None)

                details = {
                    "pip_id": getattr(pip, "id", None),
                    "pip_name": getattr(pip, "name", ""),
                    "ip_address": ip_addr,
                    "public_ip_allocation_method": str(getattr(pip, "public_ip_allocation_method", "")) or None,
                    "public_ip_address_version": str(getattr(pip, "public_ip_address_version", "")) or None,
                    "sku": str(getattr(getattr(pip, "sku", None), "name", "")) if getattr(pip, "sku", None) else None,
                    "provisioning_state": getattr(pip, "provisioning_state", None),
                }
                formatted = format_azure_resource(details, "public-ip", region)
                formatted["name"] = getattr(pip, "name", "")
                resources.append(formatted)
        except Exception as e:
            self.logger.warning(f"Error discovering Public IP Addresses in {rg_name}: {e}")
        return resources

    def _discover_network_security_groups(self, rg_name: str) -> List[Dict]:
        """Discover Network Security Groups in a resource group."""
        resources = []
        try:
            for nsg in self.network_client.network_security_groups.list(rg_name):
                region = getattr(nsg, "location", "unknown")
                details = {
                    "nsg_id": getattr(nsg, "id", None),
                    "nsg_name": getattr(nsg, "name", ""),
                    "provisioning_state": getattr(nsg, "provisioning_state", None),
                }
                formatted = format_azure_resource(details, "switch", region)
                formatted["name"] = getattr(nsg, "name", "")
                resources.append(formatted)
        except Exception as e:
            self.logger.warning(f"Error discovering Network Security Groups in {rg_name}: {e}")
        return resources

    def _discover_express_route_circuits(self, rg_name: str) -> List[Dict]:
        """Discover ExpressRoute Circuits in a resource group."""
        resources = []
        try:
            for erc in self.network_client.express_route_circuits.list(rg_name):
                region = getattr(erc, "location", "unknown")
                details = {
                    "circuit_id": getattr(erc, "id", None),
                    "circuit_name": getattr(erc, "name", ""),
                    "service_provider_name": getattr(
                        getattr(erc, "service_provider_properties", None), "service_provider_name", None
                    ),
                    "bandwidth_in_mbps": getattr(getattr(erc, "service_provider_properties", None), "bandwidth_in_mbps", None),
                    "sku": str(getattr(getattr(erc, "sku", None), "name", "")) if getattr(erc, "sku", None) else None,
                    "provisioning_state": getattr(erc, "provisioning_state", None),
                }
                formatted = format_azure_resource(details, "switch", region)
                formatted["name"] = getattr(erc, "name", "")
                resources.append(formatted)
        except Exception as e:
            self.logger.warning(f"Error discovering ExpressRoute Circuits in {rg_name}: {e}")
        return resources

    def _discover_dedicated_hosts(self, rg_name: str) -> List[Dict]:
        """Discover Dedicated Hosts in a resource group."""
        resources = []
        try:
            for host_group in self.compute_client.dedicated_host_groups.list_by_resource_group(rg_name):
                region = getattr(host_group, "location", "unknown")
                host_group_name = getattr(host_group, "name", None)
                if not host_group_name:
                    continue
                for host in self.compute_client.dedicated_hosts.list_by_host_group(rg_name, host_group_name):
                    details = {
                        "host_id": getattr(host, "id", None),
                        "host_name": getattr(host, "name", ""),
                        "host_group": host_group_name,
                        "sku": str(getattr(getattr(host, "sku", None), "name", "")) if getattr(host, "sku", None) else None,
                        "provisioning_state": getattr(host, "provisioning_state", None),
                    }
                    formatted = format_azure_resource(details, "server", region)
                    formatted["name"] = getattr(host, "name", "")
                    resources.append(formatted)
        except Exception as e:
            self.logger.warning(f"Error discovering Dedicated Hosts in {rg_name}: {e}")
        return resources

    def _discover_vmss(self, rg_name: str) -> List[Dict]:
        """Discover Virtual Machine Scale Set instances in a resource group."""
        resources = []
        try:
            for vmss in self.compute_client.virtual_machine_scale_sets.list(rg_name):
                vmss_name = getattr(vmss, "name", None)
                if not vmss_name:
                    continue

                region = getattr(vmss, "location", "unknown")

                try:
                    for vm_instance in self.compute_client.virtual_machine_scale_set_vms.list(rg_name, vmss_name):
                        instance_id = getattr(vm_instance, "instance_id", None)
                        if not instance_id:
                            continue

                        # Extract IPs from VMSS VM network interfaces
                        private_ips = []
                        public_ips = []
                        subnet_ids = []

                        try:
                            nics = self.network_client.network_interfaces.list_virtual_machine_scale_set_vm_network_interfaces(
                                rg_name, vmss_name, instance_id
                            )
                            for nic in nics:
                                if hasattr(nic, "ip_configurations") and nic.ip_configurations:
                                    for ip_config in nic.ip_configurations:
                                        if hasattr(ip_config, "private_ip_address") and ip_config.private_ip_address:
                                            private_ips.append(ip_config.private_ip_address)

                                        subnet_ref = getattr(ip_config, "subnet", None)
                                        subnet_id = getattr(subnet_ref, "id", None) if subnet_ref else None
                                        if subnet_id:
                                            subnet_ids.append(subnet_id)

                                        if (
                                            hasattr(ip_config, "public_ip_address")
                                            and ip_config.public_ip_address
                                            and hasattr(ip_config.public_ip_address, "ip_address")
                                            and ip_config.public_ip_address.ip_address
                                        ):
                                            public_ips.append(ip_config.public_ip_address.ip_address)
                        except Exception as e:
                            self.logger.warning(f"Error getting NICs for VMSS instance {vmss_name}/{instance_id}: {e}")

                        subnet_id = subnet_ids[0] if subnet_ids else None
                        vnet_id = None
                        if isinstance(subnet_id, str) and "/subnets/" in subnet_id.lower():
                            vnet_id = subnet_id[: subnet_id.lower().rfind("/subnets/")]

                        has_ips = len(private_ips) > 0 or len(public_ips) > 0
                        is_managed = self._is_managed_service(getattr(vm_instance, "tags", {}))
                        requires_token = has_ips and not is_managed

                        instance_details = {
                            "vm_id": getattr(vm_instance, "id", None),
                            "instance_id": instance_id,
                            "vmss_name": vmss_name,
                            "provisioning_state": getattr(vm_instance, "provisioning_state", None),
                            "name": getattr(vm_instance, "name", ""),
                            "tags": getattr(vm_instance, "tags", {}),
                        }
                        formatted = format_azure_resource(instance_details, "vmss-instance", region, requires_token)

                        if private_ips or public_ips:
                            formatted["details"].update(
                                {
                                    "private_ip": private_ips[0] if private_ips else None,
                                    "public_ip": public_ips[0] if public_ips else None,
                                    "private_ips": private_ips,
                                    "public_ips": public_ips,
                                    "subnet_id": subnet_id,
                                    "subnet_ids": subnet_ids,
                                    "vnet_id": vnet_id,
                                    "vmss_name": vmss_name,
                                }
                            )

                        resources.append(formatted)

                except Exception as e:
                    self.logger.warning(f"Error discovering VMSS instances in {vmss_name}/{rg_name}: {e}")

        except Exception as e:
            self.logger.warning(f"Error discovering VMSS in {rg_name}: {e}")
        return resources

    def _discover_aks_clusters(self, rg_name: str) -> List[Dict]:
        """Discover AKS (Azure Kubernetes Service) clusters in a resource group.

        AKS clusters consume pod and service CIDRs that are IPAM-relevant DDI objects,
        similar to GCP's GKE cluster discovery.
        """
        resources = []
        if not getattr(self, "container_client", None):
            return resources
        try:
            for cluster in self.container_client.managed_clusters.list_by_resource_group(rg_name):
                cluster_name = getattr(cluster, "name", None)
                if not cluster_name:
                    continue

                region = getattr(cluster, "location", "unknown")
                net_profile = getattr(cluster, "network_profile", None)

                pod_cidr = getattr(net_profile, "pod_cidr", None) if net_profile else None
                service_cidr = getattr(net_profile, "service_cidr", None) if net_profile else None
                dns_service_ip = getattr(net_profile, "dns_service_ip", None) if net_profile else None
                network_plugin = str(getattr(net_profile, "network_plugin", "")) if net_profile else None

                # Agent pool profile summary
                agent_pools = getattr(cluster, "agent_pool_profiles", []) or []
                total_node_count = sum(getattr(pool, "count", 0) or 0 for pool in agent_pools)
                vnet_subnet_id = None
                for pool in agent_pools:
                    sid = getattr(pool, "vnet_subnet_id", None)
                    if sid:
                        vnet_subnet_id = sid
                        break

                k8s_version = getattr(cluster, "kubernetes_version", None)
                provisioning_state = getattr(cluster, "provisioning_state", "unknown")

                details = {
                    "cluster_name": cluster_name,
                    "pod_cidr": pod_cidr,
                    "service_cidr": service_cidr,
                    "dns_service_ip": dns_service_ip,
                    "network_plugin": network_plugin,
                    "kubernetes_version": k8s_version,
                    "total_node_count": total_node_count,
                    "vnet_subnet_id": vnet_subnet_id,
                }

                resources.append(
                    self._format_resource(
                        resource_data=details,
                        resource_type="aks-cluster",
                        region=region,
                        name=cluster_name,
                        requires_management_token=True,
                        state=str(provisioning_state).lower(),
                        tags=getattr(cluster, "tags", {}) or {},
                    )
                )

        except Exception as e:
            self.logger.warning(f"Error discovering AKS clusters in {rg_name}: {e}")
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
                zone_details = {
                    "zone_id": zone_id,
                    "zone_name": zone_name,
                    "zone_type": str(zone_type) if zone_type else "Public",
                    "number_of_record_sets": getattr(zone, "number_of_record_sets", None),
                    "name_servers": getattr(zone, "name_servers", None),
                    "resource_group": resource_group,
                }
                zone_resource = self._format_resource(
                    resource_data=zone_details,
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
                            record_details = {
                                "record_name": record_name,
                                "record_type": record_type,
                                "ttl": getattr(record_set, "ttl", None),
                                "fqdn": getattr(record_set, "fqdn", None),
                                "zone_name": zone_name,
                            }
                            record_resource = self._format_resource(
                                resource_data=record_details,
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
                pzone_details = {
                    "zone_id": pzone_id,
                    "zone_name": pzone_name,
                    "zone_type": "Private",
                    "number_of_record_sets": getattr(pzone, "number_of_record_sets", None),
                    "resource_group": resource_group,
                }
                pzone_resource = self._format_resource(
                    resource_data=pzone_details,
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
                            record_details = {
                                "record_name": record_name,
                                "record_type": record_type,
                                "ttl": getattr(record_set, "ttl", None),
                                "fqdn": getattr(record_set, "fqdn", None),
                                "zone_name": pzone_name,
                                "is_private": True,
                            }
                            record_resource = self._format_resource(
                                resource_data=record_details,
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

    def get_scanned_subscription_ids(self) -> list:
        """Return the Azure Subscription ID(s) scanned."""
        return [self.subscription_id] if self.subscription_id else []
