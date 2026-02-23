"""Compute resource collectors for AWS.

Discovers EC2 instances, ECS tasks, EKS node groups, Lambda functions,
and load balancers (ALB, NLB, CLB). Each collector returns a list of
CloudResource instances with full IP extraction and ENI linkage for
asset de-duplication.
"""

from __future__ import annotations

import logging
from typing import Any

from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


def _get_name_tag(tags: list[dict[str, str]] | None) -> str:
    """Extract the Name tag value from an AWS tags list."""
    for tag in tags or []:
        if tag.get("Key") == "Name":
            return tag.get("Value", "")
    return ""


def _tags_to_dict(tags: list[dict[str, str]] | None) -> dict[str, str]:
    """Convert AWS tags list to a key-value dict."""
    return {tag["Key"]: tag["Value"] for tag in tags or [] if "Key" in tag}


@retry_with_backoff(max_retries=3)
def collect_ec2_instances(
    ec2_client: Any,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover EC2 instances with full IP extraction from all ENIs.

    Skips terminated instances per IP counting rules. Extracts primary,
    secondary, public, and IPv6 addresses from all attached network
    interfaces. Records network_interface_ids for ENI folding.

    Args:
        ec2_client: boto3 EC2 client.
        account_id: AWS account ID.
        region: AWS region name.

    Returns:
        List of CloudResource for each non-terminated EC2 instance.
    """
    resources: list[CloudResource] = []
    paginator = ec2_client.get_paginator("describe_instances")

    for page in paginator.paginate():
        for reservation in page.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                state = instance.get("State", {}).get("Name", "")
                if state == "terminated":
                    continue

                # Thorough IP extraction per Pitfall 2
                ips: list[str] = []
                eni_ids: list[str] = []

                # 1. Instance-level primary IPs
                if instance.get("PrivateIpAddress"):
                    ips.append(instance["PrivateIpAddress"])
                if instance.get("PublicIpAddress"):
                    ips.append(instance["PublicIpAddress"])

                # 2. ENI-level IPs (primary + secondary + public + IPv6)
                for eni in instance.get("NetworkInterfaces", []):
                    eni_id = eni.get("NetworkInterfaceId")
                    if eni_id:
                        eni_ids.append(eni_id)

                    for addr in eni.get("PrivateIpAddresses", []):
                        ip = addr.get("PrivateIpAddress")
                        if ip and ip not in ips:
                            ips.append(ip)
                        # Public IP on each private address via Association
                        assoc = addr.get("Association", {})
                        pub_ip = assoc.get("PublicIp")
                        if pub_ip and pub_ip not in ips:
                            ips.append(pub_ip)

                    for ipv6 in eni.get("Ipv6Addresses", []):
                        ip = ipv6.get("Ipv6Address")
                        if ip and ip not in ips:
                            ips.append(ip)

                tags = instance.get("Tags", [])
                resources.append(
                    CloudResource(
                        resource_id=instance["InstanceId"],
                        resource_type="ec2-instance",
                        provider="aws",
                        account_id=account_id,
                        region=region,
                        name=_get_name_tag(tags),
                        ip_addresses=ips,
                        tags=_tags_to_dict(tags),
                        details={
                            "instance_type": instance.get("InstanceType"),
                            "state": state,
                            "vpc_id": instance.get("VpcId"),
                            "subnet_id": instance.get("SubnetId"),
                            "network_interface_ids": eni_ids,
                        },
                    )
                )

    logger.debug(
        "Discovered %d EC2 instances in %s/%s",
        len(resources),
        account_id,
        region,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_ecs_tasks(
    ecs_client: Any,
    ec2_client: Any,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover running ECS tasks with IP resolution via ENI attachments.

    Lists ECS clusters, then running tasks per cluster. Resolves IPs from
    ENI attachments (awsvpc networking mode) by looking up ENIs via the
    EC2 describe_network_interfaces API.

    Args:
        ecs_client: boto3 ECS client.
        ec2_client: boto3 EC2 client (for ENI IP lookups).
        account_id: AWS account ID.
        region: AWS region name.

    Returns:
        List of CloudResource for each running ECS task.
    """
    resources: list[CloudResource] = []

    # List all clusters
    cluster_arns: list[str] = []
    cluster_paginator = ecs_client.get_paginator("list_clusters")
    for page in cluster_paginator.paginate():
        cluster_arns.extend(page.get("clusterArns", []))

    for cluster_arn in cluster_arns:
        # List running tasks in each cluster
        task_arns: list[str] = []
        task_paginator = ecs_client.get_paginator("list_tasks")
        for page in task_paginator.paginate(
            cluster=cluster_arn, desiredStatus="RUNNING"
        ):
            task_arns.extend(page.get("taskArns", []))

        if not task_arns:
            continue

        # Describe tasks in batches of 100
        for i in range(0, len(task_arns), 100):
            batch = task_arns[i : i + 100]
            response = ecs_client.describe_tasks(
                cluster=cluster_arn, tasks=batch
            )

            for task in response.get("tasks", []):
                eni_ids: list[str] = []
                ips: list[str] = []

                # Extract ENI IDs from attachments
                for attachment in task.get("attachments", []):
                    if attachment.get("type") == "ElasticNetworkInterface":
                        for detail in attachment.get("details", []):
                            if detail.get("name") == "networkInterfaceId":
                                eni_ids.append(detail["value"])

                # Resolve IPs from ENIs
                if eni_ids:
                    try:
                        eni_response = ec2_client.describe_network_interfaces(
                            NetworkInterfaceIds=eni_ids
                        )
                        for eni in eni_response.get("NetworkInterfaces", []):
                            for addr in eni.get("PrivateIpAddresses", []):
                                ip = addr.get("PrivateIpAddress")
                                if ip and ip not in ips:
                                    ips.append(ip)
                                assoc = addr.get("Association", {})
                                pub_ip = assoc.get("PublicIp")
                                if pub_ip and pub_ip not in ips:
                                    ips.append(pub_ip)
                            for ipv6 in eni.get("Ipv6Addresses", []):
                                ip = ipv6.get("Ipv6Address")
                                if ip and ip not in ips:
                                    ips.append(ip)
                    except Exception:
                        logger.warning(
                            "Failed to resolve ENI IPs for ECS task %s",
                            task.get("taskArn"),
                            exc_info=True,
                        )

                resources.append(
                    CloudResource(
                        resource_id=task["taskArn"],
                        resource_type="ecs-task",
                        provider="aws",
                        account_id=account_id,
                        region=region,
                        name="",
                        ip_addresses=ips,
                        details={
                            "cluster_arn": cluster_arn,
                            "task_definition": task.get("taskDefinitionArn", ""),
                            "launch_type": task.get("launchType", ""),
                            "network_interface_ids": eni_ids,
                        },
                    )
                )

    logger.debug(
        "Discovered %d ECS tasks in %s/%s",
        len(resources),
        account_id,
        region,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_eks_node_groups(
    eks_client: Any,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover EKS node groups as metadata resources.

    Node group IPs are captured via EC2 instance discovery; this collector
    records node group metadata for the detail report.

    Args:
        eks_client: boto3 EKS client.
        account_id: AWS account ID.
        region: AWS region name.

    Returns:
        List of CloudResource for each EKS node group (no IPs).
    """
    resources: list[CloudResource] = []

    # List EKS clusters
    cluster_names: list[str] = []
    cluster_paginator = eks_client.get_paginator("list_clusters")
    for page in cluster_paginator.paginate():
        cluster_names.extend(page.get("clusters", []))

    for cluster_name in cluster_names:
        # List node groups per cluster
        nodegroup_names: list[str] = []
        ng_paginator = eks_client.get_paginator("list_nodegroups")
        for page in ng_paginator.paginate(clusterName=cluster_name):
            nodegroup_names.extend(page.get("nodegroups", []))

        for ng_name in nodegroup_names:
            try:
                response = eks_client.describe_nodegroup(
                    clusterName=cluster_name,
                    nodegroupName=ng_name,
                )
                ng = response.get("nodegroup", {})
                resources.append(
                    CloudResource(
                        resource_id=ng.get(
                            "nodegroupArn",
                            f"arn:aws:eks:{region}:{account_id}:nodegroup/{cluster_name}/{ng_name}",
                        ),
                        resource_type="eks-nodegroup",
                        provider="aws",
                        account_id=account_id,
                        region=region,
                        name=ng_name,
                        ip_addresses=[],
                        details={
                            "cluster_name": cluster_name,
                            "nodegroup_name": ng_name,
                            "instance_types": ng.get("instanceTypes", []),
                            "scaling_config": ng.get("scalingConfig", {}),
                            "status": ng.get("status", ""),
                        },
                    )
                )
            except Exception:
                logger.warning(
                    "Failed to describe EKS nodegroup %s/%s",
                    cluster_name,
                    ng_name,
                    exc_info=True,
                )

    logger.debug(
        "Discovered %d EKS node groups in %s/%s",
        len(resources),
        account_id,
        region,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_lambda_functions(
    lambda_client: Any,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover VPC-attached Lambda functions only.

    Non-VPC Lambda functions are excluded per Pitfall 6 -- they have no
    network interfaces or IP relevance. VPC-attached Lambda functions
    are counted as managed assets even without IPs because their ENIs
    are managed by AWS and share IPs from the subnet.

    Args:
        lambda_client: boto3 Lambda client.
        account_id: AWS account ID.
        region: AWS region name.

    Returns:
        List of CloudResource for each VPC-attached Lambda function.
    """
    resources: list[CloudResource] = []
    paginator = lambda_client.get_paginator("list_functions")

    for page in paginator.paginate():
        for func in page.get("Functions", []):
            vpc_config = func.get("VpcConfig", {})
            vpc_id = vpc_config.get("VpcId", "")

            # Only include VPC-attached Lambda functions
            if not vpc_id:
                continue

            resources.append(
                CloudResource(
                    resource_id=func["FunctionArn"],
                    resource_type="lambda-function",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=func.get("FunctionName", ""),
                    ip_addresses=[],
                    details={
                        "vpc_id": vpc_id,
                        "subnet_ids": vpc_config.get("SubnetIds", []),
                        "runtime": func.get("Runtime", ""),
                        "memory": func.get("MemorySize", 0),
                    },
                )
            )

    logger.debug(
        "Discovered %d VPC-attached Lambda functions in %s/%s",
        len(resources),
        account_id,
        region,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_load_balancers_v2(
    elbv2_client: Any,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover ALB and NLB load balancers.

    NLBs with static IPs have IP addresses extracted from
    AvailabilityZones[].LoadBalancerAddresses[].IpAddress. ALBs use
    dynamic DNS-based IPs; only the DNS name is stored.

    Args:
        elbv2_client: boto3 ELBv2 client.
        account_id: AWS account ID.
        region: AWS region name.

    Returns:
        List of CloudResource for each ALB/NLB.
    """
    resources: list[CloudResource] = []
    paginator = elbv2_client.get_paginator("describe_load_balancers")

    for page in paginator.paginate():
        for lb in page.get("LoadBalancers", []):
            lb_type = lb.get("Type", "application")
            resource_type = "nlb" if lb_type == "network" else "alb"

            # Extract static IPs for NLBs
            ips: list[str] = []
            if lb_type == "network":
                for az in lb.get("AvailabilityZones", []):
                    for addr in az.get("LoadBalancerAddresses", []):
                        ip = addr.get("IpAddress")
                        if ip and ip not in ips:
                            ips.append(ip)

            resources.append(
                CloudResource(
                    resource_id=lb["LoadBalancerArn"],
                    resource_type=resource_type,
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=lb.get("LoadBalancerName", ""),
                    ip_addresses=ips,
                    details={
                        "vpc_id": lb.get("VpcId", ""),
                        "dns_name": lb.get("DNSName", ""),
                        "scheme": lb.get("Scheme", ""),
                        "type": lb_type,
                        "state": lb.get("State", {}).get("Code", ""),
                    },
                )
            )

    logger.debug(
        "Discovered %d ALB/NLB load balancers in %s/%s",
        len(resources),
        account_id,
        region,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_classic_load_balancers(
    elb_client: Any,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover Classic Load Balancers (CLB).

    CLBs have DNS names but no static IP addresses.

    Args:
        elb_client: boto3 ELB (Classic) client.
        account_id: AWS account ID.
        region: AWS region name.

    Returns:
        List of CloudResource for each Classic Load Balancer.
    """
    resources: list[CloudResource] = []
    paginator = elb_client.get_paginator("describe_load_balancers")

    for page in paginator.paginate():
        for lb in page.get("LoadBalancerDescriptions", []):
            resources.append(
                CloudResource(
                    resource_id=lb["LoadBalancerName"],
                    resource_type="classic-elb",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=lb.get("LoadBalancerName", ""),
                    ip_addresses=[],
                    details={
                        "vpc_id": lb.get("VPCId", ""),
                        "dns_name": lb.get("DNSName", ""),
                        "scheme": lb.get("Scheme", ""),
                    },
                )
            )

    logger.debug(
        "Discovered %d Classic Load Balancers in %s/%s",
        len(resources),
        account_id,
        region,
    )
    return resources
