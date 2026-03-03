"""Tests for GCP compute resource collectors (VMs and forwarding rules).

Uses unittest.mock to simulate GCP SDK responses. Tests cover IP extraction
from network_i_p/nat_i_p (Pitfall 6), aggregatedList iteration, zone-to-region
mapping, and empty scoped list handling.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# --- Module-level mocking of GCP SDK ---

_mock_compute_v1 = MagicMock()

# Mock the request classes as callables that return their kwargs
_mock_compute_v1.AggregatedListInstancesRequest = lambda **kw: kw
_mock_compute_v1.AggregatedListForwardingRulesRequest = lambda **kw: kw

_gcp_modules = {
    "google": MagicMock(),
    "google.cloud": MagicMock(),
    "google.cloud.compute_v1": _mock_compute_v1,
}


# --- Helper factories ---


def _make_access_config(nat_ip: str | None = None) -> MagicMock:
    ac = MagicMock()
    ac.nat_i_p = nat_ip
    return ac


def _make_network_interface(
    private_ip: str | None = None,
    access_configs: list | None = None,
) -> MagicMock:
    iface = MagicMock()
    iface.network_i_p = private_ip
    iface.access_configs = access_configs
    return iface


def _make_instance(
    name: str = "test-vm",
    self_link: str | None = None,
    network_interfaces: list | None = None,
    labels: dict | None = None,
    machine_type: str = "zones/us-central1-a/machineTypes/n1-standard-1",
    status: str = "RUNNING",
) -> MagicMock:
    inst = MagicMock()
    inst.name = name
    inst.self_link = self_link
    inst.network_interfaces = network_interfaces
    inst.labels = labels
    inst.machine_type = machine_type
    inst.status = status
    return inst


def _make_scoped_list(instances: list | None = None) -> MagicMock:
    sl = MagicMock()
    sl.instances = instances if instances else None
    return sl


def _make_forwarding_rule(
    name: str = "test-rule",
    self_link: str | None = None,
    ip_address: str | None = None,
    load_balancing_scheme: str = "EXTERNAL",
    target: str = "projects/test/targetPools/pool-1",
    ip_protocol: str = "TCP",
    labels: dict | None = None,
) -> MagicMock:
    rule = MagicMock(spec=[
        "name", "self_link", "I_p_address", "i_p_address", "ip_address",
        "load_balancing_scheme", "target", "ip_protocol", "labels",
    ])
    rule.name = name
    rule.self_link = self_link
    rule.I_p_address = ip_address
    rule.i_p_address = ip_address
    rule.ip_address = ip_address
    rule.load_balancing_scheme = load_balancing_scheme
    rule.target = target
    rule.ip_protocol = ip_protocol
    rule.labels = labels
    return rule


def _make_forwarding_scoped_list(rules: list | None = None) -> MagicMock:
    sl = MagicMock()
    sl.forwarding_rules = rules if rules else None
    return sl


# --- VM Tests ---


class TestCollectGcpVms:
    """Tests for collect_gcp_vms."""

    @pytest.fixture(autouse=True)
    def _patch_modules(self):
        with patch.dict(sys.modules, _gcp_modules):
            yield

    def test_basic_vm_discovery(self):
        """Test basic VM discovered with correct resource type."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        inst = _make_instance(name="vm-1", self_link="https://compute.googleapis.com/projects/proj/zones/us-central1-a/instances/vm-1")
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-central1-a", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert len(result) == 1
        assert result[0].resource_type == "gcp-vm"
        assert result[0].provider == "gcp"
        assert result[0].account_id == "proj"
        assert result[0].name == "vm-1"

    def test_private_ip_extraction_network_i_p(self):
        """Test private IP extracted from network_i_p field (Pitfall 6)."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        iface = _make_network_interface(private_ip="10.0.0.5")
        inst = _make_instance(name="vm-1", network_interfaces=[iface])
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-east1-b", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert "10.0.0.5" in result[0].ip_addresses

    def test_public_ip_extraction_nat_i_p(self):
        """Test public IP extracted from access_configs nat_i_p (Pitfall 6)."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        ac = _make_access_config(nat_ip="35.200.1.1")
        iface = _make_network_interface(private_ip="10.0.0.5", access_configs=[ac])
        inst = _make_instance(name="vm-1", network_interfaces=[iface])
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-central1-a", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert "10.0.0.5" in result[0].ip_addresses
        assert "35.200.1.1" in result[0].ip_addresses

    def test_multiple_network_interfaces(self):
        """Test VM with multiple network interfaces collects all IPs."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        iface1 = _make_network_interface(private_ip="10.0.0.1")
        iface2 = _make_network_interface(
            private_ip="10.1.0.1",
            access_configs=[_make_access_config(nat_ip="35.0.0.1")],
        )
        inst = _make_instance(name="vm-multi", network_interfaces=[iface1, iface2])
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-central1-a", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert len(result[0].ip_addresses) == 3
        assert "10.0.0.1" in result[0].ip_addresses
        assert "10.1.0.1" in result[0].ip_addresses
        assert "35.0.0.1" in result[0].ip_addresses

    def test_vm_no_network_interfaces(self):
        """Test VM with no network interfaces has empty ip_addresses."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        inst = _make_instance(name="vm-no-net", network_interfaces=None)
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-central1-a", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert result[0].ip_addresses == []

    def test_multiple_zones(self):
        """Test VMs discovered across multiple zones."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        inst1 = _make_instance(name="vm-1")
        inst2 = _make_instance(name="vm-2")
        scoped1 = _make_scoped_list(instances=[inst1])
        scoped2 = _make_scoped_list(instances=[inst2])
        client.aggregated_list.return_value = iter([
            ("zones/us-central1-a", scoped1),
            ("zones/europe-west1-b", scoped2),
        ])

        result = collect_gcp_vms(client, "proj")

        assert len(result) == 2
        names = {r.name for r in result}
        assert names == {"vm-1", "vm-2"}

    def test_empty_scoped_lists_skipped(self):
        """Test scoped lists with no instances are skipped."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        empty_scoped = _make_scoped_list(instances=None)
        inst = _make_instance(name="vm-1")
        real_scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([
            ("zones/us-central1-a", empty_scoped),
            ("zones/us-central1-b", empty_scoped),
            ("zones/us-east1-a", real_scoped),
        ])

        result = collect_gcp_vms(client, "proj")

        assert len(result) == 1
        assert result[0].name == "vm-1"

    def test_region_extraction_from_zone(self):
        """Test zone-to-region mapping: us-central1-a -> us-central1."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        inst = _make_instance(name="vm-1")
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-central1-a", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert result[0].region == "us-central1"
        assert result[0].details["zone"] == "us-central1-a"

    def test_region_extraction_europe(self):
        """Test zone-to-region mapping for europe-west1-b."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        inst = _make_instance(name="vm-eu")
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/europe-west1-b", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert result[0].region == "europe-west1"

    def test_vm_labels_as_tags(self):
        """Test instance labels become CloudResource tags."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        inst = _make_instance(name="vm-tagged", labels={"env": "prod", "team": "infra"})
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-central1-a", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert result[0].tags == {"env": "prod", "team": "infra"}

    def test_vm_no_labels(self):
        """Test VM with no labels has empty tags dict."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        inst = _make_instance(name="vm-no-tags", labels=None)
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-central1-a", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert result[0].tags == {}

    def test_machine_type_extraction(self):
        """Test machine type extracted from full path."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        inst = _make_instance(
            name="vm-1",
            machine_type="zones/us-central1-a/machineTypes/n1-standard-4",
        )
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-central1-a", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert result[0].details["machine_type"] == "n1-standard-4"

    def test_fallback_resource_id(self):
        """Test resource_id fallback when self_link is not set."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        inst = _make_instance(name="vm-no-link", self_link=None)
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-central1-a", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert result[0].resource_id == "projects/proj/zones/us-central1-a/instances/vm-no-link"

    def test_empty_project_no_vms(self):
        """Test empty project returns no resources."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        client.aggregated_list.return_value = iter([])

        result = collect_gcp_vms(client, "proj")

        assert result == []

    def test_access_config_no_nat_ip(self):
        """Test access config without nat_i_p does not add empty IP."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        ac = _make_access_config(nat_ip=None)
        iface = _make_network_interface(private_ip="10.0.0.1", access_configs=[ac])
        inst = _make_instance(name="vm-1", network_interfaces=[iface])
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-central1-a", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert result[0].ip_addresses == ["10.0.0.1"]


# --- GCP VM Network Interface Count Tests ---


class TestGCPVMCollectorNetworkInterfaceCount:
    """Tests that GCP VM collector sets details['network_interface_count'].

    Tests are RED until plan 25-03 implements network_interface_count in the collector.
    Existing ip_addresses extraction tests remain GREEN (collector still populates ip_addresses for audit).
    """

    @pytest.fixture(autouse=True)
    def _patch_modules(self):
        with patch.dict(sys.modules, _gcp_modules):
            yield

    def test_gcp_vm_three_interfaces_network_interface_count_is_3(self):
        """GCP VM with 3 network_interfaces -> details['network_interface_count'] == 3."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        iface1 = _make_network_interface(private_ip="10.0.0.1")
        iface2 = _make_network_interface(private_ip="10.1.0.1")
        iface3 = _make_network_interface(private_ip="10.2.0.1")
        inst = _make_instance(
            name="vm-3-ifaces",
            network_interfaces=[iface1, iface2, iface3],
        )
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-central1-a", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert len(result) == 1
        assert result[0].details["network_interface_count"] == 3

    def test_gcp_vm_one_interface_network_interface_count_is_1(self):
        """GCP VM with 1 network_interface -> details['network_interface_count'] == 1."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        iface = _make_network_interface(private_ip="10.0.0.5")
        inst = _make_instance(
            name="vm-1-iface",
            network_interfaces=[iface],
        )
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-central1-a", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert len(result) == 1
        assert result[0].details["network_interface_count"] == 1

    def test_gcp_vm_no_interfaces_network_interface_count_is_0(self):
        """GCP VM with empty network_interfaces -> details['network_interface_count'] == 0."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        inst = _make_instance(name="vm-no-ifaces", network_interfaces=None)
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-central1-a", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert len(result) == 1
        assert result[0].details["network_interface_count"] == 0

    def test_gcp_vm_ip_addresses_still_populated_alongside_count(self):
        """ip_addresses is still populated for audit (existing behavior preserved)."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_vms

        client = MagicMock()
        iface = _make_network_interface(
            private_ip="10.0.0.1",
            access_configs=[_make_access_config(nat_ip="35.200.1.1")],
        )
        inst = _make_instance(name="vm-with-ips", network_interfaces=[iface])
        scoped = _make_scoped_list(instances=[inst])
        client.aggregated_list.return_value = iter([("zones/us-central1-a", scoped)])

        result = collect_gcp_vms(client, "proj")

        assert len(result) == 1
        # network_interface_count is set
        assert result[0].details["network_interface_count"] == 1
        # ip_addresses still populated for audit
        assert "10.0.0.1" in result[0].ip_addresses
        assert "35.200.1.1" in result[0].ip_addresses


# --- Forwarding Rule Tests ---


class TestCollectGcpForwardingRules:
    """Tests for collect_gcp_forwarding_rules."""

    @pytest.fixture(autouse=True)
    def _patch_modules(self):
        with patch.dict(sys.modules, _gcp_modules):
            yield

    def test_basic_forwarding_rule(self):
        """Test basic forwarding rule discovered with correct type."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_forwarding_rules

        client = MagicMock()
        rule = _make_forwarding_rule(
            name="rule-1",
            self_link="https://compute.googleapis.com/projects/proj/regions/us-central1/forwardingRules/rule-1",
            ip_address="35.200.0.1",
        )
        scoped = _make_forwarding_scoped_list(rules=[rule])
        client.aggregated_list.return_value = iter([("regions/us-central1", scoped)])

        result = collect_gcp_forwarding_rules(client, "proj")

        assert len(result) == 1
        assert result[0].resource_type == "gcp-forwarding-rule"
        assert result[0].provider == "gcp"
        assert result[0].name == "rule-1"

    def test_forwarding_rule_ip_extraction(self):
        """Test IP extracted from forwarding rule I_p_address field."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_forwarding_rules

        client = MagicMock()
        rule = _make_forwarding_rule(name="rule-1", ip_address="10.128.0.1")
        scoped = _make_forwarding_scoped_list(rules=[rule])
        client.aggregated_list.return_value = iter([("regions/us-central1", scoped)])

        result = collect_gcp_forwarding_rules(client, "proj")

        assert result[0].ip_addresses == ["10.128.0.1"]

    def test_forwarding_rule_no_ip(self):
        """Test forwarding rule with no IP has empty ip_addresses."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_forwarding_rules

        client = MagicMock()
        rule = _make_forwarding_rule(name="rule-1", ip_address=None)
        scoped = _make_forwarding_scoped_list(rules=[rule])
        client.aggregated_list.return_value = iter([("regions/us-central1", scoped)])

        result = collect_gcp_forwarding_rules(client, "proj")

        assert result[0].ip_addresses == []

    def test_forwarding_rules_multiple_regions(self):
        """Test forwarding rules discovered across multiple regions."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_forwarding_rules

        client = MagicMock()
        rule1 = _make_forwarding_rule(name="rule-us", ip_address="10.0.0.1")
        rule2 = _make_forwarding_rule(name="rule-eu", ip_address="10.1.0.1")
        scoped1 = _make_forwarding_scoped_list(rules=[rule1])
        scoped2 = _make_forwarding_scoped_list(rules=[rule2])
        client.aggregated_list.return_value = iter([
            ("regions/us-central1", scoped1),
            ("regions/europe-west1", scoped2),
        ])

        result = collect_gcp_forwarding_rules(client, "proj")

        assert len(result) == 2
        regions = {r.region for r in result}
        assert regions == {"us-central1", "europe-west1"}

    def test_forwarding_rule_global_region(self):
        """Test global forwarding rule has region='global'."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_forwarding_rules

        client = MagicMock()
        rule = _make_forwarding_rule(name="global-rule", ip_address="35.0.0.1")
        scoped = _make_forwarding_scoped_list(rules=[rule])
        client.aggregated_list.return_value = iter([("global", scoped)])

        result = collect_gcp_forwarding_rules(client, "proj")

        assert result[0].region == "global"

    def test_empty_scoped_lists_skipped_forwarding(self):
        """Test empty forwarding rule scoped lists are skipped."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_forwarding_rules

        client = MagicMock()
        empty = _make_forwarding_scoped_list(rules=None)
        rule = _make_forwarding_rule(name="rule-1", ip_address="10.0.0.1")
        real = _make_forwarding_scoped_list(rules=[rule])
        client.aggregated_list.return_value = iter([
            ("regions/us-central1", empty),
            ("regions/us-east1", real),
        ])

        result = collect_gcp_forwarding_rules(client, "proj")

        assert len(result) == 1

    def test_forwarding_rule_details(self):
        """Test forwarding rule details contain scheme, target, protocol."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_forwarding_rules

        client = MagicMock()
        rule = _make_forwarding_rule(
            name="rule-1",
            ip_address="10.0.0.1",
            load_balancing_scheme="INTERNAL",
            target="projects/proj/targetPools/my-pool",
            ip_protocol="UDP",
        )
        scoped = _make_forwarding_scoped_list(rules=[rule])
        client.aggregated_list.return_value = iter([("regions/us-central1", scoped)])

        result = collect_gcp_forwarding_rules(client, "proj")

        assert result[0].details["load_balancing_scheme"] == "INTERNAL"
        assert result[0].details["target"] == "my-pool"
        assert result[0].details["ip_protocol"] == "UDP"

    def test_forwarding_rule_fallback_resource_id(self):
        """Test forwarding rule resource_id fallback when no self_link."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_forwarding_rules

        client = MagicMock()
        rule = _make_forwarding_rule(name="rule-1", self_link=None, ip_address="10.0.0.1")
        scoped = _make_forwarding_scoped_list(rules=[rule])
        client.aggregated_list.return_value = iter([("regions/us-central1", scoped)])

        result = collect_gcp_forwarding_rules(client, "proj")

        assert result[0].resource_id == "projects/proj/regions/us-central1/forwardingRules/rule-1"

    def test_empty_project_no_forwarding_rules(self):
        """Test empty project returns no forwarding rules."""
        from cloud_usage.providers.gcp.collectors.compute import collect_gcp_forwarding_rules

        client = MagicMock()
        client.aggregated_list.return_value = iter([])

        result = collect_gcp_forwarding_rules(client, "proj")

        assert result == []
