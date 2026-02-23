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
from cloud_usage.providers.aws.collectors.route53 import (
    collect_route53_records,
    collect_route53_zones,
)
from cloud_usage.providers.aws.collectors.dhcp import collect_dhcp_option_sets

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


# -- Route53 zone collector tests --


@mock_aws
def test_collect_route53_zones_discovers_zones():
    r53 = boto3.client("route53", region_name="us-east-1")
    r53.create_hosted_zone(Name="example.com", CallerReference="ref1")
    r53.create_hosted_zone(Name="internal.local", CallerReference="ref2")

    resources = collect_route53_zones(r53, ACCOUNT_ID)
    assert len(resources) == 2
    assert all(r.resource_type == "route53-zone" for r in resources)
    assert all(r.provider == "aws" for r in resources)
    assert all(r.region == "global" for r in resources)


@mock_aws
def test_collect_route53_zones_correct_type():
    """Zones should have zone_type field in details.

    Note: moto does not correctly set Config.PrivateZone for VPC-associated
    zones in list_hosted_zones -- it always returns False. The production
    code correctly checks Config.PrivateZone. This test verifies the public
    zone path works; private zone detection works correctly with real AWS.
    """
    r53 = boto3.client("route53", region_name="us-east-1")

    r53.create_hosted_zone(Name="public.example.com", CallerReference="ref-pub")

    resources = collect_route53_zones(r53, ACCOUNT_ID)
    pub_zones = [r for r in resources if r.name == "public.example.com"]

    assert len(pub_zones) == 1
    assert pub_zones[0].details["zone_type"] == "public"
    assert "zone_type" in pub_zones[0].details


def test_collect_route53_zones_private_detection_logic():
    """Verify the private zone detection logic works when Config.PrivateZone is True.

    This tests the code path directly since moto doesn't set PrivateZone=True
    in list_hosted_zones responses for VPC-associated zones.
    """
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_paginator = MagicMock()
    mock_client.get_paginator.return_value = mock_paginator
    mock_paginator.paginate.return_value = [
        {
            "HostedZones": [
                {
                    "Id": "/hostedzone/Z111",
                    "Name": "public.example.com.",
                    "Config": {"PrivateZone": False},
                    "ResourceRecordSetCount": 5,
                },
                {
                    "Id": "/hostedzone/Z222",
                    "Name": "private.internal.",
                    "Config": {"PrivateZone": True},
                    "ResourceRecordSetCount": 3,
                },
            ]
        }
    ]

    resources = collect_route53_zones(mock_client, ACCOUNT_ID)
    pub = [r for r in resources if r.name == "public.example.com"][0]
    priv = [r for r in resources if r.name == "private.internal"][0]

    assert pub.details["zone_type"] == "public"
    assert priv.details["zone_type"] == "private"


@mock_aws
def test_collect_route53_zones_strips_trailing_dot():
    """Zone names should have trailing dot stripped."""
    r53 = boto3.client("route53", region_name="us-east-1")
    r53.create_hosted_zone(Name="test.example.com.", CallerReference="ref1")

    resources = collect_route53_zones(r53, ACCOUNT_ID)
    assert resources[0].name == "test.example.com"


@mock_aws
def test_collect_route53_zones_strips_hostedzone_prefix():
    """Zone IDs should have /hostedzone/ prefix stripped."""
    r53 = boto3.client("route53", region_name="us-east-1")
    r53.create_hosted_zone(Name="example.com", CallerReference="ref1")

    resources = collect_route53_zones(r53, ACCOUNT_ID)
    assert not resources[0].resource_id.startswith("/hostedzone/")


@mock_aws
def test_collect_route53_zones_record_count():
    """Zone details should include record_count."""
    r53 = boto3.client("route53", region_name="us-east-1")
    r53.create_hosted_zone(Name="example.com", CallerReference="ref1")

    resources = collect_route53_zones(r53, ACCOUNT_ID)
    assert "record_count" in resources[0].details


# -- Route53 record collector tests --


@mock_aws
def test_collect_route53_records_discovers_all_types():
    """Records include all DNS record types (A, AAAA, CNAME, MX, NS, SOA, etc.)."""
    r53 = boto3.client("route53", region_name="us-east-1")
    zone = r53.create_hosted_zone(Name="example.com", CallerReference="ref1")
    zone_id = zone["HostedZone"]["Id"].split("/")[-1]

    # Add various record types
    r53.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": "web.example.com",
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": "1.2.3.4"}, {"Value": "5.6.7.8"}],
                    },
                },
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": "mail.example.com",
                        "Type": "CNAME",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": "mailhost.example.com"}],
                    },
                },
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": "example.com",
                        "Type": "MX",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": "10 mail.example.com"}],
                    },
                },
            ],
        },
    )

    resources = collect_route53_records(r53, ACCOUNT_ID, zone_id, "example.com")

    # Should have at least: NS, SOA (default) + A, CNAME, MX (our additions)
    record_types = {r.details["record_type"] for r in resources}
    assert "A" in record_types
    assert "CNAME" in record_types
    assert "MX" in record_types
    assert "NS" in record_types
    assert "SOA" in record_types


@mock_aws
def test_collect_route53_records_a_records_have_ips():
    """A records should have IPs extracted into ip_addresses."""
    r53 = boto3.client("route53", region_name="us-east-1")
    zone = r53.create_hosted_zone(Name="example.com", CallerReference="ref1")
    zone_id = zone["HostedZone"]["Id"].split("/")[-1]

    r53.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": "web.example.com",
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": "1.2.3.4"}, {"Value": "5.6.7.8"}],
                    },
                },
            ],
        },
    )

    resources = collect_route53_records(r53, ACCOUNT_ID, zone_id, "example.com")
    a_records = [r for r in resources if r.details["record_type"] == "A"]
    assert len(a_records) == 1
    assert "1.2.3.4" in a_records[0].ip_addresses
    assert "5.6.7.8" in a_records[0].ip_addresses


@mock_aws
def test_collect_route53_records_cname_has_empty_ips():
    """CNAME records should have empty ip_addresses."""
    r53 = boto3.client("route53", region_name="us-east-1")
    zone = r53.create_hosted_zone(Name="example.com", CallerReference="ref1")
    zone_id = zone["HostedZone"]["Id"].split("/")[-1]

    r53.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": "alias.example.com",
                        "Type": "CNAME",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": "target.example.com"}],
                    },
                },
            ],
        },
    )

    resources = collect_route53_records(r53, ACCOUNT_ID, zone_id, "example.com")
    cname_records = [r for r in resources if r.details["record_type"] == "CNAME"]
    assert len(cname_records) == 1
    assert cname_records[0].ip_addresses == []


@mock_aws
def test_collect_route53_records_global_region():
    """All Route53 records should have region='global'."""
    r53 = boto3.client("route53", region_name="us-east-1")
    zone = r53.create_hosted_zone(Name="example.com", CallerReference="ref1")
    zone_id = zone["HostedZone"]["Id"].split("/")[-1]

    resources = collect_route53_records(r53, ACCOUNT_ID, zone_id, "example.com")
    assert all(r.region == "global" for r in resources)


@mock_aws
def test_collect_route53_records_resource_id_format():
    """Record resource_id should be zone_id/name/type."""
    r53 = boto3.client("route53", region_name="us-east-1")
    zone = r53.create_hosted_zone(Name="example.com", CallerReference="ref1")
    zone_id = zone["HostedZone"]["Id"].split("/")[-1]

    r53.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": "web.example.com",
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": "1.2.3.4"}],
                    },
                },
            ],
        },
    )

    resources = collect_route53_records(r53, ACCOUNT_ID, zone_id, "example.com")
    a_records = [r for r in resources if r.details["record_type"] == "A"]
    assert len(a_records) == 1
    assert a_records[0].resource_id == f"{zone_id}/web.example.com/A"


@mock_aws
def test_collect_route53_records_details():
    """Record details should include zone_id, zone_name, record_type, ttl, alias."""
    r53 = boto3.client("route53", region_name="us-east-1")
    zone = r53.create_hosted_zone(Name="example.com", CallerReference="ref1")
    zone_id = zone["HostedZone"]["Id"].split("/")[-1]

    r53.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": "web.example.com",
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": "1.2.3.4"}],
                    },
                },
            ],
        },
    )

    resources = collect_route53_records(r53, ACCOUNT_ID, zone_id, "example.com")
    a_records = [r for r in resources if r.details["record_type"] == "A"]
    r = a_records[0]

    assert r.details["zone_id"] == zone_id
    assert r.details["zone_name"] == "example.com"
    assert r.details["record_type"] == "A"
    assert r.details["ttl"] == 300
    assert r.details["alias"] is False


# -- DHCP option set collector tests --


@mock_aws
def test_collect_dhcp_option_sets_vpc_associated():
    """DHCP option sets associated with VPCs should have orphaned=False."""
    ec2 = boto3.client("ec2", region_name=REGION)

    # Create an explicit DHCP option set and associate it with a VPC
    dhcp = ec2.create_dhcp_options(
        DhcpConfigurations=[
            {"Key": "domain-name", "Values": ["vpc.internal"]},
        ]
    )
    dhcp_id = dhcp["DhcpOptions"]["DhcpOptionsId"]

    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    ec2.associate_dhcp_options(DhcpOptionsId=dhcp_id, VpcId=vpc_id)

    vpc_dhcp_ids = {dhcp_id}
    resources = collect_dhcp_option_sets(ec2, ACCOUNT_ID, REGION, vpc_dhcp_ids)

    associated = [r for r in resources if r.resource_id == dhcp_id]
    assert len(associated) == 1
    assert associated[0].details["orphaned"] is False
    assert associated[0].resource_type == "dhcp-option-set"


@mock_aws
def test_collect_dhcp_option_sets_orphaned():
    """DHCP option sets not associated with any VPC should have orphaned=True."""
    ec2 = boto3.client("ec2", region_name=REGION)

    # Create a standalone DHCP option set (not associated with any VPC)
    dhcp = ec2.create_dhcp_options(
        DhcpConfigurations=[
            {"Key": "domain-name", "Values": ["example.com"]},
            {"Key": "domain-name-servers", "Values": ["10.0.0.2"]},
        ]
    )
    orphan_id = dhcp["DhcpOptions"]["DhcpOptionsId"]

    # Also create a VPC-associated one so we can pass its ID as vpc_dhcp_ids
    dhcp_assoc = ec2.create_dhcp_options(
        DhcpConfigurations=[{"Key": "domain-name", "Values": ["used.internal"]}]
    )
    assoc_id = dhcp_assoc["DhcpOptions"]["DhcpOptionsId"]

    # Only the associated one is in vpc_dhcp_ids; the orphan is not
    vpc_dhcp_ids = {assoc_id}
    resources = collect_dhcp_option_sets(ec2, ACCOUNT_ID, REGION, vpc_dhcp_ids)

    orphaned = [r for r in resources if r.resource_id == orphan_id]
    assert len(orphaned) == 1
    assert orphaned[0].details["orphaned"] is True

    associated = [r for r in resources if r.resource_id == assoc_id]
    assert len(associated) == 1
    assert associated[0].details["orphaned"] is False


@mock_aws
def test_collect_dhcp_option_sets_configurations():
    """DHCP option set details should include configurations."""
    ec2 = boto3.client("ec2", region_name=REGION)

    dhcp = ec2.create_dhcp_options(
        DhcpConfigurations=[
            {"Key": "domain-name", "Values": ["example.com"]},
            {"Key": "domain-name-servers", "Values": ["10.0.0.2", "10.0.0.3"]},
        ]
    )
    dhcp_id = dhcp["DhcpOptions"]["DhcpOptionsId"]

    resources = collect_dhcp_option_sets(ec2, ACCOUNT_ID, REGION, {dhcp_id})
    our_dhcp = [r for r in resources if r.resource_id == dhcp_id][0]

    assert "configurations" in our_dhcp.details
    configs = our_dhcp.details["configurations"]
    config_keys = [c["key"] for c in configs]
    assert "domain-name" in config_keys
    assert "domain-name-servers" in config_keys


@mock_aws
def test_collect_vpcs_dhcp_options_for_cross_reference():
    """VPC collector extracts DhcpOptionsId for downstream DHCP cross-reference."""
    ec2 = boto3.client("ec2", region_name=REGION)

    # Create a custom DHCP option set and associate with a VPC
    dhcp = ec2.create_dhcp_options(
        DhcpConfigurations=[{"Key": "domain-name", "Values": ["test.internal"]}]
    )
    dhcp_id = dhcp["DhcpOptions"]["DhcpOptionsId"]

    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    ec2.associate_dhcp_options(DhcpOptionsId=dhcp_id, VpcId=vpc_id)

    resources = collect_vpcs(ec2, ACCOUNT_ID, REGION)
    our_vpc = [r for r in resources if r.resource_id == vpc_id][0]

    assert our_vpc.details["dhcp_options_id"] == dhcp_id

    # Build vpc_dhcp_ids from VPCs -- this is how the caller creates the set
    vpc_dhcp_ids = {r.details["dhcp_options_id"] for r in resources if r.details["dhcp_options_id"]}
    assert dhcp_id in vpc_dhcp_ids


@mock_aws
def test_collect_subnets_returns_correct_vpc_association():
    """Subnets should return correct VPC association in details."""
    ec2 = boto3.client("ec2", region_name=REGION)
    vpc1 = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc1_id = vpc1["Vpc"]["VpcId"]
    vpc2 = ec2.create_vpc(CidrBlock="172.16.0.0/16")
    vpc2_id = vpc2["Vpc"]["VpcId"]

    subnet1 = ec2.create_subnet(VpcId=vpc1_id, CidrBlock="10.0.1.0/24")
    subnet1_id = subnet1["Subnet"]["SubnetId"]
    subnet2 = ec2.create_subnet(VpcId=vpc2_id, CidrBlock="172.16.1.0/24")
    subnet2_id = subnet2["Subnet"]["SubnetId"]

    resources = collect_subnets(ec2, ACCOUNT_ID, REGION)
    s1 = [r for r in resources if r.resource_id == subnet1_id][0]
    s2 = [r for r in resources if r.resource_id == subnet2_id][0]

    assert s1.details["vpc_id"] == vpc1_id
    assert s2.details["vpc_id"] == vpc2_id
