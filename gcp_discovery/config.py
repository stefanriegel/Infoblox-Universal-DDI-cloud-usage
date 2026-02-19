"""
GCP Configuration for Cloud Discovery
"""

import os
import sys
import threading
from typing import List, Optional

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
