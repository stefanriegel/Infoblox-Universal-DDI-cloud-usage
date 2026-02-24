"""Tests for Azure hybrid networking and infrastructure resource collectors.

Uses unittest.mock to simulate Azure SDK client objects. Verifies that
load balancer, app gateway, firewall, NAT gateway, private endpoint,
VNet peering, ExpressRoute, VPN gateway, Virtual WAN hub, and Bastion
host collectors produce correctly-shaped CloudResource instances.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from cloud_usage.providers.azure.collectors.hybrid_networking import (
    collect_azure_app_gateways,
    collect_azure_bastion_hosts,
    collect_azure_express_route_circuits,
    collect_azure_firewalls,
    collect_azure_load_balancers,
    collect_azure_nat_gateways,
    collect_azure_private_endpoints,
    collect_azure_virtual_wan_hubs,
    collect_azure_vnet_peerings,
    collect_azure_vpn_gateways,
)
from cloud_usage.schema.resource import CloudResource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _arm_id(rg: str, provider_path: str) -> str:
    """Build a full ARM resource ID for tests."""
    return f"/subscriptions/sub1/resourceGroups/{rg}/providers/{provider_path}"


# ---------------------------------------------------------------------------
# Load Balancer tests
# ---------------------------------------------------------------------------

class TestCollectAzureLoadBalancers:
    """Tests for collect_azure_load_balancers."""

    def test_lb_public_and_internal(self):
        """Two LBs: one public, one internal. Verify type detection."""
        client = MagicMock()

        # Public LB: has public_ip_address reference in frontend config
        public_fe = SimpleNamespace(
            private_ip_address=None,
            public_ip_address=SimpleNamespace(id="/pip1"),
        )
        # Internal LB: has private IP, no public IP
        internal_fe = SimpleNamespace(
            private_ip_address="10.0.0.100",
            public_ip_address=None,
        )

        client.load_balancers.list_all.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/loadBalancers/lb-public"),
                name="lb-public",
                location="eastus",
                tags={"env": "prod"},
                frontend_ip_configurations=[public_fe],
            ),
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/loadBalancers/lb-internal"),
                name="lb-internal",
                location="eastus",
                tags=None,
                frontend_ip_configurations=[internal_fe],
            ),
        ]

        result = collect_azure_load_balancers(client, "sub1")

        assert len(result) == 2
        assert all(r.resource_type == "azure-lb" for r in result)
        assert all(r.provider == "azure" for r in result)

        # Public LB
        lb_pub = result[0]
        assert lb_pub.details["lb_type"] == "public"
        assert lb_pub.ip_addresses == []  # No private IP on public frontend
        assert lb_pub.tags == {"env": "prod"}

        # Internal LB
        lb_int = result[1]
        assert lb_int.details["lb_type"] == "internal"
        assert lb_int.ip_addresses == ["10.0.0.100"]
        assert lb_int.tags == {}

    def test_lb_empty_subscription(self):
        """No load balancers returns empty list."""
        client = MagicMock()
        client.load_balancers.list_all.return_value = []

        result = collect_azure_load_balancers(client, "sub1")
        assert result == []


# ---------------------------------------------------------------------------
# App Gateway tests
# ---------------------------------------------------------------------------

class TestCollectAzureAppGateways:
    """Tests for collect_azure_app_gateways."""

    def test_app_gateway_collection(self):
        """App gateway with private IP is discovered."""
        client = MagicMock()

        fe_config = SimpleNamespace(private_ip_address="10.0.1.5")
        client.application_gateways.list_all.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/applicationGateways/agw-prod"),
                name="agw-prod",
                location="eastus",
                tags={"env": "prod"},
                frontend_ip_configurations=[fe_config],
                sku=SimpleNamespace(name="WAF_v2"),
            ),
        ]

        result = collect_azure_app_gateways(client, "sub1")

        assert len(result) == 1
        agw = result[0]
        assert agw.resource_type == "azure-app-gateway"
        assert agw.ip_addresses == ["10.0.1.5"]
        assert agw.details["sku_name"] == "WAF_v2"
        assert agw.details["resource_group"] == "rg1"

    def test_app_gateway_no_private_ip(self):
        """App gateway without private IP has empty ip_addresses."""
        client = MagicMock()

        fe_config = SimpleNamespace(private_ip_address=None)
        client.application_gateways.list_all.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/applicationGateways/agw-noip"),
                name="agw-noip",
                location="eastus",
                tags=None,
                frontend_ip_configurations=[fe_config],
                sku=SimpleNamespace(name="Standard_v2"),
            ),
        ]

        result = collect_azure_app_gateways(client, "sub1")

        assert len(result) == 1
        assert result[0].ip_addresses == []


# ---------------------------------------------------------------------------
# Firewall tests
# ---------------------------------------------------------------------------

class TestCollectAzureFirewalls:
    """Tests for collect_azure_firewalls."""

    def test_firewall_with_ip_extraction(self):
        """Firewall with ip_configurations yields private IPs."""
        client = MagicMock()

        ip_config = SimpleNamespace(private_ip_address="10.0.0.4")
        client.azure_firewalls.list_all.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/azureFirewalls/fw-prod"),
                name="fw-prod",
                location="eastus",
                tags={"env": "prod"},
                ip_configurations=[ip_config],
                firewall_policy=SimpleNamespace(id="/policies/fp1"),
            ),
        ]

        result = collect_azure_firewalls(client, "sub1")

        assert len(result) == 1
        fw = result[0]
        assert fw.resource_type == "azure-firewall"
        assert fw.ip_addresses == ["10.0.0.4"]
        assert fw.details["firewall_policy_id"] == "/policies/fp1"
        assert fw.details["resource_group"] == "rg1"

    def test_firewall_no_policy(self):
        """Firewall without firewall_policy has None for policy_id."""
        client = MagicMock()

        client.azure_firewalls.list_all.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/azureFirewalls/fw-basic"),
                name="fw-basic",
                location="eastus",
                tags=None,
                ip_configurations=[SimpleNamespace(private_ip_address="10.0.0.5")],
                firewall_policy=None,
            ),
        ]

        result = collect_azure_firewalls(client, "sub1")

        assert len(result) == 1
        assert result[0].details["firewall_policy_id"] is None


# ---------------------------------------------------------------------------
# NAT Gateway tests
# ---------------------------------------------------------------------------

class TestCollectAzureNatGateways:
    """Tests for collect_azure_nat_gateways."""

    def test_nat_gateway_collection(self):
        """NAT gateway with public IP references is discovered."""
        client = MagicMock()

        pip_ref = SimpleNamespace(id="/pip/nat-pip-1")
        client.nat_gateways.list_all.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/natGateways/nat-gw-1"),
                name="nat-gw-1",
                location="eastus",
                tags={"env": "prod"},
                public_ip_addresses=[pip_ref],
            ),
        ]

        result = collect_azure_nat_gateways(client, "sub1")

        assert len(result) == 1
        nat = result[0]
        assert nat.resource_type == "azure-nat-gateway"
        assert nat.ip_addresses == []  # NAT gateways reference PIPs by ID
        assert nat.details["public_ip_address_ids"] == ["/pip/nat-pip-1"]


# ---------------------------------------------------------------------------
# Private Endpoint tests
# ---------------------------------------------------------------------------

class TestCollectAzurePrivateEndpoints:
    """Tests for collect_azure_private_endpoints."""

    def test_private_endpoint_with_custom_dns_ips(self):
        """Private endpoint with custom_dns_configs yields IPs."""
        client = MagicMock()

        dns_config = SimpleNamespace(ip_addresses=["10.0.0.50", "10.0.0.51"])
        pls_conn = SimpleNamespace(private_link_service_id="/services/sql1")

        client.private_endpoints.list_all.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/privateEndpoints/pe-sql"),
                name="pe-sql",
                location="eastus",
                tags={"service": "sql"},
                custom_dns_configs=[dns_config],
                network_interfaces=[],
                private_link_service_connections=[pls_conn],
            ),
        ]

        result = collect_azure_private_endpoints(client, "sub1")

        assert len(result) == 1
        pe = result[0]
        assert pe.resource_type == "azure-private-endpoint"
        assert pe.ip_addresses == ["10.0.0.50", "10.0.0.51"]
        assert pe.details["private_link_service_id"] == "/services/sql1"

    def test_private_endpoint_no_dns_configs(self):
        """Private endpoint without custom_dns_configs has empty IPs."""
        client = MagicMock()

        client.private_endpoints.list_all.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/privateEndpoints/pe-empty"),
                name="pe-empty",
                location="eastus",
                tags=None,
                custom_dns_configs=[],
                network_interfaces=[],
                private_link_service_connections=[],
            ),
        ]

        result = collect_azure_private_endpoints(client, "sub1")

        assert len(result) == 1
        assert result[0].ip_addresses == []
        assert result[0].details["private_link_service_id"] is None

    def test_private_endpoint_dedup_ips(self):
        """Duplicate IPs across dns configs are deduplicated."""
        client = MagicMock()

        dns_config1 = SimpleNamespace(ip_addresses=["10.0.0.50"])
        dns_config2 = SimpleNamespace(ip_addresses=["10.0.0.50", "10.0.0.51"])

        client.private_endpoints.list_all.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/privateEndpoints/pe-dup"),
                name="pe-dup",
                location="eastus",
                tags=None,
                custom_dns_configs=[dns_config1, dns_config2],
                network_interfaces=[],
                private_link_service_connections=[],
            ),
        ]

        result = collect_azure_private_endpoints(client, "sub1")

        assert len(result) == 1
        assert result[0].ip_addresses == ["10.0.0.50", "10.0.0.51"]


# ---------------------------------------------------------------------------
# VNet Peering tests
# ---------------------------------------------------------------------------

class TestCollectAzureVnetPeerings:
    """Tests for collect_azure_vnet_peerings."""

    def test_vnet_peering_across_two_vnets(self):
        """Peerings from 2 VNets are discovered."""
        client = MagicMock()

        vnet1 = CloudResource(
            resource_id=_arm_id("rg1", "Microsoft.Network/virtualNetworks/vnet1"),
            resource_type="azure-vnet",
            provider="azure",
            account_id="sub1",
            region="eastus",
            name="vnet1",
            details={"resource_group": "rg1"},
        )
        vnet2 = CloudResource(
            resource_id=_arm_id("rg2", "Microsoft.Network/virtualNetworks/vnet2"),
            resource_type="azure-vnet",
            provider="azure",
            account_id="sub1",
            region="westeurope",
            name="vnet2",
            details={"resource_group": "rg2"},
        )

        def mock_peerings_list(rg, vnet_name):
            if vnet_name == "vnet1":
                return [
                    SimpleNamespace(
                        id=f"{vnet1.resource_id}/virtualNetworkPeerings/peer-to-vnet2",
                        name="peer-to-vnet2",
                        remote_virtual_network=SimpleNamespace(id=vnet2.resource_id),
                        peering_state="Connected",
                    ),
                ]
            elif vnet_name == "vnet2":
                return [
                    SimpleNamespace(
                        id=f"{vnet2.resource_id}/virtualNetworkPeerings/peer-to-vnet1",
                        name="peer-to-vnet1",
                        remote_virtual_network=SimpleNamespace(id=vnet1.resource_id),
                        peering_state="Connected",
                    ),
                ]
            return []

        client.virtual_network_peerings.list.side_effect = mock_peerings_list

        result = collect_azure_vnet_peerings(client, "sub1", [vnet1, vnet2])

        assert len(result) == 2
        assert all(r.resource_type == "azure-vnet-peering" for r in result)
        assert all(r.ip_addresses == [] for r in result)

        # First peering from vnet1
        p1 = result[0]
        assert p1.details["vnet_id"] == vnet1.resource_id
        assert p1.details["remote_vnet_id"] == vnet2.resource_id
        assert p1.details["peering_state"] == "Connected"
        assert p1.region == "eastus"

        # Second peering from vnet2
        p2 = result[1]
        assert p2.details["vnet_id"] == vnet2.resource_id
        assert p2.details["remote_vnet_id"] == vnet1.resource_id
        assert p2.region == "westeurope"

    def test_vnet_peering_skips_vnets_without_rg(self):
        """VNets with empty resource_group are skipped."""
        client = MagicMock()

        vnet_no_rg = CloudResource(
            resource_id="/invalid",
            resource_type="azure-vnet",
            provider="azure",
            account_id="sub1",
            region="eastus",
            name="vnet-broken",
            details={"resource_group": ""},
        )

        result = collect_azure_vnet_peerings(client, "sub1", [vnet_no_rg])

        assert result == []
        client.virtual_network_peerings.list.assert_not_called()


# ---------------------------------------------------------------------------
# VPN Gateway tests
# ---------------------------------------------------------------------------

class TestCollectAzureVpnGateways:
    """Tests for collect_azure_vpn_gateways."""

    def test_vpn_gateway_per_rg_iteration(self):
        """VPN gateways listed per unique resource group from VNets."""
        client = MagicMock()

        # Two VNets in different RGs
        vnets = [
            CloudResource(
                resource_id=_arm_id("rg1", "Microsoft.Network/virtualNetworks/vnet1"),
                resource_type="azure-vnet", provider="azure", account_id="sub1",
                region="eastus", name="vnet1", details={"resource_group": "rg1"},
            ),
            CloudResource(
                resource_id=_arm_id("rg2", "Microsoft.Network/virtualNetworks/vnet2"),
                resource_type="azure-vnet", provider="azure", account_id="sub1",
                region="westeurope", name="vnet2", details={"resource_group": "rg2"},
            ),
        ]

        def mock_gw_list(rg):
            if rg == "rg1":
                return [
                    SimpleNamespace(
                        id=_arm_id("rg1", "Microsoft.Network/virtualNetworkGateways/vpn-gw-1"),
                        name="vpn-gw-1",
                        location="eastus",
                        tags=None,
                        ip_configurations=[SimpleNamespace(private_ip_address="10.0.0.10")],
                        gateway_type="Vpn",
                        vpn_type="RouteBased",
                    ),
                ]
            return []

        client.virtual_network_gateways.list.side_effect = mock_gw_list

        result = collect_azure_vpn_gateways(client, "sub1", vnets)

        assert len(result) == 1
        gw = result[0]
        assert gw.resource_type == "azure-vpn-gateway"
        assert gw.ip_addresses == ["10.0.0.10"]
        assert gw.details["gateway_type"] == "Vpn"
        assert gw.details["vpn_type"] == "RouteBased"
        assert gw.details["resource_group"] == "rg1"

        # Both RGs should be queried
        assert client.virtual_network_gateways.list.call_count == 2

    def test_vpn_gateway_dedup_rgs(self):
        """Duplicate resource groups from multiple VNets are deduplicated."""
        client = MagicMock()

        vnets = [
            CloudResource(
                resource_id=_arm_id("rg1", "Microsoft.Network/virtualNetworks/vnet1"),
                resource_type="azure-vnet", provider="azure", account_id="sub1",
                region="eastus", name="vnet1", details={"resource_group": "rg1"},
            ),
            CloudResource(
                resource_id=_arm_id("rg1", "Microsoft.Network/virtualNetworks/vnet2"),
                resource_type="azure-vnet", provider="azure", account_id="sub1",
                region="eastus", name="vnet2", details={"resource_group": "rg1"},
            ),
        ]

        client.virtual_network_gateways.list.return_value = []

        result = collect_azure_vpn_gateways(client, "sub1", vnets)

        # Only queried rg1 once despite two VNets in same RG
        assert client.virtual_network_gateways.list.call_count == 1


# ---------------------------------------------------------------------------
# ExpressRoute tests
# ---------------------------------------------------------------------------

class TestCollectAzureExpressRouteCircuits:
    """Tests for collect_azure_express_route_circuits."""

    def test_express_route_collection(self):
        """ExpressRoute circuits are discovered with provider details."""
        client = MagicMock()

        client.express_route_circuits.list_all.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/expressRouteCircuits/er-prod"),
                name="er-prod",
                location="eastus",
                tags={"env": "prod"},
                service_provider_properties=SimpleNamespace(
                    service_provider_name="Equinix",
                    peering_location="Washington DC",
                    bandwidth_in_mbps=1000,
                ),
            ),
        ]

        result = collect_azure_express_route_circuits(client, "sub1")

        assert len(result) == 1
        er = result[0]
        assert er.resource_type == "azure-express-route"
        assert er.ip_addresses == []
        assert er.details["service_provider_name"] == "Equinix"
        assert er.details["peering_location"] == "Washington DC"
        assert er.details["bandwidth_in_mbps"] == 1000

    def test_express_route_no_provider_properties(self):
        """ExpressRoute without service_provider_properties uses defaults."""
        client = MagicMock()

        client.express_route_circuits.list_all.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/expressRouteCircuits/er-noprops"),
                name="er-noprops",
                location="eastus",
                tags=None,
                service_provider_properties=None,
            ),
        ]

        result = collect_azure_express_route_circuits(client, "sub1")

        assert len(result) == 1
        assert result[0].details["service_provider_name"] == ""
        assert result[0].details["bandwidth_in_mbps"] == 0


# ---------------------------------------------------------------------------
# Virtual WAN Hub tests
# ---------------------------------------------------------------------------

class TestCollectAzureVirtualWanHubs:
    """Tests for collect_azure_virtual_wan_hubs."""

    def test_virtual_wan_hub_collection(self):
        """Two Virtual WAN hubs with virtual_wan references discovered."""
        client = MagicMock()

        client.virtual_hubs.list.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/virtualHubs/hub-eastus"),
                name="hub-eastus",
                location="eastus",
                tags={"env": "prod"},
                virtual_wan=SimpleNamespace(id="/vwan/wan-1"),
                address_prefix="10.1.0.0/16",
                routing_state="Provisioned",
                provisioning_state="Succeeded",
            ),
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/virtualHubs/hub-westeurope"),
                name="hub-westeurope",
                location="westeurope",
                tags=None,
                virtual_wan=SimpleNamespace(id="/vwan/wan-1"),
                address_prefix="10.2.0.0/16",
                routing_state="Provisioned",
                provisioning_state="Succeeded",
            ),
        ]

        result = collect_azure_virtual_wan_hubs(client, "sub1")

        assert len(result) == 2
        assert all(r.resource_type == "azure-vwan-hub" for r in result)
        assert all(r.ip_addresses == [] for r in result)

        hub1 = result[0]
        assert hub1.details["virtual_wan_id"] == "/vwan/wan-1"
        assert hub1.details["address_prefix"] == "10.1.0.0/16"
        assert hub1.details["routing_state"] == "Provisioned"
        assert hub1.details["provisioning_state"] == "Succeeded"
        assert hub1.region == "eastus"

        hub2 = result[1]
        assert hub2.region == "westeurope"
        assert hub2.details["address_prefix"] == "10.2.0.0/16"

    def test_virtual_wan_hub_no_wan_reference(self):
        """Hub without virtual_wan has None for virtual_wan_id."""
        client = MagicMock()

        client.virtual_hubs.list.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/virtualHubs/hub-standalone"),
                name="hub-standalone",
                location="eastus",
                tags=None,
                virtual_wan=None,
                address_prefix="10.3.0.0/16",
                routing_state="Provisioned",
                provisioning_state="Succeeded",
            ),
        ]

        result = collect_azure_virtual_wan_hubs(client, "sub1")

        assert len(result) == 1
        assert result[0].details["virtual_wan_id"] is None


# ---------------------------------------------------------------------------
# Bastion Host tests
# ---------------------------------------------------------------------------

class TestCollectAzureBastionHosts:
    """Tests for collect_azure_bastion_hosts."""

    def test_bastion_host_collection(self):
        """Bastion host with IP configuration is discovered."""
        client = MagicMock()

        ip_config = SimpleNamespace(private_ip_address="10.0.0.200")
        client.bastion_hosts.list.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/bastionHosts/bastion-prod"),
                name="bastion-prod",
                location="eastus",
                tags={"env": "prod"},
                ip_configurations=[ip_config],
                dns_name="bastion-prod.bastion.azure.com",
            ),
        ]

        result = collect_azure_bastion_hosts(client, "sub1")

        assert len(result) == 1
        bastion = result[0]
        assert bastion.resource_type == "azure-bastion"
        assert bastion.ip_addresses == ["10.0.0.200"]
        assert bastion.details["dns_name"] == "bastion-prod.bastion.azure.com"
        assert bastion.details["resource_group"] == "rg1"

    def test_bastion_host_no_ip_configs(self):
        """Bastion host without ip_configurations has empty IPs."""
        client = MagicMock()

        client.bastion_hosts.list.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Network/bastionHosts/bastion-noip"),
                name="bastion-noip",
                location="eastus",
                tags=None,
                ip_configurations=None,
                dns_name="",
            ),
        ]

        result = collect_azure_bastion_hosts(client, "sub1")

        assert len(result) == 1
        assert result[0].ip_addresses == []
        assert result[0].details["dns_name"] == ""
