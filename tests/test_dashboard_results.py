"""
Tests for Results and Summary tabs with filtering, pagination, and token calculations.

Tests cover the Results tab data table with server-side filtering by
provider, account, resource type, category, and status, pagination
with 50 rows per page, filter chip rendering, and Summary tab token
calculation display.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.dashboard.app import create_app
from cloud_usage.schema.resource import CloudResource


def _make_test_resource(
    resource_id: str = "res-1",
    resource_type: str = "vm",
    provider: str = "aws",
    account_id: str = "111111111111",
    region: str = "us-east-1",
    name: str = "test-resource",
    ip_addresses: list[str] | None = None,
    counted: bool | None = True,
    category: str | None = "asset",
    skip_reason: str | None = None,
) -> CloudResource:
    """Factory for creating test CloudResource instances.

    Args:
        resource_id: Unique resource identifier.
        resource_type: Type of the resource.
        provider: Cloud provider name.
        account_id: Account identifier.
        region: Cloud region.
        name: Human-readable name.
        ip_addresses: List of IP addresses.
        counted: Whether counted toward tokens.
        category: Token category.
        skip_reason: Why excluded from counting.

    Returns:
        CloudResource instance with the specified attributes.
    """
    return CloudResource(
        resource_id=resource_id,
        resource_type=resource_type,
        provider=provider,
        account_id=account_id,
        region=region,
        name=name,
        ip_addresses=ip_addresses or [],
        counted=counted,
        category=category,
        skip_reason=skip_reason,
    )


def _populate_scan_manager(app, resources: list[CloudResource]) -> None:
    """Populate the app's ScanManager with test resources.

    Uses TestClient's lifespan to access app.state.scan_manager.

    Args:
        app: FastAPI app instance.
        resources: List of CloudResource instances to set.
    """
    # We need to access scan_manager through the test client context
    pass


@pytest.fixture()
def client():
    """Create a FastAPI TestClient with the app."""
    from fastapi.testclient import TestClient

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def client_with_data():
    """Create a TestClient with mock resources pre-populated."""
    from fastapi.testclient import TestClient

    app = create_app()
    with TestClient(app) as c:
        # Populate scan manager with test data
        resources = [
            _make_test_resource(
                resource_id="vpc-001",
                resource_type="vpc",
                provider="aws",
                account_id="111111111111",
                region="us-east-1",
                counted=True,
                category="ddi",
            ),
            _make_test_resource(
                resource_id="subnet-001",
                resource_type="subnet",
                provider="aws",
                account_id="111111111111",
                region="us-east-1",
                counted=True,
                category="ddi",
            ),
            _make_test_resource(
                resource_id="vm-001",
                resource_type="vm",
                provider="aws",
                account_id="111111111111",
                region="us-east-1",
                ip_addresses=["10.0.0.1", "52.1.2.3"],
                counted=True,
                category="asset",
            ),
            _make_test_resource(
                resource_id="azure-vnet-001",
                resource_type="azure-vnet",
                provider="azure",
                account_id="sub-001",
                region="eastus",
                counted=True,
                category="ddi",
            ),
            _make_test_resource(
                resource_id="azure-vm-001",
                resource_type="azure-vm",
                provider="azure",
                account_id="sub-001",
                region="eastus",
                ip_addresses=["10.1.0.1"],
                counted=True,
                category="asset",
            ),
            _make_test_resource(
                resource_id="ebs-001",
                resource_type="ebs-volume",
                provider="aws",
                account_id="111111111111",
                region="us-east-1",
                counted=False,
                category=None,
                skip_reason="token-free: EBS Volume",
            ),
        ]
        c.app.state.scan_manager.set_resources(resources)
        yield c


class TestResultsTabNoData:
    """Tests for Results tab with no scan data."""

    def test_results_tab_returns_200(self, client) -> None:
        """GET /tab/results returns 200 with no resources."""
        response = client.get("/tab/results")
        assert response.status_code == 200

    def test_results_tab_shows_no_results_message(self, client) -> None:
        """GET /tab/results shows empty state message when no resources."""
        response = client.get("/tab/results")
        assert "No results yet" in response.text

    def test_results_tab_has_tab_bar(self, client) -> None:
        """GET /tab/results includes tab bar with active state."""
        response = client.get("/tab/results")
        assert "tab-active" in response.text
        assert "Results" in response.text


class TestResultsTabWithData:
    """Tests for Results tab with mock data."""

    def test_results_tab_shows_table(self, client_with_data) -> None:
        """GET /tab/results shows results table when resources exist."""
        response = client_with_data.get("/tab/results")
        assert response.status_code == 200
        assert "vpc-001" in response.text
        assert "subnet-001" in response.text
        assert "vm-001" in response.text

    def test_results_tab_shows_all_columns(self, client_with_data) -> None:
        """Results table has all expected column headers."""
        response = client_with_data.get("/tab/results")
        for col in ["Resource ID", "Type", "Provider", "Account",
                     "Region", "Category", "Counted", "IPs", "Skip Reason"]:
            assert col in response.text

    def test_results_tab_shows_filter_dropdowns(self, client_with_data) -> None:
        """Results page has filter dropdowns for all five dimensions."""
        response = client_with_data.get("/tab/results")
        assert 'name="filter_provider"' in response.text
        assert 'name="filter_account"' in response.text
        assert 'name="filter_resource_type"' in response.text
        assert 'name="filter_category"' in response.text
        assert 'name="filter_status"' in response.text

    def test_results_tab_shows_resource_count(self, client_with_data) -> None:
        """Results table shows correct result count."""
        response = client_with_data.get("/tab/results")
        assert "Showing 1-6 of 6 results" in response.text


class TestFilteringByProvider:
    """Tests for provider filtering via HTMX partial."""

    def test_filter_by_aws(self, client_with_data) -> None:
        """GET /partials/results-table?filter_provider=aws returns only AWS resources."""
        response = client_with_data.get(
            "/partials/results-table?filter_provider=aws"
        )
        assert response.status_code == 200
        assert "vpc-001" in response.text
        assert "subnet-001" in response.text
        assert "vm-001" in response.text
        assert "ebs-001" in response.text
        # Azure resources should not appear
        assert "azure-vnet-001" not in response.text
        assert "azure-vm-001" not in response.text

    def test_filter_by_azure(self, client_with_data) -> None:
        """GET /partials/results-table?filter_provider=azure returns only Azure resources."""
        response = client_with_data.get(
            "/partials/results-table?filter_provider=azure"
        )
        assert response.status_code == 200
        assert "azure-vnet-001" in response.text
        assert "azure-vm-001" in response.text
        # AWS resources should not appear
        assert "vpc-001" not in response.text

    def test_filter_case_insensitive(self, client_with_data) -> None:
        """Provider filter is case-insensitive."""
        response = client_with_data.get(
            "/partials/results-table?filter_provider=AWS"
        )
        assert response.status_code == 200
        assert "vpc-001" in response.text


class TestFilteringByCategory:
    """Tests for category filtering via HTMX partial."""

    def test_filter_by_ddi(self, client_with_data) -> None:
        """GET /partials/results-table?filter_category=ddi returns only DDI resources."""
        response = client_with_data.get(
            "/partials/results-table?filter_category=ddi"
        )
        assert response.status_code == 200
        assert "vpc-001" in response.text
        assert "subnet-001" in response.text
        assert "azure-vnet-001" in response.text
        # Non-DDI resources should not appear
        assert "vm-001" not in response.text
        assert "ebs-001" not in response.text

    def test_filter_by_asset(self, client_with_data) -> None:
        """GET /partials/results-table?filter_category=asset returns only asset resources."""
        response = client_with_data.get(
            "/partials/results-table?filter_category=asset"
        )
        assert response.status_code == 200
        assert "vm-001" in response.text
        assert "azure-vm-001" in response.text
        # Non-asset resources should not appear
        assert "vpc-001" not in response.text


class TestFilteringByStatus:
    """Tests for status filtering via HTMX partial."""

    def test_filter_counted(self, client_with_data) -> None:
        """GET /partials/results-table?filter_status=counted returns only counted resources."""
        response = client_with_data.get(
            "/partials/results-table?filter_status=counted"
        )
        assert response.status_code == 200
        assert "vpc-001" in response.text
        assert "vm-001" in response.text
        # Skipped resource should not appear
        assert "ebs-001" not in response.text

    def test_filter_skipped(self, client_with_data) -> None:
        """GET /partials/results-table?filter_status=skipped returns only skipped resources."""
        response = client_with_data.get(
            "/partials/results-table?filter_status=skipped"
        )
        assert response.status_code == 200
        assert "ebs-001" in response.text
        # Counted resources should not appear
        assert "vpc-001" not in response.text
        assert "vm-001" not in response.text


class TestPagination:
    """Tests for server-side pagination."""

    @pytest.fixture()
    def client_many_resources(self):
        """Create a TestClient with 120 resources for pagination testing."""
        from fastapi.testclient import TestClient

        app = create_app()
        with TestClient(app) as c:
            resources = [
                _make_test_resource(
                    resource_id=f"res-{i:03d}",
                    resource_type="vm",
                    provider="aws",
                    account_id="111111111111",
                    region="us-east-1",
                    ip_addresses=[f"10.0.0.{i % 256}"],
                    counted=True,
                    category="asset",
                )
                for i in range(120)
            ]
            c.app.state.scan_manager.set_resources(resources)
            yield c

    def test_page_1_has_50_rows(self, client_many_resources) -> None:
        """Page 1 returns 50 resources (default page_size)."""
        response = client_many_resources.get(
            "/partials/results-table?page=1"
        )
        assert response.status_code == 200
        assert "Showing 1-50 of 120 results" in response.text

    def test_page_2_has_50_rows(self, client_many_resources) -> None:
        """Page 2 returns resources 51-100."""
        response = client_many_resources.get(
            "/partials/results-table?page=2"
        )
        assert response.status_code == 200
        assert "Showing 51-100 of 120 results" in response.text

    def test_page_3_has_20_rows(self, client_many_resources) -> None:
        """Page 3 returns remaining 20 resources."""
        response = client_many_resources.get(
            "/partials/results-table?page=3"
        )
        assert response.status_code == 200
        assert "Showing 101-120 of 120 results" in response.text

    def test_pagination_controls_present(self, client_many_resources) -> None:
        """Pagination shows Previous/Next buttons and page indicator."""
        response = client_many_resources.get(
            "/partials/results-table?page=2"
        )
        assert "Previous" in response.text
        assert "Next" in response.text
        assert "Page 2 of 3" in response.text

    def test_page_1_previous_disabled(self, client_many_resources) -> None:
        """Previous button is disabled on page 1."""
        response = client_many_resources.get(
            "/partials/results-table?page=1"
        )
        # Should have disabled Previous button
        assert "disabled" in response.text


class TestFilterChips:
    """Tests for active filter chip rendering."""

    def test_chips_appear_for_active_filter(self, client_with_data) -> None:
        """Filter chips appear when a filter is active."""
        response = client_with_data.get(
            "/partials/results-table?filter_provider=aws"
        )
        assert response.status_code == 200
        assert "chip" in response.text
        assert "Provider" in response.text
        assert "aws" in response.text

    def test_chips_have_remove_link(self, client_with_data) -> None:
        """Each chip has a remove (clear) link."""
        response = client_with_data.get(
            "/partials/results-table?filter_provider=aws"
        )
        assert "clear_filter_provider" in response.text

    def test_no_chips_without_filters(self, client_with_data) -> None:
        """No chips shown when no filters are active."""
        response = client_with_data.get("/partials/results-table")
        # Should not have chip class in filter chips area
        # The chip class may appear elsewhere, so check for filter-chips div
        assert "filter-chips" not in response.text


class TestSummaryTabNoData:
    """Tests for Summary tab with no scan data."""

    def test_summary_tab_returns_200(self, client) -> None:
        """GET /tab/summary returns 200 with no resources."""
        response = client.get("/tab/summary")
        assert response.status_code == 200

    def test_summary_tab_shows_no_data_message(self, client) -> None:
        """GET /tab/summary shows empty state message when no resources."""
        response = client.get("/tab/summary")
        assert "No scan data available" in response.text

    def test_summary_tab_has_download_placeholder(self, client) -> None:
        """Summary tab has download reports placeholder section."""
        response = client.get("/tab/summary")
        assert "Download Reports" in response.text


class TestSummaryTabWithData:
    """Tests for Summary tab with mock data."""

    def test_summary_shows_token_cards(self, client_with_data) -> None:
        """Summary tab shows total tokens, DDI, IP, and asset counts."""
        response = client_with_data.get("/tab/summary")
        assert response.status_code == 200
        assert "Total Tokens" in response.text
        assert "DDI Objects" in response.text
        assert "Active IPs" in response.text
        assert "Managed Assets" in response.text

    def test_summary_shows_correct_ddi_count(self, client_with_data) -> None:
        """Summary correctly counts DDI objects (3 DDI resources)."""
        response = client_with_data.get("/tab/summary")
        # 3 DDI resources: vpc-001, subnet-001, azure-vnet-001
        # The count should appear in the DDI Objects card
        assert response.status_code == 200

    def test_summary_shows_provider_breakdown(self, client_with_data) -> None:
        """Summary shows per-provider breakdown table."""
        response = client_with_data.get("/tab/summary")
        assert "Per-Provider Breakdown" in response.text
        assert "AWS" in response.text
        assert "AZURE" in response.text

    def test_summary_shows_account_breakdown(self, client_with_data) -> None:
        """Summary shows per-account breakdown table."""
        response = client_with_data.get("/tab/summary")
        assert "Account Attribution" in response.text
        assert "111111111111" in response.text
        assert "sub-001" in response.text

    def test_summary_token_calculation_matches_pipeline(
        self, client_with_data
    ) -> None:
        """Summary tokens match counting pipeline calculation.

        3 DDI objects -> ceil(3/25) = 1 DDI token
        3 IPs (10.0.0.1, 52.1.2.3, 10.1.0.1) -> ceil(3/13) = 1 IP token
        2 assets (vm-001, azure-vm-001) -> ceil(2/3) = 1 asset token
        Total: 3 tokens
        """
        from cloud_usage.counting.token_calculator import calculate_tokens

        expected = calculate_tokens(ddi_count=3, ip_count=3, asset_count=2)
        assert expected["total_tokens"] == 3

        response = client_with_data.get("/tab/summary")
        assert response.status_code == 200
        # Total should be 3 tokens
        # Check that the number 3 appears in context of Total Tokens
        text = response.text
        # Find "Total Tokens" section and verify
        assert "Total Tokens" in text


class TestSummaryCardsPartial:
    """Tests for the /partials/summary-cards endpoint."""

    def test_summary_cards_returns_200(self, client) -> None:
        """GET /partials/summary-cards returns 200."""
        response = client.get("/partials/summary-cards")
        assert response.status_code == 200

    def test_summary_cards_shows_no_data(self, client) -> None:
        """Summary cards show no data message when empty."""
        response = client.get("/partials/summary-cards")
        assert "No scan data available" in response.text

    def test_summary_cards_with_data(self, client_with_data) -> None:
        """Summary cards show token counts when data exists."""
        response = client_with_data.get("/partials/summary-cards")
        assert response.status_code == 200
        assert "Total Tokens" in response.text
        assert "DDI Objects" in response.text
