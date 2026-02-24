"""Tests for Azure token-free resource collectors.

Validates that each token-free collector returns correctly-shaped CloudResource
instances with ip_addresses=[] and the correct resource_type.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.providers.azure.collectors.token_free import (
    collect_azure_disks,
    collect_azure_management_groups,
    collect_azure_network_watchers,
    collect_azure_nsgs,
    collect_azure_resource_groups,
    collect_azure_storage_accounts,
    collect_azure_storage_containers,
    collect_azure_traffic_manager_profiles,
)

SUB_ID = "00000000-0000-0000-0000-000000000001"


def _make_disk():
    """Create a mock Azure Disk object."""
    disk = MagicMock()
    disk.id = f"/subscriptions/{SUB_ID}/resourceGroups/rg1/providers/Microsoft.Compute/disks/disk1"
    disk.location = "eastus"
    disk.name = "disk1"
    disk.tags = {"env": "test"}
    disk.disk_size_gb = 128
    disk.os_type = "Linux"
    disk.provisioning_state = "Succeeded"
    return disk


def _make_storage_account():
    """Create a mock Azure Storage Account object."""
    account = MagicMock()
    account.id = f"/subscriptions/{SUB_ID}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/stor1"
    account.location = "westus"
    account.name = "stor1"
    account.tags = {}
    account.kind = "StorageV2"
    account.sku = MagicMock()
    account.sku.name = "Standard_LRS"
    account.access_tier = "Hot"
    return account


def _make_blob_container(name="container1"):
    """Create a mock Azure Blob Container object."""
    container = MagicMock()
    container.id = (
        f"/subscriptions/{SUB_ID}/resourceGroups/rg1"
        f"/providers/Microsoft.Storage/storageAccounts/stor1"
        f"/blobServices/default/containers/{name}"
    )
    container.name = name
    return container


def _make_management_group():
    """Create a mock Azure Management Group object."""
    group = MagicMock()
    group.id = "/providers/Microsoft.Management/managementGroups/mg1"
    group.name = "mg1"
    group.properties = MagicMock()
    group.properties.display_name = "Management Group 1"
    group.properties.tenant_id = "tenant-123"
    return group


def _make_traffic_manager_profile():
    """Create a mock Azure Traffic Manager Profile object."""
    profile = MagicMock()
    profile.id = f"/subscriptions/{SUB_ID}/resourceGroups/rg1/providers/Microsoft.Network/trafficManagerProfiles/tm1"
    profile.name = "tm1"
    profile.location = "global"
    profile.tags = {"team": "infra"}
    profile.dns_config = MagicMock()
    profile.dns_config.relative_name = "tm1"
    profile.traffic_routing_method = "Performance"
    return profile


def _make_network_watcher():
    """Create a mock Azure Network Watcher object."""
    watcher = MagicMock()
    watcher.id = f"/subscriptions/{SUB_ID}/resourceGroups/rg1/providers/Microsoft.Network/networkWatchers/nw1"
    watcher.location = "eastus"
    watcher.name = "nw1"
    watcher.tags = {}
    watcher.provisioning_state = "Succeeded"
    return watcher


def _make_nsg():
    """Create a mock Azure NSG object."""
    nsg = MagicMock()
    nsg.id = f"/subscriptions/{SUB_ID}/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1"
    nsg.location = "eastus"
    nsg.name = "nsg1"
    nsg.tags = {}
    nsg.security_rules = [MagicMock(), MagicMock()]
    nsg.default_security_rules = [MagicMock()]
    return nsg


def _make_resource_group():
    """Create a mock Azure Resource Group object."""
    rg = MagicMock()
    rg.id = f"/subscriptions/{SUB_ID}/resourceGroups/rg1"
    rg.location = "eastus"
    rg.name = "rg1"
    rg.tags = {"purpose": "testing"}
    rg.properties = MagicMock()
    rg.properties.provisioning_state = "Succeeded"
    return rg


class TestCollectAzureDisks:
    """Tests for collect_azure_disks."""

    def test_returns_correct_resource_type(self):
        compute_client = MagicMock()
        compute_client.disks.list.return_value = [_make_disk()]

        resources = collect_azure_disks(compute_client, SUB_ID)

        assert len(resources) == 1
        assert resources[0].resource_type == "azure-disk"

    def test_ip_addresses_empty(self):
        compute_client = MagicMock()
        compute_client.disks.list.return_value = [_make_disk()]

        resources = collect_azure_disks(compute_client, SUB_ID)

        assert resources[0].ip_addresses == []

    def test_details_populated(self):
        compute_client = MagicMock()
        compute_client.disks.list.return_value = [_make_disk()]

        resources = collect_azure_disks(compute_client, SUB_ID)

        assert resources[0].details["resource_group"] == "rg1"
        assert resources[0].details["disk_size_gb"] == 128
        assert resources[0].details["provisioning_state"] == "Succeeded"

    def test_provider_and_account(self):
        compute_client = MagicMock()
        compute_client.disks.list.return_value = [_make_disk()]

        resources = collect_azure_disks(compute_client, SUB_ID)

        assert resources[0].provider == "azure"
        assert resources[0].account_id == SUB_ID

    def test_empty_list(self):
        compute_client = MagicMock()
        compute_client.disks.list.return_value = []

        resources = collect_azure_disks(compute_client, SUB_ID)

        assert resources == []


class TestCollectAzureStorageAccounts:
    """Tests for collect_azure_storage_accounts."""

    def test_returns_correct_resource_type(self):
        storage_client = MagicMock()
        storage_client.storage_accounts.list.return_value = [_make_storage_account()]

        resources = collect_azure_storage_accounts(storage_client, SUB_ID)

        assert len(resources) == 1
        assert resources[0].resource_type == "azure-storage-account"

    def test_ip_addresses_empty(self):
        storage_client = MagicMock()
        storage_client.storage_accounts.list.return_value = [_make_storage_account()]

        resources = collect_azure_storage_accounts(storage_client, SUB_ID)

        assert resources[0].ip_addresses == []

    def test_details_populated(self):
        storage_client = MagicMock()
        storage_client.storage_accounts.list.return_value = [_make_storage_account()]

        resources = collect_azure_storage_accounts(storage_client, SUB_ID)

        assert resources[0].details["kind"] == "StorageV2"
        assert resources[0].details["sku_name"] == "Standard_LRS"


class TestCollectAzureStorageContainers:
    """Tests for collect_azure_storage_containers."""

    def test_returns_correct_resource_type(self):
        storage_client = MagicMock()
        acct = _make_storage_account()
        storage_client.storage_accounts.list.return_value = [acct]
        storage_client.blob_containers.list.return_value = [_make_blob_container()]

        resources = collect_azure_storage_containers(storage_client, SUB_ID)

        assert len(resources) == 1
        assert resources[0].resource_type == "azure-storage-container"

    def test_ip_addresses_empty(self):
        storage_client = MagicMock()
        acct = _make_storage_account()
        storage_client.storage_accounts.list.return_value = [acct]
        storage_client.blob_containers.list.return_value = [_make_blob_container()]

        resources = collect_azure_storage_containers(storage_client, SUB_ID)

        assert resources[0].ip_addresses == []

    def test_per_account_error_isolation(self):
        """If listing containers fails for one account, others succeed."""
        storage_client = MagicMock()
        acct1 = _make_storage_account()
        acct1.name = "fail-account"
        acct2 = _make_storage_account()
        acct2.name = "ok-account"
        storage_client.storage_accounts.list.return_value = [acct1, acct2]

        def side_effect(rg, name):
            if name == "fail-account":
                raise Exception("Blob access disabled")
            return [_make_blob_container("c1")]

        storage_client.blob_containers.list.side_effect = side_effect

        resources = collect_azure_storage_containers(storage_client, SUB_ID)

        assert len(resources) == 1
        assert resources[0].details["storage_account_name"] == "ok-account"

    def test_details_populated(self):
        storage_client = MagicMock()
        acct = _make_storage_account()
        storage_client.storage_accounts.list.return_value = [acct]
        storage_client.blob_containers.list.return_value = [_make_blob_container()]

        resources = collect_azure_storage_containers(storage_client, SUB_ID)

        assert resources[0].details["resource_group"] == "rg1"
        assert resources[0].details["storage_account_name"] == "stor1"


class TestCollectAzureManagementGroups:
    """Tests for collect_azure_management_groups."""

    def test_returns_correct_resource_type(self):
        mgmt_client = MagicMock()
        mgmt_client.management_groups.list.return_value = [_make_management_group()]

        resources = collect_azure_management_groups(mgmt_client, SUB_ID)

        assert len(resources) == 1
        assert resources[0].resource_type == "azure-management-group"

    def test_region_is_global(self):
        mgmt_client = MagicMock()
        mgmt_client.management_groups.list.return_value = [_make_management_group()]

        resources = collect_azure_management_groups(mgmt_client, SUB_ID)

        assert resources[0].region == "global"

    def test_ip_addresses_empty(self):
        mgmt_client = MagicMock()
        mgmt_client.management_groups.list.return_value = [_make_management_group()]

        resources = collect_azure_management_groups(mgmt_client, SUB_ID)

        assert resources[0].ip_addresses == []

    def test_attributed_to_subscription(self):
        mgmt_client = MagicMock()
        mgmt_client.management_groups.list.return_value = [_make_management_group()]

        resources = collect_azure_management_groups(mgmt_client, SUB_ID)

        assert resources[0].account_id == SUB_ID


class TestCollectAzureTrafficManagerProfiles:
    """Tests for collect_azure_traffic_manager_profiles."""

    def test_returns_correct_resource_type(self):
        tm_client = MagicMock()
        tm_client.profiles.list_by_subscription.return_value = [_make_traffic_manager_profile()]

        resources = collect_azure_traffic_manager_profiles(tm_client, SUB_ID)

        assert len(resources) == 1
        assert resources[0].resource_type == "azure-traffic-manager"

    def test_ip_addresses_empty(self):
        tm_client = MagicMock()
        tm_client.profiles.list_by_subscription.return_value = [_make_traffic_manager_profile()]

        resources = collect_azure_traffic_manager_profiles(tm_client, SUB_ID)

        assert resources[0].ip_addresses == []

    def test_details_populated(self):
        tm_client = MagicMock()
        tm_client.profiles.list_by_subscription.return_value = [_make_traffic_manager_profile()]

        resources = collect_azure_traffic_manager_profiles(tm_client, SUB_ID)

        assert resources[0].details["traffic_routing_method"] == "Performance"


class TestCollectAzureNetworkWatchers:
    """Tests for collect_azure_network_watchers."""

    def test_returns_correct_resource_type(self):
        network_client = MagicMock()
        network_client.network_watchers.list_all.return_value = [_make_network_watcher()]

        resources = collect_azure_network_watchers(network_client, SUB_ID)

        assert len(resources) == 1
        assert resources[0].resource_type == "azure-network-watcher"

    def test_ip_addresses_empty(self):
        network_client = MagicMock()
        network_client.network_watchers.list_all.return_value = [_make_network_watcher()]

        resources = collect_azure_network_watchers(network_client, SUB_ID)

        assert resources[0].ip_addresses == []


class TestCollectAzureNSGs:
    """Tests for collect_azure_nsgs."""

    def test_returns_correct_resource_type(self):
        network_client = MagicMock()
        network_client.network_security_groups.list_all.return_value = [_make_nsg()]

        resources = collect_azure_nsgs(network_client, SUB_ID)

        assert len(resources) == 1
        assert resources[0].resource_type == "azure-nsg"

    def test_ip_addresses_empty(self):
        network_client = MagicMock()
        network_client.network_security_groups.list_all.return_value = [_make_nsg()]

        resources = collect_azure_nsgs(network_client, SUB_ID)

        assert resources[0].ip_addresses == []

    def test_rule_count(self):
        network_client = MagicMock()
        network_client.network_security_groups.list_all.return_value = [_make_nsg()]

        resources = collect_azure_nsgs(network_client, SUB_ID)

        # 2 security_rules + 1 default = 3
        assert resources[0].details["rule_count"] == 3


class TestCollectAzureResourceGroups:
    """Tests for collect_azure_resource_groups."""

    def test_returns_correct_resource_type(self):
        resource_client = MagicMock()
        resource_client.resource_groups.list.return_value = [_make_resource_group()]

        resources = collect_azure_resource_groups(resource_client, SUB_ID)

        assert len(resources) == 1
        assert resources[0].resource_type == "azure-resource-group"

    def test_ip_addresses_empty(self):
        resource_client = MagicMock()
        resource_client.resource_groups.list.return_value = [_make_resource_group()]

        resources = collect_azure_resource_groups(resource_client, SUB_ID)

        assert resources[0].ip_addresses == []

    def test_provider_and_account(self):
        resource_client = MagicMock()
        resource_client.resource_groups.list.return_value = [_make_resource_group()]

        resources = collect_azure_resource_groups(resource_client, SUB_ID)

        assert resources[0].provider == "azure"
        assert resources[0].account_id == SUB_ID

    def test_details_populated(self):
        resource_client = MagicMock()
        resource_client.resource_groups.list.return_value = [_make_resource_group()]

        resources = collect_azure_resource_groups(resource_client, SUB_ID)

        assert resources[0].details["provisioning_state"] == "Succeeded"
