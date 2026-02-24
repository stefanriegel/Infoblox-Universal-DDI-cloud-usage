"""GCP token-free resource collectors.

Discovers Compute Persistent Disks, Instance Groups, GKE Clusters,
URL Maps, and Cloud Storage Buckets. These resources are discovered
for the audit trail but never counted toward tokens -- they appear
in the detail sheet with counted=False and a skip_reason.
"""

from __future__ import annotations

import logging
from typing import Any

from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


@retry_with_backoff(max_retries=3)
def collect_gcp_disks(
    disks_client: Any,
    project_id: str,
) -> list[CloudResource]:
    """Discover all Compute Persistent Disks in a project via aggregatedList.

    Uses disks_client.aggregated_list() to fetch all disks across all zones
    in a single API call per project. Disks are token-free (no IPs).

    Args:
        disks_client: compute_v1.DisksClient instance.
        project_id: GCP project ID.

    Returns:
        List of CloudResource with resource_type="gcp-disk".
    """
    from google.cloud import compute_v1

    resources: list[CloudResource] = []

    request = compute_v1.AggregatedListDisksRequest(project=project_id)
    for zone_key, scoped_list in disks_client.aggregated_list(request=request):
        if not scoped_list.disks:
            continue

        zone_name = zone_key.split("/")[-1]
        region = zone_name.rsplit("-", 1)[0] if "-" in zone_name else "global"

        for disk in scoped_list.disks:
            resource_id = (
                disk.self_link
                if getattr(disk, "self_link", None)
                else f"projects/{project_id}/zones/{zone_name}/disks/{disk.name}"
            )

            disk_type = (getattr(disk, "type_", "") or "").split("/")[-1]

            resources.append(
                CloudResource(
                    resource_id=resource_id,
                    resource_type="gcp-disk",
                    provider="gcp",
                    account_id=project_id,
                    region=region,
                    name=disk.name,
                    ip_addresses=[],
                    tags=dict(disk.labels) if getattr(disk, "labels", None) else {},
                    details={
                        "size_gb": getattr(disk, "size_gb", ""),
                        "type": disk_type,
                        "status": disk.status,
                    },
                )
            )

    logger.debug(
        "Discovered %d disks in project %s",
        len(resources),
        project_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_gcp_instance_groups(
    instance_groups_client: Any,
    project_id: str,
) -> list[CloudResource]:
    """Discover all Instance Groups in a project via aggregatedList.

    Uses instance_groups_client.aggregated_list() to fetch all instance
    groups across all zones in a single API call. Instance groups are
    token-free (no IPs).

    Args:
        instance_groups_client: compute_v1.InstanceGroupsClient instance.
        project_id: GCP project ID.

    Returns:
        List of CloudResource with resource_type="gcp-instance-group".
    """
    from google.cloud import compute_v1

    resources: list[CloudResource] = []

    request = compute_v1.AggregatedListInstanceGroupsRequest(project=project_id)
    for zone_key, scoped_list in instance_groups_client.aggregated_list(request=request):
        if not scoped_list.instance_groups:
            continue

        zone_name = zone_key.split("/")[-1]
        region = zone_name.rsplit("-", 1)[0] if "-" in zone_name else "global"

        for group in scoped_list.instance_groups:
            resource_id = (
                group.self_link
                if getattr(group, "self_link", None)
                else f"projects/{project_id}/zones/{zone_name}/instanceGroups/{group.name}"
            )

            resources.append(
                CloudResource(
                    resource_id=resource_id,
                    resource_type="gcp-instance-group",
                    provider="gcp",
                    account_id=project_id,
                    region=region,
                    name=group.name,
                    ip_addresses=[],
                    tags={},
                    details={
                        "size": getattr(group, "size", 0),
                    },
                )
            )

    logger.debug(
        "Discovered %d instance groups in project %s",
        len(resources),
        project_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_gcp_gke_clusters(
    container_client: Any | None,
    project_id: str,
) -> list[CloudResource]:
    """Discover all GKE clusters in a project.

    Uses container_client.list_clusters() with parent=projects/{id}/locations/-
    for all-locations enumeration (Pattern 5 from RESEARCH.md). GKE clusters
    are token-free metadata -- nodes are already discovered as gcp-vm.

    Handles None container_client gracefully (returns []) for environments
    where google-cloud-container is not installed.

    Args:
        container_client: container_v1.ClusterManagerClient, or None.
        project_id: GCP project ID.

    Returns:
        List of CloudResource with resource_type="gcp-gke-cluster".
    """
    if container_client is None:
        return []

    resources: list[CloudResource] = []

    response = container_client.list_clusters(
        parent=f"projects/{project_id}/locations/-",
    )

    for cluster in response.clusters:
        resource_id = (
            cluster.self_link
            if getattr(cluster, "self_link", None)
            else f"projects/{project_id}/locations/{cluster.location}/clusters/{cluster.name}"
        )

        resources.append(
            CloudResource(
                resource_id=resource_id,
                resource_type="gcp-gke-cluster",
                provider="gcp",
                account_id=project_id,
                region=cluster.location,
                name=cluster.name,
                ip_addresses=[],
                tags=dict(cluster.resource_labels) if cluster.resource_labels else {},
                details={
                    "status": str(cluster.status),
                    "node_count": cluster.current_node_count,
                    "cluster_ipv4_cidr": cluster.cluster_ipv4_cidr,
                },
            )
        )

    logger.debug(
        "Discovered %d GKE clusters in project %s",
        len(resources),
        project_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_gcp_url_maps(
    url_maps_client: Any | None,
    project_id: str,
) -> list[CloudResource]:
    """Discover all URL Maps in a project via aggregatedList.

    Uses url_maps_client.aggregated_list() to fetch all URL maps across
    all regions in a single API call. URL maps are token-free (no IPs).

    Handles None url_maps_client gracefully (returns []).

    Args:
        url_maps_client: compute_v1.UrlMapsClient, or None.
        project_id: GCP project ID.

    Returns:
        List of CloudResource with resource_type="gcp-url-map".
    """
    if url_maps_client is None:
        return []

    from google.cloud import compute_v1

    resources: list[CloudResource] = []

    request = compute_v1.AggregatedListUrlMapsRequest(project=project_id)
    for scope_key, scoped_list in url_maps_client.aggregated_list(request=request):
        if not scoped_list.url_maps:
            continue

        region = scope_key.split("/")[-1]

        for url_map in scoped_list.url_maps:
            resource_id = (
                url_map.self_link
                if getattr(url_map, "self_link", None)
                else f"projects/{project_id}/global/urlMaps/{url_map.name}"
            )

            resources.append(
                CloudResource(
                    resource_id=resource_id,
                    resource_type="gcp-url-map",
                    provider="gcp",
                    account_id=project_id,
                    region=region,
                    name=url_map.name,
                    ip_addresses=[],
                    tags={},
                    details={},
                )
            )

    logger.debug(
        "Discovered %d URL maps in project %s",
        len(resources),
        project_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_gcp_storage_buckets(
    credentials: Any,
    project_id: str,
) -> list[CloudResource]:
    """Discover all Cloud Storage Buckets in a project.

    Uses google.cloud.storage.Client to list buckets. The storage client
    is created inline with the provided credentials and project.

    Handles ImportError gracefully (returns []) since google-cloud-storage
    is not in requirements.txt -- it is optional for a token-free resource
    that does not affect token count.

    Args:
        credentials: GCP credential object from google.auth.default().
        project_id: GCP project ID.

    Returns:
        List of CloudResource with resource_type="gcp-storage-bucket".
    """
    try:
        from google.cloud import storage
    except ImportError:
        logger.debug(
            "google-cloud-storage not installed, skipping bucket collection for %s",
            project_id,
        )
        return []

    resources: list[CloudResource] = []

    client = storage.Client(project=project_id, credentials=credentials)
    for bucket in client.list_buckets():
        resources.append(
            CloudResource(
                resource_id=f"projects/{project_id}/buckets/{bucket.name}",
                resource_type="gcp-storage-bucket",
                provider="gcp",
                account_id=project_id,
                region=bucket.location,
                name=bucket.name,
                ip_addresses=[],
                tags={},
                details={
                    "location": bucket.location,
                    "storage_class": bucket.storage_class,
                },
            )
        )

    logger.debug(
        "Discovered %d storage buckets in project %s",
        len(resources),
        project_id,
    )
    return resources
