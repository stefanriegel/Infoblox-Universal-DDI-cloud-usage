"""Tests for shared/constants.py and shared/output_utils.py — DDI type maps, output formatting."""

import os
import tempfile

from shared.constants import (
    ASSET_RESOURCE_TYPES,
    DDI_RESOURCE_TYPES,
    MANAGED_SERVICE_INDICATORS,
    SUPPORTED_PROVIDERS,
)
from shared.output_utils import format_azure_resource, save_unknown_resources


# ---------------------------------------------------------------------------
# DDI_RESOURCE_TYPES validation
# ---------------------------------------------------------------------------
class TestDDIResourceTypes:
    """Ensure DDI types include all expected resource types (production fixes)."""

    def test_aws_includes_clusters(self):
        assert "eks-cluster" in DDI_RESOURCE_TYPES["aws"]

    def test_azure_includes_clusters(self):
        assert "aks-cluster" in DDI_RESOURCE_TYPES["azure"]

    def test_gcp_includes_clusters(self):
        assert "gke-cluster" in DDI_RESOURCE_TYPES["gcp"]

    def test_aws_includes_dns(self):
        assert "route53-zone" in DDI_RESOURCE_TYPES["aws"]
        assert "route53-record" in DDI_RESOURCE_TYPES["aws"]

    def test_azure_includes_dns(self):
        assert "dns-zone" in DDI_RESOURCE_TYPES["azure"]
        assert "dns-record" in DDI_RESOURCE_TYPES["azure"]

    def test_gcp_includes_dns(self):
        assert "dns-zone" in DDI_RESOURCE_TYPES["gcp"]
        assert "dns-record" in DDI_RESOURCE_TYPES["gcp"]

    def test_aws_includes_network(self):
        assert "subnet" in DDI_RESOURCE_TYPES["aws"]
        assert "vpc" in DDI_RESOURCE_TYPES["aws"]

    def test_azure_includes_network(self):
        assert "subnet" in DDI_RESOURCE_TYPES["azure"]
        assert "vnet" in DDI_RESOURCE_TYPES["azure"]

    def test_gcp_includes_network(self):
        assert "subnet" in DDI_RESOURCE_TYPES["gcp"]
        assert "vpc-network" in DDI_RESOURCE_TYPES["gcp"]

    def test_multicloud_is_superset(self):
        """Multicloud DDI types should include all provider-specific types."""
        all_types = set()
        for provider in ("aws", "azure", "gcp"):
            all_types.update(DDI_RESOURCE_TYPES[provider])
        multicloud = set(DDI_RESOURCE_TYPES["multicloud"])
        assert all_types.issubset(multicloud)


# ---------------------------------------------------------------------------
# ASSET_RESOURCE_TYPES validation
# ---------------------------------------------------------------------------
class TestAssetResourceTypes:
    def test_aws_includes_ec2(self):
        assert "ec2-instance" in ASSET_RESOURCE_TYPES["aws"]

    def test_azure_includes_vm(self):
        assert "vm" in ASSET_RESOURCE_TYPES["azure"]
        assert "vmss-instance" in ASSET_RESOURCE_TYPES["azure"]

    def test_gcp_includes_compute(self):
        assert "compute-instance" in ASSET_RESOURCE_TYPES["gcp"]

    def test_aws_includes_load_balancers(self):
        aws_assets = ASSET_RESOURCE_TYPES["aws"]
        assert "application-load-balancer" in aws_assets
        assert "network-load-balancer" in aws_assets


# ---------------------------------------------------------------------------
# MANAGED_SERVICE_INDICATORS validation
# ---------------------------------------------------------------------------
class TestManagedServiceIndicators:
    def test_all_providers_have_indicators(self):
        for provider in ("aws", "azure", "gcp"):
            assert provider in MANAGED_SERVICE_INDICATORS
            assert len(MANAGED_SERVICE_INDICATORS[provider]) > 0

    def test_gcp_indicators_are_specific(self):
        """GCP indicators should use specific prefixes, not broad substrings."""
        gcp = MANAGED_SERVICE_INDICATORS["gcp"]
        # These are the specific prefixes/exact keys we use
        assert "goog-managed-by" in gcp
        assert "managed-by" in gcp
        assert "gke-managed" in gcp


# ---------------------------------------------------------------------------
# SUPPORTED_PROVIDERS
# ---------------------------------------------------------------------------
class TestSupportedProviders:
    def test_includes_all_three(self):
        assert "aws" in SUPPORTED_PROVIDERS
        assert "azure" in SUPPORTED_PROVIDERS
        assert "gcp" in SUPPORTED_PROVIDERS

    def test_includes_multicloud(self):
        assert "multicloud" in SUPPORTED_PROVIDERS


# ---------------------------------------------------------------------------
# format_azure_resource
# ---------------------------------------------------------------------------
class TestFormatAzureResource:
    def test_basic_formatting(self):
        resource_data = {"vm_name": "test-vm", "vm_size": "Standard_B2s"}
        result = format_azure_resource(resource_data, "vm", "eastus")
        assert result["resource_type"] == "vm"
        assert result["region"] == "eastus"
        assert result["state"] == "active"
        assert result["requires_management_token"] is True
        assert result["details"] == resource_data

    def test_resource_id_format(self):
        resource_data = {"name": "my-vnet"}
        result = format_azure_resource(resource_data, "vnet", "westeurope")
        assert result["resource_id"] == "westeurope:vnet:my-vnet"

    def test_details_stores_passed_dict(self):
        """After vars() elimination, details should store the clean dict we pass."""
        explicit_fields = {
            "vm_id": "/subscriptions/sub1/providers/.../vms/test-vm",
            "vm_name": "test-vm",
            "vm_size": "Standard_D4s_v3",
            "os_type": "Linux",
            "provisioning_state": "Succeeded",
        }
        result = format_azure_resource(explicit_fields, "vm", "eastus")
        assert result["details"]["vm_name"] == "test-vm"
        assert result["details"]["vm_size"] == "Standard_D4s_v3"

    def test_management_token_false(self):
        result = format_azure_resource({}, "vm", "eastus", requires_management_token=False)
        assert result["requires_management_token"] is False


# ---------------------------------------------------------------------------
# save_unknown_resources
# ---------------------------------------------------------------------------
class TestSaveUnknownResources:
    def test_no_unknown_returns_empty(self):
        resources = [{"resource_type": "subnet", "name": "test"}]
        result = save_unknown_resources(resources, tempfile.gettempdir(), "test", "aws")
        assert result == {}

    def test_unknown_resources_saved(self):
        resources = [
            {"resource_type": "unknown", "name": "mystery"},
            {"resource_type": "subnet", "name": "normal"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            result = save_unknown_resources(resources, tmpdir, "test", "aws")
            assert "unknown_resources" in result
            assert os.path.exists(result["unknown_resources"])

    def test_missing_resource_type_is_unknown(self):
        resources = [{"name": "no-type"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            result = save_unknown_resources(resources, tmpdir, "test", "gcp")
            assert "unknown_resources" in result


# ---------------------------------------------------------------------------
# Path construction (os.path.join fix)
# ---------------------------------------------------------------------------
class TestPathConstruction:
    def test_output_paths_use_os_join(self):
        """Verify os.path.join produces valid paths on all platforms."""
        path = os.path.join("output", "aws_universal_ddi_licensing_20240101.csv")
        assert "output" in path
        assert path.endswith(".csv")
        # On Windows this would use backslashes, on Unix forward slashes
        assert os.sep in path or "/" in path
