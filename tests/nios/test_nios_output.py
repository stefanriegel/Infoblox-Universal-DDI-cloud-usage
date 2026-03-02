"""TDD tests for NIOS output module (Phase 13).

Tests for:
- get_member_map() public export from cloud_usage.nios.parser
- write_nios_xlsx_report() with all 6 sheets
- run_nios_analysis() pipeline runner
- _count_ip_by_type() per-source IP counting helper
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock, patch

import openpyxl
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cloud_usage.nios.counter import CountResult, MemberCounts
from cloud_usage.nios.filter import FilterConfig
from cloud_usage.nios.scenarios import (
    HybridScenarioResult,
    MemberScenarioRow,
    MigrationSplitConfig,
    ScenarioResult,
    ScenarioSuite,
)
from cloud_usage.nios.schema import IntegrityReport, NiosFamily, NiosObject


# ---------------------------------------------------------------------------
# Module-level smoke tests (run first so import errors surface immediately)
# ---------------------------------------------------------------------------


def test_imports_write_nios_xlsx_report():
    """write_nios_xlsx_report is importable from cloud_usage.nios.output."""
    from cloud_usage.nios.output import write_nios_xlsx_report  # noqa: F401

    assert callable(write_nios_xlsx_report)


def test_imports_get_member_map():
    """get_member_map is importable from cloud_usage.nios.parser."""
    from cloud_usage.nios.parser import get_member_map  # noqa: F401

    assert callable(get_member_map)


def test_get_member_map_in_parser_all():
    """get_member_map appears in cloud_usage.nios.parser.__all__."""
    import cloud_usage.nios.parser as parser_pkg

    assert "get_member_map" in parser_pkg.__all__


def test_get_member_map_is_callable():
    """get_member_map accepts a path argument (callable interface check)."""
    from cloud_usage.nios.parser import get_member_map

    assert callable(get_member_map)
    # Verify it wraps _build_member_map (internal wiring check)
    import inspect

    src = inspect.getsource(get_member_map)
    assert "_build_member_map" in src


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def minimal_integrity_report() -> IntegrityReport:
    """Minimal IntegrityReport with all 21 families pre-populated."""
    families_found = {
        NiosFamily.MEMBER: 2,
        NiosFamily.NETWORK: 100,
        NiosFamily.LEASE: 5000,
        NiosFamily.FIXED_ADDRESS: 200,
        NiosFamily.HOST_ADDRESS: 150,
        NiosFamily.DNS_ZONE: 50,
        NiosFamily.DNS_RECORD_A: 3000,
        NiosFamily.DNS_RECORD_AAAA: 500,
        NiosFamily.DNS_RECORD_CNAME: 800,
        NiosFamily.DNS_RECORD_MX: 20,
        NiosFamily.DNS_RECORD_NS: 60,
        NiosFamily.DNS_RECORD_PTR: 2500,
        NiosFamily.DNS_RECORD_SOA: 50,
        NiosFamily.DNS_RECORD_SRV: 10,
        NiosFamily.DNS_RECORD_TXT: 100,
        NiosFamily.HOST_OBJECT: 400,
        NiosFamily.HOST_ALIAS: 200,
        NiosFamily.DHCP_RANGE: 30,
        NiosFamily.EXCLUSION_RANGE: 5,
        NiosFamily.NETWORK_CONTAINER: 15,
        NiosFamily.NETWORK_VIEW: 3,
    }
    return IntegrityReport(
        families_found=families_found,
        warnings=[],
        nios_version="9.0.6-53318-82020f7ffaad",
        snapshot_date="2025-08-12",
    )


@pytest.fixture()
def minimal_count_result() -> CountResult:
    """CountResult with 2 members and a grid aggregate."""
    member1 = MemberCounts(
        member_hostname="member-a.example.com",
        ddi_count=500,
        active_ip_count=1000,
        lease_count=2000,
        asset_count=0,
    )
    member2 = MemberCounts(
        member_hostname="member-b.example.com",
        ddi_count=300,
        active_ip_count=800,
        lease_count=1500,
        asset_count=0,
    )
    grid = MemberCounts(
        member_hostname="__grid__",
        ddi_count=200,
        active_ip_count=5000,
        lease_count=3500,
        asset_count=0,
    )
    return CountResult(member_counts=[member1, member2], grid_counts=grid)


@pytest.fixture()
def minimal_scenario_suite(minimal_count_result: CountResult) -> ScenarioSuite:
    """ScenarioSuite with all three scenarios present."""
    current_grid = ScenarioResult(
        name="current_grid",
        formula_name="NIOS Object (DDI/50 + IPs/25 + Assets/13)",
        ddi_count=1000,
        active_ip_count=5000,
        asset_count=0,
        token_total=220.0,
    )
    full_migration = ScenarioResult(
        name="full_migration",
        formula_name="UDDI native (DDI/25 + IPs/13 + Assets/3)",
        ddi_count=1000,
        active_ip_count=5000,
        asset_count=0,
        token_total=424.6,
    )
    nios_sub = ScenarioResult(
        name="nios_remaining",
        formula_name="NIOS Object (DDI/50 + IPs/25 + Assets/13)",
        ddi_count=700,
        active_ip_count=4200,
        asset_count=0,
        token_total=168.0 + 168.0,
    )
    niosx_sub = ScenarioResult(
        name="niosx_migrated",
        formula_name="UDDI native (DDI/25 + IPs/13 + Assets/3)",
        ddi_count=300,
        active_ip_count=800,
        asset_count=0,
        token_total=73.5,
    )
    hybrid = HybridScenarioResult(
        nios_sub=nios_sub,
        niosx_sub=niosx_sub,
        combined_total=nios_sub.token_total + niosx_sub.token_total,
    )
    split_config = MigrationSplitConfig(
        niosx_members=("member-b.example.com",),
        default_group="nios",
        assignment_source="yaml",
    )
    member_rows = [
        MemberScenarioRow(
            member_hostname="member-a.example.com",
            group="nios",
            ddi_count=500,
            active_ip_count=1000,
            asset_count=0,
            token_contribution=50.0,
        ),
        MemberScenarioRow(
            member_hostname="member-b.example.com",
            group="niosx",
            ddi_count=300,
            active_ip_count=800,
            asset_count=0,
            token_contribution=73.5,
        ),
    ]
    return ScenarioSuite(
        current_grid=current_grid,
        full_migration=full_migration,
        hybrid_uddi=hybrid,
        member_attribution=member_rows,
        migration_split_used=split_config,
    )


@pytest.fixture()
def minimal_filter_config() -> FilterConfig:
    return FilterConfig(whitelist=(), blacklist=(), lease_states=("active",))


@pytest.fixture()
def minimal_member_map() -> dict[str, str]:
    """virtual_oid -> hostname map."""
    return {
        "101": "member-a.example.com",
        "102": "member-b.example.com",
    }


@pytest.fixture()
def minimal_ip_by_type() -> dict[str, int]:
    return {"leases": 3000, "fixed": 200, "host": 150, "reservations": 50}


# ---------------------------------------------------------------------------
# write_nios_xlsx_report: general tests
# ---------------------------------------------------------------------------


def test_write_returns_filepath(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """write_nios_xlsx_report returns the filepath string passed in."""
    from cloud_usage.nios.output import write_nios_xlsx_report

    out = tmp_path / "out.xlsx"
    result = write_nios_xlsx_report(
        filepath=str(out),
        integrity_report=minimal_integrity_report,
        count_result=minimal_count_result,
        scenario_suite=minimal_scenario_suite,
        filter_config=minimal_filter_config,
        split_config=minimal_scenario_suite.migration_split_used,
        analysis_timestamp="2026-03-02 10:00:00 UTC",
        member_map=minimal_member_map,
        ip_by_type=minimal_ip_by_type,
    )
    assert result == str(out)


def test_write_produces_valid_xlsx(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """write_nios_xlsx_report produces a valid .xlsx file readable by openpyxl."""
    from cloud_usage.nios.output import write_nios_xlsx_report

    out = tmp_path / "out.xlsx"
    write_nios_xlsx_report(
        filepath=str(out),
        integrity_report=minimal_integrity_report,
        count_result=minimal_count_result,
        scenario_suite=minimal_scenario_suite,
        filter_config=minimal_filter_config,
        split_config=minimal_scenario_suite.migration_split_used,
        analysis_timestamp="2026-03-02 10:00:00 UTC",
        member_map=minimal_member_map,
        ip_by_type=minimal_ip_by_type,
    )
    wb = openpyxl.load_workbook(str(out))
    assert wb is not None


def test_write_produces_exactly_6_sheets(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """write_nios_xlsx_report produces a workbook with exactly 6 sheets."""
    from cloud_usage.nios.output import write_nios_xlsx_report

    out = tmp_path / "out.xlsx"
    write_nios_xlsx_report(
        filepath=str(out),
        integrity_report=minimal_integrity_report,
        count_result=minimal_count_result,
        scenario_suite=minimal_scenario_suite,
        filter_config=minimal_filter_config,
        split_config=minimal_scenario_suite.migration_split_used,
        analysis_timestamp="2026-03-02 10:00:00 UTC",
        member_map=minimal_member_map,
        ip_by_type=minimal_ip_by_type,
    )
    wb = openpyxl.load_workbook(str(out))
    assert len(wb.sheetnames) == 6


def test_write_sheet_names_and_order(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Sheets are in the correct order: Analysis Info → Object Counters → ... → Member Attribution."""
    from cloud_usage.nios.output import write_nios_xlsx_report

    out = tmp_path / "out.xlsx"
    write_nios_xlsx_report(
        filepath=str(out),
        integrity_report=minimal_integrity_report,
        count_result=minimal_count_result,
        scenario_suite=minimal_scenario_suite,
        filter_config=minimal_filter_config,
        split_config=minimal_scenario_suite.migration_split_used,
        analysis_timestamp="2026-03-02 10:00:00 UTC",
        member_map=minimal_member_map,
        ip_by_type=minimal_ip_by_type,
    )
    wb = openpyxl.load_workbook(str(out))
    assert wb.sheetnames == [
        "Analysis Info",
        "Object Counters",
        "DDI Objects",
        "Active IP by Type",
        "Scenario Comparison",
        "Member Attribution",
    ]


# ---------------------------------------------------------------------------
# Helper: write fixture workbook and return openpyxl workbook
# ---------------------------------------------------------------------------


def _write_fixture(
    tmp_path,
    integrity_report,
    count_result,
    scenario_suite,
    filter_config,
    member_map,
    ip_by_type,
    split_config=None,
    analysis_timestamp="2026-03-02 10:00:00 UTC",
):
    from cloud_usage.nios.output import write_nios_xlsx_report

    out = tmp_path / "out.xlsx"
    write_nios_xlsx_report(
        filepath=str(out),
        integrity_report=integrity_report,
        count_result=count_result,
        scenario_suite=scenario_suite,
        filter_config=filter_config,
        split_config=split_config if split_config is not None else scenario_suite.migration_split_used,
        analysis_timestamp=analysis_timestamp,
        member_map=member_map,
        ip_by_type=ip_by_type,
    )
    return openpyxl.load_workbook(str(out))


def _sheet_values(ws) -> list[list]:
    """Return all non-None rows as list of lists of cell values."""
    rows = []
    for row in ws.iter_rows(values_only=True):
        if any(v is not None for v in row):
            rows.append(list(row))
    return rows


def _find_row_by_label(rows: list[list], label: str) -> list | None:
    """Return first row where the first cell matches label (case-insensitive)."""
    for row in rows:
        if row and str(row[0]).strip().lower() == label.lower():
            return row
    return None


# ---------------------------------------------------------------------------
# Sheet 1: Analysis Info
# ---------------------------------------------------------------------------


def test_analysis_info_sheet_index(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Analysis Info sheet is at index 0."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    assert wb.sheetnames[0] == "Analysis Info"


def test_analysis_info_contains_nios_version(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Analysis Info sheet contains a row with 'NIOS Version' label."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Analysis Info"]
    rows = _sheet_values(ws)
    row = _find_row_by_label(rows, "NIOS Version")
    assert row is not None
    assert "9.0.6-53318-82020f7ffaad" in str(row[1])


def test_analysis_info_contains_snapshot_date(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Analysis Info sheet contains 'Backup Snapshot Date' row."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Analysis Info"]
    rows = _sheet_values(ws)
    row = _find_row_by_label(rows, "Backup Snapshot Date")
    assert row is not None
    assert "2025-08-12" in str(row[1])


def test_analysis_info_contains_analysis_timestamp(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Analysis Info sheet contains 'Analysis Timestamp' row."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
        analysis_timestamp="2026-03-02 10:00:00 UTC",
    )
    ws = wb["Analysis Info"]
    rows = _sheet_values(ws)
    row = _find_row_by_label(rows, "Analysis Timestamp")
    assert row is not None
    assert "2026-03-02" in str(row[1])


def test_analysis_info_contains_filter_rows(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Analysis Info sheet contains filter config rows."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Analysis Info"]
    rows = _sheet_values(ws)
    labels = [str(r[0]).strip() for r in rows if r]
    assert "Whitelist Patterns" in labels
    assert "Blacklist Patterns" in labels
    assert "Lease States" in labels


def test_analysis_info_contains_split_config_rows_when_present(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Analysis Info sheet contains MigrationSplitConfig rows when split_config is provided."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
        split_config=minimal_scenario_suite.migration_split_used,
    )
    ws = wb["Analysis Info"]
    rows = _sheet_values(ws)
    labels = [str(r[0]).strip() for r in rows if r]
    assert "NIOSX Members" in labels
    assert "Default Group" in labels
    assert "Assignment Source" in labels


def test_analysis_info_no_split_config_rows_when_absent(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Analysis Info sheet omits MigrationSplitConfig rows when split_config is None."""
    # Build a scenario suite without split config
    current_grid = ScenarioResult(
        name="current_grid",
        formula_name="NIOS Object (DDI/50 + IPs/25 + Assets/13)",
        ddi_count=1000,
        active_ip_count=5000,
        asset_count=0,
        token_total=220.0,
    )
    full_migration = ScenarioResult(
        name="full_migration",
        formula_name="UDDI native (DDI/25 + IPs/13 + Assets/3)",
        ddi_count=1000,
        active_ip_count=5000,
        asset_count=0,
        token_total=424.6,
    )
    suite_no_split = ScenarioSuite(
        current_grid=current_grid,
        full_migration=full_migration,
        hybrid_uddi=None,
        member_attribution=[],
        migration_split_used=None,
    )
    from cloud_usage.nios.output import write_nios_xlsx_report

    out = tmp_path / "no_split.xlsx"
    write_nios_xlsx_report(
        filepath=str(out),
        integrity_report=minimal_integrity_report,
        count_result=minimal_count_result,
        scenario_suite=suite_no_split,
        filter_config=minimal_filter_config,
        split_config=None,
        analysis_timestamp="2026-03-02 10:00:00 UTC",
        member_map=minimal_member_map,
        ip_by_type=minimal_ip_by_type,
    )
    wb = openpyxl.load_workbook(str(out))
    ws = wb["Analysis Info"]
    rows = _sheet_values(ws)
    labels = [str(r[0]).strip() for r in rows if r]
    assert "NIOSX Members" not in labels


def test_analysis_info_contains_nios_object_formula_row(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Analysis Info sheet contains 'NIOS Object Formula' row with divisors."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Analysis Info"]
    rows = _sheet_values(ws)
    row = _find_row_by_label(rows, "NIOS Object Formula")
    assert row is not None
    value = str(row[1])
    assert "50" in value and "25" in value and "13" in value


def test_analysis_info_contains_uddi_native_formula_row(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Analysis Info sheet contains 'UDDI Native Formula' row with divisors."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Analysis Info"]
    rows = _sheet_values(ws)
    row = _find_row_by_label(rows, "UDDI Native Formula")
    assert row is not None
    value = str(row[1])
    assert "25" in value and "13" in value and "3" in value


def test_analysis_info_contains_rounding_note(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Analysis Info sheet contains a rounding note row."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Analysis Info"]
    all_text = " ".join(
        str(c.value) for row in ws.iter_rows(values_only=False) for c in row if c.value
    )
    assert "rounded" in all_text.lower() and "integer" in all_text.lower()


# ---------------------------------------------------------------------------
# Sheet 2: Object Counters
# ---------------------------------------------------------------------------


def test_object_counters_sheet_index(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Object Counters sheet is at index 1."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    assert wb.sheetnames[1] == "Object Counters"


def test_object_counters_has_21_data_rows(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Object Counters sheet has exactly 21 data rows (one per NiosFamily), plus header."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Object Counters"]
    rows = _sheet_values(ws)
    # Subtract 1 for header row
    data_rows = rows[1:]
    assert len(data_rows) == 21


def test_object_counters_ddi_families_marked_yes(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """DDI families show 'Yes' in Counted in UDDI column."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Object Counters"]
    rows = _sheet_values(ws)
    # Find dns_record_a row (should be Yes)
    row = _find_row_by_label(rows, NiosFamily.DNS_RECORD_A)
    assert row is not None
    assert str(row[2]).strip() == "Yes"


def test_object_counters_member_family_marked_no_metadata(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """MEMBER family shows 'No' in Counted in UDDI with 'Metadata only' reason."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Object Counters"]
    rows = _sheet_values(ws)
    row = _find_row_by_label(rows, NiosFamily.MEMBER)
    assert row is not None
    assert str(row[2]).strip() == "No"
    assert "Metadata only" in str(row[3])


def test_object_counters_lease_family_marked_no_active_ip(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """LEASE family shows 'No' with 'Active IP source only' reason."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Object Counters"]
    rows = _sheet_values(ws)
    row = _find_row_by_label(rows, NiosFamily.LEASE)
    assert row is not None
    assert str(row[2]).strip() == "No"
    assert "Active IP source only" in str(row[3])


def test_object_counters_count_matches_integrity_report(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Object count column matches IntegrityReport.families_found value."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Object Counters"]
    rows = _sheet_values(ws)
    row = _find_row_by_label(rows, NiosFamily.DNS_RECORD_A)
    assert row is not None
    # families_found[dns_record_a] = 3000
    assert int(row[1]) == 3000


# ---------------------------------------------------------------------------
# Sheet 3: DDI Objects
# ---------------------------------------------------------------------------


def test_ddi_objects_sheet_index(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """DDI Objects sheet is at index 2."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    assert wb.sheetnames[2] == "DDI Objects"


def test_ddi_objects_header_columns(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """DDI Objects sheet has expected header columns."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["DDI Objects"]
    header = [c.value for c in ws[1] if c.value]
    assert "Object Family" in header
    assert "Object Count" in header
    assert any("NIOS" in str(h) for h in header)
    assert any("UDDI" in str(h) for h in header)


def test_ddi_objects_token_computation(
    tmp_path,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """For dns_record_a with count=3000: NIOS tokens = round(3000/50)=60, UDDI = round(3000/25)=120."""
    # Build integrity report with known count
    families_found = {f: 0 for f in [
        NiosFamily.MEMBER, NiosFamily.NETWORK, NiosFamily.LEASE, NiosFamily.FIXED_ADDRESS,
        NiosFamily.HOST_ADDRESS, NiosFamily.DNS_ZONE, NiosFamily.DNS_RECORD_A, NiosFamily.DNS_RECORD_AAAA,
        NiosFamily.DNS_RECORD_CNAME, NiosFamily.DNS_RECORD_MX, NiosFamily.DNS_RECORD_NS,
        NiosFamily.DNS_RECORD_PTR, NiosFamily.DNS_RECORD_SOA, NiosFamily.DNS_RECORD_SRV,
        NiosFamily.DNS_RECORD_TXT, NiosFamily.HOST_OBJECT, NiosFamily.HOST_ALIAS,
        NiosFamily.DHCP_RANGE, NiosFamily.EXCLUSION_RANGE, NiosFamily.NETWORK_CONTAINER,
        NiosFamily.NETWORK_VIEW,
    ]}
    families_found[NiosFamily.DNS_RECORD_A] = 3000
    integrity = IntegrityReport(
        families_found=families_found,
        warnings=[],
        nios_version=None,
        snapshot_date=None,
    )
    wb = _write_fixture(
        tmp_path, integrity, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["DDI Objects"]
    rows = _sheet_values(ws)
    row = _find_row_by_label(rows, NiosFamily.DNS_RECORD_A)
    assert row is not None
    assert int(row[1]) == 3000       # count
    assert int(row[2]) == 60          # NIOS tokens: 3000/50
    assert int(row[3]) == 120         # UDDI tokens: 3000/25


def test_ddi_objects_has_total_row(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """DDI Objects sheet has a total row."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["DDI Objects"]
    all_text = " ".join(str(c.value) for row in ws.iter_rows(values_only=False) for c in row if c.value)
    assert "total" in all_text.lower()


# ---------------------------------------------------------------------------
# Sheet 4: Active IP by Type
# ---------------------------------------------------------------------------


def test_active_ip_sheet_index(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Active IP by Type sheet is at index 3."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    assert wb.sheetnames[3] == "Active IP by Type"


def test_active_ip_has_source_rows(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Active IP by Type has rows for DHCP Leases, Fixed Addresses, Host Addresses, Network Reservations."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Active IP by Type"]
    all_text = " ".join(str(c.value) for row in ws.iter_rows(values_only=False) for c in row if c.value)
    assert "DHCP" in all_text or "Lease" in all_text
    assert "Fixed" in all_text
    assert "Host" in all_text
    assert "Reservation" in all_text


def test_active_ip_grand_total_uses_grid_counts(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Grand Total row shows grid_counts.active_ip_count (5000), not sum of per-source rows."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Active IP by Type"]
    rows = _sheet_values(ws)
    grand_total_row = None
    for row in rows:
        if row and "grand total" in str(row[0]).lower():
            grand_total_row = row
            break
    assert grand_total_row is not None
    # grid_counts.active_ip_count = 5000
    assert int(grand_total_row[1]) == 5000


def test_active_ip_per_source_counts(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Per-source rows show counts from ip_by_type dict."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Active IP by Type"]
    all_values = [c.value for row in ws.iter_rows(values_only=False) for c in row if c.value is not None]
    # ip_by_type = {"leases": 3000, "fixed": 200, "host": 150, "reservations": 50}
    assert 3000 in all_values
    assert 200 in all_values
    assert 150 in all_values
    assert 50 in all_values


# ---------------------------------------------------------------------------
# Sheet 5: Scenario Comparison
# ---------------------------------------------------------------------------


def test_scenario_comparison_sheet_index(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Scenario Comparison sheet is at index 4."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    assert wb.sheetnames[4] == "Scenario Comparison"


def test_scenario_comparison_column_headers(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Scenario Comparison has 3 column headers: Current Grid, Hybrid UDDI, Full Migration."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Scenario Comparison"]
    header_row = [c.value for c in ws[1] if c.value]
    header_text = " ".join(str(h) for h in header_row)
    assert "Current Grid" in header_text
    assert "Hybrid UDDI" in header_text
    assert "Full Migration" in header_text


def test_scenario_comparison_row_labels(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Scenario Comparison has 5 row labels: DDI Objects, Active IPs, Assets, Formula, Token Total."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Scenario Comparison"]
    col_a = [c.value for c in ws["A"] if c.value]
    col_a_text = " ".join(str(v) for v in col_a)
    assert "DDI" in col_a_text
    assert "IP" in col_a_text
    assert "Asset" in col_a_text
    assert "Formula" in col_a_text
    assert "Token" in col_a_text


def test_scenario_comparison_current_grid_token_total(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Current Grid token total is round(220.0) = 220."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Scenario Comparison"]
    all_values = [c.value for row in ws.iter_rows(values_only=False) for c in row if c.value is not None]
    assert 220 in all_values


def test_scenario_comparison_full_migration_token_total(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Full Migration token total is round(424.6) = 425."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Scenario Comparison"]
    all_values = [c.value for row in ws.iter_rows(values_only=False) for c in row if c.value is not None]
    assert 425 in all_values


def test_scenario_comparison_hybrid_none_greyed(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """When hybrid_uddi is None, Hybrid UDDI column has 'No migration split provided' note."""
    current_grid = ScenarioResult(
        name="current_grid",
        formula_name="NIOS Object (DDI/50 + IPs/25 + Assets/13)",
        ddi_count=1000,
        active_ip_count=5000,
        asset_count=0,
        token_total=220.0,
    )
    full_migration = ScenarioResult(
        name="full_migration",
        formula_name="UDDI native (DDI/25 + IPs/13 + Assets/3)",
        ddi_count=1000,
        active_ip_count=5000,
        asset_count=0,
        token_total=424.6,
    )
    suite_no_split = ScenarioSuite(
        current_grid=current_grid,
        full_migration=full_migration,
        hybrid_uddi=None,
        member_attribution=[],
        migration_split_used=None,
    )
    from cloud_usage.nios.output import write_nios_xlsx_report

    out = tmp_path / "no_hybrid.xlsx"
    write_nios_xlsx_report(
        filepath=str(out),
        integrity_report=minimal_integrity_report,
        count_result=minimal_count_result,
        scenario_suite=suite_no_split,
        filter_config=minimal_filter_config,
        split_config=None,
        analysis_timestamp="2026-03-02 10:00:00 UTC",
        member_map=minimal_member_map,
        ip_by_type=minimal_ip_by_type,
    )
    wb = openpyxl.load_workbook(str(out))
    ws = wb["Scenario Comparison"]
    all_text = " ".join(str(c.value) for row in ws.iter_rows(values_only=False) for c in row if c.value)
    assert "No migration split provided" in all_text


def test_scenario_comparison_hybrid_token_total_when_present(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """When hybrid_uddi is present, Hybrid UDDI shows round(combined_total)."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Scenario Comparison"]
    expected = round(minimal_scenario_suite.hybrid_uddi.combined_total)
    all_values = [c.value for row in ws.iter_rows(values_only=False) for c in row if c.value is not None]
    assert expected in all_values


# ---------------------------------------------------------------------------
# Sheet 6: Member Attribution
# ---------------------------------------------------------------------------


def test_member_attribution_sheet_index(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Member Attribution sheet is at index 5."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    assert wb.sheetnames[5] == "Member Attribution"


def test_member_attribution_header_columns(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Member Attribution header contains expected columns."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Member Attribution"]
    header = [c.value for c in ws[1] if c.value]
    header_text = " ".join(str(h) for h in header)
    assert "Virtual OID" in header_text
    assert "Hostname" in header_text
    assert "Group" in header_text
    assert "Lease Count" in header_text or "Lease" in header_text
    assert "DDI" in header_text
    assert "IP" in header_text
    assert "Token" in header_text


def test_member_attribution_one_row_per_member(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Member Attribution has one data row per MemberScenarioRow."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Member Attribution"]
    rows = _sheet_values(ws)
    data_rows = rows[1:]  # skip header
    assert len(data_rows) == len(minimal_scenario_suite.member_attribution)


def test_member_attribution_virtual_oid_populated(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Virtual OID column is populated via inverted member_map lookup."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Member Attribution"]
    rows = _sheet_values(ws)
    # All virtual OID values (col 0) in data rows
    oid_values = [str(r[0]) for r in rows[1:] if r]
    # member-a.example.com -> oid "101"; member-b.example.com -> oid "102"
    assert "101" in oid_values
    assert "102" in oid_values


def test_member_attribution_virtual_oid_na_fallback(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_filter_config,
    minimal_ip_by_type,
):
    """Virtual OID column shows 'N/A' for hostnames not in member_map."""
    # Create scenario suite with a member not in the member_map
    current_grid = ScenarioResult(
        name="current_grid",
        formula_name="NIOS Object (DDI/50 + IPs/25 + Assets/13)",
        ddi_count=100,
        active_ip_count=500,
        asset_count=0,
        token_total=22.0,
    )
    full_migration = ScenarioResult(
        name="full_migration",
        formula_name="UDDI native (DDI/25 + IPs/13 + Assets/3)",
        ddi_count=100,
        active_ip_count=500,
        asset_count=0,
        token_total=42.5,
    )
    unknown_member_row = MemberScenarioRow(
        member_hostname="unknown-host.example.com",  # NOT in member_map
        group="nios",
        ddi_count=100,
        active_ip_count=500,
        asset_count=0,
        token_contribution=22.0,
    )
    suite = ScenarioSuite(
        current_grid=current_grid,
        full_migration=full_migration,
        hybrid_uddi=None,
        member_attribution=[unknown_member_row],
        migration_split_used=None,
    )
    from cloud_usage.nios.output import write_nios_xlsx_report

    out = tmp_path / "na_fallback.xlsx"
    write_nios_xlsx_report(
        filepath=str(out),
        integrity_report=minimal_integrity_report,
        count_result=minimal_count_result,
        scenario_suite=suite,
        filter_config=minimal_filter_config,
        split_config=None,
        analysis_timestamp="2026-03-02 10:00:00 UTC",
        member_map={"101": "some-other-host.example.com"},  # unknown-host NOT here
        ip_by_type=minimal_ip_by_type,
    )
    wb = openpyxl.load_workbook(str(out))
    ws = wb["Member Attribution"]
    rows = _sheet_values(ws)
    oid_values = [str(r[0]) for r in rows[1:] if r]
    assert "N/A" in oid_values


def test_member_attribution_token_contribution_rounded(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Token Contribution column shows round(token_contribution)."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Member Attribution"]
    rows = _sheet_values(ws)
    # member-a: token_contribution=50.0, round=50
    # Find the row for member-a
    member_a_row = None
    for row in rows[1:]:
        if row and "member-a.example.com" in str(row[1]):
            member_a_row = row
            break
    assert member_a_row is not None
    # Token contribution is last column
    assert int(member_a_row[-1]) == 50


def test_member_attribution_lease_count_populated(
    tmp_path,
    minimal_integrity_report,
    minimal_count_result,
    minimal_scenario_suite,
    minimal_filter_config,
    minimal_member_map,
    minimal_ip_by_type,
):
    """Lease Count column is populated from CountResult.member_counts."""
    wb = _write_fixture(
        tmp_path, minimal_integrity_report, minimal_count_result,
        minimal_scenario_suite, minimal_filter_config, minimal_member_map, minimal_ip_by_type,
    )
    ws = wb["Member Attribution"]
    rows = _sheet_values(ws)
    # member-a has lease_count=2000 in minimal_count_result
    member_a_row = None
    for row in rows[1:]:
        if row and "member-a.example.com" in str(row[1]):
            member_a_row = row
            break
    assert member_a_row is not None
    # Lease Count is col index 3 (0-based: Virtual OID, Hostname, Group, Lease Count, ...)
    assert int(member_a_row[3]) == 2000


# ---------------------------------------------------------------------------
# Import smoke test: run_nios_analysis (Plan 13-02)
# ---------------------------------------------------------------------------


def test_imports_run_nios_analysis():
    """run_nios_analysis is importable from cloud_usage.nios.output."""
    from cloud_usage.nios.output import run_nios_analysis  # noqa: F401

    assert callable(run_nios_analysis)


def test_run_nios_analysis_in_output_all():
    """run_nios_analysis appears in cloud_usage.nios.output.__all__."""
    import cloud_usage.nios.output as out_mod

    assert "run_nios_analysis" in out_mod.__all__


def test_all_public_names_are_callable():
    """All names in cloud_usage.nios.output.__all__ are callable."""
    import cloud_usage.nios.output as out_mod

    for name in out_mod.__all__:
        obj = getattr(out_mod, name)
        assert callable(obj), f"{name} in __all__ is not callable"


# ---------------------------------------------------------------------------
# _count_ip_by_type unit tests (Plan 13-02)
# ---------------------------------------------------------------------------


def _make_nios_object(family: str, raw_attrs: dict) -> "NiosObject":
    return NiosObject(family=family, member_hostname=None, raw_attrs=raw_attrs)


def test_count_ip_by_type_empty_stream():
    """Empty stream returns all-zero counts."""
    from cloud_usage.nios.output import _count_ip_by_type

    result = _count_ip_by_type(iter([]), lease_states={"active"})
    assert result == {"leases": 0, "fixed": 0, "host": 0, "reservations": 0}


def test_count_ip_by_type_lease_active_increments():
    """LEASE with binding_state 'active' and ip_address increments leases by 1."""
    from cloud_usage.nios.output import _count_ip_by_type

    obj = _make_nios_object(NiosFamily.LEASE, {"binding_state": "active", "ip_address": "10.0.0.1"})
    result = _count_ip_by_type(iter([obj]), lease_states={"active"})
    assert result["leases"] == 1


def test_count_ip_by_type_lease_expired_not_counted():
    """LEASE with binding_state 'expired' is NOT counted when lease_states={'active'}."""
    from cloud_usage.nios.output import _count_ip_by_type

    obj = _make_nios_object(NiosFamily.LEASE, {"binding_state": "expired", "ip_address": "10.0.0.1"})
    result = _count_ip_by_type(iter([obj]), lease_states={"active"})
    assert result["leases"] == 0


def test_count_ip_by_type_fixed_address_increments():
    """FIXED_ADDRESS with ip_address increments fixed by 1."""
    from cloud_usage.nios.output import _count_ip_by_type

    obj = _make_nios_object(NiosFamily.FIXED_ADDRESS, {"ip_address": "10.0.0.2"})
    result = _count_ip_by_type(iter([obj]), lease_states={"active"})
    assert result["fixed"] == 1


def test_count_ip_by_type_host_address_uses_address_key():
    """HOST_ADDRESS with raw_attrs['address'] increments host by 1."""
    from cloud_usage.nios.output import _count_ip_by_type

    obj = _make_nios_object(NiosFamily.HOST_ADDRESS, {"address": "10.0.0.3"})
    result = _count_ip_by_type(iter([obj]), lease_states={"active"})
    assert result["host"] == 1


def test_count_ip_by_type_host_address_wrong_key_not_counted():
    """HOST_ADDRESS with raw_attrs['ip_address'] (wrong key) does NOT increment host."""
    from cloud_usage.nios.output import _count_ip_by_type

    obj = _make_nios_object(NiosFamily.HOST_ADDRESS, {"ip_address": "10.0.0.3"})
    result = _count_ip_by_type(iter([obj]), lease_states={"active"})
    assert result["host"] == 0


def test_count_ip_by_type_network_cidr_increments_by_2():
    """NETWORK object with valid cidr increments reservations by 2 (network + broadcast)."""
    from cloud_usage.nios.output import _count_ip_by_type

    obj = _make_nios_object(NiosFamily.NETWORK, {"cidr": "192.168.1.0/24"})
    result = _count_ip_by_type(iter([obj]), lease_states={"active"})
    assert result["reservations"] == 2


def test_count_ip_by_type_same_ip_counted_in_both_sources():
    """Same IP appearing as both LEASE and FIXED_ADDRESS is counted in BOTH (no cross-source dedup)."""
    from cloud_usage.nios.output import _count_ip_by_type

    lease_obj = _make_nios_object(NiosFamily.LEASE, {"binding_state": "active", "ip_address": "10.0.0.1"})
    fixed_obj = _make_nios_object(NiosFamily.FIXED_ADDRESS, {"ip_address": "10.0.0.1"})
    result = _count_ip_by_type(iter([lease_obj, fixed_obj]), lease_states={"active"})
    assert result["leases"] == 1
    assert result["fixed"] == 1


def test_count_ip_by_type_malformed_cidr_skipped():
    """NETWORK object with malformed CIDR is skipped without raising."""
    from cloud_usage.nios.output import _count_ip_by_type

    obj = _make_nios_object(NiosFamily.NETWORK, {"cidr": "not-a-cidr"})
    result = _count_ip_by_type(iter([obj]), lease_states={"active"})
    assert result["reservations"] == 0


# ---------------------------------------------------------------------------
# run_nios_analysis integration tests (Plan 13-02)
# ---------------------------------------------------------------------------


def _make_minimal_count_result_for_runner() -> CountResult:
    """Minimal CountResult for runner integration tests."""
    grid = MemberCounts(
        member_hostname="__grid__",
        ddi_count=100,
        active_ip_count=500,
        lease_count=800,
        asset_count=0,
    )
    return CountResult(member_counts=[], grid_counts=grid)


def _make_minimal_scenario_suite_for_runner() -> ScenarioSuite:
    """Minimal ScenarioSuite without hybrid for runner integration tests."""
    current_grid = ScenarioResult(
        name="current_grid",
        formula_name="NIOS Object (DDI/50 + IPs/25 + Assets/13)",
        ddi_count=100,
        active_ip_count=500,
        asset_count=0,
        token_total=22.0,
    )
    full_migration = ScenarioResult(
        name="full_migration",
        formula_name="UDDI native (DDI/25 + IPs/13 + Assets/3)",
        ddi_count=100,
        active_ip_count=500,
        asset_count=0,
        token_total=42.5,
    )
    return ScenarioSuite(
        current_grid=current_grid,
        full_migration=full_migration,
        hybrid_uddi=None,
        member_attribution=[],
        migration_split_used=None,
    )


def _make_minimal_integrity_report_for_runner() -> IntegrityReport:
    families = {f: 0 for f in _ALL_NIOS_FAMILIES()}
    families[NiosFamily.DNS_RECORD_A] = 100
    return IntegrityReport(
        families_found=families,
        warnings=[],
        nios_version="9.0.6-test",
        snapshot_date="2025-08-12",
    )


def _ALL_NIOS_FAMILIES() -> list[str]:
    return [
        NiosFamily.MEMBER, NiosFamily.NETWORK, NiosFamily.LEASE, NiosFamily.FIXED_ADDRESS,
        NiosFamily.HOST_ADDRESS, NiosFamily.DNS_ZONE, NiosFamily.DNS_RECORD_A, NiosFamily.DNS_RECORD_AAAA,
        NiosFamily.DNS_RECORD_CNAME, NiosFamily.DNS_RECORD_MX, NiosFamily.DNS_RECORD_NS,
        NiosFamily.DNS_RECORD_PTR, NiosFamily.DNS_RECORD_SOA, NiosFamily.DNS_RECORD_SRV,
        NiosFamily.DNS_RECORD_TXT, NiosFamily.HOST_OBJECT, NiosFamily.HOST_ALIAS,
        NiosFamily.DHCP_RANGE, NiosFamily.EXCLUSION_RANGE, NiosFamily.NETWORK_CONTAINER,
        NiosFamily.NETWORK_VIEW,
    ]


@pytest.fixture()
def mock_pipeline(tmp_path):
    """Mock all pipeline callables for run_nios_analysis integration tests."""
    from unittest.mock import patch, MagicMock

    minimal_integrity = _make_minimal_integrity_report_for_runner()
    minimal_count = _make_minimal_count_result_for_runner()
    minimal_suite = _make_minimal_scenario_suite_for_runner()

    patches = [
        patch("cloud_usage.nios.output.run_nios_analysis.__globals__"),
    ]

    # Use contextlib to patch the imports inside run_nios_analysis
    with patch("cloud_usage.nios.parser.inspect_backup", return_value=minimal_integrity) as mock_inspect, \
         patch("cloud_usage.nios.parser.parse_backup", return_value=iter([])) as mock_parse, \
         patch("cloud_usage.nios.parser.get_member_map", return_value={}) as mock_member_map, \
         patch("cloud_usage.nios.filter.filter_objects", return_value=iter([])) as mock_filter, \
         patch("cloud_usage.nios.counter.count_objects", return_value=minimal_count) as mock_count, \
         patch("cloud_usage.nios.scenarios.compute_scenarios", return_value=minimal_suite) as mock_scenarios:
        yield {
            "inspect_backup": mock_inspect,
            "parse_backup": mock_parse,
            "get_member_map": mock_member_map,
            "filter_objects": mock_filter,
            "count_objects": mock_count,
            "compute_scenarios": mock_scenarios,
            "tmp_path": tmp_path,
            "integrity": minimal_integrity,
            "count_result": minimal_count,
            "scenario_suite": minimal_suite,
        }


def _patch_runner():
    """Context manager that patches all pipeline callables inside run_nios_analysis.

    run_nios_analysis uses local imports inside the function body, so we patch
    the source modules directly (not cloud_usage.nios.output.*).
    """
    from unittest.mock import patch
    from contextlib import ExitStack

    minimal_integrity = _make_minimal_integrity_report_for_runner()
    minimal_count = _make_minimal_count_result_for_runner()
    minimal_suite = _make_minimal_scenario_suite_for_runner()

    return ExitStack(), {
        "inspect_backup": patch("cloud_usage.nios.parser._inspect.inspect_backup", return_value=minimal_integrity),
        "parse_backup": patch("cloud_usage.nios.parser._parse.parse_backup", return_value=iter([])),
        "get_member_map": patch("cloud_usage.nios.parser._member_map._build_member_map", return_value={}),
        "filter_objects": patch("cloud_usage.nios.filter.filter_objects", return_value=iter([])),
        "count_objects": patch("cloud_usage.nios.counter.count_objects", return_value=minimal_count),
        "compute_scenarios": patch("cloud_usage.nios.scenarios.compute_scenarios", return_value=minimal_suite),
    }


def _run_analysis_with_mocks(backup_path: str, filter_cfg, output_path: str) -> str:
    """Run run_nios_analysis with all pipeline callables mocked."""
    from cloud_usage.nios.output import run_nios_analysis

    minimal_integrity = _make_minimal_integrity_report_for_runner()
    minimal_count = _make_minimal_count_result_for_runner()
    minimal_suite = _make_minimal_scenario_suite_for_runner()

    # Patch at the source module level since run_nios_analysis uses local imports
    with patch("cloud_usage.nios.parser._inspect.inspect_backup", return_value=minimal_integrity), \
         patch("cloud_usage.nios.parser._parse.parse_backup", return_value=iter([])), \
         patch("cloud_usage.nios.parser._member_map._build_member_map", return_value={}), \
         patch("cloud_usage.nios.filter.filter_objects", return_value=iter([])), \
         patch("cloud_usage.nios.counter.count_objects", return_value=minimal_count), \
         patch("cloud_usage.nios.scenarios.compute_scenarios", return_value=minimal_suite):
        return run_nios_analysis(backup_path, filter_cfg, output_path=output_path)


def test_run_nios_analysis_returns_str(tmp_path):
    """run_nios_analysis returns a str filepath."""
    from cloud_usage.nios.filter import FilterConfig

    out = str(tmp_path / "out.xlsx")
    filter_cfg = FilterConfig(whitelist=(), blacklist=(), lease_states=("active",))

    result = _run_analysis_with_mocks("/fake/backup.tar.gz", filter_cfg, out)
    assert isinstance(result, str)


def test_run_nios_analysis_custom_output_path(tmp_path):
    """run_nios_analysis with custom output_path writes to specified path."""
    from cloud_usage.nios.filter import FilterConfig

    out = str(tmp_path / "custom_out.xlsx")
    filter_cfg = FilterConfig(whitelist=(), blacklist=(), lease_states=("active",))

    result = _run_analysis_with_mocks("/fake/backup.tar.gz", filter_cfg, out)

    assert result == out
    assert os.path.exists(out)


def test_run_nios_analysis_produces_valid_xlsx(tmp_path):
    """run_nios_analysis produces a readable .xlsx file."""
    from cloud_usage.nios.filter import FilterConfig

    out = str(tmp_path / "valid.xlsx")
    filter_cfg = FilterConfig(whitelist=(), blacklist=(), lease_states=("active",))

    _run_analysis_with_mocks("/fake/backup.tar.gz", filter_cfg, out)

    wb = openpyxl.load_workbook(out)
    assert wb is not None


def test_run_nios_analysis_produces_6_sheets(tmp_path):
    """run_nios_analysis produces a workbook with 6 sheets."""
    from cloud_usage.nios.filter import FilterConfig

    out = str(tmp_path / "six_sheets.xlsx")
    filter_cfg = FilterConfig(whitelist=(), blacklist=(), lease_states=("active",))

    _run_analysis_with_mocks("/fake/backup.tar.gz", filter_cfg, out)

    wb = openpyxl.load_workbook(out)
    assert len(wb.sheetnames) == 6
