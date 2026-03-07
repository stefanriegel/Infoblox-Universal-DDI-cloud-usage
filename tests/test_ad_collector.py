"""TDD RED gate — Microsoft AD collector tests.

The module-level import below triggers ImportError/ModuleNotFoundError until
29-02/29-03 create the providers/ad package. This file defines the full
contract for MicrosoftAdCollector, AdOptions, and helper functions.

Requirements covered: AD-01 (WinRM), AD-02 (DNS), AD-03 (DHCP), AD-04 (Users),
AD-05 (auth modes), AD-06 (options/config), AD-07 (autodiscovery).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ---------------------------------------------------------------------------
# Module-level imports — these FAIL until 29-02 creates the AD provider package.
# ImportError/ModuleNotFoundError here is the RED gate signal.
# ---------------------------------------------------------------------------

from cloud_usage.providers.ad.collector import MicrosoftAdCollector  # noqa: E402
from cloud_usage.providers.ad.options import (  # noqa: E402
    AdOptions,
    normalize_ad_servers,
    normalize_ad_services,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SUPPORTED_DNS_RECORD_TYPES = {
    "A", "AAAA", "CNAME", "MX", "TXT", "CAA", "SRV",
    "SVCB", "HTTPS", "PTR", "NS", "SOA", "NAPTR",
}


def _make_opts(
    servers=None,
    services=("dns", "dhcp", "user"),
    auth_mode="kerberos",
    username=None,
    password=None,
    autodiscover=False,
    discovery_server=None,
):
    return AdOptions(
        servers=servers or ["dc1.corp.example.com"],
        services=services,
        auth_mode=auth_mode,
        username=username,
        password=password,
        autodiscover=autodiscover,
        discovery_server=discovery_server,
    )


def _make_zone_data(zone_name: str) -> dict:
    return {"ZoneName": zone_name}


def _make_a_record(hostname: str, ip: str) -> dict:
    return {
        "HostName": hostname,
        "RecordType": "A",
        "RecordData": {"IPv4Address": ip},
    }


def _make_aaaa_record(hostname: str, ipv6: str) -> dict:
    return {
        "HostName": hostname,
        "RecordType": "AAAA",
        "RecordData": {"IPv6Address": ipv6},
    }


def _make_scope_data(scope_id: str) -> dict:
    return {"ScopeId": scope_id, "Name": f"Scope-{scope_id}", "SubnetMask": "255.255.255.0"}


def _make_lease_data(ip: str, scope_id: str, mac: str = "00:11:22:33:44:55") -> dict:
    return {"IPAddress": ip, "ScopeId": scope_id, "ClientId": mac}


def _make_reservation_data(ip: str, scope_id: str, mac: str = "AA:BB:CC:DD:EE:FF") -> dict:
    return {"IPAddress": ip, "ScopeId": scope_id, "ClientId": mac}


def _make_user_data(sam: str, sid: str) -> dict:
    return {"SamAccountName": sam, "SID": {"Value": sid}}


# ---------------------------------------------------------------------------
# TestCollectDns — AD-02 contract
# ---------------------------------------------------------------------------


class TestCollectDns:
    """_collect_dns() returns zones + records + IPs with correct structure."""

    def test_collect_dns_zone_count(self):
        """_collect_dns() with 2 zones returns zone_keys len == 2."""
        collector = MicrosoftAdCollector(_make_opts())

        session = MagicMock()
        zones = [_make_zone_data("corp.example.com"), _make_zone_data("test.corp.example.com")]
        a_records_corp = [_make_a_record(f"host{i}", f"10.0.0.{i+1}") for i in range(3)]
        a_records_test = [_make_a_record(f"host{i}", f"10.0.1.{i+1}") for i in range(3)]

        # _collect_dns internally calls _run_ps_json: once for zones, once per zone
        collector._run_ps_json = MagicMock(
            side_effect=[zones, a_records_corp, a_records_test]
        )

        result = collector._collect_dns(session)
        assert len(result["zone_keys"]) == 2

    def test_collect_dns_record_entries(self):
        """_collect_dns() returns supported_record_entries for A records."""
        collector = MicrosoftAdCollector(_make_opts())

        session = MagicMock()
        zones = [_make_zone_data("corp.example.com")]
        records = [_make_a_record(f"h{i}", f"10.0.0.{i+1}") for i in range(3)]

        collector._run_ps_json = MagicMock(side_effect=[zones, records])

        result = collector._collect_dns(session)
        # 3 A records → 3 supported_record_entries
        assert len(result["record_keys"]) == 3

    def test_collect_dns_ip_extraction(self):
        """_collect_dns() extracts ip_addresses from A record data."""
        collector = MicrosoftAdCollector(_make_opts())

        session = MagicMock()
        zones = [_make_zone_data("corp.example.com")]
        records = [_make_a_record("www", "10.0.0.5")]

        collector._run_ps_json = MagicMock(side_effect=[zones, records])

        result = collector._collect_dns(session)
        assert "10.0.0.5" in result["ip_addresses"]

    def test_collect_dns_aaaa_ip_extraction(self):
        """_collect_dns() extracts IPv6 from AAAA record data."""
        collector = MicrosoftAdCollector(_make_opts())

        session = MagicMock()
        zones = [_make_zone_data("corp.example.com")]
        records = [_make_aaaa_record("ipv6host", "2001:db8::1")]

        collector._run_ps_json = MagicMock(side_effect=[zones, records])

        result = collector._collect_dns(session)
        assert "2001:db8::1" in result["ip_addresses"]


# ---------------------------------------------------------------------------
# TestCollectDhcp — AD-03 contract
# ---------------------------------------------------------------------------


class TestCollectDhcp:
    """_collect_dhcp() returns scopes + leases + reservations with correct counts."""

    def test_collect_dhcp_scope_count(self):
        """_collect_dhcp() with 2 scopes returns scope_keys len == 2."""
        collector = MicrosoftAdCollector(_make_opts())
        session = MagicMock()

        scopes = [_make_scope_data("192.168.1.0"), _make_scope_data("192.168.2.0")]
        leases_1 = [_make_lease_data(f"192.168.1.{i+10}", "192.168.1.0") for i in range(5)]
        leases_2 = [_make_lease_data(f"192.168.2.{i+10}", "192.168.2.0") for i in range(5)]
        reservations_1 = [_make_reservation_data(f"192.168.1.{i+200}", "192.168.1.0") for i in range(2)]
        reservations_2 = [_make_reservation_data(f"192.168.2.{i+200}", "192.168.2.0") for i in range(2)]

        collector._run_ps_json = MagicMock(
            side_effect=[scopes, leases_1, reservations_1, leases_2, reservations_2]
        )

        result = collector._collect_dhcp(session)
        assert len(result["scope_keys"]) == 2

    def test_collect_dhcp_lease_count(self):
        """_collect_dhcp() 5 leases x 2 scopes = lease_keys len 10."""
        collector = MicrosoftAdCollector(_make_opts())
        session = MagicMock()

        scopes = [_make_scope_data("192.168.1.0"), _make_scope_data("192.168.2.0")]
        leases_1 = [_make_lease_data(f"192.168.1.{i+10}", "192.168.1.0") for i in range(5)]
        leases_2 = [_make_lease_data(f"192.168.2.{i+10}", "192.168.2.0") for i in range(5)]
        reservations_1 = [_make_reservation_data(f"192.168.1.201", "192.168.1.0")]
        reservations_2 = [_make_reservation_data(f"192.168.2.201", "192.168.2.0")]

        collector._run_ps_json = MagicMock(
            side_effect=[scopes, leases_1, reservations_1, leases_2, reservations_2]
        )

        result = collector._collect_dhcp(session)
        assert len(result["lease_keys"]) == 10

    def test_collect_dhcp_reservation_count(self):
        """_collect_dhcp() 2 reservations x 2 scopes = reservation_keys len 4."""
        collector = MicrosoftAdCollector(_make_opts())
        session = MagicMock()

        scopes = [_make_scope_data("192.168.1.0"), _make_scope_data("192.168.2.0")]
        leases_1 = [_make_lease_data(f"192.168.1.{i+10}", "192.168.1.0") for i in range(5)]
        leases_2 = [_make_lease_data(f"192.168.2.{i+10}", "192.168.2.0") for i in range(5)]
        reservations_1 = [_make_reservation_data(f"192.168.1.{i+200}", "192.168.1.0") for i in range(2)]
        reservations_2 = [_make_reservation_data(f"192.168.2.{i+200}", "192.168.2.0") for i in range(2)]

        collector._run_ps_json = MagicMock(
            side_effect=[scopes, leases_1, reservations_1, leases_2, reservations_2]
        )

        result = collector._collect_dhcp(session)
        assert len(result["reservation_keys"]) == 4


# ---------------------------------------------------------------------------
# TestCollectUsers — AD-04 contract
# ---------------------------------------------------------------------------


class TestCollectUsers:
    """_collect_users() returns SID-keyed user dict with correct count."""

    def test_collect_users_count(self):
        """_collect_users() with 3 unique SIDs returns user_keys len == 3."""
        collector = MicrosoftAdCollector(_make_opts())
        session = MagicMock()

        users = [
            _make_user_data("user1", "S-1-5-21-100-200-300-1001"),
            _make_user_data("user2", "S-1-5-21-100-200-300-1002"),
            _make_user_data("user3", "S-1-5-21-100-200-300-1003"),
        ]
        collector._run_ps_json = MagicMock(return_value=users)

        result = collector._collect_users(session)
        assert len(result["user_keys"]) == 3


# ---------------------------------------------------------------------------
# TestCollectUsersSidDedup — AD-04 deduplication
# ---------------------------------------------------------------------------


class TestCollectUsersSidDedup:
    """_collect_users() deduplicates users by SID across calls."""

    def test_collect_users_sid_dedup(self):
        """Same SID returned twice → user_keys len == 1 (not 2)."""
        collector = MicrosoftAdCollector(_make_opts())
        session = MagicMock()

        duplicate_users = [
            _make_user_data("user1", "S-1-5-21-100-200-300-1001"),
            _make_user_data("user1_dup", "S-1-5-21-100-200-300-1001"),  # same SID
        ]
        collector._run_ps_json = MagicMock(return_value=duplicate_users)

        result = collector._collect_users(session)
        assert len(result["user_keys"]) == 1


# ---------------------------------------------------------------------------
# TestAutodiscover — AD-07 contract
# ---------------------------------------------------------------------------


class TestAutodiscover:
    """_resolve_targets() with autodiscover=True discovers DCs via seed server."""

    def test_autodiscover_returns_dc_targets(self):
        """_resolve_targets() returns DC hostnames from autodiscovery."""
        opts = _make_opts(
            autodiscover=True,
            discovery_server="seed.corp.example.com",
        )
        collector = MicrosoftAdCollector(opts)

        mock_session = MagicMock()
        # First PS call returns domains, second returns DC controllers
        collector._run_ps_json = MagicMock(
            side_effect=[
                [{"Name": "corp.example.com"}],               # domains
                [{"HostName": "dc1.corp.example.com"}],       # DCs
            ]
        )
        collector._build_session = MagicMock(return_value=mock_session)

        targets = collector._resolve_targets()
        dc_hostnames = [t["server"] for t in targets]
        assert "dc1.corp.example.com" in dc_hostnames

    def test_autodiscover_dc_includes_services(self):
        """Autodiscovered targets include dns and user services."""
        opts = _make_opts(
            autodiscover=True,
            discovery_server="seed.corp.example.com",
            services=("dns", "user"),
        )
        collector = MicrosoftAdCollector(opts)

        mock_session = MagicMock()
        collector._run_ps_json = MagicMock(
            side_effect=[
                [{"Name": "corp.example.com"}],
                [{"HostName": "dc1.corp.example.com"}],
            ]
        )
        collector._build_session = MagicMock(return_value=mock_session)

        targets = collector._resolve_targets()
        assert len(targets) > 0
        # Services should be included in target descriptors
        dc1_target = next(t for t in targets if "dc1" in t["server"])
        assert "dns" in dc1_target["services"] or "user" in dc1_target["services"]


# ---------------------------------------------------------------------------
# TestNtlmRequiresCredentials — AD-05 auth validation
# ---------------------------------------------------------------------------


class TestNtlmRequiresCredentials:
    """AdOptions with auth_mode='ntlm' requires username and password."""

    def test_ntlm_without_credentials_raises(self):
        """AdOptions(auth_mode='ntlm') without username/password → ValueError."""
        with pytest.raises(ValueError):
            AdOptions(
                servers=["dc1.corp.example.com"],
                services=("dns",),
                auth_mode="ntlm",
            )

    def test_ntlm_with_credentials_succeeds(self):
        """AdOptions(auth_mode='ntlm') with username+password → no ValueError."""
        opts = AdOptions(
            servers=["dc1.corp.example.com"],
            services=("dns",),
            auth_mode="ntlm",
            username="CORP\\admin",
            password="secret",
        )
        assert opts.auth_mode == "ntlm"
        assert opts.username == "CORP\\admin"


# ---------------------------------------------------------------------------
# TestKerberosNoCredentialsRequired — AD-05 kerberos
# ---------------------------------------------------------------------------


class TestKerberosNoCredentialsRequired:
    """AdOptions with auth_mode='kerberos' works without explicit credentials."""

    def test_kerberos_without_credentials_succeeds(self):
        """AdOptions(auth_mode='kerberos') without credentials → no ValueError."""
        opts = AdOptions(
            servers=["dc1.corp.example.com"],
            services=("dns",),
            auth_mode="kerberos",
        )
        assert opts.auth_mode == "kerberos"
        assert opts.username is None
        assert opts.password is None


# ---------------------------------------------------------------------------
# TestNormalizeAdServices — AD-06 helper validation
# ---------------------------------------------------------------------------


class TestNormalizeAdServices:
    """normalize_ad_services() parses and validates service list strings."""

    def test_normalize_dns_dhcp(self):
        """normalize_ad_services('dns,dhcp') → returns iterable containing 'dns' and 'dhcp'."""
        result = normalize_ad_services("dns,dhcp")
        assert "dns" in result
        assert "dhcp" in result

    def test_normalize_empty_raises(self):
        """normalize_ad_services('') → raises ValueError."""
        with pytest.raises(ValueError):
            normalize_ad_services("")

    def test_normalize_invalid_service_raises(self):
        """normalize_ad_services('bad') → raises ValueError."""
        with pytest.raises(ValueError):
            normalize_ad_services("bad")

    def test_normalize_all_valid_services(self):
        """normalize_ad_services('dns,dhcp,user') succeeds."""
        result = normalize_ad_services("dns,dhcp,user")
        assert "dns" in result
        assert "dhcp" in result
        assert "user" in result


# ---------------------------------------------------------------------------
# TestNormalizeAdServers — AD-06 server normalization
# ---------------------------------------------------------------------------


class TestNormalizeAdServers:
    """normalize_ad_servers() lowercases and deduplicates server list."""

    def test_normalize_lowercases_and_dedupes(self):
        """normalize_ad_servers with same server in mixed case → single lowercase entry."""
        result = normalize_ad_servers("DC1.CORP.EXAMPLE.COM,dc1.corp.example.com")
        assert result == ["dc1.corp.example.com"]

    def test_normalize_multiple_servers(self):
        """normalize_ad_servers with two distinct servers returns both lowercased."""
        result = normalize_ad_servers("DC1.CORP.EXAMPLE.COM,dc2.corp.example.com")
        assert "dc1.corp.example.com" in result
        assert "dc2.corp.example.com" in result


# ---------------------------------------------------------------------------
# TestDcFailureContinue — DC failure isolation (AD-01 / resilience)
# ---------------------------------------------------------------------------


class TestDcFailureContinue:
    """Collector continues when one DC fails — logs error, processes others."""

    def test_dc_failure_continue(self):
        """_collect_server() raises WinRMError for dc1 but dc2 succeeds.
        Result has dc1 status='error', dc2 status='ok'."""
        from cloud_usage.providers.ad.collector import WinRMError  # type: ignore

        opts = _make_opts(servers=["dc1.corp.example.com", "dc2.corp.example.com"])
        collector = MicrosoftAdCollector(opts)

        def mock_collect_server(server, session):
            if "dc1" in server:
                raise WinRMError("dc1 unreachable")
            return {"status": "ok", "dns": {}, "dhcp": {}, "users": {}}

        collector._collect_server = mock_collect_server
        collector._build_session = MagicMock()

        results = collector.collect_all()

        dc1_result = next(r for r in results if "dc1" in r["server"])
        dc2_result = next(r for r in results if "dc2" in r["server"])
        assert dc1_result["status"] == "error"
        assert dc2_result["status"] == "ok"


# ---------------------------------------------------------------------------
# TestAllDcsFail — all DCs fail (AD-01 / resilience)
# ---------------------------------------------------------------------------


class TestAllDcsFail:
    """run_ad_analysis() with all DCs failing returns empty resources + errors."""

    def test_all_dcs_fail_returns_empty_resources(self):
        """run_ad_analysis() where every DC raises → resources==[], errors non-empty."""
        from cloud_usage.providers.ad import run_ad_analysis  # type: ignore
        from cloud_usage.providers.ad.collector import WinRMError  # type: ignore

        opts = _make_opts(servers=["dc1.corp.example.com"])

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "cloud_usage.providers.ad.collector.MicrosoftAdCollector.collect_all",
                lambda self: [{"server": "dc1.corp.example.com", "status": "error",
                                "error": "WinRM connection failed"}],
            )
            resources, errors = run_ad_analysis(opts)

        assert resources == []
        assert len(errors) > 0
