"""Tests for Azure PaaS and container resource collectors.

Uses unittest.mock to simulate Azure SDK client objects. Verifies that
App Service, Functions, Container Instance, Container App, AKS, and
API Management collectors produce correctly-shaped CloudResource instances.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from cloud_usage.providers.azure.collectors.paas import (
    collect_azure_aks_clusters,
    collect_azure_api_management,
    collect_azure_app_services,
    collect_azure_container_apps,
    collect_azure_container_apps_with_client,
    collect_azure_container_instances,
    collect_azure_functions,
)
from cloud_usage.schema.resource import CloudResource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _arm_id(rg: str, provider_path: str) -> str:
    """Build a full ARM resource ID for tests."""
    return f"/subscriptions/sub1/resourceGroups/{rg}/providers/{provider_path}"


def _make_web_app(
    name: str,
    kind: str,
    location: str = "eastus",
    inbound_ips: str | None = None,
    outbound_ips: str | None = None,
    state: str = "Running",
    default_host_name: str | None = None,
    tags: dict[str, str] | None = None,
) -> SimpleNamespace:
    """Build a mock Web App SDK object."""
    rg = "rg1"
    return SimpleNamespace(
        id=_arm_id(rg, f"Microsoft.Web/sites/{name}"),
        name=name,
        kind=kind,
        location=location,
        tags=tags,
        state=state,
        default_host_name=default_host_name or f"{name}.azurewebsites.net",
        inbound_ip_addresses=inbound_ips,
        outbound_ip_addresses=outbound_ips,
    )


# ---------------------------------------------------------------------------
# App Service tests
# ---------------------------------------------------------------------------

class TestCollectAzureAppServices:
    """Tests for collect_azure_app_services."""

    def test_app_service_excludes_functions(self):
        """3 web apps (2 regular, 1 functionapp): only 2 App Services returned."""
        client = MagicMock()

        client.web_apps.list.return_value = [
            _make_web_app("web-api", kind="app", inbound_ips="20.0.0.1", outbound_ips="20.0.0.2,20.0.0.3"),
            _make_web_app("web-frontend", kind="app,linux", inbound_ips="20.0.1.1", outbound_ips="20.0.1.2"),
            _make_web_app("func-processor", kind="functionapp,linux"),
        ]

        result = collect_azure_app_services(client, "sub1")

        assert len(result) == 2
        assert all(r.resource_type == "azure-app-service" for r in result)
        assert result[0].name == "web-api"
        assert result[1].name == "web-frontend"

    def test_app_service_outbound_ip_parsing(self):
        """Outbound IPs from comma-separated string are parsed correctly."""
        client = MagicMock()

        client.web_apps.list.return_value = [
            _make_web_app(
                "web-multi-ip",
                kind="app",
                inbound_ips="20.0.0.1",
                outbound_ips="20.0.0.2, 20.0.0.3, 20.0.0.4",
            ),
        ]

        result = collect_azure_app_services(client, "sub1")

        assert len(result) == 1
        app = result[0]
        assert app.ip_addresses == ["20.0.0.1", "20.0.0.2", "20.0.0.3", "20.0.0.4"]

    def test_app_service_no_ips(self):
        """App Service with no IPs has empty ip_addresses."""
        client = MagicMock()

        client.web_apps.list.return_value = [
            _make_web_app("web-noip", kind="app"),
        ]

        result = collect_azure_app_services(client, "sub1")

        assert len(result) == 1
        assert result[0].ip_addresses == []

    def test_app_service_dedup_inbound_outbound(self):
        """Same IP in both inbound and outbound is deduplicated."""
        client = MagicMock()

        client.web_apps.list.return_value = [
            _make_web_app(
                "web-shared-ip",
                kind="app",
                inbound_ips="20.0.0.1",
                outbound_ips="20.0.0.1,20.0.0.2",
            ),
        ]

        result = collect_azure_app_services(client, "sub1")

        assert result[0].ip_addresses == ["20.0.0.1", "20.0.0.2"]


# ---------------------------------------------------------------------------
# Functions tests
# ---------------------------------------------------------------------------

class TestCollectAzureFunctions:
    """Tests for collect_azure_functions."""

    def test_functions_only_includes_functionapp(self):
        """Only functionapp kind resources are included."""
        client = MagicMock()

        client.web_apps.list.return_value = [
            _make_web_app("web-api", kind="app"),
            _make_web_app("func-processor", kind="functionapp,linux", inbound_ips="20.0.0.10", outbound_ips="20.0.0.11"),
            _make_web_app("func-timer", kind="functionapp", inbound_ips="20.0.0.20"),
        ]

        result = collect_azure_functions(client, "sub1")

        assert len(result) == 2
        assert all(r.resource_type == "azure-function" for r in result)
        assert result[0].name == "func-processor"
        assert result[1].name == "func-timer"

    def test_functions_ip_extraction(self):
        """Functions have inbound + outbound IPs extracted."""
        client = MagicMock()

        client.web_apps.list.return_value = [
            _make_web_app(
                "func-withips",
                kind="functionapp",
                inbound_ips="20.0.0.10",
                outbound_ips="20.0.0.11,20.0.0.12",
            ),
        ]

        result = collect_azure_functions(client, "sub1")

        assert len(result) == 1
        assert result[0].ip_addresses == ["20.0.0.10", "20.0.0.11", "20.0.0.12"]


# ---------------------------------------------------------------------------
# Container Instance tests
# ---------------------------------------------------------------------------

class TestCollectAzureContainerInstances:
    """Tests for collect_azure_container_instances."""

    def test_container_instance_with_ip(self):
        """Container instance with IP is discovered."""
        client = MagicMock()

        client.container_groups.list.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.ContainerInstance/containerGroups/ci-web"),
                name="ci-web",
                location="eastus",
                tags={"env": "prod"},
                ip_address=SimpleNamespace(ip="10.0.0.100"),
                os_type="Linux",
                provisioning_state="Succeeded",
                containers=[SimpleNamespace(name="web"), SimpleNamespace(name="sidecar")],
            ),
        ]

        result = collect_azure_container_instances(client, "sub1")

        assert len(result) == 1
        ci = result[0]
        assert ci.resource_type == "azure-container-instance"
        assert ci.ip_addresses == ["10.0.0.100"]
        assert ci.details["os_type"] == "Linux"
        assert ci.details["container_count"] == 2

    def test_container_instance_no_ip(self):
        """Container instance without IP has empty ip_addresses."""
        client = MagicMock()

        client.container_groups.list.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.ContainerInstance/containerGroups/ci-noip"),
                name="ci-noip",
                location="eastus",
                tags=None,
                ip_address=None,
                os_type="Linux",
                provisioning_state="Succeeded",
                containers=[SimpleNamespace(name="worker")],
            ),
        ]

        result = collect_azure_container_instances(client, "sub1")

        assert len(result) == 1
        assert result[0].ip_addresses == []


# ---------------------------------------------------------------------------
# Container Apps tests
# ---------------------------------------------------------------------------

class TestCollectAzureContainerApps:
    """Tests for collect_azure_container_apps."""

    def test_container_apps_missing_sdk_returns_empty(self):
        """When azure.mgmt.appcontainers is not installed, returns []."""
        with patch.dict(sys.modules, {"azure.mgmt.appcontainers": None}):
            # Force ImportError by removing the module
            result = collect_azure_container_apps("sub1")
            assert result == []

    def test_container_apps_with_client(self):
        """Container Apps with pre-created client discovers apps."""
        client = MagicMock()

        client.container_apps.list_by_subscription.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.App/containerApps/ca-web"),
                name="ca-web",
                location="eastus",
                tags={"env": "prod"},
                managed_environment_id="/envs/env-prod",
                provisioning_state="Succeeded",
            ),
        ]

        result = collect_azure_container_apps_with_client(client, "sub1")

        assert len(result) == 1
        ca = result[0]
        assert ca.resource_type == "azure-container-app"
        assert ca.ip_addresses == []
        assert ca.details["managed_environment_id"] == "/envs/env-prod"

    def test_container_apps_none_client_returns_empty(self):
        """None client (SDK not installed) returns empty list."""
        result = collect_azure_container_apps_with_client(None, "sub1")
        assert result == []


# ---------------------------------------------------------------------------
# AKS tests
# ---------------------------------------------------------------------------

class TestCollectAzureAksClusters:
    """Tests for collect_azure_aks_clusters."""

    def test_aks_cluster_collection(self):
        """AKS cluster with agent pools discovered."""
        client = MagicMock()

        client.managed_clusters.list.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.ContainerService/managedClusters/aks-prod"),
                name="aks-prod",
                location="eastus",
                tags={"env": "prod"},
                kubernetes_version="1.28.3",
                fqdn="aks-prod-dns.hcp.eastus.azmk8s.io",
                agent_pool_profiles=[
                    SimpleNamespace(count=3),
                    SimpleNamespace(count=2),
                ],
            ),
        ]

        result = collect_azure_aks_clusters(client, "sub1")

        assert len(result) == 1
        aks = result[0]
        assert aks.resource_type == "azure-aks"
        assert aks.ip_addresses == []
        assert aks.details["kubernetes_version"] == "1.28.3"
        assert aks.details["node_count"] == 5
        assert aks.details["fqdn"] == "aks-prod-dns.hcp.eastus.azmk8s.io"

    def test_aks_no_agent_pools(self):
        """AKS cluster with no agent pools has node_count=0."""
        client = MagicMock()

        client.managed_clusters.list.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.ContainerService/managedClusters/aks-empty"),
                name="aks-empty",
                location="eastus",
                tags=None,
                kubernetes_version="1.27.0",
                fqdn="",
                agent_pool_profiles=None,
            ),
        ]

        result = collect_azure_aks_clusters(client, "sub1")

        assert len(result) == 1
        assert result[0].details["node_count"] == 0


# ---------------------------------------------------------------------------
# API Management tests
# ---------------------------------------------------------------------------

class TestCollectAzureApiManagement:
    """Tests for collect_azure_api_management."""

    def test_api_management_with_ips(self):
        """API Management with public and private IPs discovered."""
        client = MagicMock()

        client.api_management_service.list.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.ApiManagement/service/apim-prod"),
                name="apim-prod",
                location="eastus",
                tags={"env": "prod"},
                public_ip_addresses=["20.0.0.100"],
                private_ip_addresses=["10.0.0.50"],
                sku=SimpleNamespace(name="Premium"),
                gateway_url="https://apim-prod.azure-api.net",
            ),
        ]

        result = collect_azure_api_management(client, "sub1")

        assert len(result) == 1
        apim = result[0]
        assert apim.resource_type == "azure-api-management"
        assert apim.ip_addresses == ["20.0.0.100", "10.0.0.50"]
        assert apim.details["sku_name"] == "Premium"
        assert apim.details["gateway_url"] == "https://apim-prod.azure-api.net"

    def test_api_management_no_ips(self):
        """API Management without IPs has empty ip_addresses."""
        client = MagicMock()

        client.api_management_service.list.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.ApiManagement/service/apim-dev"),
                name="apim-dev",
                location="eastus",
                tags=None,
                public_ip_addresses=None,
                private_ip_addresses=None,
                sku=SimpleNamespace(name="Developer"),
                gateway_url="https://apim-dev.azure-api.net",
            ),
        ]

        result = collect_azure_api_management(client, "sub1")

        assert len(result) == 1
        assert result[0].ip_addresses == []
