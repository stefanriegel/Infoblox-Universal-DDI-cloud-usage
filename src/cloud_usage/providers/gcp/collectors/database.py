"""GCP database resource collectors.

Discovers Cloud SQL instances via the googleapiclient discovery API
(Pitfall 4: no dedicated gRPC client for Cloud SQL Admin). Extracts
private and public IPs from the ipAddresses list. Supports pagination
via list_next().
"""

from __future__ import annotations

import logging
from typing import Any

from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


@retry_with_backoff(max_retries=3)
def collect_gcp_cloud_sql(
    sqladmin_service: Any | None,
    project_id: str,
) -> list[CloudResource]:
    """Discover all Cloud SQL instances in a project.

    Uses the googleapiclient discovery API for Cloud SQL Admin since no
    dedicated gRPC client library exists (Pitfall 4). Paginates using
    list_next() to handle projects with many instances.

    Handles None sqladmin_service gracefully (returns []) for environments
    where google-api-python-client is not installed.

    Args:
        sqladmin_service: googleapiclient discovery service for sqladmin v1,
            or None if the package is not installed.
        project_id: GCP project ID.

    Returns:
        List of CloudResource with resource_type="gcp-cloud-sql".
    """
    if sqladmin_service is None:
        return []

    resources: list[CloudResource] = []

    request = sqladmin_service.instances().list(project=project_id)
    while request is not None:
        response = request.execute()

        for instance in response.get("items", []):
            # IP extraction: iterate ipAddresses list
            ip_addresses: list[str] = []
            for ip_entry in instance.get("ipAddresses", []):
                ip_addr = ip_entry.get("ipAddress")
                if ip_addr:
                    ip_addresses.append(ip_addr)

            resources.append(
                CloudResource(
                    resource_id=instance.get(
                        "selfLink",
                        f"projects/{project_id}/instances/{instance['name']}",
                    ),
                    resource_type="gcp-cloud-sql",
                    provider="gcp",
                    account_id=project_id,
                    region=instance.get("region", "unknown"),
                    name=instance["name"],
                    ip_addresses=ip_addresses,
                    tags=instance.get("settings", {}).get("userLabels", {}) or {},
                    details={
                        "database_version": instance.get("databaseVersion", ""),
                        "tier": instance.get("settings", {}).get("tier", ""),
                        "state": instance.get("state", ""),
                    },
                )
            )

        request = sqladmin_service.instances().list_next(
            previous_request=request,
            previous_response=response,
        )

    logger.debug(
        "Discovered %d Cloud SQL instances in project %s",
        len(resources),
        project_id,
    )
    return resources
