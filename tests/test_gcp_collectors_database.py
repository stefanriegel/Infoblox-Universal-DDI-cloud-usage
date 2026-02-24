"""Tests for GCP database resource collectors (Cloud SQL).

Uses unittest.mock to simulate the googleapiclient discovery API responses.
Tests cover IP extraction from ipAddresses, pagination via list_next,
None service handling, and label extraction.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _make_sqladmin_service(pages: list[dict] | None = None) -> MagicMock:
    """Build a mock sqladmin discovery service.

    Args:
        pages: List of response dicts for paginated responses.
            Each dict should have "items" key. If None, returns
            a single empty response.

    Returns:
        MagicMock mimicking googleapiclient discovery service.
    """
    if pages is None:
        pages = [{"items": []}]

    service = MagicMock()
    instances_resource = MagicMock()
    service.instances.return_value = instances_resource

    # Build the chain of request objects for pagination
    requests = []
    for page in pages:
        req = MagicMock()
        req.execute.return_value = page
        requests.append(req)

    # First call to .list() returns first request
    instances_resource.list.return_value = requests[0]

    # list_next returns next request or None at the end
    side_effects = []
    for i in range(len(requests)):
        if i + 1 < len(requests):
            side_effects.append(requests[i + 1])
        else:
            side_effects.append(None)

    instances_resource.list_next.side_effect = side_effects

    return service


def _make_sql_instance(
    name: str = "test-db",
    self_link: str | None = None,
    region: str = "us-central1",
    database_version: str = "POSTGRES_14",
    tier: str = "db-f1-micro",
    state: str = "RUNNABLE",
    ip_addresses: list[dict] | None = None,
    user_labels: dict | None = None,
) -> dict:
    """Build a mock Cloud SQL instance dict."""
    instance: dict = {
        "name": name,
        "region": region,
        "databaseVersion": database_version,
        "state": state,
        "settings": {
            "tier": tier,
            "userLabels": user_labels or {},
        },
    }
    if self_link is not None:
        instance["selfLink"] = self_link
    if ip_addresses is not None:
        instance["ipAddresses"] = ip_addresses
    return instance


class TestCollectGcpCloudSql:
    """Tests for collect_gcp_cloud_sql."""

    def test_basic_cloud_sql_discovery(self):
        """Test basic Cloud SQL instance discovered with correct type."""
        from cloud_usage.providers.gcp.collectors.database import collect_gcp_cloud_sql

        inst = _make_sql_instance(
            name="my-db",
            self_link="https://sqladmin.googleapis.com/sql/v1/projects/proj/instances/my-db",
        )
        service = _make_sqladmin_service([{"items": [inst]}])

        result = collect_gcp_cloud_sql(service, "proj")

        assert len(result) == 1
        assert result[0].resource_type == "gcp-cloud-sql"
        assert result[0].provider == "gcp"
        assert result[0].account_id == "proj"
        assert result[0].name == "my-db"

    def test_ip_extraction_private_and_public(self):
        """Test IP extraction from ipAddresses list (both types)."""
        from cloud_usage.providers.gcp.collectors.database import collect_gcp_cloud_sql

        inst = _make_sql_instance(
            name="db-1",
            ip_addresses=[
                {"type": "PRIMARY", "ipAddress": "34.123.45.67"},
                {"type": "PRIVATE", "ipAddress": "10.0.0.5"},
            ],
        )
        service = _make_sqladmin_service([{"items": [inst]}])

        result = collect_gcp_cloud_sql(service, "proj")

        assert len(result[0].ip_addresses) == 2
        assert "34.123.45.67" in result[0].ip_addresses
        assert "10.0.0.5" in result[0].ip_addresses

    def test_instance_no_ips(self):
        """Test instance with no IPs has empty ip_addresses."""
        from cloud_usage.providers.gcp.collectors.database import collect_gcp_cloud_sql

        inst = _make_sql_instance(name="db-no-ip", ip_addresses=[])
        service = _make_sqladmin_service([{"items": [inst]}])

        result = collect_gcp_cloud_sql(service, "proj")

        assert result[0].ip_addresses == []

    def test_instance_no_ip_addresses_field(self):
        """Test instance without ipAddresses field at all."""
        from cloud_usage.providers.gcp.collectors.database import collect_gcp_cloud_sql

        inst = _make_sql_instance(name="db-missing-ips")
        # Don't include ipAddresses in the dict at all
        service = _make_sqladmin_service([{"items": [inst]}])

        result = collect_gcp_cloud_sql(service, "proj")

        assert result[0].ip_addresses == []

    def test_pagination_multiple_pages(self):
        """Test pagination via list_next handles multiple pages."""
        from cloud_usage.providers.gcp.collectors.database import collect_gcp_cloud_sql

        inst1 = _make_sql_instance(name="db-page1")
        inst2 = _make_sql_instance(name="db-page2")
        service = _make_sqladmin_service([
            {"items": [inst1]},
            {"items": [inst2]},
        ])

        result = collect_gcp_cloud_sql(service, "proj")

        assert len(result) == 2
        names = {r.name for r in result}
        assert names == {"db-page1", "db-page2"}

    def test_none_sqladmin_service(self):
        """Test None service returns empty list (graceful fallback)."""
        from cloud_usage.providers.gcp.collectors.database import collect_gcp_cloud_sql

        result = collect_gcp_cloud_sql(None, "proj")

        assert result == []

    def test_empty_response_no_items(self):
        """Test empty response (no items key) returns empty list."""
        from cloud_usage.providers.gcp.collectors.database import collect_gcp_cloud_sql

        service = _make_sqladmin_service([{}])

        result = collect_gcp_cloud_sql(service, "proj")

        assert result == []

    def test_labels_extraction(self):
        """Test labels extracted from settings.userLabels."""
        from cloud_usage.providers.gcp.collectors.database import collect_gcp_cloud_sql

        inst = _make_sql_instance(
            name="db-labeled",
            user_labels={"env": "staging", "team": "backend"},
        )
        service = _make_sqladmin_service([{"items": [inst]}])

        result = collect_gcp_cloud_sql(service, "proj")

        assert result[0].tags == {"env": "staging", "team": "backend"}

    def test_labels_none(self):
        """Test instance with no labels has empty tags."""
        from cloud_usage.providers.gcp.collectors.database import collect_gcp_cloud_sql

        inst = _make_sql_instance(name="db-no-labels", user_labels=None)
        service = _make_sqladmin_service([{"items": [inst]}])

        result = collect_gcp_cloud_sql(service, "proj")

        assert result[0].tags == {}

    def test_region_and_details(self):
        """Test region and details (database_version, tier, state) extracted."""
        from cloud_usage.providers.gcp.collectors.database import collect_gcp_cloud_sql

        inst = _make_sql_instance(
            name="db-details",
            region="europe-west1",
            database_version="MYSQL_8_0",
            tier="db-n1-standard-2",
            state="RUNNABLE",
        )
        service = _make_sqladmin_service([{"items": [inst]}])

        result = collect_gcp_cloud_sql(service, "proj")

        assert result[0].region == "europe-west1"
        assert result[0].details["database_version"] == "MYSQL_8_0"
        assert result[0].details["tier"] == "db-n1-standard-2"
        assert result[0].details["state"] == "RUNNABLE"

    def test_fallback_resource_id(self):
        """Test resource_id fallback when selfLink is not in response."""
        from cloud_usage.providers.gcp.collectors.database import collect_gcp_cloud_sql

        inst = _make_sql_instance(name="db-no-link")
        # selfLink not set in the factory when self_link=None
        service = _make_sqladmin_service([{"items": [inst]}])

        result = collect_gcp_cloud_sql(service, "proj")

        assert result[0].resource_id == "projects/proj/instances/db-no-link"

    def test_ip_entry_with_empty_ip_address(self):
        """Test IP entry with empty ipAddress string is skipped."""
        from cloud_usage.providers.gcp.collectors.database import collect_gcp_cloud_sql

        inst = _make_sql_instance(
            name="db-empty-ip",
            ip_addresses=[
                {"type": "PRIMARY", "ipAddress": ""},
                {"type": "PRIVATE", "ipAddress": "10.0.0.1"},
            ],
        )
        service = _make_sqladmin_service([{"items": [inst]}])

        result = collect_gcp_cloud_sql(service, "proj")

        assert result[0].ip_addresses == ["10.0.0.1"]
