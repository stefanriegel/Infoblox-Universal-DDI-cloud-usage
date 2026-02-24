"""HTMX partial fragment routes for filtering, pagination, and sorting.

Serves HTML fragments for the Results tab data table, filter chips,
and summary cards. All responses are HTML partials intended for HTMX
swap targets (hx-target), not full pages.
"""

from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/partials")


def _get_filter_options(resources: list) -> dict[str, list[str]]:
    """Build unique filter option values from ALL resources (unfiltered).

    Args:
        resources: Full list of CloudResource instances.

    Returns:
        Dict with keys: providers, accounts, resource_types, categories,
        statuses -- each a sorted list of unique values.
    """
    providers: set[str] = set()
    accounts: set[str] = set()
    resource_types: set[str] = set()
    categories: set[str] = set()

    for r in resources:
        providers.add(r.provider)
        accounts.add(r.account_id)
        resource_types.add(r.resource_type)
        if r.category:
            categories.add(r.category)

    return {
        "providers": sorted(providers, key=str.lower),
        "accounts": sorted(accounts),
        "resource_types": sorted(resource_types, key=str.lower),
        "categories": sorted(categories, key=str.lower),
        "statuses": ["counted", "skipped"],
    }


def _apply_filters(
    resources: list,
    filter_provider: str,
    filter_account: str,
    filter_resource_type: str,
    filter_category: str,
    filter_status: str,
) -> list:
    """Apply sequential filters to resource list.

    Each filter is optional -- applied only when non-empty.

    Args:
        resources: List of CloudResource instances.
        filter_provider: Provider name to match (case-insensitive).
        filter_account: Account ID to match.
        filter_resource_type: Resource type to match.
        filter_category: Category (ddi/ip/asset) to match.
        filter_status: "counted" or "skipped" to match.

    Returns:
        Filtered list of CloudResource instances.
    """
    result = list(resources)

    if filter_provider:
        lp = filter_provider.lower()
        result = [r for r in result if r.provider.lower() == lp]

    if filter_account:
        result = [r for r in result if r.account_id == filter_account]

    if filter_resource_type:
        result = [r for r in result if r.resource_type == filter_resource_type]

    if filter_category:
        lc = filter_category.lower()
        result = [r for r in result if r.category and r.category.lower() == lc]

    if filter_status:
        if filter_status == "counted":
            result = [r for r in result if r.counted is True]
        elif filter_status == "skipped":
            result = [r for r in result if r.counted is False]

    return result


def _apply_sorting(
    resources: list,
    sort_by: str,
    sort_dir: str,
) -> list:
    """Sort resources by the specified field and direction.

    Args:
        resources: List of CloudResource instances.
        sort_by: Field name to sort by.
        sort_dir: "asc" or "desc".

    Returns:
        Sorted list (new list, does not mutate input).
    """
    valid_fields = {
        "resource_id", "resource_type", "provider",
        "account_id", "region", "category",
    }
    if sort_by not in valid_fields:
        sort_by = "resource_type"

    reverse = sort_dir == "desc"

    return sorted(
        resources,
        key=lambda r: (getattr(r, sort_by, "") or "").lower(),
        reverse=reverse,
    )


def _build_active_filters(
    filter_provider: str,
    filter_account: str,
    filter_resource_type: str,
    filter_category: str,
    filter_status: str,
) -> dict[str, str]:
    """Build dict of active (non-empty) filter params for chip display.

    Args:
        filter_provider: Provider filter value.
        filter_account: Account filter value.
        filter_resource_type: Resource type filter value.
        filter_category: Category filter value.
        filter_status: Status filter value.

    Returns:
        Dict of filter_key -> value for non-empty filters.
    """
    active: dict[str, str] = {}
    if filter_provider:
        active["filter_provider"] = filter_provider
    if filter_account:
        active["filter_account"] = filter_account
    if filter_resource_type:
        active["filter_resource_type"] = filter_resource_type
    if filter_category:
        active["filter_category"] = filter_category
    if filter_status:
        active["filter_status"] = filter_status
    return active


@router.get("/results-table", response_class=HTMLResponse)
async def results_table(request: Request) -> HTMLResponse:
    """Render paginated, filtered, sorted results table partial.

    Query params:
        filter_provider, filter_account, filter_resource_type,
        filter_category, filter_status: Optional filter values.
        sort_by: Field to sort by (default: resource_type).
        sort_dir: Sort direction asc/desc (default: asc).
        page: Page number (default: 1).
        page_size: Rows per page (default: 50).

    Returns:
        HTML fragment for results table body swap.
    """
    params = request.query_params

    # Handle clear_filter_* params (remove that filter)
    filter_provider = params.get("filter_provider", "")
    filter_account = params.get("filter_account", "")
    filter_resource_type = params.get("filter_resource_type", "")
    filter_category = params.get("filter_category", "")
    filter_status = params.get("filter_status", "")

    # Clear individual filters when clear_* param is present
    if params.get("clear_filter_provider"):
        filter_provider = ""
    if params.get("clear_filter_account"):
        filter_account = ""
    if params.get("clear_filter_resource_type"):
        filter_resource_type = ""
    if params.get("clear_filter_category"):
        filter_category = ""
    if params.get("clear_filter_status"):
        filter_status = ""

    sort_by = params.get("sort_by", "resource_type")
    sort_dir = params.get("sort_dir", "asc")
    page = max(1, int(params.get("page", "1")))
    page_size = max(1, int(params.get("page_size", "50")))

    scan_manager = request.app.state.scan_manager
    all_resources = scan_manager.resources

    # Build filter options from ALL resources (not filtered)
    filter_options = _get_filter_options(all_resources)

    # Apply filters
    filtered = _apply_filters(
        all_resources,
        filter_provider,
        filter_account,
        filter_resource_type,
        filter_category,
        filter_status,
    )

    # Apply sorting
    sorted_resources = _apply_sorting(filtered, sort_by, sort_dir)

    # Apply pagination
    total_results = len(sorted_resources)
    total_pages = max(1, math.ceil(total_results / page_size))
    page = min(page, total_pages)
    start = (page - 1) * page_size
    end = start + page_size
    page_resources = sorted_resources[start:end]

    # Build active filters
    active_filters = _build_active_filters(
        filter_provider,
        filter_account,
        filter_resource_type,
        filter_category,
        filter_status,
    )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "partials/results_table.html",
        {
            "resources": page_resources,
            "page": page,
            "total_pages": total_pages,
            "total_results": total_results,
            "active_filters": active_filters,
            "filter_options": filter_options,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "page_size": page_size,
            "start_row": start + 1 if total_results > 0 else 0,
            "end_row": min(end, total_results),
        },
    )


@router.get("/filter-chips", response_class=HTMLResponse)
async def filter_chips(request: Request) -> HTMLResponse:
    """Render just the filter chips for HTMX swap.

    Returns:
        HTML fragment with active filter chip elements.
    """
    params = request.query_params
    active_filters = _build_active_filters(
        params.get("filter_provider", ""),
        params.get("filter_account", ""),
        params.get("filter_resource_type", ""),
        params.get("filter_category", ""),
        params.get("filter_status", ""),
    )
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "partials/filter_chips.html",
        {"active_filters": active_filters},
    )


@router.get("/summary-cards", response_class=HTMLResponse)
async def summary_cards(request: Request) -> HTMLResponse:
    """Render summary cards partial for HTMX swap.

    Used by Progress tab completion to update summary on screen.

    Returns:
        HTML fragment with token summary card elements.
    """
    from cloud_usage.dashboard.routes.pages import _compute_summary

    scan_manager = request.app.state.scan_manager
    all_resources = scan_manager.resources
    summary = _compute_summary(all_resources)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "partials/summary_cards.html",
        summary,
    )


@router.get("/empty", response_class=HTMLResponse)
async def empty(request: Request) -> HTMLResponse:
    """Return empty string for auto-dismiss banners.

    Returns:
        Empty HTML response.
    """
    return HTMLResponse("")
