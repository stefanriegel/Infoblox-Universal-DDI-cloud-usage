"""Tests for AWS compute, database, and token-free resource collectors.

Tests use moto's @mock_aws decorator to mock all AWS services.
Covers EC2 instances, ECS tasks, EKS node groups, Lambda functions,
load balancers (ALB/NLB/CLB), RDS, ElastiCache, Redshift, EBS, and S3.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boto3
import pytest
from moto import mock_aws

from cloud_usage.providers.aws.collectors.compute import (
    collect_classic_load_balancers,
    collect_ec2_instances,
    collect_ecs_tasks,
    collect_eks_node_groups,
    collect_lambda_functions,
    collect_load_balancers_v2,
)
from cloud_usage.providers.aws.collectors.database import (
    collect_elasticache_clusters,
    collect_rds_instances,
    collect_redshift_clusters,
)
from cloud_usage.providers.aws.collectors.token_free import (
    collect_ebs_volumes,
    collect_s3_buckets,
)

ACCOUNT_ID = "123456789012"
REGION = "us-east-1"


# -- EC2 Instance Tests --


class TestCollectEC2Instances:
    """Tests for EC2 instance collector."""

    @mock_aws
    def test_basic_ec2_instance_discovery(self) -> None:
        """Discovers running EC2 instances with basic IPs."""
        ec2 = boto3.client("ec2", region_name=REGION)
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
        subnet_id = subnet["Subnet"]["SubnetId"]

        ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=2,
            MaxCount=2,
            InstanceType="t2.micro",
            SubnetId=subnet_id,
        )

        resources = collect_ec2_instances(ec2, ACCOUNT_ID, REGION)

        assert len(resources) == 2
        assert all(r.resource_type == "ec2-instance" for r in resources)
        assert all(r.provider == "aws" for r in resources)
        assert all(r.account_id == ACCOUNT_ID for r in resources)
        assert all(r.region == REGION for r in resources)
        assert all(len(r.ip_addresses) > 0 for r in resources)
        assert all(r.details.get("instance_type") == "t2.micro" for r in resources)
        assert all(r.details.get("state") == "running" for r in resources)

    @mock_aws
    def test_terminated_instances_excluded(self) -> None:
        """Terminated EC2 instances are not included in discovery."""
        ec2 = boto3.client("ec2", region_name=REGION)
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
        subnet_id = subnet["Subnet"]["SubnetId"]

        result = ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=2,
            MaxCount=2,
            InstanceType="t2.micro",
            SubnetId=subnet_id,
        )
        # Terminate one instance
        instance_id = result["Instances"][0]["InstanceId"]
        ec2.terminate_instances(InstanceIds=[instance_id])

        resources = collect_ec2_instances(ec2, ACCOUNT_ID, REGION)

        # Only the non-terminated instance should be returned
        assert len(resources) == 1
        assert resources[0].resource_id != instance_id

    @mock_aws
    def test_ec2_instance_with_multiple_enis(self) -> None:
        """EC2 with multiple ENIs extracts IPs from all interfaces."""
        ec2 = boto3.client("ec2", region_name=REGION)
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
        subnet_id = subnet["Subnet"]["SubnetId"]

        result = ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t2.micro",
            SubnetId=subnet_id,
        )
        instance_id = result["Instances"][0]["InstanceId"]

        # Create and attach a second ENI
        eni = ec2.create_network_interface(SubnetId=subnet_id)
        eni_id = eni["NetworkInterface"]["NetworkInterfaceId"]
        ec2.attach_network_interface(
            NetworkInterfaceId=eni_id,
            InstanceId=instance_id,
            DeviceIndex=1,
        )

        resources = collect_ec2_instances(ec2, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        r = resources[0]
        # Should have network_interface_ids from both ENIs
        assert len(r.details["network_interface_ids"]) >= 2
        # Should have at least 2 private IPs (one from each ENI)
        assert len(r.ip_addresses) >= 2

    @mock_aws
    def test_ec2_instance_records_eni_ids_for_folding(self) -> None:
        """EC2 instances record network_interface_ids for ENI folding."""
        ec2 = boto3.client("ec2", region_name=REGION)
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
        subnet_id = subnet["Subnet"]["SubnetId"]

        ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t2.micro",
            SubnetId=subnet_id,
        )

        resources = collect_ec2_instances(ec2, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        eni_ids = resources[0].details["network_interface_ids"]
        assert isinstance(eni_ids, list)
        assert len(eni_ids) >= 1

    @mock_aws
    def test_ec2_instance_details_populated(self) -> None:
        """EC2 instance details include vpc_id, subnet_id, instance_type, state."""
        ec2 = boto3.client("ec2", region_name=REGION)
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
        subnet_id = subnet["Subnet"]["SubnetId"]

        ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="m5.large",
            SubnetId=subnet_id,
        )

        resources = collect_ec2_instances(ec2, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        details = resources[0].details
        assert details["instance_type"] == "m5.large"
        assert details["state"] == "running"
        assert details["vpc_id"] == vpc_id
        assert details["subnet_id"] == subnet_id

    @mock_aws
    def test_ec2_no_instances(self) -> None:
        """Returns empty list when no EC2 instances exist."""
        ec2 = boto3.client("ec2", region_name=REGION)
        resources = collect_ec2_instances(ec2, ACCOUNT_ID, REGION)
        assert resources == []

    @mock_aws
    def test_ec2_ip_deduplication(self) -> None:
        """IPs are de-duplicated within a single EC2 instance."""
        ec2 = boto3.client("ec2", region_name=REGION)
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
        subnet_id = subnet["Subnet"]["SubnetId"]

        ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t2.micro",
            SubnetId=subnet_id,
        )

        resources = collect_ec2_instances(ec2, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        # All IPs should be unique (no duplicates)
        ips = resources[0].ip_addresses
        assert len(ips) == len(set(ips))


# -- ECS Task Tests --


def _make_ecs_mock_clients(
    cluster_arns: list[str] | None = None,
    tasks: list[dict] | None = None,
    eni_private_ips: list[str] | None = None,
) -> tuple:
    """Build mock ECS + EC2 clients for ECS task tests.

    moto 5.1.21 has a bug in ECS awsvpc mode (missing private_dns_name on
    NetworkInterface), so ECS tests use manually mocked boto3 clients.

    Returns:
        Tuple of (ecs_mock, ec2_mock).
    """
    ecs_mock = MagicMock()
    ec2_mock = MagicMock()

    _cluster_arns = cluster_arns or []
    _tasks = tasks or []
    _eni_ips = eni_private_ips or ["10.0.1.100"]

    # list_clusters paginator
    cluster_paginator = MagicMock()
    cluster_paginator.paginate.return_value = [
        {"clusterArns": _cluster_arns}
    ]

    # list_tasks paginator
    task_arns = [t["taskArn"] for t in _tasks]
    task_paginator = MagicMock()
    task_paginator.paginate.return_value = [{"taskArns": task_arns}]

    def get_paginator(name: str) -> MagicMock:
        if name == "list_clusters":
            return cluster_paginator
        if name == "list_tasks":
            return task_paginator
        return MagicMock()

    ecs_mock.get_paginator.side_effect = get_paginator
    ecs_mock.describe_tasks.return_value = {"tasks": _tasks}

    # EC2 describe_network_interfaces for ENI IP resolution
    ec2_mock.describe_network_interfaces.return_value = {
        "NetworkInterfaces": [
            {
                "NetworkInterfaceId": "eni-mock123",
                "PrivateIpAddresses": [
                    {"PrivateIpAddress": ip} for ip in _eni_ips
                ],
                "Ipv6Addresses": [],
            }
        ]
    }

    return ecs_mock, ec2_mock


class TestCollectECSTasks:
    """Tests for ECS task collector.

    Uses manually mocked boto3 clients because moto 5.1.21 has a bug
    in ECS awsvpc networking (missing private_dns_name on NetworkInterface).
    """

    def test_ecs_task_discovery(self) -> None:
        """Discovers running ECS tasks with ENI attachments."""
        task = {
            "taskArn": "arn:aws:ecs:us-east-1:123456789012:task/test-cluster/abc123",
            "taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task:1",
            "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster",
            "launchType": "FARGATE",
            "attachments": [
                {
                    "type": "ElasticNetworkInterface",
                    "status": "ATTACHED",
                    "details": [
                        {"name": "networkInterfaceId", "value": "eni-mock123"},
                    ],
                }
            ],
        }
        ecs_mock, ec2_mock = _make_ecs_mock_clients(
            cluster_arns=["arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster"],
            tasks=[task],
            eni_private_ips=["10.0.1.100"],
        )

        resources = collect_ecs_tasks(ecs_mock, ec2_mock, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        r = resources[0]
        assert r.resource_type == "ecs-task"
        assert r.provider == "aws"
        assert r.account_id == ACCOUNT_ID
        assert r.region == REGION
        assert "test-cluster" in r.details["cluster_arn"]
        assert r.details["launch_type"] == "FARGATE"
        assert "10.0.1.100" in r.ip_addresses

    def test_ecs_no_clusters(self) -> None:
        """Returns empty list when no ECS clusters exist."""
        ecs_mock, ec2_mock = _make_ecs_mock_clients(cluster_arns=[])
        resources = collect_ecs_tasks(ecs_mock, ec2_mock, ACCOUNT_ID, REGION)
        assert resources == []

    def test_ecs_task_records_eni_ids(self) -> None:
        """ECS tasks record network_interface_ids for ENI folding."""
        task = {
            "taskArn": "arn:aws:ecs:us-east-1:123456789012:task/test-cluster/abc123",
            "taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task:1",
            "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster",
            "launchType": "FARGATE",
            "attachments": [
                {
                    "type": "ElasticNetworkInterface",
                    "status": "ATTACHED",
                    "details": [
                        {"name": "networkInterfaceId", "value": "eni-mock123"},
                    ],
                }
            ],
        }
        ecs_mock, ec2_mock = _make_ecs_mock_clients(
            cluster_arns=["arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster"],
            tasks=[task],
        )

        resources = collect_ecs_tasks(ecs_mock, ec2_mock, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        assert resources[0].details["network_interface_ids"] == ["eni-mock123"]


# -- EKS Node Group Tests --


class TestCollectEKSNodeGroups:
    """Tests for EKS node group collector."""

    @mock_aws
    def test_eks_nodegroup_discovery(self) -> None:
        """Discovers EKS node groups as metadata (no IPs)."""
        eks = boto3.client("eks", region_name=REGION)
        ec2 = boto3.client("ec2", region_name=REGION)

        # Create VPC infrastructure for EKS
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
        subnet_id = subnet["Subnet"]["SubnetId"]

        # Create IAM role ARN (moto doesn't enforce validity)
        role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/eks-role"

        # Create cluster
        eks.create_cluster(
            name="test-cluster",
            roleArn=role_arn,
            resourcesVpcConfig={
                "subnetIds": [subnet_id],
                "securityGroupIds": [],
            },
        )

        # Create node group
        eks.create_nodegroup(
            clusterName="test-cluster",
            nodegroupName="test-nodegroup",
            nodeRole=role_arn,
            subnets=[subnet_id],
            instanceTypes=["t3.medium"],
            scalingConfig={
                "minSize": 1,
                "maxSize": 3,
                "desiredSize": 2,
            },
        )

        resources = collect_eks_node_groups(eks, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        r = resources[0]
        assert r.resource_type == "eks-nodegroup"
        assert r.provider == "aws"
        assert r.ip_addresses == []  # No IPs -- underlying EC2 captured separately
        assert r.details["cluster_name"] == "test-cluster"
        assert r.details["nodegroup_name"] == "test-nodegroup"
        assert r.details["instance_types"] == ["t3.medium"]

    @mock_aws
    def test_eks_no_clusters(self) -> None:
        """Returns empty list when no EKS clusters exist."""
        eks = boto3.client("eks", region_name=REGION)
        resources = collect_eks_node_groups(eks, ACCOUNT_ID, REGION)
        assert resources == []


# -- Lambda Function Tests --


class TestCollectLambdaFunctions:
    """Tests for Lambda function collector."""

    @mock_aws
    def test_vpc_lambda_included(self) -> None:
        """Lambda functions with VPC config are discovered."""
        ec2 = boto3.client("ec2", region_name=REGION)
        lam = boto3.client("lambda", region_name=REGION)

        # Create VPC/subnet
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
        subnet_id = subnet["Subnet"]["SubnetId"]

        # Create security group
        sg = ec2.create_security_group(
            GroupName="lambda-sg",
            Description="Lambda SG",
            VpcId=vpc_id,
        )
        sg_id = sg["GroupId"]

        # Create IAM role for Lambda
        import boto3 as _boto3

        iam = _boto3.client("iam", region_name=REGION)
        iam.create_role(
            RoleName="lambda-role",
            AssumeRolePolicyDocument=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                }
            ),
        )
        role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/lambda-role"

        # Create VPC-attached Lambda function
        lam.create_function(
            FunctionName="vpc-function",
            Runtime="python3.12",
            Role=role_arn,
            Handler="index.handler",
            Code={"ZipFile": b"fake-zip-content"},
            VpcConfig={
                "SubnetIds": [subnet_id],
                "SecurityGroupIds": [sg_id],
            },
        )

        resources = collect_lambda_functions(lam, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        r = resources[0]
        assert r.resource_type == "lambda-function"
        assert r.provider == "aws"
        assert r.ip_addresses == []
        # moto returns a synthetic VpcId for Lambda; verify it is non-empty
        assert r.details["vpc_id"]
        assert isinstance(r.details["subnet_ids"], list)
        assert len(r.details["subnet_ids"]) >= 1
        assert r.name == "vpc-function"

    @mock_aws
    def test_non_vpc_lambda_excluded(self) -> None:
        """Lambda functions without VPC config are NOT discovered."""
        lam = boto3.client("lambda", region_name=REGION)
        iam = boto3.client("iam", region_name=REGION)

        iam.create_role(
            RoleName="lambda-role",
            AssumeRolePolicyDocument=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                }
            ),
        )
        role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/lambda-role"

        # Create non-VPC Lambda function
        lam.create_function(
            FunctionName="non-vpc-function",
            Runtime="python3.12",
            Role=role_arn,
            Handler="index.handler",
            Code={"ZipFile": b"fake-zip-content"},
        )

        resources = collect_lambda_functions(lam, ACCOUNT_ID, REGION)

        assert len(resources) == 0

    @mock_aws
    def test_lambda_mixed_vpc_and_non_vpc(self) -> None:
        """Only VPC-attached functions are discovered from a mix."""
        ec2 = boto3.client("ec2", region_name=REGION)
        lam = boto3.client("lambda", region_name=REGION)
        iam = boto3.client("iam", region_name=REGION)

        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
        subnet_id = subnet["Subnet"]["SubnetId"]
        sg = ec2.create_security_group(
            GroupName="lambda-sg",
            Description="Lambda SG",
            VpcId=vpc_id,
        )
        sg_id = sg["GroupId"]

        iam.create_role(
            RoleName="lambda-role",
            AssumeRolePolicyDocument=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    ],
                }
            ),
        )
        role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/lambda-role"

        # Create one VPC Lambda and one non-VPC Lambda
        lam.create_function(
            FunctionName="vpc-fn",
            Runtime="python3.12",
            Role=role_arn,
            Handler="index.handler",
            Code={"ZipFile": b"fake-zip-content"},
            VpcConfig={
                "SubnetIds": [subnet_id],
                "SecurityGroupIds": [sg_id],
            },
        )
        lam.create_function(
            FunctionName="non-vpc-fn",
            Runtime="python3.12",
            Role=role_arn,
            Handler="index.handler",
            Code={"ZipFile": b"fake-zip-content"},
        )

        resources = collect_lambda_functions(lam, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        assert resources[0].name == "vpc-fn"


# -- Load Balancer Tests --


class TestCollectLoadBalancersV2:
    """Tests for ALB/NLB collector."""

    @mock_aws
    def test_alb_discovery(self) -> None:
        """Discovers Application Load Balancers."""
        ec2 = boto3.client("ec2", region_name=REGION)
        elbv2 = boto3.client("elbv2", region_name=REGION)

        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet1 = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.0.1.0/24", AvailabilityZone="us-east-1a"
        )
        subnet2 = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.0.2.0/24", AvailabilityZone="us-east-1b"
        )

        elbv2.create_load_balancer(
            Name="test-alb",
            Subnets=[subnet1["Subnet"]["SubnetId"], subnet2["Subnet"]["SubnetId"]],
            Type="application",
            Scheme="internet-facing",
        )

        resources = collect_load_balancers_v2(elbv2, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        r = resources[0]
        assert r.resource_type == "alb"
        assert r.provider == "aws"
        assert r.name == "test-alb"
        assert r.details["type"] == "application"
        assert r.details["scheme"] == "internet-facing"
        assert r.details["vpc_id"] == vpc_id

    @mock_aws
    def test_nlb_discovery(self) -> None:
        """Discovers Network Load Balancers."""
        ec2 = boto3.client("ec2", region_name=REGION)
        elbv2 = boto3.client("elbv2", region_name=REGION)

        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet1 = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.0.1.0/24", AvailabilityZone="us-east-1a"
        )
        subnet2 = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.0.2.0/24", AvailabilityZone="us-east-1b"
        )

        elbv2.create_load_balancer(
            Name="test-nlb",
            Subnets=[subnet1["Subnet"]["SubnetId"], subnet2["Subnet"]["SubnetId"]],
            Type="network",
            Scheme="internal",
        )

        resources = collect_load_balancers_v2(elbv2, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        r = resources[0]
        assert r.resource_type == "nlb"
        assert r.details["type"] == "network"
        assert r.details["scheme"] == "internal"

    @mock_aws
    def test_no_load_balancers(self) -> None:
        """Returns empty list when no v2 LBs exist."""
        elbv2 = boto3.client("elbv2", region_name=REGION)
        resources = collect_load_balancers_v2(elbv2, ACCOUNT_ID, REGION)
        assert resources == []


class TestCollectClassicLoadBalancers:
    """Tests for Classic Load Balancer collector."""

    @mock_aws
    def test_classic_elb_discovery(self) -> None:
        """Discovers Classic Load Balancers."""
        ec2 = boto3.client("ec2", region_name=REGION)
        elb = boto3.client("elb", region_name=REGION)

        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.0.1.0/24", AvailabilityZone="us-east-1a"
        )

        elb.create_load_balancer(
            LoadBalancerName="test-clb",
            Listeners=[
                {
                    "Protocol": "HTTP",
                    "LoadBalancerPort": 80,
                    "InstancePort": 80,
                    "InstanceProtocol": "HTTP",
                }
            ],
            Subnets=[subnet["Subnet"]["SubnetId"]],
        )

        resources = collect_classic_load_balancers(elb, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        r = resources[0]
        assert r.resource_type == "classic-elb"
        assert r.provider == "aws"
        assert r.name == "test-clb"
        assert r.ip_addresses == []
        assert r.details.get("dns_name")

    @mock_aws
    def test_no_classic_elbs(self) -> None:
        """Returns empty list when no CLBs exist."""
        elb = boto3.client("elb", region_name=REGION)
        resources = collect_classic_load_balancers(elb, ACCOUNT_ID, REGION)
        assert resources == []


# -- RDS Instance Tests --


class TestCollectRDSInstances:
    """Tests for RDS instance collector."""

    @mock_aws
    def test_rds_instance_discovery(self) -> None:
        """Discovers RDS instances with endpoint details."""
        ec2 = boto3.client("ec2", region_name=REGION)
        rds = boto3.client("rds", region_name=REGION)

        # Create VPC/subnets and subnet group for RDS
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet1 = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.0.1.0/24", AvailabilityZone="us-east-1a"
        )
        subnet2 = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.0.2.0/24", AvailabilityZone="us-east-1b"
        )

        rds.create_db_subnet_group(
            DBSubnetGroupName="test-subnet-group",
            DBSubnetGroupDescription="Test",
            SubnetIds=[
                subnet1["Subnet"]["SubnetId"],
                subnet2["Subnet"]["SubnetId"],
            ],
        )

        rds.create_db_instance(
            DBInstanceIdentifier="test-db",
            DBInstanceClass="db.t3.micro",
            Engine="mysql",
            MasterUsername="admin",
            MasterUserPassword="password123",
            DBSubnetGroupName="test-subnet-group",
        )

        resources = collect_rds_instances(rds, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        r = resources[0]
        assert r.resource_type == "rds-instance"
        assert r.provider == "aws"
        assert r.name == "test-db"
        assert r.ip_addresses == []
        assert r.details["engine"] == "mysql"
        assert r.details["db_instance_class"] == "db.t3.micro"
        assert r.details["status"] == "available"
        assert r.details["endpoint"]  # moto provides an endpoint address

    @mock_aws
    def test_rds_no_instances(self) -> None:
        """Returns empty list when no RDS instances exist."""
        rds = boto3.client("rds", region_name=REGION)
        resources = collect_rds_instances(rds, ACCOUNT_ID, REGION)
        assert resources == []

    @mock_aws
    def test_rds_instance_details_populated(self) -> None:
        """RDS instance details include all required fields."""
        ec2 = boto3.client("ec2", region_name=REGION)
        rds = boto3.client("rds", region_name=REGION)

        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet1 = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.0.1.0/24", AvailabilityZone="us-east-1a"
        )
        subnet2 = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.0.2.0/24", AvailabilityZone="us-east-1b"
        )

        rds.create_db_subnet_group(
            DBSubnetGroupName="test-subnet-group",
            DBSubnetGroupDescription="Test",
            SubnetIds=[
                subnet1["Subnet"]["SubnetId"],
                subnet2["Subnet"]["SubnetId"],
            ],
        )

        rds.create_db_instance(
            DBInstanceIdentifier="test-db",
            DBInstanceClass="db.r5.large",
            Engine="postgres",
            EngineVersion="15.3",
            MasterUsername="admin",
            MasterUserPassword="password123",
            MultiAZ=True,
            DBSubnetGroupName="test-subnet-group",
        )

        resources = collect_rds_instances(rds, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        details = resources[0].details
        assert details["db_instance_class"] == "db.r5.large"
        assert details["engine"] == "postgres"
        assert details["multi_az"] is True
        assert "port" in details


# -- ElastiCache Tests --


class TestCollectElastiCacheClusters:
    """Tests for ElastiCache cluster collector."""

    @mock_aws
    def test_elasticache_cluster_discovery(self) -> None:
        """Discovers ElastiCache clusters with cache node info."""
        ec = boto3.client("elasticache", region_name=REGION)

        ec.create_cache_cluster(
            CacheClusterId="test-redis",
            Engine="redis",
            CacheNodeType="cache.t3.micro",
            NumCacheNodes=1,
        )

        resources = collect_elasticache_clusters(ec, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        r = resources[0]
        assert r.resource_type == "elasticache-cluster"
        assert r.provider == "aws"
        assert r.name == "test-redis"
        assert r.details["engine"] == "redis"
        assert r.details["cache_node_type"] == "cache.t3.micro"
        assert r.details["num_cache_nodes"] == 1

    @mock_aws
    def test_elasticache_no_clusters(self) -> None:
        """Returns empty list when no ElastiCache clusters exist."""
        ec = boto3.client("elasticache", region_name=REGION)
        resources = collect_elasticache_clusters(ec, ACCOUNT_ID, REGION)
        assert resources == []


# -- Redshift Tests --


class TestCollectRedshiftClusters:
    """Tests for Redshift cluster collector."""

    @mock_aws
    def test_redshift_cluster_discovery(self) -> None:
        """Discovers Redshift clusters with endpoint details."""
        rs = boto3.client("redshift", region_name=REGION)

        rs.create_cluster(
            ClusterIdentifier="test-cluster",
            NodeType="dc2.large",
            MasterUsername="admin",
            MasterUserPassword="Password123!",
            NumberOfNodes=2,
            ClusterType="multi-node",
        )

        resources = collect_redshift_clusters(rs, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        r = resources[0]
        assert r.resource_type == "redshift-cluster"
        assert r.provider == "aws"
        assert r.name == "test-cluster"
        assert r.details["node_type"] == "dc2.large"
        assert r.details["number_of_nodes"] == 2
        assert r.details["endpoint"]  # moto provides endpoint address

    @mock_aws
    def test_redshift_no_clusters(self) -> None:
        """Returns empty list when no Redshift clusters exist."""
        rs = boto3.client("redshift", region_name=REGION)
        resources = collect_redshift_clusters(rs, ACCOUNT_ID, REGION)
        assert resources == []


# -- EBS Volume Tests --


class TestCollectEBSVolumes:
    """Tests for EBS volume collector."""

    @mock_aws
    def test_ebs_volume_discovery(self) -> None:
        """Discovers EBS volumes with correct details and no IPs."""
        ec2 = boto3.client("ec2", region_name=REGION)

        ec2.create_volume(
            AvailabilityZone="us-east-1a",
            Size=100,
            VolumeType="gp3",
            Encrypted=True,
        )

        resources = collect_ebs_volumes(ec2, ACCOUNT_ID, REGION)

        assert len(resources) >= 1
        # Find our gp3 volume (there may be other volumes from moto setup)
        gp3_vols = [r for r in resources if r.details["volume_type"] == "gp3"]
        assert len(gp3_vols) == 1
        r = gp3_vols[0]
        assert r.resource_type == "ebs-volume"
        assert r.provider == "aws"
        assert r.ip_addresses == []
        assert r.details["size_gb"] == 100
        assert r.details["encrypted"] is True

    @mock_aws
    def test_ebs_volume_no_ips(self) -> None:
        """EBS volumes always have empty ip_addresses."""
        ec2 = boto3.client("ec2", region_name=REGION)

        ec2.create_volume(
            AvailabilityZone="us-east-1a",
            Size=50,
            VolumeType="gp2",
        )

        resources = collect_ebs_volumes(ec2, ACCOUNT_ID, REGION)

        for r in resources:
            assert r.ip_addresses == []

    @mock_aws
    def test_ebs_attached_volume(self) -> None:
        """EBS volumes record attached instance IDs."""
        ec2 = boto3.client("ec2", region_name=REGION)

        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet = ec2.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
        subnet_id = subnet["Subnet"]["SubnetId"]

        instances = ec2.run_instances(
            ImageId="ami-12345678",
            MinCount=1,
            MaxCount=1,
            InstanceType="t2.micro",
            SubnetId=subnet_id,
        )
        instance_id = instances["Instances"][0]["InstanceId"]

        vol = ec2.create_volume(
            AvailabilityZone="us-east-1a",
            Size=50,
            VolumeType="gp3",
        )
        vol_id = vol["VolumeId"]

        ec2.attach_volume(
            VolumeId=vol_id,
            InstanceId=instance_id,
            Device="/dev/sdf",
        )

        resources = collect_ebs_volumes(ec2, ACCOUNT_ID, REGION)

        attached_vol = [r for r in resources if r.resource_id == vol_id]
        assert len(attached_vol) == 1
        assert instance_id in attached_vol[0].details["attached_instance_ids"]


# -- S3 Bucket Tests --


class TestCollectS3Buckets:
    """Tests for S3 bucket collector."""

    @mock_aws
    def test_s3_bucket_discovery(self) -> None:
        """Discovers S3 buckets with correct details and no IPs."""
        s3 = boto3.client("s3", region_name=REGION)

        s3.create_bucket(Bucket="test-bucket-123")

        resources = collect_s3_buckets(s3, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        r = resources[0]
        assert r.resource_type == "s3-bucket"
        assert r.provider == "aws"
        assert r.name == "test-bucket-123"
        assert r.resource_id == "test-bucket-123"
        assert r.ip_addresses == []
        assert r.details["creation_date"]  # Non-empty ISO datetime

    @mock_aws
    def test_s3_bucket_no_ips(self) -> None:
        """S3 buckets always have empty ip_addresses."""
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket="bucket-a")
        s3.create_bucket(Bucket="bucket-b")

        resources = collect_s3_buckets(s3, ACCOUNT_ID, REGION)

        assert len(resources) == 2
        for r in resources:
            assert r.ip_addresses == []

    @mock_aws
    def test_s3_bucket_region_detection(self) -> None:
        """S3 buckets in us-east-1 have region set to us-east-1."""
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket="us-bucket")

        resources = collect_s3_buckets(s3, ACCOUNT_ID, REGION)

        assert len(resources) == 1
        # S3 in us-east-1 has LocationConstraint=None -> region="us-east-1"
        assert resources[0].region == "us-east-1"

    @mock_aws
    def test_s3_no_buckets(self) -> None:
        """Returns empty list when no S3 buckets exist."""
        s3 = boto3.client("s3", region_name=REGION)
        resources = collect_s3_buckets(s3, ACCOUNT_ID, REGION)
        assert resources == []
