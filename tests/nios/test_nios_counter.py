"""TDD tests for count_objects(), CountResult, MemberCounts — all COUNT-01 through COUNT-06 behaviors.

Tests use in-memory NiosObject construction (no .tar.gz fixtures needed).
count_objects() takes Iterator[NiosObject], not a path.
"""

from __future__ import annotations

import ast
import pathlib
import sys
from pathlib import Path
from typing import Iterator

import pytest

# Add src/ to path so cloud_usage is importable (mirrors existing test convention).
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# These will fail with ImportError until counter.py is implemented (RED phase).
from cloud_usage.nios.counter import (
    count_objects,
    CountResult,
    MemberCounts,
    NIOS_DDI_DIVISOR,
    NIOS_IP_DIVISOR,
    NIOS_ASSET_DIVISOR,
    UDDI_DDI_DIVISOR,
    UDDI_IP_DIVISOR,
    UDDI_ASSET_DIVISOR,
    nios_object_tokens,
    uddi_native_tokens,
)
from cloud_usage.nios.filter import FilterConfig
from cloud_usage.nios.schema import NiosObject, NiosFamily


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _obj(family: str, member: str | None = None, **attrs: str) -> NiosObject:
    """Build a NiosObject directly for counter testing."""
    return NiosObject(family=family, member_hostname=member, raw_attrs=dict(attrs))


def _lease(
    member: str | None,
    ip: str = "10.0.0.1",
    binding_state: str = "active",
) -> NiosObject:
    """Build a LEASE NiosObject attributed to a specific member."""
    return _obj(NiosFamily.LEASE, member=member, ip_address=ip, binding_state=binding_state)


def _fixed(ip: str) -> NiosObject:
    """Build a FIXED_ADDRESS grid-level object."""
    return _obj(NiosFamily.FIXED_ADDRESS, member=None, ip_address=ip)


def _host_addr(ip: str) -> NiosObject:
    """Build a HOST_ADDRESS grid-level object (uses 'address' key per ZF backup)."""
    return _obj(NiosFamily.HOST_ADDRESS, member=None, address=ip)


def _network(cidr: str) -> NiosObject:
    """Build a NETWORK grid-level object."""
    return _obj(NiosFamily.NETWORK, member=None, cidr=cidr)


def _host_addr_real(ip: str) -> NiosObject:
    """Build a HOST_ADDRESS with 'address' key (as ZF backup stores them)."""
    return _obj(NiosFamily.HOST_ADDRESS, member=None, address=ip)


def _default_config() -> FilterConfig:
    """Default FilterConfig with active-only lease states (per UDDI spec)."""
    return FilterConfig(whitelist=(), blacklist=(), lease_states=("active",))


# ---------------------------------------------------------------------------
# COUNT-01: DDI families are counted
# ---------------------------------------------------------------------------

def test_ddi_families_counted():
    """All 16 DDI-counted families (except HOST_OBJECT) each produce +1 per object."""
    # DNS record families (9 types)
    ddi_objects = [
        _obj(NiosFamily.DNS_RECORD_A, member=None),
        _obj(NiosFamily.DNS_RECORD_AAAA, member=None),
        _obj(NiosFamily.DNS_RECORD_CNAME, member=None),
        _obj(NiosFamily.DNS_RECORD_MX, member=None),
        _obj(NiosFamily.DNS_RECORD_NS, member=None),
        _obj(NiosFamily.DNS_RECORD_PTR, member=None),
        _obj(NiosFamily.DNS_RECORD_SOA, member=None),
        _obj(NiosFamily.DNS_RECORD_SRV, member=None),
        _obj(NiosFamily.DNS_RECORD_TXT, member=None),
        # Other DDI families
        _obj(NiosFamily.HOST_ALIAS, member=None),
        _obj(NiosFamily.DNS_ZONE, member=None),
        _obj(NiosFamily.DHCP_RANGE, member=None),
        _obj(NiosFamily.EXCLUSION_RANGE, member=None),
        _obj(NiosFamily.NETWORK_CONTAINER, member=None),
        _obj(NiosFamily.NETWORK_VIEW, member=None),
        # NETWORK: DDI-counted AND contributes active IPs
        _obj(NiosFamily.NETWORK, member=None, cidr="10.99.0.0/24"),
    ]
    config = _default_config()
    result = count_objects(iter(ddi_objects), config)
    # 16 DDI objects, each +1 → grid_counts.ddi_count == 16
    assert result.grid_counts.ddi_count == 16


def test_non_ddi_families_not_counted():
    """MEMBER, LEASE, FIXED_ADDRESS, HOST_ADDRESS do NOT count toward DDI."""
    objects = [
        _obj(NiosFamily.MEMBER, member=None),
        _lease("member-01.example.com", ip="10.0.0.1"),
        _fixed("10.0.0.2"),
        _host_addr("10.0.0.3"),
    ]
    config = _default_config()
    result = count_objects(iter(objects), config)
    # None of these contribute to DDI
    assert result.grid_counts.ddi_count == 0
    # Member-level lease also has 0 DDI
    member_counts = {m.member_hostname: m for m in result.member_counts}
    if "member-01.example.com" in member_counts:
        assert member_counts["member-01.example.com"].ddi_count == 0


# ---------------------------------------------------------------------------
# COUNT-01: HOST_OBJECT expansion (+2 or +3)
# ---------------------------------------------------------------------------

def test_host_object_expansion_no_aliases():
    """HOST_OBJECT without aliases contributes +2 (A record + PTR record)."""
    objects = [
        _obj(NiosFamily.HOST_OBJECT, member=None, name="host1.example.com"),
    ]
    config = _default_config()
    result = count_objects(iter(objects), config)
    assert result.grid_counts.ddi_count == 2


def test_host_object_expansion_with_aliases():
    """HOST_OBJECT with non-empty 'aliases' contributes +3 (A + PTR + CNAME)."""
    objects = [
        _obj(NiosFamily.HOST_OBJECT, member=None, name="host1.example.com", aliases="alias1.example.com"),
    ]
    config = _default_config()
    result = count_objects(iter(objects), config)
    assert result.grid_counts.ddi_count == 3


def test_host_object_expansion_empty_aliases_is_two():
    """HOST_OBJECT with empty 'aliases' string contributes +2 (not +3)."""
    objects = [
        _obj(NiosFamily.HOST_OBJECT, member=None, name="host1.example.com", aliases=""),
    ]
    config = _default_config()
    result = count_objects(iter(objects), config)
    assert result.grid_counts.ddi_count == 2


def test_host_object_expansion_whitespace_aliases_is_two():
    """HOST_OBJECT with whitespace-only 'aliases' contributes +2."""
    objects = [
        _obj(NiosFamily.HOST_OBJECT, member=None, name="host1.example.com", aliases="   "),
    ]
    config = _default_config()
    result = count_objects(iter(objects), config)
    assert result.grid_counts.ddi_count == 2


def test_multiple_host_objects():
    """Multiple HOST_OBJECT entries accumulate correctly."""
    objects = [
        _obj(NiosFamily.HOST_OBJECT, member=None, name="host1.example.com"),           # +2
        _obj(NiosFamily.HOST_OBJECT, member=None, name="host2.example.com", aliases="alias.example.com"),  # +3
        _obj(NiosFamily.HOST_OBJECT, member=None, name="host3.example.com"),           # +2
    ]
    config = _default_config()
    result = count_objects(iter(objects), config)
    assert result.grid_counts.ddi_count == 7  # 2 + 3 + 2


# ---------------------------------------------------------------------------
# COUNT-02: Active IP global deduplication
# ---------------------------------------------------------------------------

def test_active_ip_deduplication():
    """Same IP from multiple sources is counted only once in global set."""
    objects = [
        _lease("member-01.example.com", ip="10.0.0.1", binding_state="active"),
        _fixed("10.0.0.1"),         # same IP as lease
        _host_addr("10.0.0.1"),     # same IP again
        _lease("member-02.example.com", ip="10.0.0.2", binding_state="active"),
    ]
    config = _default_config()
    result = count_objects(iter(objects), config)
    # 10.0.0.1 from 3 sources → counted once; 10.0.0.2 → 1 unique IP = total 2
    assert result.grid_counts.active_ip_count == 2


def test_active_ip_from_all_four_sources():
    """All four IP sources contribute to the global IP set."""
    objects = [
        _lease("member-01.example.com", ip="10.0.1.1", binding_state="active"),
        _fixed("10.0.2.1"),
        _host_addr("10.0.3.1"),
        _network("10.0.4.0/30"),  # network + broadcast: 10.0.4.0 and 10.0.4.3
    ]
    config = _default_config()
    result = count_objects(iter(objects), config)
    # 10.0.1.1 (lease) + 10.0.2.1 (fixed) + 10.0.3.1 (host_addr via 'address' key)
    # + 10.0.4.0 (network) + 10.0.4.3 (broadcast) = 5 unique IPs
    assert result.grid_counts.active_ip_count == 5


def test_host_address_uses_address_key():
    """HOST_ADDRESS Active IP uses raw_attrs['address'] key, not 'ip_address'."""
    objects = [
        # With correct 'address' key — should be counted
        _obj(NiosFamily.HOST_ADDRESS, member=None, address="10.1.1.1"),
        # With wrong 'ip_address' key — should NOT be counted (0 contribution)
        _obj(NiosFamily.HOST_ADDRESS, member=None, ip_address="10.1.1.2"),
    ]
    config = FilterConfig(whitelist=(), blacklist=(), lease_states=("active",))
    result = count_objects(iter(objects), config)
    # Only the object with 'address' key contributes; 10.1.1.2 is NOT counted
    assert result.grid_counts.active_ip_count == 1


# ---------------------------------------------------------------------------
# COUNT-02: Network reservation IPs
# ---------------------------------------------------------------------------

def test_network_reservation_ips():
    """NETWORK with cidr adds network_address and broadcast_address to global set."""
    objects = [_network("10.0.1.0/24")]
    config = _default_config()
    result = count_objects(iter(objects), config)
    # 10.0.1.0 (network) + 10.0.1.255 (broadcast) = 2 unique IPs
    assert result.grid_counts.active_ip_count == 2


def test_network_reservation_host_bits_set():
    """NETWORK with host bits set in CIDR normalises to network_address + broadcast_address."""
    objects = [_network("10.0.0.5/24")]  # host bits set; strict=False normalises
    config = _default_config()
    result = count_objects(iter(objects), config)
    # normalises to 10.0.0.0/24 → 10.0.0.0 + 10.0.0.255 = 2 unique IPs
    assert result.grid_counts.active_ip_count == 2


def test_network_reservation_slash32():
    """NETWORK with /32 CIDR: network_address == broadcast_address → 1 unique IP."""
    objects = [_network("10.0.0.1/32")]
    config = _default_config()
    result = count_objects(iter(objects), config)
    # /32: network_address == broadcast_address == 10.0.0.1 → 1 unique IP
    assert result.grid_counts.active_ip_count == 1


def test_network_without_cidr_skipped():
    """NETWORK object without cidr attribute is silently skipped (no crash)."""
    objects = [_obj(NiosFamily.NETWORK, member=None)]  # no cidr key
    config = _default_config()
    result = count_objects(iter(objects), config)
    # No IPs added; NETWORK still counts +1 toward DDI
    assert result.grid_counts.active_ip_count == 0
    assert result.grid_counts.ddi_count == 1  # NETWORK is a DDI family


def test_network_malformed_cidr_skipped():
    """NETWORK with malformed CIDR is silently skipped."""
    objects = [_obj(NiosFamily.NETWORK, member=None, cidr="not-a-cidr")]
    config = _default_config()
    result = count_objects(iter(objects), config)
    assert result.grid_counts.active_ip_count == 0


# ---------------------------------------------------------------------------
# COUNT-03: Lease state filter
# ---------------------------------------------------------------------------

def test_default_lease_state_filter():
    """Default config (active, static) counts active and static leases, excludes others."""
    objects = [
        _lease("member-01.example.com", ip="10.0.0.1", binding_state="active"),
        _lease("member-01.example.com", ip="10.0.0.2", binding_state="static"),
        _lease("member-01.example.com", ip="10.0.0.3", binding_state="free"),
        _lease("member-01.example.com", ip="10.0.0.4", binding_state="abandoned"),
        _lease("member-01.example.com", ip="10.0.0.5", binding_state="backup"),
    ]
    config = FilterConfig(whitelist=(), blacklist=(), lease_states=("active", "static"))
    result = count_objects(iter(objects), config)
    # Only active (10.0.0.1) and static (10.0.0.2) contribute to global IP set
    assert result.grid_counts.active_ip_count == 2


def test_custom_lease_states():
    """Custom lease_states=("active", "static", "backup") includes backup leases."""
    objects = [
        _lease("member-01.example.com", ip="10.0.0.1", binding_state="active"),
        _lease("member-01.example.com", ip="10.0.0.2", binding_state="backup"),
        _lease("member-01.example.com", ip="10.0.0.3", binding_state="free"),
    ]
    config = FilterConfig(whitelist=(), blacklist=(), lease_states=("active", "static", "backup"))
    result = count_objects(iter(objects), config)
    # active (10.0.0.1) and backup (10.0.0.2) included; free excluded
    assert result.grid_counts.active_ip_count == 2


def test_lease_count_is_raw_rows():
    """lease_count tracks all LEASE objects regardless of binding_state filter."""
    objects = [
        _lease("member-01.example.com", ip="10.0.0.1", binding_state="active"),
        _lease("member-01.example.com", ip="10.0.0.2", binding_state="free"),
        _lease("member-01.example.com", ip="10.0.0.3", binding_state="abandoned"),
    ]
    config = FilterConfig(whitelist=(), blacklist=(), lease_states=("active",))
    result = count_objects(iter(objects), config)
    member_counts = {m.member_hostname: m for m in result.member_counts}
    member = member_counts["member-01.example.com"]
    # All 3 leases counted as raw rows
    assert member.lease_count == 3
    # But only 1 active lease contributes to active_ip_count
    assert member.active_ip_count == 1


# ---------------------------------------------------------------------------
# COUNT-04: UDDI native formula constants
# ---------------------------------------------------------------------------

def test_uddi_native_formula_constants():
    """UDDI divisors: DDI=25, IP=13, Assets=3."""
    assert UDDI_DDI_DIVISOR == 25
    assert UDDI_IP_DIVISOR == 13
    assert UDDI_ASSET_DIVISOR == 3


def test_uddi_native_tokens_formula():
    """uddi_native_tokens(ddi=25, ips=13, assets=3) == 3.0."""
    result = uddi_native_tokens(ddi=25, ips=13, assets=3)
    assert result == pytest.approx(3.0)


def test_uddi_native_tokens_partial():
    """uddi_native_tokens with typical values returns correct sum."""
    result = uddi_native_tokens(ddi=50, ips=26, assets=0)
    expected = 50 / 25 + 26 / 13 + 0 / 3
    assert result == pytest.approx(expected)


# ---------------------------------------------------------------------------
# COUNT-05: NIOS Object formula constants
# ---------------------------------------------------------------------------

def test_nios_object_formula_constants():
    """NIOS Object divisors: DDI=50, IP=25, Assets=13."""
    assert NIOS_DDI_DIVISOR == 50
    assert NIOS_IP_DIVISOR == 25
    assert NIOS_ASSET_DIVISOR == 13


def test_nios_object_tokens_formula():
    """nios_object_tokens(ddi=50, ips=25, assets=13) == 3.0."""
    result = nios_object_tokens(ddi=50, ips=25, assets=13)
    assert result == pytest.approx(3.0)


def test_nios_object_tokens_partial():
    """nios_object_tokens with typical values returns correct sum."""
    result = nios_object_tokens(ddi=100, ips=50, assets=0)
    expected = 100 / 50 + 50 / 25 + 0 / 13
    assert result == pytest.approx(expected)


# ---------------------------------------------------------------------------
# COUNT-06: CountResult structure
# ---------------------------------------------------------------------------

def test_count_result_structure():
    """count_objects() returns CountResult with member_counts + grid_counts."""
    objects = [
        _lease("member-01.example.com", ip="10.0.0.1", binding_state="active"),
        _lease("member-02.example.com", ip="10.0.0.2", binding_state="active"),
        _obj(NiosFamily.DNS_RECORD_A, member=None),   # grid-level DDI
    ]
    config = _default_config()
    result = count_objects(iter(objects), config)

    # result must be CountResult
    assert isinstance(result, CountResult)

    # grid_counts: member_hostname="__grid__"
    assert result.grid_counts.member_hostname == "__grid__"
    assert result.grid_counts.ddi_count == 1  # DNS_RECORD_A
    # active_ip_count is len(global_ip_set): 10.0.0.1 + 10.0.0.2 = 2
    assert result.grid_counts.active_ip_count == 2

    # member_counts: one entry per unique LEASE-attributed member
    member_hostnames = {m.member_hostname for m in result.member_counts}
    assert "member-01.example.com" in member_hostnames
    assert "member-02.example.com" in member_hostnames


def test_member_counts_asset_count_zero():
    """MemberCounts.asset_count is always 0 in Phase 11."""
    objects = [
        _lease("member-01.example.com", ip="10.0.0.1", binding_state="active"),
    ]
    config = _default_config()
    result = count_objects(iter(objects), config)
    for member in result.member_counts:
        assert member.asset_count == 0
    assert result.grid_counts.asset_count == 0


def test_grid_counts_lease_count_is_total():
    """grid_counts.lease_count = total raw lease count across all members."""
    objects = [
        _lease("member-01.example.com", ip="10.0.0.1", binding_state="active"),
        _lease("member-01.example.com", ip="10.0.0.2", binding_state="free"),
        _lease("member-02.example.com", ip="10.0.0.3", binding_state="active"),
    ]
    config = _default_config()
    result = count_objects(iter(objects), config)
    # 3 total raw lease rows (binding_state filter does not affect raw count)
    assert result.grid_counts.lease_count == 3


def test_empty_stream_returns_empty_result():
    """Empty stream returns CountResult with zero counts and empty member_counts."""
    config = _default_config()
    result = count_objects(iter([]), config)
    assert isinstance(result, CountResult)
    assert result.member_counts == []
    assert result.grid_counts.member_hostname == "__grid__"
    assert result.grid_counts.ddi_count == 0
    assert result.grid_counts.active_ip_count == 0
    assert result.grid_counts.lease_count == 0


def test_per_member_lease_active_ip_count():
    """Per-member active_ip_count reflects lease-derived IPs for that member only."""
    objects = [
        _lease("member-01.example.com", ip="10.0.0.1", binding_state="active"),
        _lease("member-01.example.com", ip="10.0.0.2", binding_state="active"),
        _lease("member-02.example.com", ip="10.0.0.3", binding_state="active"),
        # Fixed addresses contribute to global but not per-member
        _fixed("10.0.0.4"),
    ]
    config = _default_config()
    result = count_objects(iter(objects), config)
    member_counts = {m.member_hostname: m for m in result.member_counts}

    # member-01 has 2 unique lease IPs
    assert member_counts["member-01.example.com"].active_ip_count == 2
    # member-02 has 1 unique lease IP
    assert member_counts["member-02.example.com"].active_ip_count == 1
    # global IP set: 10.0.0.1, 10.0.0.2, 10.0.0.3, 10.0.0.4 = 4
    assert result.grid_counts.active_ip_count == 4


def test_member_counts_is_frozen():
    """MemberCounts and CountResult must be frozen dataclasses."""
    mc = MemberCounts(
        member_hostname="test.example.com",
        ddi_count=0,
        active_ip_count=0,
        lease_count=0,
        asset_count=0,
    )
    with pytest.raises((AttributeError, TypeError)):
        mc.ddi_count = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# COUNT-06: Formula constants not from shared/
# ---------------------------------------------------------------------------

def test_formula_constants_not_from_shared():
    """counter.py must not import from cloud_usage.shared or cloud_usage.counting."""
    counter_src = pathlib.Path("src/cloud_usage/nios/counter.py").read_text()
    tree = ast.parse(counter_src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "cloud_usage.shared" not in alias.name, (
                    f"Unexpected import from cloud_usage.shared: {alias.name}"
                )
                assert "cloud_usage.counting" not in alias.name, (
                    f"Unexpected import from cloud_usage.counting: {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert "cloud_usage.shared" not in node.module, (
                    f"Unexpected import from cloud_usage.shared: {node.module}"
                )
                assert "cloud_usage.counting" not in node.module, (
                    f"Unexpected import from cloud_usage.counting: {node.module}"
                )


# ---------------------------------------------------------------------------
# DTC Counter Tests (Phase 16: DTC-06, DTC-07)
# ---------------------------------------------------------------------------


def test_count_objects_dtc_families_count_ddi_plus_one() -> None:
    """Each DTC family object counts exactly +1 toward grid DDI (DTC-06).

    DTC objects use the existing delta=1 path in count_objects() — no special
    expansion logic like HOST_OBJECT (+2/+3).
    """
    dtc_families = [
        NiosFamily.DTC_LBDN,
        NiosFamily.DTC_POOL,
        NiosFamily.DTC_SERVER,
        NiosFamily.DTC_MONITOR,
        NiosFamily.DTC_TOPOLOGY,
    ]
    for family in dtc_families:
        obj = _obj(family, member=None)
        result = count_objects(iter([obj]), _default_config())
        assert result.grid_counts.ddi_count == 1, (
            f"{family}: expected ddi_count=1, got {result.grid_counts.ddi_count}"
        )
        assert result.member_counts == [], (
            f"{family}: expected no member rows, got {result.member_counts}"
        )


def test_count_objects_dtc_all_five_families() -> None:
    """One object per DTC family yields grid_counts.ddi_count==5, member_counts=[] (DTC-06, DTC-07)."""
    objects = [
        _obj(NiosFamily.DTC_LBDN, member=None),
        _obj(NiosFamily.DTC_POOL, member=None),
        _obj(NiosFamily.DTC_SERVER, member=None),
        _obj(NiosFamily.DTC_MONITOR, member=None),
        _obj(NiosFamily.DTC_TOPOLOGY, member=None),
    ]
    result = count_objects(iter(objects), _default_config())

    assert result.grid_counts.ddi_count == 5, (
        f"Expected ddi_count=5, got {result.grid_counts.ddi_count}"
    )
    assert result.member_counts == [], (
        f"Expected no member rows, got {result.member_counts}"
    )


def test_count_objects_dtc_does_not_produce_member_rows() -> None:
    """DTC objects never appear in member_counts, even in a mixed stream (DTC-07).

    DTC objects are grid-level (member_hostname=None). The counter only creates
    member_counts entries from LEASE objects with non-None member_hostname.
    """
    # Mix: one LEASE (creates a member row) + one DTC object (grid-level only)
    objects = [
        _lease(member="ns1.example.com", ip="10.0.0.1"),
        _obj(NiosFamily.DTC_LBDN, member=None),
    ]
    result = count_objects(iter(objects), _default_config())

    # DTC does not contribute to any member row
    assert len(result.member_counts) == 1, (
        f"Expected 1 member row (for LEASE), got {len(result.member_counts)}"
    )
    member_hostnames = {mc.member_hostname for mc in result.member_counts}
    assert "ns1.example.com" in member_hostnames

    # Grid DDI: DTC_LBDN (+1) — LEASE is not a DDI family
    assert result.grid_counts.ddi_count == 1, (
        f"Expected grid ddi_count=1 (DTC_LBDN), got {result.grid_counts.ddi_count}"
    )
