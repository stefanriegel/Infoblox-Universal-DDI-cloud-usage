"""
Estimator CSV for Infoblox sizing spreadsheet integration.

Produces a flat CSV mapping account-level DDI/IP/Asset counts and token
estimates to the yellow cells of the Infoblox sizing spreadsheet.
"""

from __future__ import annotations

import csv


def write_estimator_csv(
    filepath: str,
    account_summaries: dict[str, dict],
    provider: str,
) -> str:
    """Generate an estimator CSV from account-level token calculations.

    Produces a CSV with one row per account and a TOTAL row, designed
    for direct paste into the Infoblox sizing spreadsheet yellow cells.

    Args:
        filepath: Output file path for the .csv file.
        account_summaries: Dict mapping account_id to token calculation
            results (from calculate_account_tokens).
        provider: Cloud provider name (e.g., "aws").

    Returns:
        The filepath written.
    """
    headers = [
        "Account ID",
        "DDI Objects",
        "Active IPs",
        "Managed Assets",
        "DDI Tokens",
        "IP Tokens",
        "Asset Tokens",
        "Total Tokens",
    ]

    total_ddi = 0
    total_ips = 0
    total_assets = 0
    total_ddi_tokens = 0
    total_ip_tokens = 0
    total_asset_tokens = 0
    total_tokens = 0

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for account_id in sorted(account_summaries.keys()):
            summary = account_summaries[account_id]
            ddi_count = summary.get("ddi_count", 0)
            ip_count = summary.get("ip_count", 0)
            asset_count = summary.get("asset_count", 0)
            ddi_tokens = summary.get("ddi_tokens", 0)
            ip_tokens = summary.get("ip_tokens", 0)
            asset_tokens = summary.get("asset_tokens", 0)
            acct_total = summary.get("total_tokens", 0)

            total_ddi += ddi_count
            total_ips += ip_count
            total_assets += asset_count
            total_ddi_tokens += ddi_tokens
            total_ip_tokens += ip_tokens
            total_asset_tokens += asset_tokens
            total_tokens += acct_total

            writer.writerow([
                account_id,
                ddi_count,
                ip_count,
                asset_count,
                ddi_tokens,
                ip_tokens,
                asset_tokens,
                acct_total,
            ])

        # Write TOTAL row
        writer.writerow([
            "TOTAL",
            total_ddi,
            total_ips,
            total_assets,
            total_ddi_tokens,
            total_ip_tokens,
            total_asset_tokens,
            total_tokens,
        ])

    return filepath
