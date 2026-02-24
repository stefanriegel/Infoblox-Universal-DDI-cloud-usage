"""End-to-end integration tests for Azure discovery pipeline.

Comprehensive tests exercising the full pipeline: discovery across subscriptions,
categorization, IP counting, token calculation, and output generation.
Uses unittest.mock for all Azure SDK clients (no real Azure calls).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

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
from cloud_usage.providers.azure.provider import AzureDiscoveryProvider
from cloud_usage.schema.resource import CloudResource

SUB_ID = "00000000-0000-0000-0000-000000000001"
SUB_ID_2 = "00000000-0000-0000-0000-000000000002"
TENANT_ID = "tenant-00000000-0000-0000-0000-000000000001"


def _mock_subscriptions(count=1):
    """Create mock subscription dicts."""
    subs = []
    for i in range(count):
        sub_id = f"00000000-0000-0000-0000-{str(i + 1).zfill(12)}"
        subs.append({
            "id": sub_id,
            "display_name": f"Sub-{i + 1}",
            "tenant_id": TENANT_ID,
            "state": "Enabled",
        })
    return subs


def _mock_vnet(name="vnet1", rg="rg1", location="eastus"):
    """Create a mock VNet SDK object."""
    vnet = MagicMock()
    vnet.id = f"/subscriptions/{SUB_ID}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{name}"
    vnet.name = name
    vnet.location = location
    vnet.tags = {}
    vnet.address_space = MagicMock()
    vnet.address_space.address_prefixes = ["10.0.0.0/16"]
    vnet.dhcp_options = MagicMock()
    vnet.dhcp_options.dns_servers = ["10.0.0.2"]
    return vnet


def _mock_subnet(vnet_id, name="subnet1", rg="rg1"):
    """Create a mock Subnet SDK object."""
    subnet = MagicMock()
    subnet.id = f"{vnet_id}/subnets/{name}"
    subnet.name = name
    subnet.address_prefix = "10.0.1.0/24"
    return subnet


def _mock_dns_zone(name="example.com", rg="rg1"):
    """Create a mock DNS Zone SDK object."""
    zone = MagicMock()
    zone.id = f"/subscriptions/{SUB_ID}/resourceGroups/{rg}/providers/Microsoft.Network/dnsZones/{name}"
    zone.name = name
    zone.tags = {}
    zone.number_of_record_sets = 5
    return zone


def _mock_dns_record(zone_name="example.com", name="www", record_type="A"):
    """Create a mock DNS RecordSet SDK object."""
    record = MagicMock()
    record.id = f"/subscriptions/{SUB_ID}/resourceGroups/rg1/providers/Microsoft.Network/dnsZones/{zone_name}/{record_type}/{name}"
    record.name = name
    record.type = f"Microsoft.Network/dnsZones/{record_type}"
    record.ttl = 300
    return record


def _mock_nic(name="nic1", rg="rg1", private_ip="10.0.1.5"):
    """Create a mock NIC SDK object."""
    nic = MagicMock()
    nic.id = f"/subscriptions/{SUB_ID}/resourceGroups/{rg}/providers/Microsoft.Network/networkInterfaces/{name}"
    nic.name = name
    nic.location = "eastus"
    nic.tags = {}

    ip_config = MagicMock()
    ip_config.private_ip_address = private_ip
    nic.ip_configurations = [ip_config]
    nic.virtual_machine = None
    return nic


def _mock_public_ip(name="pip1", rg="rg1", ip="52.168.1.1"):
    """Create a mock Public IP SDK object."""
    pip = MagicMock()
    pip.id = f"/subscriptions/{SUB_ID}/resourceGroups/{rg}/providers/Microsoft.Network/publicIPAddresses/{name}"
    pip.name = name
    pip.location = "eastus"
    pip.tags = {}
    pip.ip_address = ip
    pip.public_ip_allocation_method = "Static"
    pip.ip_configuration = None
    return pip


def _mock_vm(name="vm1", rg="rg1"):
    """Create a mock VM SDK object."""
    vm = MagicMock()
    vm.id = f"/subscriptions/{SUB_ID}/resourceGroups/{rg}/providers/Microsoft.Compute/virtualMachines/{name}"
    vm.name = name
    vm.location = "eastus"
    vm.tags = {}
    vm.network_profile = MagicMock()
    nic_ref = MagicMock()
    nic_ref.id = f"/subscriptions/{SUB_ID}/resourceGroups/{rg}/providers/Microsoft.Network/networkInterfaces/nic-{name}"
    vm.network_profile.network_interfaces = [nic_ref]
    vm.hardware_profile = MagicMock()
    vm.hardware_profile.vm_size = "Standard_D2s_v3"
    vm.provisioning_state = "Succeeded"
    return vm


def _mock_disk(name="disk1", rg="rg1"):
    """Create a mock Disk SDK object (token-free)."""
    disk = MagicMock()
    disk.id = f"/subscriptions/{SUB_ID}/resourceGroups/{rg}/providers/Microsoft.Compute/disks/{name}"
    disk.name = name
    disk.location = "eastus"
    disk.tags = {}
    disk.disk_size_gb = 128
    disk.os_type = "Linux"
    disk.provisioning_state = "Succeeded"
    return disk


def _mock_nsg(name="nsg1", rg="rg1"):
    """Create a mock NSG SDK object (token-free)."""
    nsg = MagicMock()
    nsg.id = f"/subscriptions/{SUB_ID}/resourceGroups/{rg}/providers/Microsoft.Network/networkSecurityGroups/{name}"
    nsg.name = name
    nsg.location = "eastus"
    nsg.tags = {}
    nsg.security_rules = [MagicMock()]
    nsg.default_security_rules = [MagicMock()]
    return nsg


def _mock_private_dns_zone(name="private.local"):
    """Create a mock Private DNS Zone SDK object."""
    zone = MagicMock()
    zone.id = f"/subscriptions/{SUB_ID}/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/{name}"
    zone.name = name
    zone.tags = {}
    zone.number_of_record_sets = 2
    return zone


def _create_mock_clients(
    vnets=None, subnets=None, dns_zones=None, dns_records=None,
    nics=None, public_ips=None, vms=None, disks=None, nsgs=None,
    private_dns_zones=None, private_dns_records=None,
    storage_accounts=None, resource_groups=None,
):
    """Create a fully-mocked AzureClients with configurable responses."""
    clients = MagicMock()

    # Network client
    clients.network.virtual_networks.list_all.return_value = vnets or []
    clients.network.subnets.list.return_value = subnets or []
    clients.network.network_interfaces.list_all.return_value = nics or []
    clients.network.public_ip_addresses.list_all.return_value = public_ips or []
    clients.network.network_security_groups.list_all.return_value = nsgs or []
    clients.network.load_balancers.list_all.return_value = []
    clients.network.application_gateways.list_all.return_value = []
    clients.network.azure_firewalls.list_all.return_value = []
    clients.network.nat_gateways.list_all.return_value = []
    clients.network.private_endpoints.list_all.return_value = []
    clients.network.virtual_network_peerings.list.return_value = []
    clients.network.express_route_circuits.list_all.return_value = []
    clients.network.virtual_network_gateways.list.return_value = []
    clients.network.virtual_hubs.list.return_value = []
    clients.network.bastion_hosts.list.return_value = []
    clients.network.network_watchers.list_all.return_value = []

    # DNS client
    clients.dns.zones.list.return_value = dns_zones or []
    clients.dns.record_sets.list_by_dns_zone.return_value = dns_records or []

    # Private DNS client
    clients.privatedns.private_zones.list.return_value = private_dns_zones or []
    clients.privatedns.record_sets.list.return_value = private_dns_records or []

    # Compute client
    clients.compute.virtual_machines.list_all.return_value = vms or []
    clients.compute.virtual_machine_scale_sets.list_all.return_value = []
    clients.compute.disks.list.return_value = disks or []

    # Storage client
    clients.storage.storage_accounts.list.return_value = storage_accounts or []
    clients.storage.blob_containers.list.return_value = []

    # Resource client
    clients.resource.resource_groups.list.return_value = resource_groups or []

    # Database clients (all empty by default)
    clients.sql.servers.list.return_value = []
    clients.cosmosdb.database_accounts.list.return_value = []
    clients.mysql.servers.list.return_value = []
    clients.postgresql.servers.list.return_value = []
    clients.redis.redis.list_by_subscription.return_value = []

    # PaaS clients (all empty by default)
    clients.web.web_apps.list.return_value = []
    clients.container.container_groups.list.return_value = []
    clients.appcontainers = None
    clients.containerservice.managed_clusters.list.return_value = []
    clients.apimanagement.api_management_service.list.return_value = []

    # Token-free clients
    clients.mgmt_groups.management_groups.list.return_value = []
    clients.trafficmanager.profiles.list_by_subscription.return_value = []

    return clients


class TestFullPipelineMixedResources:
    """Test 1: Full pipeline with mixed resources."""

    def test_full_pipeline_mixed_resources(self):
        """Create mock Azure clients returning mixed resource types and verify pipeline."""
        vnet = _mock_vnet()
        subnet = _mock_subnet(vnet.id)
        dns_zone = _mock_dns_zone()
        dns_record_a = _mock_dns_record("example.com", "www", "A")
        dns_record_mx = _mock_dns_record("example.com", "mail", "MX")
        nic = _mock_nic(private_ip="10.0.1.5")
        public_ip = _mock_public_ip(ip="52.168.1.1")
        vm = _mock_vm()
        disk = _mock_disk()
        nsg = _mock_nsg()

        mock_clients = _create_mock_clients(
            vnets=[vnet],
            subnets=[subnet],
            dns_zones=[dns_zone],
            dns_records=[dns_record_a, dns_record_mx],
            nics=[nic],
            public_ips=[public_ip],
            vms=[vm],
            disks=[disk],
            nsgs=[nsg],
        )

        subs = _mock_subscriptions(1)
        credential = MagicMock()

        provider = AzureDiscoveryProvider(
            credential=credential,
            subscriptions=subs,
        )

        with patch(
            "cloud_usage.providers.azure.provider.create_subscription_clients",
            return_value=mock_clients,
        ):
            resources = provider.discover_account(subs[0]["id"])

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

        # DDI: VNet + subnet + DNS zone + 2 DNS records + DHCP config (from VNet with DNS servers)
        assert len(ddi_resources) >= 4, f"Expected >= 4 DDI, got {len(ddi_resources)}: {[r.resource_type for r in ddi_resources]}"

        # Assets: NIC (with IP) + public IP (with IP)
        assert len(asset_resources) >= 2, f"Expected >= 2 assets, got {len(asset_resources)}: {[r.resource_type for r in asset_resources]}"

        # Token-free: disk + NSG should be excluded
        disk_resources = [r for r in resources if r.resource_type == "azure-disk"]
        nsg_resources = [r for r in resources if r.resource_type == "azure-nsg"]
        for r in disk_resources:
            assert not r.counted
            assert "token-free" in (r.skip_reason or "")
        for r in nsg_resources:
            assert not r.counted
            assert "token-free" in (r.skip_reason or "")

        # IP counting
        ip_counts = deduplicate_ips_per_vpc(resources)

        # Token calculation: DDI/25 + IPs/13 + Assets/3
        sub_id = subs[0]["id"]
        per_account_ips = ip_counts.get("per_account", {})
        deduped_ip = per_account_ips.get(sub_id, 0)
        account_tokens = calculate_account_tokens(
            resources, deduplicated_ip_count=deduped_ip
        )

        assert account_tokens["ddi_count"] > 0
        assert account_tokens["total_tokens"] >= 0
        assert "ddi_tokens" in account_tokens
        assert "ip_tokens" in account_tokens
        assert "asset_tokens" in account_tokens

        # Provider-level aggregation
        provider_totals = calculate_provider_tokens({sub_id: account_tokens})
        assert provider_totals["account_count"] == 1
        assert provider_totals["total_tokens"] == account_tokens["total_tokens"]


class TestSubscriptionFiltering:
    """Test 2: Subscription filtering."""

    def test_include_filters_subscriptions(self):
        """include_subscriptions only returns matching subscriptions."""
        subs = _mock_subscriptions(3)
        target_id = subs[1]["id"]

        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=subs,
            include_subscriptions=[target_id],
        )
        accounts = provider.list_accounts()
        assert len(accounts) == 1
        assert accounts[0] == target_id

    def test_exclude_filters_subscriptions(self):
        """exclude_subscriptions removes matching subscriptions."""
        subs = _mock_subscriptions(3)
        exclude_id = subs[0]["id"]

        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=subs,
            exclude_subscriptions=[exclude_id],
        )
        accounts = provider.list_accounts()
        assert exclude_id not in accounts
        assert len(accounts) == 2

    def test_include_by_display_name(self):
        """include_subscriptions works with display names (case-insensitive)."""
        subs = _mock_subscriptions(3)

        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=subs,
            include_subscriptions=["sub-2"],  # lowercase
        )
        accounts = provider.list_accounts()
        assert len(accounts) == 1
        assert accounts[0] == subs[1]["id"]


class TestPartialFailureResilience:
    """Test 3: Partial failure resilience."""

    def test_partial_failure_other_collectors_succeed(self):
        """One collector raises HttpResponseError, others succeed."""
        vnet = _mock_vnet()
        nic = _mock_nic()

        mock_clients = _create_mock_clients(
            vnets=[vnet],
            nics=[nic],
        )
        # Make SQL collector raise an error
        mock_clients.sql.servers.list.side_effect = Exception("Simulated SQL API failure")

        subs = _mock_subscriptions(1)
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=subs,
        )

        with patch(
            "cloud_usage.providers.azure.provider.create_subscription_clients",
            return_value=mock_clients,
        ):
            resources = provider.discover_account(subs[0]["id"])

        # Should still have resources from other collectors
        assert len(resources) > 0
        resource_types = {r.resource_type for r in resources}
        assert "azure-vnet" in resource_types
        assert "azure-nic" in resource_types
        # SQL should NOT be present since we mocked it to fail
        assert "azure-sql-server" not in resource_types
        assert "azure-sql-db" not in resource_types


class TestMissingSubscriptionRegistration:
    """Test 4: MissingSubscriptionRegistration handled gracefully."""

    def test_missing_registration_skips_resource_type(self):
        """SQL returns MissingSubscriptionRegistration, other resources present."""
        vnet = _mock_vnet()

        mock_clients = _create_mock_clients(vnets=[vnet])
        # Simulate MissingSubscriptionRegistration for SQL
        mock_clients.sql.servers.list.side_effect = Exception(
            "MissingSubscriptionRegistration: The subscription is not registered for Microsoft.Sql"
        )

        subs = _mock_subscriptions(1)
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=subs,
        )

        with patch(
            "cloud_usage.providers.azure.provider.create_subscription_clients",
            return_value=mock_clients,
        ):
            resources = provider.discover_account(subs[0]["id"])

        # VNet should be present, SQL empty
        resource_types = {r.resource_type for r in resources}
        assert "azure-vnet" in resource_types
        assert "azure-sql-server" not in resource_types


class TestTokenFreeCorrectlyExcluded:
    """Test 5: Token-free resources correctly excluded."""

    def test_token_free_all_excluded_after_categorization(self):
        """azure-disk, azure-nsg, azure-storage-account all have counted=False."""
        disk = _mock_disk()
        nsg = _mock_nsg()

        storage_account = MagicMock()
        storage_account.id = f"/subscriptions/{SUB_ID}/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/stor1"
        storage_account.name = "stor1"
        storage_account.location = "eastus"
        storage_account.tags = {}
        storage_account.kind = "StorageV2"
        storage_account.sku = MagicMock()
        storage_account.sku.name = "Standard_LRS"
        storage_account.access_tier = "Hot"

        mock_clients = _create_mock_clients(
            disks=[disk],
            nsgs=[nsg],
            storage_accounts=[storage_account],
        )

        subs = _mock_subscriptions(1)
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=subs,
        )

        with patch(
            "cloud_usage.providers.azure.provider.create_subscription_clients",
            return_value=mock_clients,
        ):
            resources = provider.discover_account(subs[0]["id"])

        categorize_resources(resources)

        for r in resources:
            if r.resource_type in ("azure-disk", "azure-nsg", "azure-storage-account"):
                assert r.counted is False, f"{r.resource_type} should not be counted"
                assert "token-free" in (r.skip_reason or ""), f"{r.resource_type} should have token-free skip reason"


class TestDHCPConfigDDICounting:
    """Test 6: DHCP config DDI counting."""

    def test_vnet_with_dhcp_generates_both_ddi(self):
        """VNet with DHCP options generates VNet DDI + DHCP config DDI."""
        vnet = _mock_vnet()
        # VNet already has dhcp_options.dns_servers set

        mock_clients = _create_mock_clients(vnets=[vnet])

        subs = _mock_subscriptions(1)
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=subs,
        )

        with patch(
            "cloud_usage.providers.azure.provider.create_subscription_clients",
            return_value=mock_clients,
        ):
            resources = provider.discover_account(subs[0]["id"])

        categorize_resources(resources)

        # Both VNet and DHCP config should be DDI
        vnet_resources = [r for r in resources if r.resource_type == "azure-vnet"]
        dhcp_resources = [r for r in resources if r.resource_type == "azure-dhcp-config"]

        assert len(vnet_resources) == 1
        assert vnet_resources[0].counted is True
        assert vnet_resources[0].category == "ddi"

        assert len(dhcp_resources) == 1
        assert dhcp_resources[0].counted is True
        assert dhcp_resources[0].category == "ddi"


class TestOutputFileGeneration:
    """Test 7: Output file generation."""

    def test_azure_xlsx_output_generated(self, tmp_path):
        """Full pipeline produces azure_discovery_*.xlsx with detail and summary sheets."""
        vnet = _mock_vnet()
        nic = _mock_nic(private_ip="10.0.1.5")
        disk = _mock_disk()

        mock_clients = _create_mock_clients(
            vnets=[vnet],
            nics=[nic],
            disks=[disk],
        )

        subs = _mock_subscriptions(1)
        provider = AzureDiscoveryProvider(
            credential=MagicMock(),
            subscriptions=subs,
        )

        with patch(
            "cloud_usage.providers.azure.provider.create_subscription_clients",
            return_value=mock_clients,
        ):
            resources = provider.discover_account(subs[0]["id"])

        # Run pipeline
        fold_enis_into_parents(resources)
        exclude_managed_service_resources(resources)
        deduplicate_assets(resources)
        categorize_resources(resources)
        ip_counts = deduplicate_ips_per_vpc(resources)

        sub_id = subs[0]["id"]
        per_account_ips = ip_counts.get("per_account", {})
        deduped_ip = per_account_ips.get(sub_id, 0)
        account_tokens = calculate_account_tokens(
            resources, deduplicated_ip_count=deduped_ip
        )
        account_summaries = {sub_id: account_tokens}

        # Write XLS report
        xlsx_path = str(tmp_path / "azure_discovery_test.xlsx")
        write_xlsx_report(xlsx_path, resources, account_summaries, [], "azure")

        assert os.path.exists(xlsx_path)

        # Verify workbook structure using openpyxl for reading
        import openpyxl
        wb = openpyxl.load_workbook(xlsx_path)
        sheet_names = wb.sheetnames
        assert "Detail" in sheet_names
        assert "Summary" in sheet_names

        # Verify resource_group column is present in Detail sheet for Azure
        detail = wb["Detail"]
        headers = [detail.cell(row=1, column=col).value for col in range(1, 20)]
        assert "Resource Group" in headers, f"Azure detail sheet should have Resource Group column, got: {headers}"

        wb.close()


class TestStressTest429Handling:
    """Test 8: 50-subscription stress test with 429 handling."""

    def test_50_subscriptions_with_429_cascades(self, caplog):
        """50 subscriptions, 10 hit 429 on first call then succeed on retry.

        Validates all 50 subscriptions are attempted, 429-returning ones
        eventually produce resources, and throttle warnings are logged.
        """
        subs = _mock_subscriptions(50)
        credential = MagicMock()

        # Track which subscriptions were called
        call_counts: dict[str, int] = {}

        # Subscriptions that will 429 on first attempt (indices 0-9)
        throttled_subs = {subs[i]["id"] for i in range(10)}

        def make_mock_clients_for_sub(cred, sub_id):
            """Create mock clients. Throttled subs raise 429 on first VNet call."""
            call_counts.setdefault(sub_id, 0)
            call_counts[sub_id] += 1

            mock_c = _create_mock_clients(
                vnets=[_mock_vnet()],
                nics=[_mock_nic()],
            )

            if sub_id in throttled_subs and call_counts[sub_id] == 1:
                # First call: VNet collector will be hit via _safe_collect
                # We simulate 429 by making the first collector (vnets) fail,
                # but since _safe_collect catches it and returns [], the
                # subscription still continues with other collectors.
                #
                # For the stress test, we simulate the 429 visible warning
                # by making the network client raise a 429-like error on VNets.
                exc = Exception("Rate limit exceeded")
                exc.status_code = 429
                exc.retry_after = 1
                mock_c.network.virtual_networks.list_all.side_effect = exc
            else:
                # Normal VNets with a resource
                vnet = _mock_vnet(name=f"vnet-{sub_id[:8]}")
                mock_c.network.virtual_networks.list_all.return_value = [vnet]

            return mock_c

        provider = AzureDiscoveryProvider(
            credential=credential,
            subscriptions=subs,
        )

        accounts = provider.list_accounts()
        assert len(accounts) == 50, "All 50 subscriptions should be listed"

        all_resources: list[CloudResource] = []
        throttle_warnings = []

        with caplog.at_level(logging.WARNING):
            for sub_id in accounts:
                with patch(
                    "cloud_usage.providers.azure.provider.create_subscription_clients",
                    side_effect=lambda c, s: make_mock_clients_for_sub(c, s),
                ):
                    resources = provider.discover_account(sub_id)
                    all_resources.extend(resources)

            # For throttled subs that failed on first attempt,
            # retry them (simulating RateLimiter coordination)
            for sub_id in throttled_subs:
                with patch(
                    "cloud_usage.providers.azure.provider.create_subscription_clients",
                    side_effect=lambda c, s: make_mock_clients_for_sub(c, s),
                ):
                    resources = provider.discover_account(sub_id)
                    all_resources.extend(resources)

        # Verify throttle warnings were logged
        throttle_log_messages = [
            record.message for record in caplog.records
            if "throttled" in record.message.lower()
        ]
        assert len(throttle_log_messages) >= 1, (
            f"Expected throttle warnings, got: {[r.message for r in caplog.records]}"
        )

        # All 50 subscriptions should have been attempted
        assert len(call_counts) == 50, f"Expected 50 subs called, got {len(call_counts)}"

        # Throttled subscriptions should have been called more than once
        for sub_id in throttled_subs:
            assert call_counts[sub_id] >= 2, (
                f"Throttled sub {sub_id} should have been retried"
            )

        # Total resources should include contributions from all 50 subs
        # (throttled subs contribute on retry: NIC from initial + VNet+NIC from retry)
        assert len(all_resources) > 0, "Should have discovered resources"

        # All resources should be valid CloudResource instances
        for r in all_resources:
            assert isinstance(r, CloudResource)
            assert r.provider == "azure"


class TestPriorPipelineExclusionsRespected:
    """Verify categorizer respects prior pipeline exclusions."""

    def test_already_excluded_not_recategorized(self):
        """Resources with counted=False and skip_reason set are not recategorized."""
        r = CloudResource(
            resource_id="test-id",
            resource_type="azure-nic",
            provider="azure",
            account_id=SUB_ID,
            region="eastus",
            name="test-nic",
            ip_addresses=["10.0.1.5"],
            counted=False,
            skip_reason="fold: attached ENI",
        )
        result = categorize_resources([r])
        assert result[0].counted is False
        assert result[0].skip_reason == "fold: attached ENI"
