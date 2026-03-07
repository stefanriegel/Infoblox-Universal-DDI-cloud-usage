"""TDD RED gate — Microsoft AD runner / run_ad_analysis() tests.

The module-level import below triggers ImportError/ModuleNotFoundError until
29-02/29-03 create the providers/ad package. Tests define the full CloudResource
output contract for run_ad_analysis() and the XLS report integration (AD-08).

Requirements covered: AD-01, AD-02, AD-03, AD-04, AD-08.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ---------------------------------------------------------------------------
# Module-level imports — these FAIL until 29-02 creates the AD provider package.
# ImportError/ModuleNotFoundError here is the RED gate signal.
# ---------------------------------------------------------------------------

from cloud_usage.providers.ad import run_ad_analysis  # noqa: E402
from cloud_usage.providers.ad.options import AdOptions  # noqa: E402
from cloud_usage.schema.resource import CloudResource  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_opts(servers=None, services=("dns", "dhcp", "user"), auth_mode="kerberos"):
    return AdOptions(
        servers=servers or ["dc1.corp.example.com"],
        services=services,
        auth_mode=auth_mode,
    )


def _make_mock_collector_result():
    """Return a mock collector result dict simulating a successful AD scan."""
    return {
        "server": "dc1.corp.example.com",
        "status": "ok",
        "dns": {
            "zone_keys": {"corp.example.com": {"ZoneName": "corp.example.com"},
                          "test.corp.example.com": {"ZoneName": "test.corp.example.com"}},
            "record_keys": {
                "corp.example.com|www|A|10.0.0.1": {"HostName": "www", "RecordType": "A",
                                                     "RecordData": {"IPv4Address": "10.0.0.1"}},
                "corp.example.com|mail|A|10.0.0.2": {"HostName": "mail", "RecordType": "A",
                                                      "RecordData": {"IPv4Address": "10.0.0.2"}},
                "corp.example.com|vpn|A|10.0.0.3": {"HostName": "vpn", "RecordType": "A",
                                                     "RecordData": {"IPv4Address": "10.0.0.3"}},
                "test.corp.example.com|app|A|10.0.1.1": {"HostName": "app", "RecordType": "A",
                                                          "RecordData": {"IPv4Address": "10.0.1.1"}},
                "test.corp.example.com|db|A|10.0.1.2": {"HostName": "db", "RecordType": "A",
                                                         "RecordData": {"IPv4Address": "10.0.1.2"}},
            },
            "ip_addresses": ["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.1.1", "10.0.1.2"],
        },
        "dhcp": {
            "scope_keys": {
                "192.168.1.0": {"ScopeId": "192.168.1.0", "Name": "Scope-1"},
                "192.168.2.0": {"ScopeId": "192.168.2.0", "Name": "Scope-2"},
                "192.168.3.0": {"ScopeId": "192.168.3.0", "Name": "Scope-3"},
            },
            "lease_keys": {f"192.168.{s}.{i}": {"IPAddress": f"192.168.{s}.{i}"}
                           for s in range(1, 4) for i in range(10, 14)},  # 12 leases
            "reservation_keys": {f"192.168.{s}.200": {"IPAddress": f"192.168.{s}.200"}
                                  for s in range(1, 4)},  # 3 reservations
        },
        "users": {
            "user_keys": {
                "S-1-5-21-100-200-300-1001": {"SamAccountName": "user1",
                                               "SID": {"Value": "S-1-5-21-100-200-300-1001"}},
                "S-1-5-21-100-200-300-1002": {"SamAccountName": "user2",
                                               "SID": {"Value": "S-1-5-21-100-200-300-1002"}},
                "S-1-5-21-100-200-300-1003": {"SamAccountName": "user3",
                                               "SID": {"Value": "S-1-5-21-100-200-300-1003"}},
                "S-1-5-21-100-200-300-1004": {"SamAccountName": "user4",
                                               "SID": {"Value": "S-1-5-21-100-200-300-1004"}},
                "S-1-5-21-100-200-300-1005": {"SamAccountName": "user5",
                                               "SID": {"Value": "S-1-5-21-100-200-300-1005"}},
                "S-1-5-21-100-200-300-1006": {"SamAccountName": "user6",
                                               "SID": {"Value": "S-1-5-21-100-200-300-1006"}},
                "S-1-5-21-100-200-300-1007": {"SamAccountName": "user7",
                                               "SID": {"Value": "S-1-5-21-100-200-300-1007"}},
                "S-1-5-21-100-200-300-1008": {"SamAccountName": "user8",
                                               "SID": {"Value": "S-1-5-21-100-200-300-1008"}},
                "S-1-5-21-100-200-300-1009": {"SamAccountName": "user9",
                                               "SID": {"Value": "S-1-5-21-100-200-300-1009"}},
                "S-1-5-21-100-200-300-1010": {"SamAccountName": "user10",
                                               "SID": {"Value": "S-1-5-21-100-200-300-1010"}},
            },
        },
    }


# ---------------------------------------------------------------------------
# TestRunAdAnalysisReturnsCloudResources — overall contract
# ---------------------------------------------------------------------------


class TestRunAdAnalysisReturnsCloudResources:
    """run_ad_analysis() returns a list of CloudResource objects."""

    def test_returns_cloud_resources(self):
        """run_ad_analysis() returns a list of CloudResource instances."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        assert isinstance(resources, list)
        assert len(resources) > 0
        assert all(isinstance(r, CloudResource) for r in resources)

    def test_returns_correct_resource_types(self):
        """run_ad_analysis() resources include all expected resource_type strings."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        resource_types = {r.resource_type for r in resources}
        assert "ad-dns-zone" in resource_types
        assert "ad-dns-record" in resource_types
        assert "ad-dhcp-scope" in resource_types
        assert "ad-user" in resource_types

    def test_resource_counts(self):
        """run_ad_analysis() returns expected counts per type."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        zones = [r for r in resources if r.resource_type == "ad-dns-zone"]
        records = [r for r in resources if r.resource_type == "ad-dns-record"]
        scopes = [r for r in resources if r.resource_type == "ad-dhcp-scope"]
        users = [r for r in resources if r.resource_type == "ad-user"]

        assert len(zones) == 2
        assert len(records) == 5
        assert len(scopes) == 3
        assert len(users) == 10


# ---------------------------------------------------------------------------
# TestAdDnsZoneResourceType — AD-02 zone resource shape
# ---------------------------------------------------------------------------


class TestAdDnsZoneResourceType:
    """DNS zone CloudResource has correct provider, resource_type, ip_addresses."""

    def test_dns_zone_provider(self):
        """DNS zone CloudResource has provider='ad'."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        zones = [r for r in resources if r.resource_type == "ad-dns-zone"]
        assert all(z.provider == "ad" for z in zones)

    def test_dns_zone_resource_type(self):
        """DNS zone CloudResource has resource_type='ad-dns-zone'."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        zones = [r for r in resources if r.resource_type == "ad-dns-zone"]
        assert len(zones) > 0

    def test_dns_zone_no_ip_addresses(self):
        """DNS zone CloudResource has ip_addresses=[] (DDI-only, not an active IP)."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        zones = [r for r in resources if r.resource_type == "ad-dns-zone"]
        assert all(z.ip_addresses == [] for z in zones)


# ---------------------------------------------------------------------------
# TestAdDnsRecordResourceType — AD-02 record resource shape
# ---------------------------------------------------------------------------


class TestAdDnsRecordResourceType:
    """DNS record CloudResource has resource_type='ad-dns-record' with A/AAAA IPs."""

    def test_dns_record_resource_type(self):
        """DNS record CloudResource has resource_type='ad-dns-record'."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        records = [r for r in resources if r.resource_type == "ad-dns-record"]
        assert len(records) > 0

    def test_a_record_has_ip_addresses(self):
        """A record CloudResource has ip_addresses populated with the record IP."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        a_records = [
            r for r in resources
            if r.resource_type == "ad-dns-record"
            and r.details.get("record_type") == "A"
        ]
        assert len(a_records) > 0
        assert all(len(r.ip_addresses) == 1 for r in a_records)
        assert all(r.ip_addresses[0].startswith("10.") for r in a_records)


# ---------------------------------------------------------------------------
# TestAdDhcpScopeResourceType — AD-03 scope resource shape
# ---------------------------------------------------------------------------


class TestAdDhcpScopeResourceType:
    """DHCP scope CloudResource has resource_type='ad-dhcp-scope', ip_addresses=[]."""

    def test_dhcp_scope_resource_type(self):
        """DHCP scope CloudResource has resource_type='ad-dhcp-scope'."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        scopes = [r for r in resources if r.resource_type == "ad-dhcp-scope"]
        assert len(scopes) == 3

    def test_dhcp_scope_no_ip_addresses(self):
        """DHCP scope CloudResource has ip_addresses=[] (DDI-only)."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        scopes = [r for r in resources if r.resource_type == "ad-dhcp-scope"]
        assert all(s.ip_addresses == [] for s in scopes)


# ---------------------------------------------------------------------------
# TestAdDhcpIpCount — AD-03 DHCP IP representation
# ---------------------------------------------------------------------------


class TestAdDhcpIpCount:
    """DHCP lease/reservation IPs are represented in CloudResource objects."""

    def test_dhcp_ip_total_count(self):
        """Total DHCP IP count (leases + reservations) matches expected number.

        Mock data: 3 scopes, 12 leases + 3 reservations = 15 total IPs.
        Either as separate ad-dhcp-ip CloudResources (each with 1 IP),
        OR aggregated into scope ip_addresses lists (total count == 15).
        """
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        # Count total DHCP IPs across all representations
        dhcp_ips_resources = [r for r in resources if r.resource_type == "ad-dhcp-ip"]
        scope_ips = sum(
            len(r.ip_addresses)
            for r in resources if r.resource_type == "ad-dhcp-scope"
        )
        total_dhcp_ips = len(dhcp_ips_resources) + scope_ips
        # 12 leases + 3 reservations = 15 total IPs
        assert total_dhcp_ips == 15

    def test_dhcp_ip_resource_provider(self):
        """DHCP IP resources (if separate) have provider='ad'."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        dhcp_ip_resources = [r for r in resources if r.resource_type == "ad-dhcp-ip"]
        if dhcp_ip_resources:  # only if this shape is used
            assert all(r.provider == "ad" for r in dhcp_ip_resources)


# ---------------------------------------------------------------------------
# TestAdUserResourceType — AD-04 user resource shape
# ---------------------------------------------------------------------------


class TestAdUserResourceType:
    """AD user CloudResource has resource_type='ad-user' with sentinel IP."""

    def test_user_resource_type(self):
        """AD user CloudResource has resource_type='ad-user'."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        users = [r for r in resources if r.resource_type == "ad-user"]
        assert len(users) == 10

    def test_user_sentinel_ip(self):
        """AD user CloudResource has ip_addresses=['0.0.0.0'] (sentinel for asset count)."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        users = [r for r in resources if r.resource_type == "ad-user"]
        assert all(r.ip_addresses == ["0.0.0.0"] for r in users)

    def test_user_details_has_sid(self):
        """AD user CloudResource has details['sid'] populated with SID string."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            resources, _ = run_ad_analysis(opts)

        users = [r for r in resources if r.resource_type == "ad-user"]
        assert all("sid" in r.details for r in users)
        assert all(r.details["sid"].startswith("S-1-5-") for r in users)


# ---------------------------------------------------------------------------
# TestXlsReportProduced — AD-08 XLS output integration
# ---------------------------------------------------------------------------


class TestXlsReportProduced:
    """run_ad_analysis() with output_path calls write_xlsx_report with provider='ad'."""

    def test_xls_report_called_with_ad_provider(self):
        """run_ad_analysis(output_path=...) → write_xlsx_report called with provider='ad'."""
        opts = _make_opts()
        with patch("cloud_usage.providers.ad.MicrosoftAdCollector") as MockCollector, \
             patch("cloud_usage.providers.ad.write_xlsx_report") as mock_xls:
            MockCollector.return_value.collect_all.return_value = [_make_mock_collector_result()]
            run_ad_analysis(opts, output_path="/tmp/ad_test_report.xlsx")

        mock_xls.assert_called_once()
        call_kwargs = mock_xls.call_args.kwargs or {}
        call_args = mock_xls.call_args.args
        # provider="ad" should appear as kwarg or positional arg
        assert call_kwargs.get("provider") == "ad" or "ad" in call_args
