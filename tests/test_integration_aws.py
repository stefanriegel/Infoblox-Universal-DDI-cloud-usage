"""End-to-end integration tests for AWS discovery pipeline with moto.

Comprehensive tests exercising the full pipeline: discovery across regions,
categorization, IP counting, token calculation, and output generation.
Uses moto @mock_aws for realistic multi-account, multi-region environments.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boto3
from moto import mock_aws

from cloud_usage.counting.asset_dedup import (
    deduplicate_assets,
    exclude_managed_service_resources,
    fold_enis_into_parents,
)
from cloud_usage.counting.categorizer import categorize_resources
from cloud_usage.counting.ip_counter import deduplicate_ips_per_vpc
from cloud_usage.counting.token_calculator import (
    calculate_account_tokens,
    calculate_provider_tokens,
)
from cloud_usage.providers.aws.provider import AWSDiscoveryProvider
from cloud_usage.schema.resource import CloudResource


def _create_test_environment(session: boto3.Session, region: str = "us-east-1"):
    """Create a realistic AWS environment in moto for testing.

    Creates VPC, subnets, EC2 instances with ENIs, NAT gateway,
    Route53 zone with records, RDS instance, ALB, EBS volumes, and S3 bucket.

    Args:
        session: moto-mocked boto3 session.
        region: AWS region for resource creation.

    Returns:
        Dict with created resource IDs for assertion.
    """
    ec2 = session.client("ec2", region_name=region)
    ec2_resource = session.resource("ec2", region_name=region)

    # Create VPC with subnets
    vpc_resp = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc_resp["Vpc"]["VpcId"]

    subnet1_resp = ec2.create_subnet(
        VpcId=vpc_id, CidrBlock="10.0.1.0/24", AvailabilityZone=f"{region}a"
    )
    subnet1_id = subnet1_resp["Subnet"]["SubnetId"]

    subnet2_resp = ec2.create_subnet(
        VpcId=vpc_id, CidrBlock="10.0.2.0/24", AvailabilityZone=f"{region}b"
    )
    subnet2_id = subnet2_resp["Subnet"]["SubnetId"]

    # Create DHCP option set and associate with VPC
    dhcp_resp = ec2.create_dhcp_options(
        DhcpConfigurations=[
            {"Key": "domain-name", "Values": ["example.com"]},
            {"Key": "domain-name-servers", "Values": ["10.0.0.2"]},
        ]
    )
    dhcp_id = dhcp_resp["DhcpOptions"]["DhcpOptionsId"]
    ec2.associate_dhcp_options(DhcpOptionsId=dhcp_id, VpcId=vpc_id)

    # Create EC2 instances
    instances = ec2.run_instances(
        ImageId="ami-12345678",
        MinCount=2,
        MaxCount=2,
        InstanceType="t3.micro",
        SubnetId=subnet1_id,
    )
    instance_ids = [i["InstanceId"] for i in instances["Instances"]]

    # Create a NAT Gateway (requires an EIP and IGW)
    igw = ec2.create_internet_gateway()
    igw_id = igw["InternetGateway"]["InternetGatewayId"]
    ec2.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
    eip = ec2.allocate_address(Domain="vpc")
    nat_resp = ec2.create_nat_gateway(
        SubnetId=subnet1_id, AllocationId=eip["AllocationId"]
    )
    nat_id = nat_resp["NatGateway"]["NatGatewayId"]

    # Create Route53 hosted zone with records
    route53 = session.client("route53", region_name="us-east-1")
    zone_resp = route53.create_hosted_zone(
        Name="example.com", CallerReference="test-ref-1"
    )
    zone_id = zone_resp["HostedZone"]["Id"].split("/")[-1]

    route53.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            "Changes": [
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": "web.example.com",
                        "Type": "A",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": "1.2.3.4"}],
                    },
                },
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": "mail.example.com",
                        "Type": "MX",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": "10 mail.example.com"}],
                    },
                },
                {
                    "Action": "CREATE",
                    "ResourceRecordSet": {
                        "Name": "www.example.com",
                        "Type": "CNAME",
                        "TTL": 300,
                        "ResourceRecords": [{"Value": "web.example.com"}],
                    },
                },
            ]
        },
    )

    # Create RDS instance
    rds = session.client("rds", region_name=region)
    rds.create_db_subnet_group(
        DBSubnetGroupName="test-subnet-group",
        DBSubnetGroupDescription="Test subnet group",
        SubnetIds=[subnet1_id, subnet2_id],
    )
    rds.create_db_instance(
        DBInstanceIdentifier="test-db",
        DBInstanceClass="db.t3.micro",
        Engine="mysql",
        MasterUsername="admin",
        MasterUserPassword="password123",
        DBSubnetGroupName="test-subnet-group",
    )

    # Create ALB
    elbv2 = session.client("elbv2", region_name=region)
    alb_resp = elbv2.create_load_balancer(
        Name="test-alb",
        Subnets=[subnet1_id, subnet2_id],
        Type="application",
    )

    # Create EBS volumes (token-free)
    vol1 = ec2.create_volume(
        AvailabilityZone=f"{region}a", Size=100, VolumeType="gp3"
    )
    vol2 = ec2.create_volume(
        AvailabilityZone=f"{region}b", Size=200, VolumeType="gp3"
    )

    # Create S3 bucket (token-free)
    s3 = session.client("s3", region_name=region)
    s3.create_bucket(Bucket="test-bucket-12345")

    return {
        "vpc_id": vpc_id,
        "subnet_ids": [subnet1_id, subnet2_id],
        "instance_ids": instance_ids,
        "nat_id": nat_id,
        "zone_id": zone_id,
        "dhcp_id": dhcp_id,
        "region": region,
    }


class TestFullPipelineSingleAccount:
    """Test the complete pipeline for a single-account scan."""

    @mock_aws
    def test_full_pipeline_single_account(self) -> None:
        """Discovery + categorization + counting + tokens for single account."""
        session = boto3.Session(region_name="us-east-1")
        env = _create_test_environment(session, "us-east-1")

        provider = AWSDiscoveryProvider(session=session)
        accounts = provider.list_accounts()
        assert len(accounts) >= 1

        account_id = accounts[0]
        resources = provider.discover_account(account_id)

        # Should have discovered multiple resource types
        assert len(resources) > 0
        resource_types = set(r.resource_type for r in resources)

        # Must find VPCs, subnets, ENIs, Route53 zones/records
        assert "vpc" in resource_types
        assert "subnet" in resource_types
        assert "route53-zone" in resource_types
        assert "route53-record" in resource_types
        assert "ec2-instance" in resource_types
        assert "ebs-volume" in resource_types
        assert "s3-bucket" in resource_types

        # Run counting pipeline
        fold_enis_into_parents(resources)
        exclude_managed_service_resources(resources)
        deduplicate_assets(resources)
        categorize_resources(resources)

        # Verify categorization
        ddi_resources = [r for r in resources if r.counted and r.category == "ddi"]
        asset_resources = [r for r in resources if r.counted and r.category == "asset"]
        skipped_resources = [r for r in resources if not r.counted]

        assert len(ddi_resources) > 0, "Should have DDI objects (VPCs, subnets, zones, records)"
        assert len(asset_resources) > 0, "Should have managed assets (EC2 instances, ALB)"

        # EBS and S3 should be skipped (token-free)
        ebs_resources = [r for r in resources if r.resource_type == "ebs-volume"]
        s3_resources = [r for r in resources if r.resource_type == "s3-bucket"]
        for r in ebs_resources:
            assert not r.counted
            assert "token-free" in (r.skip_reason or "")
        for r in s3_resources:
            assert not r.counted
            assert "token-free" in (r.skip_reason or "")

        # IP counting
        ip_counts = deduplicate_ips_per_vpc(resources)
        assert ip_counts["total_unique_ips"] >= 0

        # Token calculation
        per_account_ips = ip_counts.get("per_account", {})
        deduped_ip = per_account_ips.get(account_id, 0)
        account_tokens = calculate_account_tokens(
            resources, deduplicated_ip_count=deduped_ip
        )

        assert account_tokens["ddi_count"] > 0
        assert account_tokens["total_tokens"] >= 0
        assert "ddi_tokens" in account_tokens
        assert "ip_tokens" in account_tokens
        assert "asset_tokens" in account_tokens

        # Provider-level aggregation
        provider_totals = calculate_provider_tokens({account_id: account_tokens})
        assert provider_totals["account_count"] == 1
        assert provider_totals["total_tokens"] == account_tokens["total_tokens"]


class TestOutputFilesGenerated:
    """Test that output files are generated correctly."""

    @mock_aws
    def test_output_files_generated(self, tmp_path) -> None:
        """Full pipeline via main() generates XLS, CSV, and proof manifest."""
        session = boto3.Session(region_name="us-east-1")
        env = _create_test_environment(session, "us-east-1")

        output_dir = str(tmp_path / "output")

        # Run main with mocked AWS
        from cloud_usage.cli import main

        result = main([
            "--aws",
            "--skip-auth-check",
            "--no-resume",
            "--output-dir", output_dir,
        ])

        assert result == 0

        # Verify output files exist
        output_files = os.listdir(output_dir)

        xlsx_files = [f for f in output_files if f.endswith(".xlsx")]
        csv_files = [f for f in output_files if f.endswith(".csv")]
        json_files = [f for f in output_files if f.endswith(".json")]

        assert len(xlsx_files) >= 1, f"Expected XLSX file, found: {output_files}"
        assert len(csv_files) >= 1, f"Expected CSV file, found: {output_files}"
        assert len(json_files) >= 1, f"Expected JSON manifest, found: {output_files}"

        # Verify proof manifest is valid JSON with required fields
        manifest_path = os.path.join(output_dir, json_files[0])
        with open(manifest_path) as f:
            manifest = json.load(f)

        assert "version" in manifest
        assert "provider" in manifest
        assert manifest["provider"] == "aws"
        assert "counts" in manifest
        assert "tokens" in manifest
        assert "resource_hash" in manifest
        assert "manifest_hash" in manifest

        # Verify manifest hash is consistent (recomputing should match)
        import hashlib
        stored_hash = manifest.pop("manifest_hash")
        recomputed = hashlib.sha256(
            json.dumps(manifest, sort_keys=True, default=str).encode()
        ).hexdigest()
        assert stored_hash == recomputed


class TestPartialFailureResilience:
    """Test that partial failures don't crash the scan."""

    @mock_aws
    def test_partial_failure_resilience(self) -> None:
        """When one collector fails, other collectors still return resources."""
        session = boto3.Session(region_name="us-east-1")
        _create_test_environment(session, "us-east-1")

        provider = AWSDiscoveryProvider(session=session)
        account_id = provider.list_accounts()[0]

        # Patch one collector to raise an exception
        with patch(
            "cloud_usage.providers.aws.provider.collect_rds_instances",
            side_effect=Exception("Simulated RDS API failure"),
        ):
            resources = provider.discover_account(account_id)

        # Should still have resources from other collectors
        assert len(resources) > 0
        resource_types = set(r.resource_type for r in resources)
        assert "vpc" in resource_types
        assert "ec2-instance" in resource_types

        # RDS should NOT be present since we mocked it to fail
        assert "rds-instance" not in resource_types


class TestAccountFiltering:
    """Test include/exclude account filtering."""

    @mock_aws
    def test_include_accounts_filters_correctly(self) -> None:
        """include_accounts only scans the specified accounts."""
        session = boto3.Session(region_name="us-east-1")
        org = session.client("organizations", region_name="us-east-1")
        org.create_organization(FeatureSet="ALL")
        resp1 = org.create_account(Email="a@test.com", AccountName="A")
        resp2 = org.create_account(Email="b@test.com", AccountName="B")

        target_id = resp1["CreateAccountStatus"]["AccountId"]

        provider = AWSDiscoveryProvider(
            session=session, include_accounts=[target_id]
        )
        accounts = provider.list_accounts()
        assert len(accounts) == 1
        assert accounts[0] == target_id

    @mock_aws
    def test_exclude_accounts_filters_correctly(self) -> None:
        """exclude_accounts removes the specified accounts from the scan."""
        session = boto3.Session(region_name="us-east-1")
        org = session.client("organizations", region_name="us-east-1")
        org.create_organization(FeatureSet="ALL")
        resp1 = org.create_account(Email="a@test.com", AccountName="A")
        resp2 = org.create_account(Email="b@test.com", AccountName="B")

        exclude_id = resp1["CreateAccountStatus"]["AccountId"]

        provider = AWSDiscoveryProvider(
            session=session, exclude_accounts=[exclude_id]
        )
        accounts = provider.list_accounts()
        assert exclude_id not in accounts
        # Management + B = 2
        assert len(accounts) == 2


class TestDryRunNoDiscovery:
    """Test that dry-run mode doesn't generate output files."""

    @mock_aws
    def test_dry_run_no_output_files(self, tmp_path) -> None:
        """--dry-run shows scan plan without creating output files."""
        session = boto3.Session(region_name="us-east-1")
        _create_test_environment(session, "us-east-1")

        output_dir = str(tmp_path / "output")

        from cloud_usage.cli import main

        result = main([
            "--aws",
            "--skip-auth-check",
            "--no-resume",
            "--dry-run",
            "--output-dir", output_dir,
        ])

        assert result == 0

        # Dry run should NOT create data output files (may create log files)
        if os.path.exists(output_dir):
            output_files = os.listdir(output_dir)
            xlsx_files = [f for f in output_files if f.endswith(".xlsx")]
            csv_files = [f for f in output_files if f.endswith(".csv")]
            json_manifest_files = [
                f for f in output_files
                if f.endswith(".json") and "proof" in f
            ]
            assert len(xlsx_files) == 0, "Dry run should not create XLSX"
            assert len(csv_files) == 0, "Dry run should not create CSV"
            assert len(json_manifest_files) == 0, "Dry run should not create proof manifest"


class TestTokenFreeResourcesInReport:
    """Test that token-free resources appear in report but don't count."""

    @mock_aws
    def test_token_free_resources_in_report(self) -> None:
        """EBS volumes and S3 buckets are discovered but counted=False."""
        session = boto3.Session(region_name="us-east-1")
        _create_test_environment(session, "us-east-1")

        provider = AWSDiscoveryProvider(session=session)
        account_id = provider.list_accounts()[0]
        resources = provider.discover_account(account_id)

        # Run pipeline
        fold_enis_into_parents(resources)
        exclude_managed_service_resources(resources)
        deduplicate_assets(resources)
        categorize_resources(resources)

        # EBS volumes
        ebs = [r for r in resources if r.resource_type == "ebs-volume"]
        assert len(ebs) > 0, "Should discover EBS volumes"
        for r in ebs:
            assert r.counted is False
            assert r.skip_reason == "token-free: EBS Volume"

        # S3 buckets
        s3 = [r for r in resources if r.resource_type == "s3-bucket"]
        assert len(s3) > 0, "Should discover S3 buckets"
        for r in s3:
            assert r.counted is False
            assert r.skip_reason == "token-free: S3 Bucket"

        # Token-free should NOT contribute to token totals
        ip_counts = deduplicate_ips_per_vpc(resources)
        per_account_ips = ip_counts.get("per_account", {})
        deduped_ip = per_account_ips.get(account_id, 0)
        tokens = calculate_account_tokens(resources, deduplicated_ip_count=deduped_ip)

        # Token totals should not include EBS/S3 counts
        assert tokens["asset_count"] >= 0
        # Verify no EBS/S3 types got into counted resources
        counted_types = set(
            r.resource_type for r in resources if r.counted
        )
        assert "ebs-volume" not in counted_types
        assert "s3-bucket" not in counted_types


class TestEKSManagedNodesExcluded:
    """Test that EKS-managed EC2 instances are excluded from counting."""

    @mock_aws
    def test_eks_managed_nodes_excluded(self) -> None:
        """EC2 instances with EKS tags are excluded from managed asset count."""
        session = boto3.Session(region_name="us-east-1")
        ec2 = session.client("ec2", region_name="us-east-1")

        # Create VPC and subnet
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        vpc_id = vpc["Vpc"]["VpcId"]
        subnet = ec2.create_subnet(
            VpcId=vpc_id, CidrBlock="10.0.1.0/24",
            AvailabilityZone="us-east-1a"
        )
        subnet_id = subnet["Subnet"]["SubnetId"]

        # Create regular EC2 instance (should be counted)
        regular = ec2.run_instances(
            ImageId="ami-12345678", MinCount=1, MaxCount=1,
            InstanceType="t3.micro", SubnetId=subnet_id,
        )
        regular_id = regular["Instances"][0]["InstanceId"]

        # Create EKS-managed EC2 instance (should be excluded)
        eks_managed = ec2.run_instances(
            ImageId="ami-12345678", MinCount=1, MaxCount=1,
            InstanceType="t3.micro", SubnetId=subnet_id,
            TagSpecifications=[{
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "eks:nodegroup-name", "Value": "my-nodegroup"},
                    {"Key": "kubernetes.io/cluster/test-cluster", "Value": "owned"},
                ],
            }],
        )
        eks_managed_id = eks_managed["Instances"][0]["InstanceId"]

        provider = AWSDiscoveryProvider(session=session)
        account_id = provider.list_accounts()[0]
        resources = provider.discover_account(account_id)

        # Run the full dedup + categorization pipeline
        fold_enis_into_parents(resources)
        exclude_managed_service_resources(resources)
        deduplicate_assets(resources)
        categorize_resources(resources)

        # Find our specific instances
        regular_resource = None
        eks_resource = None
        for r in resources:
            if r.resource_type == "ec2-instance":
                if r.resource_id == regular_id:
                    regular_resource = r
                elif r.resource_id == eks_managed_id:
                    eks_resource = r

        assert regular_resource is not None, "Regular EC2 instance should be discovered"
        assert eks_resource is not None, "EKS-managed EC2 instance should be discovered"

        # Regular instance should be counted as asset
        assert regular_resource.counted is True
        assert regular_resource.category == "asset"

        # EKS-managed instance should be excluded
        assert eks_resource.counted is False
        assert "tag-based exclusion" in (eks_resource.skip_reason or "")
