"""TDD tests for compute_scenarios(), ScenarioSuite, and MigrationSplitConfig.

Tests cover all 5 Phase 12 success criteria and MIGR-01, MIGR-03, MIGR-04.
Uses in-memory CountResult/MemberCounts construction (no .tar.gz fixtures needed).

Plan 01 tests: core nominal scenarios.
Plan 02 tests: edge cases + phase success criteria acceptance tests.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import List

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cloud_usage.nios.scenarios import (
    MigrationSplitConfig,
    ScenarioResult,
    HybridScenarioResult,
    MemberScenarioRow,
    ScenarioSuite,
    compute_scenarios,
)
from cloud_usage.nios.counter import (
    CountResult,
    MemberCounts,
    nios_object_tokens,
    uddi_native_tokens,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _member(hostname: str, ddi: int = 0, ips: int = 0, leases: int = 0) -> MemberCounts:
    """Build a per-member MemberCounts entry."""
    return MemberCounts(
        member_hostname=hostname,
        ddi_count=ddi,
        active_ip_count=ips,
        lease_count=leases,
        asset_count=0,
    )


def _grid(ddi: int = 0, ips: int = 0, leases: int = 0) -> MemberCounts:
    """Build a grid-level MemberCounts entry (member_hostname='__grid__')."""
    return MemberCounts(
        member_hostname="__grid__",
        ddi_count=ddi,
        active_ip_count=ips,
        lease_count=leases,
        asset_count=0,
    )


def _result(members: List[MemberCounts], grid: MemberCounts) -> CountResult:
    """Build a CountResult from member list and grid counts."""
    return CountResult(member_counts=members, grid_counts=grid)


# ---------------------------------------------------------------------------
# PLAN 01 TESTS — core nominal scenarios
# ---------------------------------------------------------------------------

# ---- SCEN-01: Current grid scenario ----

def test_current_grid_scenario_nios_formula():
    """SCEN-01: current_grid applies NIOS Object formula to total DDI and global Active IPs."""
    members = [_member("gm1", ddi=100, ips=500), _member("gm2", ddi=200, ips=800)]
    grid = _grid(ddi=50, ips=2000)
    result = _result(members, grid)
    suite = compute_scenarios(result)

    expected_ddi = 350      # 100 + 200 (members) + 50 (grid)
    expected_ips = 2000     # grid_counts.active_ip_count (global dedup total)
    expected_tokens = nios_object_tokens(expected_ddi, expected_ips, 0)

    assert suite.current_grid.ddi_count == expected_ddi
    assert suite.current_grid.active_ip_count == expected_ips
    assert suite.current_grid.asset_count == 0
    assert suite.current_grid.token_total == pytest.approx(expected_tokens)
    assert "NIOS Object" in suite.current_grid.formula_name
    assert suite.current_grid.name == "current_grid"


# ---- SCEN-03: Full migration scenario ----

def test_full_migration_scenario_uddi_formula():
    """SCEN-03: full_migration applies UDDI native formula to total DDI and global Active IPs."""
    members = [_member("gm1", ddi=100, ips=500)]
    grid = _grid(ddi=50, ips=1000)
    result = _result(members, grid)
    suite = compute_scenarios(result)

    expected_ddi = 150
    expected_ips = 1000     # grid_counts.active_ip_count
    expected_tokens = uddi_native_tokens(expected_ddi, expected_ips, 0)

    assert suite.full_migration.ddi_count == expected_ddi
    assert suite.full_migration.active_ip_count == expected_ips
    assert suite.full_migration.asset_count == 0
    assert suite.full_migration.token_total == pytest.approx(expected_tokens)
    assert "UDDI native" in suite.full_migration.formula_name
    assert suite.full_migration.name == "full_migration"


def test_full_migration_ge_current_grid():
    """SCEN-03: full_migration.token_total >= current_grid.token_total always.

    UDDI native has smaller divisors (DDI/25 vs DDI/50, IPs/13 vs IPs/25), so each
    object costs MORE tokens in full migration than in current grid.
    """
    members = [_member("gm1", ddi=500, ips=2500)]
    grid = _grid(ddi=100, ips=10000)
    result = _result(members, grid)
    suite = compute_scenarios(result)

    assert suite.full_migration.token_total >= suite.current_grid.token_total


# ---- SCEN-02: Hybrid UDDI scenario ----

def test_hybrid_scenario_requires_split_config():
    """SCEN-02: hybrid_uddi is None when no split_config provided."""
    result = _result([_member("gm1", ddi=10, ips=50)], _grid(ddi=5, ips=100))
    suite_no_config = compute_scenarios(result)
    assert suite_no_config.hybrid_uddi is None

    suite_with_config = compute_scenarios(result, MigrationSplitConfig())
    assert suite_with_config.hybrid_uddi is not None


def test_hybrid_scenario_sub_total_sum():
    """SCEN-02: combined_total is the EXACT arithmetic sum of nios_sub + niosx_sub."""
    members = [
        _member("gm1.corp", ddi=100, ips=400),
        _member("gm2.corp", ddi=200, ips=800),
    ]
    grid = _grid(ddi=50, ips=2000)
    result = _result(members, grid)
    split_config = MigrationSplitConfig(niosx_members=("gm1.corp",))
    suite = compute_scenarios(result, split_config)

    hybrid = suite.hybrid_uddi
    assert hybrid is not None

    expected_combined = hybrid.nios_sub.token_total + hybrid.niosx_sub.token_total
    assert hybrid.combined_total == pytest.approx(expected_combined, rel=1e-9), (
        f"combined_total ({hybrid.combined_total}) must equal "
        f"nios_sub ({hybrid.nios_sub.token_total}) + "
        f"niosx_sub ({hybrid.niosx_sub.token_total}) = {expected_combined}"
    )


def test_hybrid_grid_counts_always_nios():
    """SCEN-02: grid_counts (member_hostname='__grid__') always goes to NIOS sub-total."""
    members = [_member("gm1.corp", ddi=100, ips=500)]
    grid = _grid(ddi=50, ips=1000)
    result = _result(members, grid)
    split_config = MigrationSplitConfig(niosx_members=("gm1.corp",))
    suite = compute_scenarios(result, split_config)

    hybrid = suite.hybrid_uddi
    assert hybrid is not None

    # Grid DDI (50) goes to NIOS sub-total — not NIOSX
    # NIOSX only gets the member's DDI (100)
    assert hybrid.niosx_sub.ddi_count == 100  # gm1 member only
    assert hybrid.nios_sub.ddi_count == 50    # grid only (gm1 is NIOSX)
    # NIOS gets grid IPs (1000), NIOSX gets gm1's lease IPs (500)
    assert hybrid.nios_sub.active_ip_count == 1000   # grid IPs always NIOS
    assert hybrid.niosx_sub.active_ip_count == 500


# ---- MIGR-01: Member group assignment ----

def test_member_group_assignment_by_hostname():
    """MIGR-01: Members in niosx_members → 'niosx'; others → default_group."""
    members = [
        _member("member1.corp.example.com", ddi=10, ips=50),
        _member("member2.corp.example.com", ddi=20, ips=100),
    ]
    grid = _grid(ddi=0, ips=150)
    result = _result(members, grid)
    split_config = MigrationSplitConfig(niosx_members=("member1.corp.example.com",))
    suite = compute_scenarios(result, split_config)

    hybrid = suite.hybrid_uddi
    assert hybrid is not None
    # member1 goes to NIOSX, member2 stays NIOS
    assert hybrid.niosx_sub.ddi_count == 10    # member1 only
    assert hybrid.niosx_sub.active_ip_count == 50
    assert hybrid.nios_sub.ddi_count == 20     # member2 + grid (0)
    assert hybrid.nios_sub.active_ip_count == 100 + 150  # member2 + grid IPs


def test_member_not_in_niosx_gets_default_group():
    """MIGR-01/MIGR-03: Members not in niosx_members use default_group='nios'."""
    members = [
        _member("gm1", ddi=10, ips=50),
        _member("gm2", ddi=20, ips=100),
    ]
    grid = _grid(ddi=0, ips=150)
    result = _result(members, grid)
    split_config = MigrationSplitConfig(niosx_members=())  # empty — all default to nios
    suite = compute_scenarios(result, split_config)

    # All member_attribution rows should be "nios"
    for row in suite.member_attribution:
        assert row.group == "nios", f"Member {row.member_hostname} should be 'nios' by default"


# ---- MIGR-03: Default group configurable ----

def test_default_group_configurable():
    """MIGR-03: default_group='niosx' makes unassigned members NIOSX by default."""
    members = [_member("gm1.corp", ddi=50, ips=100)]
    grid = _grid(ddi=10, ips=200)
    result = _result(members, grid)
    split_config = MigrationSplitConfig(niosx_members=(), default_group="niosx")
    suite = compute_scenarios(result, split_config)

    hybrid = suite.hybrid_uddi
    assert hybrid is not None
    # gm1 is not in niosx_members but default_group="niosx" → goes to NIOSX
    assert hybrid.niosx_sub.ddi_count == 50
    assert hybrid.niosx_sub.active_ip_count == 100
    # NIOS gets only grid DDI/IPs
    assert hybrid.nios_sub.ddi_count == 10
    assert hybrid.nios_sub.active_ip_count == 200


# ---- MIGR-04: Migration split captured verbatim ----

def test_migration_split_captured_verbatim():
    """MIGR-04: migration_split_used is identity-equal to the input split_config."""
    members = [_member("gm1", ddi=10, ips=50)]
    grid = _grid(ddi=0, ips=50)
    result = _result(members, grid)
    split_config = MigrationSplitConfig(niosx_members=("gm1",), assignment_source="dashboard")
    suite = compute_scenarios(result, split_config)

    assert suite.migration_split_used is split_config
    assert suite.migration_split_used.assignment_source == "dashboard"


def test_migration_split_none_when_no_config():
    """MIGR-04: migration_split_used is None when no split_config provided."""
    result = _result([_member("gm1")], _grid())
    suite = compute_scenarios(result)
    assert suite.migration_split_used is None


# ---- Member Attribution ----

def test_member_attribution_rows():
    """Member Attribution: one MemberScenarioRow per MemberCounts entry."""
    members = [
        _member("gm1", ddi=100, ips=500),
        _member("gm2", ddi=200, ips=1000),
    ]
    grid = _grid(ddi=0, ips=1500)
    result = _result(members, grid)
    suite = compute_scenarios(result)

    assert len(suite.member_attribution) == 2

    hostnames = {row.member_hostname for row in suite.member_attribution}
    assert "gm1" in hostnames
    assert "gm2" in hostnames

    for row in suite.member_attribution:
        original = next(m for m in members if m.member_hostname == row.member_hostname)
        assert row.ddi_count == original.ddi_count
        assert row.active_ip_count == original.active_ip_count
        assert row.asset_count == 0


# ---- Empty inputs ----

def test_empty_count_result():
    """Edge case: empty member list produces zero tokens."""
    result = _result([], _grid(ddi=0, ips=0))
    suite = compute_scenarios(result)

    assert suite.current_grid.token_total == pytest.approx(0.0)
    assert suite.full_migration.token_total == pytest.approx(0.0)
    assert suite.member_attribution == []
    assert suite.hybrid_uddi is None


# ---------------------------------------------------------------------------
# PLAN 02 TESTS — edge cases and phase success criteria
# ---------------------------------------------------------------------------

# ---- Edge Case 1: IP Attribution Correctness ----

def test_ip_total_uses_grid_counts_not_member_sum():
    """Active IP total must come from grid_counts.active_ip_count, not sum of member IPs."""
    members = [_member("gm1", ddi=10, ips=50), _member("gm2", ddi=20, ips=30)]
    # grid has 200 unique IPs (includes fixed/host/network IPs not counted per-member)
    grid = _grid(ddi=5, ips=200)
    result = _result(members, grid)
    suite = compute_scenarios(result)

    # Sum of member IPs = 80, but global total = 200
    assert suite.current_grid.active_ip_count == 200, (
        "current_grid must use grid_counts.active_ip_count (200), "
        "not sum of member IPs (80)"
    )
    assert suite.full_migration.active_ip_count == 200, (
        "full_migration must use grid_counts.active_ip_count (200)"
    )


# ---- Edge Case 2: All members NIOSX hybrid ----

def test_hybrid_all_members_niosx():
    """Hybrid: when all members are NIOSX, only grid-level objects remain in NIOS sub-total."""
    members = [_member("gm1.corp", ddi=100, ips=500)]
    grid = _grid(ddi=50, ips=1000)
    result = _result(members, grid)
    split_config = MigrationSplitConfig(niosx_members=("gm1.corp",))
    suite = compute_scenarios(result, split_config)

    assert suite.hybrid_uddi is not None
    hybrid = suite.hybrid_uddi

    # NIOSX gets all member DDI/IPs
    assert hybrid.niosx_sub.ddi_count == 100
    assert hybrid.niosx_sub.active_ip_count == 500

    # NIOS gets only grid DDI/IPs
    assert hybrid.nios_sub.ddi_count == 50
    assert hybrid.nios_sub.active_ip_count == 1000

    # combined_total is additive sum
    expected_combined = hybrid.nios_sub.token_total + hybrid.niosx_sub.token_total
    assert hybrid.combined_total == pytest.approx(expected_combined)


# ---- Edge Case 3: All members NIOS (empty niosx_members) ----

def test_hybrid_all_members_nios():
    """Hybrid: when no members are NIOSX, niosx_sub is zero and nios_sub has all counts."""
    members = [_member("gm1.corp", ddi=100, ips=500)]
    grid = _grid(ddi=50, ips=1000)
    result = _result(members, grid)
    split_config = MigrationSplitConfig(niosx_members=())  # empty — all NIOS
    suite = compute_scenarios(result, split_config)

    assert suite.hybrid_uddi is not None
    hybrid = suite.hybrid_uddi

    # NIOSX gets nothing
    assert hybrid.niosx_sub.ddi_count == 0
    assert hybrid.niosx_sub.active_ip_count == 0
    assert hybrid.niosx_sub.token_total == pytest.approx(0.0)

    # NIOS gets grid + all member DDI/IPs
    assert hybrid.nios_sub.ddi_count == 150   # 50 grid + 100 member
    assert hybrid.nios_sub.active_ip_count == 1500  # 1000 grid + 500 member

    # combined_total == nios_sub.token_total (niosx contributes 0)
    assert hybrid.combined_total == pytest.approx(hybrid.nios_sub.token_total)


# ---- Edge Case 4: DDI count equality across scenarios ----

def test_scen01_scen03_same_ddi_and_ips():
    """current_grid and full_migration operate on the same DDI and IP totals."""
    members = [_member("gm1", ddi=200, ips=1000)]
    grid = _grid(ddi=100, ips=5000)
    result = _result(members, grid)
    suite = compute_scenarios(result)

    assert suite.current_grid.ddi_count == suite.full_migration.ddi_count
    assert suite.current_grid.active_ip_count == suite.full_migration.active_ip_count
    assert suite.current_grid.asset_count == suite.full_migration.asset_count == 0


# ---- Edge Case 5: MigrationSplitConfig is frozen ----

def test_migration_split_config_is_frozen():
    """MigrationSplitConfig is a frozen dataclass — mutation raises FrozenInstanceError."""
    config = MigrationSplitConfig(niosx_members=("m1",))
    with pytest.raises((dataclasses.FrozenInstanceError, TypeError, AttributeError)):
        config.niosx_members = ("m2",)  # type: ignore[misc]


# ---- Edge Case 6: default_group="niosx" hybrid ----

def test_hybrid_default_group_niosx():
    """Members not in niosx_members go to NIOSX when default_group='niosx'."""
    members = [_member("gm1.corp", ddi=50, ips=100)]
    grid = _grid(ddi=10, ips=200)
    result = _result(members, grid)
    split_config = MigrationSplitConfig(niosx_members=(), default_group="niosx")
    suite = compute_scenarios(result, split_config)

    hybrid = suite.hybrid_uddi
    assert hybrid is not None
    # gm1.corp is not in niosx_members but default_group="niosx" → goes to NIOSX
    assert hybrid.niosx_sub.ddi_count == 50
    assert hybrid.niosx_sub.active_ip_count == 100
    # NIOS has only grid counts
    assert hybrid.nios_sub.ddi_count == 10
    assert hybrid.nios_sub.active_ip_count == 200


# ---- Edge Case 7: member_attribution token formula validation ----

def test_member_attribution_token_formula_by_group():
    """MemberScenarioRow.token_contribution uses the correct formula per group."""
    members = [
        _member("nios-member.corp", ddi=50, ips=250),
        _member("niosx-member.corp", ddi=25, ips=130),
    ]
    grid = _grid(ddi=0, ips=0)
    result = _result(members, grid)
    split_config = MigrationSplitConfig(niosx_members=("niosx-member.corp",))
    suite = compute_scenarios(result, split_config)

    rows = {r.member_hostname: r for r in suite.member_attribution}

    nios_row = rows["nios-member.corp"]
    niosx_row = rows["niosx-member.corp"]

    assert nios_row.group == "nios"
    assert nios_row.token_contribution == pytest.approx(
        nios_object_tokens(50, 250, 0)
    )

    assert niosx_row.group == "niosx"
    assert niosx_row.token_contribution == pytest.approx(
        uddi_native_tokens(25, 130, 0)
    )


# ---- Edge Case 8: default_group default value ----

def test_migration_split_config_default_group_is_nios():
    """MIGR-03: MigrationSplitConfig().default_group defaults to 'nios'."""
    config = MigrationSplitConfig()
    assert config.default_group == "nios"


# ---- Edge Case 9: assignment_source captured ----

def test_assignment_source_captured_in_suite():
    """MIGR-04: assignment_source is captured verbatim in migration_split_used."""
    members = [_member("gm1", ddi=10, ips=50)]
    grid = _grid(ddi=0, ips=50)
    result = _result(members, grid)
    split_config = MigrationSplitConfig(niosx_members=("gm1",), assignment_source="dashboard")
    suite = compute_scenarios(result, split_config)

    assert suite.migration_split_used is split_config
    assert suite.migration_split_used.assignment_source == "dashboard"


# ---------------------------------------------------------------------------
# PHASE SUCCESS CRITERIA — explicit acceptance tests
# ---------------------------------------------------------------------------

def test_sc1_current_grid_nios_formula_single_ddi_ip_token_total():
    """SC-1: Current grid applies NIOS Object formula to all members + grid."""
    members = [_member("gm1", ddi=50, ips=0)]
    grid = _grid(ddi=100, ips=500)
    result = _result(members, grid)
    suite = compute_scenarios(result)

    expected_ddi = 150      # 50 member + 100 grid
    expected_ips = 500      # grid_counts.active_ip_count
    expected_tokens = nios_object_tokens(expected_ddi, expected_ips, 0)

    assert suite.current_grid.ddi_count == expected_ddi, "SC-1: DDI total"
    assert suite.current_grid.active_ip_count == expected_ips, "SC-1: Active IP total"
    assert suite.current_grid.token_total == pytest.approx(expected_tokens), "SC-1: Token total"


def test_sc2_hybrid_sub_totals_sum_exactly():
    """SC-2: NIOS-remaining + NIOSX-migrated sub-totals sum exactly to combined_total."""
    members = [
        _member("gm1.corp", ddi=100, ips=400),
        _member("gm2.corp", ddi=200, ips=800),
    ]
    grid = _grid(ddi=50, ips=2000)
    result = _result(members, grid)
    split_config = MigrationSplitConfig(niosx_members=("gm1.corp",))
    suite = compute_scenarios(result, split_config)
    hybrid = suite.hybrid_uddi

    assert hybrid is not None, "SC-2: hybrid_uddi must be computed when split_config provided"

    expected_combined = hybrid.nios_sub.token_total + hybrid.niosx_sub.token_total
    assert hybrid.combined_total == pytest.approx(expected_combined, rel=1e-9), (
        f"SC-2: combined_total ({hybrid.combined_total}) must equal "
        f"nios + niosx sub-totals ({expected_combined})"
    )


def test_sc3_full_migration_gte_current_grid():
    """SC-3: Full migration token total >= current grid total (UDDI has smaller divisors)."""
    members = [_member("gm1", ddi=500, ips=2500)]
    grid = _grid(ddi=100, ips=10000)
    result = _result(members, grid)
    suite = compute_scenarios(result)

    assert suite.full_migration.token_total >= suite.current_grid.token_total, (
        f"SC-3: full_migration ({suite.full_migration.token_total}) must be >= "
        f"current_grid ({suite.current_grid.token_total})"
    )


def test_sc4_default_group_nios_recorded_in_attribution():
    """SC-4: Members not in split config default to 'nios' and this is recorded."""
    members = [
        _member("gm1.corp", ddi=10, ips=50),
        _member("gm2.corp", ddi=20, ips=100),
    ]
    grid = _grid(ddi=0, ips=150)
    result = _result(members, grid)
    # gm1 in NIOSX; gm2 gets default group
    split_config = MigrationSplitConfig(niosx_members=("gm1.corp",), default_group="nios")
    suite = compute_scenarios(result, split_config)

    rows = {r.member_hostname: r for r in suite.member_attribution}
    assert rows["gm1.corp"].group == "niosx", "SC-4: gm1 explicitly assigned to niosx"
    assert rows["gm2.corp"].group == "nios", "SC-4: gm2 defaults to 'nios'"


def test_sc5_migration_split_captured_verbatim_in_suite():
    """SC-5: migration_split_used is identity-equal to the input split_config."""
    members = [_member("gm1", ddi=10, ips=50)]
    grid = _grid(ddi=0, ips=50)
    result = _result(members, grid)
    split_config = MigrationSplitConfig(
        niosx_members=("gm1",),
        default_group="nios",
        assignment_source="yaml",
    )
    suite = compute_scenarios(result, split_config)

    assert suite.migration_split_used is split_config, (
        "SC-5: migration_split_used must be the exact same object (verbatim capture)"
    )
    # Also verify None case
    suite_no_config = compute_scenarios(result)
    assert suite_no_config.migration_split_used is None, (
        "SC-5: migration_split_used is None when no split_config provided"
    )
