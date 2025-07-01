"""
AWS Cloud Discovery for Infoblox Universal DDI Management Token Calculator.

Discovers AWS Native Objects and calculates Management Token requirements.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import math

from config import AWSConfig, load_config
from utils import (
    get_aws_client,
    save_output,
    get_resource_tags
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class NativeObject:
    """AWS Native Object representation."""
    
    resource_id: str
    resource_type: str
    region: str
    name: str
    state: str
    requires_management_token: bool
    tags: Dict[str, str]
    details: Dict[str, Any]
    discovered_at: str


@dataclass
class ManagementTokenCalculation:
    """Management Token calculation results."""
    
    total_native_objects: int
    management_token_required: int
    management_token_free: int
    breakdown_by_type: Dict[str, int]
    breakdown_by_region: Dict[str, int]
    calculation_timestamp: str


class AWSDiscovery:
    """AWS Cloud Discovery for Native Objects and Management Token calculation."""
    
    def __init__(self, config: Optional[AWSConfig] = None):
        """
        Initialize AWS Discovery.
        
        Args:
            config: AWS configuration. If None, loads from environment.
        """
        self.config = config or load_config()
        self.native_objects: List[NativeObject] = []
        self.discovery_results: Dict[str, Any] = {}
        
    def discover_native_objects(self, max_workers: int = 5) -> List[NativeObject]:
        """
        Discover all Native Objects across configured AWS regions using parallel processing.
        
        Args:
            max_workers: Maximum number of parallel threads (default: 5)
            
        Returns:
            List of discovered Native Objects
        """
        logger.info("Starting AWS Native Objects discovery...")
        
        self.native_objects = []
        regions = self.config.regions or []
        
        # Thread-safe list for collecting results
        results_lock = threading.Lock()
        all_native_objects = []
        
        def discover_region_safe(region: str) -> List[NativeObject]:
            """Thread-safe region discovery."""
            try:
                # Create a temporary discovery instance for this thread
                temp_discovery = AWSDiscovery(self.config)
                temp_discovery._discover_region(region)
                return temp_discovery.native_objects
            except Exception as e:
                logger.error(f"Error discovering region {region}: {e}")
                return []
        
        # Progress bar for regions
        with tqdm(total=len(regions), desc="Scanning regions", unit="region") as pbar:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all region discovery tasks
                future_to_region = {
                    executor.submit(discover_region_safe, region): region 
                    for region in regions
                }
                
                # Process completed tasks
                for future in as_completed(future_to_region):
                    region = future_to_region[future]
                    try:
                        region_objects = future.result()
                        with results_lock:
                            all_native_objects.extend(region_objects)
                        pbar.set_description(f"Completed {region}")
                    except Exception as e:
                        logger.error(f"Error processing region {region}: {e}")
                    finally:
                        pbar.update(1)
        
        self.native_objects = all_native_objects
        logger.info(f"Discovery complete. Found {len(self.native_objects)} Native Objects")
        return self.native_objects
    
    def _discover_region(self, region: str):
        """Discover Native Objects in a specific region."""
        # Discover EC2 instances
        self._discover_ec2_instances(region)
        
        # Discover VPCs
        self._discover_vpcs(region)
        
        # Discover subnets
        self._discover_subnets(region)
        
        # Discover load balancers
        self._discover_load_balancers(region)
    

    
    def _discover_ec2_instances(self, region: str):
        """Discover EC2 instances in the region."""
        try:
            ec2_client = get_aws_client('ec2', region, self.config)
            
            # Get total count for progress bar
            paginator = ec2_client.get_paginator('describe_instances')
            instances = []
            for page in paginator.paginate():
                for reservation in page['Reservations']:
                    instances.extend(reservation['Instances'])
            
            # Process instances with progress bar
            with tqdm(total=len(instances), desc=f"  EC2 instances in {region}", leave=False) as pbar:
                for instance in instances:
                    # Skip terminated instances
                    if instance['State']['Name'] == 'terminated':
                        pbar.update(1)
                        continue
                    
                    # Check if instance has network interfaces
                    has_network_interfaces = len(instance.get('NetworkInterfaces', [])) > 0
                    
                    # Check if it's a managed service
                    is_managed = self._is_managed_service(instance.get('Tags', []))
                    
                    # Determine if Management Token is required
                    requires_token = has_network_interfaces and not is_managed
                    
                    native_object = NativeObject(
                        resource_id=f"{region}:ec2:{instance['InstanceId']}",
                        resource_type='ec2-instance',
                        region=region,
                        name=instance.get('InstanceId', 'Unknown'),
                        state=instance['State']['Name'],
                        requires_management_token=requires_token,
                        tags=get_resource_tags(instance.get('Tags', [])),
                        details={
                            'instance_type': instance.get('InstanceType'),
                            'vpc_id': instance.get('VpcId'),
                            'subnet_id': instance.get('SubnetId'),
                            'network_interfaces': len(instance.get('NetworkInterfaces', [])),
                            'private_ip': instance.get('PrivateIpAddress'),
                            'public_ip': instance.get('PublicIpAddress')
                        },
                        discovered_at=datetime.now().isoformat()
                    )
                    
                    self.native_objects.append(native_object)
                    pbar.update(1)
                        
        except Exception as e:
            logger.error(f"Error discovering EC2 instances in {region}: {e}")
    

    
    def _discover_vpcs(self, region: str):
        """Discover VPCs in the region."""
        try:
            ec2_client = get_aws_client('ec2', region, self.config)
            
            response = ec2_client.describe_vpcs()
            for vpc in response['Vpcs']:
                native_object = NativeObject(
                    resource_id=f"{region}:vpc:{vpc['VpcId']}",
                    resource_type='vpc',
                    region=region,
                    name=vpc.get('VpcId', 'Unknown'),
                    state=vpc.get('State', 'available'),
                    requires_management_token=True,  # VPCs always require Management Tokens
                    tags=get_resource_tags(vpc.get('Tags', [])),
                    details={
                        'cidr_block': vpc.get('CidrBlock'),
                        'is_default': vpc.get('IsDefault', False),
                        'dhcp_options_id': vpc.get('DhcpOptionsId')
                    },
                    discovered_at=datetime.now().isoformat()
                )
                
                self.native_objects.append(native_object)
                
        except Exception as e:
            logger.error(f"Error discovering VPCs in {region}: {e}")
    
    def _discover_subnets(self, region: str):
        """Discover subnets in the region."""
        try:
            ec2_client = get_aws_client('ec2', region, self.config)
            
            response = ec2_client.describe_subnets()
            for subnet in response['Subnets']:
                native_object = NativeObject(
                    resource_id=f"{region}:subnet:{subnet['SubnetId']}",
                    resource_type='subnet',
                    region=region,
                    name=subnet.get('SubnetId', 'Unknown'),
                    state=subnet.get('State', 'available'),
                    requires_management_token=True,  # Subnets always require Management Tokens
                    tags=get_resource_tags(subnet.get('Tags', [])),
                    details={
                        'cidr_block': subnet.get('CidrBlock'),
                        'vpc_id': subnet.get('VpcId'),
                        'availability_zone': subnet.get('AvailabilityZone'),
                        'available_ip_address_count': subnet.get('AvailableIpAddressCount')
                    },
                    discovered_at=datetime.now().isoformat()
                )
                
                self.native_objects.append(native_object)
                
        except Exception as e:
            logger.error(f"Error discovering subnets in {region}: {e}")
    
    def _discover_load_balancers(self, region: str):
        """Discover load balancers in the region."""
        try:
            elbv2_client = get_aws_client('elbv2', region, self.config)
            
            response = elbv2_client.describe_load_balancers()
            for lb in response['LoadBalancers']:
                # Get tags for load balancer
                tags_response = elbv2_client.describe_tags(ResourceArns=[lb['LoadBalancerArn']])
                tags = {}
                if tags_response['TagDescriptions']:
                    tags = get_resource_tags(tags_response['TagDescriptions'][0].get('Tags', []))
                
                native_object = NativeObject(
                    resource_id=f"{region}:alb:{lb['LoadBalancerName']}",
                    resource_type='application-load-balancer',
                    region=region,
                    name=lb.get('LoadBalancerName', 'Unknown'),
                    state=lb.get('State', {}).get('Code', 'unknown'),
                    requires_management_token=True,  # Load balancers require Management Tokens
                    tags=tags,
                    details={
                        'type': lb.get('Type'),
                        'scheme': lb.get('Scheme'),
                        'vpc_id': lb.get('VpcId'),
                        'subnets': lb.get('AvailabilityZones', [])
                    },
                    discovered_at=datetime.now().isoformat()
                )
                
                self.native_objects.append(native_object)
                
        except Exception as e:
            logger.error(f"Error discovering load balancers in {region}: {e}")
    
    def _is_managed_service(self, tags: List[Dict[str, str]]) -> bool:
        """Check if a resource is a managed service (Management Token-free)."""
        if not tags:
            return False
        
        for tag in tags:
            key = tag.get('Key', '').lower()
            value = tag.get('Value', '').lower()
            
            # Common managed service indicators
            if any(indicator in key for indicator in ['managed', 'service', 'aws']):
                return True
            if any(indicator in value for indicator in ['managed', 'service', 'aws']):
                return True
        
        return False
    
    def get_management_token_free_assets(self) -> List[NativeObject]:
        """
        Get list of Management Token-free assets.
        
        Returns:
            List of Native Objects that don't require Management Tokens
        """
        return [obj for obj in self.native_objects if not obj.requires_management_token]
    
    def calculate_management_token_requirements(self) -> ManagementTokenCalculation:
        """
        Calculate Management Token requirements according to official Infoblox Universal DDI rules:
        - 1 token per 25 DDI objects
        - 1 token per 13 active IP addresses
        - 1 token per 3 assets (with at least one IP address)
        Reference: https://docs.infoblox.com/space/BloxOneDDI/846954761/Universal+DDI+Licensing
        
        Returns:
            ManagementTokenCalculation object with results
        """
        if not self.native_objects:
            self.discover_native_objects()

        # Categorize objects
        ddi_objects = [obj for obj in self.native_objects if obj.resource_type in [
            'dns-zone', 'dns-record', 'dhcp-range', 'subnet', 'ipam-block', 'ipam-space', 'host-record', 'ddns-record', 'address-block', 'view', 'zone', 'dtc-lbdn', 'dtc-server', 'dtc-pool', 'dtc-topology-rule', 'dtc-health-check', 'dhcp-exclusion-range', 'dhcp-filter-rule', 'dhcp-option', 'ddns-zone'
        ]]
        # Active IPs: count unique IPs from all objects with an 'ip' or 'private_ip' or 'public_ip' in details
        ip_set = set()
        for obj in self.native_objects:
            details = obj.details
            for key in ['ip', 'private_ip', 'public_ip']:
                ip = details.get(key)
                if ip:
                    ip_set.add(ip)
            # For subnets, optionally add discovered IPs if available
            if obj.resource_type == 'subnet' and 'discovered_ips' in details:
                for ip in details['discovered_ips']:
                    ip_set.add(ip)
        active_ips = list(ip_set)
        # Assets: VMs, gateways, endpoints, firewalls, switches, routers, servers, etc. with at least one IP
        asset_types = ['ec2-instance', 'vm', 'gateway', 'endpoint', 'firewall', 'switch', 'router', 'server', 'load_balancer', 'application-load-balancer']
        assets = [obj for obj in self.native_objects if obj.resource_type in asset_types and any(obj.details.get(key) for key in ['ip', 'private_ip', 'public_ip'])]
        # De-duplicate assets by resource_id
        asset_ids = set()
        unique_assets = []
        for asset in assets:
            if asset.resource_id not in asset_ids:
                asset_ids.add(asset.resource_id)
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
        for obj in self.native_objects:
            if obj.requires_management_token:
                breakdown_by_region[obj.region] = breakdown_by_region.get(obj.region, 0) + 1
        calculation = ManagementTokenCalculation(
            total_native_objects=len(self.native_objects),
            management_token_required=total_tokens,
            management_token_free=0,  # All counted objects require tokens
            breakdown_by_type=breakdown_by_type,
            breakdown_by_region=breakdown_by_region,
            calculation_timestamp=datetime.now().isoformat()
        )
        return calculation
    
    def save_discovery_results(self, output_dir: Optional[str] = None) -> Dict[str, str]:
        """
        Save discovery results to files.
        
        Args:
            output_dir: Output directory. If None, uses config default.
            
        Returns:
            Dictionary mapping file types to saved file paths
        """
        if not self.native_objects:
            self.discover_native_objects()
        
        output_dir = output_dir or self.config.output_directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        saved_files = {}
        
        # Save all Native Objects
        native_objects_data = [asdict(obj) for obj in self.native_objects]
        saved_files['native_objects'] = save_output(
            native_objects_data,
            f"aws_native_objects_{timestamp}",
            output_dir,
            self.config.output_format
        )
        
        # Save Management Token-free assets
        token_free_objects = [asdict(obj) for obj in self.get_management_token_free_assets()]
        saved_files['management_token_free'] = save_output(
            token_free_objects,
            f"aws_management_token_free_{timestamp}",
            output_dir,
            self.config.output_format
        )
        
        # Save Management Token calculation
        calculation = self.calculate_management_token_requirements()
        saved_files['management_token_calculation'] = save_output(
            asdict(calculation),
            f"aws_management_token_calculation_{timestamp}",
            output_dir,
            self.config.output_format
        )
        
        # Save summary report
        summary = {
            'discovery_summary': {
                'total_native_objects': calculation.total_native_objects,
                'management_token_required': calculation.management_token_required,
                'management_token_free': calculation.management_token_free,
                'regions_scanned': list(set(obj.region for obj in self.native_objects)),
                'discovery_timestamp': timestamp
            },
            'breakdown_by_type': calculation.breakdown_by_type,
            'breakdown_by_region': calculation.breakdown_by_region
        }
        
        saved_files['summary'] = save_output(
            summary,
            f"aws_discovery_summary_{timestamp}",
            output_dir,
            self.config.output_format
        )
        
        return saved_files 