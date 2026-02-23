"""EC2 networking resource collectors.

Discovers VPCs, subnets, ENIs, Elastic IPs, NAT Gateways, VPN Gateways,
and Transit Gateways. All functions return list[CloudResource] and use
boto3 paginators where the API supports pagination.
"""

from __future__ import annotations

from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource


def _get_name_tag(tags: list[dict] | None) -> str:
    """Extract the Name tag value from an AWS tag list.

    Args:
        tags: List of {"Key": ..., "Value": ...} dicts, or None.

    Returns:
        The Name tag value, or empty string if not found.
    """
    if not tags:
        return ""
    for tag in tags:
        if tag.get("Key") == "Name":
            return tag.get("Value", "")
    return ""


def _tags_to_dict(tags: list[dict] | None) -> dict[str, str]:
    """Convert an AWS tag list to a plain dict.

    Args:
        tags: List of {"Key": ..., "Value": ...} dicts, or None.

    Returns:
        Dict mapping tag keys to values.
    """
    if not tags:
        return {}
    return {tag["Key"]: tag["Value"] for tag in tags if "Key" in tag}


@retry_with_backoff(max_retries=3)
def collect_vpcs(
    ec2_client,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover all VPCs in a region.

    Uses describe_vpcs paginator. Extracts CIDR block, default status,
    owner ID, and DHCP option set association for downstream cross-reference.

    Args:
        ec2_client: boto3 EC2 client for the target account/region.
        account_id: AWS account ID owning these resources.
        region: AWS region being scanned.

    Returns:
        List of CloudResource with resource_type="vpc".
    """
    resources: list[CloudResource] = []
    paginator = ec2_client.get_paginator("describe_vpcs")

    for page in paginator.paginate():
        for vpc in page.get("Vpcs", []):
            tags = vpc.get("Tags", [])
            resources.append(
                CloudResource(
                    resource_id=vpc["VpcId"],
                    resource_type="vpc",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=_get_name_tag(tags),
                    ip_addresses=[],
                    tags=_tags_to_dict(tags),
                    details={
                        "vpc_id": vpc["VpcId"],
                        "cidr_block": vpc.get("CidrBlock", ""),
                        "is_default": vpc.get("IsDefault", False),
                        "state": vpc.get("State", ""),
                        "owner_id": vpc.get("OwnerId", ""),
                        "dhcp_options_id": vpc.get("DhcpOptionsId", ""),
                    },
                )
            )

    return resources


@retry_with_backoff(max_retries=3)
def collect_subnets(
    ec2_client,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover all subnets in a region.

    Uses describe_subnets paginator. Captures VPC association and
    availability zone placement.

    Args:
        ec2_client: boto3 EC2 client for the target account/region.
        account_id: AWS account ID owning these resources.
        region: AWS region being scanned.

    Returns:
        List of CloudResource with resource_type="subnet".
    """
    resources: list[CloudResource] = []
    paginator = ec2_client.get_paginator("describe_subnets")

    for page in paginator.paginate():
        for subnet in page.get("Subnets", []):
            tags = subnet.get("Tags", [])
            resources.append(
                CloudResource(
                    resource_id=subnet["SubnetId"],
                    resource_type="subnet",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=_get_name_tag(tags),
                    ip_addresses=[],
                    tags=_tags_to_dict(tags),
                    details={
                        "vpc_id": subnet.get("VpcId", ""),
                        "cidr_block": subnet.get("CidrBlock", ""),
                        "availability_zone": subnet.get("AvailabilityZone", ""),
                        "owner_id": subnet.get("OwnerId", ""),
                    },
                )
            )

    return resources


@retry_with_backoff(max_retries=3)
def collect_enis(
    ec2_client,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover all Elastic Network Interfaces in a region.

    Uses describe_network_interfaces paginator (MUST paginate per Pitfall 7).
    Captures ALL private IPs (primary + secondary), public IPs from
    associations, and IPv6 addresses.

    All ENIs are included -- the asset_dedup module handles folding
    attached ENIs into their parent resources.

    Args:
        ec2_client: boto3 EC2 client for the target account/region.
        account_id: AWS account ID owning these resources.
        region: AWS region being scanned.

    Returns:
        List of CloudResource with resource_type="eni".
    """
    resources: list[CloudResource] = []
    paginator = ec2_client.get_paginator("describe_network_interfaces")

    for page in paginator.paginate():
        for eni in page.get("NetworkInterfaces", []):
            # Extract ALL IPs: primary + secondary private, public, IPv6
            ip_addresses: list[str] = []

            for private_ip_entry in eni.get("PrivateIpAddresses", []):
                private_ip = private_ip_entry.get("PrivateIpAddress")
                if private_ip:
                    ip_addresses.append(private_ip)

                # Public IP associated with this private IP
                assoc = private_ip_entry.get("Association", {})
                public_ip = assoc.get("PublicIp")
                if public_ip and public_ip not in ip_addresses:
                    ip_addresses.append(public_ip)

            # IPv6 addresses
            for ipv6_entry in eni.get("Ipv6Addresses", []):
                ipv6_addr = ipv6_entry.get("Ipv6Address")
                if ipv6_addr and ipv6_addr not in ip_addresses:
                    ip_addresses.append(ipv6_addr)

            attachment = eni.get("Attachment", {})
            resources.append(
                CloudResource(
                    resource_id=eni["NetworkInterfaceId"],
                    resource_type="eni",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=_get_name_tag(eni.get("TagSet", [])),
                    ip_addresses=ip_addresses,
                    tags=_tags_to_dict(eni.get("TagSet", [])),
                    details={
                        "vpc_id": eni.get("VpcId", ""),
                        "subnet_id": eni.get("SubnetId", ""),
                        "attachment_id": attachment.get("AttachmentId"),
                        "attachment_instance_id": attachment.get("InstanceId"),
                        "status": eni.get("Status", ""),
                        "interface_type": eni.get("InterfaceType", ""),
                        "owner_id": eni.get("OwnerId", ""),
                    },
                )
            )

    return resources


@retry_with_backoff(max_retries=3)
def collect_eips(
    ec2_client,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover all Elastic IP addresses in a region.

    Uses describe_addresses (no paginator needed -- returns all EIPs).
    Captures both public and private IPs (if associated).

    Args:
        ec2_client: boto3 EC2 client for the target account/region.
        account_id: AWS account ID owning these resources.
        region: AWS region being scanned.

    Returns:
        List of CloudResource with resource_type="elastic-ip".
    """
    resources: list[CloudResource] = []
    response = ec2_client.describe_addresses()

    for addr in response.get("Addresses", []):
        ip_addresses: list[str] = []

        if addr.get("PublicIp"):
            ip_addresses.append(addr["PublicIp"])
        if addr.get("PrivateIpAddress"):
            ip_addresses.append(addr["PrivateIpAddress"])

        tags = addr.get("Tags", [])
        resources.append(
            CloudResource(
                resource_id=addr.get("AllocationId", addr.get("PublicIp", "")),
                resource_type="elastic-ip",
                provider="aws",
                account_id=account_id,
                region=region,
                name=_get_name_tag(tags),
                ip_addresses=ip_addresses,
                tags=_tags_to_dict(tags),
                details={
                    "vpc_id": addr.get("AssociationId") and addr.get("NetworkInterfaceId") and "",
                    "instance_id": addr.get("InstanceId"),
                    "association_id": addr.get("AssociationId"),
                    "network_interface_id": addr.get("NetworkInterfaceId"),
                },
            )
        )

    return resources


@retry_with_backoff(max_retries=3)
def collect_nat_gateways(
    ec2_client,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover all NAT Gateways in a region (excluding deleted).

    Uses describe_nat_gateways paginator. Extracts both private and
    public IPs from NatGatewayAddresses.

    Args:
        ec2_client: boto3 EC2 client for the target account/region.
        account_id: AWS account ID owning these resources.
        region: AWS region being scanned.

    Returns:
        List of CloudResource with resource_type="nat-gateway".
    """
    resources: list[CloudResource] = []
    paginator = ec2_client.get_paginator("describe_nat_gateways")

    for page in paginator.paginate():
        for nat_gw in page.get("NatGateways", []):
            if nat_gw.get("State") == "deleted":
                continue

            ip_addresses: list[str] = []
            for addr in nat_gw.get("NatGatewayAddresses", []):
                if addr.get("PrivateIp"):
                    ip_addresses.append(addr["PrivateIp"])
                if addr.get("PublicIp"):
                    ip_addresses.append(addr["PublicIp"])

            tags = nat_gw.get("Tags", [])
            resources.append(
                CloudResource(
                    resource_id=nat_gw["NatGatewayId"],
                    resource_type="nat-gateway",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=_get_name_tag(tags),
                    ip_addresses=ip_addresses,
                    tags=_tags_to_dict(tags),
                    details={
                        "vpc_id": nat_gw.get("VpcId", ""),
                        "subnet_id": nat_gw.get("SubnetId", ""),
                        "state": nat_gw.get("State", ""),
                    },
                )
            )

    return resources


@retry_with_backoff(max_retries=3)
def collect_vpn_gateways(
    ec2_client,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover all VPN Gateways in a region (excluding deleted).

    Uses describe_vpn_gateways (no paginator). VPN Gateways don't have
    direct IPs; they are DDI/infrastructure resources.

    Args:
        ec2_client: boto3 EC2 client for the target account/region.
        account_id: AWS account ID owning these resources.
        region: AWS region being scanned.

    Returns:
        List of CloudResource with resource_type="vpn-gateway".
    """
    resources: list[CloudResource] = []
    response = ec2_client.describe_vpn_gateways()

    for vgw in response.get("VpnGateways", []):
        if vgw.get("State") == "deleted":
            continue

        vpc_attachments = [
            att["VpcId"]
            for att in vgw.get("VpcAttachments", [])
            if "VpcId" in att
        ]

        tags = vgw.get("Tags", [])
        resources.append(
            CloudResource(
                resource_id=vgw["VpnGatewayId"],
                resource_type="vpn-gateway",
                provider="aws",
                account_id=account_id,
                region=region,
                name=_get_name_tag(tags),
                ip_addresses=[],
                tags=_tags_to_dict(tags),
                details={
                    "vpc_attachments": vpc_attachments,
                },
            )
        )

    return resources


@retry_with_backoff(max_retries=3)
def collect_transit_gateways(
    ec2_client,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover all Transit Gateways in a region (excluding deleted/deleting).

    Uses describe_transit_gateways paginator. Transit Gateways are
    infrastructure resources without direct IPs.

    Args:
        ec2_client: boto3 EC2 client for the target account/region.
        account_id: AWS account ID owning these resources.
        region: AWS region being scanned.

    Returns:
        List of CloudResource with resource_type="transit-gateway".
    """
    resources: list[CloudResource] = []
    paginator = ec2_client.get_paginator("describe_transit_gateways")

    for page in paginator.paginate():
        for tgw in page.get("TransitGateways", []):
            if tgw.get("State") in ("deleted", "deleting"):
                continue

            tags = tgw.get("Tags", [])
            resources.append(
                CloudResource(
                    resource_id=tgw["TransitGatewayId"],
                    resource_type="transit-gateway",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=_get_name_tag(tags),
                    ip_addresses=[],
                    tags=_tags_to_dict(tags),
                    details={
                        "state": tgw.get("State", ""),
                        "owner_id": tgw.get("OwnerId", ""),
                    },
                )
            )

    return resources
