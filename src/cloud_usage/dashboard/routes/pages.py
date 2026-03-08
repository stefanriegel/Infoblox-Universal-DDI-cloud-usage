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

from cloud_usage.counting.ip_counter import count_nics_per_account
from cloud_usage.counting.token_calculator import (
    calculate_account_tokens,
    calculate_tokens,
)
from cloud_usage.dashboard.routes.partials import (
    _apply_sorting,
    _get_filter_options,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# DDI display name mapping — applied at summary computation time only.
# r.resource_type is never mutated; this dict is used only when building the
# resource_type_breakdown dict inside _compute_summary().
# ---------------------------------------------------------------------------
DDI_DISPLAY_NAMES: dict[str, str] = {
    # AWS — pre-v1.7
    "vpc": "VPC",
    "subnet": "Subnet",
    "vpn-gateway": "VPN Gateway",
    "transit-gateway": "Transit Gateway",
    "dhcp-option-set": "DHCP Option Set",
    "route53-zone": "Route53 Hosted Zone",
    "route53-record": "Route53 Record",
    # AWS — v1.7
    "aws-internet-gateway": "Internet Gateway",
    "aws-customer-gateway": "Customer Gateway",
    "aws-route-table": "Route Table",
    "aws-resolver-endpoint": "Route53 Resolver Endpoint",
    "aws-resolver-rule": "Route53 Resolver Rule",
    "aws-resolver-rule-association": "Route53 Resolver Rule Association",
    "aws-route53-health-check": "Route53 Health Check",
    "aws-route53-traffic-policy": "Route53 Traffic Policy",
    "aws-route53-traffic-policy-instance": "Route53 Traffic Policy Instance",
    "aws-ipam": "VPC IPAM",
    "aws-ipam-scope": "IPAM Scope",
    "aws-ipam-pool": "IPAM Pool",
    "aws-ipam-resource-discovery": "IPAM Resource Discovery",
    "aws-ipam-resource-discovery-association": "IPAM Resource Discovery Association",
    "aws-direct-connect-gateway": "Direct Connect Gateway",
    # Azure — pre-v1.7
    "azure-vnet": "Virtual Network",
    "azure-subnet": "Subnet",
    "azure-dhcp-config": "DHCP Configuration",
    "azure-dns-zone": "DNS Zone",
    "azure-dns-record": "DNS Record",
    "azure-private-dns-zone": "Private DNS Zone",
    "azure-private-dns-record": "Private DNS Record",
    "azure-lb": "Load Balancer",
    "azure-app-gateway": "Application Gateway",
    "azure-firewall": "Azure Firewall",
    "azure-nat-gateway": "NAT Gateway",
    "azure-vnet-peering": "VNet Peering",
    "azure-bastion": "Azure Bastion",
    # Azure — v1.7
    "azure-private-endpoint": "Private Endpoint",
    "azure-express-route": "ExpressRoute Circuit",
    "azure-vnet-gateway": "VNet Gateway",
    "azure-private-link-service": "Private Link Service",
    "azure-virtual-wan": "Virtual WAN",
    "azure-route-table": "Route Table",
    "azure-vwan-hub": "Virtual WAN Hub",
    "azure-tenant": "Azure Tenant",
    # GCP — pre-v1.7
    "gcp-vpc": "VPC Network",
    "gcp-subnet": "Subnet",
    "gcp-dns-zone": "Cloud DNS Zone",
    "gcp-dns-record": "Cloud DNS Record",
    # GCP — v1.7
    "gcp-reserved-ip": "Reserved IP Address",
    "gcp-router-nat": "Cloud NAT",
    "gcp-target-vpn-gateway": "Target VPN Gateway",
    # AD
    "ad-dns-zone": "AD DNS Zone",
    "ad-dns-record": "AD DNS Record",
    "ad-dhcp-scope": "AD DHCP Scope",
}


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

    # Add NIOS analysis state for tab bar badge (SC-1, SC-5)
    nios_manager = request.app.state.nios_manager
    nios_state = nios_manager.state.value

    # Add AD analysis state for tab bar badge (SC-5)
    ad_manager = request.app.state.ad_manager
    ad_state = ad_manager.state.value

    return {
        "request": request,
        "active_tab": active_tab,
        "scan_state": state,
        "resource_count": resource_count,
        "providers": providers,
        "total_resources": total_resources,
        "total_providers": len(providers),
        "nios_state": nios_state,
        "ad_state": ad_state,
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

    # NIC-based IP counting (Phase 25 methodology)
    ip_dedup = count_nics_per_account(resources)
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
        # Build resource_type_breakdown: counted resources only, grouped by resource_type
        breakdown: dict[str, dict] = {}
        for r in by_account[account_id]:
            if r.counted and r.category in ("ddi", "ip", "asset"):
                rt = r.resource_type
                if rt not in breakdown:
                    breakdown[rt] = {
                        "count": 0,
                        "category": r.category,
                        "display_name": DDI_DISPLAY_NAMES.get(rt, rt),
                    }
                breakdown[rt]["count"] += 1

        per_account_details.append({
            "account_id": account_id,
            "provider": account_provider[account_id],
            "ddi_count": result["ddi_count"],
            "ip_count": result["ip_count"],
            "asset_count": result["asset_count"],
            "total_tokens": result["total_tokens"],
            "ddi_tokens": result["ddi_tokens"],
            "ip_tokens": result["ip_tokens"],
            "asset_tokens": result["asset_tokens"],
            "resource_type_breakdown": breakdown,
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


def _compute_top_cloud_dns_zones(resources: list) -> list:
    """Compute Top 5 DNS zones by record count from cloud resources.

    AWS and Azure zones carry details["record_count"] directly.
    GCP zones have no record_count — count gcp-dns-record resources by zone.

    Returns:
        List of (zone_name, count) tuples, max 5, sorted descending by count.
    """
    zone_counts: dict = {}

    # AWS and Azure: use record_count from zone resource details
    ZONE_TYPES_WITH_COUNT = {"route53-zone", "azure-dns-zone", "azure-private-dns-zone"}
    for r in resources:
        if r.resource_type in ZONE_TYPES_WITH_COUNT:
            count = r.details.get("record_count", 0) or 0
            if r.name:
                zone_counts[r.name] = zone_counts.get(r.name, 0) + count

    # GCP: build zone name → FQDN map, then count records
    gcp_zone_internal_to_fqdn: dict = {}
    for r in resources:
        if r.resource_type == "gcp-dns-zone":
            internal = r.details.get("zone_name", "")
            fqdn = r.name  # dns_name on the zone object
            if internal and fqdn:
                gcp_zone_internal_to_fqdn[internal] = fqdn

    gcp_counts: dict = {}
    for r in resources:
        if r.resource_type == "gcp-dns-record":
            internal = r.details.get("zone_name", "")
            fqdn = gcp_zone_internal_to_fqdn.get(internal, "")
            if fqdn:
                gcp_counts[fqdn] = gcp_counts.get(fqdn, 0) + 1

    zone_counts.update(gcp_counts)

    # Sort descending, take top 5
    return sorted(zone_counts.items(), key=lambda x: x[1], reverse=True)[:5]


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the home selector screen."""
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "home.html", {"request": request})


@router.get("/cloud", response_class=HTMLResponse)
async def cloud_calculator(request: Request) -> HTMLResponse:
    """Render the Cloud Calculator at /cloud."""
    templates = request.app.state.templates
    context = _get_tab_context(request, "progress")
    context["calculator_name"] = "Cloud Calculator"
    return templates.TemplateResponse(request, "base.html", context)


@router.get("/nios", response_class=HTMLResponse)
async def nios_calculator(request: Request) -> HTMLResponse:
    """Render the NIOS Calculator at /nios."""
    templates = request.app.state.templates
    context = _get_tab_context(request, "nios")
    context["calculator_name"] = "NIOS Calculator"
    return templates.TemplateResponse(request, "base.html", context)


@router.get("/ad", response_class=HTMLResponse)
async def ad_calculator(request: Request) -> HTMLResponse:
    """Render the AD Calculator at /ad."""
    templates = request.app.state.templates
    context = _get_tab_context(request, "ad")
    context["calculator_name"] = "AD Calculator"
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
    top_cloud_dns_zones = _compute_top_cloud_dns_zones(all_resources)

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
    context["top_cloud_dns_zones"] = top_cloud_dns_zones
    return templates.TemplateResponse(
        request, "pages/summary.html", context
    )


@router.get("/tab/nios", response_class=HTMLResponse)
async def tab_nios(request: Request) -> HTMLResponse:
    """Render the NIOS Analysis tab content for HTMX swap.

    State-driven: idle shows upload form, running shows spinner,
    complete shows summary card + download, error shows error + upload form.

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered pages/nios.html template.
    """
    import os

    templates = request.app.state.templates
    nios_manager = request.app.state.nios_manager

    nios_state = nios_manager.state.value
    original_filename = nios_manager.original_filename
    output_path = nios_manager.output_path
    error = nios_manager.error
    scenario_suite = nios_manager.scenario_suite
    family_breakdown = nios_manager.family_breakdown
    top_dns_zones = nios_manager.top_dns_zones

    # Build download filename from output_path if complete
    download_filename = None
    if output_path:
        download_filename = os.path.basename(output_path)

    context = _get_tab_context(request, "nios")
    context.update({
        "nios_state": nios_state,
        "original_filename": original_filename,
        "output_path": output_path,
        "download_filename": download_filename,
        "error": error,
        "scenario_suite": scenario_suite,
        "family_breakdown": family_breakdown,
        "top_dns_zones": top_dns_zones,
    })
    return templates.TemplateResponse(
        request, "pages/nios.html", context
    )


@router.get("/tab/ad", response_class=HTMLResponse)
async def tab_ad(request: Request) -> HTMLResponse:
    """Render the AD Analysis tab content for HTMX swap.

    State-driven: idle shows connection wizard, running shows spinner,
    complete shows summary card + download, error shows error + wizard.

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered pages/ad.html template.
    """
    import os

    templates = request.app.state.templates
    ad_manager = request.app.state.ad_manager

    ad_state = ad_manager.state.value
    error = ad_manager.error
    last_options = ad_manager.last_options
    dns_zone_count = ad_manager.dns_zone_count
    dhcp_scope_count = ad_manager.dhcp_scope_count
    user_count = ad_manager.user_count
    ddi_count = ad_manager.ddi_count
    ip_count = ad_manager.ip_count
    token_total = ad_manager.token_total

    # Build download filename from output_path if complete
    download_filename = os.path.basename(ad_manager.output_path) if ad_manager.output_path else None

    context = _get_tab_context(request, "ad")
    context.update({
        "ad_state": ad_state,
        "dns_zone_count": dns_zone_count,
        "dhcp_scope_count": dhcp_scope_count,
        "user_count": user_count,
        "ddi_count": ddi_count,
        "ip_count": ip_count,
        "token_total": token_total,
        "download_filename": download_filename,
        "error": error,
        "last_options": last_options,
        "top_dns_zones": ad_manager.top_dns_zones,
    })
    return templates.TemplateResponse(request, "pages/ad.html", context)
