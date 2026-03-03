"""Tests for Phase 23 Results Navigation — per-provider formula cards (CLOUD-06)
and sortable per-account attribution table (CLOUD-07).

Covers:
  TestFormulaCards: formula derivation lines (÷ 25, ÷ 13, ÷ 3) appear in Results and Summary
                    tab HTML when the per_provider_details template variable is populated.
  TestSortableTable: data attributes (data-col, data-value, acct-row class) present in the
                     per-account attribution table, and IIFE sort script is embedded (CLOUD-07).
  TestANA07: collapsible <details> breakdown already present (ANA-07 verification only).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient

from cloud_usage.dashboard.app import create_app
from cloud_usage.schema.resource import CloudResource


def _make_resource(
    resource_type: str,
    category: str | None,
    account_id: str,
    provider: str,
    counted: bool = True,
    ip_addresses: list | None = None,
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
        ip_addresses=ip_addresses or [],
    )


def _make_client(resources: list) -> TestClient:
    """Create a TestClient with the given resources pre-loaded into scan_manager."""
    app = create_app()
    client = TestClient(app)
    client.__enter__()
    client.app.state.scan_manager.set_resources(resources)
    return client


class TestFormulaCards:
    """HTML rendering tests for per-provider formula cards (CLOUD-06)."""

    def test_formula_card_shows_on_results_tab(self):
        """GET /tab/results with scan data returns 200 and HTML contains DDI formula line."""
        app = create_app()
        with TestClient(app) as client:
            resources = [
                _make_resource("dns-zone", "ddi", "111111111111", "aws"),
                _make_resource("vm", "asset", "111111111111", "aws"),
                _make_resource("network-interface", "ip", "111111111111", "aws",
                               ip_addresses=["10.0.0.1"]),
            ]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/results")
            assert response.status_code == 200
            assert "\u00f7 25 =" in response.text  # ÷ 25 =

    def test_formula_card_shows_on_summary_tab(self):
        """GET /tab/summary with scan data returns 200 and HTML contains IP formula line."""
        app = create_app()
        with TestClient(app) as client:
            resources = [
                _make_resource("dns-zone", "ddi", "111111111111", "aws"),
                _make_resource("vm", "asset", "111111111111", "aws"),
                _make_resource("network-interface", "ip", "111111111111", "aws",
                               ip_addresses=["10.0.0.1"]),
            ]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "\u00f7 13 =" in response.text  # ÷ 13 =

    def test_formula_card_suppresses_zero_count_lines(self):
        """GET /tab/summary where azure has no IP resources does NOT show ÷ 13 = for AZURE card."""
        app = create_app()
        with TestClient(app) as client:
            # AWS has all three categories (ddi, ip with address, asset)
            # azure has only ddi + asset — no IP resources, so ips == 0 for azure
            resources = [
                _make_resource("dns-zone", "ddi", "111111111111", "aws"),
                _make_resource("network-interface", "ip", "111111111111", "aws",
                               ip_addresses=["10.0.0.1"]),
                _make_resource("vm", "asset", "111111111111", "aws"),
                _make_resource("private-dns-zone", "ddi", "sub-azure-001", "azure"),
                _make_resource("vm", "asset", "sub-azure-001", "azure"),
            ]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "\u00f7 13 =" in response.text  # ÷ 13 = present for AWS (has IPs)
            # The AZURE card appears after the AWS card in sorted order.
            # Find the AZURE section of the per-provider formula breakdown and confirm
            # it does NOT contain ÷ 13 = (azure has 0 IPs so the formula line is suppressed).
            text = response.text
            azure_idx = text.find("AZURE")
            assert azure_idx != -1, "AZURE section should be present"
            # Slice from AZURE heading to the end of the details block
            # The per-provider breakdown section ends at </details>
            details_end = text.find("</details>", azure_idx)
            azure_section = text[azure_idx:details_end if details_end != -1 else azure_idx + 2000]
            assert "\u00f7 13 =" not in azure_section  # ÷ 13 = absent in AZURE card

    def test_formula_card_shows_provider_name(self):
        """HTML contains provider name in upper case (e.g. AWS)."""
        app = create_app()
        with TestClient(app) as client:
            resources = [
                _make_resource("dns-zone", "ddi", "111111111111", "aws"),
                _make_resource("vm", "asset", "111111111111", "aws"),
                _make_resource("network-interface", "ip", "111111111111", "aws",
                               ip_addresses=["10.0.0.1"]),
            ]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "AWS" in response.text

    def test_no_scan_data_no_error(self):
        """GET /tab/summary with no resources returns 200 (no template exception)."""
        app = create_app()
        with TestClient(app) as client:
            # No resources set — scan_manager defaults to empty list
            response = client.get("/tab/summary")
            assert response.status_code == 200


class TestSortableTable:
    """HTML structure tests for sortable per-account attribution table (CLOUD-07)."""

    def _make_multi_account_resources(self) -> list:
        """Create resources across 2 accounts to produce per_account_details with multiple rows."""
        return [
            _make_resource("dns-zone", "ddi", "acct-111", "aws"),
            _make_resource("dns-zone", "ddi", "acct-111", "aws"),
            _make_resource("vm", "asset", "acct-111", "aws"),
            _make_resource("network-interface", "ip", "acct-111", "aws",
                           ip_addresses=["10.0.0.1"]),
            _make_resource("dns-zone", "ddi", "acct-222", "aws"),
            _make_resource("vm", "asset", "acct-222", "aws"),
            _make_resource("vm", "asset", "acct-222", "aws"),
        ]

    def test_sortable_headers_present(self):
        """GET /tab/summary HTML contains data-col="tokens" and data-col="ddi" on table headers."""
        app = create_app()
        with TestClient(app) as client:
            client.app.state.scan_manager.set_resources(self._make_multi_account_resources())
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert 'data-col="tokens"' in response.text
            assert 'data-col="ddi"' in response.text

    def test_data_value_attrs_present(self):
        """GET /tab/summary with multi-account data contains data-value= in HTML (numeric cells)."""
        app = create_app()
        with TestClient(app) as client:
            client.app.state.scan_manager.set_resources(self._make_multi_account_resources())
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "data-value=" in response.text

    def test_sort_iife_present(self):
        """GET /tab/summary HTML contains 'acct-attribution-table' (IIFE script target id)."""
        app = create_app()
        with TestClient(app) as client:
            client.app.state.scan_manager.set_resources(self._make_multi_account_resources())
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "acct-attribution-table" in response.text

    def test_acct_row_class_present(self):
        """GET /tab/summary HTML contains 'acct-row' (CSS class used by IIFE sort targeting)."""
        app = create_app()
        with TestClient(app) as client:
            client.app.state.scan_manager.set_resources(self._make_multi_account_resources())
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "acct-row" in response.text


class TestANA07:
    """Verification that ANA-07 (<details> collapsible breakdown) is already satisfied."""

    def test_details_summary_element_present(self):
        """GET /tab/summary with multi-resource account contains <details in HTML."""
        app = create_app()
        with TestClient(app) as client:
            resources = [
                _make_resource("dns-zone", "ddi", "111111111111", "aws"),
                _make_resource("vm", "asset", "111111111111", "aws"),
            ]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "<details" in response.text
