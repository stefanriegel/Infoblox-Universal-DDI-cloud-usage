"""
IP extraction and per-VPC de-duplication.

Extracts private and public IP addresses from CloudResource instances,
de-duplicates per VPC IP space, and provides per-account breakdowns.
"""

from __future__ import annotations

import ipaddress
from collections import defaultdict

from cloud_usage.schema.resource import CloudResource


def count_ips(resources: list[CloudResource]) -> dict:
    """Count private, public, and total unique IPs from counted resources.

    Only considers resources where counted=True. IPs are classified as
    private (RFC 1918/loopback/link-local) or public. IPv6 addresses
    are also classified.

    Args:
        resources: List of CloudResource instances (already categorized).

    Returns:
        Dict with keys: private_ips, public_ips, total_unique_ips.
    """
    private_set: set[str] = set()
    public_set: set[str] = set()

    for resource in resources:
        if not resource.counted:
            continue

        for ip_str in resource.ip_addresses:
            try:
                addr = ipaddress.ip_address(ip_str)
            except ValueError:
                # Skip malformed addresses
                continue

            if addr.is_private or addr.is_loopback or addr.is_link_local:
                private_set.add(ip_str)
            else:
                public_set.add(ip_str)

    return {
        "private_ips": len(private_set),
        "public_ips": len(public_set),
        "total_unique_ips": len(private_set) + len(public_set),
    }


def deduplicate_ips_per_vpc(resources: list[CloudResource]) -> dict:
    """De-duplicate IPs per VPC IP space and provide per-account counts.

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
