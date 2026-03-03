"""
Tests for NIC-based IP counting (Phase 25 methodology).

Validates that count_nics_per_account() correctly counts IP addresses by
counting NIC/interface objects rather than unique IP strings. DDI resources
contribute 0 regardless of ip_addresses. Uncounted resources are skipped.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.schema.resource import CloudResource
from cloud_usage.counting.ip_counter import count_nics_per_account


def _make_resource(
    resource_type: str = "ec2-instance",
    ip_addresses: list[str] | None = None,
    details: dict | None = None,
    account_id: str = "111111111111",
    region: str = "us-east-1",
    counted: bool = True,
    category: str = "asset",
) -> CloudResource:
    """Helper to create a CloudResource for IP counting tests."""
    return CloudResource(
        resource_id=f"arn:aws:{resource_type}:{region}:{account_id}:test-{id(ip_addresses)}",
        resource_type=resource_type,
        provider="aws",
        account_id=account_id,
        region=region,
        name=f"test-{resource_type}",
        ip_addresses=ip_addresses or [],
        details=details or {},
        discovered_at="2026-02-23T10:00:00",
        counted=counted,
        category=category,
    )


def _make_ddi_resource(
    resource_type: str = "vpc",
    ip_addresses: list[str] | None = None,
    details: dict | None = None,
    account_id: str = "111111111111",
    region: str = "us-east-1",
) -> CloudResource:
    """Helper to create a DDI-category CloudResource."""
    return CloudResource(
        resource_id=f"arn:aws:{resource_type}:{region}:{account_id}:test-{id(ip_addresses)}",
        resource_type=resource_type,
        provider="aws",
        account_id=account_id,
        region=region,
        name=f"test-{resource_type}",
        ip_addresses=ip_addresses or [],
        details=details or {},
        discovered_at="2026-02-23T10:00:00",
        counted=True,
        category="ddi",
    )


class TestCountNicsPerAccountAWS:
    """EC2 NIC-based counting, fallback case, per_account breakdown."""

    def test_ec2_with_nic_ip_count_contributes_nic_count(self):
        """EC2 instance with nic_ip_count=3 contributes 3 (not ip_addresses length)."""
        r = _make_resource(
            resource_type="ec2-instance",
            ip_addresses=["10.0.1.5"],  # only 1 IP but nic_ip_count says 3
            details={"nic_ip_count": 3},
        )
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 3

    def test_ec2_with_no_nic_ip_count_contributes_zero(self):
        """EC2 instance with no nic_ip_count key contributes 0 (safe .get default)."""
        r = _make_resource(
            resource_type="ec2-instance",
            ip_addresses=["10.0.1.5", "10.0.1.6"],
            details={},  # no nic_ip_count key
        )
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 0

    def test_ec2_fallback_private_only_contributes_1(self):
        """EC2 with no NetworkInterfaces + only PrivateIpAddress -> nic_ip_count=1."""
        r = _make_resource(
            resource_type="ec2-instance",
            ip_addresses=["10.0.1.5"],
            details={"nic_ip_count": 1},
        )
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 1

    def test_ec2_fallback_private_and_public_contributes_2(self):
        """EC2 with no NetworkInterfaces + PrivateIpAddress + PublicIpAddress -> nic_ip_count=2."""
        r = _make_resource(
            resource_type="ec2-instance",
            ip_addresses=["10.0.1.5", "54.23.100.50"],
            details={"nic_ip_count": 2},
        )
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 2

    def test_per_account_breakdown_aws(self):
        """Multi-account results are keyed by account_id."""
        r1 = _make_resource(
            resource_type="ec2-instance",
            account_id="111111111111",
            details={"nic_ip_count": 3},
        )
        r2 = _make_resource(
            resource_type="ec2-instance",
            account_id="222222222222",
            details={"nic_ip_count": 2},
        )
        result = count_nics_per_account([r1, r2])
        assert result["total_unique_ips"] == 5
        assert result["per_account"]["111111111111"] == 3
        assert result["per_account"]["222222222222"] == 2


class TestCountNicsPerAccountAzure:
    """Azure VM-attached vs unattached NIC counting, per_account."""

    def test_azure_nic_attached_to_vm_contributes_ip_config_count(self):
        """Azure NIC with vm_id set contributes ip_configuration_count=2."""
        r = _make_resource(
            resource_type="azure-nic",
            ip_addresses=["10.0.1.5", "10.0.1.6"],
            details={"vm_id": "vm-abc", "ip_configuration_count": 2},
            account_id="00000000-0000-0000-0000-000000000001",
            region="eastus",
        )
        r.provider = "azure"
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 2

    def test_azure_nic_unattached_contributes_zero(self):
        """Azure NIC with vm_id=None (unattached) contributes 0 despite ip_configuration_count=3."""
        r = _make_resource(
            resource_type="azure-nic",
            ip_addresses=["10.0.1.5", "10.0.1.6", "10.0.1.7"],
            details={"vm_id": None, "ip_configuration_count": 3},
            account_id="00000000-0000-0000-0000-000000000001",
            region="eastus",
        )
        r.provider = "azure"
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 0

    def test_azure_nic_per_account_breakdown(self):
        """Azure multi-subscription results keyed by account_id."""
        r1 = _make_resource(
            resource_type="azure-nic",
            details={"vm_id": "vm-1", "ip_configuration_count": 2},
            account_id="sub-aaa",
            region="eastus",
        )
        r1.provider = "azure"
        r2 = _make_resource(
            resource_type="azure-nic",
            details={"vm_id": "vm-2", "ip_configuration_count": 1},
            account_id="sub-bbb",
            region="westus",
        )
        r2.provider = "azure"
        result = count_nics_per_account([r1, r2])
        assert result["total_unique_ips"] == 3
        assert result["per_account"]["sub-aaa"] == 2
        assert result["per_account"]["sub-bbb"] == 1


class TestCountNicsPerAccountGCP:
    """GCP VM network_interface_count counting."""

    def test_gcp_vm_contributes_network_interface_count(self):
        """GCP VM with network_interface_count=3 contributes 3 (not len(ip_addresses))."""
        r = _make_resource(
            resource_type="gcp-vm",
            ip_addresses=["10.0.0.1"],  # only 1 IP but 3 interfaces
            details={"network_interface_count": 3},
            account_id="my-gcp-project",
            region="us-central1",
        )
        r.provider = "gcp"
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 3

    def test_gcp_vm_with_one_interface_contributes_1(self):
        """GCP VM with network_interface_count=1 contributes 1."""
        r = _make_resource(
            resource_type="gcp-vm",
            ip_addresses=["10.0.0.1"],
            details={"network_interface_count": 1},
            account_id="my-gcp-project",
            region="us-central1",
        )
        r.provider = "gcp"
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 1

    def test_gcp_vm_per_account_breakdown(self):
        """GCP multi-project results keyed by account_id (project)."""
        r1 = _make_resource(
            resource_type="gcp-vm",
            details={"network_interface_count": 2},
            account_id="project-alpha",
            region="us-central1",
        )
        r1.provider = "gcp"
        r2 = _make_resource(
            resource_type="gcp-vm",
            details={"network_interface_count": 4},
            account_id="project-beta",
            region="europe-west1",
        )
        r2.provider = "gcp"
        result = count_nics_per_account([r1, r2])
        assert result["total_unique_ips"] == 6
        assert result["per_account"]["project-alpha"] == 2
        assert result["per_account"]["project-beta"] == 4


class TestCountNicsPerAccountDDIExclusion:
    """DDI resources (eni, elastic-ip, nat-gateway, etc.) contribute 0 to IP count."""

    def test_ddi_resource_contributes_zero(self):
        """DDI resource with ip_addresses set contributes 0 to total."""
        r = _make_ddi_resource(
            resource_type="vpc",
            ip_addresses=["10.0.0.0"],
        )
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 0

    def test_eni_reclassified_as_ddi_contributes_zero(self):
        """ENI resource after reclassification (category=ddi) contributes 0."""
        r = _make_ddi_resource(
            resource_type="eni",
            ip_addresses=["10.0.1.5"],
        )
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 0

    def test_elastic_ip_as_ddi_contributes_zero(self):
        """EIP resource (category=ddi) contributes 0 to IP count."""
        r = _make_ddi_resource(
            resource_type="elastic-ip",
            ip_addresses=["54.23.100.50"],
        )
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 0

    def test_nat_gateway_as_ddi_contributes_zero(self):
        """NAT GW resource (category=ddi) contributes 0 to IP count."""
        r = _make_ddi_resource(
            resource_type="nat-gateway",
            ip_addresses=["10.0.0.1", "52.20.30.40"],
        )
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 0

    def test_azure_nic_as_ddi_contributes_zero(self):
        """azure-nic reclassified as DDI contributes 0 when category=ddi."""
        r = _make_ddi_resource(
            resource_type="azure-nic",
            ip_addresses=["10.0.1.5"],
        )
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 0

    def test_azure_public_ip_as_ddi_contributes_zero(self):
        """azure-public-ip reclassified as DDI contributes 0 when category=ddi."""
        r = _make_ddi_resource(
            resource_type="azure-public-ip",
            ip_addresses=["52.168.1.1"],
        )
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 0

    def test_ddi_does_not_appear_in_per_account(self):
        """DDI resources do not appear in per_account breakdown (contribute 0)."""
        ddi = _make_ddi_resource(resource_type="vpc", ip_addresses=["10.0.0.0"])
        asset = _make_resource(
            resource_type="ec2-instance",
            details={"nic_ip_count": 2},
            account_id="111111111111",
        )
        result = count_nics_per_account([ddi, asset])
        assert result["total_unique_ips"] == 2
        assert result["per_account"].get("111111111111") == 2


class TestCountNicsPerAccountFallback:
    """Non-VM assets fall back to len(ip_addresses) when no NIC count details."""

    def test_rds_falls_back_to_ip_addresses_count(self):
        """rds-instance with 2 IPs contributes 2 via fallback."""
        r = _make_resource(
            resource_type="rds-instance",
            ip_addresses=["10.0.2.10", "10.0.2.11"],
            details={},  # no nic_ip_count, no ip_configuration_count
        )
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 2

    def test_ecs_task_falls_back_to_ip_addresses_count(self):
        """ecs-task with 1 IP contributes 1 via fallback."""
        r = _make_resource(
            resource_type="ecs-task",
            ip_addresses=["10.0.3.5"],
            details={},
        )
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 1

    def test_uncounted_resource_is_skipped(self):
        """Resource with counted=False is excluded from count."""
        r = _make_resource(
            resource_type="ec2-instance",
            ip_addresses=["10.0.1.5"],
            details={"nic_ip_count": 3},
            counted=False,
        )
        result = count_nics_per_account([r])
        assert result["total_unique_ips"] == 0


class TestCountNicsPerAccountReturnShape:
    """Return dict shape matches deduplicate_ips_per_vpc for drop-in compatibility."""

    def test_empty_list_returns_correct_shape(self):
        """Empty list returns correct shape with zero values."""
        result = count_nics_per_account([])
        assert result["total_unique_ips"] == 0
        assert result["per_account"] == {}

    def test_return_dict_has_required_keys(self):
        """Return dict has exactly the keys 'total_unique_ips' and 'per_account'."""
        result = count_nics_per_account([])
        assert "total_unique_ips" in result
        assert "per_account" in result

    def test_per_account_is_dict(self):
        """per_account is always a dict."""
        r = _make_resource(
            resource_type="ec2-instance",
            details={"nic_ip_count": 1},
            account_id="111111111111",
        )
        result = count_nics_per_account([r])
        assert isinstance(result["per_account"], dict)

    def test_total_unique_ips_is_int(self):
        """total_unique_ips is always an integer."""
        result = count_nics_per_account([])
        assert isinstance(result["total_unique_ips"], int)

    def test_multi_account_per_account_keys_are_account_ids(self):
        """per_account keys are account_id strings."""
        r1 = _make_resource(
            resource_type="ec2-instance",
            details={"nic_ip_count": 2},
            account_id="111111111111",
        )
        r2 = _make_resource(
            resource_type="ec2-instance",
            details={"nic_ip_count": 1},
            account_id="222222222222",
        )
        result = count_nics_per_account([r1, r2])
        assert "111111111111" in result["per_account"]
        assert "222222222222" in result["per_account"]
        assert result["per_account"]["111111111111"] == 2
        assert result["per_account"]["222222222222"] == 1
