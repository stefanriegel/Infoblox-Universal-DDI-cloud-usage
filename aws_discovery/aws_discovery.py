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
from .utils import get_aws_client
from shared.base_discovery import BaseDiscovery, DiscoveryConfig
from shared.output_utils import get_resource_tags, save_discovery_results, save_management_token_results

# Configure logging - suppress INFO messages and boto3/botocore logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Suppress boto3 and botocore logging
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)


class AWSDiscovery(BaseDiscovery):
    """AWS Cloud Discovery implementation."""
    
    def __init__(self, config: AWSConfig):
        """
        Initialize AWS discovery.
        
        Args:
            config: AWS configuration
        """
        # Convert AWSConfig to DiscoveryConfig
        discovery_config = DiscoveryConfig(
            regions=config.regions or [],
            output_directory=config.output_directory,
            output_format=config.output_format,
            provider='aws'
        )
        super().__init__(discovery_config)
        
        # Store original AWS config for AWS-specific functionality
        self.aws_config = config
        
        # Initialize AWS clients
        self._init_aws_clients()
    
    def _init_aws_clients(self):
        """Initialize AWS clients for different services."""
        self.clients = {}
        for region in self.config.regions:
            self.clients[region] = {
                'ec2': get_aws_client('ec2', region, self.aws_config),
                'elbv2': get_aws_client('elbv2', region, self.aws_config),
                'elb': get_aws_client('elb', region, self.aws_config)
            }
    
    def discover_native_objects(self, max_workers: int = 8) -> List[Dict]:
        """
        Discover all Native Objects across all AWS regions.
        
        Args:
            max_workers: Maximum number of parallel workers
            
        Returns:
            List of discovered resources
        """
        if self._discovered_resources is not None:
            return self._discovered_resources
        
        self.logger.info("Starting AWS discovery across all regions...")
        
        all_resources = []
        
        # Discover regional resources in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_region = {
                executor.submit(self._discover_region, region): region 
                for region in self.config.regions
            }
            
            # Use tqdm for progress tracking
            with tqdm(total=len(self.config.regions), desc="Completed") as pbar:
                for future in as_completed(future_to_region):
                    region = future_to_region[future]
                    try:
                        region_resources = future.result()
                        all_resources.extend(region_resources)
                        self.logger.debug(f"Discovered {len(region_resources)} resources in {region}")
                    except Exception as e:
                        self.logger.error(f"Error discovering region {region}: {e}")
                    finally:
                        pbar.update(1)
        
        # Discover global resources (Route 53)
        route53_resources = self._discover_route53_zones_and_records()
        all_resources.extend(route53_resources)
        
        self.logger.info(f"Discovery complete. Found {len(all_resources)} Native Objects")
        
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
            self.logger.error(f"Error discovering region {region}: {e}")
        
        return region_resources
    
    def _discover_ec2_instances(self, region: str) -> List[Dict]:
        """Discover EC2 instances in a region."""
        resources = []
        try:
            ec2 = self.clients[region]['ec2']
            
            # Get all instances
            paginator = ec2.get_paginator('describe_instances')
            for page in paginator.paginate():
                for reservation in page.get('Reservations', []):
                    for instance in reservation.get('Instances', []):
                        instance_id = instance.get('InstanceId')
                        if not instance_id:
                            continue
                        
                        # Get instance details
                        instance_state = instance.get('State', {}).get('Name', 'unknown')
                        instance_type = instance.get('InstanceType', 'unknown')
                        
                        # Extract IP addresses
                        private_ip = instance.get('PrivateIpAddress')
                        public_ip = instance.get('PublicIpAddress')
                        
                        # Get tags
                        tags = get_resource_tags(instance.get('Tags', []))
                        
                        # Determine if Management Token is required
                        is_managed = self._is_managed_service(tags)
                        requires_token = bool(private_ip or public_ip) and not is_managed
                        
                        # Create resource details
                        details = {
                            'instance_id': instance_id,
                            'instance_type': instance_type,
                            'state': instance_state,
                            'private_ip': private_ip,
                            'public_ip': public_ip,
                            'vpc_id': instance.get('VpcId'),
                            'subnet_id': instance.get('SubnetId'),
                            'launch_time': instance.get('LaunchTime'),
                            'platform': instance.get('Platform'),
                            'architecture': instance.get('Architecture')
                        }
                        
                        # Format resource
                        formatted_resource = self._format_resource(
                            resource_data=details,
                            resource_type='ec2-instance',
                            region=region,
                            name=instance_id,
                            requires_management_token=requires_token,
                            state=instance_state,
                            tags=tags
                        )
                        
                        resources.append(formatted_resource)
                        
        except Exception as e:
            self.logger.warning(f"Error discovering EC2 instances in {region}: {e}")
        
        return resources
    
    def _discover_vpcs(self, region: str) -> List[Dict]:
        """Discover VPCs in a region."""
        resources = []
        try:
            ec2 = self.clients[region]['ec2']
            
            paginator = ec2.get_paginator('describe_vpcs')
            for page in paginator.paginate():
                for vpc in page.get('Vpcs', []):
                    vpc_id = vpc.get('VpcId')
                    if not vpc_id:
                        continue
                    
                    # Get VPC details
                    cidr_block = vpc.get('CidrBlock')
                    state = vpc.get('State', 'unknown')
                    is_default = vpc.get('IsDefault', False)
                    
                    # Get tags
                    tags = get_resource_tags(vpc.get('Tags', []))
                    
                    # VPCs always require Management Tokens
                    requires_token = True
                    
                    # Create resource details
                    details = {
                        'vpc_id': vpc_id,
                        'cidr_block': cidr_block,
                        'state': state,
                        'is_default': is_default,
                        'dhcp_options_id': vpc.get('DhcpOptionsId'),
                        'instance_tenancy': vpc.get('InstanceTenancy')
                    }
                    
                    # Format resource
                    formatted_resource = self._format_resource(
                        resource_data=details,
                        resource_type='vpc',
                        region=region,
                        name=vpc_id,
                        requires_management_token=requires_token,
                        state=state,
                        tags=tags
                    )
                    
                    resources.append(formatted_resource)
                    
        except Exception as e:
            self.logger.warning(f"Error discovering VPCs in {region}: {e}")
        
        return resources
    
    def _discover_subnets(self, region: str) -> List[Dict]:
        """Discover subnets in a region."""
        resources = []
        try:
            ec2 = self.clients[region]['ec2']
            
            paginator = ec2.get_paginator('describe_subnets')
            for page in paginator.paginate():
                for subnet in page.get('Subnets', []):
                    subnet_id = subnet.get('SubnetId')
                    if not subnet_id:
                        continue
                    
                    # Get subnet details
                    cidr_block = subnet.get('CidrBlock')
                    state = subnet.get('State', 'unknown')
                    vpc_id = subnet.get('VpcId')
                    availability_zone = subnet.get('AvailabilityZone')
                    
                    # Get tags
                    tags = get_resource_tags(subnet.get('Tags', []))
                    
                    # Subnets always require Management Tokens
                    requires_token = True
                    
                    # Create resource details
                    details = {
                        'subnet_id': subnet_id,
                        'cidr_block': cidr_block,
                        'state': state,
                        'vpc_id': vpc_id,
                        'availability_zone': availability_zone,
                        'available_ip_address_count': subnet.get('AvailableIpAddressCount'),
                        'default_for_az': subnet.get('DefaultForAz', False),
                        'map_public_ip_on_launch': subnet.get('MapPublicIpOnLaunch', False)
                    }
                    
                    # Format resource
                    formatted_resource = self._format_resource(
                        resource_data=details,
                        resource_type='subnet',
                        region=region,
                        name=subnet_id,
                        requires_management_token=requires_token,
                        state=state,
                        tags=tags
                    )
                    
                    resources.append(formatted_resource)
                    
        except Exception as e:
            self.logger.warning(f"Error discovering subnets in {region}: {e}")
        
        return resources
    
    def _discover_load_balancers(self, region: str) -> List[Dict]:
        """Discover load balancers in a region."""
        resources = []
        
        # Discover Application Load Balancers and Network Load Balancers
        try:
            elbv2 = self.clients[region]['elbv2']
            
            paginator = elbv2.get_paginator('describe_load_balancers')
            for page in paginator.paginate():
                for lb in page.get('LoadBalancers', []):
                    lb_arn = lb.get('LoadBalancerArn')
                    lb_name = lb.get('LoadBalancerName')
                    if not lb_arn or not lb_name:
                        continue
                    
                    # Get load balancer details
                    lb_type = lb.get('Type', 'unknown')
                    state = lb.get('State', {}).get('Code', 'unknown')
                    scheme = lb.get('Scheme', 'unknown')
                    
                    # Get tags
                    tags_response = elbv2.describe_tags(ResourceArns=[lb_arn])
                    lb_tags = {}
                    if tags_response.get('TagDescriptions'):
                        lb_tags = get_resource_tags(tags_response['TagDescriptions'][0].get('Tags', []))
                    
                    # Determine if Management Token is required
                    is_managed = self._is_managed_service(lb_tags)
                    requires_token = not is_managed
                    
                    # Create resource details
                    details = {
                        'load_balancer_arn': lb_arn,
                        'load_balancer_name': lb_name,
                        'type': lb_type,
                        'state': state,
                        'scheme': scheme,
                        'vpc_id': lb.get('VpcId'),
                        'availability_zones': lb.get('AvailabilityZones', []),
                        'security_groups': lb.get('SecurityGroups', [])
                    }
                    
                    # Format resource
                    formatted_resource = self._format_resource(
                        resource_data=details,
                        resource_type=f'{lb_type.lower()}-load-balancer',
                        region=region,
                        name=lb_name,
                        requires_management_token=requires_token,
                        state=state,
                        tags=lb_tags
                    )
                    
                    resources.append(formatted_resource)
                    
        except Exception as e:
            self.logger.warning(f"Error discovering ALB/NLB in {region}: {e}")
        
        # Discover Classic Load Balancers
        try:
            elb = self.clients[region]['elb']
            
            response = elb.describe_load_balancers()
            for lb in response.get('LoadBalancerDescriptions', []):
                lb_name = lb.get('LoadBalancerName')
                if not lb_name:
                    continue
                
                # Get load balancer details
                dns_name = lb.get('DNSName')
                state = 'active' if dns_name else 'inactive'
                
                # Get tags
                try:
                    tags_response = elb.describe_tags(LoadBalancerNames=[lb_name])
                    lb_tags = {}
                    if tags_response.get('TagDescriptions'):
                        lb_tags = get_resource_tags(tags_response['TagDescriptions'][0].get('Tags', []))
                except:
                    lb_tags = {}
                
                # Determine if Management Token is required
                is_managed = self._is_managed_service(lb_tags)
                requires_token = not is_managed
                
                # Create resource details
                details = {
                    'load_balancer_name': lb_name,
                    'dns_name': dns_name,
                    'state': state,
                    'vpc_id': lb.get('VPCId'),
                    'availability_zones': lb.get('AvailabilityZones', []),
                    'security_groups': lb.get('SecurityGroups', [])
                }
                
                # Format resource
                formatted_resource = self._format_resource(
                    resource_data=details,
                    resource_type='classic-load-balancer',
                    region=region,
                    name=lb_name,
                    requires_management_token=requires_token,
                    state=state,
                    tags=lb_tags
                )
                
                resources.append(formatted_resource)
                
        except Exception as e:
            self.logger.warning(f"Error discovering Classic LB in {region}: {e}")
        
        return resources
    
    def _discover_route53_zones_and_records(self) -> List[Dict]:
        """Discover Route 53 hosted zones and DNS records (global)."""
        resources = []
        try:
            route53 = get_aws_client('route53', 'us-east-1', self.aws_config)
            zones_resp = route53.list_hosted_zones()
            for zone in zones_resp.get('HostedZones', []):
                zone_id = zone['Id'].split('/')[-1]
                zone_name = zone['Name'].rstrip('.')
                is_private = zone.get('Config', {}).get('PrivateZone', False)
                
                # Add the zone as a resource
                zone_resource = self._format_resource(
                    resource_data={
                        'zone_id': zone_id,
                        'zone_name': zone_name,
                        'private': is_private,
                        'record_set_count': zone.get('ResourceRecordSetCount', 0)
                    },
                    resource_type='route53-zone',
                    region='global',
                    name=zone_name,
                    requires_management_token=True,
                    state='private' if is_private else 'public',
                    tags={}
                )
                resources.append(zone_resource)
                
                # List all records in the zone
                paginator = route53.get_paginator('list_resource_record_sets')
                for page in paginator.paginate(HostedZoneId=zone['Id']):
                    for record in page.get('ResourceRecordSets', []):
                        record_type = record.get('Type')
                        record_name = record.get('Name', '').rstrip('.')
                        
                        record_resource = self._format_resource(
                            resource_data={
                                'zone_id': zone_id,
                                'zone_name': zone_name,
                                'record_type': record_type,
                                'record_name': record_name,
                                'ttl': record.get('TTL'),
                                'resource_records': record.get('ResourceRecords', [])
                            },
                            resource_type='route53-record',
                            region='global',
                            name=record_name,
                            requires_management_token=True,
                            state=record_type,
                            tags={}
                        )
                        resources.append(record_resource)
                        
        except Exception as e:
            self.logger.error(f"Error discovering Route 53 zones/records: {e}")
        
        return resources

    def _is_managed_service(self, tags: Dict[str, str]) -> bool:
        """Check if a resource is a managed service (Management Token-free)."""
        if not tags:
            return False
        
        for key, value in tags.items():
            key_lower = key.lower()
            value_lower = value.lower()
            
            # Common managed service indicators
            if any(indicator in key_lower for indicator in ['managed', 'service', 'aws']):
                return True
            if any(indicator in value_lower for indicator in ['managed', 'service', 'aws']):
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
        ddi_types = ['subnet', 'vpc', 'route53-zone', 'route53-record']  # Add DNS objects
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
        
        # Token calculation (SUM, not max)
        tokens_ddi = math.ceil(len(ddi_objects) / 25)
        tokens_ips = math.ceil(len(active_ips) / 13)
        tokens_assets = math.ceil(len(unique_assets) / 3)
        total_tokens = tokens_ddi + tokens_ips + tokens_assets  # SUM, not max
        
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
            'management_tokens_packs_total': tokens_packs_total,
            'tokens_ddi': tokens_ddi,
            'tokens_ips': tokens_ips,
            'tokens_assets': tokens_assets
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