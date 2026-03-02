"""NIOS Grid licensing scenario computation module.

Provides:
- MigrationSplitConfig: frozen dataclass specifying member-to-group assignments
- ScenarioResult: frozen dataclass with per-scenario token computation output
- HybridScenarioResult: frozen dataclass with NIOS-remaining and NIOSX-migrated sub-totals
- MemberScenarioRow: frozen dataclass with per-member group assignment and token contribution
- ScenarioSuite: top-level container returned by compute_scenarios()
- compute_scenarios(): public API — computes all three scenarios from CountResult

Design notes:
- Pure data transformation layer: no I/O, no parsing, no filtering.
- Inputs: CountResult from counter.count_objects(), optional MigrationSplitConfig.
- Outputs: ScenarioSuite consumed by Phase 13 output.py for XLS generation.
- Formula functions nios_object_tokens() and uddi_native_tokens() are imported from
  counter.py and NOT redefined here — single source of truth for formula constants.
- SCEN-01 and SCEN-03 use grid_counts.active_ip_count as the total Active IP figure.
  This is the global deduplication total (all four sources: leases, fixed addresses,
  host addresses, network reservations). Summing member.active_ip_count values is WRONG
  as those are lease-only per-member IPs that exclude grid-level IP sources.
- SCEN-02 hybrid combined_total is computed as the arithmetic sum of sub-totals:
    combined_total = nios_sub.token_total + niosx_sub.token_total
  Never re-applied from aggregated combined DDI/IP inputs. This ensures exact summation
  with no floating-point rounding divergence between combined_total and sub-total sum.
- Grid-level objects (grid_counts, member_hostname="__grid__") ALWAYS contribute to the
  NIOS-remaining sub-total in hybrid scenario, regardless of member group assignments.
  Rationale: grid-level objects exist independently of any member and represent the
  conservative/correct approach matching current licensing reality.
- SCEN-03 invariant: full_migration.token_total >= current_grid.token_total always.
  UDDI native has SMALLER divisors than NIOS Object (DDI/25 vs DDI/50, IPs/13 vs IPs/25,
  Assets/3 vs Assets/13), so each object costs MORE tokens in UDDI native, meaning the
  full migration total is always >= the current grid total.
- asset_count is always 0 in Phase 11/12; propagated without modification.
- MigrationSplitConfig.migration_split_used is captured by identity in ScenarioSuite
  (not copied) for MIGR-04 verbatim capture in Phase 13 report.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from cloud_usage.nios.counter import (
    CountResult,
    MemberCounts,
    nios_object_tokens,
    uddi_native_tokens,
)

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MigrationSplitConfig:
    """Configuration for member-to-group assignment in hybrid UDDI scenario.

    Follows the FilterConfig frozen dataclass pattern from filter.py.
    All fields are immutable (tuple, not list, for true frozen dataclass behaviour).

    Args:
        niosx_members: Tuple of member_hostname or virtual_oid strings assigned to the
            NIOSX group. All other members use default_group.
            Lookup is exact-string match against MemberCounts.member_hostname.
        default_group: Group for members not listed in niosx_members.
            Valid values: "nios" | "niosx". Default: "nios" (MIGR-03).
        assignment_source: Records how the config was provided for MIGR-04 verbatim
            capture in Phase 13 report. Typical values: "yaml", "dashboard".
    """

    niosx_members: tuple[str, ...] = field(default_factory=tuple)
    default_group: str = "nios"
    assignment_source: str = "yaml"


@dataclass(frozen=True)
class ScenarioResult:
    """Token computation result for a single scenario or sub-scenario.

    Args:
        name: Scenario identifier: "current_grid", "full_migration",
            "nios_remaining", or "niosx_migrated".
        formula_name: Human-readable formula description for Phase 13 report display.
        ddi_count: Total DDI object count for this scenario/sub-scenario.
        active_ip_count: Total Active IP count for this scenario/sub-scenario.
        asset_count: Always 0 in Phase 12 (Phase 11 sets asset_count=0 everywhere).
        token_total: Token total computed from the applicable formula.
    """

    name: str
    formula_name: str
    ddi_count: int
    active_ip_count: int
    asset_count: int
    token_total: float


@dataclass(frozen=True)
class HybridScenarioResult:
    """Hybrid UDDI scenario with two sub-totals that sum to combined_total.

    Invariant: combined_total == nios_sub.token_total + niosx_sub.token_total
    (computed as arithmetic sum; never re-aggregated to avoid floating point divergence).

    Args:
        nios_sub: NIOS-remaining sub-total: grid-level objects + NIOS-assigned members,
            computed under NIOS Object formula (DDI/50 + IPs/25 + Assets/13).
        niosx_sub: NIOSX-migrated sub-total: NIOSX-assigned members only,
            computed under UDDI native formula (DDI/25 + IPs/13 + Assets/3).
        combined_total: Exact arithmetic sum: nios_sub.token_total + niosx_sub.token_total.
    """

    nios_sub: ScenarioResult
    niosx_sub: ScenarioResult
    combined_total: float


@dataclass(frozen=True)
class MemberScenarioRow:
    """Per-member breakdown for Phase 13 Member Attribution sheet.

    Args:
        member_hostname: FQDN of the member (from MemberCounts.member_hostname).
        group: Group assignment: "nios" or "niosx".
        ddi_count: DDI object count from MemberCounts.
        active_ip_count: Active IP count from MemberCounts (lease IPs only for this member).
        asset_count: Always 0 in Phase 12.
        token_contribution: Token total computed under the applicable formula for this member's group.
            "nios" → nios_object_tokens; "niosx" → uddi_native_tokens.
    """

    member_hostname: str
    group: str
    ddi_count: int
    active_ip_count: int
    asset_count: int
    token_contribution: float


@dataclass(frozen=True)
class ScenarioSuite:
    """Complete output of compute_scenarios(): all three scenarios + member attribution.

    Args:
        current_grid: SCEN-01: all members under NIOS Object formula.
        full_migration: SCEN-03: all members under UDDI native formula.
        hybrid_uddi: SCEN-02: NIOS-remaining + NIOSX-migrated sub-totals.
            None if compute_scenarios() was called without a split_config.
        member_attribution: One MemberScenarioRow per MemberCounts entry (Phase 13
            Member Attribution sheet). Does not include the "__grid__" sentinel entry.
        migration_split_used: The MigrationSplitConfig passed to compute_scenarios(),
            captured by identity for MIGR-04 verbatim report inclusion.
            None if compute_scenarios() was called without a split_config.
    """

    current_grid: ScenarioResult
    full_migration: ScenarioResult
    hybrid_uddi: Optional[HybridScenarioResult]
    member_attribution: List[MemberScenarioRow]
    migration_split_used: Optional[MigrationSplitConfig]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_scenarios(
    count_result: CountResult,
    split_config: Optional[MigrationSplitConfig] = None,
) -> ScenarioSuite:
    """Compute three licensing scenarios from grid counts and optional migration split.

    Computes:
    - SCEN-01: current_grid — all members under NIOS Object formula
    - SCEN-03: full_migration — all members under UDDI native formula
    - SCEN-02: hybrid_uddi — if split_config provided, NIOS-remaining + NIOSX-migrated

    Args:
        count_result: Output of count_objects(). Provides per-member counts (member_counts)
            and grid-level totals (grid_counts, member_hostname="__grid__").
        split_config: Optional member-to-group assignment config. If None, hybrid_uddi
            in the returned ScenarioSuite is None.

    Returns:
        ScenarioSuite with all three scenarios, per-member attribution, and the input
        split_config captured verbatim.

    Notes:
        - Active IP totals for SCEN-01 and SCEN-03 use grid_counts.active_ip_count
          (the global deduplication total). Summing member.active_ip_count gives wrong
          results — those are lease-only per-member IPs.
        - SCEN-02 combined_total = nios_sub.token_total + niosx_sub.token_total (exact
          arithmetic sum; never re-computed from aggregated inputs).
        - SCEN-03 invariant: full_migration.token_total >= current_grid.token_total
          (UDDI native has smaller divisors, so each object costs more tokens).
        - grid_counts always contributes to NIOS sub-total in hybrid scenario.
    """

    # --- Aggregate totals for all-grid scenarios (SCEN-01, SCEN-03) ---
    # DDI is additive: per-member DDI + grid-level DDI
    total_ddi: int = (
        sum(m.ddi_count for m in count_result.member_counts)
        + count_result.grid_counts.ddi_count
    )
    # Active IPs: always use global dedup total from grid_counts (NOT sum of member IPs)
    total_ips: int = count_result.grid_counts.active_ip_count
    # Assets always 0 in Phase 11/12
    total_assets: int = 0

    # --- SCEN-01: Current grid — NIOS Object formula ---
    current_grid = ScenarioResult(
        name="current_grid",
        formula_name="NIOS Object (DDI/50 + IPs/25 + Assets/13)",
        ddi_count=total_ddi,
        active_ip_count=total_ips,
        asset_count=total_assets,
        token_total=nios_object_tokens(total_ddi, total_ips, total_assets),
    )

    # --- SCEN-03: Full migration — UDDI native formula ---
    full_migration = ScenarioResult(
        name="full_migration",
        formula_name="UDDI native (DDI/25 + IPs/13 + Assets/3)",
        ddi_count=total_ddi,
        active_ip_count=total_ips,
        asset_count=total_assets,
        token_total=uddi_native_tokens(total_ddi, total_ips, total_assets),
    )

    # Log SCEN-03 invariant violation (should not occur with correct formula constants)
    if full_migration.token_total < current_grid.token_total:
        _logger.warning(
            "SCEN-03 invariant violated: full_migration tokens (%s) < current_grid (%s). "
            "Check formula constants in counter.py.",
            full_migration.token_total,
            current_grid.token_total,
        )

    # --- Precompute NIOSX member set for group resolution ---
    niosx_set: frozenset[str] = (
        frozenset(split_config.niosx_members) if split_config is not None else frozenset()
    )

    # --- Member Attribution (all scenarios; excludes "__grid__" sentinel entry) ---
    member_attribution: List[MemberScenarioRow] = []
    for m in count_result.member_counts:
        if split_config is not None:
            group = "niosx" if m.member_hostname in niosx_set else split_config.default_group
        else:
            # No split config: attribute all members as "nios" for current_grid formula
            group = "nios"

        token_contribution = (
            uddi_native_tokens(m.ddi_count, m.active_ip_count, 0)
            if group == "niosx"
            else nios_object_tokens(m.ddi_count, m.active_ip_count, 0)
        )
        member_attribution.append(MemberScenarioRow(
            member_hostname=m.member_hostname,
            group=group,
            ddi_count=m.ddi_count,
            active_ip_count=m.active_ip_count,
            asset_count=0,
            token_contribution=token_contribution,
        ))

    # --- SCEN-02: Hybrid UDDI scenario (only if split_config provided) ---
    hybrid_uddi: Optional[HybridScenarioResult] = None
    if split_config is not None:
        # NIOS-remaining: grid_counts always goes to NIOS sub-total (CONTEXT.md decision)
        # Grid-level DDI and global IPs (including fixed/host/network IPs with no member
        # attribution) are always NIOS — conservative and correct per current licensing.
        nios_ddi: int = count_result.grid_counts.ddi_count
        nios_ips: int = count_result.grid_counts.active_ip_count  # grid IPs always NIOS

        # NIOSX-migrated: member-attributed objects only
        niosx_ddi: int = 0
        niosx_ips: int = 0

        # Partition member_counts by group assignment
        for m in count_result.member_counts:
            group = "niosx" if m.member_hostname in niosx_set else split_config.default_group
            if group == "niosx":
                niosx_ddi += m.ddi_count
                niosx_ips += m.active_ip_count
            else:
                nios_ddi += m.ddi_count
                nios_ips += m.active_ip_count

        nios_sub = ScenarioResult(
            name="nios_remaining",
            formula_name="NIOS Object (DDI/50 + IPs/25 + Assets/13)",
            ddi_count=nios_ddi,
            active_ip_count=nios_ips,
            asset_count=0,
            token_total=nios_object_tokens(nios_ddi, nios_ips, 0),
        )
        niosx_sub = ScenarioResult(
            name="niosx_migrated",
            formula_name="UDDI native (DDI/25 + IPs/13 + Assets/3)",
            ddi_count=niosx_ddi,
            active_ip_count=niosx_ips,
            asset_count=0,
            token_total=uddi_native_tokens(niosx_ddi, niosx_ips, 0),
        )
        # combined_total is the ARITHMETIC SUM — never re-computed from aggregated inputs
        # This prevents floating-point divergence between the sum and the stored value.
        combined_total = nios_sub.token_total + niosx_sub.token_total

        hybrid_uddi = HybridScenarioResult(
            nios_sub=nios_sub,
            niosx_sub=niosx_sub,
            combined_total=combined_total,
        )

    return ScenarioSuite(
        current_grid=current_grid,
        full_migration=full_migration,
        hybrid_uddi=hybrid_uddi,
        member_attribution=member_attribution,
        migration_split_used=split_config,  # captured by identity for MIGR-04
    )
