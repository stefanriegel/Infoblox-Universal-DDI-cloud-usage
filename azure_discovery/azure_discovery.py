#!/usr/bin/env python3
"""
Azure Cloud Discovery for Infoblox Universal DDI Management Token Calculator.
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
from .utils import format_azure_vm_resource, format_azure_vnet_resource, format_azure_subnet_resource
from shared.output_utils import (
    format_azure_resource,
    save_discovery_results, 
    save_management_token_results
)

# Configure logging - suppress INFO messages and Azure SDK logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Suppress Azure SDK logging
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('azure.core').setLevel(logging.WARNING)
logging.getLogger('azure.mgmt').setLevel(logging.WARNING)

class AzureDiscovery:
    """Azure Cloud Discovery for Management Token calculation."""
    
    def __init__(self, config: AzureConfig):
        """Initialize Azure Discovery with configuration."""
        self.config = config
        self.subscription_id = config.subscription_id
        self.credential = DefaultAzureCredential()
        
        # Management clients
        self.compute_client = ComputeManagementClient(self.credential, self.subscription_id)  # type: ignore
        self.network_client = NetworkManagementClient(self.credential, self.subscription_id)  # type: ignore
        self.resource_client = ResourceManagementClient(self.credential, self.subscription_id)  # type: ignore
        self.dns_client = DnsManagementClient(self.credential, self.subscription_id)  # type: ignore
        
        # Cache for discovered resources to avoid multiple discovery runs
        self._discovered_resources = None
        
        logger.info(f"Azure Discovery initialized for subscription: {self.subscription_id}")
    
    def discover_native_objects(self, max_workers: int = 5) -> List[Dict]:
        """
        Discover Azure Native Objects across all resource groups.
        
        Args:
            max_workers: Maximum number of parallel workers
            
        Returns:
            List of discovered Azure Native Objects
        """
        # Return cached results if available
        if self._discovered_resources is not None:
            return self._discovered_resources
            
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
        
        # Add Azure DNS discovery (global, not per-resource group)
        dns_resources = self._discover_azure_dns_zones_and_records()
        all_resources.extend(dns_resources)
        logger.info(f"Discovery complete. Found {len(all_resources)} Native Objects")
        
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
        rg_name = getattr(resource_group, 'name', None)
        if not rg_name:
            logger.warning("Resource group with no name encountered, skipping.")
            return []
        resources = []
        # VMs
        try:
            for vm in self.compute_client.virtual_machines.list(rg_name):
                region = getattr(vm, 'location', 'unknown')
                vm_name = getattr(vm, 'name', 'unknown')
                
                # Get VM details including network interfaces
                try:
                    vm_details = self.compute_client.virtual_machines.get(rg_name, vm_name, expand='instanceView')
                    
                    # Extract IP addresses from network interfaces
                    private_ips = []
                    public_ips = []
                    
                    if hasattr(vm_details, 'network_profile') and vm_details.network_profile and vm_details.network_profile.network_interfaces:
                        for nic_ref in vm_details.network_profile.network_interfaces:
                            if nic_ref and nic_ref.id:
                                # Extract resource group and NIC name from the ID
                                nic_id_parts = nic_ref.id.split('/')
                                if len(nic_id_parts) >= 9:
                                    nic_rg = nic_id_parts[4]  # Resource group
                                    nic_name = nic_id_parts[8]  # NIC name
                                    
                                    try:
                                        # Get the network interface details
                                        nic = self.network_client.network_interfaces.get(nic_rg, nic_name)
                                        
                                        # Extract private IPs
                                        if hasattr(nic, 'ip_configurations') and nic.ip_configurations:
                                            for ip_config in nic.ip_configurations:
                                                if hasattr(ip_config, 'private_ip_address') and ip_config.private_ip_address:
                                                    private_ips.append(ip_config.private_ip_address)
                                                
                                                # Extract public IP if present
                                                if hasattr(ip_config, 'public_ip_address') and ip_config.public_ip_address:
                                                    if hasattr(ip_config.public_ip_address, 'ip_address') and ip_config.public_ip_address.ip_address:
                                                        public_ips.append(ip_config.public_ip_address.ip_address)
                                    except Exception as e:
                                        logger.warning(f"Error getting network interface {nic_name} for VM {vm_name}: {e}")
                    
                    # Determine if Management Token is required
                    has_network_interfaces = len(private_ips) > 0 or len(public_ips) > 0
                    is_managed = self._is_managed_service(getattr(vm, 'tags', {}))
                    requires_token = has_network_interfaces and not is_managed
                    
                    # Use vars() to convert Azure SDK model to dict
                    vm_dict = vars(vm)
                    formatted_vm = format_azure_resource(vm_dict, 'vm', region, requires_token)
                    
                    # Add IP addresses to details
                    if private_ips or public_ips:
                        formatted_vm['details'].update({
                            'private_ip': private_ips[0] if private_ips else None,
                            'public_ip': public_ips[0] if public_ips else None,
                            'private_ips': private_ips,
                            'public_ips': public_ips
                        })
                    
                    resources.append(formatted_vm)
                    
                except Exception as e:
                    logger.warning(f"Error getting detailed VM info for {vm_name}: {e}")
                    # Fallback to basic VM info without IP addresses
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
    
    def _discover_azure_dns_zones_and_records(self) -> List[Dict]:
        """Discover Azure DNS zones and records (global) - both public and private zones."""
        resources = []
        try:
            # Discover public DNS zones
            logger.info("Discovering public DNS zones...")
            for zone in self.dns_client.zones.list():
                zone_name = zone.name
                zone_id = zone.id
                region = getattr(zone, 'location', 'global')
                resource_group = getattr(zone, 'resource_group', None)
                if not resource_group and zone_id:
                    resource_group = self.extract_resource_group_from_id(zone_id)
                
                # Add the zone as a resource
                resources.append({
                    'resource_id': f"azure:dns:zone:public:{zone_name}",
                    'resource_type': 'dns-zone',
                    'region': region,
                    'name': zone_name,
                    'state': 'active',
                    'requires_management_token': True,
                    'tags': getattr(zone, 'tags', {}),
                    'details': {
                        'zone_name': zone_name,
                        'zone_type': 'Public',
                        'number_of_record_sets': getattr(zone, 'number_of_record_sets', 0)
                    },
                    'discovered_at': datetime.now().isoformat()
                })
                
                # List all records in the zone
                try:
                    if resource_group and zone_name:
                        for record_set in self.dns_client.record_sets.list_by_dns_zone(resource_group_name=resource_group, zone_name=zone_name):
                            record_type = record_set.type.split('/')[-1]  # Extract type from full type path
                            record_name = record_set.name
                            
                            resources.append({
                                'resource_id': f"azure:dns:record:public:{zone_name}:{record_name}:{record_type}",
                                'resource_type': 'dns-record',
                                'region': region,
                                'name': record_name,
                                'state': record_type,
                                'requires_management_token': True,
                                'tags': getattr(record_set, 'tags', {}),
                                'details': {
                                    'zone_name': zone_name,
                                    'record_type': record_type,
                                    'record_name': record_name,
                                    'ttl': getattr(record_set, 'ttl', None),
                                    'fqdn': getattr(record_set, 'fqdn', None),
                                    'zone_type': 'Public'
                                },
                                'discovered_at': datetime.now().isoformat()
                            })
                except Exception as e:
                    logger.warning(f"Error discovering records in public DNS zone {zone_name}: {e}")
            
            # Discover private DNS zones using Azure CLI (since SDK doesn't support private zones directly)
            logger.info("Discovering private DNS zones...")
            try:
                import subprocess
                import json
                
                # Get private DNS zones using Azure CLI
                result = subprocess.run([
                    'az', 'network', 'private-dns', 'zone', 'list', '--output', 'json'
                ], capture_output=True, text=True, check=True)
                
                private_zones = json.loads(result.stdout)
                logger.info(f"Found {len(private_zones)} private DNS zones")
                
                for zone in private_zones:
                    zone_name = zone['name']
                    resource_group = zone['resourceGroup']
                    region = zone.get('location', 'global')
                    
                    # Add the zone as a resource
                    resources.append({
                        'resource_id': f"azure:dns:zone:private:{zone_name}",
                        'resource_type': 'dns-zone',
                        'region': region,
                        'name': zone_name,
                        'state': 'active',
                        'requires_management_token': True,
                        'tags': zone.get('tags', {}),
                        'details': {
                            'zone_name': zone_name,
                            'zone_type': 'Private',
                            'resource_group': resource_group,
                            'number_of_record_sets': zone.get('numberOfRecordSets', 0)
                        },
                        'discovered_at': datetime.now().isoformat()
                    })
                    
                    # Get records for this private zone
                    try:
                        record_result = subprocess.run([
                            'az', 'network', 'private-dns', 'record-set', 'list',
                            '--zone-name', zone_name,
                            '--resource-group', resource_group,
                            '--output', 'json'
                        ], capture_output=True, text=True, check=True)
                        
                        records = json.loads(record_result.stdout)
                        logger.info(f"Found {len(records)} records in private zone {zone_name}")
                        
                        for record in records:
                            record_name = record['name']
                            record_type = record['type'].split('/')[-1]  # Extract type from full path
                            
                            # Skip SOA records as they are system records
                            if record_type == 'SOA':
                                continue
                            
                            resources.append({
                                'resource_id': f"azure:dns:record:private:{zone_name}:{record_name}:{record_type}",
                                'resource_type': 'dns-record',
                                'region': region,
                                'name': record_name,
                                'state': record_type,
                                'requires_management_token': True,
                                'tags': record.get('tags', {}),
                                'details': {
                                    'zone_name': zone_name,
                                    'record_type': record_type,
                                    'record_name': record_name,
                                    'ttl': record.get('ttl'),
                                    'fqdn': record.get('fqdn'),
                                    'zone_type': 'Private',
                                    'resource_group': resource_group
                                },
                                'discovered_at': datetime.now().isoformat()
                            })
                            
                    except subprocess.CalledProcessError as e:
                        logger.warning(f"Error discovering records in private DNS zone {zone_name}: {e}")
                    except Exception as e:
                        logger.warning(f"Error processing records for private DNS zone {zone_name}: {e}")
                        
            except subprocess.CalledProcessError as e:
                logger.warning(f"Error discovering private DNS zones via Azure CLI: {e}")
            except Exception as e:
                logger.warning(f"Error in private DNS zone discovery: {e}")
                    
        except Exception as e:
            logger.error(f"Error discovering Azure DNS zones/records: {e}")
        
        return resources
    
    def extract_resource_group_from_id(self, resource_id: str) -> str:
        """Extract the resource group name from an Azure resource ID."""
        if not resource_id or not isinstance(resource_id, str):
            return ""
        try:
            parts = resource_id.split('/')
            rg_index = [i for i, part in enumerate(parts) if part.lower() == 'resourcegroups']
            if rg_index and rg_index[0] + 1 < len(parts):
                return parts[rg_index[0] + 1]
        except Exception:
            pass
        return ""
    
    def _is_managed_service(self, tags: Dict[str, str]) -> bool:
        """Check if a resource is a managed service (Management Token-free)."""
        if not tags:
            return False
        
        for key, value in tags.items():
            key_lower = key.lower()
            value_lower = value.lower()
            
            # Common managed service indicators
            if any(indicator in key_lower for indicator in ['managed', 'service', 'azure', 'aks', 'appservice']):
                return True
            if any(indicator in value_lower for indicator in ['managed', 'service', 'azure', 'aks', 'appservice']):
                return True
        
        return False
    
    def get_management_token_free_assets(self) -> List[Dict]:
        """
        Get list of Management Token-free assets.
        
        Returns:
            List of resources that don't require Management Tokens
        """
        resources = self.discover_native_objects()
        return [obj for obj in resources if not obj['requires_management_token']]
    
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
        # Get discovered resources (will use cached results if available)
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
        # Token calculation (SUM, not max)
        tokens_ddi = math.ceil(len(ddi_objects) / 25)
        tokens_ips = math.ceil(len(active_ips) / 13)
        tokens_assets = math.ceil(len(unique_assets) / 3)
        total_tokens = tokens_ddi + tokens_ips + tokens_assets
        
        # Packs to sell (round up to next 1000)
        packs = math.ceil(total_tokens / 1000)
        tokens_packs_total = packs * 1000
        
        # Breakdown
        breakdown_by_type = {
            'ddi_objects': len(ddi_objects),
            'active_ips': len(active_ips),
            'assets': len(unique_assets)
        }
        breakdown_by_region = {}
        for r in resources:
            region = r.get('region', 'unknown')
            breakdown_by_region[region] = breakdown_by_region.get(region, 0) + 1
        
        # Management Token-free resources
        management_token_free_resources = [r for r in resources if not r.get('requires_management_token', True)]
        
        calculation_results = {
            'total_native_objects': len(resources),
            'management_token_required': total_tokens,
            'management_token_free': len(management_token_free_resources),
            'breakdown_by_type': breakdown_by_type,
            'breakdown_by_region': breakdown_by_region,
            'management_token_free_resources': management_token_free_resources,
            'calculation_timestamp': datetime.now().isoformat(),
            'management_token_packs': packs,
            'management_tokens_packs_total': tokens_packs_total,
            'tokens_ddi': tokens_ddi,
            'tokens_ips': tokens_ips,
            'tokens_assets': tokens_assets
        }
        
        return calculation_results
    
    def save_discovery_results(self) -> Dict[str, str]:
        """
        Save discovery results to files.
        
        Returns:
            Dictionary mapping file types to file paths
        """
        # Get discovered resources (will use cached results if available)
        resources = self.discover_native_objects()
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save native objects
        native_objects_files = save_discovery_results(
            resources, 
            self.config.output_directory, 
            self.config.output_format, 
            timestamp,
            'azure'
        )
        
        # Calculate and save Management Token results (will use cached resources)
        calculation_results = self.calculate_management_token_requirements()
        token_files = save_management_token_results(
            calculation_results,
            self.config.output_directory,
            self.config.output_format,
            timestamp,
            'azure'
        )
        
        # Combine all saved files
        saved_files = {**native_objects_files, **token_files}
        
        return saved_files 