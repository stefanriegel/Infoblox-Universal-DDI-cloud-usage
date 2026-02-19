#!/usr/bin/env python3
"""
AWS Cloud Discovery for Infoblox Universal DDI Resource Counter.

Discovers AWS Native Objects and calculates Management Token requirements.
"""

import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List

from tqdm import tqdm

from shared.base_discovery import BaseDiscovery, DiscoveryConfig
from shared.output_utils import get_resource_tags

from .config import AWSConfig
from .utils import get_aws_client

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging - suppress INFO messages and boto3/botocore logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Suppress boto3 and botocore logging
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


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
            provider="aws",
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
                "ec2": get_aws_client("ec2", region, self.aws_config),
                "elbv2": get_aws_client("elbv2", region, self.aws_config),
                "elb": get_aws_client("elb", region, self.aws_config),
                "eks": get_aws_client("eks", region, self.aws_config),
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
            future_to_region = {executor.submit(self._discover_region, region): region for region in self.config.regions}

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

            # Discover allocated Elastic IPs (including unattached)
            elastic_ips = self._discover_elastic_ips(region)
            region_resources.extend(elastic_ips)

            # Discover standalone ENIs (not attached to EC2 instances)
            enis = self._discover_enis(region)
            region_resources.extend(enis)

            # Discover DHCP Option Sets (DDI objects)
            dhcp_opts = self._discover_dhcp_option_sets(region)
            region_resources.extend(dhcp_opts)

            # Discover EKS clusters (DDI objects — pod/service CIDRs)
            eks_clusters = self._discover_eks_clusters(region)
            region_resources.extend(eks_clusters)

        except Exception as e:
            self.logger.error(f"Error discovering region {region}: {e}")

        return region_resources

    def _discover_ec2_instances(self, region: str) -> List[Dict]:
        """Discover EC2 instances in a region."""
        resources = []
        try:
            ec2 = self.clients[region]["ec2"]

            # Get all instances
            paginator = ec2.get_paginator("describe_instances")
            for page in paginator.paginate():
                for reservation in page.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        instance_id = instance.get("InstanceId")
                        if not instance_id:
                            continue

                        # Get instance details
                        instance_state = instance.get("State", {}).get("Name", "unknown")
                        instance_type = instance.get("InstanceType", "unknown")

                        # Extract IP addresses
                        private_ip = instance.get("PrivateIpAddress")
                        public_ip = instance.get("PublicIpAddress")

                        # IPv6 addresses live on the network interfaces
                        ipv6_ips = []
                        for nic in instance.get("NetworkInterfaces", []) or []:
                            for entry in nic.get("Ipv6Addresses", []) or []:
                                ipv6 = entry.get("Ipv6Address")
                                if ipv6:
                                    ipv6_ips.append(ipv6)

                        # Secondary private IPv4 addresses from all NICs
                        secondary_private_ips = []
                        for nic in instance.get("NetworkInterfaces", []) or []:
                            for entry in nic.get("PrivateIpAddresses", []) or []:
                                if not entry.get("Primary", False):
                                    ip = entry.get("PrivateIpAddress")
                                    if ip:
                                        secondary_private_ips.append(ip)

                        # Get tags
                        tags = get_resource_tags(instance.get("Tags", []))

                        # Determine if Management Token is required
                        is_managed = self._is_managed_service(tags)
                        requires_token = bool(private_ip or public_ip) and not is_managed

                        # Create resource details
                        details = {
                            "instance_id": instance_id,
                            "instance_type": instance_type,
                            "state": instance_state,
                            "private_ip": private_ip,
                            "public_ip": public_ip,
                            "private_ips": secondary_private_ips,
                            "ipv6_ips": ipv6_ips,
                            "vpc_id": instance.get("VpcId"),
                            "subnet_id": instance.get("SubnetId"),
                            "launch_time": instance.get("LaunchTime"),
                            "platform": instance.get("Platform"),
                            "architecture": instance.get("Architecture"),
                        }

                        # Format resource
                        formatted_resource = self._format_resource(
                            resource_data=details,
                            resource_type="ec2-instance",
                            region=region,
                            name=instance_id,
                            requires_management_token=requires_token,
                            state=instance_state,
                            tags=tags,
                        )

                        resources.append(formatted_resource)

        except Exception as e:
            self.logger.warning(f"Error discovering EC2 instances in {region}: {e}")

        return resources

    def _discover_vpcs(self, region: str) -> List[Dict]:
        """Discover VPCs in a region."""
        resources = []
        try:
            ec2 = self.clients[region]["ec2"]

            paginator = ec2.get_paginator("describe_vpcs")
            for page in paginator.paginate():
                for vpc in page.get("Vpcs", []):
                    vpc_id = vpc.get("VpcId")
                    if not vpc_id:
                        continue

                    # Get VPC details
                    cidr_block = vpc.get("CidrBlock")
                    state = vpc.get("State", "unknown")
                    is_default = vpc.get("IsDefault", False)

                    # Get tags
                    tags = get_resource_tags(vpc.get("Tags", []))

                    # VPCs always require Management Tokens
                    requires_token = True

                    # Create resource details
                    details = {
                        "vpc_id": vpc_id,
                        "cidr_block": cidr_block,
                        "state": state,
                        "is_default": is_default,
                        "dhcp_options_id": vpc.get("DhcpOptionsId"),
                        "instance_tenancy": vpc.get("InstanceTenancy"),
                    }

                    # Format resource
                    formatted_resource = self._format_resource(
                        resource_data=details,
                        resource_type="vpc",
                        region=region,
                        name=vpc_id,
                        requires_management_token=requires_token,
                        state=state,
                        tags=tags,
                    )

                    resources.append(formatted_resource)

        except Exception as e:
            self.logger.warning(f"Error discovering VPCs in {region}: {e}")

        return resources

    def _discover_subnets(self, region: str) -> List[Dict]:
        """Discover subnets in a region."""
        resources = []
        try:
            ec2 = self.clients[region]["ec2"]

            paginator = ec2.get_paginator("describe_subnets")
            for page in paginator.paginate():
                for subnet in page.get("Subnets", []):
                    subnet_id = subnet.get("SubnetId")
                    if not subnet_id:
                        continue

                    # Get subnet details
                    cidr_block = subnet.get("CidrBlock")
                    state = subnet.get("State", "unknown")
                    vpc_id = subnet.get("VpcId")
                    availability_zone = subnet.get("AvailabilityZone")

                    # Get tags
                    tags = get_resource_tags(subnet.get("Tags", []))

                    # Subnets always require Management Tokens
                    requires_token = True

                    # Create resource details
                    details = {
                        "subnet_id": subnet_id,
                        "cidr_block": cidr_block,
                        "Ipv6CidrBlockAssociationSet": subnet.get("Ipv6CidrBlockAssociationSet", []),
                        "state": state,
                        "vpc_id": vpc_id,
                        "availability_zone": availability_zone,
                        "available_ip_address_count": subnet.get("AvailableIpAddressCount"),
                        "default_for_az": subnet.get("DefaultForAz", False),
                        "map_public_ip_on_launch": subnet.get("MapPublicIpOnLaunch", False),
                    }

                    # Format resource
                    formatted_resource = self._format_resource(
                        resource_data=details,
                        resource_type="subnet",
                        region=region,
                        name=subnet_id,
                        requires_management_token=requires_token,
                        state=state,
                        tags=tags,
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
            elbv2 = self.clients[region]["elbv2"]

            paginator = elbv2.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page.get("LoadBalancers", []):
                    lb_arn = lb.get("LoadBalancerArn")
                    lb_name = lb.get("LoadBalancerName")
                    if not lb_arn or not lb_name:
                        continue

                    # Get load balancer details
                    lb_type = lb.get("Type", "unknown")
                    state = lb.get("State", {}).get("Code", "unknown")
                    scheme = lb.get("Scheme", "unknown")

                    # Get tags
                    try:
                        tags_response = elbv2.describe_tags(ResourceArns=[lb_arn])
                        lb_tags = {}
                        if tags_response.get("TagDescriptions"):
                            lb_tags = get_resource_tags(tags_response["TagDescriptions"][0].get("Tags", []))
                    except Exception as e:
                        self.logger.warning(f"Could not describe tags for {lb_arn}: {e}")
                        lb_tags = {}

                    # Determine if Management Token is required
                    is_managed = self._is_managed_service(lb_tags)
                    requires_token = not is_managed

                    # Create resource details
                    details = {
                        "load_balancer_arn": lb_arn,
                        "load_balancer_name": lb_name,
                        "type": lb_type,
                        "state": state,
                        "scheme": scheme,
                        "vpc_id": lb.get("VpcId"),
                        "availability_zones": lb.get("AvailabilityZones", []),
                        "security_groups": lb.get("SecurityGroups", []),
                    }

                    # Format resource
                    formatted_resource = self._format_resource(
                        resource_data=details,
                        resource_type=f"{lb_type.lower()}-load-balancer",
                        region=region,
                        name=lb_name,
                        requires_management_token=requires_token,
                        state=state,
                        tags=lb_tags,
                    )

                    resources.append(formatted_resource)

        except Exception as e:
            self.logger.warning(f"Error discovering ALB/NLB in {region}: {e}")

        # Discover Classic Load Balancers
        try:
            elb = self.clients[region]["elb"]

            paginator = elb.get_paginator("describe_load_balancers")
            for response in paginator.paginate():
                for lb in response.get("LoadBalancerDescriptions", []):
                    lb_name = lb.get("LoadBalancerName")
                    if not lb_name:
                        continue

                    # Get load balancer details
                    dns_name = lb.get("DNSName")
                    state = "active" if dns_name else "inactive"

                    # Get tags
                    try:
                        tags_response = elb.describe_tags(LoadBalancerNames=[lb_name])
                        lb_tags = {}
                        if tags_response.get("TagDescriptions"):
                            lb_tags = get_resource_tags(tags_response["TagDescriptions"][0].get("Tags", []))
                    except Exception as e:
                        self.logger.warning(f"Could not describe tags for {lb_name}: {e}")
                        lb_tags = {}

                    # Determine if Management Token is required
                    is_managed = self._is_managed_service(lb_tags)
                    requires_token = not is_managed

                    # Create resource details
                    details = {
                        "load_balancer_name": lb_name,
                        "dns_name": dns_name,
                        "state": state,
                        "vpc_id": lb.get("VPCId"),
                        "availability_zones": lb.get("AvailabilityZones", []),
                        "security_groups": lb.get("SecurityGroups", []),
                    }

                    # Format resource
                    formatted_resource = self._format_resource(
                        resource_data=details,
                        resource_type="classic-load-balancer",
                        region=region,
                        name=lb_name,
                        requires_management_token=requires_token,
                        state=state,
                        tags=lb_tags,
                    )

                    resources.append(formatted_resource)

        except Exception as e:
            self.logger.warning(f"Error discovering Classic LB in {region}: {e}")

        return resources

    def _discover_elastic_ips(self, region: str) -> List[Dict]:
        """Discover allocated Elastic IPs (including unattached) in a region."""
        resources: List[Dict] = []
        try:
            ec2 = self.clients[region]["ec2"]
            resp = ec2.describe_addresses()
            for addr in resp.get("Addresses", []):
                public_ip = addr.get("PublicIp")
                allocation_id = addr.get("AllocationId") or public_ip
                if not allocation_id:
                    continue

                tags = get_resource_tags(addr.get("Tags", []))

                # Elastic IPs are allocations. We record them under the allocated key
                # so they show up clearly in active IP breakdowns.
                details = {
                    "allocation_id": addr.get("AllocationId"),
                    "association_id": addr.get("AssociationId"),
                    "domain": addr.get("Domain"),
                    "instance_id": addr.get("InstanceId"),
                    "network_interface_id": addr.get("NetworkInterfaceId"),
                    "private_ip": addr.get("PrivateIpAddress"),
                    "elastic_ip": public_ip,
                    "public_ipv4_pool": addr.get("PublicIpv4Pool"),
                }

                state = "associated" if addr.get("AssociationId") or addr.get("InstanceId") else "unassociated"

                resources.append(
                    self._format_resource(
                        resource_data=details,
                        resource_type="elastic-ip",
                        region=region,
                        name=str(allocation_id),
                        requires_management_token=True,
                        state=state,
                        tags=tags,
                    )
                )

        except Exception as e:
            self.logger.warning(f"Error discovering Elastic IPs in {region}: {e}")

        return resources

    def _discover_enis(self, region: str) -> List[Dict]:
        """Discover standalone ENIs (not attached to EC2 instances) in a region."""
        resources: List[Dict] = []
        try:
            ec2 = self.clients[region]["ec2"]

            paginator = ec2.get_paginator("describe_network_interfaces")
            for page in paginator.paginate():
                for eni in page.get("NetworkInterfaces", []):
                    eni_id = eni.get("NetworkInterfaceId")
                    if not eni_id:
                        continue

                    # Skip ENIs attached to EC2 instances (already captured via _discover_ec2_instances)
                    attachment = eni.get("Attachment") or {}
                    attached_instance = attachment.get("InstanceId")
                    if attached_instance:
                        continue

                    # Extract all private IPs
                    primary_private_ip = eni.get("PrivateIpAddress")
                    private_ips = []
                    for entry in eni.get("PrivateIpAddresses", []) or []:
                        ip = entry.get("PrivateIpAddress")
                        if ip:
                            private_ips.append(ip)

                    # Extract public IP from primary IP association
                    public_ip = None
                    association = eni.get("Association") or {}
                    public_ip = association.get("PublicIp")

                    tags = get_resource_tags(eni.get("Tags", []))
                    requires_token = bool(private_ips or public_ip)

                    details = {
                        "eni_id": eni_id,
                        "description": eni.get("Description"),
                        "vpc_id": eni.get("VpcId"),
                        "subnet_id": eni.get("SubnetId"),
                        "private_ip": primary_private_ip,
                        "private_ips": private_ips,
                        "public_ip": public_ip,
                        "status": eni.get("Status"),
                        "interface_type": eni.get("InterfaceType"),
                    }

                    resources.append(
                        self._format_resource(
                            resource_data=details,
                            resource_type="eni",
                            region=region,
                            name=eni_id,
                            requires_management_token=requires_token,
                            state=eni.get("Status", "available"),
                            tags=tags,
                        )
                    )

        except Exception as e:
            self.logger.warning(f"Error discovering ENIs in {region}: {e}")

        return resources

    def _discover_dhcp_option_sets(self, region: str) -> List[Dict]:
        """Discover DHCP option sets in a region (DDI objects)."""
        resources: List[Dict] = []
        try:
            ec2 = self.clients[region]["ec2"]

            resp = ec2.describe_dhcp_options()
            for dhcp_option in resp.get("DhcpOptions", []):
                dhcp_id = dhcp_option.get("DhcpOptionsId")
                if not dhcp_id:
                    continue

                # Parse DHCP configurations into a readable dict
                config_dict = {}
                for cfg in dhcp_option.get("DhcpConfigurations", []):
                    key = cfg.get("Key")
                    values = cfg.get("Values", [])
                    if key and values:
                        config_dict[key] = [v.get("Value") for v in values]

                tags = get_resource_tags(dhcp_option.get("Tags", []))

                details = {
                    "dhcp_options_id": dhcp_id,
                    "configurations": config_dict,
                    "owner_id": dhcp_option.get("OwnerId"),
                }

                resources.append(
                    self._format_resource(
                        resource_data=details,
                        resource_type="dhcp-option-set",
                        region=region,
                        name=dhcp_id,
                        requires_management_token=True,
                        state="available",
                        tags=tags,
                    )
                )

        except Exception as e:
            self.logger.warning(f"Error discovering DHCP option sets in {region}: {e}")

        return resources

    def _discover_eks_clusters(self, region: str) -> List[Dict]:
        """Discover EKS clusters and their pod/service CIDR ranges (DDI objects)."""
        resources: List[Dict] = []
        try:
            eks = self.clients[region]["eks"]

            cluster_names = []
            paginator = eks.get_paginator("list_clusters")
            for page in paginator.paginate():
                cluster_names.extend(page.get("clusters", []))

            for cluster_name in cluster_names:
                try:
                    resp = eks.describe_cluster(name=cluster_name)
                    cluster = resp.get("cluster", {})

                    k8s_net = cluster.get("kubernetesNetworkConfig", {}) or {}
                    service_cidr = k8s_net.get("serviceIpv4Cidr")
                    pod_cidr = None
                    # EKS pod CIDR comes from VPC CNI or custom networking; not always in API.
                    # Check for IP family info.
                    ip_family = k8s_net.get("ipFamily")

                    resources_vpc = cluster.get("resourcesVpcConfig", {}) or {}
                    vpc_id = resources_vpc.get("vpcId")
                    subnet_ids = resources_vpc.get("subnetIds", [])

                    status = (cluster.get("status") or "unknown").lower()
                    version = cluster.get("version")
                    tags = cluster.get("tags", {}) or {}

                    details = {
                        "cluster_name": cluster_name,
                        "service_ipv4_cidr": service_cidr,
                        "pod_cidr": pod_cidr,
                        "ip_family": ip_family,
                        "vpc_id": vpc_id,
                        "subnet_ids": subnet_ids,
                        "kubernetes_version": version,
                        "platform_version": cluster.get("platformVersion"),
                    }

                    resources.append(
                        self._format_resource(
                            resource_data=details,
                            resource_type="eks-cluster",
                            region=region,
                            name=cluster_name,
                            requires_management_token=True,
                            state=status,
                            tags=tags,
                        )
                    )

                except Exception as e:
                    self.logger.warning(f"Error describing EKS cluster {cluster_name} in {region}: {e}")

        except Exception as e:
            error_msg = str(e)
            if "AccessDeniedException" in error_msg or "is not authorized" in error_msg:
                self.logger.debug(f"EKS API not authorized in {region}: {error_msg}")
            else:
                self.logger.warning(f"Error discovering EKS clusters in {region}: {e}")

        return resources

    def _discover_route53_zones_and_records(self) -> List[Dict]:
        """Discover Route 53 hosted zones and DNS records (global)."""
        resources = []
        try:
            route53 = get_aws_client("route53", "us-east-1", self.aws_config)

            zones_paginator = route53.get_paginator("list_hosted_zones")
            for zones_resp in zones_paginator.paginate():
                for zone in zones_resp.get("HostedZones", []):
                    zone_id = zone["Id"].split("/")[-1]
                    zone_name = zone["Name"].rstrip(".")
                    is_private = zone.get("Config", {}).get("PrivateZone", False)

                    # Add the zone as a resource
                    zone_resource = self._format_resource(
                        resource_data={
                            "zone_id": zone_id,
                            "zone_name": zone_name,
                            "private": is_private,
                            "record_set_count": zone.get("ResourceRecordSetCount", 0),
                        },
                        resource_type="route53-zone",
                        region="global",
                        name=zone_name,
                        requires_management_token=True,
                        state="private" if is_private else "public",
                        tags={},
                    )
                    resources.append(zone_resource)

                    # List all records in the zone
                    paginator = route53.get_paginator("list_resource_record_sets")
                    for page in paginator.paginate(HostedZoneId=zone["Id"]):
                        for record in page.get("ResourceRecordSets", []):
                            record_type = record.get("Type")
                            record_name = record.get("Name", "").rstrip(".")

                            record_resource = self._format_resource(
                                resource_data={
                                    "zone_id": zone_id,
                                    "zone_name": zone_name,
                                    "record_type": record_type,
                                    "record_name": record_name,
                                    "ttl": record.get("TTL"),
                                    "resource_records": record.get("ResourceRecords", []),
                                },
                                resource_type="route53-record",
                                region="global",
                                name=record_name,
                                requires_management_token=True,
                                state=record_type,
                                tags={},
                            )
                            resources.append(record_resource)

        except Exception as e:
            self.logger.error(f"Error discovering Route 53 zones/records: {e}")

        return resources

    def _is_managed_service(self, tags: Dict[str, str]) -> bool:
        """Check if a resource is a managed service (Management Token-free).

        Detects resources created/managed by AWS platform services (ECS tasks,
        Lambda ENIs, EKS system pods, etc.). Avoids false positives from generic
        aws:cloudformation:* or aws:autoscaling:* auto-tags.
        """
        if not tags:
            return False

        # Specific tag key prefixes that indicate AWS-managed resources
        managed_key_prefixes = (
            "aws:ecs:",
            "aws:eks:",
            "eks.amazonaws.com/",
            "lambda:",
            "aws:lambda:",
            "elasticmapreduce:",
            "aws:elasticmapreduce:",
        )
        managed_key_exact = {"managed-by", "managed_by", "aws-managed"}

        for key, value in tags.items():
            key_lower = key.lower()
            value_lower = value.lower()

            if key_lower in managed_key_exact:
                return True
            if any(key_lower.startswith(prefix) for prefix in managed_key_prefixes):
                return True
            if value_lower in ("aws-managed", "ecs", "lambda", "eks"):
                return True

        return False

    def get_management_token_free_assets(self) -> List[Dict]:
        """
        Get list of Management Token-free assets.

        Returns:
            List of resources that don't require Management Tokens
        """
        resources = self.discover_native_objects()
        return [obj for obj in resources if not obj["requires_management_token"]]

    def get_scanned_account_ids(self) -> list:
        """Return the AWS Account ID(s) scanned."""
        import boto3

        session = boto3.Session()
        sts = session.client("sts")
        try:
            identity = sts.get_caller_identity()
            return [identity.get("Account")]
        except Exception:
            return []
