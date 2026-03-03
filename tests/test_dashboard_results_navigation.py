"""Tests for Phase 23 Results Navigation — per-provider formula cards (CLOUD-06).

Covers:
  TestFormulaCards: formula derivation lines (÷ 25, ÷ 13, ÷ 3) appear in Results and Summary
                    tab HTML when the per_provider_details template variable is populated.
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
                _make_resource("vpc", "ip", "111111111111", "aws"),
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
                _make_resource("vpc", "ip", "111111111111", "aws"),
            ]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            assert "\u00f7 13 =" in response.text  # ÷ 13 =

    def test_formula_card_suppresses_zero_count_lines(self):
        """GET /tab/summary where azure has no IP resources does NOT show ÷ 13 = for AZURE."""
        app = create_app()
        with TestClient(app) as client:
            # AWS has all three; azure has only ddi + asset (no ips)
            resources = [
                _make_resource("dns-zone", "ddi", "111111111111", "aws"),
                _make_resource("vpc", "ip", "111111111111", "aws"),
                _make_resource("vm", "asset", "111111111111", "aws"),
                _make_resource("private-dns-zone", "ddi", "sub-azure-001", "azure"),
                _make_resource("vm", "asset", "sub-azure-001", "azure"),
            ]
            client.app.state.scan_manager.set_resources(resources)
            response = client.get("/tab/summary")
            assert response.status_code == 200
            # AWS has IPs so ÷ 13 = should appear somewhere in the page
            assert "\u00f7 13 =" in response.text  # ÷ 13 =
            # But specifically the AZURE section should NOT contain ÷ 13 = because azure ips == 0
            # We check by locating the AZURE card and confirming ÷ 13 = is absent before the
            # next provider card. We do a simple structural check: count of ÷ 13 = occurrences
            # equals the number of providers that have ips > 0 (just aws = 1).
            assert response.text.count("\u00f7 13 =") == 1

    def test_formula_card_shows_provider_name(self):
        """HTML contains provider name in upper case (e.g. AWS)."""
        app = create_app()
        with TestClient(app) as client:
            resources = [
                _make_resource("dns-zone", "ddi", "111111111111", "aws"),
                _make_resource("vm", "asset", "111111111111", "aws"),
                _make_resource("vpc", "ip", "111111111111", "aws"),
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
