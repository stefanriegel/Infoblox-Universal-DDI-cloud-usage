"""
Resource categorization for token calculation.

Categorizes each CloudResource as DDI, IP, Asset, or excluded (with skip
reason) based on resource type, IP presence, and provider-specific rules.
"""

from __future__ import annotations

from cloud_usage.schema.resource import CloudResource

# Resource types that are DDI objects (counted toward DDI token bucket)
DDI_TYPES: set[str] = {
    # AWS DDI types
    "vpc",
    "subnet",
    "route53-zone",
    "route53-record",
    "dhcp-option-set",
    # AWS networking objects — reclassified Phase 25 (METH-04)
    "eni",
    "elastic-ip",
    "nat-gateway",
    # Azure DDI types
    "azure-vnet",
    "azure-subnet",
    "azure-dns-zone",
    "azure-private-dns-zone",
    "azure-dns-record",
    "azure-private-dns-record",
    "azure-dhcp-config",
    # Azure networking objects — reclassified Phase 25 (METH-02)
    "azure-nic",
    "azure-public-ip",
    # GCP DDI types
    "gcp-vpc",
    "gcp-subnet",
    "gcp-dns-zone",
    "gcp-dns-record",
    # AWS DDI Gaps — Phase 26 (AWSG-01 through AWSG-07)
    # AWSG-01: Route53 Resolver Endpoints
    "aws-resolver-endpoint",
    # AWSG-02: Route53 Resolver Rules and Rule Associations
    "aws-resolver-rule",
    "aws-resolver-rule-association",
    # AWSG-03: IPAM types (all 5 sub-types from reference)
    "aws-ipam",
    "aws-ipam-scope",
    "aws-ipam-pool",
    "aws-ipam-resource-discovery",
    "aws-ipam-resource-discovery-association",
    # AWSG-04: Internet Gateways and Customer Gateways
    "aws-internet-gateway",
    "aws-customer-gateway",
    # AWSG-05: Route Tables (all, including implicit main route table)
    "aws-route-table",
    # AWSG-06: Direct Connect Gateways
    "aws-direct-connect-gateway",
    # AWSG-07: Route53 Health Checks and Traffic Policies
    "aws-route53-health-check",
    "aws-route53-traffic-policy",
    "aws-route53-traffic-policy-instance",
}

# Resource types that are discovered but not counted (token-free)
TOKEN_FREE_TYPES: dict[str, str] = {
    # AWS token-free types
    "ebs-volume": "token-free: EBS Volume",
    "s3-bucket": "token-free: S3 Bucket",
    # Azure token-free types (per ASSET-04)
    "azure-disk": "token-free: Azure VM Disk",
    "azure-management-group": "token-free: Azure Management Group",
    "azure-monitoring-stats": "token-free: Azure VM Monitoring Stats",
    "azure-flow-log": "token-free: Azure Network Watcher Flow Log",
    "azure-network-watcher": "token-free: Azure Network Watcher",
    "azure-storage-account": "token-free: Azure Storage Account",
    "azure-storage-container": "token-free: Azure Storage Container",
    "azure-subscription-tenant": "token-free: Azure Subscription Tenant",
    "azure-traffic-manager": "token-free: Azure Traffic Manager Profile",
    "azure-resource-group": "token-free: Azure Resource Group",
    "azure-nsg": "token-free: Azure Network Security Group",
    # GCP token-free types (per ASSET-05 + GKE clusters)
    "gcp-disk": "token-free: GCP Compute Persistent Disk",
    "gcp-instance-group": "token-free: GCP Instance Group",
    "gcp-url-map": "token-free: GCP URL Map",
    "gcp-monitoring-stats": "token-free: GCP Cloud Monitoring Metric Stats",
    "gcp-connectivity-location": "token-free: GCP Network Connectivity Location",
    "gcp-storage-bucket-policy": "token-free: GCP Cloud Storage Bucket Policy",
    "gcp-storage-bucket": "token-free: GCP Cloud Storage Bucket",
    "gcp-gke-cluster": "token-free: GCP GKE Cluster (metadata only)",
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
