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
