"""
GCP Configuration for Cloud Discovery
"""

import fnmatch
import os
import sys
import threading
from dataclasses import dataclass
from typing import List, Optional, Tuple

from google.auth import default
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import google.oauth2.credentials
import google.auth.compute_engine

from shared.config import BaseConfig


# Module-level credential singleton (thread-safe)
_gcp_credential_cache = None  # Tuple of (credentials, project)
_gcp_credential_lock = threading.Lock()


@dataclass
class ProjectInfo:
    """Per-project API availability record produced by enumerate_gcp_projects()."""

    project_id: str
    compute_enabled: bool
    dns_enabled: bool


def get_gcp_credential():
    """Return validated (credentials, project) singleton. Exits on auth failure."""
    global _gcp_credential_cache
    if _gcp_credential_cache is not None:
        return _gcp_credential_cache
    with _gcp_credential_lock:
        if _gcp_credential_cache is not None:
            return _gcp_credential_cache
        _gcp_credential_cache = _build_gcp_credential()
        return _gcp_credential_cache


def _build_gcp_credential():
    """Build validated (credentials, project) tuple. Calls sys.exit on auth failure."""
    # Step 1: Discover credentials via ADC chain
    try:
        credentials, project = default()
    except DefaultCredentialsError as e:
        _fail_gcp_auth(
            f"No GCP credentials found: {e}",
            include_both_paths=True,
        )

    # Step 2: Validate by forcing a token refresh
    try:
        credentials.refresh(Request())
    except RefreshError as e:
        _fail_gcp_auth(f"GCP credentials are invalid or expired: {e}")

    # Step 3: Log credential type (CRED-04)
    _log_gcp_credential_type(credentials, project)

    # Step 4: Permission pre-check (locked decision)
    _check_gcp_compute_permission(credentials, project)

    return credentials, project


def _log_gcp_credential_type(credentials, project):
    """Print [Auth] log line identifying the credential type and default project."""
    project_info = f" (default project: {project})" if project else ""

    if isinstance(credentials, service_account.Credentials):
        email = getattr(credentials, "service_account_email", "unknown")
        print(f"[Auth] Using service account: {email}{project_info}")
    elif isinstance(credentials, google.oauth2.credentials.Credentials):
        # Covers both ADC user credentials (gcloud auth application-default login)
        # and end-user credentials (gcloud auth login) — same Python class
        print(f"[Auth] Using Application Default Credentials{project_info}")
    elif isinstance(credentials, google.auth.compute_engine.Credentials):
        # Running on GCE, Cloud Run, App Engine, etc.
        print(f"[Auth] Using Application Default Credentials (Compute Engine){project_info}")
    else:
        # Workload Identity Federation, impersonated SA, GDCH, external_account
        cred_type = type(credentials).__name__
        print(f"[Auth] Using Application Default Credentials ({cred_type}){project_info}")


def _check_gcp_compute_permission(credentials, project):
    """
    Validate credentials can reach the Compute API.

    Exits with IAM guidance on PermissionDenied or Forbidden.
    Other exceptions (network, 429) are transient — let discovery handle them.
    """
    if not project:
        # No project to check against; skip silently.
        # Discovery will fail later with a clear message.
        return

    # Imports inside function to avoid circular imports and keep self-contained
    from google.cloud import compute_v1
    from google.api_core import exceptions as api_exceptions

    try:
        client = compute_v1.RegionsClient(credentials=credentials)
        # list() returns a pager; next() fetches exactly one page — cheap
        next(iter(client.list(project=project)), None)
    except api_exceptions.PermissionDenied as e:
        print(f"ERROR: GCP credential lacks compute.regions.list permission on project '{project}': {e}")
        print(f"Ensure your service account or user has at minimum the Viewer role, or:")
        print(f"  roles/compute.viewer")
        sys.exit(1)
    except api_exceptions.Forbidden as e:
        print(f"ERROR: GCP API access forbidden for project '{project}': {e}")
        print(f"Check that the Compute Engine API is enabled:")
        print(f"  gcloud services enable compute.googleapis.com --project={project}")
        sys.exit(1)
    except Exception:
        # Other exceptions (network, quota, 429) are transient — proceed silently
        pass


def _fail_gcp_auth(message: str, include_both_paths: bool = False) -> None:
    """Print actionable GCP auth error and exit. Never returns."""
    print(f"ERROR: {message}")
    print()
    if include_both_paths:
        print("Option 1 — Application Default Credentials (ADC):")
        print("  gcloud auth application-default login")
        print()
        print("Option 2 — Service Account key file:")
        print("  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
    else:
        print("To refresh Application Default Credentials:")
        print("  gcloud auth application-default login")
        print()
        print("Or set a Service Account key file:")
        print("  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
    print()
    print("To set the default project (if not in credentials):")
    print("  export GOOGLE_CLOUD_PROJECT=my-project-id")
    sys.exit(1)


def _fetch_active_projects(credentials, org_id: Optional[str]) -> List[str]:
    """Return list of ACTIVE project IDs accessible to the credential.

    Uses search_projects (not list_projects) so the entire org hierarchy is
    traversed in a single paginated call — no folder recursion required.
    """
    from google.cloud import resourcemanager_v3
    from google.api_core import exceptions as api_exceptions

    client = resourcemanager_v3.ProjectsClient(credentials=credentials)

    if org_id:
        # org_id may be numeric ("123456") or full resource name ("organizations/123456")
        parent = org_id if org_id.startswith("organizations/") else f"organizations/{org_id}"
        query = f"state:ACTIVE parent:{parent}"
    else:
        query = "state:ACTIVE"

    try:
        request = resourcemanager_v3.SearchProjectsRequest(query=query)
        project_ids = []
        for project in client.search_projects(request=request):
            # query="state:ACTIVE" is server-side; this is defense-in-depth
            if project.state == resourcemanager_v3.Project.State.ACTIVE:
                project_ids.append(project.project_id)
        return project_ids
    except api_exceptions.PermissionDenied:
        print(
            "ERROR: Cannot enumerate GCP projects. Ensure cloudresourcemanager.googleapis.com"
            " is enabled and the credential has resourcemanager.projects.get permission."
        )
        sys.exit(1)


def _apply_project_filters(
    project_ids: List[str],
    include_patterns: Optional[List[str]],
    exclude_patterns: Optional[List[str]],
) -> List[str]:
    """Filter project list by include/exclude glob patterns."""
    if include_patterns is not None:
        project_ids = [
            p for p in project_ids
            if any(fnmatch.fnmatch(p, pat) for pat in include_patterns)
        ]
    if exclude_patterns is not None:
        project_ids = [
            p for p in project_ids
            if not any(fnmatch.fnmatch(p, pat) for pat in exclude_patterns)
        ]
    return project_ids


def _check_apis_enabled(client, project_id: str) -> Tuple[bool, bool]:
    """Check if Compute and DNS APIs are enabled for a project.

    Returns (compute_enabled, dns_enabled).

    Args:
        client: A ServiceUsageClient instance (created once by the caller and reused).
        project_id: The GCP project ID string (e.g. "my-project-123").
    """
    from google.cloud import service_usage_v1
    from google.api_core import exceptions as api_exceptions

    parent = f"projects/{project_id}"
    try:
        request = service_usage_v1.BatchGetServicesRequest(
            parent=parent,
            names=[
                f"{parent}/services/compute.googleapis.com",
                f"{parent}/services/dns.googleapis.com",
            ],
        )
        response = client.batch_get_services(request=request)
        compute_enabled = False
        dns_enabled = False
        for svc in response.services:
            enabled = (svc.state == service_usage_v1.types.Service.State.ENABLED)
            if "compute.googleapis.com" in svc.name:
                compute_enabled = enabled
            elif "dns.googleapis.com" in svc.name:
                dns_enabled = enabled
        return compute_enabled, dns_enabled
    except api_exceptions.PermissionDenied:
        # accessNotConfigured or insufficient IAM — treat both APIs as unavailable
        return False, False
    except Exception:
        # Network/quota transient error — assume enabled, let discovery surface the real error
        return True, True


def _log_api_status(project_id: str, compute_enabled: bool, dns_enabled: bool) -> None:
    """Print [Skip] lines for disabled APIs. Silent for fully-enabled projects."""
    if not compute_enabled:
        print(f"[Skip] {project_id}: Compute API disabled")
    if not dns_enabled:
        print(f"[Skip] {project_id}: DNS API disabled")


def enumerate_gcp_projects(
    credentials,
    adc_project: Optional[str],
    project: Optional[str],
    org_id: Optional[str],
    include_patterns: Optional[List[str]],
    exclude_patterns: Optional[List[str]],
) -> List[ProjectInfo]:
    """Return a curated list of ProjectInfo for accessible ACTIVE GCP projects.

    Backward-compatible: if an explicit project is specified (via the project
    parameter, GOOGLE_CLOUD_PROJECT env var, or ADC), returns a single-element
    list without calling search_projects.

    Args:
        credentials: Validated GCP credential object from get_gcp_credential().
        adc_project: Project ID inferred from the ADC chain (may be None).
        project: Explicit --project flag value (takes priority over env and ADC).
        org_id: Organization ID for scoping enumeration (--org-id flag or
                GOOGLE_CLOUD_ORG_ID env var). Applied only in multi-project path.
        include_patterns: Glob patterns; only matching project IDs are kept.
        exclude_patterns: Glob patterns; matching project IDs are removed.

    Returns:
        List of ProjectInfo with per-project compute_enabled and dns_enabled flags.
    """
    from google.cloud import service_usage_v1

    # Priority: --project flag > GOOGLE_CLOUD_PROJECT env var > ADC project
    # This matches GCP SDK convention: explicit flag always wins.
    explicit_project = project or os.getenv("GOOGLE_CLOUD_PROJECT") or adc_project

    # Create a single ServiceUsageClient and reuse it across all pre-checks.
    usage_client = service_usage_v1.ServiceUsageClient(credentials=credentials)

    if explicit_project:
        # ENUM-03: bypass enumeration — single-project backward-compat path
        compute_ok, dns_ok = _check_apis_enabled(usage_client, explicit_project)
        _log_api_status(explicit_project, compute_ok, dns_ok)
        return [ProjectInfo(
            project_id=explicit_project,
            compute_enabled=compute_ok,
            dns_enabled=dns_ok,
        )]

    # Multi-project enumeration path
    # org_id arg takes priority over env var (same flag-overrides-env convention)
    effective_org_id = org_id or os.getenv("GOOGLE_CLOUD_ORG_ID")
    project_ids = _fetch_active_projects(credentials, effective_org_id)

    # ENUM-05: apply include/exclude glob filters before API pre-checks
    project_ids = _apply_project_filters(project_ids, include_patterns, exclude_patterns)

    # ENUM-02: zero-project case — print actionable hint and exit
    if not project_ids:
        print(
            "ERROR: No ACTIVE GCP projects found."
            " Ensure the credential has resourcemanager.projects.get permission."
        )
        sys.exit(1)

    # ENUM-01: print count before pre-checks so count appears above [Skip] lines
    print(f"Found {len(project_ids)} ACTIVE projects")

    # ENUM-06: per-project API pre-check using shared usage_client
    results: List[ProjectInfo] = []
    for pid in project_ids:
        compute_ok, dns_ok = _check_apis_enabled(usage_client, pid)
        _log_api_status(pid, compute_ok, dns_ok)
        results.append(ProjectInfo(
            project_id=pid,
            compute_enabled=compute_ok,
            dns_enabled=dns_ok,
        ))

    return results


class GCPConfig(BaseConfig):
    """GCP-specific configuration."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        regions: Optional[List[str]] = None,
        output_directory: str = "output",
        output_format: str = "txt",
    ):
        super().__init__(output_directory=output_directory, output_format=output_format)
        self.project_id = project_id or self._get_default_project_id()
        self.regions = regions or []

    def _get_default_project_id(self) -> Optional[str]:
        """Get default project ID from environment variable.

        The project is also returned by get_gcp_credential() from the ADC chain.
        GCPDiscovery._init_gcp_clients() merges both sources.
        """
        return os.getenv("GOOGLE_CLOUD_PROJECT")


def get_all_gcp_regions() -> List[str]:
    """
    Get all available GCP regions for the current project.

    Returns:
        List of GCP region names that are available in the project
    """
    try:
        credentials, project = get_gcp_credential()
        if not project:
            # Fallback to major regions if no project found
            return _get_major_regions()

        # Use compute API to get available regions for the project
        from google.cloud import compute_v1

        client = compute_v1.RegionsClient(credentials=credentials)
        request = compute_v1.ListRegionsRequest(project=project)

        available_regions = []
        for region in client.list(request=request):
            available_regions.append(region.name)

        if available_regions:
            return available_regions
        else:
            # Fallback to major regions if no regions found
            return _get_major_regions()

    except Exception as e:
        print(f"Warning: Could not fetch regions from GCP API: {e}")
        print("Using fallback list of major regions")
        return _get_major_regions()


def _get_major_regions() -> List[str]:
    """
    Get a list of major GCP regions as fallback.

    Returns:
        List of major GCP region names
    """
    # Major GCP regions for compute and networking
    major_regions = [
        "us-central1",
        "us-east1",
        "us-west1",
        "us-west2",
        "us-west3",
        "us-west4",
        "us-east4",
        "us-east5",
        "us-central2",
        "us-south1",
        "europe-west1",
        "europe-west2",
        "europe-west3",
        "europe-west4",
        "europe-west6",
        "europe-west8",
        "europe-west9",
        "europe-west10",
        "europe-west12",
        "europe-central2",
        "europe-north1",
        "asia-east1",
        "asia-southeast1",
        "asia-southeast2",
        "asia-southeast3",
        "asia-northeast1",
        "asia-northeast2",
        "asia-northeast3",
        "asia-south1",
        "asia-south2",
        "australia-southeast1",
        "australia-southeast2",
        "southamerica-east1",
        "northamerica-northeast1",
        "northamerica-northeast2",
    ]

    return major_regions


def validate_gcp_config(config: GCPConfig) -> bool:
    """Validate GCP configuration."""
    if not config.project_id:
        print("Error: GCP project ID is required")
        return False

    if not config.regions:
        print("Warning: No GCP regions specified, using major regions")
        config.regions = get_all_gcp_regions()

    return config.validate()
