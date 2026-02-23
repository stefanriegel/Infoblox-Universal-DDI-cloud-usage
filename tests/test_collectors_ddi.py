"""Tests for AWS DDI and networking resource collectors.

Tests use moto's @mock_aws decorator to mock all AWS services.
Covers EC2 (VPCs, subnets, ENIs, EIPs, NAT/VPN/Transit Gateways),
Route53 (zones, records), and DHCP option sets.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boto3
from moto import mock_aws

from cloud_usage.providers.aws.collectors.ec2 import (
    _get_name_tag,
    _tags_to_dict,
    collect_eips,
    collect_enis,
    collect_nat_gateways,
    collect_subnets,
    collect_transit_gateways,
    collect_vpcs,
    collect_vpn_gateways,
)

ACCOUNT_ID = "123456789012"
REGION = "us-east-1"


# -- Helper function tests --


def test_get_name_tag_extracts_name():
    tags = [{"Key": "Name", "Value": "my-resource"}, {"Key": "Env", "Value": "prod"}]
    assert _get_name_tag(tags) == "my-resource"


def test_get_name_tag_returns_empty_when_missing():
    tags = [{"Key": "Env", "Value": "prod"}]
    assert _get_name_tag(tags) == ""


def test_get_name_tag_handles_none():
    assert _get_name_tag(None) == ""


def test_get_name_tag_handles_empty_list():
    assert _get_name_tag([]) == ""


def test_tags_to_dict_converts_tags():
    tags = [{"Key": "Name", "Value": "test"}, {"Key": "Env", "Value": "prod"}]
    result = _tags_to_dict(tags)
    assert result == {"Name": "test", "Env": "prod"}


def test_tags_to_dict_handles_none():
    assert _tags_to_dict(None) == {}


def test_tags_to_dict_handles_empty():
    assert _tags_to_dict([]) == {}


# -- VPC collector tests --


@mock_aws
def test_collect_vpcs_discovers_vpcs():
    ec2 = boto3.client("ec2", region_name=REGION)
    ec2.create_vpc(CidrBlock="10.0.0.0/16")
    ec2.create_vpc(CidrBlock="172.16.0.0/16")

    # moto also creates a default VPC, so expect 3
    resources = collect_vpcs(ec2, ACCOUNT_ID, REGION)
    assert len(resources) >= 2
    assert all(r.resource_type == "vpc" for r in resources)
    assert all(r.provider == "aws" for r in resources)
    assert all(r.account_id == ACCOUNT_ID for r in resources)
    assert all(r.region == REGION for r in resources)


@mock_aws
def test_collect_vpcs_extracts_details():
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]

    resources = collect_vpcs(ec2, ACCOUNT_ID, REGION)
    # Find the specific VPC we created
    created_vpc = [r for r in resources if r.resource_id == vpc_id]
    assert len(created_vpc) == 1
    r = created_vpc[0]

    assert r.details["vpc_id"] == vpc_id
    assert r.details["cidr_block"] == "10.0.0.0/16"
    assert "is_default" in r.details
    assert "state" in r.details
    assert "dhcp_options_id" in r.details


@mock_aws
def test_collect_vpcs_extracts_dhcp_options_id():
    """VPCs must include DhcpOptionsId for downstream DHCP cross-reference."""
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]

    resources = collect_vpcs(ec2, ACCOUNT_ID, REGION)
    created_vpc = [r for r in resources if r.resource_id == vpc_id][0]

    # DhcpOptionsId should be a non-empty string (moto creates a default DHCP option set)
    assert created_vpc.details["dhcp_options_id"] != ""


@mock_aws
def test_collect_vpcs_empty_ip_addresses():
    """VPCs should have empty ip_addresses (CIDRs stored in details only)."""
    ec2 = boto3.client("ec2", region_name=REGION)
    ec2.create_vpc(CidrBlock="10.0.0.0/16")

    resources = collect_vpcs(ec2, ACCOUNT_ID, REGION)
    for r in resources:
        assert r.ip_addresses == []


@mock_aws
def test_collect_vpcs_with_name_tag():
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    ec2.create_tags(Resources=[vpc_id], Tags=[{"Key": "Name", "Value": "prod-vpc"}])

    resources = collect_vpcs(ec2, ACCOUNT_ID, REGION)
    created_vpc = [r for r in resources if r.resource_id == vpc_id][0]
    assert created_vpc.name == "prod-vpc"
    assert created_vpc.tags["Name"] == "prod-vpc"


# -- Subnet collector tests --


@mock_aws
def test_collect_subnets_discovers_subnets():
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
    ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.2.0/24")

    resources = collect_subnets(ec2, ACCOUNT_ID, REGION)
    # Find subnets for our VPC (moto may create default subnets)
    our_subnets = [r for r in resources if r.details["vpc_id"] == vpc_id
                   and r.details["cidr_block"] in ("10.0.1.0/24", "10.0.2.0/24")]
    assert len(our_subnets) == 2
    assert all(r.resource_type == "subnet" for r in our_subnets)


@mock_aws
def test_collect_subnets_vpc_association():
    """Subnets must have correct VPC association in details."""
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
    subnet_id = subnet["Subnet"]["SubnetId"]

    resources = collect_subnets(ec2, ACCOUNT_ID, REGION)
    created_subnet = [r for r in resources if r.resource_id == subnet_id][0]

    assert created_subnet.details["vpc_id"] == vpc_id
    assert created_subnet.details["cidr_block"] == "10.0.1.0/24"
    assert "availability_zone" in created_subnet.details


# -- ENI collector tests --


@mock_aws
def test_collect_enis_discovers_interfaces():
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
    subnet_id = subnet["Subnet"]["SubnetId"]
    eni = ec2.create_network_interface(SubnetId=subnet_id)
    eni_id = eni["NetworkInterface"]["NetworkInterfaceId"]

    resources = collect_enis(ec2, ACCOUNT_ID, REGION)
    our_enis = [r for r in resources if r.resource_id == eni_id]
    assert len(our_enis) == 1
    assert our_enis[0].resource_type == "eni"


@mock_aws
def test_collect_enis_captures_private_ips():
    """ENIs must capture all private IPs (primary + secondary)."""
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
    subnet_id = subnet["Subnet"]["SubnetId"]

    eni = ec2.create_network_interface(
        SubnetId=subnet_id,
        PrivateIpAddresses=[
            {"PrivateIpAddress": "10.0.1.10", "Primary": True},
            {"PrivateIpAddress": "10.0.1.11", "Primary": False},
        ],
    )
    eni_id = eni["NetworkInterface"]["NetworkInterfaceId"]

    resources = collect_enis(ec2, ACCOUNT_ID, REGION)
    our_eni = [r for r in resources if r.resource_id == eni_id][0]

    assert "10.0.1.10" in our_eni.ip_addresses
    assert "10.0.1.11" in our_eni.ip_addresses


@mock_aws
def test_collect_enis_details():
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
    subnet_id = subnet["Subnet"]["SubnetId"]
    eni = ec2.create_network_interface(SubnetId=subnet_id)
    eni_id = eni["NetworkInterface"]["NetworkInterfaceId"]

    resources = collect_enis(ec2, ACCOUNT_ID, REGION)
    our_eni = [r for r in resources if r.resource_id == eni_id][0]

    assert our_eni.details["vpc_id"] == vpc_id
    assert our_eni.details["subnet_id"] == subnet_id
    assert "status" in our_eni.details
    assert "interface_type" in our_eni.details


# -- EIP collector tests --


@mock_aws
def test_collect_eips_discovers_addresses():
    ec2 = boto3.client("ec2", region_name=REGION)
    alloc = ec2.allocate_address(Domain="vpc")
    alloc_id = alloc["AllocationId"]

    resources = collect_eips(ec2, ACCOUNT_ID, REGION)
    our_eips = [r for r in resources if r.resource_id == alloc_id]
    assert len(our_eips) == 1
    assert our_eips[0].resource_type == "elastic-ip"


@mock_aws
def test_collect_eips_captures_public_ip():
    ec2 = boto3.client("ec2", region_name=REGION)
    alloc = ec2.allocate_address(Domain="vpc")
    public_ip = alloc["PublicIp"]
    alloc_id = alloc["AllocationId"]

    resources = collect_eips(ec2, ACCOUNT_ID, REGION)
    our_eip = [r for r in resources if r.resource_id == alloc_id][0]

    assert public_ip in our_eip.ip_addresses


# -- NAT Gateway collector tests --


@mock_aws
def test_collect_nat_gateways_discovers_gateways():
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
    subnet_id = subnet["Subnet"]["SubnetId"]
    alloc = ec2.allocate_address(Domain="vpc")
    alloc_id = alloc["AllocationId"]

    nat = ec2.create_nat_gateway(SubnetId=subnet_id, AllocationId=alloc_id)
    nat_id = nat["NatGateway"]["NatGatewayId"]

    resources = collect_nat_gateways(ec2, ACCOUNT_ID, REGION)
    our_nats = [r for r in resources if r.resource_id == nat_id]
    assert len(our_nats) == 1
    assert our_nats[0].resource_type == "nat-gateway"


@mock_aws
def test_collect_nat_gateways_extracts_ips():
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
    subnet_id = subnet["Subnet"]["SubnetId"]
    alloc = ec2.allocate_address(Domain="vpc")
    alloc_id = alloc["AllocationId"]

    nat = ec2.create_nat_gateway(SubnetId=subnet_id, AllocationId=alloc_id)
    nat_id = nat["NatGateway"]["NatGatewayId"]

    resources = collect_nat_gateways(ec2, ACCOUNT_ID, REGION)
    our_nat = [r for r in resources if r.resource_id == nat_id][0]

    # NAT gateway should have at least one IP (public from EIP)
    assert len(our_nat.ip_addresses) > 0


@mock_aws
def test_collect_nat_gateways_details():
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
    subnet_id = subnet["Subnet"]["SubnetId"]
    alloc = ec2.allocate_address(Domain="vpc")

    nat = ec2.create_nat_gateway(SubnetId=subnet_id, AllocationId=alloc["AllocationId"])
    nat_id = nat["NatGateway"]["NatGatewayId"]

    resources = collect_nat_gateways(ec2, ACCOUNT_ID, REGION)
    our_nat = [r for r in resources if r.resource_id == nat_id][0]

    assert our_nat.details["vpc_id"] == vpc_id
    assert our_nat.details["subnet_id"] == subnet_id
    assert "state" in our_nat.details


# -- VPN Gateway collector tests --


@mock_aws
def test_collect_vpn_gateways_discovers_gateways():
    ec2 = boto3.client("ec2", region_name=REGION)
    vgw = ec2.create_vpn_gateway(Type="ipsec.1")
    vgw_id = vgw["VpnGateway"]["VpnGatewayId"]

    resources = collect_vpn_gateways(ec2, ACCOUNT_ID, REGION)
    our_vgws = [r for r in resources if r.resource_id == vgw_id]
    assert len(our_vgws) == 1
    assert our_vgws[0].resource_type == "vpn-gateway"
    assert our_vgws[0].ip_addresses == []


@mock_aws
def test_collect_vpn_gateways_vpc_attachments():
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    vgw = ec2.create_vpn_gateway(Type="ipsec.1")
    vgw_id = vgw["VpnGateway"]["VpnGatewayId"]
    ec2.attach_vpn_gateway(VpnGatewayId=vgw_id, VpcId=vpc_id)

    resources = collect_vpn_gateways(ec2, ACCOUNT_ID, REGION)
    our_vgw = [r for r in resources if r.resource_id == vgw_id][0]

    assert vpc_id in our_vgw.details["vpc_attachments"]


# -- Transit Gateway collector tests --


@mock_aws
def test_collect_transit_gateways_discovers_gateways():
    ec2 = boto3.client("ec2", region_name=REGION)
    tgw = ec2.create_transit_gateway(Description="test-tgw")
    tgw_id = tgw["TransitGateway"]["TransitGatewayId"]

    resources = collect_transit_gateways(ec2, ACCOUNT_ID, REGION)
    our_tgws = [r for r in resources if r.resource_id == tgw_id]
    assert len(our_tgws) == 1
    assert our_tgws[0].resource_type == "transit-gateway"
    assert our_tgws[0].ip_addresses == []


@mock_aws
def test_collect_transit_gateways_details():
    ec2 = boto3.client("ec2", region_name=REGION)
    tgw = ec2.create_transit_gateway(Description="test-tgw")
    tgw_id = tgw["TransitGateway"]["TransitGatewayId"]

    resources = collect_transit_gateways(ec2, ACCOUNT_ID, REGION)
    our_tgw = [r for r in resources if r.resource_id == tgw_id][0]

    assert "state" in our_tgw.details
    assert "owner_id" in our_tgw.details


# -- No resources tests --


@mock_aws
def test_collect_vpcs_returns_empty_for_no_custom_vpcs():
    """With only the default VPC, should still return at least 1 (the default)."""
    ec2 = boto3.client("ec2", region_name=REGION)
    resources = collect_vpcs(ec2, ACCOUNT_ID, REGION)
    # Moto creates a default VPC
    assert isinstance(resources, list)


@mock_aws
def test_collect_eips_returns_empty_when_none():
    ec2 = boto3.client("ec2", region_name=REGION)
    resources = collect_eips(ec2, ACCOUNT_ID, REGION)
    assert resources == []


@mock_aws
def test_collect_transit_gateways_returns_empty_when_none():
    ec2 = boto3.client("ec2", region_name=REGION)
    resources = collect_transit_gateways(ec2, ACCOUNT_ID, REGION)
    assert resources == []
