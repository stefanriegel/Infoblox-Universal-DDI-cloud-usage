"""
Per-VPC IP de-duplication for cloud resource counting.

De-duplicates IP addresses per VPC IP space and provides per-account
breakdowns for token calculation.
"""

from __future__ import annotations

from collections import defaultdict

from cloud_usage.schema.resource import CloudResource


def count_nics_per_account(resources: list[CloudResource]) -> dict:
    """Count NIC/interface objects per account (reference implementation method).

    Replaces deduplicate_ips_per_vpc(). Reads provider-specific details fields
    instead of deduplicating ip_addresses strings.

    Dispatch logic:
    - ec2-instance: details["nic_ip_count"] (pre-computed at collection, ref aws.py:457-483)
    - azure-nic: details["ip_configuration_count"] only if details["vm_id"] is not None
    - gcp-vm: details["network_interface_count"]
    - DDI resources (category="ddi"): contribute 0
    - Uncounted resources (counted=False or counted=None): skipped
    - All other counted non-DDI assets: len(ip_addresses) fallback

    Returns same dict shape as deduplicate_ips_per_vpc() for drop-in compatibility:
        {"total_unique_ips": int, "per_account": dict[str, int]}
    """
    total = 0
    per_account: dict[str, int] = defaultdict(int)

    for resource in resources:
        if not resource.counted:
            continue
        if resource.category == "ddi":
            continue  # DDI objects never contribute to IP count

        count = _get_nic_count(resource)
        total += count
        per_account[resource.account_id] += count

    return {
        "total_unique_ips": total,
        "per_account": dict(per_account),
    }


def _get_nic_count(resource: CloudResource) -> int:
    """Extract NIC/interface count for a single counted non-DDI resource."""
    if resource.resource_type == "ec2-instance":
        return resource.details.get("nic_ip_count", 0)
    if resource.resource_type == "azure-nic":
        if resource.details.get("vm_id") is not None:
            return resource.details.get("ip_configuration_count", 0)
        return 0
    if resource.resource_type == "gcp-vm":
        return resource.details.get("network_interface_count", 0)
    # Fallback: all other asset types (RDS, ECS, LBs, forwarding rules, etc.)
    return len(resource.ip_addresses)


def deduplicate_ips_per_vpc(resources: list[CloudResource]) -> dict:
    """De-duplicate IPs per VPC IP space and provide per-account counts.

    Deprecated: Use count_nics_per_account() instead (Phase 25).
    Retained for reference.

    Each IP is keyed by (vpc_id_or_account_id, ip_address). The same IP
    in different VPCs counts separately (different IP spaces). For resources
    without a vpc_id in details, the account_id is used as the IP space key.

    Only considers resources where counted=True.

    Args:
        resources: List of CloudResource instances (already categorized).

    Returns:
        Dict with keys:
            total_unique_ips: int
            per_account: dict mapping account_id -> unique IP count
    """
    # Global dedup set: (ip_space_key, ip_address)
    seen: set[tuple[str, str]] = set()
    # Per-account dedup: account_id -> set of (ip_space_key, ip_address)
    per_account_seen: dict[str, set[tuple[str, str]]] = defaultdict(set)

    for resource in resources:
        if not resource.counted:
            continue

        ip_space_key = resource.details.get("vpc_id") or resource.account_id

        for ip_str in resource.ip_addresses:
            dedup_key = (ip_space_key, ip_str)
            seen.add(dedup_key)
            per_account_seen[resource.account_id].add(dedup_key)

    per_account = {
        account_id: len(ip_set)
        for account_id, ip_set in per_account_seen.items()
    }

    return {
        "total_unique_ips": len(seen),
        "per_account": per_account,
    }
