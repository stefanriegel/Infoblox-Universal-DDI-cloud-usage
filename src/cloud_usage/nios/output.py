"""NIOS Grid analysis XLS report writer and pipeline runner.

Provides:
- write_nios_xlsx_report(): produce a 6-sheet .xlsx from ScenarioSuite + CountResult +
  IntegrityReport + FilterConfig + ip_by_type dict.
- run_nios_analysis(): single-callable runner that wires the full
  parse->filter->count->scenarios->output pipeline.

Sheet order:
1. Analysis Info        -- metadata, filter config, formula constants, analysis timestamp
2. Object Counters      -- all 26 NiosFamily rows with raw counts and UDDI flag
3. DDI Objects          -- 22 DDI families with per-family NIOS/UDDI token contributions
4. Active IP by Type    -- per-source IP counts + grand total (deduped from grid_counts)
5. Scenario Comparison  -- 3-scenario side-by-side (Current Grid / Hybrid UDDI / Full Migration)
6. Member Attribution   -- per-member group assignment, counts, and token contributions

Design notes:
- Write-only (xlsxwriter), never read. Formats shared at workbook level.
- Formatting mirrors src/cloud_usage/output/xlsx_report.py exactly.
- Grand Total on Active IP by Type always comes from grid_counts.active_ip_count
  (authoritative deduped total). The per-source rows from ip_by_type are raw/overlapping.
- Token totals displayed as round(float) = integer per CONTEXT.md decision.
- _DDI_FAMILIES imported ONLY from counter.py (single source of truth).
- workbook.close() called ONLY in write_nios_xlsx_report(), never in sheet writers.
"""

from __future__ import annotations

from typing import Optional

import xlsxwriter

from cloud_usage.nios.counter import (
    CountResult,
    _DDI_FAMILIES,
    NIOS_DDI_DIVISOR,
    NIOS_IP_DIVISOR,
    NIOS_ASSET_DIVISOR,
    UDDI_DDI_DIVISOR,
    UDDI_IP_DIVISOR,
    UDDI_ASSET_DIVISOR,
)
from cloud_usage.nios.filter import FilterConfig
from cloud_usage.nios.scenarios import MigrationSplitConfig, ScenarioSuite
from cloud_usage.nios.schema import IntegrityReport, NiosFamily

__all__ = ["write_nios_xlsx_report", "run_nios_analysis"]


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Families NOT DDI-contributing with their reason strings for Object Counters sheet
_UDDI_FLAG_REASON: dict[str, str] = {
    NiosFamily.MEMBER:        "Metadata only",
    NiosFamily.LEASE:         "Active IP source only",
    NiosFamily.FIXED_ADDRESS: "Active IP source only",
    NiosFamily.HOST_ADDRESS:  "Active IP source only",
}

# All 21 families in display order for Object Counters sheet
_ALL_FAMILIES_ORDERED: list[str] = [
    NiosFamily.MEMBER,
    NiosFamily.NETWORK,
    NiosFamily.LEASE,
    NiosFamily.FIXED_ADDRESS,
    NiosFamily.HOST_ADDRESS,
    NiosFamily.DNS_ZONE,
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
    NiosFamily.DHCP_RANGE,
    NiosFamily.EXCLUSION_RANGE,
    NiosFamily.NETWORK_CONTAINER,
    NiosFamily.NETWORK_VIEW,
    # ---- DTC (DNS Traffic Control) — Phase 17: DTC-09 ----
    NiosFamily.DTC_LBDN,
    NiosFamily.DTC_POOL,
    NiosFamily.DTC_SERVER,
    NiosFamily.DTC_MONITOR,
    NiosFamily.DTC_TOPOLOGY,
]

# Human-readable display names for Object Counters sheet
_FAMILY_DISPLAY_NAMES: dict[str, str] = {
    NiosFamily.MEMBER:            "member",
    NiosFamily.NETWORK:           "network",
    NiosFamily.LEASE:             "lease",
    NiosFamily.FIXED_ADDRESS:     "fixed_address",
    NiosFamily.HOST_ADDRESS:      "host_address",
    NiosFamily.DNS_ZONE:          "dns_zone",
    NiosFamily.DNS_RECORD_A:      "dns_record_a",
    NiosFamily.DNS_RECORD_AAAA:   "dns_record_aaaa",
    NiosFamily.DNS_RECORD_CNAME:  "dns_record_cname",
    NiosFamily.DNS_RECORD_MX:     "dns_record_mx",
    NiosFamily.DNS_RECORD_NS:     "dns_record_ns",
    NiosFamily.DNS_RECORD_PTR:    "dns_record_ptr",
    NiosFamily.DNS_RECORD_SOA:    "dns_record_soa",
    NiosFamily.DNS_RECORD_SRV:    "dns_record_srv",
    NiosFamily.DNS_RECORD_TXT:    "dns_record_txt",
    NiosFamily.HOST_OBJECT:       "host_object",
    NiosFamily.HOST_ALIAS:        "host_alias",
    NiosFamily.DHCP_RANGE:        "dhcp_range",
    NiosFamily.EXCLUSION_RANGE:   "exclusion_range",
    NiosFamily.NETWORK_CONTAINER: "network_container",
    NiosFamily.NETWORK_VIEW:      "network_view",
    # ---- DTC (DNS Traffic Control) — Phase 17: DTC-09 ----
    NiosFamily.DTC_LBDN:      "dtc_lbdn",
    NiosFamily.DTC_POOL:      "dtc_pool",
    NiosFamily.DTC_SERVER:    "dtc_server",
    NiosFamily.DTC_MONITOR:   "dtc_monitor",
    NiosFamily.DTC_TOPOLOGY:  "dtc_topology",
}


# ---------------------------------------------------------------------------
# Public API: write_nios_xlsx_report
# ---------------------------------------------------------------------------

def write_nios_xlsx_report(
    filepath: str,
    integrity_report: IntegrityReport,
    count_result: CountResult,
    scenario_suite: ScenarioSuite,
    filter_config: FilterConfig,
    split_config: Optional[MigrationSplitConfig],
    analysis_timestamp: str,
    member_map: dict[str, str],
    ip_by_type: dict[str, int],
) -> str:
    """Generate a 6-sheet NIOS Grid analysis report as an .xlsx file.

    Creates a workbook with six sheets in this order:
    1. Analysis Info      - metadata, filter config verbatim, formula constants
    2. Object Counters    - all 26 NIOS families with raw counts and UDDI flag
    3. DDI Objects        - 17 DDI families with NIOS/UDDI token contributions per family
    4. Active IP by Type  - per-source IP counts + grand total (deduped)
    5. Scenario Comparison - 3-scenario side-by-side comparison
    6. Member Attribution  - per-member group assignment, lease count, counts, tokens

    Args:
        filepath: Output path for the .xlsx file.
        integrity_report: IntegrityReport with families_found counts, nios_version,
            snapshot_date, and warnings.
        count_result: CountResult with per-member counts and grid aggregate.
        scenario_suite: ScenarioSuite with all three scenarios and member attribution.
        filter_config: FilterConfig with whitelist/blacklist/lease_states (written verbatim).
        split_config: Optional MigrationSplitConfig written verbatim to Analysis Info.
            None if no migration split was configured.
        analysis_timestamp: ISO-style timestamp string for the Analysis Info sheet,
            e.g. "2026-03-02 10:00:00 UTC".
        member_map: virtual_oid -> hostname dict (from get_member_map()).
            Used to populate Virtual OID column in Member Attribution sheet.
        ip_by_type: Per-source IP counts dict with keys "leases", "fixed", "host",
            "reservations". Values are raw (potentially overlapping) counts.
            Grand Total on Active IP by Type uses grid_counts.active_ip_count instead.

    Returns:
        The filepath string passed in.
    """
    workbook = xlsxwriter.Workbook(filepath)

    # -- Define shared formats (mirrors xlsx_report.py pattern exactly) --
    header_fmt = workbook.add_format({
        "bold": True,
        "bg_color": "#4472C4",
        "font_color": "white",
        "border": 1,
        "text_wrap": True,
    })
    even_row_fmt = workbook.add_format({
        "bg_color": "#D9E2F3",
        "border": 1,
    })
    odd_row_fmt = workbook.add_format({
        "border": 1,
    })
    number_fmt = workbook.add_format({
        "border": 1,
        "num_format": "#,##0",
    })
    even_number_fmt = workbook.add_format({
        "bg_color": "#D9E2F3",
        "border": 1,
        "num_format": "#,##0",
    })
    total_row_fmt = workbook.add_format({
        "bold": True,
        "border": 1,
        "bg_color": "#E2EFDA",
    })
    total_number_fmt = workbook.add_format({
        "bold": True,
        "border": 1,
        "bg_color": "#E2EFDA",
        "num_format": "#,##0",
    })
    greyed_fmt = workbook.add_format({
        "border": 1,
        "font_color": "#808080",
        "bg_color": "#F2F2F2",
        "italic": True,
    })
    # Analysis Info sheet specific formats
    field_label_fmt = workbook.add_format({
        "bold": True,
        "bg_color": "#D9E2F3",
        "border": 1,
    })
    value_fmt = workbook.add_format({
        "border": 1,
        "text_wrap": True,
    })
    italic_fmt = workbook.add_format({
        "italic": True,
        "border": 1,
        "font_color": "#808080",
    })

    # -- Write all 6 sheets in order --
    _write_analysis_info_sheet(
        workbook, field_label_fmt, value_fmt,
        integrity_report, filter_config, split_config, analysis_timestamp,
    )
    _write_object_counters_sheet(
        workbook, header_fmt, even_row_fmt, odd_row_fmt, number_fmt, even_number_fmt,
        integrity_report,
    )
    _write_ddi_objects_sheet(
        workbook, header_fmt, even_row_fmt, odd_row_fmt, number_fmt, even_number_fmt,
        total_row_fmt, total_number_fmt, italic_fmt,
        integrity_report,
    )
    _write_active_ip_by_type_sheet(
        workbook, header_fmt, even_row_fmt, odd_row_fmt, number_fmt,
        total_row_fmt, total_number_fmt,
        ip_by_type, count_result.grid_counts,
    )
    _write_scenario_comparison_sheet(
        workbook, header_fmt, even_row_fmt, odd_row_fmt, number_fmt,
        total_number_fmt, greyed_fmt,
        scenario_suite,
    )
    _write_member_attribution_sheet(
        workbook, header_fmt, even_row_fmt, odd_row_fmt, number_fmt, even_number_fmt,
        scenario_suite, count_result, member_map,
    )

    workbook.close()
    return filepath


# ---------------------------------------------------------------------------
# Sheet 1: Analysis Info
# ---------------------------------------------------------------------------

def _write_analysis_info_sheet(
    workbook,
    field_label_fmt,
    value_fmt,
    integrity_report: IntegrityReport,
    filter_config: FilterConfig,
    split_config: Optional[MigrationSplitConfig],
    analysis_timestamp: str,
) -> None:
    """Write the Analysis Info sheet — two-column layout (Field | Value)."""
    ws = workbook.add_worksheet("Analysis Info")
    ws.set_column(0, 0, 30)
    ws.set_column(1, 1, 60)

    row = 0

    def write_row(label: str, value: str) -> None:
        nonlocal row
        ws.write(row, 0, label, field_label_fmt)
        ws.write(row, 1, value, value_fmt)
        row += 1

    # Backup metadata
    write_row("NIOS Version", integrity_report.nios_version or "(not available)")
    write_row("Backup Snapshot Date", integrity_report.snapshot_date or "(not available)")
    write_row("Analysis Timestamp", analysis_timestamp)

    # Filter config (verbatim)
    whitelist_str = ", ".join(filter_config.whitelist) if filter_config.whitelist else "(none)"
    blacklist_str = ", ".join(filter_config.blacklist) if filter_config.blacklist else "(none)"
    lease_states_str = ", ".join(filter_config.lease_states)
    write_row("Whitelist Patterns", whitelist_str)
    write_row("Blacklist Patterns", blacklist_str)
    write_row("Lease States", lease_states_str)

    # Migration split config (verbatim, only if provided)
    if split_config is not None:
        niosx_members_str = (
            ", ".join(split_config.niosx_members) if split_config.niosx_members else "(none)"
        )
        write_row("NIOSX Members", niosx_members_str)
        write_row("Default Group", split_config.default_group)
        write_row("Assignment Source", split_config.assignment_source)

    # Formula constants (built from imported divisor constants)
    nios_formula = (
        f"DDI / {NIOS_DDI_DIVISOR} + IPs / {NIOS_IP_DIVISOR} + Assets / {NIOS_ASSET_DIVISOR}"
    )
    uddi_formula = (
        f"DDI / {UDDI_DDI_DIVISOR} + IPs / {UDDI_IP_DIVISOR} + Assets / {UDDI_ASSET_DIVISOR}"
    )
    write_row("NIOS Object Formula", nios_formula)
    write_row("UDDI Native Formula", uddi_formula)

    # Rounding note
    rounding_note = (
        f"Token totals are rounded to the nearest integer for display. "
        f"Raw formula: DDI/{NIOS_DDI_DIVISOR} + IPs/{NIOS_IP_DIVISOR} + "
        f"Assets/{NIOS_ASSET_DIVISOR} (NIOS) or "
        f"DDI/{UDDI_DDI_DIVISOR} + IPs/{UDDI_IP_DIVISOR} + "
        f"Assets/{UDDI_ASSET_DIVISOR} (UDDI)."
    )
    ws.write(row, 0, "Rounding Note", field_label_fmt)
    ws.write(row, 1, rounding_note, value_fmt)
    row += 1


# ---------------------------------------------------------------------------
# Sheet 2: Object Counters
# ---------------------------------------------------------------------------

def _write_object_counters_sheet(
    workbook,
    header_fmt,
    even_fmt,
    odd_fmt,
    number_fmt,
    even_number_fmt,
    integrity_report: IntegrityReport,
) -> None:
    """Write Object Counters sheet — all 26 NiosFamily rows with counts and UDDI flag."""
    ws = workbook.add_worksheet("Object Counters")
    ws.freeze_panes(1, 0)
    ws.set_column(0, 0, 30)
    ws.set_column(1, 1, 15)
    ws.set_column(2, 2, 18)
    ws.set_column(3, 3, 35)

    # Header
    ws.write(0, 0, "Object Family", header_fmt)
    ws.write(0, 1, "Object Count", header_fmt)
    ws.write(0, 2, "Counted in UDDI", header_fmt)
    ws.write(0, 3, "Reason", header_fmt)

    for i, family in enumerate(_ALL_FAMILIES_ORDERED):
        data_row = i + 1
        is_even = (i % 2 == 0)
        text_fmt = even_fmt if is_even else odd_fmt
        num_fmt = even_number_fmt if is_even else number_fmt

        count = integrity_report.families_found.get(family, 0)
        in_ddi = family in _DDI_FAMILIES
        uddi_flag = "Yes" if in_ddi else "No"
        reason = "" if in_ddi else _UDDI_FLAG_REASON.get(family, "Not a DDI or IP object")

        ws.write(data_row, 0, family, text_fmt)
        ws.write(data_row, 1, count, num_fmt)
        ws.write(data_row, 2, uddi_flag, text_fmt)
        ws.write(data_row, 3, reason, text_fmt)


# ---------------------------------------------------------------------------
# Sheet 3: DDI Objects
# ---------------------------------------------------------------------------

def _write_ddi_objects_sheet(
    workbook,
    header_fmt,
    even_fmt,
    odd_fmt,
    number_fmt,
    even_number_fmt,
    total_row_fmt,
    total_number_fmt,
    italic_fmt,
    integrity_report: IntegrityReport,
) -> None:
    """Write DDI Objects sheet — 17 DDI families with NIOS/UDDI token contributions."""
    ws = workbook.add_worksheet("DDI Objects")
    ws.freeze_panes(1, 0)
    ws.set_column(0, 0, 30)
    ws.set_column(1, 1, 15)
    ws.set_column(2, 2, 28)
    ws.set_column(3, 3, 28)

    # Header
    ws.write(0, 0, "Object Family", header_fmt)
    ws.write(0, 1, "Object Count", header_fmt)
    ws.write(0, 2, f"NIOS Object Tokens (DDI/{NIOS_DDI_DIVISOR})", header_fmt)
    ws.write(0, 3, f"UDDI Native Tokens (DDI/{UDDI_DDI_DIVISOR})", header_fmt)

    # Only DDI families, in _ALL_FAMILIES_ORDERED order
    ddi_families = [f for f in _ALL_FAMILIES_ORDERED if f in _DDI_FAMILIES]

    total_count = 0
    total_nios_tokens = 0
    total_uddi_tokens = 0

    for i, family in enumerate(ddi_families):
        data_row = i + 1
        is_even = (i % 2 == 0)
        text_fmt = even_fmt if is_even else odd_fmt
        num_fmt = even_number_fmt if is_even else number_fmt

        count = integrity_report.families_found.get(family, 0)
        nios_tokens = round(count / NIOS_DDI_DIVISOR)
        uddi_tokens = round(count / UDDI_DDI_DIVISOR)

        total_count += count
        total_nios_tokens += nios_tokens
        total_uddi_tokens += uddi_tokens

        ws.write(data_row, 0, family, text_fmt)
        ws.write(data_row, 1, count, num_fmt)
        ws.write(data_row, 2, nios_tokens, num_fmt)
        ws.write(data_row, 3, uddi_tokens, num_fmt)

    # Total row
    total_row = len(ddi_families) + 1
    ws.write(total_row, 0, "Total", total_row_fmt)
    ws.write(total_row, 1, total_count, total_number_fmt)
    ws.write(total_row, 2, total_nios_tokens, total_number_fmt)
    ws.write(total_row, 3, total_uddi_tokens, total_number_fmt)

    # Footnote row
    footnote_row = total_row + 1
    ws.write(
        footnote_row, 0,
        "Note: Token contributions shown per DDI object family only. "
        "Active IP and Asset contributions are shown in Scenario Comparison.",
        italic_fmt,
    )


# ---------------------------------------------------------------------------
# Sheet 4: Active IP by Type
# ---------------------------------------------------------------------------

def _write_active_ip_by_type_sheet(
    workbook,
    header_fmt,
    even_fmt,
    odd_fmt,
    number_fmt,
    total_row_fmt,
    total_number_fmt,
    ip_by_type: dict[str, int],
    grid_counts,
) -> None:
    """Write Active IP by Type sheet — per-source raw counts + deduped grand total."""
    ws = workbook.add_worksheet("Active IP by Type")
    ws.freeze_panes(1, 0)
    ws.set_column(0, 0, 35)
    ws.set_column(1, 1, 20)

    # Header
    ws.write(0, 0, "IP Source", header_fmt)
    ws.write(0, 1, "Count", header_fmt)

    sources = [
        ("DHCP Leases (active)", ip_by_type.get("leases", 0)),
        ("Fixed Addresses", ip_by_type.get("fixed", 0)),
        ("Host Addresses", ip_by_type.get("host", 0)),
        ("Network Reservations", ip_by_type.get("reservations", 0)),
    ]

    for i, (label, count) in enumerate(sources):
        data_row = i + 1
        is_even = (i % 2 == 0)
        text_fmt = even_fmt if is_even else odd_fmt
        num_fmt_row = number_fmt  # Use standard number format for source rows

        ws.write(data_row, 0, label, text_fmt)
        ws.write(data_row, 1, count, num_fmt_row)

    # Grand Total — authoritative deduped total from grid_counts (NOT sum of per-source)
    grand_total_row = len(sources) + 1
    ws.write(grand_total_row, 0, "Grand Total (deduplicated)", total_row_fmt)
    ws.write(grand_total_row, 1, grid_counts.active_ip_count, total_number_fmt)


# ---------------------------------------------------------------------------
# Sheet 5: Scenario Comparison
# ---------------------------------------------------------------------------

def _write_scenario_comparison_sheet(
    workbook,
    header_fmt,
    even_fmt,
    odd_fmt,
    number_fmt,
    total_number_fmt,
    greyed_fmt,
    scenario_suite: ScenarioSuite,
) -> None:
    """Write Scenario Comparison sheet — 3-scenario side-by-side comparison."""
    ws = workbook.add_worksheet("Scenario Comparison")
    ws.set_column(0, 0, 18)
    ws.set_column(1, 1, 20)
    ws.set_column(2, 2, 20)
    ws.set_column(3, 3, 20)

    # Header row: blank + 3 scenario columns
    ws.write(0, 0, "", header_fmt)
    ws.write(0, 1, "Current Grid", header_fmt)
    ws.write(0, 2, "Hybrid UDDI", header_fmt)
    ws.write(0, 3, "Full Migration", header_fmt)

    cg = scenario_suite.current_grid
    fm = scenario_suite.full_migration
    hybrid = scenario_suite.hybrid_uddi

    # Row labels and data
    row_labels = [
        "DDI Objects",
        "Active IPs",
        "Assets",
        "Formula",
        "Token Total",
    ]

    current_grid_values = [
        cg.ddi_count,
        cg.active_ip_count,
        cg.asset_count,
        cg.formula_name,
        round(cg.token_total),
    ]

    full_migration_values = [
        fm.ddi_count,
        fm.active_ip_count,
        fm.asset_count,
        fm.formula_name,
        round(fm.token_total),
    ]

    if hybrid is not None:
        hybrid_values = [
            hybrid.nios_sub.ddi_count + hybrid.niosx_sub.ddi_count,
            hybrid.nios_sub.active_ip_count + hybrid.niosx_sub.active_ip_count,
            0,
            "NIOS Object + UDDI native (split)",
            round(hybrid.combined_total),
        ]
    else:
        hybrid_values = None  # Will use greyed_fmt

    for i, label in enumerate(row_labels):
        data_row = i + 1
        is_even = (i % 2 == 0)
        label_fmt = even_fmt if is_even else odd_fmt
        num_fmt_row = number_fmt

        # Is this the Token Total row?
        is_token_row = (label == "Token Total")
        cg_fmt = total_number_fmt if is_token_row else (label_fmt if isinstance(current_grid_values[i], str) else num_fmt_row)
        fm_fmt = total_number_fmt if is_token_row else (label_fmt if isinstance(full_migration_values[i], str) else num_fmt_row)

        ws.write(data_row, 0, label, label_fmt)

        # Current Grid column
        if isinstance(current_grid_values[i], str):
            ws.write(data_row, 1, current_grid_values[i], label_fmt)
        else:
            ws.write(data_row, 1, current_grid_values[i], cg_fmt)

        # Hybrid UDDI column
        if hybrid_values is None:
            # No split config — grey out
            if i == 0:
                ws.write(data_row, 2, "No migration split provided", greyed_fmt)
            else:
                ws.write_blank(data_row, 2, greyed_fmt)
        else:
            if isinstance(hybrid_values[i], str):
                ws.write(data_row, 2, hybrid_values[i], label_fmt)
            else:
                hybrid_fmt = total_number_fmt if is_token_row else num_fmt_row
                ws.write(data_row, 2, hybrid_values[i], hybrid_fmt)

        # Full Migration column
        if isinstance(full_migration_values[i], str):
            ws.write(data_row, 3, full_migration_values[i], label_fmt)
        else:
            ws.write(data_row, 3, full_migration_values[i], fm_fmt)


# ---------------------------------------------------------------------------
# Sheet 6: Member Attribution
# ---------------------------------------------------------------------------

def _write_member_attribution_sheet(
    workbook,
    header_fmt,
    even_fmt,
    odd_fmt,
    number_fmt,
    even_number_fmt,
    scenario_suite: ScenarioSuite,
    count_result: CountResult,
    member_map: dict[str, str],
) -> None:
    """Write Member Attribution sheet — per-member group, counts, and token contributions."""
    ws = workbook.add_worksheet("Member Attribution")
    ws.freeze_panes(1, 0)
    ws.set_column(0, 0, 15)
    ws.set_column(1, 1, 40)
    ws.set_column(2, 2, 10)
    ws.set_column(3, 3, 15)
    ws.set_column(4, 4, 15)
    ws.set_column(5, 5, 15)
    ws.set_column(6, 6, 22)

    # Header
    ws.write(0, 0, "Virtual OID", header_fmt)
    ws.write(0, 1, "Hostname", header_fmt)
    ws.write(0, 2, "Group", header_fmt)
    ws.write(0, 3, "Lease Count", header_fmt)
    ws.write(0, 4, "DDI Objects", header_fmt)
    ws.write(0, 5, "Active IPs", header_fmt)
    ws.write(0, 6, "Token Contribution", header_fmt)

    # Invert member_map: hostname -> virtual_oid (for lookup)
    hostname_to_oid: dict[str, str] = {v: k for k, v in member_map.items()}

    # Build lease count lookup from count_result
    lease_lookup: dict[str, int] = {
        m.member_hostname: m.lease_count for m in count_result.member_counts
    }

    for i, row_data in enumerate(scenario_suite.member_attribution):
        data_row = i + 1
        is_even = (i % 2 == 0)
        text_fmt = even_fmt if is_even else odd_fmt
        num_fmt_row = even_number_fmt if is_even else number_fmt

        virtual_oid = hostname_to_oid.get(row_data.member_hostname, "N/A")
        lease_count = lease_lookup.get(row_data.member_hostname, 0)

        ws.write(data_row, 0, virtual_oid, text_fmt)
        ws.write(data_row, 1, row_data.member_hostname, text_fmt)
        ws.write(data_row, 2, row_data.group, text_fmt)
        ws.write(data_row, 3, lease_count, num_fmt_row)
        ws.write(data_row, 4, row_data.ddi_count, num_fmt_row)
        ws.write(data_row, 5, row_data.active_ip_count, num_fmt_row)
        ws.write(data_row, 6, round(row_data.token_contribution), num_fmt_row)


# ---------------------------------------------------------------------------
# Per-source IP counting helper (used by run_nios_analysis)
# ---------------------------------------------------------------------------

def _count_ip_by_type(
    objects,
    lease_states: set[str],
) -> dict[str, int]:
    """Count Active IPs by source in a single pass. No cross-source deduplication.

    Returns raw (potentially overlapping) counts per source. The grand total for
    display MUST use grid_counts.active_ip_count (the authoritative deduped total),
    not the sum of these per-source counts.

    Args:
        objects: Filtered NiosObject stream (already past filter_objects()).
        lease_states: Set of binding_state values to count as active leases.
            Passed from FilterConfig.lease_states.

    Returns:
        Dict with keys "leases", "fixed", "host", "reservations" — each is the
        raw count of IPs from that source (may overlap with other sources).
    """
    import ipaddress

    counts: dict[str, int] = {"leases": 0, "fixed": 0, "host": 0, "reservations": 0}

    for obj in objects:
        if obj.family == NiosFamily.LEASE:
            state = obj.raw_attrs.get("binding_state", "")
            ip = obj.raw_attrs.get("ip_address", "").strip()
            if state in lease_states and ip:
                counts["leases"] += 1
        elif obj.family == NiosFamily.FIXED_ADDRESS:
            ip = obj.raw_attrs.get("ip_address", "").strip()
            if ip:
                counts["fixed"] += 1
        elif obj.family == NiosFamily.HOST_ADDRESS:
            # ZF backup stores host IPs under "address" key (NOT "ip_address")
            ip = obj.raw_attrs.get("address", "").strip()
            if ip:
                counts["host"] += 1
        elif obj.family == NiosFamily.NETWORK:
            cidr = obj.raw_attrs.get("cidr", "").strip()
            if cidr:
                try:
                    ipaddress.IPv4Network(cidr, strict=False)
                    counts["reservations"] += 2  # network_address + broadcast_address
                except ValueError:
                    pass  # Malformed CIDR — skip silently

    return counts


# ---------------------------------------------------------------------------
# Public API: run_nios_analysis (pipeline runner)
# ---------------------------------------------------------------------------

def run_nios_analysis(
    backup_path: str,
    filter_config: "FilterConfig",
    split_config: "Optional[MigrationSplitConfig]" = None,
    output_path: "Optional[str]" = None,
) -> str:
    """Wire the full NIOS analysis pipeline: parse -> filter -> count -> scenarios -> output.

    Accepts pre-built FilterConfig and optional MigrationSplitConfig.
    No YAML parsing or config loading — callers (Phase 14 CLI, Phase 15 dashboard) build configs.

    Pipeline:
    1. inspect_backup()  — extract nios_version, snapshot_date for report header
    2. get_member_map()  — virtual_oid -> hostname for Member Attribution sheet
    3. Pass A: parse_backup() -> filter_objects() -> count_objects() -> CountResult
    4. Pass B: parse_backup() -> filter_objects() -> _count_ip_by_type() -> ip_by_type dict
    5. compute_scenarios(count_result, split_config) -> ScenarioSuite
    6. write_nios_xlsx_report(filepath, ...) -> str

    Args:
        backup_path: Path to the .tar.gz NIOS Grid backup file.
        filter_config: Pre-built FilterConfig with whitelist/blacklist/lease_states.
        split_config: Optional MigrationSplitConfig for hybrid UDDI scenario. None = no hybrid.
        output_path: Override output file path. If None, uses output/nios_analysis_<timestamp>.xlsx.

    Returns:
        Absolute or relative path to the written .xlsx file.

    Raises:
        NiosParseError: If backup_path is missing, corrupt, or lacks onedb.xml.
        Any exception from the pipeline propagates to the caller.
    """
    import os
    from datetime import datetime
    from pathlib import Path

    from cloud_usage.nios.parser import inspect_backup, parse_backup, get_member_map
    from cloud_usage.nios.filter import filter_objects
    from cloud_usage.nios.counter import count_objects
    from cloud_usage.nios.scenarios import compute_scenarios

    # Step 1: Inspect backup for metadata (nios_version, snapshot_date)
    integrity = inspect_backup(backup_path)

    # Step 2: Build member map for virtual_oid lookup in Member Attribution sheet
    member_map = get_member_map(backup_path)

    # Step 3 (Pass A): parse -> filter -> count
    raw_stream_a = parse_backup(backup_path)
    filtered_a = filter_objects(raw_stream_a, filter_config)
    count_result = count_objects(filtered_a, filter_config)

    # Step 4 (Pass B): parse -> filter -> ip_by_type (per-source raw counts)
    raw_stream_b = parse_backup(backup_path)
    filtered_b = filter_objects(raw_stream_b, filter_config)
    ip_by_type = _count_ip_by_type(filtered_b, set(filter_config.lease_states))

    # Step 5: compute scenarios
    scenario_suite = compute_scenarios(count_result, split_config)

    # Step 6: resolve output path
    analysis_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    if output_path is None:
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        resolved_path = f"{output_dir}/nios_analysis_{ts}.xlsx"
    else:
        os.makedirs(str(Path(output_path).parent), exist_ok=True)
        resolved_path = output_path

    # Step 7: write report
    return write_nios_xlsx_report(
        filepath=resolved_path,
        integrity_report=integrity,
        count_result=count_result,
        scenario_suite=scenario_suite,
        filter_config=filter_config,
        split_config=split_config,
        analysis_timestamp=analysis_timestamp,
        member_map=member_map,
        ip_by_type=ip_by_type,
    )
