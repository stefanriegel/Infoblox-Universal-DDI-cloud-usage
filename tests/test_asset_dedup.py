"""
Tests for tag-based managed service exclusion and cross-account asset de-duplication.

Note: fold_enis_into_parents() removed in Phase 25 — ENIs are DDI; no folding needed.
The TestFoldEnisIntoParents class has been removed from this file accordingly.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.schema.resource import CloudResource
from cloud_usage.counting.asset_dedup import (
    exclude_managed_service_resources,
    deduplicate_assets,
)


def _make_resource(
    resource_type: str = "ec2-instance",
    resource_id: str | None = None,
    ip_addresses: list[str] | None = None,
    details: dict | None = None,
    tags: dict | None = None,
    account_id: str = "111111111111",
    region: str = "us-east-1",
    counted: bool = True,
    category: str | None = "asset",
) -> CloudResource:
    """Helper to create a CloudResource for asset dedup tests."""
    if resource_id is None:
        resource_id = f"arn:aws:{resource_type}:{region}:{account_id}:{id(ip_addresses)}"
    return CloudResource(
        resource_id=resource_id,
        resource_type=resource_type,
        provider="aws",
        account_id=account_id,
        region=region,
        name=f"test-{resource_type}",
        ip_addresses=ip_addresses or [],
        details=details or {},
        tags=tags or {},
        discovered_at="2026-02-23T10:00:00",
        counted=counted,
        category=category,
    )


class TestExcludeManagedServiceResources:
    """Test tag-based managed service exclusion."""

    def test_eks_nodegroup_tag_excludes(self):
        """EC2 tagged with eks:nodegroup-name is excluded."""
        r = _make_resource(
            "ec2-instance",
            ip_addresses=["10.0.1.5"],
            tags={"eks:nodegroup-name": "my-nodegroup"},
        )
        result = exclude_managed_service_resources([r])
        assert result[0].counted is False
        assert "AWS-managed" in result[0].skip_reason

    def test_kubernetes_cluster_prefix_tag_excludes(self):
        """EC2 tagged with kubernetes.io/cluster/ prefix is excluded."""
        r = _make_resource(
            "ec2-instance",
            ip_addresses=["10.0.1.5"],
            tags={"kubernetes.io/cluster/my-cluster": "owned"},
        )
        result = exclude_managed_service_resources([r])
        assert result[0].counted is False
        assert "AWS-managed" in result[0].skip_reason

    def test_aws_eks_cluster_name_tag_excludes(self):
        """EC2 tagged with aws:eks:cluster-name is excluded."""
        r = _make_resource(
            "ec2-instance",
            ip_addresses=["10.0.1.5"],
            tags={"aws:eks:cluster-name": "my-cluster"},
        )
        result = exclude_managed_service_resources([r])
        assert result[0].counted is False

    def test_no_eks_tags_remains_counted(self):
        """EC2 instance without EKS tags remains counted."""
        r = _make_resource(
            "ec2-instance",
            ip_addresses=["10.0.1.5"],
            tags={"env": "prod"},
        )
        result = exclude_managed_service_resources([r])
        assert result[0].counted is True

    def test_vpc_with_eks_tags_not_excluded(self):
        """VPC with EKS tags is NOT excluded (DDI types exempt)."""
        r = _make_resource(
            "vpc",
            tags={"eks:nodegroup-name": "my-nodegroup"},
            category="ddi",
        )
        result = exclude_managed_service_resources([r])
        assert result[0].counted is True

    def test_already_uncounted_not_modified(self):
        """Resources already excluded are not double-processed."""
        r = _make_resource(
            "ec2-instance",
            ip_addresses=["10.0.1.5"],
            tags={"eks:nodegroup-name": "ng"},
            counted=False,
            category=None,
        )
        r.skip_reason = "some other reason"
        result = exclude_managed_service_resources([r])
        assert result[0].skip_reason == "some other reason"

    def test_empty_list(self):
        assert exclude_managed_service_resources([]) == []


class TestDeduplicateAssets:
    """Test cross-account asset de-duplication for shared resources."""

    def test_same_resource_two_accounts_counted_once(self):
        """Same VPC ID in two accounts (RAM-shared) -> counted in owner only."""
        owner = _make_resource(
            "vpc",
            resource_id="vpc-shared-123",
            account_id="111111111111",
            details={"owner_id": "111111111111"},
            category="ddi",
        )
        shared = _make_resource(
            "vpc",
            resource_id="vpc-shared-123",
            account_id="222222222222",
            details={"owner_id": "111111111111"},
            category="ddi",
        )
        result = deduplicate_assets([owner, shared])
        owner_r = [r for r in result if r.account_id == "111111111111"][0]
        shared_r = [r for r in result if r.account_id == "222222222222"][0]
        assert owner_r.counted is True
        assert shared_r.counted is False
        assert "shared resource" in shared_r.skip_reason.lower()
        assert "111111111111" in shared_r.skip_reason

    def test_same_subnet_two_accounts(self):
        """Same subnet in two accounts -> counted once in owner."""
        owner = _make_resource(
            "subnet",
            resource_id="subnet-shared-456",
            account_id="111111111111",
            details={"owner_id": "111111111111"},
            category="ddi",
        )
        shared = _make_resource(
            "subnet",
            resource_id="subnet-shared-456",
            account_id="222222222222",
            details={"owner_id": "111111111111"},
            category="ddi",
        )
        result = deduplicate_assets([owner, shared])
        counted_list = [r for r in result if r.counted is True]
        assert len(counted_list) == 1
        assert counted_list[0].account_id == "111111111111"

    def test_unique_resource_ids_all_kept(self):
        """Resources with unique IDs are all kept."""
        r1 = _make_resource(
            "ec2-instance",
            resource_id="i-aaa",
            ip_addresses=["10.0.1.5"],
        )
        r2 = _make_resource(
            "ec2-instance",
            resource_id="i-bbb",
            ip_addresses=["10.0.1.6"],
        )
        result = deduplicate_assets([r1, r2])
        assert all(r.counted is True for r in result)

    def test_shared_resource_owner_not_first(self):
        """Owner appears second in list but still gets kept."""
        shared = _make_resource(
            "vpc",
            resource_id="vpc-xyz",
            account_id="222222222222",
            details={"owner_id": "111111111111"},
            category="ddi",
        )
        owner = _make_resource(
            "vpc",
            resource_id="vpc-xyz",
            account_id="111111111111",
            details={"owner_id": "111111111111"},
            category="ddi",
        )
        result = deduplicate_assets([shared, owner])
        owner_r = [r for r in result if r.account_id == "111111111111"][0]
        shared_r = [r for r in result if r.account_id == "222222222222"][0]
        assert owner_r.counted is True
        assert shared_r.counted is False

    def test_already_uncounted_skipped(self):
        """Resources already excluded are not considered for dedup."""
        r = _make_resource(
            "ec2-instance",
            resource_id="i-aaa",
            counted=False,
        )
        r.skip_reason = "some reason"
        result = deduplicate_assets([r])
        assert result[0].counted is False
        assert result[0].skip_reason == "some reason"


# -- Regression tests for INT-02: DDI_TYPES unification --


class TestDDITypesUnification:
    """Tests confirming asset_dedup.DDI_TYPES matches categorizer.DDI_TYPES."""

    def test_ddi_types_matches_categorizer(self):
        """asset_dedup.DDI_TYPES is identical to categorizer.DDI_TYPES."""
        from cloud_usage.counting import asset_dedup
        from cloud_usage.counting import categorizer

        assert asset_dedup.DDI_TYPES == categorizer.DDI_TYPES
        # Verify multi-provider coverage
        assert "azure-vnet" in asset_dedup.DDI_TYPES
        assert "gcp-vpc" in asset_dedup.DDI_TYPES

    def test_azure_ddi_exempt_from_managed_exclusion(self):
        """azure-vnet with kubernetes managed tag is NOT excluded (DDI type exempt)."""
        r = _make_resource(
            "azure-vnet",
            resource_id="azure-vnet-001",
            tags={"kubernetes.io/cluster/my-cluster": "owned"},
            counted=None,
            category=None,
        )
        result = exclude_managed_service_resources([r])
        assert result[0].counted is not False, (
            "azure-vnet should be exempt from managed-service tag exclusion"
        )

    def test_gcp_ddi_exempt_from_managed_exclusion(self):
        """gcp-vpc with EKS-style managed tag is NOT excluded (DDI type exempt)."""
        r = _make_resource(
            "gcp-vpc",
            resource_id="gcp-vpc-001",
            tags={"kubernetes.io/cluster/my-cluster": "owned"},
            counted=None,
            category=None,
        )
        result = exclude_managed_service_resources([r])
        assert result[0].counted is not False, (
            "gcp-vpc should be exempt from managed-service tag exclusion"
        )

    def test_empty_list(self):
        assert deduplicate_assets([]) == []
