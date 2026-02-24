"""End-to-end integration tests for GCP discovery pipeline.

Comprehensive tests exercising the full pipeline: discovery across projects,
categorization, IP counting, token calculation, and output generation.
Uses unittest.mock for all GCP SDK clients (no real GCP calls).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Mock google.cloud modules before importing GCP modules
_mock_compute_v1 = MagicMock()
_mock_container_v1 = MagicMock()
_mock_storage = MagicMock()
_mock_dns = MagicMock()
_mock_google = MagicMock()
_mock_google_cloud = MagicMock()
_mock_google_cloud.compute_v1 = _mock_compute_v1
_mock_google_cloud.container_v1 = _mock_container_v1
_mock_google_cloud.storage = _mock_storage
_mock_google_cloud.dns = _mock_dns
_mock_google.cloud = _mock_google_cloud
sys.modules.setdefault("google", _mock_google)
sys.modules.setdefault("google.cloud", _mock_google_cloud)
sys.modules.setdefault("google.cloud.compute_v1", _mock_compute_v1)
sys.modules.setdefault("google.cloud.container_v1", _mock_container_v1)
sys.modules.setdefault("google.cloud.storage", _mock_storage)
sys.modules.setdefault("google.cloud.dns", _mock_dns)

from cloud_usage.counting.asset_dedup import (
    deduplicate_assets,
    exclude_managed_service_resources,
    fold_enis_into_parents,
)
from cloud_usage.counting.categorizer import categorize_resources
from cloud_usage.counting.ip_counter import deduplicate_ips_per_vpc
from cloud_usage.counting.token_calculator import (
    calculate_account_tokens,
    calculate_provider_tokens,
)
from cloud_usage.output.xlsx_report import write_xlsx_report
from cloud_usage.providers.gcp.client_factory import GCPClients
from cloud_usage.providers.gcp.projects import ProjectInfo
from cloud_usage.providers.gcp.provider import GCPDiscoveryProvider
from cloud_usage.schema.resource import CloudResource

PROJECT_ID = "test-project-001"
PROJECT_ID_2 = "test-project-002"
PROJECT_ID_3 = "test-project-003"


# --- Mock resource builders ---


def _make_project_info(
    project_id: str = PROJECT_ID,
    compute_enabled: bool = True,
    dns_enabled: bool = True,
    sqladmin_enabled: bool = True,
    container_enabled: bool = True,
) -> ProjectInfo:
    """Create a ProjectInfo with configurable API flags."""
    return ProjectInfo(
        project_id=project_id,
        compute_enabled=compute_enabled,
        dns_enabled=dns_enabled,
        sqladmin_enabled=sqladmin_enabled,
        container_enabled=container_enabled,
    )


def _make_mock_network(name="vpc-1", project_id=PROJECT_ID):
    """Create a mock VPC network."""
    net = MagicMock()
    net.name = name
    net.self_link = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/global/networks/{name}"
    net.labels = {}
    net.auto_create_subnetworks = True
    return net


def _make_mock_subnet(name="subnet-1", region="us-central1", project_id=PROJECT_ID):
    """Create a mock subnet scoped list entry."""
    subnet = MagicMock()
    subnet.name = name
    subnet.self_link = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/subnetworks/{name}"
    subnet.labels = {}
    subnet.ip_cidr_range = "10.0.0.0/24"
    subnet.network = f"projects/{project_id}/global/networks/vpc-1"
    return subnet


def _make_mock_dns_zone(zone_name="test-zone", dns_name="test.example.com."):
    """Create a mock DNS zone."""
    zone = MagicMock()
    zone.name = zone_name
    zone.dns_name = dns_name
    zone.visibility = "public"
    return zone


def _make_mock_dns_record_set(name="www.test.example.com.", record_type="A", rrdatas=None, ttl=300):
    """Create a mock DNS record set."""
    rs = MagicMock()
    rs.name = name
    rs.record_type = record_type
    rs.rrdatas = rrdatas or []
    rs.ttl = ttl
    return rs


def _make_mock_vm(name="vm-1", zone="us-central1-a", private_ip="10.0.0.5", public_ip=None, project_id=PROJECT_ID):
    """Create a mock VM instance."""
    vm = MagicMock()
    vm.name = name
    vm.self_link = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/zones/{zone}/instances/{name}"
    vm.labels = {}
    vm.machine_type = f"projects/{project_id}/zones/{zone}/machineTypes/n1-standard-1"
    vm.status = "RUNNING"

    iface = MagicMock()
    iface.network_i_p = private_ip
    ac = MagicMock()
    ac.nat_i_p = public_ip
    iface.access_configs = [ac] if public_ip else []
    vm.network_interfaces = [iface]
    return vm


def _make_mock_forwarding_rule(name="fr-1", ip="34.120.0.1", region="us-central1", project_id=PROJECT_ID):
    """Create a mock forwarding rule."""
    rule = MagicMock(spec=["name", "self_link", "labels", "load_balancing_scheme", "target", "ip_protocol", "I_p_address"])
    rule.name = name
    rule.self_link = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/regions/{region}/forwardingRules/{name}"
    rule.labels = {}
    rule.load_balancing_scheme = "EXTERNAL"
    rule.target = f"projects/{project_id}/regions/{region}/targetPools/pool-1"
    rule.ip_protocol = "TCP"
    rule.I_p_address = ip
    return rule


def _make_mock_disk(name="disk-1", zone="us-central1-a", project_id=PROJECT_ID):
    """Create a mock disk."""
    disk = MagicMock()
    disk.name = name
    disk.self_link = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/zones/{zone}/disks/{name}"
    disk.labels = {}
    disk.size_gb = 100
    disk.type_ = f"projects/{project_id}/zones/{zone}/diskTypes/pd-standard"
    disk.status = "READY"
    return disk


def _make_mock_gke_cluster(name="cluster-1", location="us-central1", project_id=PROJECT_ID):
    """Create a mock GKE cluster."""
    cluster = MagicMock()
    cluster.name = name
    cluster.location = location
    cluster.self_link = f"https://container.googleapis.com/v1/projects/{project_id}/locations/{location}/clusters/{name}"
    cluster.current_node_count = 3
    cluster.status = "RUNNING"
    cluster.cluster_ipv4_cidr = "10.0.0.0/14"
    cluster.resource_labels = {}
    return cluster


def _make_mock_cloud_sql(name="sql-1", region="us-central1", ips=None, project_id=PROJECT_ID):
    """Create a mock Cloud SQL instance dict."""
    ip_entries = []
    for ip in (ips or []):
        ip_entries.append({"ipAddress": ip, "type": "PRIMARY"})
    return {
        "name": name,
        "selfLink": f"https://sqladmin.googleapis.com/sql/v1beta4/projects/{project_id}/instances/{name}",
        "region": region,
        "ipAddresses": ip_entries,
        "databaseVersion": "POSTGRES_14",
        "settings": {"tier": "db-f1-micro", "userLabels": {}},
        "state": "RUNNABLE",
    }


def _make_scoped_list(field_name, items):
    """Create a scoped list with items on the named field."""
    sl = MagicMock()
    setattr(sl, field_name, items if items else None)
    return sl


def _setup_mock_clients(
    networks=None, subnets=None, vms=None, forwarding_rules=None,
    reserved_ips=None, global_reserved_ips=None, disks=None,
    instance_groups=None, url_maps=None, gke_clusters=None,
    cloud_sql_instances=None, storage_buckets=None,
):
    """Create a GCPClients with mocked SDK clients."""
    clients = GCPClients()

    # Networks (global list)
    clients.networks = MagicMock()
    clients.networks.list.return_value = networks or []

    # Subnetworks (aggregatedList)
    clients.subnetworks = MagicMock()
    if subnets:
        scoped = _make_scoped_list("subnetworks", subnets)
        clients.subnetworks.aggregated_list.return_value = [("regions/us-central1", scoped)]
    else:
        clients.subnetworks.aggregated_list.return_value = []

    # Instances (aggregatedList)
    clients.instances = MagicMock()
    if vms:
        scoped = _make_scoped_list("instances", vms)
        clients.instances.aggregated_list.return_value = [("zones/us-central1-a", scoped)]
    else:
        clients.instances.aggregated_list.return_value = []

    # Forwarding rules (aggregatedList)
    clients.forwarding_rules = MagicMock()
    if forwarding_rules:
        scoped = _make_scoped_list("forwarding_rules", forwarding_rules)
        clients.forwarding_rules.aggregated_list.return_value = [("regions/us-central1", scoped)]
    else:
        clients.forwarding_rules.aggregated_list.return_value = []

    # Addresses (aggregatedList)
    clients.addresses = MagicMock()
    if reserved_ips:
        scoped = _make_scoped_list("addresses", reserved_ips)
        clients.addresses.aggregated_list.return_value = [("regions/us-central1", scoped)]
    else:
        clients.addresses.aggregated_list.return_value = []

    # Global addresses (list)
    clients.global_addresses = MagicMock()
    clients.global_addresses.list.return_value = global_reserved_ips or []

    # Disks (aggregatedList)
    clients.disks = MagicMock()
    if disks:
        scoped = _make_scoped_list("disks", disks)
        clients.disks.aggregated_list.return_value = [("zones/us-central1-a", scoped)]
    else:
        clients.disks.aggregated_list.return_value = []

    # Instance groups (aggregatedList)
    clients.instance_groups = MagicMock()
    if instance_groups:
        scoped = _make_scoped_list("instance_groups", instance_groups)
        clients.instance_groups.aggregated_list.return_value = [("zones/us-central1-a", scoped)]
    else:
        clients.instance_groups.aggregated_list.return_value = []

    # URL maps (aggregatedList)
    clients.url_maps = MagicMock()
    if url_maps:
        scoped = _make_scoped_list("url_maps", url_maps)
        clients.url_maps.aggregated_list.return_value = [("global", scoped)]
    else:
        clients.url_maps.aggregated_list.return_value = []

    # GKE clusters (list_clusters)
    clients.container = MagicMock()
    if gke_clusters:
        response = MagicMock()
        response.clusters = gke_clusters
        clients.container.list_clusters.return_value = response
    else:
        response = MagicMock()
        response.clusters = []
        clients.container.list_clusters.return_value = response

    # Cloud SQL (discovery API)
    clients.sqladmin = MagicMock()
    if cloud_sql_instances:
        request_mock = MagicMock()
        request_mock.execute.return_value = {"items": cloud_sql_instances}
        clients.sqladmin.instances.return_value.list.return_value = request_mock
        clients.sqladmin.instances.return_value.list_next.return_value = None
    else:
        request_mock = MagicMock()
        request_mock.execute.return_value = {"items": []}
        clients.sqladmin.instances.return_value.list.return_value = request_mock
        clients.sqladmin.instances.return_value.list_next.return_value = None

    return clients


def _make_dns_mock(zones=None, records=None):
    """Create a mock DNS client for per-project creation."""
    dns_client = MagicMock()
    dns_client.list_zones.return_value = zones or []

    if records:
        zone_mock = MagicMock()
        zone_mock.list_resource_record_sets.return_value = records
        dns_client.zone.return_value = zone_mock
    else:
        zone_mock = MagicMock()
        zone_mock.list_resource_record_sets.return_value = []
        dns_client.zone.return_value = zone_mock

    return dns_client


def _create_provider(
    projects=None, shared_clients=None, credentials=None,
    include_projects=None, exclude_projects=None, checkpoint_engine=None,
):
    """Create a GCPDiscoveryProvider with given configuration."""
    if projects is None:
        projects = [_make_project_info()]
    if credentials is None:
        credentials = MagicMock()
    if shared_clients is None:
        shared_clients = _setup_mock_clients()

    return GCPDiscoveryProvider(
        credentials=credentials,
        projects=projects,
        shared_clients=shared_clients,
        include_projects=include_projects,
        exclude_projects=exclude_projects,
        checkpoint_engine=checkpoint_engine,
    )


class TestFullPipeline:
    """Test 1: Full pipeline with representative resources."""

    def test_full_pipeline_discovery_to_tokens(self):
        """Full pipeline: discovery -> counting -> tokenization."""
        vpc = _make_mock_network()
        subnet = _make_mock_subnet()
        vm = _make_mock_vm(private_ip="10.0.0.5", public_ip="34.120.0.2")
        fr = _make_mock_forwarding_rule(ip="34.120.0.1")
        disk = _make_mock_disk()
        gke = _make_mock_gke_cluster()
        sql = _make_mock_cloud_sql(ips=["10.0.1.1", "34.120.0.3"])
        dns_zone = _make_mock_dns_zone()
        dns_a = _make_mock_dns_record_set("www.test.example.com.", "A", ["34.120.0.4"])
        dns_mx = _make_mock_dns_record_set("test.example.com.", "MX", [])

        clients = _setup_mock_clients(
            networks=[vpc],
            subnets=[subnet],
            vms=[vm],
            forwarding_rules=[fr],
            disks=[disk],
            gke_clusters=[gke],
            cloud_sql_instances=[sql],
        )

        dns_client = _make_dns_mock(zones=[dns_zone], records=[dns_a, dns_mx])
        provider = _create_provider(shared_clients=clients)

        with patch.object(provider, "_create_dns_client", return_value=dns_client):
            with patch.dict(sys.modules, {"google.cloud.storage": MagicMock()}):
                _mock_storage.Client.return_value = MagicMock(list_buckets=MagicMock(return_value=[]))
                resources = provider.discover_account(PROJECT_ID)

        assert len(resources) > 0

        # Run counting pipeline
        fold_enis_into_parents(resources)
        exclude_managed_service_resources(resources)
        deduplicate_assets(resources)
        categorize_resources(resources)

        # Verify categorization
        ddi_resources = [r for r in resources if r.counted and r.category == "ddi"]
        asset_resources = [r for r in resources if r.counted and r.category == "asset"]
        excluded_resources = [r for r in resources if not r.counted]

        # DDI: VPC + subnet + DNS zone + 2 DNS records
        assert len(ddi_resources) >= 4, f"Expected >= 4 DDI, got {len(ddi_resources)}: {[r.resource_type for r in ddi_resources]}"

        # Assets: VM (with IPs) + forwarding rule (with IP) + Cloud SQL (with IPs) + DNS A record (with IP)
        assert len(asset_resources) >= 2, f"Expected >= 2 assets, got {len(asset_resources)}"

        # Token-free: disk + GKE should be excluded
        disk_resources = [r for r in resources if r.resource_type == "gcp-disk"]
        gke_resources = [r for r in resources if r.resource_type == "gcp-gke-cluster"]
        for r in disk_resources:
            assert not r.counted
            assert "token-free" in (r.skip_reason or "")
        for r in gke_resources:
            assert not r.counted
            assert "token-free" in (r.skip_reason or "")

        # IP counting
        ip_counts = deduplicate_ips_per_vpc(resources)

        # Token calculation
        per_account_ips = ip_counts.get("per_account", {})
        deduped_ip = per_account_ips.get(PROJECT_ID, 0)
        account_tokens = calculate_account_tokens(
            resources, deduplicated_ip_count=deduped_ip
        )

        assert account_tokens["ddi_count"] > 0
        assert account_tokens["total_tokens"] >= 0
        assert "ddi_tokens" in account_tokens
        assert "ip_tokens" in account_tokens
        assert "asset_tokens" in account_tokens

        # Provider-level aggregation
        provider_totals = calculate_provider_tokens({PROJECT_ID: account_tokens})
        assert provider_totals["account_count"] == 1
        assert provider_totals["total_tokens"] == account_tokens["total_tokens"]


class TestTokenFreeExclusion:
    """Test 2: Token-free resources are correctly excluded."""

    def test_token_free_resources_excluded(self):
        """gcp-disk, gcp-gke-cluster, gcp-instance-group all have counted=False."""
        disk = _make_mock_disk()
        gke = _make_mock_gke_cluster()

        ig = MagicMock()
        ig.name = "ig-1"
        ig.self_link = f"https://compute.googleapis.com/compute/v1/projects/{PROJECT_ID}/zones/us-central1-a/instanceGroups/ig-1"
        ig.size = 3

        clients = _setup_mock_clients(
            disks=[disk],
            gke_clusters=[gke],
            instance_groups=[ig],
        )

        provider = _create_provider(shared_clients=clients)

        with patch.object(provider, "_create_dns_client", return_value=None):
            _mock_storage.Client.return_value = MagicMock(list_buckets=MagicMock(return_value=[]))
            resources = provider.discover_account(PROJECT_ID)

        categorize_resources(resources)

        for r in resources:
            if r.resource_type in ("gcp-disk", "gcp-gke-cluster", "gcp-instance-group"):
                assert r.counted is False, f"{r.resource_type} should not be counted"
                assert "token-free" in (r.skip_reason or ""), f"{r.resource_type} should have token-free skip reason"


class TestDDICounting:
    """Test 3: DDI counting for GCP types."""

    def test_gcp_ddi_resources_counted(self):
        """gcp-vpc, gcp-subnet, gcp-dns-zone, gcp-dns-record all counted as DDI."""
        vpc = _make_mock_network()
        subnet = _make_mock_subnet()
        dns_zone = _make_mock_dns_zone()
        dns_record = _make_mock_dns_record_set("www.test.example.com.", "CNAME", [])

        clients = _setup_mock_clients(networks=[vpc], subnets=[subnet])
        dns_client = _make_dns_mock(zones=[dns_zone], records=[dns_record])

        provider = _create_provider(shared_clients=clients)

        with patch.object(provider, "_create_dns_client", return_value=dns_client):
            _mock_storage.Client.return_value = MagicMock(list_buckets=MagicMock(return_value=[]))
            resources = provider.discover_account(PROJECT_ID)

        categorize_resources(resources)

        ddi_types = {r.resource_type for r in resources if r.counted and r.category == "ddi"}
        assert "gcp-vpc" in ddi_types
        assert "gcp-subnet" in ddi_types
        assert "gcp-dns-zone" in ddi_types
        assert "gcp-dns-record" in ddi_types


class TestIPDeduplication:
    """Test 4: IP deduplication across resources."""

    def test_overlapping_ips_deduplicated(self):
        """Resources with overlapping IPs get deduplicated."""
        # Two VMs with overlapping IPs
        vm1 = _make_mock_vm(name="vm-1", private_ip="10.0.0.5")
        vm2 = _make_mock_vm(name="vm-2", private_ip="10.0.0.5")  # Same IP

        clients = _setup_mock_clients(vms=[vm1, vm2])
        provider = _create_provider(shared_clients=clients)

        with patch.object(provider, "_create_dns_client", return_value=None):
            _mock_storage.Client.return_value = MagicMock(list_buckets=MagicMock(return_value=[]))
            resources = provider.discover_account(PROJECT_ID)

        categorize_resources(resources)
        ip_counts = deduplicate_ips_per_vpc(resources)

        # Both VMs should be discovered
        vm_resources = [r for r in resources if r.resource_type == "gcp-vm"]
        assert len(vm_resources) == 2

        # But deduplicated IPs should count 10.0.0.5 only once per account
        per_account = ip_counts.get("per_account", {})
        deduped = per_account.get(PROJECT_ID, 0)
        assert deduped == 1, f"Expected 1 deduped IP, got {deduped}"


class TestMultiProject:
    """Test 5: Multi-project discovery."""

    def test_three_projects_different_resources(self):
        """Three projects with different resource mixes produce correct per-project totals."""
        # Project 1: VPC + VM
        projects = [
            _make_project_info(PROJECT_ID),
            _make_project_info(PROJECT_ID_2),
            _make_project_info(PROJECT_ID_3),
        ]

        # We'll create one provider and call discover_account for each project
        # Each call returns different resources based on the mock setup
        all_resources: list[CloudResource] = []

        for pid in [PROJECT_ID, PROJECT_ID_2, PROJECT_ID_3]:
            vpc = _make_mock_network(name=f"vpc-{pid}", project_id=pid)
            vm = _make_mock_vm(name=f"vm-{pid}", private_ip=f"10.{hash(pid) % 256}.0.1", project_id=pid)

            clients = _setup_mock_clients(networks=[vpc], vms=[vm])
            provider = _create_provider(
                projects=projects,
                shared_clients=clients,
            )

            with patch.object(provider, "_create_dns_client", return_value=None):
                _mock_storage.Client.return_value = MagicMock(list_buckets=MagicMock(return_value=[]))
                resources = provider.discover_account(pid)
                all_resources.extend(resources)

        categorize_resources(all_resources)
        ip_counts = deduplicate_ips_per_vpc(all_resources)

        # Each project should have resources
        projects_found = {r.account_id for r in all_resources}
        assert PROJECT_ID in projects_found
        assert PROJECT_ID_2 in projects_found
        assert PROJECT_ID_3 in projects_found

        # Per-project token calculation
        from collections import defaultdict
        resources_by_account = defaultdict(list)
        for r in all_resources:
            resources_by_account[r.account_id].append(r)

        account_summaries = {}
        per_account_ips = ip_counts.get("per_account", {})
        for acct_id, acct_resources in resources_by_account.items():
            deduped = per_account_ips.get(acct_id, 0)
            account_summaries[acct_id] = calculate_account_tokens(
                acct_resources, deduplicated_ip_count=deduped
            )

        provider_totals = calculate_provider_tokens(account_summaries)
        assert provider_totals["account_count"] == 3


class TestPartialFailure:
    """Test 6: Partial failure with _safe_collect."""

    def test_one_collector_fails_others_succeed(self):
        """One collector raises exception, others still return resources."""
        vpc = _make_mock_network()
        clients = _setup_mock_clients(networks=[vpc])

        # Make VMs collector raise
        clients.instances.aggregated_list.side_effect = Exception("Simulated compute API error")

        provider = _create_provider(shared_clients=clients)

        with patch.object(provider, "_create_dns_client", return_value=None):
            _mock_storage.Client.return_value = MagicMock(list_buckets=MagicMock(return_value=[]))
            resources = provider.discover_account(PROJECT_ID)

        # VPCs should be present, VMs should NOT
        resource_types = {r.resource_type for r in resources}
        assert "gcp-vpc" in resource_types
        assert "gcp-vm" not in resource_types


class TestAPIDisabledSkip:
    """Test 7: API disabled skip test."""

    def test_compute_disabled_skips_compute_collectors(self):
        """compute_enabled=False skips VMs, disks, subnets but DNS still runs."""
        vpc = _make_mock_network()
        vm = _make_mock_vm()
        dns_zone = _make_mock_dns_zone()

        clients = _setup_mock_clients(networks=[vpc], vms=[vm])
        dns_client = _make_dns_mock(zones=[dns_zone])

        project_info = _make_project_info(compute_enabled=False, dns_enabled=True)
        provider = _create_provider(
            projects=[project_info],
            shared_clients=clients,
        )

        with patch.object(provider, "_create_dns_client", return_value=dns_client):
            _mock_storage.Client.return_value = MagicMock(list_buckets=MagicMock(return_value=[]))
            resources = provider.discover_account(PROJECT_ID)

        resource_types = {r.resource_type for r in resources}

        # Compute-dependent should be absent
        assert "gcp-vpc" not in resource_types
        assert "gcp-subnet" not in resource_types
        assert "gcp-vm" not in resource_types
        assert "gcp-disk" not in resource_types

        # DNS should be present
        assert "gcp-dns-zone" in resource_types


class TestOutputGeneration:
    """Test 8: Output file generation."""

    def test_gcp_xlsx_output_generated(self, tmp_path):
        """Full pipeline produces xlsx with detail and summary sheets."""
        vpc = _make_mock_network()
        vm = _make_mock_vm(private_ip="10.0.0.5")
        disk = _make_mock_disk()

        clients = _setup_mock_clients(networks=[vpc], vms=[vm], disks=[disk])
        provider = _create_provider(shared_clients=clients)

        with patch.object(provider, "_create_dns_client", return_value=None):
            _mock_storage.Client.return_value = MagicMock(list_buckets=MagicMock(return_value=[]))
            resources = provider.discover_account(PROJECT_ID)

        # Run pipeline
        fold_enis_into_parents(resources)
        exclude_managed_service_resources(resources)
        deduplicate_assets(resources)
        categorize_resources(resources)
        ip_counts = deduplicate_ips_per_vpc(resources)

        per_account_ips = ip_counts.get("per_account", {})
        deduped_ip = per_account_ips.get(PROJECT_ID, 0)
        account_tokens = calculate_account_tokens(
            resources, deduplicated_ip_count=deduped_ip
        )
        account_summaries = {PROJECT_ID: account_tokens}

        # Write XLS report
        xlsx_path = str(tmp_path / "gcp_discovery_test.xlsx")
        write_xlsx_report(xlsx_path, resources, account_summaries, [], "gcp")

        assert os.path.exists(xlsx_path)

        # Verify workbook structure
        import openpyxl
        wb = openpyxl.load_workbook(xlsx_path)
        sheet_names = wb.sheetnames
        assert "Detail" in sheet_names
        assert "Summary" in sheet_names
        wb.close()


class TestCheckpointResume:
    """Test 9: Checkpoint resume skips completed projects."""

    def test_completed_project_skipped(self):
        """Project already in checkpoint is skipped (returns [])."""
        checkpoint_engine = MagicMock()
        existing_checkpoint = MagicMock()
        gcp_progress = MagicMock()
        gcp_progress.completed_accounts = {PROJECT_ID}
        existing_checkpoint.providers = {"gcp": gcp_progress}
        checkpoint_engine.load.return_value = existing_checkpoint

        clients = _setup_mock_clients(networks=[_make_mock_network()])
        provider = _create_provider(
            shared_clients=clients,
            checkpoint_engine=checkpoint_engine,
        )

        resources = provider.discover_account(PROJECT_ID)
        assert resources == []

        # Verify collectors were NOT called (checkpoint short-circuited)
        clients.networks.list.assert_not_called()


class TestEmptyProject:
    """Test 10: Empty project with no resources."""

    def test_empty_project_returns_empty(self):
        """Project with no resources returns empty list, no errors."""
        clients = _setup_mock_clients()

        provider = _create_provider(shared_clients=clients)

        with patch.object(provider, "_create_dns_client", return_value=None):
            with patch(
                "cloud_usage.providers.gcp.provider.collect_gcp_storage_buckets",
                return_value=[],
            ):
                resources = provider.discover_account(PROJECT_ID)

        assert resources == []


class TestContainerDisabledSkip:
    """Test: container_enabled=False skips GKE but not compute."""

    def test_container_disabled_skips_gke(self):
        """container_enabled=False skips GKE clusters but VMs still run."""
        vm = _make_mock_vm()
        gke = _make_mock_gke_cluster()

        clients = _setup_mock_clients(vms=[vm], gke_clusters=[gke])
        project_info = _make_project_info(container_enabled=False)
        provider = _create_provider(
            projects=[project_info],
            shared_clients=clients,
        )

        with patch.object(provider, "_create_dns_client", return_value=None):
            _mock_storage.Client.return_value = MagicMock(list_buckets=MagicMock(return_value=[]))
            resources = provider.discover_account(PROJECT_ID)

        resource_types = {r.resource_type for r in resources}
        assert "gcp-vm" in resource_types
        assert "gcp-gke-cluster" not in resource_types


class TestSqlAdminDisabledSkip:
    """Test: sqladmin_enabled=False skips Cloud SQL."""

    def test_sqladmin_disabled_skips_cloud_sql(self):
        """sqladmin_enabled=False skips Cloud SQL but compute still runs."""
        vm = _make_mock_vm()
        sql = _make_mock_cloud_sql(ips=["10.0.1.1"])

        clients = _setup_mock_clients(vms=[vm], cloud_sql_instances=[sql])
        project_info = _make_project_info(sqladmin_enabled=False)
        provider = _create_provider(
            projects=[project_info],
            shared_clients=clients,
        )

        with patch.object(provider, "_create_dns_client", return_value=None):
            _mock_storage.Client.return_value = MagicMock(list_buckets=MagicMock(return_value=[]))
            resources = provider.discover_account(PROJECT_ID)

        resource_types = {r.resource_type for r in resources}
        assert "gcp-vm" in resource_types
        assert "gcp-cloud-sql" not in resource_types
