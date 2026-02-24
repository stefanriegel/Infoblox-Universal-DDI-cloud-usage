"""
Tests for per-VPC IP de-duplication.

Validates that IP addresses are de-duplicated per VPC IP space and
per-account breakdowns are correct.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.schema.resource import CloudResource
from cloud_usage.counting.ip_counter import deduplicate_ips_per_vpc


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


class TestDeduplicateIpsPerVpc:
    """Test per-VPC IP de-duplication."""

    def test_same_ip_same_vpc_deduped(self):
        """Same IP in same VPC counted only once."""
        r1 = _make_resource(
            ip_addresses=["10.0.1.5"],
            details={"vpc_id": "vpc-aaa"},
        )
        r2 = _make_resource(
            ip_addresses=["10.0.1.5"],
            details={"vpc_id": "vpc-aaa"},
        )
        result = deduplicate_ips_per_vpc([r1, r2])
        assert result["total_unique_ips"] == 1

    def test_same_ip_different_vpcs_both_counted(self):
        """Same IP (10.0.0.1) in different VPCs counts separately."""
        r1 = _make_resource(
            ip_addresses=["10.0.0.1"],
            details={"vpc_id": "vpc-aaa"},
        )
        r2 = _make_resource(
            ip_addresses=["10.0.0.1"],
            details={"vpc_id": "vpc-bbb"},
        )
        result = deduplicate_ips_per_vpc([r1, r2])
        assert result["total_unique_ips"] == 2

    def test_no_vpc_id_uses_account_id(self):
        """Resources without vpc_id use account_id as IP space key."""
        r1 = _make_resource(
            ip_addresses=["54.23.100.50"],
            account_id="111111111111",
        )
        r2 = _make_resource(
            ip_addresses=["54.23.100.50"],
            account_id="111111111111",
        )
        result = deduplicate_ips_per_vpc([r1, r2])
        assert result["total_unique_ips"] == 1

    def test_no_vpc_different_accounts(self):
        """Same IP in different accounts (no VPC) counts separately."""
        r1 = _make_resource(
            ip_addresses=["54.23.100.50"],
            account_id="111111111111",
        )
        r2 = _make_resource(
            ip_addresses=["54.23.100.50"],
            account_id="222222222222",
        )
        result = deduplicate_ips_per_vpc([r1, r2])
        assert result["total_unique_ips"] == 2

    def test_per_account_breakdown(self):
        """Result includes per_account IP counts."""
        r1 = _make_resource(
            ip_addresses=["10.0.1.5", "10.0.1.6"],
            details={"vpc_id": "vpc-aaa"},
            account_id="111111111111",
        )
        r2 = _make_resource(
            ip_addresses=["10.0.2.5"],
            details={"vpc_id": "vpc-bbb"},
            account_id="222222222222",
        )
        result = deduplicate_ips_per_vpc([r1, r2])
        assert result["total_unique_ips"] == 3
        assert result["per_account"]["111111111111"] == 2
        assert result["per_account"]["222222222222"] == 1

    def test_empty_list_returns_zero(self):
        result = deduplicate_ips_per_vpc([])
        assert result["total_unique_ips"] == 0
        assert result["per_account"] == {}

    def test_uncounted_resources_excluded(self):
        """Resources with counted=False are excluded from dedup."""
        r = _make_resource(
            ip_addresses=["10.0.1.5"],
            details={"vpc_id": "vpc-aaa"},
            counted=False,
        )
        result = deduplicate_ips_per_vpc([r])
        assert result["total_unique_ips"] == 0

    def test_ipv6_deduplicated(self):
        """IPv6 addresses are deduplicated per VPC just like IPv4."""
        r1 = _make_resource(
            ip_addresses=["2001:db8::1"],
            details={"vpc_id": "vpc-aaa"},
        )
        r2 = _make_resource(
            ip_addresses=["2001:db8::1"],
            details={"vpc_id": "vpc-aaa"},
        )
        result = deduplicate_ips_per_vpc([r1, r2])
        assert result["total_unique_ips"] == 1
