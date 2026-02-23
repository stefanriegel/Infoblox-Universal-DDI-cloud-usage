"""Database resource collectors for AWS.

Discovers RDS instances, ElastiCache clusters, and Redshift clusters.
Each collector returns a list of CloudResource instances with endpoint
and IP information where available.
"""

from __future__ import annotations

import logging
from typing import Any

from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


@retry_with_backoff(max_retries=3)
def collect_rds_instances(
    rds_client: Any,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover RDS database instances.

    RDS instances in VPCs have ENIs discoverable via describe_network_interfaces
    with attachment owner "amazon-rds". For simplicity, set ip_addresses=[]
    and let ENI discovery + folding handle IP attribution. The endpoint
    DNS name is stored in details for reference.

    Args:
        rds_client: boto3 RDS client.
        account_id: AWS account ID.
        region: AWS region name.

    Returns:
        List of CloudResource for each RDS instance.
    """
    resources: list[CloudResource] = []
    paginator = rds_client.get_paginator("describe_db_instances")

    for page in paginator.paginate():
        for db in page.get("DBInstances", []):
            endpoint = db.get("Endpoint", {})
            db_subnet_group = db.get("DBSubnetGroup", {})

            resources.append(
                CloudResource(
                    resource_id=db.get(
                        "DBInstanceArn",
                        f"arn:aws:rds:{region}:{account_id}:db:{db['DBInstanceIdentifier']}",
                    ),
                    resource_type="rds-instance",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=db.get("DBInstanceIdentifier", ""),
                    ip_addresses=[],
                    details={
                        "db_instance_class": db.get("DBInstanceClass", ""),
                        "engine": db.get("Engine", ""),
                        "engine_version": db.get("EngineVersion", ""),
                        "vpc_id": db_subnet_group.get("VpcId", ""),
                        "endpoint": endpoint.get("Address", ""),
                        "port": endpoint.get("Port", 0),
                        "status": db.get("DBInstanceStatus", ""),
                        "multi_az": db.get("MultiAZ", False),
                    },
                )
            )

    logger.debug(
        "Discovered %d RDS instances in %s/%s",
        len(resources),
        account_id,
        region,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_elasticache_clusters(
    elasticache_client: Any,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover ElastiCache clusters with cache node IPs.

    Retrieves cache clusters with ShowCacheNodeInfo=True to get
    individual cache node endpoint addresses as IPs.

    Args:
        elasticache_client: boto3 ElastiCache client.
        account_id: AWS account ID.
        region: AWS region name.

    Returns:
        List of CloudResource for each ElastiCache cluster.
    """
    resources: list[CloudResource] = []
    paginator = elasticache_client.get_paginator("describe_cache_clusters")

    for page in paginator.paginate(ShowCacheNodeInfo=True):
        for cluster in page.get("CacheClusters", []):
            ips: list[str] = []
            for node in cluster.get("CacheNodes", []):
                endpoint = node.get("Endpoint", {})
                addr = endpoint.get("Address", "")
                if addr and addr not in ips:
                    ips.append(addr)

            resources.append(
                CloudResource(
                    resource_id=cluster.get(
                        "ARN",
                        f"arn:aws:elasticache:{region}:{account_id}:cluster:{cluster['CacheClusterId']}",
                    ),
                    resource_type="elasticache-cluster",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=cluster.get("CacheClusterId", ""),
                    ip_addresses=ips,
                    details={
                        "cache_node_type": cluster.get("CacheNodeType", ""),
                        "engine": cluster.get("Engine", ""),
                        "engine_version": cluster.get("EngineVersion", ""),
                        "num_cache_nodes": cluster.get("NumCacheNodes", 0),
                        "status": cluster.get("CacheClusterStatus", ""),
                    },
                )
            )

    logger.debug(
        "Discovered %d ElastiCache clusters in %s/%s",
        len(resources),
        account_id,
        region,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_redshift_clusters(
    redshift_client: Any,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover Redshift clusters with node IPs.

    Extracts IPs from Endpoint.Address (if IP) and from
    ClusterNodes[].PrivateIPAddress and PublicIPAddress.

    Args:
        redshift_client: boto3 Redshift client.
        account_id: AWS account ID.
        region: AWS region name.

    Returns:
        List of CloudResource for each Redshift cluster.
    """
    resources: list[CloudResource] = []
    paginator = redshift_client.get_paginator("describe_clusters")

    for page in paginator.paginate():
        for cluster in page.get("Clusters", []):
            ips: list[str] = []
            endpoint = cluster.get("Endpoint", {})

            # Extract node IPs
            for node in cluster.get("ClusterNodes", []):
                priv_ip = node.get("PrivateIPAddress")
                if priv_ip and priv_ip not in ips:
                    ips.append(priv_ip)
                pub_ip = node.get("PublicIPAddress")
                if pub_ip and pub_ip not in ips:
                    ips.append(pub_ip)

            resources.append(
                CloudResource(
                    resource_id=cluster.get(
                        "ClusterNamespaceArn",
                        cluster.get("ClusterIdentifier", ""),
                    ),
                    resource_type="redshift-cluster",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=cluster.get("ClusterIdentifier", ""),
                    ip_addresses=ips,
                    details={
                        "node_type": cluster.get("NodeType", ""),
                        "number_of_nodes": cluster.get("NumberOfNodes", 0),
                        "vpc_id": cluster.get("VpcId", ""),
                        "status": cluster.get("ClusterStatus", ""),
                        "endpoint": endpoint.get("Address", ""),
                    },
                )
            )

    logger.debug(
        "Discovered %d Redshift clusters in %s/%s",
        len(resources),
        account_id,
        region,
    )
    return resources
