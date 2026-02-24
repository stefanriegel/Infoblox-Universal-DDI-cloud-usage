"""Azure PaaS and container resource collectors.

Discovers App Services, Azure Functions, Container Instances, Container
Apps, AKS clusters, and API Management instances. App Services and
Functions have inbound + outbound IP extraction per CONTEXT.md.
"""

from __future__ import annotations

import logging
from typing import Any

from cloud_usage.providers.azure.utils import _extract_resource_group
from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


@retry_with_backoff(max_retries=3)
def collect_azure_app_services(
    web_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover App Services (Web Apps) in a subscription.

    Uses web_client.web_apps.list() for subscription-level enumeration.
    Filters OUT resources where kind contains "functionapp" (Functions
    are handled separately). Per CONTEXT.md: discover both inbound and
    outbound IPs.

    Args:
        web_client: Azure WebSiteManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-app-service".
    """
    resources: list[CloudResource] = []

    for app in web_client.web_apps.list():
        kind = app.kind or "" if hasattr(app, "kind") else ""

        # Filter out Functions (handled by collect_azure_functions)
        if "functionapp" in kind.lower():
            continue

        rg = _extract_resource_group(app.id)
        ip_addresses: list[str] = _extract_web_app_ips(app)

        resources.append(
            CloudResource(
                resource_id=app.id,
                resource_type="azure-app-service",
                provider="azure",
                account_id=subscription_id,
                region=app.location,
                name=app.name,
                ip_addresses=ip_addresses,
                tags=dict(app.tags) if app.tags else {},
                details={
                    "resource_group": rg,
                    "kind": kind,
                    "state": app.state or "" if hasattr(app, "state") else "",
                    "default_host_name": app.default_host_name or "" if hasattr(app, "default_host_name") else "",
                },
            )
        )

    logger.debug(
        "Discovered %d App Services in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_functions(
    web_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover Azure Functions in a subscription.

    Uses the same web_client.web_apps.list() but filters FOR kind
    containing "functionapp". Per CONTEXT.md: discover both inbound
    and outbound IPs.

    Args:
        web_client: Azure WebSiteManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-function".
    """
    resources: list[CloudResource] = []

    for app in web_client.web_apps.list():
        kind = app.kind or "" if hasattr(app, "kind") else ""

        # Only include Functions
        if "functionapp" not in kind.lower():
            continue

        rg = _extract_resource_group(app.id)
        ip_addresses: list[str] = _extract_web_app_ips(app)

        resources.append(
            CloudResource(
                resource_id=app.id,
                resource_type="azure-function",
                provider="azure",
                account_id=subscription_id,
                region=app.location,
                name=app.name,
                ip_addresses=ip_addresses,
                tags=dict(app.tags) if app.tags else {},
                details={
                    "resource_group": rg,
                    "kind": kind,
                    "state": app.state or "" if hasattr(app, "state") else "",
                    "default_host_name": app.default_host_name or "" if hasattr(app, "default_host_name") else "",
                },
            )
        )

    logger.debug(
        "Discovered %d Azure Functions in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


def _extract_web_app_ips(app: Any) -> list[str]:
    """Extract inbound and outbound IPs from an App Service or Function.

    Collects inbound IP from inbound_ip_addresses and outbound IPs from
    outbound_ip_addresses (comma-separated string). Deduplicates IPs.

    Args:
        app: Azure Web App SDK object.

    Returns:
        List of unique IP address strings.
    """
    ips: list[str] = []

    # Inbound IPs
    inbound = getattr(app, "inbound_ip_addresses", None)
    if inbound:
        for ip in inbound.split(","):
            ip = ip.strip()
            if ip and ip not in ips:
                ips.append(ip)

    # Outbound IPs (comma-separated string)
    outbound = getattr(app, "outbound_ip_addresses", None)
    if outbound:
        for ip in outbound.split(","):
            ip = ip.strip()
            if ip and ip not in ips:
                ips.append(ip)

    return ips


@retry_with_backoff(max_retries=3)
def collect_azure_container_instances(
    container_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover Container Instances (container groups) in a subscription.

    Uses container_client.container_groups.list() for subscription-level
    enumeration. Extracts IP from container_group.ip_address.ip if present.

    Args:
        container_client: Azure ContainerInstanceManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-container-instance".
    """
    resources: list[CloudResource] = []

    for group in container_client.container_groups.list():
        rg = _extract_resource_group(group.id)

        ip_addresses: list[str] = []
        if group.ip_address and group.ip_address.ip:
            ip_addresses.append(group.ip_address.ip)

        os_type = group.os_type or "" if hasattr(group, "os_type") else ""
        provisioning_state = group.provisioning_state or "" if hasattr(group, "provisioning_state") else ""
        containers = getattr(group, "containers", None) or []

        resources.append(
            CloudResource(
                resource_id=group.id,
                resource_type="azure-container-instance",
                provider="azure",
                account_id=subscription_id,
                region=group.location,
                name=group.name,
                ip_addresses=ip_addresses,
                tags=dict(group.tags) if group.tags else {},
                details={
                    "resource_group": rg,
                    "os_type": os_type,
                    "provisioning_state": provisioning_state,
                    "container_count": len(containers),
                },
            )
        )

    logger.debug(
        "Discovered %d Container Instances in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


def collect_azure_container_apps(
    subscription_id: str,
) -> list[CloudResource]:
    """Discover Container Apps in a subscription.

    Attempts to import azure.mgmt.appcontainers. If the import fails,
    logs debug and returns [] (soft dependency per RESEARCH.md Open
    Question 3). No @retry_with_backoff since the function handles
    client creation internally.

    Args:
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-container-app",
        or empty list if the SDK package is not available.
    """
    try:
        from azure.mgmt.appcontainers import ContainerAppsAPIClient
    except ImportError:
        logger.debug(
            "azure-mgmt-appcontainers not installed; skipping Container Apps"
        )
        return []

    # If we get here, SDK is available but we need a credential + client.
    # In practice, collect_azure_container_apps is called with a pre-created
    # client from the client factory. This function signature allows
    # graceful degradation when the SDK is missing.
    # The actual collection is done by _collect_container_apps_with_client.
    return []


def collect_azure_container_apps_with_client(
    appcontainers_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover Container Apps using a pre-created client.

    Called when the client factory successfully created an appcontainers
    client. Container Apps use managed ingress so ip_addresses=[].

    Args:
        appcontainers_client: Azure ContainerAppsAPIClient, or None if
            the SDK is not installed.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-container-app".
    """
    if appcontainers_client is None:
        logger.debug(
            "Container Apps client not available; skipping Container Apps"
        )
        return []

    resources: list[CloudResource] = []

    try:
        for app in appcontainers_client.container_apps.list_by_subscription():
            rg = _extract_resource_group(app.id)

            managed_env_id = ""
            if hasattr(app, "managed_environment_id"):
                managed_env_id = app.managed_environment_id or ""

            resources.append(
                CloudResource(
                    resource_id=app.id,
                    resource_type="azure-container-app",
                    provider="azure",
                    account_id=subscription_id,
                    region=app.location,
                    name=app.name,
                    ip_addresses=[],
                    tags=dict(app.tags) if app.tags else {},
                    details={
                        "resource_group": rg,
                        "managed_environment_id": managed_env_id,
                        "provisioning_state": app.provisioning_state or "" if hasattr(app, "provisioning_state") else "",
                    },
                )
            )
    except Exception:
        logger.warning(
            "Failed to list Container Apps in subscription %s",
            subscription_id,
            exc_info=True,
        )

    logger.debug(
        "Discovered %d Container Apps in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_aks_clusters(
    containerservice_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover AKS managed clusters in a subscription.

    Uses containerservice_client.managed_clusters.list() for subscription-level
    enumeration. ip_addresses=[] since underlying VMs/VMSS capture IPs.

    Args:
        containerservice_client: Azure ContainerServiceClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-aks".
    """
    resources: list[CloudResource] = []

    for cluster in containerservice_client.managed_clusters.list():
        rg = _extract_resource_group(cluster.id)

        # Sum node counts across agent pools
        node_count = 0
        for pool in (cluster.agent_pool_profiles or []):
            node_count += pool.count or 0

        fqdn = cluster.fqdn or "" if hasattr(cluster, "fqdn") else ""
        k8s_version = cluster.kubernetes_version or "" if hasattr(cluster, "kubernetes_version") else ""

        resources.append(
            CloudResource(
                resource_id=cluster.id,
                resource_type="azure-aks",
                provider="azure",
                account_id=subscription_id,
                region=cluster.location,
                name=cluster.name,
                ip_addresses=[],
                tags=dict(cluster.tags) if cluster.tags else {},
                details={
                    "resource_group": rg,
                    "kubernetes_version": k8s_version,
                    "node_count": node_count,
                    "fqdn": fqdn,
                },
            )
        )

    logger.debug(
        "Discovered %d AKS clusters in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_api_management(
    apimanagement_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover API Management instances in a subscription.

    Uses apimanagement_client.api_management_service.list() for
    subscription-level enumeration. Extracts public and private IPs.

    Args:
        apimanagement_client: Azure ApiManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-api-management".
    """
    resources: list[CloudResource] = []

    for service in apimanagement_client.api_management_service.list():
        rg = _extract_resource_group(service.id)

        ip_addresses: list[str] = []

        # Public IPs
        for ip in (getattr(service, "public_ip_addresses", None) or []):
            if ip and ip not in ip_addresses:
                ip_addresses.append(ip)

        # Private IPs
        for ip in (getattr(service, "private_ip_addresses", None) or []):
            if ip and ip not in ip_addresses:
                ip_addresses.append(ip)

        sku_name = ""
        if hasattr(service, "sku") and service.sku:
            sku_name = service.sku.name or ""

        gateway_url = getattr(service, "gateway_url", None) or ""

        resources.append(
            CloudResource(
                resource_id=service.id,
                resource_type="azure-api-management",
                provider="azure",
                account_id=subscription_id,
                region=service.location,
                name=service.name,
                ip_addresses=ip_addresses,
                tags=dict(service.tags) if service.tags else {},
                details={
                    "resource_group": rg,
                    "sku_name": sku_name,
                    "gateway_url": gateway_url,
                },
            )
        )

    logger.debug(
        "Discovered %d API Management instances in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources
