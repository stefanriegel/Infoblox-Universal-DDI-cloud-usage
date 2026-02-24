"""Azure database resource collectors.

Discovers Azure SQL databases (and servers), Cosmos DB accounts, MySQL
Flexible Servers, PostgreSQL Flexible Servers, and Redis Cache instances.
All PaaS database resources set ip_addresses=[] because IPs are attributed
via private endpoints collected separately (per CONTEXT.md PaaS IP
extraction decision).
"""

from __future__ import annotations

import logging
from typing import Any

from cloud_usage.providers.azure.utils import _extract_resource_group
from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


@retry_with_backoff(max_retries=3)
def collect_azure_sql_databases(
    sql_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover Azure SQL servers and their databases.

    Lists SQL servers at subscription level, then databases per server.
    Creates a parent resource for each SQL Server (resource_type="azure-sql-server")
    and child resources for each database (resource_type="azure-sql-db").

    IPs are attributed via private endpoints collected separately.

    Args:
        sql_client: Azure SqlManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource for SQL servers and databases.
    """
    resources: list[CloudResource] = []

    for server in sql_client.servers.list():
        rg = _extract_resource_group(server.id)
        server_name = server.name
        fqdn = server.fully_qualified_domain_name or ""

        # Create parent SQL Server resource
        resources.append(
            CloudResource(
                resource_id=server.id,
                resource_type="azure-sql-server",
                provider="azure",
                account_id=subscription_id,
                region=server.location,
                name=server_name,
                ip_addresses=[],
                tags=dict(server.tags) if server.tags else {},
                details={
                    "resource_group": rg,
                    "server_fqdn": fqdn,
                },
            )
        )

        # List databases for this server
        if not rg or not server_name:
            continue

        try:
            for db in sql_client.databases.list_by_server(rg, server_name):
                resources.append(
                    CloudResource(
                        resource_id=db.id,
                        resource_type="azure-sql-db",
                        provider="azure",
                        account_id=subscription_id,
                        region=db.location or server.location,
                        name=db.name,
                        ip_addresses=[],
                        tags=dict(db.tags) if db.tags else {},
                        details={
                            "resource_group": rg,
                            "server_name": server_name,
                            "server_fqdn": fqdn,
                            "edition": db.edition or "" if hasattr(db, "edition") else "",
                            "status": db.status or "" if hasattr(db, "status") else "",
                        },
                    )
                )
        except Exception:
            logger.warning(
                "Failed to list databases for SQL server %s/%s",
                rg,
                server_name,
                exc_info=True,
            )

    logger.debug(
        "Discovered %d SQL resources in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_cosmosdb_accounts(
    cosmosdb_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover Cosmos DB accounts in a subscription.

    Uses cosmosdb_client.database_accounts.list() for subscription-level
    enumeration. IPs are attributed via private endpoints.

    Args:
        cosmosdb_client: Azure CosmosDBManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-cosmosdb".
    """
    resources: list[CloudResource] = []

    for account in cosmosdb_client.database_accounts.list():
        rg = _extract_resource_group(account.id)

        kind = account.kind or "" if hasattr(account, "kind") else ""
        consistency_policy = ""
        if hasattr(account, "consistency_policy") and account.consistency_policy:
            consistency_policy = account.consistency_policy.default_consistency_level or ""

        resources.append(
            CloudResource(
                resource_id=account.id,
                resource_type="azure-cosmosdb",
                provider="azure",
                account_id=subscription_id,
                region=account.location,
                name=account.name,
                ip_addresses=[],
                tags=dict(account.tags) if account.tags else {},
                details={
                    "resource_group": rg,
                    "kind": kind,
                    "consistency_policy": consistency_policy,
                    "document_endpoint": account.document_endpoint or "" if hasattr(account, "document_endpoint") else "",
                },
            )
        )

    logger.debug(
        "Discovered %d Cosmos DB accounts in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_mysql_servers(
    mysql_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover MySQL Flexible Servers in a subscription.

    Uses mysql_client.servers.list() for subscription-level enumeration
    (MySQL Flexible Servers API). IPs are attributed via private endpoints.

    Args:
        mysql_client: Azure MySQLManagementClient (Flexible Servers).
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-mysql".
    """
    resources: list[CloudResource] = []

    for server in mysql_client.servers.list():
        rg = _extract_resource_group(server.id)

        resources.append(
            CloudResource(
                resource_id=server.id,
                resource_type="azure-mysql",
                provider="azure",
                account_id=subscription_id,
                region=server.location,
                name=server.name,
                ip_addresses=[],
                tags=dict(server.tags) if server.tags else {},
                details={
                    "resource_group": rg,
                    "fully_qualified_domain_name": server.fully_qualified_domain_name or "",
                    "state": server.state or "" if hasattr(server, "state") else "",
                    "version": server.version or "" if hasattr(server, "version") else "",
                },
            )
        )

    logger.debug(
        "Discovered %d MySQL servers in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_postgresql_servers(
    postgresql_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover PostgreSQL Flexible Servers in a subscription.

    Uses postgresql_client.servers.list() for subscription-level enumeration
    (PostgreSQL Flexible Servers API). IPs are attributed via private endpoints.

    Args:
        postgresql_client: Azure PostgreSQLFlexibleManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-postgresql".
    """
    resources: list[CloudResource] = []

    for server in postgresql_client.servers.list():
        rg = _extract_resource_group(server.id)

        resources.append(
            CloudResource(
                resource_id=server.id,
                resource_type="azure-postgresql",
                provider="azure",
                account_id=subscription_id,
                region=server.location,
                name=server.name,
                ip_addresses=[],
                tags=dict(server.tags) if server.tags else {},
                details={
                    "resource_group": rg,
                    "fully_qualified_domain_name": server.fully_qualified_domain_name or "",
                    "state": server.state or "" if hasattr(server, "state") else "",
                    "version": server.version or "" if hasattr(server, "version") else "",
                },
            )
        )

    logger.debug(
        "Discovered %d PostgreSQL servers in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_redis_caches(
    redis_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover Redis Cache instances in a subscription.

    Uses redis_client.redis.list_by_subscription() for subscription-level
    enumeration. For Redis, host_name is a DNS name so ip_addresses=[]
    unless static_ip is set.

    Args:
        redis_client: Azure RedisManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-redis".
    """
    resources: list[CloudResource] = []

    for cache in redis_client.redis.list_by_subscription():
        rg = _extract_resource_group(cache.id)

        ip_addresses: list[str] = []
        static_ip = getattr(cache, "static_ip", None)
        if static_ip:
            ip_addresses.append(static_ip)

        host_name = cache.host_name or "" if hasattr(cache, "host_name") else ""
        port = cache.port or 0 if hasattr(cache, "port") else 0
        ssl_port = cache.ssl_port or 0 if hasattr(cache, "ssl_port") else 0

        sku_name = ""
        if hasattr(cache, "sku") and cache.sku:
            sku_name = cache.sku.name or ""

        resources.append(
            CloudResource(
                resource_id=cache.id,
                resource_type="azure-redis",
                provider="azure",
                account_id=subscription_id,
                region=cache.location,
                name=cache.name,
                ip_addresses=ip_addresses,
                tags=dict(cache.tags) if cache.tags else {},
                details={
                    "resource_group": rg,
                    "host_name": host_name,
                    "port": port,
                    "ssl_port": ssl_port,
                    "sku_name": sku_name,
                },
            )
        )

    logger.debug(
        "Discovered %d Redis caches in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources
