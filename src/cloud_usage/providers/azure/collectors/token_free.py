"""Azure token-free resource collectors.

Discovers VM Disks, Storage Accounts, Storage Containers, Management Groups,
Traffic Manager Profiles, Network Watchers, NSGs, and Resource Groups. These
resources are discovered for the audit trail but never counted toward tokens.
They appear in the detail sheet with counted=False and a skip_reason.
"""

from __future__ import annotations

import logging
from typing import Any

from cloud_usage.providers.azure.utils import _extract_resource_group
from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


@retry_with_backoff(max_retries=3)
def collect_azure_disks(
    compute_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all VM Disks in a subscription (token-free, no IPs).

    Uses compute_client.disks.list() for subscription-level enumeration.
    Disks have no IP addresses and are categorized as token-free.

    Args:
        compute_client: Azure ComputeManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-disk".
    """
    resources: list[CloudResource] = []

    for disk in compute_client.disks.list():
        rg = _extract_resource_group(disk.id)

        resources.append(
            CloudResource(
                resource_id=disk.id,
                resource_type="azure-disk",
                provider="azure",
                account_id=subscription_id,
                region=disk.location,
                name=disk.name,
                ip_addresses=[],
                tags=dict(disk.tags) if disk.tags else {},
                details={
                    "resource_group": rg,
                    "disk_size_gb": disk.disk_size_gb or 0,
                    "os_type": disk.os_type or "" if hasattr(disk, "os_type") else "",
                    "provisioning_state": disk.provisioning_state or "",
                },
            )
        )

    logger.debug(
        "Discovered %d VM Disks in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_storage_accounts(
    storage_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all Storage Accounts in a subscription (token-free, no IPs).

    Uses storage_client.storage_accounts.list() for subscription-level
    enumeration. Storage accounts have no IP addresses.

    Args:
        storage_client: Azure StorageManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-storage-account".
    """
    resources: list[CloudResource] = []

    for account in storage_client.storage_accounts.list():
        rg = _extract_resource_group(account.id)

        kind = account.kind or "" if hasattr(account, "kind") else ""
        sku_name = ""
        if hasattr(account, "sku") and account.sku:
            sku_name = account.sku.name or ""
        access_tier = account.access_tier or "" if hasattr(account, "access_tier") else ""

        resources.append(
            CloudResource(
                resource_id=account.id,
                resource_type="azure-storage-account",
                provider="azure",
                account_id=subscription_id,
                region=account.location,
                name=account.name,
                ip_addresses=[],
                tags=dict(account.tags) if account.tags else {},
                details={
                    "resource_group": rg,
                    "kind": kind,
                    "sku_name": sku_name,
                    "access_tier": access_tier,
                },
            )
        )

    logger.debug(
        "Discovered %d Storage Accounts in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_storage_containers(
    storage_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all Storage Containers across all storage accounts (token-free).

    For each storage account, calls storage_client.blob_containers.list()
    with per-account error isolation (some accounts may have blob access
    disabled).

    Args:
        storage_client: Azure StorageManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-storage-container".
    """
    resources: list[CloudResource] = []

    for account in storage_client.storage_accounts.list():
        rg = _extract_resource_group(account.id)
        account_name = account.name

        if not rg or not account_name:
            continue

        try:
            for container in storage_client.blob_containers.list(rg, account_name):
                resource_id = container.id or (
                    f"/subscriptions/{subscription_id}/resourceGroups/{rg}"
                    f"/providers/Microsoft.Storage/storageAccounts/{account_name}"
                    f"/blobServices/default/containers/{container.name}"
                )

                resources.append(
                    CloudResource(
                        resource_id=resource_id,
                        resource_type="azure-storage-container",
                        provider="azure",
                        account_id=subscription_id,
                        region=account.location,
                        name=container.name,
                        ip_addresses=[],
                        tags={},
                        details={
                            "resource_group": rg,
                            "storage_account_name": account_name,
                        },
                    )
                )
        except Exception:
            logger.warning(
                "Failed to list blob containers for storage account %s/%s",
                rg,
                account_name,
                exc_info=True,
            )

    logger.debug(
        "Discovered %d Storage Containers in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_management_groups(
    mgmt_groups_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all Management Groups (token-free, tenant-level).

    Uses mgmt_groups_client.management_groups.list() which is a tenant-level
    API. Results are attributed to the subscription that ran the query.
    Region is "global" since management groups are not region-scoped.

    Args:
        mgmt_groups_client: Azure ManagementGroupsAPI.
        subscription_id: Azure subscription ID (for attribution).

    Returns:
        List of CloudResource with resource_type="azure-management-group".
    """
    resources: list[CloudResource] = []

    for group in mgmt_groups_client.management_groups.list():
        display_name = ""
        tenant_id = ""
        if group.properties:
            display_name = group.properties.display_name or "" if hasattr(group.properties, "display_name") else ""
            tenant_id = group.properties.tenant_id or "" if hasattr(group.properties, "tenant_id") else ""

        resources.append(
            CloudResource(
                resource_id=group.id,
                resource_type="azure-management-group",
                provider="azure",
                account_id=subscription_id,
                region="global",
                name=group.name,
                ip_addresses=[],
                tags={},
                details={
                    "display_name": display_name,
                    "tenant_id": tenant_id,
                },
            )
        )

    logger.debug(
        "Discovered %d Management Groups attributed to subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_traffic_manager_profiles(
    trafficmanager_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all Traffic Manager Profiles in a subscription (token-free).

    Uses trafficmanager_client.profiles.list_by_subscription() for
    subscription-level enumeration.

    Args:
        trafficmanager_client: Azure TrafficManagerManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-traffic-manager".
    """
    resources: list[CloudResource] = []

    for profile in trafficmanager_client.profiles.list_by_subscription():
        rg = _extract_resource_group(profile.id)

        dns_config = ""
        if hasattr(profile, "dns_config") and profile.dns_config:
            dns_config = profile.dns_config.relative_name or "" if hasattr(profile.dns_config, "relative_name") else ""

        traffic_routing_method = ""
        if hasattr(profile, "traffic_routing_method") and profile.traffic_routing_method:
            traffic_routing_method = str(profile.traffic_routing_method)

        resources.append(
            CloudResource(
                resource_id=profile.id,
                resource_type="azure-traffic-manager",
                provider="azure",
                account_id=subscription_id,
                region="global",
                name=profile.name,
                ip_addresses=[],
                tags=dict(profile.tags) if profile.tags else {},
                details={
                    "resource_group": rg,
                    "dns_config": dns_config,
                    "traffic_routing_method": traffic_routing_method,
                },
            )
        )

    logger.debug(
        "Discovered %d Traffic Manager Profiles in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_network_watchers(
    network_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all Network Watchers in a subscription (token-free).

    Uses network_client.network_watchers.list_all() for subscription-level
    enumeration.

    Args:
        network_client: Azure NetworkManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-network-watcher".
    """
    resources: list[CloudResource] = []

    for watcher in network_client.network_watchers.list_all():
        rg = _extract_resource_group(watcher.id)

        resources.append(
            CloudResource(
                resource_id=watcher.id,
                resource_type="azure-network-watcher",
                provider="azure",
                account_id=subscription_id,
                region=watcher.location,
                name=watcher.name,
                ip_addresses=[],
                tags=dict(watcher.tags) if watcher.tags else {},
                details={
                    "resource_group": rg,
                    "provisioning_state": watcher.provisioning_state or "",
                },
            )
        )

    logger.debug(
        "Discovered %d Network Watchers in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_nsgs(
    network_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all Network Security Groups in a subscription (token-free).

    Uses network_client.network_security_groups.list_all() for subscription-level
    enumeration. NSGs are discovered for audit trail per CONTEXT.md.

    Args:
        network_client: Azure NetworkManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-nsg".
    """
    resources: list[CloudResource] = []

    for nsg in network_client.network_security_groups.list_all():
        rg = _extract_resource_group(nsg.id)

        security_rules = nsg.security_rules or []
        default_rules = nsg.default_security_rules or []
        rule_count = len(security_rules) + len(default_rules)

        resources.append(
            CloudResource(
                resource_id=nsg.id,
                resource_type="azure-nsg",
                provider="azure",
                account_id=subscription_id,
                region=nsg.location,
                name=nsg.name,
                ip_addresses=[],
                tags=dict(nsg.tags) if nsg.tags else {},
                details={
                    "resource_group": rg,
                    "rule_count": rule_count,
                },
            )
        )

    logger.debug(
        "Discovered %d NSGs in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_resource_groups(
    resource_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all Resource Groups in a subscription (token-free).

    Uses resource_client.resource_groups.list() for subscription-level
    enumeration. Resource groups are discovered for audit trail per CONTEXT.md.

    Args:
        resource_client: Azure ResourceManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-resource-group".
    """
    resources: list[CloudResource] = []

    for rg_obj in resource_client.resource_groups.list():
        resources.append(
            CloudResource(
                resource_id=rg_obj.id,
                resource_type="azure-resource-group",
                provider="azure",
                account_id=subscription_id,
                region=rg_obj.location,
                name=rg_obj.name,
                ip_addresses=[],
                tags=dict(rg_obj.tags) if rg_obj.tags else {},
                details={
                    "provisioning_state": rg_obj.properties.provisioning_state or "" if rg_obj.properties else "",
                },
            )
        )

    logger.debug(
        "Discovered %d Resource Groups in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources
