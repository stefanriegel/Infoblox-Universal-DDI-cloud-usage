"""NIOS Grid per-member DDI/IP/Asset counter module.

Provides:
- MemberCounts: frozen dataclass with per-member DDI, Active IP, lease, and asset counts
- CountResult: frozen dataclass with member_counts list and grid_counts aggregate
- Formula constants: NIOS Object (50/25/13) and UDDI native (25/13/3) divisors
- Formula functions: nios_object_tokens() and uddi_native_tokens()
- count_objects(): single-pass counter returning CountResult from Iterator[NiosObject]

Design notes:
- Formula constants are defined only here — NOT imported from cloud_usage.shared.
- Active IP deduplication uses a single global set[str] collecting IPs from all four
  sources: active leases, fixed addresses, host addresses (raw_attrs['address'] key),
  and network reservations.
- Network reservations contribute both network_address and broadcast_address (via
  ipaddress.IPv4Network(cidr, strict=False) to tolerate host bits in CIDR strings).
- Lease state filter uses FilterConfig.lease_states; default = ("active",) per UDDI spec.
- Per-member active_ip_count = unique lease-derived IPs for that member only.
- grid_counts.active_ip_count = len(global_ip_set) — the global deduplication total.
- grid_counts member_hostname = "__grid__" sentinel to distinguish from real hostnames.
- HOST_OBJECT expands to +2 (A+PTR) or +3 (A+PTR+CNAME) based on non-empty "aliases"
  raw_attr. All other DDI families count as +1.
- NETWORK is both a DDI family (+1) AND contributes IPs (network + broadcast address).
- asset_count is always 0 in Phase 11; Phase 12 Scenario Engine fills it in.
- _MemberAcc is an internal mutable accumulator and is NOT exported.
"""

from __future__ import annotations

import ipaddress
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterator

from cloud_usage.nios.filter import FilterConfig
from cloud_usage.nios.schema import NiosFamily, NiosObject

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Formula constants
# ---------------------------------------------------------------------------

# NIOS Object formula: tokens = DDI/50 + IPs/25 + Assets/13
NIOS_DDI_DIVISOR: int = 50
NIOS_IP_DIVISOR: int = 25
NIOS_ASSET_DIVISOR: int = 13

# UDDI native formula: tokens = DDI/25 + IPs/13 + Assets/3
UDDI_DDI_DIVISOR: int = 25
UDDI_IP_DIVISOR: int = 13
UDDI_ASSET_DIVISOR: int = 3


def nios_object_tokens(ddi: int | float, ips: int | float, assets: int | float) -> float:
    """Compute NIOS Object token count from DDI, active IP, and asset counts.

    Formula: tokens = DDI / 50 + IPs / 25 + Assets / 13

    Args:
        ddi: Total DDI object count.
        ips: Total Active IP count.
        assets: Total asset count.

    Returns:
        Token count as a float.
    """
    return ddi / NIOS_DDI_DIVISOR + ips / NIOS_IP_DIVISOR + assets / NIOS_ASSET_DIVISOR


def uddi_native_tokens(ddi: int | float, ips: int | float, assets: int | float) -> float:
    """Compute UDDI native token count from DDI, active IP, and asset counts.

    Formula: tokens = DDI / 25 + IPs / 13 + Assets / 3

    Args:
        ddi: Total DDI object count.
        ips: Total Active IP count.
        assets: Total asset count.

    Returns:
        Token count as a float.
    """
    return ddi / UDDI_DDI_DIVISOR + ips / UDDI_IP_DIVISOR + assets / UDDI_ASSET_DIVISOR


# ---------------------------------------------------------------------------
# DDI family sets
# ---------------------------------------------------------------------------

# All 17 families that contribute to DDI count (including HOST_OBJECT and HOST_ALIAS
# which have special counting rules). NETWORK is included — it counts +1 toward DDI
# AND contributes IPs (network_address + broadcast_address) to the global IP set.
_DDI_FAMILIES: frozenset[str] = frozenset({
    NiosFamily.DNS_RECORD_A,
    NiosFamily.DNS_RECORD_AAAA,
    NiosFamily.DNS_RECORD_CNAME,
    NiosFamily.DNS_RECORD_MX,
    NiosFamily.DNS_RECORD_NS,
    NiosFamily.DNS_RECORD_PTR,
    NiosFamily.DNS_RECORD_SOA,
    NiosFamily.DNS_RECORD_SRV,
    NiosFamily.DNS_RECORD_TXT,
    NiosFamily.HOST_OBJECT,
    NiosFamily.HOST_ALIAS,
    NiosFamily.DNS_ZONE,
    NiosFamily.DHCP_RANGE,
    NiosFamily.EXCLUSION_RANGE,
    NiosFamily.NETWORK,
    NiosFamily.NETWORK_CONTAINER,
    NiosFamily.NETWORK_VIEW,
    NiosFamily.DTC_LBDN,
    NiosFamily.DTC_POOL,
    NiosFamily.DTC_SERVER,
    NiosFamily.DTC_MONITOR,
    NiosFamily.DTC_TOPOLOGY,
})


# ---------------------------------------------------------------------------
# Public output dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MemberCounts:
    """Per-member (or grid-level) counts for DDI objects, Active IPs, and leases.

    For member entries: member_hostname is the FQDN of the NIOS grid member.
    For the grid-level aggregate: member_hostname = "__grid__" sentinel.

    Args:
        member_hostname: FQDN of the member, or "__grid__" for grid-level totals.
        ddi_count: Total DDI object count attributed to this member.
        active_ip_count: Unique active IP count.
            Per-member: lease-derived IPs only (binding_state in lease_states).
            Grid (__grid__): len(global_ip_set) across all four sources.
        lease_count: Raw LEASE object row count (all binding_states, not filtered).
        asset_count: Always 0 in Phase 11; Phase 12 Scenario Engine fills this in.
    """

    member_hostname: str
    ddi_count: int
    active_ip_count: int
    lease_count: int
    asset_count: int


@dataclass(frozen=True)
class CountResult:
    """Result of count_objects(): per-member counts and grid-level totals.

    Args:
        member_counts: One MemberCounts entry per unique member_hostname from LEASE
            objects. Members with no LEASE attribution do not appear here.
        grid_counts: Grid-level aggregate: member_hostname="__grid__", ddi_count from
            grid-level objects (member_hostname=None), active_ip_count = len(global_ip_set),
            lease_count = total raw lease rows across all members.
        per_family_ddi: DDI-adjusted contribution per family across the whole grid.
            Keyed by NiosFamily constant string (e.g. "host_object").
            HOST_OBJECT entries reflect the +2/+3 expansion (not raw object count).
            Only DDI families appear as keys; non-DDI families are absent.
            sum(per_family_ddi.values()) == total grid + member DDI (the scenario total_ddi).
        ip_by_type: Per-source IP counts with keys "leases", "fixed", "host",
            "reservations". Raw (potentially overlapping) counts — accumulated inline
            alongside the global_ip_set in count_objects(), eliminating a separate pass.
            leases: state-filtered active lease IPs (non-empty ip_address).
            fixed: FIXED_ADDRESS objects with non-empty ip_address.
            host: HOST_ADDRESS objects with non-empty "address" key.
            reservations: 2 * number of valid NETWORK CIDRs (network + broadcast).
    """

    member_counts: list[MemberCounts]
    grid_counts: MemberCounts
    per_family_ddi: dict[str, int] = field(default_factory=dict)
    ip_by_type: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Internal mutable accumulator (NOT exported)
# ---------------------------------------------------------------------------

@dataclass
class _MemberAcc:
    """Internal mutable accumulator for per-member counts during single-pass traversal."""

    ddi_count: int = 0
    lease_ip_set: set = field(default_factory=set)  # per-member lease IPs (state-filtered)
    lease_count: int = 0  # raw lease rows (all binding_states)


# ---------------------------------------------------------------------------
# Public counting function
# ---------------------------------------------------------------------------

def count_objects(
    objects: Iterator[NiosObject],
    config: FilterConfig,
) -> CountResult:
    """Count DDI objects, Active IPs, and leases from a stream of NiosObject instances.

    Performs a single-pass traversal of the stream to compute:
    - Per-member DDI count (from LEASE-attributed objects only in Phase 11, since only
      LEASE has member_hostname != None in the ZF reference backup)
    - Global Active IP count across all four sources (lease, fixed_address, host_address,
      network reservations), deduplicated via a single set[str]
    - Per-member Active IP count (lease-derived IPs only, filtered by lease_states)
    - Raw lease row counts (all binding_states, not filtered)

    Args:
        objects: Iterator of NiosObject instances, typically from filter_objects() output.
        config: FilterConfig providing lease_states for binding_state filtering.

    Returns:
        CountResult with member_counts (one per LEASE-attributed member) and
        grid_counts (member_hostname="__grid__", global totals).
    """
    lease_states_set: set[str] = set(config.lease_states)

    # Single global IP set for deduplication across all four Active IP sources.
    global_ip_set: set[str] = set()

    # Per-member accumulators (keyed by member_hostname).
    per_member: dict[str, _MemberAcc] = defaultdict(_MemberAcc)

    # Grid-level DDI count (objects with member_hostname=None).
    grid_ddi: int = 0

    # Total raw lease count across all members (before binding_state filter).
    grid_lease_count: int = 0

    # Per-family DDI-adjusted contributions (DDI families only, HOST_OBJECT uses expanded delta).
    per_family_ddi: dict[str, int] = defaultdict(int)

    # Per-source IP counters (raw, potentially overlapping — same conditions as global_ip_set
    # but without deduplication, matching _count_ip_by_type() behaviour).
    ip_leases: int = 0
    ip_fixed: int = 0
    ip_host: int = 0
    ip_reservations: int = 0

    for obj in objects:
        family = obj.family
        hostname = obj.member_hostname
        attrs = obj.raw_attrs

        # --- DDI counting ---
        if family in _DDI_FAMILIES:
            if family == NiosFamily.HOST_OBJECT:
                # Expand HOST_OBJECT: +2 (A+PTR) or +3 (A+PTR+CNAME if aliases present).
                aliases = attrs.get("aliases", "").strip()
                delta = 3 if aliases else 2
            else:
                delta = 1

            # Accumulate per-family DDI contribution (grid-wide, regardless of member attribution).
            per_family_ddi[family] += delta

            if hostname is None:
                grid_ddi += delta
            else:
                per_member[hostname].ddi_count += delta

        # --- Lease counting and per-member IP attribution ---
        if family == NiosFamily.LEASE:
            state = attrs.get("binding_state", "")
            ip = attrs.get("ip_address", "").strip()

            # Always count raw lease rows.
            grid_lease_count += 1
            if hostname:
                per_member[hostname].lease_count += 1

            # State-filtered: contribute to global and per-member IP sets.
            if state in lease_states_set and ip:
                global_ip_set.add(ip)
                ip_leases += 1
                if hostname:
                    per_member[hostname].lease_ip_set.add(ip)

        # --- Fixed address IPs (grid-level, no member attribution) ---
        elif family == NiosFamily.FIXED_ADDRESS:
            ip = attrs.get("ip_address", "").strip()
            if ip:
                global_ip_set.add(ip)
                ip_fixed += 1

        # --- Host address IPs (grid-level; ZF backup stores IP under "address" key) ---
        elif family == NiosFamily.HOST_ADDRESS:
            # ZF backup stores host record IPs under "address" key, not "ip_address"
            ip = attrs.get("address", "").strip()
            if ip:
                global_ip_set.add(ip)
                ip_host += 1

        # --- Network reservation IPs (network_address + broadcast_address) ---
        elif family == NiosFamily.NETWORK:
            cidr = attrs.get("cidr", "").strip()
            if cidr:
                try:
                    net = ipaddress.IPv4Network(cidr, strict=False)
                    global_ip_set.add(str(net.network_address))
                    global_ip_set.add(str(net.broadcast_address))
                    ip_reservations += 2
                except ValueError:
                    # Malformed CIDR — skip silently.
                    _logger.debug("Skipping malformed CIDR %r in NETWORK object", cidr)

    # --- Build result ---
    member_counts = [
        MemberCounts(
            member_hostname=hostname,
            ddi_count=acc.ddi_count,
            active_ip_count=len(acc.lease_ip_set),
            lease_count=acc.lease_count,
            asset_count=0,
        )
        for hostname, acc in per_member.items()
    ]

    grid_counts = MemberCounts(
        member_hostname="__grid__",
        ddi_count=grid_ddi,
        active_ip_count=len(global_ip_set),
        lease_count=grid_lease_count,
        asset_count=0,
    )

    return CountResult(
        member_counts=member_counts,
        grid_counts=grid_counts,
        per_family_ddi=dict(per_family_ddi),
        ip_by_type={"leases": ip_leases, "fixed": ip_fixed, "host": ip_host, "reservations": ip_reservations},
    )
