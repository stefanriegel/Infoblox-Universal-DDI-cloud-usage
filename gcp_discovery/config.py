"""
GCP Configuration for Cloud Discovery
"""

import os
from typing import List, Optional

from google.auth import default
from google.auth.exceptions import DefaultCredentialsError

from shared.config import BaseConfig


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

    def _get_default_project_id(self) -> str:
        """Get default project ID from environment or gcloud CLI."""
        # Try environment variable first
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        if project_id:
            return project_id

        # Try gcloud CLI
        try:
            import subprocess

            result = subprocess.run(
                ["gcloud", "config", "get-value", "project"],
                capture_output=True,
                text=True,
                check=True,
            )
            project_id = result.stdout.strip()
            if project_id and project_id != "(unset)":
                return project_id
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Fallback to a default
        return "default-project"


def get_gcp_credential():
    """Get GCP credentials using default authentication."""
    try:
        credentials, project = default()
        return credentials, project
    except DefaultCredentialsError as e:
        raise Exception(
            f"GCP credentials not found: {e}. Please run 'gcloud auth "
            "application-default login' or set GOOGLE_APPLICATION_CREDENTIALS."
        )


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
