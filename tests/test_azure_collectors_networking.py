"""Tests for Azure networking resource collectors.

Uses unittest.mock to simulate Azure SDK client objects. Verifies that
VNet, subnet, DHCP config, NIC, and public IP collectors produce
correctly-shaped CloudResource instances.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cloud_usage.providers.azure.collectors.networking import (
    collect_azure_dhcp_configs,
    collect_azure_nics,
    collect_azure_public_ips,
    collect_azure_subnets,
    collect_azure_vnets,
)
from cloud_usage.schema.resource import CloudResource


# ---------------------------------------------------------------------------
# Helpers to build mock Azure SDK model objects
# ---------------------------------------------------------------------------

def _make_vnet(
    name: str,
    location: str,
    resource_id: str,
    address_prefixes: list[str] | None = None,
    dns_servers: list[str] | None = None,
    tags: dict[str, str] | None = None,
) -> SimpleNamespace:
    """Build a mock VNet SDK object with attribute access."""
    address_space = None
    if address_prefixes is not None:
        address_space = SimpleNamespace(address_prefixes=address_prefixes)

    dhcp_options = None
    if dns_servers is not None:
        dhcp_options = SimpleNamespace(dns_servers=dns_servers)

    return SimpleNamespace(
        id=resource_id,
        name=name,
        location=location,
        tags=tags,
        address_space=address_space,
        dhcp_options=dhcp_options,
    )


def _make_subnet(
    name: str,
    resource_id: str,
    address_prefix: str = "10.0.0.0/24",
) -> SimpleNamespace:
    """Build a mock Subnet SDK object."""
    return SimpleNamespace(
        id=resource_id,
        name=name,
        address_prefix=address_prefix,
    )


def _make_nic(
    name: str,
    location: str,
    resource_id: str,
    ip_configs: list[dict] | None = None,
    vm_id: str | None = None,
    tags: dict[str, str] | None = None,
) -> SimpleNamespace:
    """Build a mock NIC SDK object."""
    ip_configurations = []
    for cfg in (ip_configs or []):
        ip_configurations.append(
            SimpleNamespace(private_ip_address=cfg.get("private_ip"))
        )

    virtual_machine = None
    if vm_id:
        virtual_machine = SimpleNamespace(id=vm_id)

    return SimpleNamespace(
        id=resource_id,
        name=name,
        location=location,
        tags=tags,
        ip_configurations=ip_configurations if ip_configurations else None,
        virtual_machine=virtual_machine,
    )


def _make_public_ip(
    name: str,
    location: str,
    resource_id: str,
    ip_address: str | None = None,
    allocation_method: str = "Static",
    ip_config_id: str | None = None,
    tags: dict[str, str] | None = None,
) -> SimpleNamespace:
    """Build a mock PublicIPAddress SDK object."""
    ip_configuration = None
    if ip_config_id:
        ip_configuration = SimpleNamespace(id=ip_config_id)

    return SimpleNamespace(
        id=resource_id,
        name=name,
        location=location,
        tags=tags,
        ip_address=ip_address,
        public_ip_allocation_method=allocation_method,
        ip_configuration=ip_configuration,
    )


# ---------------------------------------------------------------------------
# VNet tests
# ---------------------------------------------------------------------------

class TestCollectAzureVnets:
    """Tests for collect_azure_vnets."""

    def test_basic_vnet_collection(self):
        """Two VNets with address spaces and DHCP options are discovered."""
        mock_client = MagicMock()
        mock_client.virtual_networks.list_all.return_value = [
            _make_vnet(
                name="vnet-prod",
                location="eastus",
                resource_id="/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Network/virtualNetworks/vnet-prod",
                address_prefixes=["10.0.0.0/16", "172.16.0.0/16"],
                dns_servers=["10.0.0.4", "10.0.0.5"],
                tags={"env": "production"},
            ),
            _make_vnet(
                name="vnet-dev",
                location="westeurope",
                resource_id="/subscriptions/sub1/resourceGroups/rg-dev/providers/Microsoft.Network/virtualNetworks/vnet-dev",
                address_prefixes=["192.168.0.0/16"],
                tags={"env": "development"},
            ),
        ]

        result = collect_azure_vnets(mock_client, "sub1")

        assert len(result) == 2
        assert all(isinstance(r, CloudResource) for r in result)

        # First VNet
        vnet1 = result[0]
        assert vnet1.resource_type == "azure-vnet"
        assert vnet1.provider == "azure"
        assert vnet1.account_id == "sub1"
        assert vnet1.region == "eastus"
        assert vnet1.name == "vnet-prod"
        assert vnet1.resource_id == "/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Network/virtualNetworks/vnet-prod"
        assert vnet1.ip_addresses == []
        assert vnet1.tags == {"env": "production"}
        assert vnet1.details["resource_group"] == "rg-prod"
        assert vnet1.details["address_prefixes"] == ["10.0.0.0/16", "172.16.0.0/16"]
        assert vnet1.details["dhcp_dns_servers"] == ["10.0.0.4", "10.0.0.5"]

        # Second VNet (no DHCP)
        vnet2 = result[1]
        assert vnet2.details["dhcp_dns_servers"] == []
        assert vnet2.details["resource_group"] == "rg-dev"

    def test_vnet_with_no_dhcp_options(self):
        """VNet without DHCP options has empty dhcp_dns_servers."""
        mock_client = MagicMock()
        mock_client.virtual_networks.list_all.return_value = [
            _make_vnet(
                name="vnet-nodns",
                location="eastus",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-nodns",
                address_prefixes=["10.0.0.0/16"],
            ),
        ]

        result = collect_azure_vnets(mock_client, "sub1")

        assert len(result) == 1
        assert result[0].details["dhcp_dns_servers"] == []

    def test_vnet_with_no_address_space(self):
        """VNet without address_space has empty address_prefixes."""
        mock_client = MagicMock()
        mock_client.virtual_networks.list_all.return_value = [
            _make_vnet(
                name="vnet-empty",
                location="eastus",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-empty",
            ),
        ]

        result = collect_azure_vnets(mock_client, "sub1")

        assert len(result) == 1
        assert result[0].details["address_prefixes"] == []

    def test_vnet_with_no_tags(self):
        """VNet with tags=None gets empty tags dict."""
        mock_client = MagicMock()
        mock_client.virtual_networks.list_all.return_value = [
            _make_vnet(
                name="vnet-notags",
                location="eastus",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-notags",
                address_prefixes=["10.0.0.0/8"],
            ),
        ]

        result = collect_azure_vnets(mock_client, "sub1")

        assert result[0].tags == {}


# ---------------------------------------------------------------------------
# Subnet tests
# ---------------------------------------------------------------------------

class TestCollectAzureSubnets:
    """Tests for collect_azure_subnets."""

    def test_subnet_collection_from_two_vnets(self):
        """Subnets from 2 VNets are discovered with inherited region."""
        vnet1 = CloudResource(
            resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            resource_type="azure-vnet",
            provider="azure",
            account_id="sub1",
            region="eastus",
            name="vnet1",
            details={"resource_group": "rg1"},
        )
        vnet2 = CloudResource(
            resource_id="/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Network/virtualNetworks/vnet2",
            resource_type="azure-vnet",
            provider="azure",
            account_id="sub1",
            region="westeurope",
            name="vnet2",
            details={"resource_group": "rg2"},
        )

        mock_client = MagicMock()

        def subnets_list(rg, vnet_name):
            if vnet_name == "vnet1":
                return [
                    _make_subnet("subnet-a", "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet-a", "10.0.1.0/24"),
                    _make_subnet("subnet-b", "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet-b", "10.0.2.0/24"),
                ]
            elif vnet_name == "vnet2":
                return [
                    _make_subnet("subnet-c", "/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Network/virtualNetworks/vnet2/subnets/subnet-c", "192.168.0.0/24"),
                ]
            return []

        mock_client.subnets.list.side_effect = subnets_list

        result = collect_azure_subnets(mock_client, "sub1", [vnet1, vnet2])

        assert len(result) == 3
        assert all(r.resource_type == "azure-subnet" for r in result)
        assert all(r.provider == "azure" for r in result)

        # subnet-a inherits eastus from vnet1
        assert result[0].region == "eastus"
        assert result[0].details["vnet_id"] == vnet1.resource_id
        assert result[0].details["address_prefix"] == "10.0.1.0/24"

        # subnet-c inherits westeurope from vnet2
        assert result[2].region == "westeurope"
        assert result[2].details["vnet_id"] == vnet2.resource_id

    def test_subnet_skips_vnets_with_missing_resource_group(self):
        """VNets with empty resource_group are skipped."""
        vnet_no_rg = CloudResource(
            resource_id="/some/invalid/id",
            resource_type="azure-vnet",
            provider="azure",
            account_id="sub1",
            region="eastus",
            name="vnet-broken",
            details={"resource_group": ""},
        )

        mock_client = MagicMock()
        result = collect_azure_subnets(mock_client, "sub1", [vnet_no_rg])

        assert result == []
        mock_client.subnets.list.assert_not_called()

    def test_subnet_skips_vnets_with_missing_name(self):
        """VNets with empty name are skipped."""
        vnet_no_name = CloudResource(
            resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            resource_type="azure-vnet",
            provider="azure",
            account_id="sub1",
            region="eastus",
            name="",
            details={"resource_group": "rg1"},
        )

        mock_client = MagicMock()
        result = collect_azure_subnets(mock_client, "sub1", [vnet_no_name])

        assert result == []
        mock_client.subnets.list.assert_not_called()


# ---------------------------------------------------------------------------
# DHCP config tests
# ---------------------------------------------------------------------------

class TestCollectAzureDhcpConfigs:
    """Tests for collect_azure_dhcp_configs."""

    def test_dhcp_config_extraction(self):
        """3 VNets, 2 with DHCP options, yield 2 DHCP configs."""
        vnets = [
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-a",
                resource_type="azure-vnet",
                provider="azure",
                account_id="sub1",
                region="eastus",
                name="vnet-a",
                details={
                    "resource_group": "rg1",
                    "dhcp_dns_servers": ["10.0.0.4", "10.0.0.5"],
                },
            ),
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-b",
                resource_type="azure-vnet",
                provider="azure",
                account_id="sub1",
                region="eastus",
                name="vnet-b",
                details={
                    "resource_group": "rg1",
                    "dhcp_dns_servers": [],
                },
            ),
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Network/virtualNetworks/vnet-c",
                resource_type="azure-vnet",
                provider="azure",
                account_id="sub1",
                region="westeurope",
                name="vnet-c",
                details={
                    "resource_group": "rg2",
                    "dhcp_dns_servers": ["8.8.8.8"],
                },
            ),
        ]

        result = collect_azure_dhcp_configs(vnets)

        assert len(result) == 2
        assert all(r.resource_type == "azure-dhcp-config" for r in result)
        assert all(r.provider == "azure" for r in result)

        # First DHCP config from vnet-a
        dhcp1 = result[0]
        assert dhcp1.resource_id == "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet-a/dhcpOptions"
        assert dhcp1.details["dns_servers"] == ["10.0.0.4", "10.0.0.5"]
        assert dhcp1.details["vnet_id"] == vnets[0].resource_id
        assert dhcp1.region == "eastus"
        assert dhcp1.name == "vnet-a-dhcp"

        # Second DHCP config from vnet-c
        dhcp2 = result[1]
        assert dhcp2.details["dns_servers"] == ["8.8.8.8"]
        assert dhcp2.region == "westeurope"

    def test_dhcp_config_skips_vnets_without_dns_servers(self):
        """VNets with no dhcp_dns_servers produce no DHCP configs."""
        vnets = [
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                resource_type="azure-vnet",
                provider="azure",
                account_id="sub1",
                region="eastus",
                name="vnet1",
                details={"resource_group": "rg1", "dhcp_dns_servers": []},
            ),
            CloudResource(
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet2",
                resource_type="azure-vnet",
                provider="azure",
                account_id="sub1",
                region="eastus",
                name="vnet2",
                details={"resource_group": "rg1"},
            ),
        ]

        result = collect_azure_dhcp_configs(vnets)

        assert result == []

    def test_dhcp_config_inherits_account_and_region(self):
        """DHCP config inherits account_id and region from parent VNet."""
        vnets = [
            CloudResource(
                resource_id="/subscriptions/sub-xyz/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                resource_type="azure-vnet",
                provider="azure",
                account_id="sub-xyz",
                region="japaneast",
                name="vnet1",
                details={"resource_group": "rg1", "dhcp_dns_servers": ["1.1.1.1"]},
            ),
        ]

        result = collect_azure_dhcp_configs(vnets)

        assert len(result) == 1
        assert result[0].account_id == "sub-xyz"
        assert result[0].region == "japaneast"


# ---------------------------------------------------------------------------
# NIC tests
# ---------------------------------------------------------------------------

class TestCollectAzureNics:
    """Tests for collect_azure_nics."""

    def test_nic_collection_with_multiple_ip_configs(self):
        """NIC with 2 ip_configurations yields 2 private IPs."""
        mock_client = MagicMock()
        mock_client.network_interfaces.list_all.return_value = [
            _make_nic(
                name="nic-multi",
                location="eastus",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic-multi",
                ip_configs=[
                    {"private_ip": "10.0.0.4"},
                    {"private_ip": "10.0.0.5"},
                ],
                vm_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            ),
        ]

        result = collect_azure_nics(mock_client, "sub1")

        assert len(result) == 1
        nic = result[0]
        assert nic.resource_type == "azure-nic"
        assert nic.ip_addresses == ["10.0.0.4", "10.0.0.5"]
        assert nic.details["vm_id"] == "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
        assert nic.details["ip_configuration_count"] == 2

    def test_nic_with_single_ip(self):
        """NIC with 1 ip_configuration yields 1 private IP."""
        mock_client = MagicMock()
        mock_client.network_interfaces.list_all.return_value = [
            _make_nic(
                name="nic-single",
                location="westeurope",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic-single",
                ip_configs=[{"private_ip": "192.168.1.10"}],
                vm_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm2",
            ),
        ]

        result = collect_azure_nics(mock_client, "sub1")

        assert len(result) == 1
        assert result[0].ip_addresses == ["192.168.1.10"]

    def test_nic_unattached(self):
        """Unattached NIC (no VM) is still discovered."""
        mock_client = MagicMock()
        mock_client.network_interfaces.list_all.return_value = [
            _make_nic(
                name="nic-orphan",
                location="eastus",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic-orphan",
                ip_configs=[{"private_ip": "10.0.0.100"}],
            ),
        ]

        result = collect_azure_nics(mock_client, "sub1")

        assert len(result) == 1
        assert result[0].details["vm_id"] is None
        assert result[0].ip_addresses == ["10.0.0.100"]

    def test_nic_collection_three_nics(self):
        """Three NICs: 2 IPs, 1 IP, unattached -- all discovered."""
        mock_client = MagicMock()
        mock_client.network_interfaces.list_all.return_value = [
            _make_nic(
                name="nic-a",
                location="eastus",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic-a",
                ip_configs=[{"private_ip": "10.0.0.4"}, {"private_ip": "10.0.0.5"}],
                vm_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            ),
            _make_nic(
                name="nic-b",
                location="westeurope",
                resource_id="/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Network/networkInterfaces/nic-b",
                ip_configs=[{"private_ip": "192.168.1.10"}],
                vm_id="/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Compute/virtualMachines/vm2",
            ),
            _make_nic(
                name="nic-c",
                location="eastus",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic-c",
                ip_configs=[{"private_ip": "10.0.0.100"}],
            ),
        ]

        result = collect_azure_nics(mock_client, "sub1")

        assert len(result) == 3
        assert all(r.resource_type == "azure-nic" for r in result)
        assert all(r.provider == "azure" for r in result)
        assert result[0].ip_addresses == ["10.0.0.4", "10.0.0.5"]
        assert result[1].ip_addresses == ["192.168.1.10"]
        assert result[2].ip_addresses == ["10.0.0.100"]
        assert result[2].details["vm_id"] is None

    def test_nic_with_no_ip_configurations(self):
        """NIC with ip_configurations=None produces empty IP list."""
        mock_client = MagicMock()
        mock_client.network_interfaces.list_all.return_value = [
            _make_nic(
                name="nic-noip",
                location="eastus",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic-noip",
            ),
        ]

        result = collect_azure_nics(mock_client, "sub1")

        assert len(result) == 1
        assert result[0].ip_addresses == []
        assert result[0].details["ip_configuration_count"] == 0


# ---------------------------------------------------------------------------
# Public IP tests
# ---------------------------------------------------------------------------

class TestCollectAzurePublicIps:
    """Tests for collect_azure_public_ips."""

    def test_public_ip_collection(self):
        """Two public IPs: one allocated, one not yet allocated."""
        mock_client = MagicMock()
        mock_client.public_ip_addresses.list_all.return_value = [
            _make_public_ip(
                name="pip-allocated",
                location="eastus",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/publicIPAddresses/pip-allocated",
                ip_address="20.0.0.1",
                allocation_method="Static",
                ip_config_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1/ipConfigurations/ipconfig1",
            ),
            _make_public_ip(
                name="pip-unallocated",
                location="westeurope",
                resource_id="/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Network/publicIPAddresses/pip-unallocated",
                ip_address=None,
                allocation_method="Dynamic",
            ),
        ]

        result = collect_azure_public_ips(mock_client, "sub1")

        assert len(result) == 2
        assert all(r.resource_type == "azure-public-ip" for r in result)
        assert all(r.provider == "azure" for r in result)

        # Allocated IP
        pip1 = result[0]
        assert pip1.ip_addresses == ["20.0.0.1"]
        assert pip1.details["allocation_method"] == "Static"
        assert pip1.details["ip_configuration_id"] == "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1/ipConfigurations/ipconfig1"

        # Unallocated IP
        pip2 = result[1]
        assert pip2.ip_addresses == []
        assert pip2.details["allocation_method"] == "Dynamic"
        assert pip2.details["ip_configuration_id"] is None


# ---------------------------------------------------------------------------
# Import verification test
# ---------------------------------------------------------------------------

class TestImportFromUtils:
    """Verify collectors use _extract_resource_group from utils module."""

    def test_extract_resource_group_import_works(self):
        """Verify _extract_resource_group is importable from utils."""
        from cloud_usage.providers.azure.utils import _extract_resource_group

        assert _extract_resource_group(
            "/subscriptions/sub1/resourceGroups/myRG/providers/Microsoft.Network/virtualNetworks/vnet1"
        ) == "myRG"

    def test_extract_resource_group_case_insensitive(self):
        """ARM IDs with non-standard casing are handled."""
        from cloud_usage.providers.azure.utils import _extract_resource_group

        assert _extract_resource_group(
            "/subscriptions/sub1/RESOURCEGROUPS/MyRG/providers/Microsoft.Network/virtualNetworks/vnet1"
        ) == "MyRG"

    def test_extract_resource_group_empty_id(self):
        """Empty resource ID returns empty string."""
        from cloud_usage.providers.azure.utils import _extract_resource_group

        assert _extract_resource_group("") == ""

    def test_extract_resource_group_malformed_id(self):
        """Malformed resource ID without resourceGroups returns empty string."""
        from cloud_usage.providers.azure.utils import _extract_resource_group

        assert _extract_resource_group("/some/random/path") == ""
