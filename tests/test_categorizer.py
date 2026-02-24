"""
Tests for the resource categorizer.

Validates that CloudResource instances are correctly categorized as DDI,
IP, Asset, or excluded (with skip reason) based on resource type and state.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.schema.resource import CloudResource
from cloud_usage.counting.categorizer import categorize_resources


def _make_resource(
    resource_type: str = "ec2-instance",
    ip_addresses: list[str] | None = None,
    details: dict | None = None,
    tags: dict | None = None,
    account_id: str = "111111111111",
    region: str = "us-east-1",
) -> CloudResource:
    """Helper to create a CloudResource with sensible defaults."""
    return CloudResource(
        resource_id=f"arn:aws:{resource_type}:{region}:{account_id}:test",
        resource_type=resource_type,
        provider="aws",
        account_id=account_id,
        region=region,
        name=f"test-{resource_type}",
        ip_addresses=ip_addresses or [],
        details=details or {},
        tags=tags or {},
        discovered_at="2026-02-23T10:00:00",
    )


class TestCategorizeDDIResources:
    """DDI resource types are categorized as category='ddi', counted=True."""

    def test_vpc_is_ddi(self):
        resources = categorize_resources([_make_resource("vpc")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"
        assert resources[0].skip_reason is None

    def test_subnet_is_ddi(self):
        resources = categorize_resources([_make_resource("subnet")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"

    def test_route53_zone_is_ddi(self):
        resources = categorize_resources([_make_resource("route53-zone")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"

    def test_route53_record_is_ddi(self):
        resources = categorize_resources([_make_resource("route53-record")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"

    def test_dhcp_option_set_is_ddi(self):
        """Non-orphaned DHCP option set is DDI."""
        resources = categorize_resources([_make_resource("dhcp-option-set")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"


class TestCategorizeTokenFreeResources:
    """Token-free resources are excluded with specific skip reasons."""

    def test_ebs_volume_is_token_free(self):
        resources = categorize_resources([_make_resource("ebs-volume")])
        assert resources[0].counted is False
        assert resources[0].category is None
        assert resources[0].skip_reason == "token-free: EBS Volume"

    def test_s3_bucket_is_token_free(self):
        resources = categorize_resources([_make_resource("s3-bucket")])
        assert resources[0].counted is False
        assert resources[0].category is None
        assert resources[0].skip_reason == "token-free: S3 Bucket"


class TestCategorizeOrphanedDHCP:
    """Orphaned DHCP option sets are excluded."""

    def test_orphaned_dhcp_not_counted(self):
        r = _make_resource("dhcp-option-set", details={"orphaned": True})
        resources = categorize_resources([r])
        assert resources[0].counted is False
        assert "orphaned" in resources[0].skip_reason.lower()


class TestCategorizeAssetResources:
    """Resources with IPs that are not DDI are categorized as assets."""

    def test_ec2_with_ips_is_asset(self):
        r = _make_resource("ec2-instance", ip_addresses=["10.0.1.5", "54.23.100.50"])
        resources = categorize_resources([r])
        assert resources[0].counted is True
        assert resources[0].category == "asset"

    def test_rds_with_ips_is_asset(self):
        r = _make_resource("rds-instance", ip_addresses=["10.0.2.10"])
        resources = categorize_resources([r])
        assert resources[0].counted is True
        assert resources[0].category == "asset"

    def test_elb_with_ips_is_asset(self):
        r = _make_resource("alb", ip_addresses=["10.0.3.1"])
        resources = categorize_resources([r])
        assert resources[0].counted is True
        assert resources[0].category == "asset"


class TestCategorizeNoIPs:
    """Resources with no IPs and not DDI/special-case are excluded."""

    def test_no_ips_not_ddi_excluded(self):
        r = _make_resource("ec2-instance", ip_addresses=[])
        resources = categorize_resources([r])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "no IP addresses"

    def test_lambda_without_vpc_excluded(self):
        """Non-VPC Lambda is excluded."""
        r = _make_resource("lambda-function", ip_addresses=[])
        resources = categorize_resources([r])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "no IP addresses"


class TestCategorizeLambdaSpecialCase:
    """VPC-attached Lambda is counted as asset even without ip_addresses."""

    def test_lambda_with_vpc_is_asset(self):
        r = _make_resource(
            "lambda-function",
            ip_addresses=[],
            details={"vpc_id": "vpc-12345"},
        )
        resources = categorize_resources([r])
        assert resources[0].counted is True
        assert resources[0].category == "asset"

    def test_lambda_with_empty_vpc_id_excluded(self):
        """Lambda with empty vpc_id is not VPC-attached."""
        r = _make_resource(
            "lambda-function",
            ip_addresses=[],
            details={"vpc_id": ""},
        )
        resources = categorize_resources([r])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "no IP addresses"


class TestCategorizeMixedBatch:
    """Categorizing a batch of mixed resources."""

    def test_mixed_batch_categorization(self):
        resources = [
            _make_resource("vpc"),
            _make_resource("ec2-instance", ip_addresses=["10.0.1.5"]),
            _make_resource("ebs-volume"),
            _make_resource("subnet"),
            _make_resource("ec2-instance", ip_addresses=[]),
        ]
        result = categorize_resources(resources)

        assert result[0].category == "ddi"  # VPC
        assert result[1].category == "asset"  # EC2 with IP
        assert result[2].skip_reason == "token-free: EBS Volume"  # EBS
        assert result[3].category == "ddi"  # Subnet
        assert result[4].counted is False  # EC2 no IPs

    def test_empty_list_returns_empty(self):
        assert categorize_resources([]) == []


class TestCategorizePreservesExistingFields:
    """Categorization preserves all existing resource fields."""

    def test_fields_preserved(self):
        r = _make_resource(
            "ec2-instance",
            ip_addresses=["10.0.1.5"],
            tags={"env": "prod"},
            details={"instance_type": "t3.medium"},
        )
        result = categorize_resources([r])[0]
        assert result.resource_type == "ec2-instance"
        assert result.tags == {"env": "prod"}
        assert result.details["instance_type"] == "t3.medium"
        assert result.ip_addresses == ["10.0.1.5"]


# --- Azure DDI type tests ---


def _make_azure_resource(
    resource_type: str = "azure-vnet",
    ip_addresses: list[str] | None = None,
    details: dict | None = None,
    account_id: str = "00000000-0000-0000-0000-000000000001",
    region: str = "eastus",
) -> CloudResource:
    """Helper to create an Azure CloudResource with sensible defaults."""
    return CloudResource(
        resource_id=f"/subscriptions/{account_id}/resourceGroups/rg/{resource_type}/test",
        resource_type=resource_type,
        provider="azure",
        account_id=account_id,
        region=region,
        name=f"test-{resource_type}",
        ip_addresses=ip_addresses or [],
        details=details or {},
        tags={},
        discovered_at="2026-02-24T10:00:00",
    )


class TestCategorizeAzureDDIResources:
    """Azure DDI resource types are categorized as category='ddi', counted=True."""

    def test_azure_vnet_is_ddi(self):
        resources = categorize_resources([_make_azure_resource("azure-vnet")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"
        assert resources[0].skip_reason is None

    def test_azure_subnet_is_ddi(self):
        resources = categorize_resources([_make_azure_resource("azure-subnet")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"

    def test_azure_dns_zone_is_ddi(self):
        resources = categorize_resources([_make_azure_resource("azure-dns-zone")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"

    def test_azure_private_dns_zone_is_ddi(self):
        resources = categorize_resources([_make_azure_resource("azure-private-dns-zone")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"

    def test_azure_dns_record_is_ddi(self):
        resources = categorize_resources([_make_azure_resource("azure-dns-record")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"

    def test_azure_private_dns_record_is_ddi(self):
        resources = categorize_resources([_make_azure_resource("azure-private-dns-record")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"

    def test_azure_dhcp_config_is_ddi(self):
        resources = categorize_resources([_make_azure_resource("azure-dhcp-config")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"


class TestCategorizeAzureTokenFreeResources:
    """Azure token-free resources are excluded with specific skip reasons."""

    def test_azure_disk_is_token_free(self):
        resources = categorize_resources([_make_azure_resource("azure-disk")])
        assert resources[0].counted is False
        assert resources[0].category is None
        assert resources[0].skip_reason == "token-free: Azure VM Disk"

    def test_azure_nsg_is_token_free(self):
        resources = categorize_resources([_make_azure_resource("azure-nsg")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: Azure Network Security Group"

    def test_azure_storage_account_is_token_free(self):
        resources = categorize_resources([_make_azure_resource("azure-storage-account")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: Azure Storage Account"

    def test_azure_storage_container_is_token_free(self):
        resources = categorize_resources([_make_azure_resource("azure-storage-container")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: Azure Storage Container"

    def test_azure_management_group_is_token_free(self):
        resources = categorize_resources([_make_azure_resource("azure-management-group")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: Azure Management Group"

    def test_azure_resource_group_is_token_free(self):
        resources = categorize_resources([_make_azure_resource("azure-resource-group")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: Azure Resource Group"

    def test_azure_traffic_manager_is_token_free(self):
        resources = categorize_resources([_make_azure_resource("azure-traffic-manager")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: Azure Traffic Manager Profile"

    def test_azure_network_watcher_is_token_free(self):
        resources = categorize_resources([_make_azure_resource("azure-network-watcher")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: Azure Network Watcher"

    def test_azure_flow_log_is_token_free(self):
        resources = categorize_resources([_make_azure_resource("azure-flow-log")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: Azure Network Watcher Flow Log"

    def test_azure_monitoring_stats_is_token_free(self):
        resources = categorize_resources([_make_azure_resource("azure-monitoring-stats")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: Azure VM Monitoring Stats"

    def test_azure_subscription_tenant_is_token_free(self):
        resources = categorize_resources([_make_azure_resource("azure-subscription-tenant")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: Azure Subscription Tenant"


class TestCategorizeAzureAssetResources:
    """Azure resources with IPs are categorized as managed assets."""

    def test_azure_nic_with_ips_is_asset(self):
        r = _make_azure_resource("azure-nic", ip_addresses=["10.0.1.5"])
        resources = categorize_resources([r])
        assert resources[0].counted is True
        assert resources[0].category == "asset"

    def test_azure_public_ip_with_ips_is_asset(self):
        r = _make_azure_resource("azure-public-ip", ip_addresses=["52.168.1.1"])
        resources = categorize_resources([r])
        assert resources[0].counted is True
        assert resources[0].category == "asset"


class TestCategorizeAzureMixedBatch:
    """Categorizing a batch of mixed Azure and AWS resources."""

    def test_mixed_azure_aws_batch(self):
        resources = [
            _make_resource("vpc"),  # AWS DDI
            _make_azure_resource("azure-vnet"),  # Azure DDI
            _make_resource("ebs-volume"),  # AWS token-free
            _make_azure_resource("azure-disk"),  # Azure token-free
            _make_azure_resource("azure-nic", ip_addresses=["10.0.1.5"]),  # Azure asset
        ]
        result = categorize_resources(resources)

        assert result[0].category == "ddi"  # VPC
        assert result[1].category == "ddi"  # azure-vnet
        assert result[2].skip_reason == "token-free: EBS Volume"  # EBS
        assert result[3].skip_reason == "token-free: Azure VM Disk"  # azure-disk
        assert result[4].category == "asset"  # azure-nic with IP


# --- GCP type tests ---


def _make_gcp_resource(
    resource_type: str = "gcp-vpc",
    ip_addresses: list[str] | None = None,
    details: dict | None = None,
    account_id: str = "my-gcp-project",
    region: str = "us-central1",
) -> CloudResource:
    """Helper to create a GCP CloudResource with sensible defaults."""
    return CloudResource(
        resource_id=f"projects/{account_id}/{resource_type}/test",
        resource_type=resource_type,
        provider="gcp",
        account_id=account_id,
        region=region,
        name=f"test-{resource_type}",
        ip_addresses=ip_addresses or [],
        details=details or {},
        tags={},
        discovered_at="2026-02-24T19:00:00",
    )


class TestCategorizeGcpDDIResources:
    """GCP DDI resource types are categorized as category='ddi', counted=True."""

    def test_gcp_vpc_is_ddi(self):
        resources = categorize_resources([_make_gcp_resource("gcp-vpc")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"
        assert resources[0].skip_reason is None

    def test_gcp_subnet_is_ddi(self):
        resources = categorize_resources([_make_gcp_resource("gcp-subnet")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"

    def test_gcp_dns_zone_is_ddi(self):
        resources = categorize_resources([_make_gcp_resource("gcp-dns-zone")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"

    def test_gcp_dns_record_is_ddi(self):
        resources = categorize_resources([_make_gcp_resource("gcp-dns-record")])
        assert resources[0].counted is True
        assert resources[0].category == "ddi"


class TestCategorizeGcpTokenFreeResources:
    """GCP token-free resources are excluded with specific skip reasons."""

    def test_gcp_disk_is_token_free(self):
        resources = categorize_resources([_make_gcp_resource("gcp-disk")])
        assert resources[0].counted is False
        assert resources[0].category is None
        assert resources[0].skip_reason == "token-free: GCP Compute Persistent Disk"

    def test_gcp_instance_group_is_token_free(self):
        resources = categorize_resources([_make_gcp_resource("gcp-instance-group")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: GCP Instance Group"

    def test_gcp_gke_cluster_is_token_free(self):
        resources = categorize_resources([_make_gcp_resource("gcp-gke-cluster")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: GCP GKE Cluster (metadata only)"

    def test_gcp_url_map_is_token_free(self):
        resources = categorize_resources([_make_gcp_resource("gcp-url-map")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: GCP URL Map"

    def test_gcp_storage_bucket_is_token_free(self):
        resources = categorize_resources([_make_gcp_resource("gcp-storage-bucket")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: GCP Cloud Storage Bucket"

    def test_gcp_monitoring_stats_is_token_free(self):
        resources = categorize_resources([_make_gcp_resource("gcp-monitoring-stats")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: GCP Cloud Monitoring Metric Stats"

    def test_gcp_connectivity_location_is_token_free(self):
        resources = categorize_resources([_make_gcp_resource("gcp-connectivity-location")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: GCP Network Connectivity Location"

    def test_gcp_storage_bucket_policy_is_token_free(self):
        resources = categorize_resources([_make_gcp_resource("gcp-storage-bucket-policy")])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "token-free: GCP Cloud Storage Bucket Policy"


class TestCategorizeGcpAssetResources:
    """GCP resources with IPs are categorized as managed assets."""

    def test_gcp_vm_with_ips_is_asset(self):
        r = _make_gcp_resource("gcp-vm", ip_addresses=["10.0.1.5", "34.123.45.67"])
        resources = categorize_resources([r])
        assert resources[0].counted is True
        assert resources[0].category == "asset"

    def test_gcp_vm_without_ips_excluded(self):
        r = _make_gcp_resource("gcp-vm", ip_addresses=[])
        resources = categorize_resources([r])
        assert resources[0].counted is False
        assert resources[0].skip_reason == "no IP addresses"

    def test_gcp_forwarding_rule_with_ip_is_asset(self):
        r = _make_gcp_resource("gcp-forwarding-rule", ip_addresses=["34.120.0.1"])
        resources = categorize_resources([r])
        assert resources[0].counted is True
        assert resources[0].category == "asset"

    def test_gcp_cloud_sql_with_ips_is_asset(self):
        r = _make_gcp_resource("gcp-cloud-sql", ip_addresses=["10.0.2.1", "34.100.0.5"])
        resources = categorize_resources([r])
        assert resources[0].counted is True
        assert resources[0].category == "asset"

    def test_gcp_reserved_ip_with_ip_is_asset(self):
        r = _make_gcp_resource("gcp-reserved-ip", ip_addresses=["34.100.0.10"])
        resources = categorize_resources([r])
        assert resources[0].counted is True
        assert resources[0].category == "asset"


class TestCategorizeGcpMixedBatch:
    """Categorizing a batch of mixed GCP resources."""

    def test_mixed_gcp_batch(self):
        resources = [
            _make_gcp_resource("gcp-vpc"),  # DDI
            _make_gcp_resource("gcp-subnet"),  # DDI
            _make_gcp_resource("gcp-dns-zone"),  # DDI
            _make_gcp_resource("gcp-dns-record"),  # DDI
            _make_gcp_resource("gcp-vm", ip_addresses=["10.0.1.5"]),  # asset
            _make_gcp_resource("gcp-disk"),  # token-free
            _make_gcp_resource("gcp-gke-cluster"),  # token-free
            _make_gcp_resource("gcp-vm", ip_addresses=[]),  # no IPs
        ]
        result = categorize_resources(resources)

        assert result[0].category == "ddi"  # gcp-vpc
        assert result[1].category == "ddi"  # gcp-subnet
        assert result[2].category == "ddi"  # gcp-dns-zone
        assert result[3].category == "ddi"  # gcp-dns-record
        assert result[4].category == "asset"  # gcp-vm with IP
        assert "token-free" in result[5].skip_reason  # gcp-disk
        assert "token-free" in result[6].skip_reason  # gcp-gke-cluster
        assert result[7].counted is False  # gcp-vm no IPs
