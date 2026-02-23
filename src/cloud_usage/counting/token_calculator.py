"""
Token calculation with ceiling division.

Converts DDI object counts, IP counts, and managed asset counts into
UDDI token estimates using the formula:
    ceil(DDI / 25) + ceil(IPs / 13) + ceil(Assets / 3)

Zero-count categories produce zero tokens (no minimum-1 rounding).
"""

from __future__ import annotations

import math

from cloud_usage.schema.resource import CloudResource

# Token ratio constants (hardcoded per business rules, not configurable)
DDI_PER_TOKEN: int = 25
IPS_PER_TOKEN: int = 13
ASSETS_PER_TOKEN: int = 3


def _ceil_div(count: int, divisor: int) -> int:
    """Ceiling division that returns 0 when count is 0.

    Args:
        count: The count to divide.
        divisor: The divisor (tokens per unit).

    Returns:
        Ceiling of count/divisor, or 0 if count is 0.
    """
    if count <= 0:
        return 0
    return math.ceil(count / divisor)


def calculate_tokens(
    ddi_count: int,
    ip_count: int,
    asset_count: int,
) -> dict:
    """Calculate token estimates from raw counts.

    Uses ceiling division for each category with 0-count producing
    0 tokens.

    Args:
        ddi_count: Number of DDI objects.
        ip_count: Number of unique active IPs.
        asset_count: Number of managed assets.

    Returns:
        Dict with ddi_count, ip_count, asset_count, ddi_tokens,
        ip_tokens, asset_tokens, and total_tokens.
    """
    ddi_tokens = _ceil_div(ddi_count, DDI_PER_TOKEN)
    ip_tokens = _ceil_div(ip_count, IPS_PER_TOKEN)
    asset_tokens = _ceil_div(asset_count, ASSETS_PER_TOKEN)

    return {
        "ddi_count": ddi_count,
        "ip_count": ip_count,
        "asset_count": asset_count,
        "ddi_tokens": ddi_tokens,
        "ip_tokens": ip_tokens,
        "asset_tokens": asset_tokens,
        "total_tokens": ddi_tokens + ip_tokens + asset_tokens,
    }


def calculate_account_tokens(
    resources: list[CloudResource],
    deduplicated_ip_count: int | None = None,
) -> dict:
    """Calculate token estimates for a single account from its resources.

    Groups counted resources by category, counts DDI objects and managed
    assets. For IP count, uses deduplicated_ip_count if provided (from
    deduplicate_ips_per_vpc), otherwise sums len(r.ip_addresses) for
    all counted resources.

    Args:
        resources: List of CloudResource instances for one account.
        deduplicated_ip_count: Pre-computed deduplicated IP count. If
            provided, used instead of summing ip_addresses.

    Returns:
        Dict with ddi_count, ip_count, asset_count, ddi_tokens,
        ip_tokens, asset_tokens, and total_tokens.
    """
    ddi_count = 0
    asset_count = 0
    ip_sum = 0

    for resource in resources:
        if not resource.counted:
            continue

        if resource.category == "ddi":
            ddi_count += 1
        elif resource.category == "asset":
            asset_count += 1

        # Sum IPs from all counted resources (fallback if no dedup count)
        ip_sum += len(resource.ip_addresses)

    # Use deduplicated count if provided
    ip_count = deduplicated_ip_count if deduplicated_ip_count is not None else ip_sum

    return calculate_tokens(ddi_count, ip_count, asset_count)


def calculate_provider_tokens(
    account_results: dict[str, dict],
) -> dict:
    """Aggregate token calculations across all accounts for a provider.

    Sums raw counts and token totals from each account's results.

    Args:
        account_results: Dict mapping account_id to the dict returned
            by calculate_account_tokens.

    Returns:
        Dict with total_ddi_count, total_ip_count, total_asset_count,
        total_tokens, and account_count.
    """
    total_ddi_count = 0
    total_ip_count = 0
    total_asset_count = 0
    total_tokens = 0

    for account_id, result in account_results.items():
        total_ddi_count += result.get("ddi_count", 0)
        total_ip_count += result.get("ip_count", 0)
        total_asset_count += result.get("asset_count", 0)
        total_tokens += result.get("total_tokens", 0)

    return {
        "total_ddi_count": total_ddi_count,
        "total_ip_count": total_ip_count,
        "total_asset_count": total_asset_count,
        "total_tokens": total_tokens,
        "account_count": len(account_results),
    }
