"""Unit tests for GCP networking resource collectors.

Tests VPC networks (global list), subnets (aggregatedList), and reserved
IPs (regional aggregatedList + global list) collectors using unittest.mock.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Module-level mock setup: mock GCP SDK modules so imports succeed
# without the actual google-cloud-compute SDK installed.
# ---------------------------------------------------------------------------

_mock_compute_v1 = MagicMock()
_mock_google = ModuleType("google")
_mock_google_cloud = ModuleType("google.cloud")
_mock_google.__path__ = []
_mock_google_cloud.__path__ = []

_patches = {
    "google": _mock_google,
    "google.cloud": _mock_google_cloud,
    "google.cloud.compute_v1": _mock_compute_v1,
}


@pytest.fixture(autouse=True)
def _mock_gcp_sdk():
    """Mock GCP SDK modules for every test."""
    with patch.dict(sys.modules, _patches):
        yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_network(
    name: str = "my-vpc",
    self_link: str | None = None,
    auto_create: bool = True,
    labels=None,
):
    """Create a mock VPC network object."""
    net = MagicMock()
    net.name = name
    net.self_link = self_link or f"https://compute.googleapis.com/compute/v1/projects/proj/global/networks/{name}"
    net.auto_create_subnetworks = auto_create
    net.labels = labels
    return net


def _make_subnetwork(
    name: str = "sub-1",
    self_link: str | None = None,
    ip_cidr_range: str = "10.0.0.0/24",
    network: str = "projects/proj/global/networks/my-vpc",
    labels=None,
):
    """Create a mock subnetwork object."""
    sub = MagicMock()
    sub.name = name
    sub.self_link = self_link or f"https://compute.googleapis.com/compute/v1/projects/proj/regions/us-central1/subnetworks/{name}"
    sub.ip_cidr_range = ip_cidr_range
    sub.network = network
    sub.labels = labels
    return sub


def _make_address(
    name: str = "addr-1",
    self_link: str | None = None,
    address: str = "10.128.0.1",
    address_type: str = "INTERNAL",
    status: str = "RESERVED",
    purpose: str = "",
    labels=None,
):
    """Create a mock address object."""
    addr = MagicMock()
    addr.name = name
    addr.self_link = self_link or f"https://compute.googleapis.com/compute/v1/projects/proj/regions/us-central1/addresses/{name}"
    addr.address = address
    addr.address_type = address_type
    addr.status = status
    addr.purpose = purpose
    addr.labels = labels
    return addr


def _make_scoped_list(items, attr_name):
    """Create a mock scoped list with the given attribute populated."""
    scoped = MagicMock()
    setattr(scoped, attr_name, items)
    return scoped


def _make_empty_scoped_list(attr_name):
    """Create a mock scoped list with an empty/falsy attribute."""
    scoped = MagicMock()
    setattr(scoped, attr_name, [])
    return scoped


# ===========================================================================
# collect_gcp_vpcs tests
# ===========================================================================


class TestCollectGcpVpcs:
    """Tests for collect_gcp_vpcs."""

    def test_returns_vpc_resources(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_vpcs

        net1 = _make_network("vpc-1")
        net2 = _make_network("vpc-2")
        client = MagicMock()
        client.list.return_value = [net1, net2]

        result = collect_gcp_vpcs(client, "my-project")

        assert len(result) == 2
        assert result[0].resource_type == "gcp-vpc"
        assert result[1].resource_type == "gcp-vpc"

    def test_vpc_fields(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_vpcs

        net = _make_network("prod-vpc", auto_create=False)
        client = MagicMock()
        client.list.return_value = [net]

        result = collect_gcp_vpcs(client, "proj-123")

        r = result[0]
        assert r.provider == "gcp"
        assert r.account_id == "proj-123"
        assert r.region == "global"
        assert r.name == "prod-vpc"
        assert r.ip_addresses == []
        assert r.details["auto_create_subnetworks"] is False

    def test_vpc_uses_self_link_as_resource_id(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_vpcs

        link = "https://compute.googleapis.com/compute/v1/projects/proj/global/networks/my-vpc"
        net = _make_network("my-vpc", self_link=link)
        client = MagicMock()
        client.list.return_value = [net]

        result = collect_gcp_vpcs(client, "proj")

        assert result[0].resource_id == link

    def test_vpc_fallback_resource_id_when_no_self_link(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_vpcs

        net = _make_network("my-vpc")
        net.self_link = None
        client = MagicMock()
        client.list.return_value = [net]

        result = collect_gcp_vpcs(client, "proj")

        assert result[0].resource_id == "projects/proj/global/networks/my-vpc"

    def test_vpc_empty_project(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_vpcs

        client = MagicMock()
        client.list.return_value = []

        result = collect_gcp_vpcs(client, "empty-proj")

        assert result == []

    def test_vpc_labels_extracted(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_vpcs

        net = _make_network("labeled-vpc", labels={"env": "prod", "team": "infra"})
        client = MagicMock()
        client.list.return_value = [net]

        result = collect_gcp_vpcs(client, "proj")

        assert result[0].tags == {"env": "prod", "team": "infra"}

    def test_vpc_no_labels(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_vpcs

        net = _make_network("no-label-vpc", labels=None)
        client = MagicMock()
        client.list.return_value = [net]

        result = collect_gcp_vpcs(client, "proj")

        assert result[0].tags == {}


# ===========================================================================
# collect_gcp_subnets tests
# ===========================================================================


class TestCollectGcpSubnets:
    """Tests for collect_gcp_subnets."""

    def test_returns_subnet_resources_across_regions(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_subnets

        sub1 = _make_subnetwork("sub-1", ip_cidr_range="10.0.0.0/24")
        sub2 = _make_subnetwork("sub-2", ip_cidr_range="10.1.0.0/24")

        scoped_us = _make_scoped_list([sub1], "subnetworks")
        scoped_eu = _make_scoped_list([sub2], "subnetworks")

        client = MagicMock()
        client.aggregated_list.return_value = [
            ("regions/us-central1", scoped_us),
            ("regions/europe-west1", scoped_eu),
        ]

        result = collect_gcp_subnets(client, "proj")

        assert len(result) == 2
        assert result[0].resource_type == "gcp-subnet"
        assert result[0].region == "us-central1"
        assert result[1].region == "europe-west1"

    def test_subnet_fields(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_subnets

        sub = _make_subnetwork(
            "prod-sub",
            ip_cidr_range="172.16.0.0/20",
            network="projects/proj/global/networks/prod-vpc",
        )
        scoped = _make_scoped_list([sub], "subnetworks")

        client = MagicMock()
        client.aggregated_list.return_value = [("regions/us-east1", scoped)]

        result = collect_gcp_subnets(client, "proj-x")

        r = result[0]
        assert r.provider == "gcp"
        assert r.account_id == "proj-x"
        assert r.name == "prod-sub"
        assert r.ip_addresses == []
        assert r.details["ip_cidr_range"] == "172.16.0.0/20"
        assert r.details["network"] == "prod-vpc"

    def test_subnet_skips_empty_scoped_lists(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_subnets

        sub = _make_subnetwork("sub-1")
        scoped_with = _make_scoped_list([sub], "subnetworks")
        scoped_empty = _make_empty_scoped_list("subnetworks")

        client = MagicMock()
        client.aggregated_list.return_value = [
            ("regions/us-central1", scoped_with),
            ("regions/asia-east1", scoped_empty),
        ]

        result = collect_gcp_subnets(client, "proj")

        assert len(result) == 1
        assert result[0].name == "sub-1"

    def test_subnet_empty_project(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_subnets

        client = MagicMock()
        client.aggregated_list.return_value = []

        result = collect_gcp_subnets(client, "empty-proj")

        assert result == []

    def test_subnet_extracts_network_name_from_path(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_subnets

        sub = _make_subnetwork("sub-1", network="projects/proj/global/networks/my-vpc")
        scoped = _make_scoped_list([sub], "subnetworks")

        client = MagicMock()
        client.aggregated_list.return_value = [("regions/us-central1", scoped)]

        result = collect_gcp_subnets(client, "proj")

        assert result[0].details["network"] == "my-vpc"

    def test_subnet_handles_empty_network(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_subnets

        sub = _make_subnetwork("sub-orphan", network="")
        scoped = _make_scoped_list([sub], "subnetworks")

        client = MagicMock()
        client.aggregated_list.return_value = [("regions/us-west1", scoped)]

        result = collect_gcp_subnets(client, "proj")

        assert result[0].details["network"] == ""


# ===========================================================================
# collect_gcp_reserved_ips tests
# ===========================================================================


class TestCollectGcpReservedIps:
    """Tests for collect_gcp_reserved_ips."""

    def test_combines_regional_and_global_addresses(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_reserved_ips

        regional_addr = _make_address("regional-1", address="10.128.0.1")
        global_addr = _make_address("global-1", address="34.120.0.1")

        scoped = _make_scoped_list([regional_addr], "addresses")

        addresses_client = MagicMock()
        addresses_client.aggregated_list.return_value = [("regions/us-central1", scoped)]

        global_client = MagicMock()
        global_client.list.return_value = [global_addr]

        result = collect_gcp_reserved_ips(addresses_client, global_client, "proj")

        assert len(result) == 2
        assert all(r.resource_type == "gcp-reserved-ip" for r in result)

    def test_regional_address_fields(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_reserved_ips

        addr = _make_address(
            "internal-1",
            address="10.128.0.5",
            address_type="INTERNAL",
            status="RESERVED",
            purpose="GCE_ENDPOINT",
        )
        scoped = _make_scoped_list([addr], "addresses")

        addresses_client = MagicMock()
        addresses_client.aggregated_list.return_value = [("regions/us-east1", scoped)]

        global_client = MagicMock()
        global_client.list.return_value = []

        result = collect_gcp_reserved_ips(addresses_client, global_client, "proj-a")

        r = result[0]
        assert r.provider == "gcp"
        assert r.account_id == "proj-a"
        assert r.region == "us-east1"
        assert r.name == "internal-1"
        assert r.ip_addresses == ["10.128.0.5"]
        assert r.details["address_type"] == "INTERNAL"
        assert r.details["status"] == "RESERVED"
        assert r.details["purpose"] == "GCE_ENDPOINT"

    def test_global_address_region_is_global(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_reserved_ips

        addr = _make_address("global-lb", address="34.120.0.1")

        addresses_client = MagicMock()
        addresses_client.aggregated_list.return_value = []

        global_client = MagicMock()
        global_client.list.return_value = [addr]

        result = collect_gcp_reserved_ips(addresses_client, global_client, "proj")

        assert result[0].region == "global"

    def test_ip_extraction_populates_ip_addresses(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_reserved_ips

        addr = _make_address("ip-addr", address="192.168.1.10")
        scoped = _make_scoped_list([addr], "addresses")

        addresses_client = MagicMock()
        addresses_client.aggregated_list.return_value = [("regions/us-west1", scoped)]

        global_client = MagicMock()
        global_client.list.return_value = []

        result = collect_gcp_reserved_ips(addresses_client, global_client, "proj")

        assert result[0].ip_addresses == ["192.168.1.10"]

    def test_empty_address_has_no_ips(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_reserved_ips

        addr = _make_address("pending", address="")
        scoped = _make_scoped_list([addr], "addresses")

        addresses_client = MagicMock()
        addresses_client.aggregated_list.return_value = [("regions/us-west1", scoped)]

        global_client = MagicMock()
        global_client.list.return_value = []

        result = collect_gcp_reserved_ips(addresses_client, global_client, "proj")

        assert result[0].ip_addresses == []

    def test_skips_empty_address_scoped_lists(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_reserved_ips

        scoped_empty = _make_empty_scoped_list("addresses")

        addresses_client = MagicMock()
        addresses_client.aggregated_list.return_value = [("regions/us-central1", scoped_empty)]

        global_client = MagicMock()
        global_client.list.return_value = []

        result = collect_gcp_reserved_ips(addresses_client, global_client, "proj")

        assert result == []

    def test_empty_project_no_addresses(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_reserved_ips

        addresses_client = MagicMock()
        addresses_client.aggregated_list.return_value = []

        global_client = MagicMock()
        global_client.list.return_value = []

        result = collect_gcp_reserved_ips(addresses_client, global_client, "proj")

        assert result == []

    def test_multiple_regional_addresses_across_regions(self):
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_reserved_ips

        addr1 = _make_address("addr-1", address="10.0.0.1")
        addr2 = _make_address("addr-2", address="10.0.1.1")
        addr3 = _make_address("addr-3", address="10.1.0.1")

        scoped_us = _make_scoped_list([addr1, addr2], "addresses")
        scoped_eu = _make_scoped_list([addr3], "addresses")

        addresses_client = MagicMock()
        addresses_client.aggregated_list.return_value = [
            ("regions/us-central1", scoped_us),
            ("regions/europe-west1", scoped_eu),
        ]

        global_client = MagicMock()
        global_client.list.return_value = []

        result = collect_gcp_reserved_ips(addresses_client, global_client, "proj")

        assert len(result) == 3
        assert result[0].region == "us-central1"
        assert result[1].region == "us-central1"
        assert result[2].region == "europe-west1"


# ---------------------------------------------------------------------------
# Phase 28 helpers: Router NAT and Target VPN Gateway
# ---------------------------------------------------------------------------


def _make_router(name="router-1", self_link=None, nats=None):
    """Create a mock Cloud Router object."""
    r = MagicMock()
    r.name = name
    r.self_link = self_link or f"https://compute.googleapis.com/compute/v1/projects/proj/regions/us-central1/routers/{name}"
    r.nats = nats if nats is not None else []
    r.labels = None
    return r


def _make_nat(name="nat-1"):
    """Create a mock Cloud Router NAT object."""
    n = MagicMock()
    n.name = name
    return n


def _make_target_vpn_gw(name="vpn-gw-1", self_link=None):
    """Create a mock Target VPN Gateway object."""
    gw = MagicMock()
    gw.name = name
    gw.self_link = self_link or f"https://compute.googleapis.com/compute/v1/projects/proj/regions/us-central1/targetVpnGateways/{name}"
    gw.labels = None
    return gw


# ===========================================================================
# GCPG-01: collect_gcp_reserved_ips DDI-only fix (Phase 28)
# ===========================================================================


class TestCollectGcpReservedIpsDdiOnly:
    """Phase 28 GCPG-01: Reserved IPs must be DDI-only with ip_addresses=[].

    After Plan 28-02 the collector sets ip_addresses=[] (DDI-only mode).
    This test is RED now (current code still populates ip_addresses) and
    becomes GREEN after the Plan 02 fix.
    """

    def test_reserved_ip_has_empty_ip_addresses(self):
        """After GCPG-01 fix: ip_addresses==[] and resource_type=='gcp-reserved-ip'."""
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_reserved_ips

        addr = _make_address("static-1", address="10.128.0.5")
        scoped = _make_scoped_list([addr], "addresses")

        addresses_client = MagicMock()
        addresses_client.aggregated_list.return_value = [("regions/us-central1", scoped)]

        global_client = MagicMock()
        global_client.list.return_value = []

        result = collect_gcp_reserved_ips(addresses_client, global_client, "proj")

        assert len(result) == 1
        assert result[0].resource_type == "gcp-reserved-ip"
        assert result[0].ip_addresses == []


# ===========================================================================
# GCPG-03: collect_gcp_router_nats (Phase 28)
# ===========================================================================


class TestCollectGcpRouterNats:
    """Phase 28 GCPG-03: Cloud Router NAT configurations.

    Tests are RED until collect_gcp_router_nats is implemented in Plan 02.
    """

    def test_router_with_nats_emits_one_per_nat(self):
        """Router with one NAT emits exactly one gcp-router-nat resource."""
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_router_nats

        router = _make_router(name="router-1", nats=[_make_nat("nat-1")])
        scoped = _make_scoped_list([router], "routers")

        routers_client = MagicMock()
        routers_client.aggregated_list.return_value = [("regions/us-central1", scoped)]

        result = collect_gcp_router_nats(routers_client, "proj")

        assert len(result) == 1
        assert result[0].resource_type == "gcp-router-nat"
        assert result[0].ip_addresses == []

    def test_router_with_two_nats_emits_two(self):
        """Router with two NATs emits two gcp-router-nat resources."""
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_router_nats

        router = _make_router(name="router-1", nats=[_make_nat("nat-1"), _make_nat("nat-2")])
        scoped = _make_scoped_list([router], "routers")

        routers_client = MagicMock()
        routers_client.aggregated_list.return_value = [("regions/us-central1", scoped)]

        result = collect_gcp_router_nats(routers_client, "proj")

        assert len(result) == 2

    def test_router_with_no_nats_emits_nothing(self):
        """Router with empty nats list emits no resources."""
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_router_nats

        router = _make_router(name="router-empty", nats=[])
        scoped = _make_scoped_list([router], "routers")

        routers_client = MagicMock()
        routers_client.aggregated_list.return_value = [("regions/us-central1", scoped)]

        result = collect_gcp_router_nats(routers_client, "proj")

        assert result == []

    def test_router_nat_resource_id_constructed(self):
        """resource_id contains project_id, region, router name, and nat name."""
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_router_nats

        router = _make_router(name="router-1", nats=[_make_nat("nat-1")])
        scoped = _make_scoped_list([router], "routers")

        routers_client = MagicMock()
        routers_client.aggregated_list.return_value = [("regions/us-central1", scoped)]

        result = collect_gcp_router_nats(routers_client, "my-proj")

        resource_id = result[0].resource_id
        assert "my-proj" in resource_id
        assert "us-central1" in resource_id
        assert "router-1" in resource_id
        assert "nat-1" in resource_id


# ===========================================================================
# GCPG-04: collect_gcp_target_vpn_gateways (Phase 28)
# ===========================================================================


class TestCollectGcpTargetVpnGateways:
    """Phase 28 GCPG-04: Legacy Target VPN Gateways.

    Tests are RED until collect_gcp_target_vpn_gateways is implemented in Plan 02.
    """

    def test_target_vpn_gateway_collection(self):
        """Target VPN gateway is collected as gcp-target-vpn-gateway with ip_addresses==[]."""
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_target_vpn_gateways

        gw = _make_target_vpn_gw("vpn-gw-1")
        scoped = _make_scoped_list([gw], "target_vpn_gateways")

        target_vpn_gateways_client = MagicMock()
        target_vpn_gateways_client.aggregated_list.return_value = [("regions/us-central1", scoped)]

        result = collect_gcp_target_vpn_gateways(target_vpn_gateways_client, "proj")

        assert len(result) == 1
        assert result[0].resource_type == "gcp-target-vpn-gateway"
        assert result[0].ip_addresses == []

    def test_target_vpn_gateway_skips_empty_scopes(self):
        """Scoped list with no target_vpn_gateways emits no resources."""
        from cloud_usage.providers.gcp.collectors.networking import collect_gcp_target_vpn_gateways

        scoped = _make_empty_scoped_list("target_vpn_gateways")

        target_vpn_gateways_client = MagicMock()
        target_vpn_gateways_client.aggregated_list.return_value = [("regions/us-central1", scoped)]

        result = collect_gcp_target_vpn_gateways(target_vpn_gateways_client, "proj")

        assert result == []
