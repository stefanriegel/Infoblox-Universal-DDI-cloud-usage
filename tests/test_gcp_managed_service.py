"""Tests for GCP _is_managed_service detection — prefix matching, false positive prevention."""

from unittest.mock import MagicMock, patch

import pytest

from gcp_discovery.gcp_discovery import GCPDiscovery


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def discovery():
    """Create a GCPDiscovery instance with fully mocked GCP clients (no real auth)."""
    config = MagicMock()
    config.project_id = "test-project"
    config.regions = ["us-central1"]
    config.output_directory = "output"
    config.output_format = "txt"

    shared_clients = {
        "instances": MagicMock(),
        "zones": MagicMock(),
        "networks": MagicMock(),
        "subnetworks": MagicMock(),
        "addresses": MagicMock(),
        "global_addresses": MagicMock(),
        "routers": MagicMock(),
    }

    mock_creds = MagicMock()
    with (
        patch("gcp_discovery.gcp_discovery.get_gcp_credential", return_value=(mock_creds, "test-project")),
        patch("google.cloud.dns.Client", return_value=MagicMock()),
    ):
        d = GCPDiscovery(config, shared_compute_clients=shared_clients)
    return d


# ---------------------------------------------------------------------------
# True Positives — these SHOULD be detected as managed
# ---------------------------------------------------------------------------
class TestManagedServiceTruePositives:
    def test_goog_managed_by_prefix(self, discovery):
        assert discovery._is_managed_service({"goog-managed-by": "cloud-run"})

    def test_gke_managed_prefix(self, discovery):
        assert discovery._is_managed_service({"gke-managed-components": "true"})

    def test_cloud_run_prefix(self, discovery):
        assert discovery._is_managed_service({"cloud-run-service": "my-svc"})

    def test_cloud_functions_prefix(self, discovery):
        assert discovery._is_managed_service({"cloud-functions-instance": "func1"})

    def test_managed_by_exact(self, discovery):
        assert discovery._is_managed_service({"managed-by": "gke"})

    def test_managed_by_underscore_exact(self, discovery):
        assert discovery._is_managed_service({"managed_by": "some-service"})

    def test_google_managed_exact(self, discovery):
        assert discovery._is_managed_service({"google-managed": "true"})

    def test_value_google_managed(self, discovery):
        assert discovery._is_managed_service({"some-key": "google-managed"})

    def test_value_gke(self, discovery):
        assert discovery._is_managed_service({"orchestrator": "gke"})

    def test_value_cloud_run(self, discovery):
        assert discovery._is_managed_service({"platform": "cloud-run"})

    def test_value_cloud_functions(self, discovery):
        assert discovery._is_managed_service({"runtime": "cloud-functions"})

    def test_case_insensitive_key(self, discovery):
        assert discovery._is_managed_service({"Managed-By": "gke"})

    def test_case_insensitive_value(self, discovery):
        assert discovery._is_managed_service({"platform": "Google-Managed"})


# ---------------------------------------------------------------------------
# True Negatives — these should NOT be detected as managed
# ---------------------------------------------------------------------------
class TestManagedServiceTrueNegatives:
    """These were false positives before the fix — broad substring matching."""

    def test_empty_labels(self, discovery):
        assert not discovery._is_managed_service({})

    def test_none_labels(self, discovery):
        assert not discovery._is_managed_service(None)

    def test_app_with_managed_substring(self, discovery):
        """Label 'app-managed-version' should NOT match (not a prefix or exact key)."""
        assert not discovery._is_managed_service({"app-managed-version": "v2"})

    def test_user_managed_by_value(self, discovery):
        """Value 'user-managed' should NOT match (not in the exact value set)."""
        assert not discovery._is_managed_service({"team": "user-managed"})

    def test_regular_app_labels(self, discovery):
        assert not discovery._is_managed_service({"app": "web-server", "env": "production"})

    def test_numeric_labels(self, discovery):
        assert not discovery._is_managed_service({"version": "3", "replicas": "5"})

    def test_partial_gke_in_value(self, discovery):
        """Value containing 'gke' as substring but not exact should NOT match."""
        assert not discovery._is_managed_service({"cluster": "my-gke-cluster"})

    def test_cloud_in_generic_label(self, discovery):
        """'cloud-provider' key should NOT match (no matching prefix)."""
        assert not discovery._is_managed_service({"cloud-provider": "gcp"})

    def test_managed_in_unrelated_key(self, discovery):
        """'self-managed' key should NOT match (not a matching prefix or exact)."""
        assert not discovery._is_managed_service({"self-managed": "true"})
