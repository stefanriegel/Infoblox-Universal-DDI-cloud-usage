"""
XLS report generation with Detail, Summary, and Warnings sheets.

Produces a professional Excel workbook from cloud discovery results with
frozen header rows, alternating row colors, and auto-sized columns.
Uses xlsxwriter for write-only performance and rich formatting support.
"""

from __future__ import annotations

from typing import Any

import xlsxwriter

from cloud_usage.schema.resource import CloudResource


def write_xlsx_report(
    filepath: str,
    resources: list[CloudResource],
    account_summaries: dict[str, dict],
    errors: list[dict[str, str]],
    provider: str,
) -> str:
    """Generate a professional XLS report from discovery results.

    Creates a workbook with three sheets:
    - Detail: one row per discovered resource with all fields
    - Summary: per-account token totals with provider grand total
    - Warnings: any discovery errors or a "no errors" message

    Args:
        filepath: Output file path for the .xlsx file.
        resources: All discovered CloudResource instances.
        account_summaries: Dict mapping account_id to token calculation
            results (from calculate_account_tokens).
        errors: List of error dicts with keys: account, region,
            resource_type, error, suggestion.
        provider: Cloud provider name (e.g., "aws").

    Returns:
        The filepath written.
    """
    workbook = xlsxwriter.Workbook(filepath)

    # -- Define formats once at workbook level --
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
    number_even_fmt = workbook.add_format({
        "border": 1,
        "num_format": "#,##0",
        "bg_color": "#D9E2F3",
    })
    counted_yes_fmt = workbook.add_format({
        "border": 1,
        "font_color": "#006100",
        "bg_color": "#C6EFCE",
    })
    counted_no_fmt = workbook.add_format({
        "border": 1,
        "font_color": "#9C0006",
        "bg_color": "#FFC7CE",
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

    _write_detail_sheet(workbook, resources, header_fmt, even_row_fmt, odd_row_fmt,
                        number_fmt, number_even_fmt, counted_yes_fmt, counted_no_fmt)
    _write_summary_sheet(workbook, account_summaries, provider, header_fmt,
                         even_row_fmt, odd_row_fmt, number_fmt, number_even_fmt,
                         total_row_fmt, total_number_fmt)
    _write_warnings_sheet(workbook, errors, header_fmt, even_row_fmt, odd_row_fmt)

    workbook.close()
    return filepath


def _write_detail_sheet(
    workbook: xlsxwriter.Workbook,
    resources: list[CloudResource],
    header_fmt: xlsxwriter.format.Format,
    even_row_fmt: xlsxwriter.format.Format,
    odd_row_fmt: xlsxwriter.format.Format,
    number_fmt: xlsxwriter.format.Format,
    number_even_fmt: xlsxwriter.format.Format,
    counted_yes_fmt: xlsxwriter.format.Format,
    counted_no_fmt: xlsxwriter.format.Format,
) -> None:
    """Write the Detail sheet with one row per discovered resource."""
    sheet = workbook.add_worksheet("Detail")
    sheet.freeze_panes(1, 0)

    headers = [
        "Resource ID", "Type", "Account", "Region", "Name",
        "IP Addresses", "IP Count", "Counted", "Category",
        "Skip Reason", "Tags",
    ]

    # Write headers
    for col, header in enumerate(headers):
        sheet.write(0, col, header, header_fmt)

    # Track max widths for auto-sizing (start with header widths)
    col_widths = [len(h) for h in headers]

    # Write resource rows
    for row_idx, resource in enumerate(resources, start=1):
        is_even = row_idx % 2 == 0
        text_fmt = even_row_fmt if is_even else odd_row_fmt
        num_fmt = number_even_fmt if is_even else number_fmt

        ip_str = ", ".join(resource.ip_addresses)
        ip_count = len(resource.ip_addresses)
        counted_str = "Yes" if resource.counted else "No"
        counted_fmt = counted_yes_fmt if resource.counted else counted_no_fmt
        category_str = resource.category.upper() if resource.category else "-"
        skip_str = resource.skip_reason or ""
        tags_str = "; ".join(f"{k}={v}" for k, v in resource.tags.items())

        values: list[tuple[Any, Any]] = [
            (resource.resource_id, text_fmt),
            (resource.resource_type, text_fmt),
            (resource.account_id, text_fmt),
            (resource.region, text_fmt),
            (resource.name, text_fmt),
            (ip_str, text_fmt),
            (ip_count, num_fmt),
            (counted_str, counted_fmt),
            (category_str, text_fmt),
            (skip_str, text_fmt),
            (tags_str, text_fmt),
        ]

        for col, (value, fmt) in enumerate(values):
            sheet.write(row_idx, col, value, fmt)
            # Update max column width
            val_len = len(str(value)) if value else 0
            if val_len > col_widths[col]:
                col_widths[col] = val_len

    # Auto-size columns (minimum 12, maximum 40)
    for col, width in enumerate(col_widths):
        sheet.set_column(col, col, max(12, min(40, width + 2)))


def _write_summary_sheet(
    workbook: xlsxwriter.Workbook,
    account_summaries: dict[str, dict],
    provider: str,
    header_fmt: xlsxwriter.format.Format,
    even_row_fmt: xlsxwriter.format.Format,
    odd_row_fmt: xlsxwriter.format.Format,
    number_fmt: xlsxwriter.format.Format,
    number_even_fmt: xlsxwriter.format.Format,
    total_row_fmt: xlsxwriter.format.Format,
    total_number_fmt: xlsxwriter.format.Format,
) -> None:
    """Write the Summary sheet with per-account totals and provider grand total."""
    sheet = workbook.add_worksheet("Summary")
    sheet.freeze_panes(1, 0)

    headers = [
        "Account ID", "DDI Objects", "DDI Tokens", "Active IPs",
        "IP Tokens", "Managed Assets", "Asset Tokens", "Total Tokens",
    ]

    for col, header in enumerate(headers):
        sheet.write(0, col, header, header_fmt)

    # Track column widths
    col_widths = [len(h) for h in headers]

    # Totals accumulators
    total_ddi = 0
    total_ddi_tokens = 0
    total_ips = 0
    total_ip_tokens = 0
    total_assets = 0
    total_asset_tokens = 0
    total_tokens = 0

    for row_idx, (account_id, summary) in enumerate(
        sorted(account_summaries.items()), start=1
    ):
        is_even = row_idx % 2 == 0
        text_fmt = even_row_fmt if is_even else odd_row_fmt
        num_fmt = number_even_fmt if is_even else number_fmt

        ddi_count = summary.get("ddi_count", 0)
        ddi_tokens = summary.get("ddi_tokens", 0)
        ip_count = summary.get("ip_count", 0)
        ip_tokens = summary.get("ip_tokens", 0)
        asset_count = summary.get("asset_count", 0)
        asset_tokens = summary.get("asset_tokens", 0)
        acct_total = summary.get("total_tokens", 0)

        total_ddi += ddi_count
        total_ddi_tokens += ddi_tokens
        total_ips += ip_count
        total_ip_tokens += ip_tokens
        total_assets += asset_count
        total_asset_tokens += asset_tokens
        total_tokens += acct_total

        values: list[tuple[Any, Any]] = [
            (account_id, text_fmt),
            (ddi_count, num_fmt),
            (ddi_tokens, num_fmt),
            (ip_count, num_fmt),
            (ip_tokens, num_fmt),
            (asset_count, num_fmt),
            (asset_tokens, num_fmt),
            (acct_total, num_fmt),
        ]

        for col, (value, fmt) in enumerate(values):
            sheet.write(row_idx, col, value, fmt)
            val_len = len(str(value))
            if val_len > col_widths[col]:
                col_widths[col] = val_len

    # Provider total row
    total_row = len(account_summaries) + 1
    total_values = [
        (f"{provider.upper()} TOTAL", total_row_fmt),
        (total_ddi, total_number_fmt),
        (total_ddi_tokens, total_number_fmt),
        (total_ips, total_number_fmt),
        (total_ip_tokens, total_number_fmt),
        (total_assets, total_number_fmt),
        (total_asset_tokens, total_number_fmt),
        (total_tokens, total_number_fmt),
    ]

    for col, (value, fmt) in enumerate(total_values):
        sheet.write(total_row, col, value, fmt)

    # Auto-size columns
    for col, width in enumerate(col_widths):
        sheet.set_column(col, col, max(12, min(40, width + 2)))


def _write_warnings_sheet(
    workbook: xlsxwriter.Workbook,
    errors: list[dict[str, str]],
    header_fmt: xlsxwriter.format.Format,
    even_row_fmt: xlsxwriter.format.Format,
    odd_row_fmt: xlsxwriter.format.Format,
) -> None:
    """Write the Warnings sheet with discovery errors."""
    sheet = workbook.add_worksheet("Warnings")
    sheet.freeze_panes(1, 0)

    headers = ["Account", "Region", "Resource Type", "Error", "Suggestion"]

    for col, header in enumerate(headers):
        sheet.write(0, col, header, header_fmt)

    if not errors:
        sheet.write(1, 0, "No errors occurred during discovery", odd_row_fmt)
        # Set reasonable column widths even with no data
        for col, header in enumerate(headers):
            sheet.set_column(col, col, max(12, len(header) + 2))
        return

    col_widths = [len(h) for h in headers]

    for row_idx, error in enumerate(errors, start=1):
        is_even = row_idx % 2 == 0
        text_fmt = even_row_fmt if is_even else odd_row_fmt

        values = [
            error.get("account", ""),
            error.get("region", ""),
            error.get("resource_type", ""),
            error.get("error", ""),
            error.get("suggestion", ""),
        ]

        for col, value in enumerate(values):
            sheet.write(row_idx, col, value, text_fmt)
            val_len = len(str(value))
            if val_len > col_widths[col]:
                col_widths[col] = val_len

    for col, width in enumerate(col_widths):
        sheet.set_column(col, col, max(12, min(40, width + 2)))
