"""Tests for GCP token-free resource collectors.

Validates that disks, instance groups, GKE clusters, URL maps, and storage
buckets are discovered correctly as token-free resources with no IPs.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Mock google.cloud modules before importing collectors
_mock_compute_v1 = MagicMock()
_mock_container_v1 = MagicMock()
_mock_storage = MagicMock()
_mock_google = MagicMock()
_mock_google_cloud = MagicMock()
# Wire storage attribute so 'from google.cloud import storage' resolves
_mock_google_cloud.storage = _mock_storage
_mock_google_cloud.compute_v1 = _mock_compute_v1
_mock_google_cloud.container_v1 = _mock_container_v1
_mock_google.cloud = _mock_google_cloud
sys.modules.setdefault("google", _mock_google)
sys.modules.setdefault("google.cloud", _mock_google_cloud)
sys.modules.setdefault("google.cloud.compute_v1", _mock_compute_v1)
sys.modules.setdefault("google.cloud.container_v1", _mock_container_v1)
sys.modules.setdefault("google.cloud.storage", _mock_storage)

from cloud_usage.providers.gcp.collectors.token_free import (
    collect_gcp_disks,
    collect_gcp_gke_cidr_ranges,
    collect_gcp_gke_clusters,
    collect_gcp_instance_groups,
    collect_gcp_storage_buckets,
    collect_gcp_url_maps,
)

PROJECT_ID = "my-gcp-project"


# --- Disk collector tests ---


def _make_mock_disk(name="disk-1", zone="us-central1-a", size_gb=100, status="READY"):
    """Create a mock Compute Disk object."""
    disk = MagicMock()
    disk.name = name
    disk.self_link = f"https://compute.googleapis.com/compute/v1/projects/{PROJECT_ID}/zones/{zone}/disks/{name}"
    disk.size_gb = size_gb
    disk.type_ = f"projects/{PROJECT_ID}/zones/{zone}/diskTypes/pd-standard"
    disk.status = status
    disk.labels = {"env": "prod"}
    return disk


class TestCollectGcpDisks:
    """Tests for collect_gcp_disks."""

    def test_basic_disk_discovery(self):
        """Disks are discovered with correct resource_type and no IPs."""
        disk = _make_mock_disk()
        scoped_list = MagicMock()
        scoped_list.disks = [disk]

        client = MagicMock()
        client.aggregated_list.return_value = [("zones/us-central1-a", scoped_list)]

        resources = collect_gcp_disks(client, PROJECT_ID)

        assert len(resources) == 1
        assert resources[0].resource_type == "gcp-disk"
        assert resources[0].provider == "gcp"
        assert resources[0].account_id == PROJECT_ID
        assert resources[0].ip_addresses == []
        assert resources[0].name == "disk-1"

    def test_disk_details(self):
        """Disk details include size_gb, type, and status."""
        disk = _make_mock_disk(size_gb=500, status="READY")
        scoped_list = MagicMock()
        scoped_list.disks = [disk]

        client = MagicMock()
        client.aggregated_list.return_value = [("zones/us-central1-a", scoped_list)]

        resources = collect_gcp_disks(client, PROJECT_ID)

        assert resources[0].details["size_gb"] == 500
        assert resources[0].details["type"] == "pd-standard"
        assert resources[0].details["status"] == "READY"

    def test_disk_labels_as_tags(self):
        """Disk labels are passed as tags."""
        disk = _make_mock_disk()
        scoped_list = MagicMock()
        scoped_list.disks = [disk]

        client = MagicMock()
        client.aggregated_list.return_value = [("zones/us-central1-a", scoped_list)]

        resources = collect_gcp_disks(client, PROJECT_ID)
        assert resources[0].tags == {"env": "prod"}

    def test_empty_scoped_list_skipped(self):
        """Empty disk scoped list in a zone is skipped."""
        scoped_list = MagicMock()
        scoped_list.disks = None

        client = MagicMock()
        client.aggregated_list.return_value = [("zones/us-east1-b", scoped_list)]

        resources = collect_gcp_disks(client, PROJECT_ID)
        assert len(resources) == 0

    def test_multiple_zones_multiple_disks(self):
        """Disks from multiple zones are all discovered."""
        disk_a = _make_mock_disk(name="disk-a", zone="us-central1-a")
        disk_b = _make_mock_disk(name="disk-b", zone="us-east1-b")

        scoped_a = MagicMock()
        scoped_a.disks = [disk_a]
        scoped_b = MagicMock()
        scoped_b.disks = [disk_b]

        client = MagicMock()
        client.aggregated_list.return_value = [
            ("zones/us-central1-a", scoped_a),
            ("zones/us-east1-b", scoped_b),
        ]

        resources = collect_gcp_disks(client, PROJECT_ID)
        assert len(resources) == 2
        assert resources[0].region == "us-central1"
        assert resources[1].region == "us-east1"

    def test_disk_self_link_fallback(self):
        """Disk without self_link gets constructed resource_id."""
        disk = _make_mock_disk()
        disk.self_link = None
        scoped_list = MagicMock()
        scoped_list.disks = [disk]

        client = MagicMock()
        client.aggregated_list.return_value = [("zones/us-central1-a", scoped_list)]

        resources = collect_gcp_disks(client, PROJECT_ID)
        assert "projects/" in resources[0].resource_id
        assert "disks/disk-1" in resources[0].resource_id


# --- Instance Group collector tests ---


def _make_mock_instance_group(name="ig-1", zone="us-central1-a", size=3):
    """Create a mock Instance Group object."""
    group = MagicMock()
    group.name = name
    group.self_link = f"https://compute.googleapis.com/compute/v1/projects/{PROJECT_ID}/zones/{zone}/instanceGroups/{name}"
    group.size = size
    return group


class TestCollectGcpInstanceGroups:
    """Tests for collect_gcp_instance_groups."""

    def test_basic_instance_group(self):
        """Instance groups are discovered with correct type and no IPs."""
        group = _make_mock_instance_group()
        scoped_list = MagicMock()
        scoped_list.instance_groups = [group]

        client = MagicMock()
        client.aggregated_list.return_value = [("zones/us-central1-a", scoped_list)]

        resources = collect_gcp_instance_groups(client, PROJECT_ID)

        assert len(resources) == 1
        assert resources[0].resource_type == "gcp-instance-group"
        assert resources[0].ip_addresses == []
        assert resources[0].details["size"] == 3

    def test_empty_scoped_list_skipped(self):
        """Empty instance group scoped list is skipped."""
        scoped_list = MagicMock()
        scoped_list.instance_groups = None

        client = MagicMock()
        client.aggregated_list.return_value = [("zones/us-east1-b", scoped_list)]

        resources = collect_gcp_instance_groups(client, PROJECT_ID)
        assert len(resources) == 0

    def test_instance_group_self_link_fallback(self):
        """Instance group without self_link gets constructed resource_id."""
        group = _make_mock_instance_group()
        group.self_link = None
        scoped_list = MagicMock()
        scoped_list.instance_groups = [group]

        client = MagicMock()
        client.aggregated_list.return_value = [("zones/us-central1-a", scoped_list)]

        resources = collect_gcp_instance_groups(client, PROJECT_ID)
        assert "instanceGroups/ig-1" in resources[0].resource_id


# --- GKE Cluster collector tests ---


def _make_mock_cluster(
    name="cluster-1", location="us-central1", node_count=6,
    status="RUNNING", cidr="10.0.0.0/14",
):
    """Create a mock GKE Cluster object."""
    cluster = MagicMock()
    cluster.name = name
    cluster.location = location
    cluster.self_link = f"https://container.googleapis.com/v1/projects/{PROJECT_ID}/locations/{location}/clusters/{name}"
    cluster.current_node_count = node_count
    cluster.status = status
    cluster.cluster_ipv4_cidr = cidr
    cluster.resource_labels = {"team": "platform"}
    return cluster


class TestCollectGcpGkeClusters:
    """Tests for collect_gcp_gke_clusters."""

    def test_basic_gke_cluster(self):
        """GKE clusters are discovered as token-free with no IPs."""
        cluster = _make_mock_cluster()
        response = MagicMock()
        response.clusters = [cluster]

        client = MagicMock()
        client.list_clusters.return_value = response

        resources = collect_gcp_gke_clusters(client, PROJECT_ID)

        assert len(resources) == 1
        assert resources[0].resource_type == "gcp-gke-cluster"
        assert resources[0].ip_addresses == []
        assert resources[0].region == "us-central1"
        assert resources[0].name == "cluster-1"

    def test_gke_cluster_details(self):
        """GKE cluster details include status, node_count, cidr."""
        cluster = _make_mock_cluster(node_count=12, cidr="10.4.0.0/14")
        response = MagicMock()
        response.clusters = [cluster]

        client = MagicMock()
        client.list_clusters.return_value = response

        resources = collect_gcp_gke_clusters(client, PROJECT_ID)

        assert resources[0].details["node_count"] == 12
        assert resources[0].details["cluster_ipv4_cidr"] == "10.4.0.0/14"
        assert resources[0].details["status"] == "RUNNING"

    def test_gke_cluster_labels_as_tags(self):
        """GKE cluster resource_labels are passed as tags."""
        cluster = _make_mock_cluster()
        response = MagicMock()
        response.clusters = [cluster]

        client = MagicMock()
        client.list_clusters.return_value = response

        resources = collect_gcp_gke_clusters(client, PROJECT_ID)
        assert resources[0].tags == {"team": "platform"}

    def test_gke_none_container_client_returns_empty(self):
        """None container_client returns [] (graceful fallback)."""
        resources = collect_gcp_gke_clusters(None, PROJECT_ID)
        assert resources == []

    def test_gke_cluster_self_link_fallback(self):
        """GKE cluster without self_link gets constructed resource_id."""
        cluster = _make_mock_cluster()
        cluster.self_link = None
        response = MagicMock()
        response.clusters = [cluster]

        client = MagicMock()
        client.list_clusters.return_value = response

        resources = collect_gcp_gke_clusters(client, PROJECT_ID)
        assert "locations/us-central1/clusters/cluster-1" in resources[0].resource_id

    def test_gke_cluster_no_labels(self):
        """GKE cluster with no resource_labels gets empty tags."""
        cluster = _make_mock_cluster()
        cluster.resource_labels = None
        response = MagicMock()
        response.clusters = [cluster]

        client = MagicMock()
        client.list_clusters.return_value = response

        resources = collect_gcp_gke_clusters(client, PROJECT_ID)
        assert resources[0].tags == {}

    def test_multiple_gke_clusters(self):
        """Multiple clusters in different locations are all discovered."""
        cluster_a = _make_mock_cluster(name="cluster-a", location="us-central1")
        cluster_b = _make_mock_cluster(name="cluster-b", location="europe-west1")
        response = MagicMock()
        response.clusters = [cluster_a, cluster_b]

        client = MagicMock()
        client.list_clusters.return_value = response

        resources = collect_gcp_gke_clusters(client, PROJECT_ID)
        assert len(resources) == 2
        assert resources[0].region == "us-central1"
        assert resources[1].region == "europe-west1"


# --- URL Map collector tests ---


def _make_mock_url_map(name="urlmap-1"):
    """Create a mock URL Map object."""
    url_map = MagicMock()
    url_map.name = name
    url_map.self_link = f"https://compute.googleapis.com/compute/v1/projects/{PROJECT_ID}/global/urlMaps/{name}"
    return url_map


class TestCollectGcpUrlMaps:
    """Tests for collect_gcp_url_maps."""

    def test_basic_url_map(self):
        """URL maps are discovered with correct type and no IPs."""
        url_map = _make_mock_url_map()
        scoped_list = MagicMock()
        scoped_list.url_maps = [url_map]

        client = MagicMock()
        client.aggregated_list.return_value = [("global", scoped_list)]

        resources = collect_gcp_url_maps(client, PROJECT_ID)

        assert len(resources) == 1
        assert resources[0].resource_type == "gcp-url-map"
        assert resources[0].ip_addresses == []
        assert resources[0].region == "global"

    def test_url_map_none_client_returns_empty(self):
        """None url_maps_client returns [] (graceful fallback)."""
        resources = collect_gcp_url_maps(None, PROJECT_ID)
        assert resources == []

    def test_url_map_empty_scoped_list(self):
        """Empty url_maps scoped list is skipped."""
        scoped_list = MagicMock()
        scoped_list.url_maps = None

        client = MagicMock()
        client.aggregated_list.return_value = [("global", scoped_list)]

        resources = collect_gcp_url_maps(client, PROJECT_ID)
        assert len(resources) == 0


# --- Storage Bucket collector tests ---


def _make_mock_bucket(name="my-bucket", location="US", storage_class="STANDARD"):
    """Create a mock Storage Bucket object."""
    bucket = MagicMock()
    bucket.name = name
    bucket.location = location
    bucket.storage_class = storage_class
    return bucket


class TestCollectGcpStorageBuckets:
    """Tests for collect_gcp_storage_buckets."""

    def test_basic_storage_bucket(self):
        """Storage buckets are discovered with correct type and no IPs."""
        bucket = _make_mock_bucket()
        mock_client_instance = MagicMock()
        mock_client_instance.list_buckets.return_value = [bucket]

        credentials = MagicMock()

        # The google.cloud.storage module is mocked at the top of this file
        # (via sys.modules). Configure the Client on that mock.
        _mock_storage.Client.return_value = mock_client_instance
        resources = collect_gcp_storage_buckets(credentials, PROJECT_ID)

        assert len(resources) == 1
        assert resources[0].resource_type == "gcp-storage-bucket"
        assert resources[0].ip_addresses == []
        assert resources[0].name == "my-bucket"

    def test_storage_bucket_details(self):
        """Bucket details include location and storage_class."""
        bucket = _make_mock_bucket(location="EU", storage_class="NEARLINE")
        mock_client_instance = MagicMock()
        mock_client_instance.list_buckets.return_value = [bucket]

        credentials = MagicMock()

        _mock_storage.Client.return_value = mock_client_instance
        resources = collect_gcp_storage_buckets(credentials, PROJECT_ID)

        assert resources[0].details["location"] == "EU"
        assert resources[0].details["storage_class"] == "NEARLINE"

    def test_storage_buckets_import_error_returns_empty(self):
        """ImportError for google.cloud.storage returns [] gracefully."""
        credentials = MagicMock()

        # To trigger ImportError, we need to:
        # 1. Set sys.modules["google.cloud.storage"] to None
        # 2. Remove the storage attribute from the google.cloud mock
        saved_mod = sys.modules.get("google.cloud.storage")
        saved_attr = getattr(_mock_google_cloud, "storage", None)
        try:
            sys.modules["google.cloud.storage"] = None  # type: ignore[assignment]
            # Remove attribute so 'from google.cloud import storage' fails
            if hasattr(_mock_google_cloud, "storage"):
                delattr(_mock_google_cloud, "storage")
            resources = collect_gcp_storage_buckets(credentials, PROJECT_ID)
            assert resources == []
        finally:
            if saved_mod is not None:
                sys.modules["google.cloud.storage"] = saved_mod
            else:
                sys.modules.pop("google.cloud.storage", None)
            if saved_attr is not None:
                _mock_google_cloud.storage = saved_attr

    def test_multiple_buckets(self):
        """Multiple buckets are all discovered."""
        bucket_a = _make_mock_bucket(name="bucket-a")
        bucket_b = _make_mock_bucket(name="bucket-b")
        mock_client_instance = MagicMock()
        mock_client_instance.list_buckets.return_value = [bucket_a, bucket_b]

        credentials = MagicMock()

        _mock_storage.Client.return_value = mock_client_instance
        resources = collect_gcp_storage_buckets(credentials, PROJECT_ID)

        assert len(resources) == 2
        assert resources[0].name == "bucket-a"
        assert resources[1].name == "bucket-b"


# --- GKE CIDR Ranges collector tests (Phase 28 GCPG-02) ---


def _make_mock_cluster_with_cidrs(
    name="cluster-1",
    location="us-central1",
    control_plane_cidr="10.0.0.0/28",
    pod_cidr="10.1.0.0/16",
    service_cidr="10.2.0.0/20",
):
    """Create a mock GKE Cluster with private cluster config and IP allocation policy."""
    cluster = MagicMock()
    cluster.name = name
    cluster.location = location
    cluster.self_link = (
        f"https://container.googleapis.com/v1/projects/{PROJECT_ID}"
        f"/locations/{location}/clusters/{name}"
    )
    cluster.resource_labels = {}
    # private_cluster_config
    pcc = MagicMock()
    pcc.master_ipv4_cidr_block = control_plane_cidr
    cluster.private_cluster_config = pcc
    # ip_allocation_policy
    iap = MagicMock()
    iap.cluster_ipv4_cidr_block = pod_cidr
    iap.services_ipv4_cidr_block = service_cidr
    cluster.ip_allocation_policy = iap
    return cluster


class TestCollectGcpGkeCidrRanges:
    """Phase 28 GCPG-02: GKE CIDR ranges (control-plane, pod, service).

    Tests are RED until collect_gcp_gke_cidr_ranges is implemented in Plan 02.
    """

    def test_cluster_with_all_cidrs_emits_three(self):
        """Cluster with all three CIDRs emits three DDI resources."""
        cluster = _make_mock_cluster_with_cidrs(
            control_plane_cidr="10.0.0.0/28",
            pod_cidr="10.1.0.0/16",
            service_cidr="10.2.0.0/20",
        )
        response = MagicMock()
        response.clusters = [cluster]

        client = MagicMock()
        client.list_clusters.return_value = response

        result = collect_gcp_gke_cidr_ranges(client, PROJECT_ID)

        assert len(result) == 3
        resource_types = {r.resource_type for r in result}
        assert "gcp-gke-control-plane-range" in resource_types
        assert "gcp-gke-pod-range" in resource_types
        assert "gcp-gke-service-range" in resource_types

    def test_cluster_without_private_control_plane_emits_two(self):
        """Cluster without control-plane CIDR emits only pod and service ranges."""
        cluster = _make_mock_cluster_with_cidrs(
            control_plane_cidr="",  # falsy — no control plane CIDR
            pod_cidr="10.1.0.0/16",
            service_cidr="10.2.0.0/20",
        )
        response = MagicMock()
        response.clusters = [cluster]

        client = MagicMock()
        client.list_clusters.return_value = response

        result = collect_gcp_gke_cidr_ranges(client, PROJECT_ID)

        assert len(result) == 2
        resource_types = {r.resource_type for r in result}
        assert "gcp-gke-pod-range" in resource_types
        assert "gcp-gke-service-range" in resource_types
        assert "gcp-gke-control-plane-range" not in resource_types

    def test_cluster_with_no_cidrs_emits_nothing(self):
        """Cluster with no CIDRs set emits no DDI resources."""
        cluster = _make_mock_cluster_with_cidrs(
            control_plane_cidr="",
            pod_cidr="",
            service_cidr="",
        )
        response = MagicMock()
        response.clusters = [cluster]

        client = MagicMock()
        client.list_clusters.return_value = response

        result = collect_gcp_gke_cidr_ranges(client, PROJECT_ID)

        assert result == []

    def test_none_container_client_returns_empty(self):
        """None container_client returns [] (graceful fallback)."""
        result = collect_gcp_gke_cidr_ranges(None, PROJECT_ID)
        assert result == []

    def test_gke_cidr_ip_addresses_are_empty(self):
        """All GKE CIDR resources have ip_addresses==[] (DDI-only)."""
        cluster = _make_mock_cluster_with_cidrs(
            control_plane_cidr="10.0.0.0/28",
            pod_cidr="10.1.0.0/16",
            service_cidr="10.2.0.0/20",
        )
        response = MagicMock()
        response.clusters = [cluster]

        client = MagicMock()
        client.list_clusters.return_value = response

        result = collect_gcp_gke_cidr_ranges(client, PROJECT_ID)

        assert all(r.ip_addresses == [] for r in result)
