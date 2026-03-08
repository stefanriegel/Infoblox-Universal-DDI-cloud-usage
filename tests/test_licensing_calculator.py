"""Tests for shared/licensing_calculator.py — token math, provider detection, asset counting."""

import os
import tempfile

import pytest

from shared.licensing_calculator import UniversalDDILicensingCalculator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_resource(resource_type, region="us-east-1", details=None, name="test"):
    return {
        "resource_id": f"test:{region}:{resource_type}:{name}",
        "resource_type": resource_type,
        "region": region,
        "name": name,
        "state": "active",
        "requires_management_token": True,
        "tags": {},
        "details": details or {},
        "discovered_at": "2024-01-01T00:00:00",
    }


# ---------------------------------------------------------------------------
# Token Calculation Math
# ---------------------------------------------------------------------------
class TestTokenCalculation:
    """Verify the 25/13/3 ratios and ceiling division."""

    def test_ratios_are_correct(self):
        calc = UniversalDDILicensingCalculator()
        assert calc.DDI_OBJECTS_PER_TOKEN == 25
        assert calc.ACTIVE_IPS_PER_TOKEN == 13
        assert calc.ASSETS_PER_TOKEN == 3

    def test_zero_resources_gives_minimum_tokens(self):
        calc = UniversalDDILicensingCalculator()
        result = calc.calculate_from_discovery_results([], provider="aws")
        # Even with 0 resources, minimum 1 token per category
        assert result["token_requirements"]["ddi_objects_tokens"] == 1
        assert result["token_requirements"]["active_ips_tokens"] == 1
        assert result["token_requirements"]["managed_assets_tokens"] == 1
        assert result["token_requirements"]["total_management_tokens"] == 3

    def test_25_ddi_objects_need_1_token(self):
        calc = UniversalDDILicensingCalculator()
        resources = [_make_resource("subnet") for _ in range(25)]
        result = calc.calculate_from_discovery_results(resources, provider="aws")
        assert result["token_requirements"]["ddi_objects_tokens"] == 1

    def test_26_ddi_objects_need_2_tokens(self):
        calc = UniversalDDILicensingCalculator()
        resources = [_make_resource("subnet") for _ in range(26)]
        result = calc.calculate_from_discovery_results(resources, provider="aws")
        assert result["token_requirements"]["ddi_objects_tokens"] == 2

    def test_13_active_ips_need_1_token(self):
        calc = UniversalDDILicensingCalculator()
        resources = [
            _make_resource("ec2-instance", details={"private_ip": f"10.0.0.{i}", "vpc_id": "vpc-aaa"}) for i in range(1, 14)
        ]
        result = calc.calculate_from_discovery_results(resources, provider="aws")
        assert result["token_requirements"]["active_ips_tokens"] == 1

    def test_14_active_ips_need_2_tokens(self):
        calc = UniversalDDILicensingCalculator()
        resources = [
            _make_resource("ec2-instance", details={"private_ip": f"10.0.0.{i}", "vpc_id": "vpc-aaa"}) for i in range(1, 15)
        ]
        result = calc.calculate_from_discovery_results(resources, provider="aws")
        assert result["token_requirements"]["active_ips_tokens"] == 2

    def test_3_managed_assets_need_1_token(self):
        calc = UniversalDDILicensingCalculator()
        resources = [_make_resource("ec2-instance", details={"private_ip": f"10.0.0.{i}"}) for i in range(1, 4)]
        result = calc.calculate_from_discovery_results(resources, provider="aws")
        assert result["token_requirements"]["managed_assets_tokens"] == 1

    def test_4_managed_assets_need_2_tokens(self):
        calc = UniversalDDILicensingCalculator()
        resources = [_make_resource("ec2-instance", details={"private_ip": f"10.0.0.{i}"}) for i in range(1, 5)]
        result = calc.calculate_from_discovery_results(resources, provider="aws")
        assert result["token_requirements"]["managed_assets_tokens"] == 2

    def test_total_tokens_is_sum(self):
        calc = UniversalDDILicensingCalculator()
        resources = [
            _make_resource("subnet"),  # 1 DDI object
            _make_resource("ec2-instance", details={"private_ip": "10.0.0.1"}),  # 1 asset + 1 IP
        ]
        result = calc.calculate_from_discovery_results(resources, provider="aws")
        total = (
            result["token_requirements"]["ddi_objects_tokens"]
            + result["token_requirements"]["active_ips_tokens"]
            + result["token_requirements"]["managed_assets_tokens"]
        )
        assert result["token_requirements"]["total_management_tokens"] == total


# ---------------------------------------------------------------------------
# DDI Object Counting
# ---------------------------------------------------------------------------
class TestDDIObjectCounting:
    def test_counts_all_ddi_types(self):
        calc = UniversalDDILicensingCalculator()
        resources = [
            _make_resource("subnet"),
            _make_resource("vpc"),
            _make_resource("route53-zone"),
            _make_resource("route53-record"),
            _make_resource("eks-cluster"),
        ]
        result = calc.calculate_from_discovery_results(resources, provider="aws")
        assert result["counts"]["ddi_objects"] == 5

    def test_non_ddi_types_not_counted(self):
        calc = UniversalDDILicensingCalculator()
        resources = [
            _make_resource("ec2-instance"),
            _make_resource("elastic-ip"),
        ]
        result = calc.calculate_from_discovery_results(resources, provider="aws")
        assert result["counts"]["ddi_objects"] == 0

    def test_cluster_types_are_ddi(self):
        """EKS, AKS, GKE clusters are DDI objects (production fix)."""
        calc = UniversalDDILicensingCalculator()
        for provider, rtype in [("aws", "eks-cluster"), ("azure", "aks-cluster"), ("gcp", "gke-cluster")]:
            resources = [_make_resource(rtype)]
            result = calc.calculate_from_discovery_results(resources, provider=provider)
            assert result["counts"]["ddi_objects"] == 1, f"{rtype} should be DDI for {provider}"


# ---------------------------------------------------------------------------
# Managed Asset Counting
# ---------------------------------------------------------------------------
class TestManagedAssetCounting:
    def test_vm_with_ip_is_asset(self):
        calc = UniversalDDILicensingCalculator()
        resources = [_make_resource("ec2-instance", details={"private_ip": "10.0.0.1"})]
        result = calc.calculate_from_discovery_results(resources, provider="aws")
        assert result["counts"]["managed_assets"] == 1

    def test_vm_without_ip_not_counted(self):
        calc = UniversalDDILicensingCalculator()
        resources = [_make_resource("ec2-instance", details={})]
        result = calc.calculate_from_discovery_results(resources, provider="aws")
        assert result["counts"]["managed_assets"] == 0

    @pytest.mark.parametrize(
        "provider,resource_type",
        [
            ("aws", "ec2-instance"),
            ("azure", "vm"),
            ("azure", "vmss-instance"),
            ("azure", "load-balancer"),
            ("azure", "firewall"),
            ("gcp", "compute-instance"),
        ],
    )
    def test_asset_types_with_ip(self, provider, resource_type):
        calc = UniversalDDILicensingCalculator()
        resources = [_make_resource(resource_type, details={"private_ip": "10.0.0.1"})]
        result = calc.calculate_from_discovery_results(resources, provider=provider)
        assert result["counts"]["managed_assets"] >= 1


# ---------------------------------------------------------------------------
# Provider Detection (region regex)
# ---------------------------------------------------------------------------
class TestProviderDetection:
    """_determine_provider must correctly identify cloud from region string."""

    def setup_method(self):
        self.calc = UniversalDDILicensingCalculator()

    def test_aws_regions(self):
        for region in ("us-east-1", "eu-west-2", "ap-southeast-1", "af-south-1"):
            r = _make_resource("subnet", region=region)
            assert self.calc._determine_provider(r) == "aws", f"Failed for {region}"

    def test_gcp_regions(self):
        for region in ("us-central1", "europe-west4", "asia-southeast1"):
            r = _make_resource("vpc-network", region=region)
            assert self.calc._determine_provider(r) == "gcp", f"Failed for {region}"

    def test_azure_regions(self):
        for region in ("eastus", "westeurope", "canadacentral", "uksouth"):
            r = _make_resource("vnet", region=region)
            assert self.calc._determine_provider(r) == "azure", f"Failed for {region}"

    def test_global_region_uses_current_provider(self):
        self.calc.current_provider = "gcp"
        r = _make_resource("dns-zone", region="global")
        assert self.calc._determine_provider(r) == "gcp"

    def test_current_provider_preferred_on_overlap(self):
        """'subnet' and 'dns-zone' exist in multiple providers — prefer current."""
        self.calc.current_provider = "azure"
        r = _make_resource("subnet", region="eastus")
        assert self.calc._determine_provider(r) == "azure"

        self.calc.current_provider = "aws"
        r = _make_resource("subnet", region="us-east-1")
        assert self.calc._determine_provider(r) == "aws"


# ---------------------------------------------------------------------------
# CSV/Text Export (encoding)
# ---------------------------------------------------------------------------
class TestExportEncoding:
    """Exports must use UTF-8 encoding (cross-platform fix)."""

    def test_csv_export_utf8(self):
        calc = UniversalDDILicensingCalculator()
        calc.calculate_from_discovery_results([], provider="aws")
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            calc.export_csv(path, provider="aws")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "Infoblox Universal DDI" in content
        finally:
            os.unlink(path)

    def test_text_export_utf8(self):
        calc = UniversalDDILicensingCalculator()
        calc.calculate_from_discovery_results([], provider="aws")
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            path = f.name
        try:
            calc.export_text_summary(path, provider="aws")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "INFOBLOX UNIVERSAL DDI" in content
        finally:
            os.unlink(path)

    def test_estimator_csv_export(self):
        calc = UniversalDDILicensingCalculator()
        calc.calculate_from_discovery_results([], provider="aws")
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            calc.export_estimator_csv(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "ddi_objects" in content
            assert "tokens_total" in content
        finally:
            os.unlink(path)

    def test_proof_manifest_export(self):
        calc = UniversalDDILicensingCalculator()
        resources = [_make_resource("subnet")]
        calc.calculate_from_discovery_results(resources, provider="aws")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            calc.export_proof_manifest(
                path,
                provider="aws",
                scope={"accounts": ["123456789"]},
                regions=["us-east-1"],
                native_objects=resources,
            )
            import json

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["provider"] == "aws"
            assert "resources_sha256" in data["hashes"]
            assert "manifest_sha256" in data["hashes"]
        finally:
            os.unlink(path)
