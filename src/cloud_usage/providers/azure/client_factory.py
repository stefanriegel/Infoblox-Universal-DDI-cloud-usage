"""Per-subscription Azure SDK client factory.

Creates all Azure management clients needed for resource discovery
within a single subscription. Clients are grouped in an AzureClients
dataclass for easy passing to collector modules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AzureClients:
    """All Azure management clients for a single subscription.

    Each field holds the management client instance for that service,
    or None if the SDK package is not installed (optional dependency).

    Args:
        compute: ComputeManagementClient for VMs, VMSS, disks.
        network: NetworkManagementClient for VNets, NICs, NSGs, LBs.
        resource: ResourceManagementClient for resource groups.
        dns: DnsManagementClient for public DNS zones.
        privatedns: PrivateDnsManagementClient for private DNS zones.
        storage: StorageManagementClient for storage accounts.
        sql: SqlManagementClient for Azure SQL databases.
        cosmosdb: CosmosDBManagementClient for Cosmos DB accounts.
        mysql: MySQLManagementClient for MySQL Flexible Servers.
        postgresql: PostgreSQLManagementClient for PostgreSQL Flexible Servers.
        redis: RedisManagementClient for Redis Cache.
        web: WebSiteManagementClient for App Service / Functions.
        container: ContainerInstanceManagementClient for Container Instances.
        containerservice: ContainerServiceClient for AKS.
        apimanagement: ApiManagementClient for API Management.
        trafficmanager: TrafficManagerManagementClient for Traffic Manager.
        mgmt_groups: ManagementGroupsAPI for management group listing.
        subscription: SubscriptionClient for subscription metadata.
        appcontainers: ContainerAppsAPIClient for Container Apps.
    """

    compute: Any | None = None
    network: Any | None = None
    resource: Any | None = None
    dns: Any | None = None
    privatedns: Any | None = None
    storage: Any | None = None
    sql: Any | None = None
    cosmosdb: Any | None = None
    mysql: Any | None = None
    postgresql: Any | None = None
    redis: Any | None = None
    web: Any | None = None
    container: Any | None = None
    containerservice: Any | None = None
    apimanagement: Any | None = None
    trafficmanager: Any | None = None
    mgmt_groups: Any | None = None
    subscription: Any | None = None
    appcontainers: Any | None = None


def _try_create(name: str, factory_fn) -> Any | None:
    """Attempt to create a client, returning None on ImportError.

    Args:
        name: Human-readable client name for logging.
        factory_fn: Callable that creates and returns the client.

    Returns:
        The client instance, or None if import fails.
    """
    try:
        return factory_fn()
    except ImportError:
        logger.debug("Optional Azure SDK package not installed for %s", name)
        return None
    except Exception:
        logger.debug("Failed to create %s client", name, exc_info=True)
        return None


def create_subscription_clients(credential, subscription_id: str) -> AzureClients:
    """Create all Azure management clients for a single subscription.

    Each client is created independently with try/except. If an SDK
    package is not installed, that client field is set to None and a
    debug message is logged.

    Args:
        credential: Azure credential object (DefaultAzureCredential or similar).
        subscription_id: Azure subscription GUID to bind clients to.

    Returns:
        AzureClients dataclass with all available management clients.
    """
    clients = AzureClients()

    clients.compute = _try_create("compute", lambda: _create_compute(credential, subscription_id))
    clients.network = _try_create("network", lambda: _create_network(credential, subscription_id))
    clients.resource = _try_create("resource", lambda: _create_resource(credential, subscription_id))
    clients.dns = _try_create("dns", lambda: _create_dns(credential, subscription_id))
    clients.privatedns = _try_create("privatedns", lambda: _create_privatedns(credential, subscription_id))
    clients.storage = _try_create("storage", lambda: _create_storage(credential, subscription_id))
    clients.sql = _try_create("sql", lambda: _create_sql(credential, subscription_id))
    clients.cosmosdb = _try_create("cosmosdb", lambda: _create_cosmosdb(credential, subscription_id))
    clients.mysql = _try_create("mysql", lambda: _create_mysql(credential, subscription_id))
    clients.postgresql = _try_create("postgresql", lambda: _create_postgresql(credential, subscription_id))
    clients.redis = _try_create("redis", lambda: _create_redis(credential, subscription_id))
    clients.web = _try_create("web", lambda: _create_web(credential, subscription_id))
    clients.container = _try_create("container", lambda: _create_container(credential, subscription_id))
    clients.containerservice = _try_create("containerservice", lambda: _create_containerservice(credential, subscription_id))
    clients.apimanagement = _try_create("apimanagement", lambda: _create_apimanagement(credential, subscription_id))
    clients.trafficmanager = _try_create("trafficmanager", lambda: _create_trafficmanager(credential, subscription_id))
    clients.mgmt_groups = _try_create("mgmt_groups", lambda: _create_mgmt_groups(credential))
    clients.subscription = _try_create("subscription", lambda: _create_subscription(credential))
    clients.appcontainers = _try_create("appcontainers", lambda: _create_appcontainers(credential, subscription_id))

    return clients


# --- Individual client factory functions ---


def _create_compute(credential, subscription_id: str):
    from azure.mgmt.compute import ComputeManagementClient
    return ComputeManagementClient(credential, subscription_id)


def _create_network(credential, subscription_id: str):
    from azure.mgmt.network import NetworkManagementClient
    return NetworkManagementClient(credential, subscription_id)


def _create_resource(credential, subscription_id: str):
    from azure.mgmt.resource import ResourceManagementClient
    return ResourceManagementClient(credential, subscription_id)


def _create_dns(credential, subscription_id: str):
    from azure.mgmt.dns import DnsManagementClient
    return DnsManagementClient(credential, subscription_id)


def _create_privatedns(credential, subscription_id: str):
    from azure.mgmt.privatedns import PrivateDnsManagementClient
    return PrivateDnsManagementClient(credential, subscription_id)


def _create_storage(credential, subscription_id: str):
    from azure.mgmt.storage import StorageManagementClient
    return StorageManagementClient(credential, subscription_id)


def _create_sql(credential, subscription_id: str):
    from azure.mgmt.sql import SqlManagementClient
    return SqlManagementClient(credential, subscription_id)


def _create_cosmosdb(credential, subscription_id: str):
    from azure.mgmt.cosmosdb import CosmosDBManagementClient
    return CosmosDBManagementClient(credential, subscription_id)


def _create_mysql(credential, subscription_id: str):
    from azure.mgmt.rdbms.mysql_flexibleservers import MySQLManagementClient
    return MySQLManagementClient(credential, subscription_id)


def _create_postgresql(credential, subscription_id: str):
    from azure.mgmt.rdbms.postgresql_flexibleservers import PostgreSQLFlexibleManagementClient
    return PostgreSQLFlexibleManagementClient(credential, subscription_id)


def _create_redis(credential, subscription_id: str):
    from azure.mgmt.redis import RedisManagementClient
    return RedisManagementClient(credential, subscription_id)


def _create_web(credential, subscription_id: str):
    from azure.mgmt.web import WebSiteManagementClient
    return WebSiteManagementClient(credential, subscription_id)


def _create_container(credential, subscription_id: str):
    from azure.mgmt.containerinstance import ContainerInstanceManagementClient
    return ContainerInstanceManagementClient(credential, subscription_id)


def _create_containerservice(credential, subscription_id: str):
    from azure.mgmt.containerservice import ContainerServiceClient
    return ContainerServiceClient(credential, subscription_id)


def _create_apimanagement(credential, subscription_id: str):
    from azure.mgmt.apimanagement import ApiManagementClient
    return ApiManagementClient(credential, subscription_id)


def _create_trafficmanager(credential, subscription_id: str):
    from azure.mgmt.trafficmanager import TrafficManagerManagementClient
    return TrafficManagerManagementClient(credential, subscription_id)


def _create_mgmt_groups(credential):
    from azure.mgmt.managementgroups import ManagementGroupsAPI
    return ManagementGroupsAPI(credential)


def _create_subscription(credential):
    from azure.mgmt.resource import SubscriptionClient
    return SubscriptionClient(credential)


def _create_appcontainers(credential, subscription_id: str):
    from azure.mgmt.appcontainers import ContainerAppsAPIClient
    return ContainerAppsAPIClient(credential, subscription_id)
