"""Full-page HTML routes and HTMX tab endpoints for the dashboard.

Serves the base HTML page at root URL and tab content endpoints
for HTMX HATEOAS tab switching. Each tab endpoint returns the
full #tab-container div (tab bar + content) for hx-target swap.
"""

from __future__ import annotations

import math
from collections import defaultdict

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from cloud_usage.counting.ip_counter import deduplicate_ips_per_vpc
from cloud_usage.counting.token_calculator import (
    calculate_account_tokens,
    calculate_tokens,
)
from cloud_usage.dashboard.routes.partials import (
    _apply_sorting,
    _get_filter_options,
)

router = APIRouter()


def _get_tab_context(request: Request, active_tab: str) -> dict:
    """Build template context for tab rendering.

    Reads scan state, resource count, and provider progress from
    the ScanManager to populate tab badges and progress display.

    Args:
        request: The incoming HTTP request.
        active_tab: Which tab is currently active.

    Returns:
        Template context dict with tab state variables.
    """
    scan_manager = request.app.state.scan_manager
    state = scan_manager.state.value
    resources = scan_manager.resources
    resource_count = len(resources)

    # Build provider progress data from progress_data dict if available
    providers: list[dict] = []
    total_resources = 0
    progress_data = getattr(scan_manager, "_progress_data", {})
    for _prov_name, prov_data in progress_data.items():
        providers.append(prov_data)
        total_resources += prov_data.get("resources", 0)

    return {
        "request": request,
        "active_tab": active_tab,
        "scan_state": state,
        "resource_count": resource_count,
        "providers": providers,
        "total_resources": total_resources,
        "total_providers": len(providers),
    }


def _compute_summary(resources: list) -> dict:
    """Compute token summary data from resources.

    Groups resources by account, calculates per-account tokens with
    IP deduplication, then aggregates per-provider and overall totals.

    Args:
        resources: List of CloudResource instances.

    Returns:
        Dict with total_tokens, ddi_count, ip_count, asset_count,
        provider_breakdown (provider -> tokens), per_provider_details
        (provider -> {accounts, ddi, ips, assets, tokens}),
        per_account_details (list of account dicts).
    """
    if not resources:
        return {
            "total_tokens": 0,
            "ddi_count": 0,
            "ip_count": 0,
            "asset_count": 0,
            "provider_breakdown": {},
            "per_provider_details": {},
            "per_account_details": [],
        }

    # Group resources by account
    by_account: dict[str, list] = defaultdict(list)
    account_provider: dict[str, str] = {}
    for r in resources:
        by_account[r.account_id].append(r)
        account_provider[r.account_id] = r.provider

    # Deduplicate IPs globally
    ip_dedup = deduplicate_ips_per_vpc(resources)
    per_account_ips = ip_dedup.get("per_account", {})

    # Calculate per-account tokens
    account_results: dict[str, dict] = {}
    for account_id, acct_resources in by_account.items():
        dedup_ip_count = per_account_ips.get(account_id, 0)
        account_results[account_id] = calculate_account_tokens(
            acct_resources, deduplicated_ip_count=dedup_ip_count
        )

    # Aggregate per-provider
    provider_data: dict[str, dict] = defaultdict(
        lambda: {"accounts": 0, "ddi": 0, "ips": 0, "assets": 0, "tokens": 0}
    )
    for account_id, result in account_results.items():
        prov = account_provider[account_id]
        provider_data[prov]["accounts"] += 1
        provider_data[prov]["ddi"] += result["ddi_count"]
        provider_data[prov]["ips"] += result["ip_count"]
        provider_data[prov]["assets"] += result["asset_count"]
        provider_data[prov]["tokens"] += result["total_tokens"]

    # Build provider breakdown (provider -> token count)
    provider_breakdown = {
        prov: data["tokens"] for prov, data in sorted(provider_data.items())
    }

    # Build per-account detail list
    per_account_details = []
    for account_id, result in sorted(account_results.items()):
        per_account_details.append({
            "account_id": account_id,
            "provider": account_provider[account_id],
            "ddi_count": result["ddi_count"],
            "ip_count": result["ip_count"],
            "asset_count": result["asset_count"],
            "total_tokens": result["total_tokens"],
        })

    # Grand totals
    total_ddi = sum(r["ddi_count"] for r in account_results.values())
    total_ips = sum(r["ip_count"] for r in account_results.values())
    total_assets = sum(r["asset_count"] for r in account_results.values())
    grand_totals = calculate_tokens(total_ddi, total_ips, total_assets)

    return {
        "total_tokens": grand_totals["total_tokens"],
        "ddi_count": total_ddi,
        "ip_count": total_ips,
        "asset_count": total_assets,
        "provider_breakdown": provider_breakdown,
        "per_provider_details": dict(provider_data),
        "per_account_details": per_account_details,
    }


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the base dashboard page with Progress tab as default.

    The base.html template loads the Progress tab via HTMX on page load.

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered base.html template with initial tab load trigger.
    """
    templates = request.app.state.templates
    context = _get_tab_context(request, "progress")
    return templates.TemplateResponse(request, "base.html", context)


@router.get("/tab/progress", response_class=HTMLResponse)
async def tab_progress(request: Request) -> HTMLResponse:
    """Render the Progress tab content for HTMX swap.

    Returns the full #tab-container div with tab bar and progress
    page content. Used by hx-get on tab links.

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered progress.html template.
    """
    templates = request.app.state.templates
    context = _get_tab_context(request, "progress")
    return templates.TemplateResponse(
        request, "pages/progress.html", context
    )


@router.get("/tab/results", response_class=HTMLResponse)
async def tab_results(request: Request) -> HTMLResponse:
    """Render the Results tab with filter bar, data table, and pagination.

    Provides initial page load data. Subsequent filtering/sorting/paging
    is handled by HTMX partials via /partials/results-table.

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered results.html tab content for HTMX swap.
    """
    scan_manager = request.app.state.scan_manager
    all_resources = scan_manager.resources

    filter_options = _get_filter_options(all_resources)
    summary = _compute_summary(all_resources)

    # Initial page of results (no filters, default sort)
    sorted_resources = _apply_sorting(all_resources, "resource_type", "asc")
    page_size = 50
    total_results = len(sorted_resources)
    total_pages = max(1, math.ceil(total_results / page_size))
    page_resources = sorted_resources[:page_size]

    templates = request.app.state.templates
    context = _get_tab_context(request, "results")
    context.update({
        "filter_options": filter_options,
        "active_filters": {},
        # Results table data
        "resources": page_resources,
        "page": 1,
        "total_pages": total_pages,
        "total_results": total_results,
        "sort_by": "resource_type",
        "sort_dir": "asc",
        "page_size": page_size,
        "start_row": 1 if total_results > 0 else 0,
        "end_row": min(page_size, total_results),
        # Summary card data
        **summary,
    })
    return templates.TemplateResponse(
        request, "pages/results.html", context
    )


@router.get("/tab/summary", response_class=HTMLResponse)
async def tab_summary(request: Request) -> HTMLResponse:
    """Render the Summary tab with token cards and breakdowns.

    Calculates summary data from scan_manager resources using the
    counting pipeline functions for consistency with CLI output.
    Includes download links for generated output files.

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered summary.html tab content for HTMX swap.
    """
    scan_manager = request.app.state.scan_manager
    all_resources = scan_manager.resources

    summary = _compute_summary(all_resources)

    # Build download list from output paths
    import os

    downloads = []
    for file_type, file_path in scan_manager.output_paths.items():
        filename = os.path.basename(file_path)
        downloads.append({
            "type": file_type,
            "filename": filename,
            "url": f"/download/{filename}",
        })

    templates = request.app.state.templates
    context = _get_tab_context(request, "summary")
    context.update(summary)
    context["downloads"] = downloads
    return templates.TemplateResponse(
        request, "pages/summary.html", context
    )
