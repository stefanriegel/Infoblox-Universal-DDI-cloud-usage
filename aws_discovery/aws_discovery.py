#!/usr/bin/env python3
"""
AWS Cloud Discovery for Infoblox Universal DDI Management Token Calculator.

Discovers AWS Native Objects and calculates Management Token requirements.
"""

import sys
import logging
import math
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from .config import AWSConfig, load_config, get_all_enabled_regions
from .utils import (
    get_aws_client,
    save_output,
    get_resource_tags
)
from shared.output_utils import save_discovery_results, save_management_token_results

# Configure logging - suppress INFO messages and boto3/botocore logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Suppress boto3 and botocore logging
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


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
    """AWS Cloud Discovery for Management Token calculation."""
    
    def __init__(self, config: AWSConfig):
        """Initialize AWS Discovery with configuration."""
        self.config = config
        self.regions = config.regions or get_all_enabled_regions()
        
        # Cache for discovered resources to avoid multiple discovery runs
        self._discovered_resources = None
        
        logger.info(f"AWS Discovery initialized for {len(self.regions)} regions")
    
    def discover_native_objects(self, max_workers: int = 5) -> List[Dict]:
        """
        Discover AWS Native Objects across all enabled regions.
        
        Args:
            max_workers: Maximum number of parallel workers
            
        Returns:
            List of discovered AWS Native Objects
        """
        # Return cached results if available
        if self._discovered_resources is not None:
            return self._discovered_resources
            
        logger.info("Starting AWS Native Objects discovery...")
        all_resources = []
        
        # Use ThreadPoolExecutor for parallel region scanning
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_region = {
                executor.submit(self._discover_region, region): region
                for region in self.regions
            }
            
            with tqdm(total=len(self.regions), desc="Completed") as pbar:
                for future in as_completed(future_to_region):
                    region = future_to_region[future]
                    try:
                        region_resources = future.result()
                        all_resources.extend(region_resources)
                        logger.info(f"Completed {region}: {len(region_resources)} resources")
                    except Exception as e:
                        logger.error(f"Error scanning region {region}: {e}")
                    finally:
                        pbar.update(1)
        
        logger.info(f"Discovery complete. Found {len(all_resources)} Native Objects")
        
        # Cache the results
        self._discovered_resources = all_resources
        return all_resources
    
    def _discover_region(self, region: str) -> List[Dict]:
        """
        Discover all Native Objects in a specific AWS region.
        
        Args:
            region: AWS region name
            
        Returns:
            List of discovered resources in the region
        """
        region_resources = []
        
        try:
            # Discover EC2 instances
            ec2_instances = self._discover_ec2_instances(region)
            region_resources.extend(ec2_instances)
            
            # Discover VPCs
            vpcs = self._discover_vpcs(region)
            region_resources.extend(vpcs)
            
            # Discover subnets
            subnets = self._discover_subnets(region)
            region_resources.extend(subnets)
            
            # Discover load balancers
            load_balancers = self._discover_load_balancers(region)
            region_resources.extend(load_balancers)
            
        except Exception as e:
            logger.error(f"Error discovering region {region}: {e}")
        
        return region_resources
    
    def _discover_ec2_instances(self, region: str) -> List[Dict]:
        """Discover EC2 instances in the region."""
        instances = []
        try:
            ec2_client = get_aws_client('ec2', region, self.config)
            
            # Get total count for progress bar
            paginator = ec2_client.get_paginator('describe_instances')
            raw_instances = []
            for page in paginator.paginate():
                for reservation in page['Reservations']:
                    raw_instances.extend(reservation['Instances'])
            
            # Process instances with progress bar
            with tqdm(total=len(raw_instances), desc=f"  EC2 instances in {region}", leave=False) as pbar:
                for instance in raw_instances:
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
                    
                    native_object = {
                        'resource_id': f"{region}:ec2:{instance['InstanceId']}",
                        'resource_type': 'ec2-instance',
                        'region': region,
                        'name': instance.get('InstanceId', 'Unknown'),
                        'state': instance['State']['Name'],
                        'requires_management_token': requires_token,
                        'tags': get_resource_tags(instance.get('Tags', [])),
                        'details': {
                            'instance_type': instance.get('InstanceType'),
                            'vpc_id': instance.get('VpcId'),
                            'subnet_id': instance.get('SubnetId'),
                            'network_interfaces': len(instance.get('NetworkInterfaces', [])),
                            'private_ip': instance.get('PrivateIpAddress'),
                            'public_ip': instance.get('PublicIpAddress')
                        },
                        'discovered_at': datetime.now().isoformat()
                    }
                    
                    instances.append(native_object)
                    pbar.update(1)
                        
        except Exception as e:
            logger.error(f"Error discovering EC2 instances in {region}: {e}")
        
        return instances
    
    def _discover_vpcs(self, region: str) -> List[Dict]:
        """Discover VPCs in the region."""
        vpcs = []
        try:
            ec2_client = get_aws_client('ec2', region, self.config)
            
            response = ec2_client.describe_vpcs()
            for vpc in response['Vpcs']:
                native_object = {
                    'resource_id': f"{region}:vpc:{vpc['VpcId']}",
                    'resource_type': 'vpc',
                    'region': region,
                    'name': vpc.get('VpcId', 'Unknown'),
                    'state': vpc.get('State', 'available'),
                    'requires_management_token': True,  # VPCs always require Management Tokens
                    'tags': get_resource_tags(vpc.get('Tags', [])),
                    'details': {
                        'cidr_block': vpc.get('CidrBlock'),
                        'is_default': vpc.get('IsDefault', False),
                        'dhcp_options_id': vpc.get('DhcpOptionsId')
                    },
                    'discovered_at': datetime.now().isoformat()
                }
                
                vpcs.append(native_object)
                
        except Exception as e:
            logger.error(f"Error discovering VPCs in {region}: {e}")
        
        return vpcs
    
    def _discover_subnets(self, region: str) -> List[Dict]:
        """Discover subnets in the region."""
        subnets = []
        try:
            ec2_client = get_aws_client('ec2', region, self.config)
            
            response = ec2_client.describe_subnets()
            for subnet in response['Subnets']:
                native_object = {
                    'resource_id': f"{region}:subnet:{subnet['SubnetId']}",
                    'resource_type': 'subnet',
                    'region': region,
                    'name': subnet.get('SubnetId', 'Unknown'),
                    'state': subnet.get('State', 'available'),
                    'requires_management_token': True,  # Subnets always require Management Tokens
                    'tags': get_resource_tags(subnet.get('Tags', [])),
                    'details': {
                        'cidr_block': subnet.get('CidrBlock'),
                        'vpc_id': subnet.get('VpcId'),
                        'availability_zone': subnet.get('AvailabilityZone'),
                        'available_ip_address_count': subnet.get('AvailableIpAddressCount')
                    },
                    'discovered_at': datetime.now().isoformat()
                }
                
                subnets.append(native_object)
                
        except Exception as e:
            logger.error(f"Error discovering subnets in {region}: {e}")
        
        return subnets
    
    def _discover_load_balancers(self, region: str) -> List[Dict]:
        """Discover load balancers in the region."""
        load_balancers = []
        try:
            elbv2_client = get_aws_client('elbv2', region, self.config)
            
            response = elbv2_client.describe_load_balancers()
            for lb in response['LoadBalancers']:
                # Get tags for load balancer
                tags_response = elbv2_client.describe_tags(ResourceArns=[lb['LoadBalancerArn']])
                tags = {}
                if tags_response['TagDescriptions']:
                    tags = get_resource_tags(tags_response['TagDescriptions'][0].get('Tags', []))
                
                native_object = {
                    'resource_id': f"{region}:alb:{lb['LoadBalancerName']}",
                    'resource_type': 'application-load-balancer',
                    'region': region,
                    'name': lb.get('LoadBalancerName', 'Unknown'),
                    'state': lb.get('State', {}).get('Code', 'unknown'),
                    'requires_management_token': True,  # Load balancers require Management Tokens
                    'tags': tags,
                    'details': {
                        'type': lb.get('Type'),
                        'scheme': lb.get('Scheme'),
                        'vpc_id': lb.get('VpcId'),
                        'subnets': lb.get('AvailabilityZones', [])
                    },
                    'discovered_at': datetime.now().isoformat()
                }
                
                load_balancers.append(native_object)
                
        except Exception as e:
            logger.error(f"Error discovering load balancers in {region}: {e}")
        
        return load_balancers
    
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
        ddi_types = ['subnet', 'vpc']  # Simplified for AWS
        ddi_objects = [r for r in resources if r['resource_type'] in ddi_types]
        
        # Active IPs: unique IPs from all resources
        ip_set = set()
        for r in resources:
            details = r.get('details', {})
            for key in ['private_ip', 'public_ip']:
                ip = details.get(key)
                if ip:
                    ip_set.add(ip)
        active_ips = list(ip_set)
        
        # Assets: VMs, gateways, endpoints, firewalls, switches, routers, servers, etc. with at least one IP
        asset_types = ['ec2-instance', 'application-load-balancer']
        assets = [r for r in resources if r['resource_type'] in asset_types and any(r.get('details', {}).get(key) for key in ['private_ip', 'public_ip'])]
        
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
        total_tokens = max(tokens_ddi, tokens_ips, tokens_assets)  # Take the maximum
        
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
            breakdown_by_region[r['region']] = breakdown_by_region.get(r['region'], 0) + 1
        
        # Management Token-free resources
        management_token_free_resources = [r for r in resources if not r['requires_management_token']]
        
        calculation_results = {
            'total_native_objects': len(resources),
            'management_token_required': total_tokens,
            'management_token_free': len(management_token_free_resources),
            'breakdown_by_type': breakdown_by_type,
            'breakdown_by_region': breakdown_by_region,
            'management_token_free_resources': management_token_free_resources,
            'calculation_timestamp': datetime.now().isoformat(),
            'management_token_packs': packs,
            'management_tokens_packs_total': tokens_packs_total
        }
        
        return calculation_results
    
    def save_discovery_results(self, output_dir: Optional[str] = None) -> Dict[str, str]:
        """
        Save discovery results to files.
        
        Args:
            output_dir: Output directory (uses config default if None)
            
        Returns:
            Dictionary mapping file types to file paths
        """
        # Get discovered resources (will use cached results if available)
        resources = self.discover_native_objects()
        
        # Use provided output directory or config default
        output_directory = output_dir or self.config.output_directory
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save native objects
        native_objects_files = save_discovery_results(
            resources, 
            output_directory, 
            self.config.output_format, 
            timestamp,
            'aws'
        )
        
        # Calculate and save Management Token results (will use cached resources)
        calculation_results = self.calculate_management_token_requirements()
        token_files = save_management_token_results(
            calculation_results,
            output_directory,
            self.config.output_format,
            timestamp,
            'aws'
        )
        
        # Combine all saved files
        saved_files = {**native_objects_files, **token_files}
        
        return saved_files 