"""GCP project enumeration with filtering and API pre-checks.

Enumerates accessible GCP projects using search_projects(), applies
include/exclude glob filters, and checks per-project API enablement
for Compute, DNS, Cloud SQL Admin, and GKE Container APIs.
"""

from __future__ import annotations

import fnmatch
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProjectInfo:
    """Per-project API availability record.

    Tracks which APIs are enabled for each project so collectors
    can skip disabled projects without making failing API calls.

    Args:
        project_id: GCP project ID string.
        compute_enabled: True if Compute Engine API is enabled.
        dns_enabled: True if Cloud DNS API is enabled.
        sqladmin_enabled: True if Cloud SQL Admin API is enabled.
        container_enabled: True if GKE Container API is enabled.
    """

    project_id: str
    compute_enabled: bool
    dns_enabled: bool
    sqladmin_enabled: bool
    container_enabled: bool


def enumerate_gcp_projects(
    credentials,
    adc_project: str | None,
    project: str | None,
    org_id: str | None,
    include_patterns: list[str] | None,
    exclude_patterns: list[str] | None,
) -> list[ProjectInfo]:
    """Return a curated list of ProjectInfo for accessible ACTIVE GCP projects.

    If an explicit project is specified (via the project parameter,
    GOOGLE_CLOUD_PROJECT env var, or ADC), returns a single-element list
    without calling search_projects.

    Args:
        credentials: Validated GCP credential object.
        adc_project: Project ID inferred from the ADC chain (may be None).
        project: Explicit --project flag value (takes priority over env and ADC).
        org_id: Organization ID for scoping enumeration (--org-id flag).
        include_patterns: Glob patterns; only matching project IDs are kept.
            Include takes precedence (if include provided, only match include;
            exclude is applied only when no include).
        exclude_patterns: Glob patterns; matching project IDs are removed.

    Returns:
        List of ProjectInfo with per-project API enablement flags.
    """
    # Priority: --project flag > GOOGLE_CLOUD_PROJECT env var > ADC project
    explicit_project = project or os.getenv("GOOGLE_CLOUD_PROJECT") or adc_project

    if explicit_project:
        # Single-project mode: bypass enumeration
        api_status = _check_apis_enabled(credentials, explicit_project)
        _log_api_status(explicit_project, api_status)
        return [ProjectInfo(
            project_id=explicit_project,
            compute_enabled=api_status.get("compute", True),
            dns_enabled=api_status.get("dns", True),
            sqladmin_enabled=api_status.get("sqladmin", True),
            container_enabled=api_status.get("container", True),
        )]

    # Multi-project enumeration path
    project_ids = _fetch_active_projects(credentials, org_id)

    # Apply include/exclude glob filters
    project_ids = _apply_project_filters(project_ids, include_patterns, exclude_patterns)

    # Zero projects: return empty list (caller handles the error message)
    if not project_ids:
        return []

    # Per-project API pre-checks
    results: list[ProjectInfo] = []
    for pid in project_ids:
        api_status = _check_apis_enabled(credentials, pid)
        _log_api_status(pid, api_status)
        results.append(ProjectInfo(
            project_id=pid,
            compute_enabled=api_status.get("compute", True),
            dns_enabled=api_status.get("dns", True),
            sqladmin_enabled=api_status.get("sqladmin", True),
            container_enabled=api_status.get("container", True),
        ))

    return results


def _fetch_active_projects(credentials, org_id: str | None) -> list[str]:
    """Return list of ACTIVE project IDs accessible to the credential.

    Uses search_projects (not list_projects) so the entire org hierarchy is
    traversed in a single paginated call.

    Args:
        credentials: Validated GCP credentials.
        org_id: Optional organization ID to scope enumeration.

    Returns:
        List of project ID strings.
    """
    from google.cloud import resourcemanager_v3

    client = resourcemanager_v3.ProjectsClient(credentials=credentials)

    if org_id:
        parent = org_id if org_id.startswith("organizations/") else f"organizations/{org_id}"
        query = f"state:ACTIVE parent:{parent}"
    else:
        query = "state:ACTIVE"

    request = resourcemanager_v3.SearchProjectsRequest(query=query)
    project_ids = []
    for proj in client.search_projects(request=request):
        project_ids.append(proj.project_id)
    return project_ids


def _apply_project_filters(
    project_ids: list[str],
    include_patterns: list[str] | None,
    exclude_patterns: list[str] | None,
) -> list[str]:
    """Filter project list by include/exclude glob patterns.

    Include takes precedence: if include is provided, only matching
    projects are kept and exclude is ignored. Exclude is applied only
    when no include is provided.

    Args:
        project_ids: Full list of project IDs.
        include_patterns: Glob patterns to include (takes precedence).
        exclude_patterns: Glob patterns to exclude.

    Returns:
        Filtered list of project IDs.
    """
    if include_patterns is not None:
        project_ids = [
            p for p in project_ids
            if any(fnmatch.fnmatch(p, pat) for pat in include_patterns)
        ]
    elif exclude_patterns is not None:
        project_ids = [
            p for p in project_ids
            if not any(fnmatch.fnmatch(p, pat) for pat in exclude_patterns)
        ]
    return project_ids


def _check_apis_enabled(credentials, project_id: str) -> dict[str, bool]:
    """Check if Compute, DNS, Cloud SQL Admin, and Container APIs are enabled.

    Uses ServiceUsageClient.batch_get_services() for efficient checking.
    On PermissionDenied: treat all as unavailable (False).
    On other transient errors: assume enabled (True).

    Args:
        credentials: Validated GCP credentials.
        project_id: GCP project ID string.

    Returns:
        Dict mapping API short name to enabled status.
    """
    try:
        from google.cloud import service_usage_v1

        client = service_usage_v1.ServiceUsageClient(credentials=credentials)
        parent = f"projects/{project_id}"

        request = service_usage_v1.BatchGetServicesRequest(
            parent=parent,
            names=[
                f"{parent}/services/compute.googleapis.com",
                f"{parent}/services/dns.googleapis.com",
                f"{parent}/services/sqladmin.googleapis.com",
                f"{parent}/services/container.googleapis.com",
            ],
        )
        response = client.batch_get_services(request=request)

        status: dict[str, bool] = {
            "compute": False,
            "dns": False,
            "sqladmin": False,
            "container": False,
        }
        for svc in response.services:
            enabled = svc.state == service_usage_v1.types.Service.State.ENABLED
            if "compute.googleapis.com" in svc.name:
                status["compute"] = enabled
            elif "dns.googleapis.com" in svc.name:
                status["dns"] = enabled
            elif "sqladmin.googleapis.com" in svc.name:
                status["sqladmin"] = enabled
            elif "container.googleapis.com" in svc.name:
                status["container"] = enabled
        return status

    except Exception as exc:
        exc_name = type(exc).__name__
        # PermissionDenied: treat all APIs as unavailable
        if exc_name in ("PermissionDenied", "Forbidden"):
            return {
                "compute": False,
                "dns": False,
                "sqladmin": False,
                "container": False,
            }
        # Other transient errors: assume enabled, let discovery surface the real error
        return {
            "compute": True,
            "dns": True,
            "sqladmin": True,
            "container": True,
        }


def _log_api_status(project_id: str, api_status: dict[str, bool]) -> None:
    """Log [Skip] lines for disabled APIs. Silent for fully-enabled projects.

    Args:
        project_id: GCP project ID string.
        api_status: Dict mapping API short name to enabled status.
    """
    api_display = {
        "compute": "Compute API",
        "dns": "DNS API",
        "sqladmin": "Cloud SQL Admin API",
        "container": "Container API",
    }
    for api_name, enabled in api_status.items():
        if not enabled:
            display = api_display.get(api_name, api_name)
            logger.info("[Skip] %s: %s disabled", project_id, display)
