"""
Tests for the unified CloudResource schema.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.schema.resource import CloudResource


class TestCloudResourceCreation:
    """Test creating CloudResource instances with all fields."""

    def test_create_with_all_fields(self):
        """CloudResource can be created with all fields explicitly set."""
        resource = CloudResource(
            resource_id="arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            resource_type="vm",
            provider="aws",
            account_id="123456789012",
            region="us-east-1",
            name="web-server-01",
            ip_addresses=["10.0.1.5", "54.23.100.50"],
            tags={"Environment": "production", "Team": "platform"},
            details={"InstanceType": "t3.medium", "State": "running"},
            discovered_at="2026-02-23T10:00:00",
            counted=True,
            category="asset",
            skip_reason=None,
        )
        assert resource.resource_id == "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0"
        assert resource.resource_type == "vm"
        assert resource.provider == "aws"
        assert resource.account_id == "123456789012"
        assert resource.region == "us-east-1"
        assert resource.name == "web-server-01"
        assert resource.ip_addresses == ["10.0.1.5", "54.23.100.50"]
        assert resource.tags == {"Environment": "production", "Team": "platform"}
        assert resource.details == {"InstanceType": "t3.medium", "State": "running"}
        assert resource.discovered_at == "2026-02-23T10:00:00"
        assert resource.counted is True
        assert resource.category == "asset"
        assert resource.skip_reason is None

    def test_create_azure_resource(self):
        """CloudResource can represent an Azure resource."""
        resource = CloudResource(
            resource_id="/subscriptions/abc-123/resourceGroups/rg-prod/providers/Microsoft.Network/virtualNetworks/vnet-main",
            resource_type="subnet",
            provider="azure",
            account_id="abc-123-def-456",
            region="eastus",
            name="subnet-web",
            ip_addresses=["10.1.0.0/24"],
            tags={"env": "prod"},
        )
        assert resource.provider == "azure"
        assert resource.account_id == "abc-123-def-456"

    def test_create_gcp_resource(self):
        """CloudResource can represent a GCP resource."""
        resource = CloudResource(
            resource_id="projects/my-project/zones/us-central1-a/instances/vm-1",
            resource_type="vm",
            provider="gcp",
            account_id="my-project-id",
            region="us-central1",
            name="vm-1",
        )
        assert resource.provider == "gcp"
        assert resource.account_id == "my-project-id"


class TestCloudResourceDefaults:
    """Test default values for optional fields."""

    def test_ip_addresses_default_empty(self):
        """ip_addresses defaults to an empty list."""
        resource = _make_minimal_resource()
        assert resource.ip_addresses == []

    def test_tags_default_empty(self):
        """tags defaults to an empty dict."""
        resource = _make_minimal_resource()
        assert resource.tags == {}

    def test_details_default_empty(self):
        """details defaults to an empty dict."""
        resource = _make_minimal_resource()
        assert resource.details == {}

    def test_counted_default_none(self):
        """counted defaults to None (not yet categorized)."""
        resource = _make_minimal_resource()
        assert resource.counted is None

    def test_category_default_none(self):
        """category defaults to None (not yet categorized)."""
        resource = _make_minimal_resource()
        assert resource.category is None

    def test_skip_reason_default_none(self):
        """skip_reason defaults to None."""
        resource = _make_minimal_resource()
        assert resource.skip_reason is None

    def test_mutable_defaults_are_independent(self):
        """Each instance gets its own mutable default (no shared state)."""
        r1 = _make_minimal_resource()
        r2 = _make_minimal_resource()
        r1.ip_addresses.append("10.0.0.1")
        r1.tags["key"] = "value"
        assert r2.ip_addresses == []
        assert r2.tags == {}


class TestHasIps:
    """Test the has_ips() helper method."""

    def test_has_ips_with_ips(self):
        """has_ips() returns True when ip_addresses is non-empty."""
        resource = _make_minimal_resource()
        resource.ip_addresses = ["10.0.1.5"]
        assert resource.has_ips() is True

    def test_has_ips_without_ips(self):
        """has_ips() returns False when ip_addresses is empty."""
        resource = _make_minimal_resource()
        assert resource.has_ips() is False

    def test_has_ips_with_multiple_ips(self):
        """has_ips() returns True with multiple IP addresses."""
        resource = _make_minimal_resource()
        resource.ip_addresses = ["10.0.1.5", "54.23.100.50", "172.16.0.1"]
        assert resource.has_ips() is True


class TestDiscoveredAt:
    """Test that discovered_at is auto-populated."""

    def test_discovered_at_auto_populated(self):
        """discovered_at is automatically set to an ISO timestamp."""
        resource = _make_minimal_resource()
        assert resource.discovered_at is not None
        assert len(resource.discovered_at) > 0
        # Should be a valid ISO format string containing 'T' separator
        assert "T" in resource.discovered_at

    def test_discovered_at_can_be_overridden(self):
        """discovered_at can be explicitly set."""
        resource = CloudResource(
            resource_id="test-id",
            resource_type="vm",
            provider="aws",
            account_id="123456",
            region="us-east-1",
            name="test",
            discovered_at="2026-01-01T00:00:00",
        )
        assert resource.discovered_at == "2026-01-01T00:00:00"


class TestSerialization:
    """Test that CloudResource works with dataclasses.asdict() for JSON serialization."""

    def test_asdict_produces_dict(self):
        """dataclasses.asdict() converts CloudResource to a plain dict."""
        resource = CloudResource(
            resource_id="arn:aws:ec2:us-east-1:123456:instance/i-abc",
            resource_type="vm",
            provider="aws",
            account_id="123456",
            region="us-east-1",
            name="test-vm",
            ip_addresses=["10.0.1.5"],
            tags={"env": "test"},
            details={"state": "running"},
            discovered_at="2026-02-23T10:00:00",
            counted=True,
            category="asset",
            skip_reason=None,
        )
        result = dataclasses.asdict(resource)
        assert isinstance(result, dict)
        assert result["resource_id"] == "arn:aws:ec2:us-east-1:123456:instance/i-abc"
        assert result["resource_type"] == "vm"
        assert result["provider"] == "aws"
        assert result["ip_addresses"] == ["10.0.1.5"]
        assert result["tags"] == {"env": "test"}
        assert result["counted"] is True
        assert result["category"] == "asset"

    def test_asdict_is_json_serializable(self):
        """dataclasses.asdict() output can be serialized to JSON."""
        resource = _make_minimal_resource()
        result = dataclasses.asdict(resource)
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
        # Round-trip: parse back and verify
        parsed = json.loads(json_str)
        assert parsed["resource_id"] == resource.resource_id
        assert parsed["provider"] == resource.provider

    def test_asdict_with_nested_details(self):
        """dataclasses.asdict() handles nested dicts in details field."""
        resource = _make_minimal_resource()
        resource.details = {
            "network": {"vpc_id": "vpc-abc", "subnet_id": "subnet-123"},
            "state": "running",
        }
        result = dataclasses.asdict(resource)
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed["details"]["network"]["vpc_id"] == "vpc-abc"


def _make_minimal_resource() -> CloudResource:
    """Create a CloudResource with only required fields for testing defaults."""
    return CloudResource(
        resource_id="test-resource-id",
        resource_type="vm",
        provider="aws",
        account_id="123456789012",
        region="us-east-1",
        name="test-resource",
    )
