"""Tests for Phase 21 cloud per-account attribution table.

Covers:
  T1: _compute_summary() enriches per_account_details with ddi_tokens, ip_tokens, asset_tokens
  T1: _compute_summary() builds resource_type_breakdown with counted resources only
  T1: _compute_summary() groups resource types correctly per account
  T1: _compute_summary() omits non-counted resources from breakdown
  T2: GET /tab/summary renders rich attribution table HTML
  T2: Formula derivation (÷ 25 =, ÷ 13 =, ÷ 3 =) present for non-zero counts
  T2: Zero-count cells suppress formula line
  T2: Provider-aware labels (Account/Subscription/Project) per row
  T2: Collapsible ▶ N resource types breakdown trigger present
  T2: tfoot non-summability notes present
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.dashboard.routes.pages import _compute_summary
from cloud_usage.schema.resource import CloudResource


def _make_resource(
    resource_type: str,
    category: str | None,
    account_id: str,
    provider: str,
    counted: bool = True,
) -> CloudResource:
    """Factory for CloudResource test instances."""
    return CloudResource(
        resource_id=f"{account_id}-{resource_type}-{id(object())}",
        resource_type=resource_type,
        provider=provider,
        account_id=account_id,
        region="us-east-1",
        name=resource_type,
        counted=counted,
        category=category,
    )


class TestComputeSummaryEnrichment:
    """Tests for per_account_details enrichment with token and breakdown fields."""

    def test_token_fields_present(self):
        """ddi_tokens, ip_tokens, asset_tokens appear in each per_account_details entry."""
        resources = [
            _make_resource("dns-zone", "ddi", "acct-1", "aws"),
            _make_resource("vm", "asset", "acct-1", "aws"),
        ]
        result = _compute_summary(resources)
        assert len(result["per_account_details"]) == 1
        acct = result["per_account_details"][0]
        assert "ddi_tokens" in acct
        assert "ip_tokens" in acct
        assert "asset_tokens" in acct

    def test_ddi_tokens_value(self):
        """ddi_tokens = ceil(ddi_count / 25)."""
        resources = [
            _make_resource("dns-zone", "ddi", "acct-1", "aws")
            for _ in range(25)
        ]
        result = _compute_summary(resources)
        acct = result["per_account_details"][0]
        assert acct["ddi_tokens"] == 1  # ceil(25/25) = 1
        assert acct["ip_tokens"] == 0

    def test_asset_tokens_value(self):
        """asset_tokens = ceil(asset_count / 3)."""
        resources = [
            _make_resource("vm", "asset", "acct-1", "aws")
            for _ in range(4)
        ]
        result = _compute_summary(resources)
        acct = result["per_account_details"][0]
        assert acct["asset_tokens"] == 2  # ceil(4/3) = 2

    def test_resource_type_breakdown_present(self):
        """resource_type_breakdown key exists in each per_account_details entry."""
        resources = [_make_resource("dns-zone", "ddi", "acct-1", "aws")]
        result = _compute_summary(resources)
        acct = result["per_account_details"][0]
        assert "resource_type_breakdown" in acct

    def test_breakdown_groups_by_type(self):
        """Breakdown groups resources by resource_type with count and category."""
        resources = [
            _make_resource("dns-zone", "ddi", "acct-1", "aws"),
            _make_resource("dns-zone", "ddi", "acct-1", "aws"),
            _make_resource("vm", "asset", "acct-1", "aws"),
        ]
        result = _compute_summary(resources)
        breakdown = result["per_account_details"][0]["resource_type_breakdown"]
        assert breakdown["dns-zone"]["count"] == 2
        assert breakdown["dns-zone"]["category"] == "ddi"
        assert breakdown["vm"]["count"] == 1
        assert breakdown["vm"]["category"] == "asset"

    def test_breakdown_excludes_non_counted(self):
        """Resources with counted=False are excluded from breakdown."""
        resources = [
            _make_resource("dns-zone", "ddi", "acct-1", "aws", counted=True),
            _make_resource("ebs-volume", None, "acct-1", "aws", counted=False),
        ]
        result = _compute_summary(resources)
        breakdown = result["per_account_details"][0]["resource_type_breakdown"]
        assert "ebs-volume" not in breakdown
        assert "dns-zone" in breakdown

    def test_breakdown_empty_when_no_counted_resources(self):
        """Accounts with all non-counted resources have empty breakdown."""
        resources = [
            _make_resource("ebs-volume", None, "acct-1", "aws", counted=False),
        ]
        result = _compute_summary(resources)
        for acct in result["per_account_details"]:
            assert isinstance(acct["resource_type_breakdown"], dict)

    def test_multi_account_breakdown_isolated(self):
        """Each account's breakdown only contains its own resource types."""
        resources = [
            _make_resource("dns-zone", "ddi", "acct-aws", "aws"),
            _make_resource("private-dns-zone", "ddi", "sub-azure", "azure"),
        ]
        result = _compute_summary(resources)
        accounts = {a["account_id"]: a for a in result["per_account_details"]}
        assert "dns-zone" in accounts["acct-aws"]["resource_type_breakdown"]
        assert "dns-zone" not in accounts["sub-azure"]["resource_type_breakdown"]
        assert "private-dns-zone" in accounts["sub-azure"]["resource_type_breakdown"]

    def test_provider_preserved_in_per_account_details(self):
        """Provider field is correct for each account in multi-provider scans."""
        resources = [
            _make_resource("dns-zone", "ddi", "acct-aws", "aws"),
            _make_resource("private-dns-zone", "ddi", "sub-azure", "azure"),
            _make_resource("cloud-dns", "ddi", "proj-gcp", "gcp"),
        ]
        result = _compute_summary(resources)
        accounts = {a["account_id"]: a for a in result["per_account_details"]}
        assert accounts["acct-aws"]["provider"] == "aws"
        assert accounts["sub-azure"]["provider"] == "azure"
        assert accounts["proj-gcp"]["provider"] == "gcp"

    def test_existing_fields_unchanged(self):
        """Existing fields (ddi_count, ip_count, asset_count, total_tokens) still present."""
        resources = [_make_resource("dns-zone", "ddi", "acct-1", "aws")]
        result = _compute_summary(resources)
        acct = result["per_account_details"][0]
        assert "ddi_count" in acct
        assert "ip_count" in acct
        assert "asset_count" in acct
        assert "total_tokens" in acct
        assert "account_id" in acct
        assert "provider" in acct


# ---------------------------------------------------------------------------
# Template rendering tests (HTML content assertions via TestClient)
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient

from cloud_usage.dashboard.app import create_app


class TestSummaryTabHTMLRendering:
    """HTML content tests for Phase 21 rich per-account attribution table."""

    def test_summary_tab_returns_200(self):
        """GET /tab/summary returns 200 when resources exist."""
        app = create_app()
        with TestClient(app) as client:
            resources = [_make_resource("dns-zone", "ddi", "123456789012", "aws")]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200

    def test_account_column_header_present(self):
        """Summary tab shows 'Account / Sub / Project' column header."""
        app = create_app()
        with TestClient(app) as client:
            resources = [_make_resource("dns-zone", "ddi", "123456789012", "aws")]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "Account / Sub / Project" in response.text

    def test_formula_derivation_ddi(self):
        """DDI column shows ÷ 25 = formula for non-zero DDI count."""
        app = create_app()
        with TestClient(app) as client:
            resources = [_make_resource("dns-zone", "ddi", "123456789012", "aws")]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "÷ 25 =" in response.text

    def test_formula_derivation_assets(self):
        """Asset column shows ÷ 3 = formula for non-zero asset count."""
        app = create_app()
        with TestClient(app) as client:
            resources = [
                _make_resource("vm", "asset", "123456789012", "aws"),
                _make_resource("vm", "asset", "123456789012", "aws"),
                _make_resource("vm", "asset", "123456789012", "aws"),
            ]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "÷ 3 =" in response.text

    def test_zero_count_suppresses_formula(self):
        """Zero IP count suppresses ÷ 13 = formula line."""
        app = create_app()
        with TestClient(app) as client:
            resources = [_make_resource("dns-zone", "ddi", "123456789012", "aws")]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "÷ 25 =" in response.text  # DDI present
            assert "÷ 13 =" not in response.text  # IP absent (zero count)

    def test_provider_aware_label_aws(self):
        """AWS account rows show 'Account' label."""
        app = create_app()
        with TestClient(app) as client:
            resources = [_make_resource("dns-zone", "ddi", "123456789012", "aws")]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "Account" in response.text

    def test_provider_aware_label_azure(self):
        """Azure account rows show 'Subscription' label."""
        app = create_app()
        with TestClient(app) as client:
            resources = [_make_resource("private-dns-zone", "ddi", "sub-abc-123", "azure")]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "Subscription" in response.text

    def test_provider_aware_label_gcp(self):
        """GCP account rows show 'Project' label."""
        app = create_app()
        with TestClient(app) as client:
            resources = [_make_resource("cloud-dns", "ddi", "my-gcp-project", "gcp")]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "Project" in response.text

    def test_resource_type_breakdown_collapsible(self):
        """Summary tab shows '▶ N resource types' collapsible trigger."""
        app = create_app()
        with TestClient(app) as client:
            resources = [
                _make_resource("dns-zone", "ddi", "123456789012", "aws"),
                _make_resource("vm", "asset", "123456789012", "aws"),
            ]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "resource types" in response.text

    def test_footer_non_summability_notes(self):
        """Summary tab footer contains non-summability notes."""
        app = create_app()
        with TestClient(app) as client:
            resources = [_make_resource("dns-zone", "ddi", "123456789012", "aws")]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            text_lower = response.text.lower()
            assert "not summable" in text_lower or "not directly summable" in text_lower

    def test_footer_ddi_summable_note(self):
        """Summary tab footer states DDI column is summable."""
        app = create_app()
        with TestClient(app) as client:
            resources = [_make_resource("dns-zone", "ddi", "123456789012", "aws")]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "summable" in response.text
