"""
Azure Cloud Discovery Module for Infoblox Universal DDI Management Token Calculator.
Discovers Azure Native Objects and calculates Management Token requirements.
"""

import logging
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from datetime import datetime
import math

from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.identity import DefaultAzureCredential

from config import AzureConfig, get_azure_credential, validate_azure_config
from utils import format_azure_resource, save_discovery_results, save_management_token_results

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AzureDiscovery:
    """Azure Native Objects discovery and Management Token calculation."""
    
    def __init__(self, config: AzureConfig):
        """
        Initialize Azure discovery.
        
        Args:
            config: Azure configuration object
        """
        self.config = config
        
        # Validate configuration
        if not validate_azure_config(config):
            raise ValueError("Invalid Azure configuration")
        
        # Initialize Azure clients
        self.credential = get_azure_credential()
        self.subscription_id = config.subscription_id
        if not self.subscription_id:
            raise ValueError("Azure subscription_id must not be None")
        
        # Management clients
        self.compute_client = ComputeManagementClient(self.credential, self.subscription_id)  # type: ignore
        self.network_client = NetworkManagementClient(self.credential, self.subscription_id)  # type: ignore
        self.resource_client = ResourceManagementClient(self.credential, self.subscription_id)  # type: ignore
        
        logger.info(f"Azure Discovery initialized for subscription: {self.subscription_id}")
    
    def discover_native_objects(self, max_workers: int = 5) -> List[Dict]:
        """
        Discover Azure Native Objects across all resource groups.
        
        Args:
            max_workers: Maximum number of parallel workers
            
        Returns:
            List of discovered Azure Native Objects
        """
        logger.info("Starting Azure Native Objects discovery (resource group-based)...")
        all_resources = []
        resource_groups = list(self.resource_client.resource_groups.list())
        logger.info(f"Found {len(resource_groups)} resource groups")
        # Use ThreadPoolExecutor for parallel resource group scanning
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_rg = {
                executor.submit(self._discover_resource_group_resources, rg): rg.name
                for rg in resource_groups
            }
            with tqdm(total=len(resource_groups), desc="Scanning resource groups") as pbar:
                for future in as_completed(future_to_rg):
                    rg_name = future_to_rg[future]
                    try:
                        rg_resources = future.result()
                        all_resources.extend(rg_resources)
                        logger.info(f"Completed {rg_name}: {len(rg_resources)} resources")
                    except Exception as e:
                        logger.error(f"Error scanning resource group {rg_name}: {e}")
                    finally:
                        pbar.update(1)
        logger.info(f"Discovery complete. Found {len(all_resources)} Native Objects")
        return all_resources
    
    def _discover_resource_group_resources(self, resource_group) -> List[Dict]:
        """
        Discover resources in a specific Azure resource group.
        
        Args:
            resource_group: ResourceGroup object
            
        Returns:
            List of resources found in the resource group
        """
        rg_name = getattr(resource_group, 'name', None)
        if not rg_name:
            logger.warning("Resource group with no name encountered, skipping.")
            return []
        resources = []
        # VMs
        try:
            for vm in self.compute_client.virtual_machines.list(rg_name):
                region = getattr(vm, 'location', 'unknown')
                # Use vars() to convert Azure SDK model to dict
                vm_dict = vars(vm)
                formatted_vm = format_azure_resource(vm_dict, 'vm', region)
                resources.append(formatted_vm)
        except Exception as e:
            logger.warning(f"Error discovering VMs in {rg_name}: {e}")
        # VNets
        try:
            for vnet in self.network_client.virtual_networks.list(rg_name):
                region = getattr(vnet, 'location', 'unknown')
                vnet_name = getattr(vnet, 'name', None)
                if not vnet_name:
                    logger.warning(f"VNet with no name in {rg_name}, skipping subnets.")
                    continue
                vnet_dict = vars(vnet)
                formatted_vnet = format_azure_resource(vnet_dict, 'vnet', region)
                resources.append(formatted_vnet)
                # Subnets for this VNet
                try:
                    for subnet in self.network_client.subnets.list(rg_name, vnet_name):
                        subnet_dict = vars(subnet)
                        formatted_subnet = format_azure_resource(subnet_dict, 'subnet', region)
                        resources.append(formatted_subnet)
                except Exception as e:
                    logger.warning(f"Error discovering subnets in VNet {vnet_name} in {rg_name}: {e}")
        except Exception as e:
            logger.warning(f"Error discovering VNets in {rg_name}: {e}")
        # Load Balancers
        try:
            for lb in self.network_client.load_balancers.list(rg_name):
                region = getattr(lb, 'location', 'unknown')
                lb_dict = vars(lb)
                formatted_lb = format_azure_resource(lb_dict, 'load_balancer', region)
                resources.append(formatted_lb)
        except Exception as e:
            logger.warning(f"Error discovering Load Balancers in {rg_name}: {e}")
        return resources
    
    def calculate_management_token_requirements(self) -> Dict:
        """
        Calculate Management Token requirements according to official Infoblox Universal DDI rules:
        - 1 token per 25 DDI objects
        - 1 token per 13 active IP addresses
        - 1 token per 3 assets (with at least one IP address)
        Reference: https://docs.infoblox.com/space/BloxOneDDI/846954761/Universal+DDI+Licensing
        
        Returns:
            Dictionary with calculation results
        """
        # Get discovered resources
        resources = self.discover_native_objects()
        # DDI objects: DNS, DHCP, IPAM objects
        ddi_types = [
            'dns-zone', 'dns-record', 'dhcp-range', 'subnet', 'ipam-block', 'ipam-space', 'host-record', 'ddns-record', 'address-block', 'view', 'zone', 'dtc-lbdn', 'dtc-server', 'dtc-pool', 'dtc-topology-rule', 'dtc-health-check', 'dhcp-exclusion-range', 'dhcp-filter-rule', 'dhcp-option', 'ddns-zone'
        ]
        ddi_objects = [r for r in resources if r['resource_type'] in ddi_types]
        # Active IPs: unique IPs from all resources with 'ip', 'private_ip', or 'public_ip' in details
        ip_set = set()
        for r in resources:
            details = r.get('details', {})
            for key in ['ip', 'private_ip', 'public_ip']:
                ip = details.get(key)
                if ip:
                    ip_set.add(ip)
            # For subnets, optionally add discovered IPs if available
            if r['resource_type'] == 'subnet' and 'discovered_ips' in details:
                for ip in details['discovered_ips']:
                    ip_set.add(ip)
        active_ips = list(ip_set)
        # Assets: VMs, gateways, endpoints, firewalls, switches, routers, servers, etc. with at least one IP
        asset_types = ['vm', 'gateway', 'endpoint', 'firewall', 'switch', 'router', 'server', 'load_balancer']
        assets = [r for r in resources if r['resource_type'] in asset_types and any(r.get('details', {}).get(key) for key in ['ip', 'private_ip', 'public_ip'])]
        # De-duplicate assets by resource_id
        asset_ids = set()
        unique_assets = []
        for asset in assets:
            if asset['resource_id'] not in asset_ids:
                asset_ids.add(asset['resource_id'])
                unique_assets.append(asset)
        # Token calculation
        tokens_ddi = math.ceil(len(ddi_objects) / 25)
        tokens_ips = math.ceil(len(active_ips) / 13)
        tokens_assets = math.ceil(len(unique_assets) / 3)
        total_tokens = tokens_ddi + tokens_ips + tokens_assets
        # Breakdown
        breakdown_by_type = {
            'ddi_objects': len(ddi_objects),
            'active_ips': len(active_ips),
            'assets': len(unique_assets)
        }
        breakdown_by_region = {}
        for r in resources:
            breakdown_by_region[r['region']] = breakdown_by_region.get(r['region'], 0) + 1
        # Management Token-free resources (empty for Azure)
        management_token_free_resources = []
        calculation_results = {
            'total_native_objects': len(resources),
            'management_token_required': total_tokens,
            'management_token_free': 0,
            'breakdown_by_type': breakdown_by_type,
            'breakdown_by_region': breakdown_by_region,
            'management_token_free_resources': management_token_free_resources,
            'calculation_timestamp': datetime.now().isoformat()
        }
        return calculation_results
    
    def save_discovery_results(self) -> Dict[str, str]:
        """
        Save discovery results to files.
        
        Returns:
            Dictionary mapping file types to file paths
        """
        # Discover resources
        resources = self.discover_native_objects()
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save native objects
        native_objects_files = save_discovery_results(
            resources, 
            self.config.output_directory, 
            self.config.output_format, 
            timestamp
        )
        
        # Calculate and save Management Token results
        calculation_results = self.calculate_management_token_requirements()
        token_files = save_management_token_results(
            calculation_results,
            self.config.output_directory,
            self.config.output_format,
            timestamp
        )
        
        # Combine all saved files
        saved_files = {**native_objects_files, **token_files}
        
        return saved_files 