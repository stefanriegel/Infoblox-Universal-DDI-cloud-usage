"""
Tests for token calculation with ceiling division.

Validates the formula: ceil(DDI/25) + ceil(IPs/13) + ceil(Assets/3)
with 0-count producing 0 tokens (not minimum 1).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.schema.resource import CloudResource
from cloud_usage.counting.token_calculator import (
    calculate_tokens,
    calculate_account_tokens,
    calculate_provider_tokens,
    DDI_PER_TOKEN,
    IPS_PER_TOKEN,
    ASSETS_PER_TOKEN,
)


def _make_resource(
    resource_type: str = "ec2-instance",
    ip_addresses: list[str] | None = None,
    counted: bool = True,
    category: str | None = "asset",
    account_id: str = "111111111111",
) -> CloudResource:
    """Helper to create a CloudResource for token calculation tests."""
    return CloudResource(
        resource_id=f"arn:aws:{resource_type}:us-east-1:{account_id}:{id(ip_addresses)}",
        resource_type=resource_type,
        provider="aws",
        account_id=account_id,
        region="us-east-1",
        name=f"test-{resource_type}",
        ip_addresses=ip_addresses or [],
        discovered_at="2026-02-23T10:00:00",
        counted=counted,
        category=category,
    )


class TestConstants:
    """Verify token ratio constants."""

    def test_ddi_per_token(self):
        assert DDI_PER_TOKEN == 25

    def test_ips_per_token(self):
        assert IPS_PER_TOKEN == 13

    def test_assets_per_token(self):
        assert ASSETS_PER_TOKEN == 3


class TestCalculateTokens:
    """Test the core ceiling division formula."""

    def test_all_zeros(self):
        """0 DDI, 0 IPs, 0 assets -> 0 total tokens."""
        result = calculate_tokens(0, 0, 0)
        assert result["ddi_tokens"] == 0
        assert result["ip_tokens"] == 0
        assert result["asset_tokens"] == 0
        assert result["total_tokens"] == 0

    def test_exact_ddi_boundary(self):
        """25 DDI -> 1 DDI token (exact boundary)."""
        result = calculate_tokens(25, 0, 0)
        assert result["ddi_tokens"] == 1
        assert result["total_tokens"] == 1

    def test_ddi_one_over_boundary(self):
        """26 DDI -> 2 DDI tokens (ceiling)."""
        result = calculate_tokens(26, 0, 0)
        assert result["ddi_tokens"] == 2

    def test_exact_ip_boundary(self):
        """13 IPs -> 1 IP token."""
        result = calculate_tokens(0, 13, 0)
        assert result["ip_tokens"] == 1
        assert result["total_tokens"] == 1

    def test_ip_one_over_boundary(self):
        """14 IPs -> 2 IP tokens."""
        result = calculate_tokens(0, 14, 0)
        assert result["ip_tokens"] == 2

    def test_exact_asset_boundary(self):
        """3 assets -> 1 asset token."""
        result = calculate_tokens(0, 0, 3)
        assert result["asset_tokens"] == 1
        assert result["total_tokens"] == 1

    def test_asset_one_over_boundary(self):
        """4 assets -> 2 asset tokens."""
        result = calculate_tokens(0, 0, 4)
        assert result["asset_tokens"] == 2

    def test_single_ddi(self):
        """1 DDI -> 1 DDI token (ceiling of 1/25)."""
        result = calculate_tokens(1, 0, 0)
        assert result["ddi_tokens"] == 1

    def test_single_ip(self):
        """1 IP -> 1 IP token."""
        result = calculate_tokens(0, 1, 0)
        assert result["ip_tokens"] == 1

    def test_single_asset(self):
        """1 asset -> 1 asset token."""
        result = calculate_tokens(0, 0, 1)
        assert result["asset_tokens"] == 1

    def test_large_mixed(self):
        """100 DDI + 200 IPs + 50 assets -> 4 + 16 + 17 = 37 tokens."""
        result = calculate_tokens(100, 200, 50)
        assert result["ddi_tokens"] == 4   # ceil(100/25)
        assert result["ip_tokens"] == 16   # ceil(200/13) = ceil(15.38) = 16
        assert result["asset_tokens"] == 17  # ceil(50/3) = ceil(16.67) = 17
        assert result["total_tokens"] == 37

    def test_returns_all_counts(self):
        """Result includes raw counts along with token values."""
        result = calculate_tokens(10, 20, 5)
        assert result["ddi_count"] == 10
        assert result["ip_count"] == 20
        assert result["asset_count"] == 5


class TestCalculateAccountTokens:
    """Test per-account token calculation from resource lists."""

    def test_empty_resource_list(self):
        result = calculate_account_tokens([])
        assert result["total_tokens"] == 0
        assert result["ddi_count"] == 0
        assert result["ip_count"] == 0
        assert result["asset_count"] == 0

    def test_mixed_resources(self):
        """Calculate tokens from a mix of DDI, asset, and excluded resources."""
        resources = [
            _make_resource("vpc", category="ddi", counted=True),
            _make_resource("subnet", category="ddi", counted=True),
            _make_resource(
                "ec2-instance",
                ip_addresses=["10.0.1.5", "54.23.100.50"],
                category="asset",
                counted=True,
            ),
            _make_resource(
                "ebs-volume", category=None, counted=False,
            ),
        ]
        result = calculate_account_tokens(resources)
        assert result["ddi_count"] == 2  # vpc + subnet
        assert result["asset_count"] == 1  # ec2
        # IPs are summed from ip_addresses when no deduplicated count provided
        assert result["ip_count"] == 2
        assert result["ddi_tokens"] == 1  # ceil(2/25)
        assert result["ip_tokens"] == 1   # ceil(2/13)
        assert result["asset_tokens"] == 1  # ceil(1/3)
        assert result["total_tokens"] == 3

    def test_with_deduplicated_ip_count(self):
        """When deduplicated_ip_count is provided, use it instead of summing IPs."""
        resources = [
            _make_resource(
                "ec2-instance",
                ip_addresses=["10.0.1.5", "10.0.1.5", "10.0.1.6"],
                category="asset",
                counted=True,
            ),
        ]
        # Deduplicated count says only 2 unique IPs (10.0.1.5 counted once)
        result = calculate_account_tokens(resources, deduplicated_ip_count=2)
        assert result["ip_count"] == 2
        assert result["ip_tokens"] == 1  # ceil(2/13)

    def test_uncounted_resources_excluded(self):
        """Resources with counted=False are not counted."""
        resources = [
            _make_resource("vpc", category="ddi", counted=False),
            _make_resource("ec2-instance", ip_addresses=["10.0.1.5"], counted=False),
        ]
        result = calculate_account_tokens(resources)
        assert result["ddi_count"] == 0
        assert result["ip_count"] == 0
        assert result["asset_count"] == 0
        assert result["total_tokens"] == 0


class TestCalculateProviderTokens:
    """Test provider-level token aggregation across accounts."""

    def test_empty_accounts(self):
        result = calculate_provider_tokens({})
        assert result["total_tokens"] == 0

    def test_single_account(self):
        account_results = {
            "111111111111": {
                "ddi_count": 10,
                "ip_count": 20,
                "asset_count": 5,
                "ddi_tokens": 1,
                "ip_tokens": 2,
                "asset_tokens": 2,
                "total_tokens": 5,
            }
        }
        result = calculate_provider_tokens(account_results)
        assert result["total_ddi_count"] == 10
        assert result["total_ip_count"] == 20
        assert result["total_asset_count"] == 5
        assert result["total_tokens"] == 5

    def test_multiple_accounts(self):
        """Provider tokens sum across accounts."""
        account_results = {
            "111111111111": {
                "ddi_count": 10,
                "ip_count": 20,
                "asset_count": 5,
                "ddi_tokens": 1,
                "ip_tokens": 2,
                "asset_tokens": 2,
                "total_tokens": 5,
            },
            "222222222222": {
                "ddi_count": 50,
                "ip_count": 100,
                "asset_count": 30,
                "ddi_tokens": 2,
                "ip_tokens": 8,
                "asset_tokens": 10,
                "total_tokens": 20,
            },
        }
        result = calculate_provider_tokens(account_results)
        assert result["total_ddi_count"] == 60
        assert result["total_ip_count"] == 120
        assert result["total_asset_count"] == 35
        assert result["total_tokens"] == 25  # 5 + 20
        assert result["account_count"] == 2
