"""Unit tests for GCP Cloud DNS resource collectors.

Tests DNS zone collection (per-project) and DNS record collection (per-zone)
with full record type enumeration. Covers A/AAAA IP extraction, SOA/NS
inclusion, per-zone error isolation, and empty zone handling.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from cloud_usage.schema.resource import CloudResource


# ---------------------------------------------------------------------------
# Module-level mock setup: mock GCP DNS SDK modules so imports succeed
# without the actual google-cloud-dns SDK installed.
# ---------------------------------------------------------------------------

_mock_dns = MagicMock()
_mock_google = ModuleType("google")
_mock_google_cloud = ModuleType("google.cloud")
_mock_google.__path__ = []
_mock_google_cloud.__path__ = []

_patches = {
    "google": _mock_google,
    "google.cloud": _mock_google_cloud,
    "google.cloud.dns": _mock_dns,
}


@pytest.fixture(autouse=True)
def _mock_gcp_sdk():
    """Mock GCP SDK modules for every test."""
    with patch.dict(sys.modules, _patches):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_zone(
    name: str = "my-zone",
    dns_name: str = "example.com.",
    visibility: str = "public",
):
    """Create a mock DNS zone object."""
    zone = MagicMock()
    zone.name = name
    zone.dns_name = dns_name
    zone.visibility = visibility
    return zone


def _make_record_set(
    name: str = "www.example.com.",
    record_type: str = "A",
    ttl: int = 300,
    rrdatas: list[str] | None = None,
):
    """Create a mock DNS resource record set."""
    rs = MagicMock()
    rs.name = name
    rs.record_type = record_type
    rs.ttl = ttl
    rs.rrdatas = rrdatas or []
    return rs


def _make_zone_resource(
    zone_name: str = "my-zone",
    dns_name: str = "example.com.",
    project_id: str = "proj",
) -> CloudResource:
    """Create a CloudResource representing a discovered DNS zone."""
    return CloudResource(
        resource_id=f"projects/{project_id}/managedZones/{zone_name}",
        resource_type="gcp-dns-zone",
        provider="gcp",
        account_id=project_id,
        region="global",
        name=dns_name,
        ip_addresses=[],
        tags={},
        details={
            "zone_name": zone_name,
            "dns_name": dns_name,
            "visibility": "public",
        },
    )


# ===========================================================================
# collect_gcp_dns_zones tests
# ===========================================================================


class TestCollectGcpDnsZones:
    """Tests for collect_gcp_dns_zones."""

    def test_returns_dns_zone_resources(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_zones

        z1 = _make_zone("zone-1", "example.com.")
        z2 = _make_zone("zone-2", "internal.corp.")

        dns_client = MagicMock()
        dns_client.list_zones.return_value = [z1, z2]

        result = collect_gcp_dns_zones(dns_client, "proj")

        assert len(result) == 2
        assert result[0].resource_type == "gcp-dns-zone"
        assert result[1].resource_type == "gcp-dns-zone"

    def test_dns_zone_fields(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_zones

        z = _make_zone("prod-zone", "prod.example.com.", "private")
        dns_client = MagicMock()
        dns_client.list_zones.return_value = [z]

        result = collect_gcp_dns_zones(dns_client, "proj-x")

        r = result[0]
        assert r.provider == "gcp"
        assert r.account_id == "proj-x"
        assert r.region == "global"
        assert r.name == "prod.example.com."
        assert r.ip_addresses == []
        assert r.resource_id == "projects/proj-x/managedZones/prod-zone"
        assert r.details["zone_name"] == "prod-zone"
        assert r.details["dns_name"] == "prod.example.com."
        assert r.details["visibility"] == "private"

    def test_dns_zone_empty_project(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_zones

        dns_client = MagicMock()
        dns_client.list_zones.return_value = []

        result = collect_gcp_dns_zones(dns_client, "empty-proj")

        assert result == []

    def test_dns_zone_default_visibility(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_zones

        z = _make_zone("pub-zone", "public.example.com.")
        # Remove visibility attribute to test default
        del z.visibility
        dns_client = MagicMock()
        dns_client.list_zones.return_value = [z]

        result = collect_gcp_dns_zones(dns_client, "proj")

        assert result[0].details["visibility"] == "public"


# ===========================================================================
# collect_gcp_dns_records tests
# ===========================================================================


class TestCollectGcpDnsRecords:
    """Tests for collect_gcp_dns_records."""

    def test_returns_dns_record_resources(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_records

        rs1 = _make_record_set("www.example.com.", "A", 300, ["1.2.3.4"])
        rs2 = _make_record_set("mail.example.com.", "MX", 3600, ["10 mail.example.com."])

        zone_obj = MagicMock()
        zone_obj.list_resource_record_sets.return_value = [rs1, rs2]

        dns_client = MagicMock()
        dns_client.zone.return_value = zone_obj

        zones = [_make_zone_resource("my-zone")]

        result = collect_gcp_dns_records(dns_client, "proj", zones)

        assert len(result) == 2
        assert all(r.resource_type == "gcp-dns-record" for r in result)

    def test_a_record_ip_extraction(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_records

        rs = _make_record_set("www.example.com.", "A", 300, ["1.2.3.4", "5.6.7.8"])

        zone_obj = MagicMock()
        zone_obj.list_resource_record_sets.return_value = [rs]

        dns_client = MagicMock()
        dns_client.zone.return_value = zone_obj

        zones = [_make_zone_resource("my-zone")]

        result = collect_gcp_dns_records(dns_client, "proj", zones)

        assert result[0].ip_addresses == ["1.2.3.4", "5.6.7.8"]

    def test_aaaa_record_ip_extraction(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_records

        rs = _make_record_set("ipv6.example.com.", "AAAA", 300, ["2001:db8::1"])

        zone_obj = MagicMock()
        zone_obj.list_resource_record_sets.return_value = [rs]

        dns_client = MagicMock()
        dns_client.zone.return_value = zone_obj

        zones = [_make_zone_resource("my-zone")]

        result = collect_gcp_dns_records(dns_client, "proj", zones)

        assert result[0].ip_addresses == ["2001:db8::1"]

    def test_non_ip_record_types_have_empty_ips(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_records

        cname_rs = _make_record_set("alias.example.com.", "CNAME", 300, ["www.example.com."])
        mx_rs = _make_record_set("example.com.", "MX", 3600, ["10 mail.example.com."])
        txt_rs = _make_record_set("example.com.", "TXT", 3600, ["v=spf1 include:_spf.google.com ~all"])

        zone_obj = MagicMock()
        zone_obj.list_resource_record_sets.return_value = [cname_rs, mx_rs, txt_rs]

        dns_client = MagicMock()
        dns_client.zone.return_value = zone_obj

        zones = [_make_zone_resource("my-zone")]

        result = collect_gcp_dns_records(dns_client, "proj", zones)

        assert len(result) == 3
        for r in result:
            assert r.ip_addresses == []

    def test_soa_and_ns_records_included(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_records

        soa_rs = _make_record_set(
            "example.com.", "SOA", 21600,
            ["ns-cloud-a1.googledomains.com. cloud-dns-hostmaster.google.com. 1 21600 3600 259200 300"]
        )
        ns_rs = _make_record_set(
            "example.com.", "NS", 21600,
            ["ns-cloud-a1.googledomains.com.", "ns-cloud-a2.googledomains.com."]
        )

        zone_obj = MagicMock()
        zone_obj.list_resource_record_sets.return_value = [soa_rs, ns_rs]

        dns_client = MagicMock()
        dns_client.zone.return_value = zone_obj

        zones = [_make_zone_resource("my-zone")]

        result = collect_gcp_dns_records(dns_client, "proj", zones)

        assert len(result) == 2
        record_types = {r.details["record_type"] for r in result}
        assert "SOA" in record_types
        assert "NS" in record_types

    def test_per_zone_error_isolation(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_records

        # Zone 1 will fail
        zone1_obj = MagicMock()
        zone1_obj.list_resource_record_sets.side_effect = Exception("API error")

        # Zone 2 will succeed
        rs = _make_record_set("www.good.com.", "A", 300, ["10.0.0.1"])
        zone2_obj = MagicMock()
        zone2_obj.list_resource_record_sets.return_value = [rs]

        dns_client = MagicMock()
        dns_client.zone.side_effect = lambda name: (
            zone1_obj if name == "bad-zone" else zone2_obj
        )

        zones = [
            _make_zone_resource("bad-zone", "bad.example.com."),
            _make_zone_resource("good-zone", "good.example.com."),
        ]

        result = collect_gcp_dns_records(dns_client, "proj", zones)

        # Only zone 2 records should be present
        assert len(result) == 1
        assert result[0].name == "www.good.com."

    def test_empty_zone_returns_empty(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_records

        zone_obj = MagicMock()
        zone_obj.list_resource_record_sets.return_value = []

        dns_client = MagicMock()
        dns_client.zone.return_value = zone_obj

        zones = [_make_zone_resource("empty-zone")]

        result = collect_gcp_dns_records(dns_client, "proj", zones)

        assert result == []

    def test_record_resource_id_format(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_records

        rs = _make_record_set("www.example.com.", "A", 300, ["1.2.3.4"])

        zone_obj = MagicMock()
        zone_obj.list_resource_record_sets.return_value = [rs]

        dns_client = MagicMock()
        dns_client.zone.return_value = zone_obj

        zones = [_make_zone_resource("my-zone")]

        result = collect_gcp_dns_records(dns_client, "proj", zones)

        assert result[0].resource_id == "projects/proj/managedZones/my-zone/www.example.com./A"

    def test_record_fields(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_records

        rs = _make_record_set("app.example.com.", "A", 600, ["10.0.0.1"])

        zone_obj = MagicMock()
        zone_obj.list_resource_record_sets.return_value = [rs]

        dns_client = MagicMock()
        dns_client.zone.return_value = zone_obj

        zones = [_make_zone_resource("my-zone")]

        result = collect_gcp_dns_records(dns_client, "proj-a", zones)

        r = result[0]
        assert r.provider == "gcp"
        assert r.account_id == "proj-a"
        assert r.region == "global"
        assert r.name == "app.example.com."
        assert r.details["record_type"] == "A"
        assert r.details["ttl"] == 600
        assert r.details["zone_name"] == "my-zone"

    def test_multiple_zones_records_collected(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_records

        rs1 = _make_record_set("www.zone1.com.", "A", 300, ["1.1.1.1"])
        rs2 = _make_record_set("api.zone2.com.", "A", 300, ["2.2.2.2"])

        zone1_obj = MagicMock()
        zone1_obj.list_resource_record_sets.return_value = [rs1]

        zone2_obj = MagicMock()
        zone2_obj.list_resource_record_sets.return_value = [rs2]

        dns_client = MagicMock()
        dns_client.zone.side_effect = lambda name: (
            zone1_obj if name == "zone-1" else zone2_obj
        )

        zones = [
            _make_zone_resource("zone-1", "zone1.com."),
            _make_zone_resource("zone-2", "zone2.com."),
        ]

        result = collect_gcp_dns_records(dns_client, "proj", zones)

        assert len(result) == 2

    def test_skips_zones_without_zone_name_in_details(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_records

        # Create a zone resource with empty zone_name
        bad_zone = CloudResource(
            resource_id="projects/proj/managedZones/",
            resource_type="gcp-dns-zone",
            provider="gcp",
            account_id="proj",
            region="global",
            name="bad.example.com.",
            details={"zone_name": "", "dns_name": "bad.example.com."},
        )

        dns_client = MagicMock()

        result = collect_gcp_dns_records(dns_client, "proj", [bad_zone])

        assert result == []
        # dns_client.zone should not have been called
        dns_client.zone.assert_not_called()

    def test_no_zones_returns_empty(self):
        from cloud_usage.providers.gcp.collectors.dns import collect_gcp_dns_records

        dns_client = MagicMock()

        result = collect_gcp_dns_records(dns_client, "proj", [])

        assert result == []
