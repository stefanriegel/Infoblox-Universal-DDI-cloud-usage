"""Tests for Azure database resource collectors.

Uses unittest.mock to simulate Azure SDK client objects. Verifies that
SQL, Cosmos DB, MySQL, PostgreSQL, and Redis collectors produce
correctly-shaped CloudResource instances.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from cloud_usage.providers.azure.collectors.database import (
    collect_azure_cosmosdb_accounts,
    collect_azure_mysql_servers,
    collect_azure_postgresql_servers,
    collect_azure_redis_caches,
    collect_azure_sql_databases,
)
from cloud_usage.schema.resource import CloudResource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _arm_id(rg: str, provider_path: str) -> str:
    """Build a full ARM resource ID for tests."""
    return f"/subscriptions/sub1/resourceGroups/{rg}/providers/{provider_path}"


# ---------------------------------------------------------------------------
# SQL Database tests
# ---------------------------------------------------------------------------

class TestCollectAzureSqlDatabases:
    """Tests for collect_azure_sql_databases."""

    def test_sql_server_and_databases(self):
        """1 server with 2 databases yields 3 resources (server + 2 DBs)."""
        client = MagicMock()

        server = SimpleNamespace(
            id=_arm_id("rg1", "Microsoft.Sql/servers/sql-prod"),
            name="sql-prod",
            location="eastus",
            tags={"env": "prod"},
            fully_qualified_domain_name="sql-prod.database.windows.net",
        )
        client.servers.list.return_value = [server]

        db1 = SimpleNamespace(
            id=f"{server.id}/databases/db-main",
            name="db-main",
            location="eastus",
            tags=None,
            edition="Standard",
            status="Online",
        )
        db2 = SimpleNamespace(
            id=f"{server.id}/databases/db-analytics",
            name="db-analytics",
            location="eastus",
            tags={"team": "data"},
            edition="Premium",
            status="Online",
        )
        client.databases.list_by_server.return_value = [db1, db2]

        result = collect_azure_sql_databases(client, "sub1")

        assert len(result) == 3  # 1 server + 2 databases

        # SQL Server resource
        srv = result[0]
        assert srv.resource_type == "azure-sql-server"
        assert srv.provider == "azure"
        assert srv.ip_addresses == []
        assert srv.details["server_fqdn"] == "sql-prod.database.windows.net"
        assert srv.tags == {"env": "prod"}

        # Database resources
        d1 = result[1]
        assert d1.resource_type == "azure-sql-db"
        assert d1.name == "db-main"
        assert d1.details["server_name"] == "sql-prod"
        assert d1.details["edition"] == "Standard"
        assert d1.details["status"] == "Online"

        d2 = result[2]
        assert d2.name == "db-analytics"
        assert d2.details["edition"] == "Premium"

    def test_sql_server_with_no_databases(self):
        """Server with no databases yields only the server resource."""
        client = MagicMock()

        server = SimpleNamespace(
            id=_arm_id("rg1", "Microsoft.Sql/servers/sql-empty"),
            name="sql-empty",
            location="eastus",
            tags=None,
            fully_qualified_domain_name="sql-empty.database.windows.net",
        )
        client.servers.list.return_value = [server]
        client.databases.list_by_server.return_value = []

        result = collect_azure_sql_databases(client, "sub1")

        assert len(result) == 1
        assert result[0].resource_type == "azure-sql-server"

    def test_sql_no_servers(self):
        """No SQL servers returns empty list."""
        client = MagicMock()
        client.servers.list.return_value = []

        result = collect_azure_sql_databases(client, "sub1")
        assert result == []


# ---------------------------------------------------------------------------
# Cosmos DB tests
# ---------------------------------------------------------------------------

class TestCollectAzureCosmosdbAccounts:
    """Tests for collect_azure_cosmosdb_accounts."""

    def test_cosmosdb_collection(self):
        """Two Cosmos DB accounts are discovered."""
        client = MagicMock()

        client.database_accounts.list.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.DocumentDB/databaseAccounts/cosmos-prod"),
                name="cosmos-prod",
                location="eastus",
                tags={"env": "prod"},
                kind="GlobalDocumentDB",
                consistency_policy=SimpleNamespace(default_consistency_level="Session"),
                document_endpoint="https://cosmos-prod.documents.azure.com:443/",
            ),
            SimpleNamespace(
                id=_arm_id("rg2", "Microsoft.DocumentDB/databaseAccounts/cosmos-mongo"),
                name="cosmos-mongo",
                location="westeurope",
                tags=None,
                kind="MongoDB",
                consistency_policy=SimpleNamespace(default_consistency_level="BoundedStaleness"),
                document_endpoint="https://cosmos-mongo.documents.azure.com:443/",
            ),
        ]

        result = collect_azure_cosmosdb_accounts(client, "sub1")

        assert len(result) == 2
        assert all(r.resource_type == "azure-cosmosdb" for r in result)
        assert all(r.ip_addresses == [] for r in result)

        c1 = result[0]
        assert c1.details["kind"] == "GlobalDocumentDB"
        assert c1.details["consistency_policy"] == "Session"
        assert c1.details["document_endpoint"] == "https://cosmos-prod.documents.azure.com:443/"

        c2 = result[1]
        assert c2.details["kind"] == "MongoDB"


# ---------------------------------------------------------------------------
# MySQL tests
# ---------------------------------------------------------------------------

class TestCollectAzureMysqlServers:
    """Tests for collect_azure_mysql_servers."""

    def test_mysql_server_collection(self):
        """MySQL Flexible server is discovered."""
        client = MagicMock()

        client.servers.list.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.DBforMySQL/flexibleServers/mysql-prod"),
                name="mysql-prod",
                location="eastus",
                tags={"env": "prod"},
                fully_qualified_domain_name="mysql-prod.mysql.database.azure.com",
                state="Ready",
                version="8.0",
            ),
        ]

        result = collect_azure_mysql_servers(client, "sub1")

        assert len(result) == 1
        mysql = result[0]
        assert mysql.resource_type == "azure-mysql"
        assert mysql.ip_addresses == []
        assert mysql.details["fully_qualified_domain_name"] == "mysql-prod.mysql.database.azure.com"
        assert mysql.details["state"] == "Ready"
        assert mysql.details["version"] == "8.0"


# ---------------------------------------------------------------------------
# PostgreSQL tests
# ---------------------------------------------------------------------------

class TestCollectAzurePostgresqlServers:
    """Tests for collect_azure_postgresql_servers."""

    def test_postgresql_server_collection(self):
        """PostgreSQL Flexible server is discovered."""
        client = MagicMock()

        client.servers.list.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.DBforPostgreSQL/flexibleServers/pg-prod"),
                name="pg-prod",
                location="eastus",
                tags={"env": "prod"},
                fully_qualified_domain_name="pg-prod.postgres.database.azure.com",
                state="Ready",
                version="15",
            ),
        ]

        result = collect_azure_postgresql_servers(client, "sub1")

        assert len(result) == 1
        pg = result[0]
        assert pg.resource_type == "azure-postgresql"
        assert pg.ip_addresses == []
        assert pg.details["fully_qualified_domain_name"] == "pg-prod.postgres.database.azure.com"
        assert pg.details["version"] == "15"


# ---------------------------------------------------------------------------
# Redis tests
# ---------------------------------------------------------------------------

class TestCollectAzureRedisCaches:
    """Tests for collect_azure_redis_caches."""

    def test_redis_with_static_ip(self):
        """Redis with static_ip present includes it in ip_addresses."""
        client = MagicMock()

        client.redis.list_by_subscription.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Cache/Redis/redis-prod"),
                name="redis-prod",
                location="eastus",
                tags={"env": "prod"},
                static_ip="10.0.0.50",
                host_name="redis-prod.redis.cache.windows.net",
                port=6379,
                ssl_port=6380,
                sku=SimpleNamespace(name="Premium"),
            ),
        ]

        result = collect_azure_redis_caches(client, "sub1")

        assert len(result) == 1
        redis = result[0]
        assert redis.resource_type == "azure-redis"
        assert redis.ip_addresses == ["10.0.0.50"]
        assert redis.details["host_name"] == "redis-prod.redis.cache.windows.net"
        assert redis.details["port"] == 6379
        assert redis.details["ssl_port"] == 6380
        assert redis.details["sku_name"] == "Premium"

    def test_redis_without_static_ip(self):
        """Redis without static_ip has empty ip_addresses."""
        client = MagicMock()

        client.redis.list_by_subscription.return_value = [
            SimpleNamespace(
                id=_arm_id("rg1", "Microsoft.Cache/Redis/redis-basic"),
                name="redis-basic",
                location="eastus",
                tags=None,
                static_ip=None,
                host_name="redis-basic.redis.cache.windows.net",
                port=6379,
                ssl_port=6380,
                sku=SimpleNamespace(name="Basic"),
            ),
        ]

        result = collect_azure_redis_caches(client, "sub1")

        assert len(result) == 1
        assert result[0].ip_addresses == []
