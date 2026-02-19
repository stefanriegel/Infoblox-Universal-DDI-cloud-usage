"""Tests for shared/resource_counter.py — DDI classification, active IP dedup, edge cases."""

import pytest

from shared.resource_counter import ResourceCount, ResourceCounter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_resource(resource_type, region="us-east-1", details=None, name="test"):
    return {
        "resource_id": f"test:{region}:{resource_type}:{name}",
        "resource_type": resource_type,
        "region": region,
        "name": name,
        "state": "active",
        "requires_management_token": True,
        "tags": {},
        "details": details or {},
        "discovered_at": "2024-01-01T00:00:00",
    }


# ---------------------------------------------------------------------------
# DDI Classification
# ---------------------------------------------------------------------------
class TestDDIClassification:
    """Verify that all expected resource types are classified as DDI objects."""

    @pytest.mark.parametrize(
        "provider,resource_type",
        [
            # AWS DDI types
            ("aws", "subnet"),
            ("aws", "vpc"),
            ("aws", "route53-zone"),
            ("aws", "route53-record"),
            ("aws", "dhcp-option-set"),
            ("aws", "eks-cluster"),
            # Azure DDI types
            ("azure", "dns-zone"),
            ("azure", "dns-record"),
            ("azure", "subnet"),
            ("azure", "vnet"),
            ("azure", "aks-cluster"),
            # GCP DDI types
            ("gcp", "subnet"),
            ("gcp", "vpc-network"),
            ("gcp", "dns-zone"),
            ("gcp", "dns-record"),
            ("gcp", "gke-cluster"),
        ],
    )
    def test_ddi_type_counted(self, provider, resource_type):
        counter = ResourceCounter(provider)
        resources = [_make_resource(resource_type)]
        result = counter.count_resources(resources)
        assert result.ddi_objects == 1, f"{resource_type} should be a DDI object for {provider}"
        assert resource_type in result.ddi_breakdown

    @pytest.mark.parametrize(
        "provider,resource_type",
        [
            ("aws", "ec2-instance"),
            ("azure", "vm"),
            ("gcp", "compute-instance"),
            ("gcp", "cloud-nat"),
            ("gcp", "reserved-ip"),
        ],
    )
    def test_non_ddi_type_not_counted(self, provider, resource_type):
        counter = ResourceCounter(provider)
        resources = [_make_resource(resource_type)]
        result = counter.count_resources(resources)
        assert result.ddi_objects == 0, f"{resource_type} should NOT be a DDI object for {provider}"

    def test_dns_soa_ns_records_counted_as_ddi(self):
        """SOA and NS records should be counted — they use resource_type 'dns-record'."""
        for provider in ("aws", "azure", "gcp"):
            rtype = "route53-record" if provider == "aws" else "dns-record"
            counter = ResourceCounter(provider)
            resources = [
                _make_resource(rtype, name="soa-record"),
                _make_resource(rtype, name="ns-record"),
            ]
            result = counter.count_resources(resources)
            assert result.ddi_objects == 2


# ---------------------------------------------------------------------------
# Active IP Deduplication
# ---------------------------------------------------------------------------
class TestActiveIPDedup:
    """IP-space-aware deduplication — same IP in different VPCs = 2 IPs."""

    def test_same_ip_different_vpcs_counted_separately(self):
        """10.0.0.1 in VPC-A and 10.0.0.1 in VPC-B = 2 active IPs."""
        counter = ResourceCounter("aws")
        resources = [
            _make_resource("ec2-instance", details={"private_ip": "10.0.0.1", "vpc_id": "vpc-aaa"}),
            _make_resource("ec2-instance", details={"private_ip": "10.0.0.1", "vpc_id": "vpc-bbb"}),
        ]
        result = counter.count_resources(resources)
        assert result.active_ips == 2

    def test_same_ip_same_vpc_deduped(self):
        """10.0.0.1 appearing twice in the same VPC = 1 active IP."""
        counter = ResourceCounter("aws")
        resources = [
            _make_resource("ec2-instance", details={"private_ip": "10.0.0.1", "vpc_id": "vpc-aaa"}),
            _make_resource("ec2-instance", details={"private_ip": "10.0.0.1", "vpc_id": "vpc-aaa"}),
        ]
        result = counter.count_resources(resources)
        assert result.active_ips == 1

    def test_public_ips_in_same_space(self):
        """Public IPs share a single 'public' space — deduped globally."""
        counter = ResourceCounter("aws")
        resources = [
            _make_resource("elastic-ip", details={"public_ip": "54.1.2.3"}),
            _make_resource("ec2-instance", details={"public_ip": "54.1.2.3", "vpc_id": "vpc-aaa"}),
        ]
        result = counter.count_resources(resources)
        assert result.active_ips == 1

    def test_private_and_public_on_same_instance(self):
        """Instance with both private and public IP = 2 active IPs (different spaces)."""
        counter = ResourceCounter("aws")
        resources = [
            _make_resource(
                "ec2-instance",
                details={"private_ip": "10.0.0.1", "public_ip": "54.1.2.3", "vpc_id": "vpc-aaa"},
            ),
        ]
        result = counter.count_resources(resources)
        assert result.active_ips == 2

    def test_azure_ip_dedup_by_vnet(self):
        """Azure deduplication uses VNet ID as IP space."""
        counter = ResourceCounter("azure")
        resources = [
            _make_resource(
                "vm",
                region="eastus",
                details={
                    "private_ip": "10.0.0.1",
                    "vnet_id": "/subscriptions/sub1/providers/Microsoft.Network/virtualNetworks/vnet-a",
                },
            ),
            _make_resource(
                "vm",
                region="eastus",
                details={
                    "private_ip": "10.0.0.1",
                    "vnet_id": "/subscriptions/sub1/providers/Microsoft.Network/virtualNetworks/vnet-b",
                },
            ),
        ]
        result = counter.count_resources(resources)
        assert result.active_ips == 2

    def test_gcp_ip_dedup_by_network(self):
        """GCP deduplication uses VPC network as IP space."""
        counter = ResourceCounter("gcp")
        resources = [
            _make_resource(
                "compute-instance",
                region="us-central1",
                details={"private_ip": "10.0.0.1", "network": "projects/p1/global/networks/net-a"},
            ),
            _make_resource(
                "compute-instance",
                region="us-central1",
                details={"private_ip": "10.0.0.1", "network": "projects/p1/global/networks/net-b"},
            ),
        ]
        result = counter.count_resources(resources)
        assert result.active_ips == 2


# ---------------------------------------------------------------------------
# IP Canonicalization
# ---------------------------------------------------------------------------
class TestIPCanonicalization:
    def test_valid_ipv4(self):
        counter = ResourceCounter("aws")
        assert counter._canonicalize_ip("10.0.0.1") == "10.0.0.1"

    def test_valid_ipv6(self):
        counter = ResourceCounter("aws")
        assert counter._canonicalize_ip("::1") == "::1"

    def test_invalid_ip_returns_none(self):
        counter = ResourceCounter("aws")
        assert counter._canonicalize_ip("not-an-ip") is None

    def test_empty_string_returns_none(self):
        counter = ResourceCounter("aws")
        assert counter._canonicalize_ip("") is None

    def test_whitespace_stripped(self):
        counter = ResourceCounter("aws")
        assert counter._canonicalize_ip("  10.0.0.1  ") == "10.0.0.1"


# ---------------------------------------------------------------------------
# Subnet Reservation IPs
# ---------------------------------------------------------------------------
class TestSubnetReservationIPs:
    def test_aws_subnet_reserves_5_ips(self):
        """AWS reserves first 4 + last IP in a /24."""
        counter = ResourceCounter("aws")
        resources = [_make_resource("subnet", details={"cidr_block": "10.0.0.0/24"})]
        result = counter.count_resources(resources)
        # First 4 (10.0.0.0, .1, .2, .3) + last (10.0.0.255) = 5
        assert result.active_ips == 5

    def test_gcp_subnet_reserves_4_ips(self):
        """GCP reserves first 2 + last 2 in a /24."""
        counter = ResourceCounter("gcp")
        resources = [_make_resource("subnet", region="us-central1", details={"ip_cidr_range": "10.0.0.0/24"})]
        result = counter.count_resources(resources)
        # First 2 (10.0.0.0, .1) + last 2 (10.0.0.254, .255) = 4
        assert result.active_ips == 4

    def test_azure_subnet_reserves_5_ips(self):
        """Azure reserves first 4 + last IP in a /24."""
        counter = ResourceCounter("azure")
        resources = [_make_resource("subnet", region="eastus", details={"address_prefix": "10.0.0.0/24"})]
        result = counter.count_resources(resources)
        assert result.active_ips == 5


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_empty_input(self):
        counter = ResourceCounter("aws")
        result = counter.count_resources([])
        assert result.total_objects == 0
        assert result.ddi_objects == 0
        assert result.active_ips == 0

    def test_unsupported_provider_raises(self):
        with pytest.raises(ValueError, match="Unsupported provider"):
            ResourceCounter("oracle")

    def test_resource_with_no_details(self):
        counter = ResourceCounter("aws")
        resources = [_make_resource("ec2-instance", details={})]
        result = counter.count_resources(resources)
        assert result.active_ips == 0

    def test_resource_with_list_of_ips(self):
        counter = ResourceCounter("aws")
        resources = [
            _make_resource(
                "ec2-instance",
                details={"private_ips": ["10.0.0.1", "10.0.0.2"], "vpc_id": "vpc-aaa"},
            ),
        ]
        result = counter.count_resources(resources)
        assert result.active_ips == 2

    def test_result_is_dataclass(self):
        counter = ResourceCounter("aws")
        result = counter.count_resources([])
        assert isinstance(result, ResourceCount)

    def test_result_converts_to_dict(self):
        """GCP discover.py wraps count_resources with dataclasses.asdict()."""
        from dataclasses import asdict

        counter = ResourceCounter("gcp")
        result = counter.count_resources([])
        d = asdict(result)
        assert isinstance(d, dict)
        assert "ddi_objects" in d
        assert "active_ips" in d
        # Verify .get() works (the bug we fixed)
        assert d.get("ddi_objects") == 0
