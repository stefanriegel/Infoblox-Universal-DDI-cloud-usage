"""
Resource categorization for token calculation.

Categorizes each CloudResource as DDI, IP, Asset, or excluded (with skip
reason) based on resource type, IP presence, and provider-specific rules.
"""

from __future__ import annotations

from cloud_usage.schema.resource import CloudResource

# Resource types that are DDI objects (counted toward DDI token bucket)
DDI_TYPES: set[str] = {
    "vpc",
    "subnet",
    "route53-zone",
    "route53-record",
    "dhcp-option-set",
}

# Resource types that are discovered but not counted (token-free)
TOKEN_FREE_TYPES: dict[str, str] = {
    "ebs-volume": "token-free: EBS Volume",
    "s3-bucket": "token-free: S3 Bucket",
}


def categorize_resources(
    resources: list[CloudResource],
) -> list[CloudResource]:
    """Categorize each resource as DDI, IP, Asset, or excluded.

    Mutates the counted, category, and skip_reason fields on each resource
    and returns the same list.

    Categorization rules (applied in order):
      1. Token-free types -> excluded with specific skip reason
      2. DDI types -> counted=True, category="ddi"
         - Exception: orphaned DHCP option sets are excluded
      3. Special case: VPC-attached Lambda -> counted=True, category="asset"
      4. Resources with IPs -> counted=True, category="asset"
      5. Everything else -> counted=False, skip_reason="no IP addresses"

    Args:
        resources: List of CloudResource instances to categorize.

    Returns:
        The same list with counted/category/skip_reason fields populated.
    """
    for resource in resources:
        _categorize_single(resource)
    return resources


def _categorize_single(resource: CloudResource) -> None:
    """Apply categorization rules to a single resource."""

    # 0. Respect prior pipeline exclusions (fold_enis, exclude_managed, dedup)
    if resource.counted is False and resource.skip_reason is not None:
        return

    # 1. Token-free types are excluded outright
    if resource.resource_type in TOKEN_FREE_TYPES:
        resource.counted = False
        resource.category = None
        resource.skip_reason = TOKEN_FREE_TYPES[resource.resource_type]
        return

    # 2. DDI types
    if resource.resource_type in DDI_TYPES:
        # Orphaned DHCP option sets are not counted
        if (
            resource.resource_type == "dhcp-option-set"
            and resource.details.get("orphaned") is True
        ):
            resource.counted = False
            resource.category = None
            resource.skip_reason = (
                "orphaned DHCP option set (not associated with any VPC)"
            )
            return

        resource.counted = True
        resource.category = "ddi"
        resource.skip_reason = None
        return

    # 3. Special case: VPC-attached Lambda functions are assets even without IPs
    if resource.resource_type == "lambda-function":
        vpc_id = resource.details.get("vpc_id", "")
        if vpc_id:
            resource.counted = True
            resource.category = "asset"
            resource.skip_reason = None
            return

    # 4. Resources with IPs are managed assets
    if resource.has_ips():
        resource.counted = True
        resource.category = "asset"
        resource.skip_reason = None
        return

    # 5. No IPs, not DDI, not a special case -> excluded
    resource.counted = False
    resource.category = None
    resource.skip_reason = "no IP addresses"
