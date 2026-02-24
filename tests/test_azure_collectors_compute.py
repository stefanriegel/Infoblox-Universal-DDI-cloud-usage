"""Tests for Azure compute resource collectors.

Uses unittest.mock to simulate Azure SDK client objects. Verifies that
VM and VMSS instance collectors produce correctly-shaped CloudResource
instances with proper IP extraction and NIC cross-referencing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from cloud_usage.providers.azure.collectors.compute import (
    collect_azure_vms,
    collect_azure_vmss_instances,
)
from cloud_usage.schema.resource import CloudResource


# ---------------------------------------------------------------------------
# Helpers to build mock Azure SDK model objects
# ---------------------------------------------------------------------------

def _make_vm(
    name: str,
    location: str,
    resource_id: str,
    vm_size: str = "Standard_D2s_v3",
    provisioning_state: str = "Succeeded",
    nic_ids: list[str] | None = None,
    tags: dict[str, str] | None = None,
    network_profile: bool = True,
) -> SimpleNamespace:
    """Build a mock VM SDK object with attribute access."""
    hardware_profile = SimpleNamespace(vm_size=vm_size)

    net_profile = None
    if network_profile and nic_ids is not None:
        net_profile = SimpleNamespace(
            network_interfaces=[SimpleNamespace(id=nic_id) for nic_id in nic_ids]
        )
    elif network_profile:
        net_profile = SimpleNamespace(network_interfaces=[])

    return SimpleNamespace(
        id=resource_id,
        name=name,
        location=location,
        tags=tags,
        hardware_profile=hardware_profile,
        network_profile=net_profile,
        provisioning_state=provisioning_state,
    )


def _make_vmss(
    name: str,
    location: str,
    resource_id: str,
    tags: dict[str, str] | None = None,
) -> SimpleNamespace:
    """Build a mock VMSS SDK object."""
    return SimpleNamespace(
        id=resource_id,
        name=name,
        location=location,
        tags=tags,
    )


def _make_vmss_instance(
    instance_id: str,
    name: str,
    resource_id: str,
) -> SimpleNamespace:
    """Build a mock VMSS instance SDK object."""
    return SimpleNamespace(
        id=resource_id,
        name=name,
        instance_id=instance_id,
    )


def _make_vmss_nic(
    ip_configs: list[dict],
) -> SimpleNamespace:
    """Build a mock NIC for VMSS instance with ip_configurations."""
    return SimpleNamespace(
        ip_configurations=[
            SimpleNamespace(private_ip_address=cfg.get("private_ip"))
            for cfg in ip_configs
        ]
    )


# ---------------------------------------------------------------------------
# VM tests
# ---------------------------------------------------------------------------

class TestCollectAzureVms:
    """Tests for collect_azure_vms."""

    def test_basic_vm_collection(self):
        """Two VMs with NIC IDs are discovered with ip_addresses=[]."""
        compute_client = MagicMock()
        network_client = MagicMock()

        compute_client.virtual_machines.list_all.return_value = [
            _make_vm(
                name="vm-web",
                location="eastus",
                resource_id="/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/vm-web",
                vm_size="Standard_D4s_v3",
                nic_ids=[
                    "/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Network/networkInterfaces/nic-web-1",
                    "/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Network/networkInterfaces/nic-web-2",
                ],
                tags={"env": "production", "role": "web"},
            ),
            _make_vm(
                name="vm-db",
                location="westeurope",
                resource_id="/subscriptions/sub1/resourceGroups/rg-data/providers/Microsoft.Compute/virtualMachines/vm-db",
                vm_size="Standard_E8s_v3",
                nic_ids=[
                    "/subscriptions/sub1/resourceGroups/rg-data/providers/Microsoft.Network/networkInterfaces/nic-db-1",
                ],
                tags={"env": "production", "role": "database"},
            ),
        ]

        result = collect_azure_vms(compute_client, network_client, "sub1")

        assert len(result) == 2
        assert all(isinstance(r, CloudResource) for r in result)

        # VM 1
        vm1 = result[0]
        assert vm1.resource_type == "azure-vm"
        assert vm1.provider == "azure"
        assert vm1.account_id == "sub1"
        assert vm1.region == "eastus"
        assert vm1.name == "vm-web"
        assert vm1.ip_addresses == []  # No inline NIC resolution
        assert vm1.tags == {"env": "production", "role": "web"}
        assert vm1.details["resource_group"] == "rg-prod"
        assert vm1.details["vm_size"] == "Standard_D4s_v3"
        assert vm1.details["provisioning_state"] == "Succeeded"
        assert len(vm1.details["nic_ids"]) == 2
        assert "/Microsoft.Network/networkInterfaces/nic-web-1" in vm1.details["nic_ids"][0]

        # VM 2
        vm2 = result[1]
        assert vm2.region == "westeurope"
        assert len(vm2.details["nic_ids"]) == 1

    def test_vm_with_missing_network_profile(self):
        """VM with no network_profile still discovered with empty nic_ids."""
        compute_client = MagicMock()
        network_client = MagicMock()

        compute_client.virtual_machines.list_all.return_value = [
            _make_vm(
                name="vm-isolated",
                location="eastus",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm-isolated",
                network_profile=False,
            ),
        ]

        result = collect_azure_vms(compute_client, network_client, "sub1")

        assert len(result) == 1
        assert result[0].details["nic_ids"] == []
        assert result[0].ip_addresses == []

    def test_vm_with_no_tags(self):
        """VM with tags=None gets empty tags dict."""
        compute_client = MagicMock()
        network_client = MagicMock()

        compute_client.virtual_machines.list_all.return_value = [
            _make_vm(
                name="vm-notags",
                location="eastus",
                resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm-notags",
            ),
        ]

        result = collect_azure_vms(compute_client, network_client, "sub1")

        assert result[0].tags == {}

    def test_vm_empty_subscription(self):
        """Empty subscription returns empty list."""
        compute_client = MagicMock()
        network_client = MagicMock()
        compute_client.virtual_machines.list_all.return_value = []

        result = collect_azure_vms(compute_client, network_client, "sub1")

        assert result == []


# ---------------------------------------------------------------------------
# VMSS instance tests
# ---------------------------------------------------------------------------

class TestCollectAzureVmssInstances:
    """Tests for collect_azure_vmss_instances."""

    def test_vmss_instance_enumeration(self):
        """1 VMSS with 3 instances, each with 1 NIC having 1 private IP."""
        compute_client = MagicMock()
        network_client = MagicMock()

        vmss = _make_vmss(
            name="vmss-web",
            location="eastus",
            resource_id="/subscriptions/sub1/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachineScaleSets/vmss-web",
            tags={"env": "production"},
        )
        compute_client.virtual_machine_scale_sets.list_all.return_value = [vmss]

        # 3 instances
        compute_client.virtual_machine_scale_set_vms.list.return_value = [
            _make_vmss_instance("0", "vmss-web_0", f"{vmss.id}/virtualMachines/0"),
            _make_vmss_instance("1", "vmss-web_1", f"{vmss.id}/virtualMachines/1"),
            _make_vmss_instance("2", "vmss-web_2", f"{vmss.id}/virtualMachines/2"),
        ]

        # Each instance has 1 NIC with 1 private IP
        def mock_list_vmss_nics(rg, vmss_name, instance_id):
            ip = f"10.0.0.{int(instance_id) + 4}"
            return [_make_vmss_nic([{"private_ip": ip}])]

        network_client.network_interfaces.list_virtual_machine_scale_set_vm_network_interfaces.side_effect = mock_list_vmss_nics

        result = collect_azure_vmss_instances(compute_client, network_client, "sub1")

        assert len(result) == 3
        assert all(r.resource_type == "azure-vmss-instance" for r in result)
        assert all(r.provider == "azure" for r in result)
        assert all(r.account_id == "sub1" for r in result)
        assert all(r.region == "eastus" for r in result)

        # Verify IPs
        assert result[0].ip_addresses == ["10.0.0.4"]
        assert result[1].ip_addresses == ["10.0.0.5"]
        assert result[2].ip_addresses == ["10.0.0.6"]

        # Verify details
        assert result[0].details["vmss_name"] == "vmss-web"
        assert result[0].details["vmss_id"] == vmss.id
        assert result[0].details["instance_id"] == "0"
        assert result[0].details["resource_group"] == "rg-prod"

    def test_vmss_with_zero_instances(self):
        """VMSS with 0 instances returns empty list."""
        compute_client = MagicMock()
        network_client = MagicMock()

        vmss = _make_vmss(
            name="vmss-empty",
            location="eastus",
            resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachineScaleSets/vmss-empty",
        )
        compute_client.virtual_machine_scale_sets.list_all.return_value = [vmss]
        compute_client.virtual_machine_scale_set_vms.list.return_value = []

        result = collect_azure_vmss_instances(compute_client, network_client, "sub1")

        assert result == []

    def test_vmss_no_scale_sets(self):
        """No VMSS in subscription returns empty list."""
        compute_client = MagicMock()
        network_client = MagicMock()
        compute_client.virtual_machine_scale_sets.list_all.return_value = []

        result = collect_azure_vmss_instances(compute_client, network_client, "sub1")

        assert result == []

    def test_vmss_instance_nic_failure_graceful(self):
        """NIC lookup failure for one instance doesn't block others."""
        compute_client = MagicMock()
        network_client = MagicMock()

        vmss = _make_vmss(
            name="vmss-partial",
            location="eastus",
            resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachineScaleSets/vmss-partial",
        )
        compute_client.virtual_machine_scale_sets.list_all.return_value = [vmss]

        compute_client.virtual_machine_scale_set_vms.list.return_value = [
            _make_vmss_instance("0", "vmss-partial_0", f"{vmss.id}/virtualMachines/0"),
            _make_vmss_instance("1", "vmss-partial_1", f"{vmss.id}/virtualMachines/1"),
        ]

        # Instance 0 fails, instance 1 succeeds
        def mock_list_vmss_nics(rg, vmss_name, instance_id):
            if instance_id == "0":
                raise RuntimeError("NIC lookup failed")
            return [_make_vmss_nic([{"private_ip": "10.0.0.5"}])]

        network_client.network_interfaces.list_virtual_machine_scale_set_vm_network_interfaces.side_effect = mock_list_vmss_nics

        result = collect_azure_vmss_instances(compute_client, network_client, "sub1")

        assert len(result) == 2
        # Instance 0 has no IPs due to failure
        assert result[0].ip_addresses == []
        # Instance 1 has IP
        assert result[1].ip_addresses == ["10.0.0.5"]

    def test_vmss_instance_multiple_nics(self):
        """VMSS instance with multiple NICs gets all private IPs."""
        compute_client = MagicMock()
        network_client = MagicMock()

        vmss = _make_vmss(
            name="vmss-multi",
            location="eastus",
            resource_id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachineScaleSets/vmss-multi",
        )
        compute_client.virtual_machine_scale_sets.list_all.return_value = [vmss]

        compute_client.virtual_machine_scale_set_vms.list.return_value = [
            _make_vmss_instance("0", "vmss-multi_0", f"{vmss.id}/virtualMachines/0"),
        ]

        # 2 NICs with different IPs
        network_client.network_interfaces.list_virtual_machine_scale_set_vm_network_interfaces.return_value = [
            _make_vmss_nic([{"private_ip": "10.0.0.4"}]),
            _make_vmss_nic([{"private_ip": "10.0.1.4"}]),
        ]

        result = collect_azure_vmss_instances(compute_client, network_client, "sub1")

        assert len(result) == 1
        assert result[0].ip_addresses == ["10.0.0.4", "10.0.1.4"]
