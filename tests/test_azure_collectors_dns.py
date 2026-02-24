"""Tests for Azure DNS resource collectors.

Uses unittest.mock to simulate Azure DNS and Private DNS SDK client
objects. Verifies that public and private DNS zone and record collectors
produce correctly-shaped CloudResource instances with full ARM resource IDs.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cloud_usage.providers.azure.collectors.dns import (
    collect_azure_dns_records,
    collect_azure_dns_zones,
    collect_azure_private_dns_records,
    collect_azure_private_dns_zones,
)
from cloud_usage.schema.resource import CloudResource


# ---------------------------------------------------------------------------
# Helpers to build mock Azure DNS SDK model objects
# ---------------------------------------------------------------------------

def _make_dns_zone(
    name: str,
    resource_id: str,
    number_of_record_sets: int | None = None,
    tags: dict[str, str] | None = None,
) -> SimpleNamespace:
    """Build a mock DNS Zone SDK object."""
    return SimpleNamespace(
        id=resource_id,
        name=name,
        tags=tags,
        number_of_record_sets=number_of_record_sets,
    )


def _make_record_set(
    name: str,
    resource_id: str,
    record_type: str,
    ttl: int = 300,
) -> SimpleNamespace:
    """Build a mock RecordSet SDK object."""
    return SimpleNamespace(
        id=resource_id,
        name=name,
        type=record_type,
        ttl=ttl,
    )


# ---------------------------------------------------------------------------
# Public DNS zone tests
# ---------------------------------------------------------------------------

class TestCollectAzureDnsZones:
    """Tests for collect_azure_dns_zones."""

    def test_public_dns_zone_collection(self):
        """Two public DNS zones are discovered."""
        mock_client = MagicMock()
        mock_client.zones.list.return_value = [
            _make_dns_zone(
                name="example.com",
                resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/dnszones/example.com",
                number_of_record_sets=42,
                tags={"purpose": "production"},
            ),
            _make_dns_zone(
                name="internal.corp",
                resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/dnszones/internal.corp",
                number_of_record_sets=5,
            ),
        ]

        result = collect_azure_dns_zones(mock_client, "sub1")

        assert len(result) == 2
        assert all(isinstance(r, CloudResource) for r in result)

        zone1 = result[0]
        assert zone1.resource_type == "azure-dns-zone"
        assert zone1.provider == "azure"
        assert zone1.account_id == "sub1"
        assert zone1.region == "global"
        assert zone1.name == "example.com"
        assert zone1.ip_addresses == []
        assert zone1.details["zone_type"] == "public"
        assert zone1.details["resource_group"] == "rg-dns"
        assert zone1.details["record_count"] == 42
        assert zone1.tags == {"purpose": "production"}

        zone2 = result[1]
        assert zone2.name == "internal.corp"
        assert zone2.details["record_count"] == 5
        assert zone2.tags == {}

    def test_dns_zone_with_no_record_count(self):
        """Zone without number_of_record_sets defaults to 0."""
        mock_client = MagicMock()
        mock_client.zones.list.return_value = [
            _make_dns_zone(
                name="test.io",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/dnszones/test.io",
            ),
        ]

        result = collect_azure_dns_zones(mock_client, "sub1")

        assert len(result) == 1
        assert result[0].details["record_count"] == 0


# ---------------------------------------------------------------------------
# Public DNS record tests
# ---------------------------------------------------------------------------

class TestCollectAzureDnsRecords:
    """Tests for collect_azure_dns_records."""

    def test_dns_record_collection(self):
        """Records from two zones are discovered with full ARM resource IDs."""
        zones = [
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/dnszones/example.com",
                resource_type="azure-dns-zone",
                provider="azure",
                account_id="sub1",
                region="global",
                name="example.com",
                details={"resource_group": "rg-dns", "zone_type": "public"},
            ),
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/dnszones/test.io",
                resource_type="azure-dns-zone",
                provider="azure",
                account_id="sub1",
                region="global",
                name="test.io",
                details={"resource_group": "rg-dns", "zone_type": "public"},
            ),
        ]

        mock_client = MagicMock()

        def list_by_dns_zone(rg, zone_name):
            if zone_name == "example.com":
                return [
                    _make_record_set(
                        name="@",
                        resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/dnszones/example.com/@/A",
                        record_type="Microsoft.Network/dnszones/A",
                        ttl=300,
                    ),
                    _make_record_set(
                        name="www",
                        resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/dnszones/example.com/www/CNAME",
                        record_type="Microsoft.Network/dnszones/CNAME",
                        ttl=600,
                    ),
                ]
            elif zone_name == "test.io":
                return [
                    _make_record_set(
                        name="api",
                        resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/dnszones/test.io/api/A",
                        record_type="Microsoft.Network/dnszones/A",
                        ttl=60,
                    ),
                ]
            return []

        mock_client.record_sets.list_by_dns_zone.side_effect = list_by_dns_zone

        result = collect_azure_dns_records(mock_client, "sub1", zones)

        assert len(result) == 3
        assert all(r.resource_type == "azure-dns-record" for r in result)
        assert all(r.provider == "azure" for r in result)
        assert all(r.region == "global" for r in result)

        # Verify full ARM resource IDs (not just names)
        assert result[0].resource_id == "/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/dnszones/example.com/@/A"
        assert result[0].details["record_type"] == "A"
        assert result[0].details["zone_name"] == "example.com"
        assert result[0].details["ttl"] == 300

        assert result[1].details["record_type"] == "CNAME"
        assert result[1].details["ttl"] == 600

        assert result[2].resource_id == "/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/dnszones/test.io/api/A"

    def test_dns_record_per_zone_error_isolation(self):
        """One zone failure does not block records from other zones."""
        zones = [
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/dnszones/failing.com",
                resource_type="azure-dns-zone",
                provider="azure",
                account_id="sub1",
                region="global",
                name="failing.com",
                details={"resource_group": "rg-dns"},
            ),
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/dnszones/ok.com",
                resource_type="azure-dns-zone",
                provider="azure",
                account_id="sub1",
                region="global",
                name="ok.com",
                details={"resource_group": "rg-dns"},
            ),
        ]

        mock_client = MagicMock()

        def list_by_dns_zone(rg, zone_name):
            if zone_name == "failing.com":
                raise RuntimeError("Simulated Azure API error")
            return [
                _make_record_set(
                    name="healthy",
                    resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/dnszones/ok.com/healthy/A",
                    record_type="Microsoft.Network/dnszones/A",
                    ttl=300,
                ),
            ]

        mock_client.record_sets.list_by_dns_zone.side_effect = list_by_dns_zone

        result = collect_azure_dns_records(mock_client, "sub1", zones)

        # Should still get records from ok.com despite failing.com error
        assert len(result) == 1
        assert result[0].name == "healthy"

    def test_dns_record_zone_with_no_records(self):
        """Zone with no records returns empty list."""
        zones = [
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/dnszones/empty.com",
                resource_type="azure-dns-zone",
                provider="azure",
                account_id="sub1",
                region="global",
                name="empty.com",
                details={"resource_group": "rg-dns"},
            ),
        ]

        mock_client = MagicMock()
        mock_client.record_sets.list_by_dns_zone.return_value = []

        result = collect_azure_dns_records(mock_client, "sub1", zones)

        assert result == []

    def test_record_type_parsing_from_arm_type(self):
        """Record type is correctly parsed from full ARM type path."""
        zones = [
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/dnszones/test.com",
                resource_type="azure-dns-zone",
                provider="azure",
                account_id="sub1",
                region="global",
                name="test.com",
                details={"resource_group": "rg1"},
            ),
        ]

        mock_client = MagicMock()
        mock_client.record_sets.list_by_dns_zone.return_value = [
            _make_record_set(
                name="@",
                resource_id="/subs/sub1/rg/rg1/providers/Microsoft.Network/dnszones/test.com/@/SOA",
                record_type="Microsoft.Network/dnszones/SOA",
            ),
            _make_record_set(
                name="mail",
                resource_id="/subs/sub1/rg/rg1/providers/Microsoft.Network/dnszones/test.com/mail/MX",
                record_type="Microsoft.Network/dnszones/MX",
            ),
            _make_record_set(
                name="txt",
                resource_id="/subs/sub1/rg/rg1/providers/Microsoft.Network/dnszones/test.com/txt/TXT",
                record_type="Microsoft.Network/dnszones/TXT",
            ),
        ]

        result = collect_azure_dns_records(mock_client, "sub1", zones)

        assert result[0].details["record_type"] == "SOA"
        assert result[1].details["record_type"] == "MX"
        assert result[2].details["record_type"] == "TXT"

    def test_dns_record_skips_zones_with_missing_resource_group(self):
        """Zones with empty resource_group are skipped."""
        zones = [
            CloudResource(
                resource_id="/some/invalid",
                resource_type="azure-dns-zone",
                provider="azure",
                account_id="sub1",
                region="global",
                name="broken.com",
                details={"resource_group": ""},
            ),
        ]

        mock_client = MagicMock()
        result = collect_azure_dns_records(mock_client, "sub1", zones)

        assert result == []
        mock_client.record_sets.list_by_dns_zone.assert_not_called()


# ---------------------------------------------------------------------------
# Private DNS zone tests
# ---------------------------------------------------------------------------

class TestCollectAzurePrivateDnsZones:
    """Tests for collect_azure_private_dns_zones."""

    def test_private_dns_zone_collection(self):
        """Two private DNS zones are discovered."""
        mock_client = MagicMock()
        mock_client.private_zones.list.return_value = [
            _make_dns_zone(
                name="privatelink.database.windows.net",
                resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/privateDnsZones/privatelink.database.windows.net",
                number_of_record_sets=10,
                tags={"managed": "true"},
            ),
            _make_dns_zone(
                name="internal.contoso.com",
                resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/privateDnsZones/internal.contoso.com",
                number_of_record_sets=25,
            ),
        ]

        result = collect_azure_private_dns_zones(mock_client, "sub1")

        assert len(result) == 2
        assert all(r.resource_type == "azure-private-dns-zone" for r in result)
        assert all(r.provider == "azure" for r in result)
        assert all(r.region == "global" for r in result)

        zone1 = result[0]
        assert zone1.name == "privatelink.database.windows.net"
        assert zone1.details["zone_type"] == "private"
        assert zone1.details["record_count"] == 10
        assert zone1.details["resource_group"] == "rg-dns"
        assert zone1.tags == {"managed": "true"}

        zone2 = result[1]
        assert zone2.name == "internal.contoso.com"
        assert zone2.details["record_count"] == 25


# ---------------------------------------------------------------------------
# Private DNS record tests
# ---------------------------------------------------------------------------

class TestCollectAzurePrivateDnsRecords:
    """Tests for collect_azure_private_dns_records."""

    def test_private_dns_record_collection(self):
        """Records from a private DNS zone are discovered."""
        zones = [
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/privateDnsZones/internal.contoso.com",
                resource_type="azure-private-dns-zone",
                provider="azure",
                account_id="sub1",
                region="global",
                name="internal.contoso.com",
                details={"resource_group": "rg-dns", "zone_type": "private"},
            ),
        ]

        mock_client = MagicMock()
        mock_client.record_sets.list.return_value = [
            _make_record_set(
                name="db",
                resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/privateDnsZones/internal.contoso.com/A/db",
                record_type="Microsoft.Network/privateDnsZones/A",
                ttl=10,
            ),
            _make_record_set(
                name="app",
                resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/privateDnsZones/internal.contoso.com/A/app",
                record_type="Microsoft.Network/privateDnsZones/A",
                ttl=30,
            ),
        ]

        result = collect_azure_private_dns_records(mock_client, "sub1", zones)

        assert len(result) == 2
        assert all(r.resource_type == "azure-private-dns-record" for r in result)
        assert all(r.provider == "azure" for r in result)
        assert all(r.region == "global" for r in result)

        rec1 = result[0]
        assert rec1.resource_id == "/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/privateDnsZones/internal.contoso.com/A/db"
        assert rec1.details["record_type"] == "A"
        assert rec1.details["zone_name"] == "internal.contoso.com"
        assert rec1.details["ttl"] == 10

    def test_private_dns_record_per_zone_error_isolation(self):
        """One private zone failure does not block records from other zones."""
        zones = [
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/privateDnsZones/failing.internal",
                resource_type="azure-private-dns-zone",
                provider="azure",
                account_id="sub1",
                region="global",
                name="failing.internal",
                details={"resource_group": "rg-dns"},
            ),
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/privateDnsZones/working.internal",
                resource_type="azure-private-dns-zone",
                provider="azure",
                account_id="sub1",
                region="global",
                name="working.internal",
                details={"resource_group": "rg-dns"},
            ),
        ]

        mock_client = MagicMock()

        def list_records(rg, zone_name):
            if zone_name == "failing.internal":
                raise RuntimeError("Simulated private DNS API error")
            return [
                _make_record_set(
                    name="host1",
                    resource_id="/subscriptions/sub1/resourceGroups/rg-dns/providers/Microsoft.Network/privateDnsZones/working.internal/A/host1",
                    record_type="Microsoft.Network/privateDnsZones/A",
                    ttl=60,
                ),
            ]

        mock_client.record_sets.list.side_effect = list_records

        result = collect_azure_private_dns_records(mock_client, "sub1", zones)

        assert len(result) == 1
        assert result[0].name == "host1"

    def test_private_dns_zone_with_no_records(self):
        """Private zone with no records returns empty list."""
        zones = [
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/empty.internal",
                resource_type="azure-private-dns-zone",
                provider="azure",
                account_id="sub1",
                region="global",
                name="empty.internal",
                details={"resource_group": "rg1"},
            ),
        ]

        mock_client = MagicMock()
        mock_client.record_sets.list.return_value = []

        result = collect_azure_private_dns_records(mock_client, "sub1", zones)

        assert result == []

    def test_private_dns_record_type_parsing(self):
        """Record type is parsed from full ARM type path for private zones."""
        zones = [
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/test.internal",
                resource_type="azure-private-dns-zone",
                provider="azure",
                account_id="sub1",
                region="global",
                name="test.internal",
                details={"resource_group": "rg1"},
            ),
        ]

        mock_client = MagicMock()
        mock_client.record_sets.list.return_value = [
            _make_record_set(
                name="@",
                resource_id="/subs/sub1/rg/rg1/providers/Microsoft.Network/privateDnsZones/test.internal/@/SOA",
                record_type="Microsoft.Network/privateDnsZones/SOA",
            ),
            _make_record_set(
                name="srv",
                resource_id="/subs/sub1/rg/rg1/providers/Microsoft.Network/privateDnsZones/test.internal/srv/SRV",
                record_type="Microsoft.Network/privateDnsZones/SRV",
            ),
        ]

        result = collect_azure_private_dns_records(mock_client, "sub1", zones)

        assert result[0].details["record_type"] == "SOA"
        assert result[1].details["record_type"] == "SRV"

    def test_private_dns_record_skips_zones_with_missing_resource_group(self):
        """Private zones with empty resource_group are skipped."""
        zones = [
            CloudResource(
                resource_id="/some/invalid",
                resource_type="azure-private-dns-zone",
                provider="azure",
                account_id="sub1",
                region="global",
                name="broken.internal",
                details={"resource_group": ""},
            ),
        ]

        mock_client = MagicMock()
        result = collect_azure_private_dns_records(mock_client, "sub1", zones)

        assert result == []
        mock_client.record_sets.list.assert_not_called()


# ---------------------------------------------------------------------------
# Cross-cutting verification tests
# ---------------------------------------------------------------------------

class TestDnsCollectorsGlobalProperties:
    """Verify all DNS resources have provider=azure and region=global."""

    def test_all_public_dns_resources_are_global(self):
        """Public DNS zones and records all have region='global'."""
        mock_dns = MagicMock()
        mock_dns.zones.list.return_value = [
            _make_dns_zone(
                name="example.com",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/dnszones/example.com",
                number_of_record_sets=1,
            ),
        ]
        mock_dns.record_sets.list_by_dns_zone.return_value = [
            _make_record_set(
                name="@",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/dnszones/example.com/@/A",
                record_type="Microsoft.Network/dnszones/A",
            ),
        ]

        zones = collect_azure_dns_zones(mock_dns, "sub1")
        records = collect_azure_dns_records(mock_dns, "sub1", zones)

        all_resources = zones + records
        assert all(r.provider == "azure" for r in all_resources)
        assert all(r.region == "global" for r in all_resources)

    def test_all_private_dns_resources_are_global(self):
        """Private DNS zones and records all have region='global'."""
        mock_privatedns = MagicMock()
        mock_privatedns.private_zones.list.return_value = [
            _make_dns_zone(
                name="internal.com",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/internal.com",
                number_of_record_sets=1,
            ),
        ]
        mock_privatedns.record_sets.list.return_value = [
            _make_record_set(
                name="host",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/internal.com/A/host",
                record_type="Microsoft.Network/privateDnsZones/A",
            ),
        ]

        zones = collect_azure_private_dns_zones(mock_privatedns, "sub1")
        records = collect_azure_private_dns_records(mock_privatedns, "sub1", zones)

        all_resources = zones + records
        assert all(r.provider == "azure" for r in all_resources)
        assert all(r.region == "global" for r in all_resources)
