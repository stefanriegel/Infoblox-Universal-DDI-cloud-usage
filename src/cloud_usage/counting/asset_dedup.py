"""
Tag-based managed service exclusion and cross-account asset de-duplication.

Provides two pipeline stages that run before token calculation:
1. exclude_managed_service_resources: Tag-based EKS/managed exclusion
2. deduplicate_assets: Cross-account RAM-shared resource dedup
"""

from __future__ import annotations

from cloud_usage.counting.categorizer import DDI_TYPES
from cloud_usage.schema.resource import CloudResource

# Token-free types are also exempt from tag-based exclusion
TOKEN_FREE_TYPES: set[str] = {"ebs-volume", "s3-bucket"}

# Tag key prefixes indicating AWS-managed resources
MANAGED_SERVICE_TAG_PREFIXES: list[str] = ["kubernetes.io/cluster/"]

# Exact tag keys indicating AWS-managed resources
MANAGED_SERVICE_TAG_KEYS: set[str] = {
    "eks:nodegroup-name",
    "aws:eks:cluster-name",
}


def _is_aws_managed(tags: dict[str, str]) -> bool:
    """Check if a resource has AWS-managed service tags.

    Returns True if any tag key matches a managed service tag pattern
    (exact match or prefix match).

    Args:
        tags: Resource tags as key-value pairs.

    Returns:
        True if the resource is AWS-managed based on tags.
    """
    for key in tags:
        if key in MANAGED_SERVICE_TAG_KEYS:
            return True
        for prefix in MANAGED_SERVICE_TAG_PREFIXES:
            if key.startswith(prefix):
                return True
    return False


def exclude_managed_service_resources(
    resources: list[CloudResource],
) -> list[CloudResource]:
    """Exclude resources tagged as AWS-managed from counting.

    Checks each resource's tags for managed service tag patterns.
    Only applies to resource types that are managed assets -- DDI objects
    and token-free types are exempt from this exclusion.

    Resources already marked as counted=False are skipped (preserve
    existing skip_reason).

    Args:
        resources: List of CloudResource instances.

    Returns:
        The same list with managed service resources excluded.
    """
    exempt_types = DDI_TYPES | TOKEN_FREE_TYPES

    for resource in resources:
        # Skip resources already explicitly excluded (counted=False)
        # but allow resources not yet categorized (counted=None) to be checked
        if resource.counted is False:
            continue
        # DDI and token-free types are exempt
        if resource.resource_type in exempt_types:
            continue
        # Check for managed service tags
        if _is_aws_managed(resource.tags):
            resource.counted = False
            resource.category = None
            resource.skip_reason = "AWS-managed resource (tag-based exclusion)"

    return resources


def deduplicate_assets(
    resources: list[CloudResource],
) -> list[CloudResource]:
    """De-duplicate resources by resource_id across accounts.

    When the same resource_id appears in multiple accounts (e.g.,
    RAM-shared VPCs/subnets), keep the one from the owning account
    (details["owner_id"] matches account_id) and mark others as not
    counted.

    Resources already marked as counted=False are skipped.

    Args:
        resources: List of CloudResource instances.

    Returns:
        The same list with shared duplicates excluded.
    """
    # Group resources by resource_id (skip explicitly excluded ones)
    by_id: dict[str, list[CloudResource]] = {}
    for resource in resources:
        if resource.counted is False:
            continue
        by_id.setdefault(resource.resource_id, []).append(resource)

    # For each group with duplicates, keep the owner, exclude others
    for resource_id, group in by_id.items():
        if len(group) <= 1:
            continue

        # Find the owner (owner_id matches account_id)
        owner_id = None
        for resource in group:
            candidate_owner = resource.details.get("owner_id", resource.account_id)
            if candidate_owner == resource.account_id:
                owner_id = resource.account_id
                break

        # If no explicit owner found, use the first resource's account
        if owner_id is None:
            owner_id = group[0].account_id

        # Mark non-owners as not counted
        for resource in group:
            if resource.account_id != owner_id:
                real_owner = resource.details.get("owner_id", owner_id)
                resource.counted = False
                resource.category = None
                resource.skip_reason = (
                    f"shared resource counted in owning account {real_owner}"
                )

    return resources
