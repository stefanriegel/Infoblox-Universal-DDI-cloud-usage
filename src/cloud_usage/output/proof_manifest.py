"""
SHA-256 JSON proof manifest for scan integrity verification.

Produces a cryptographically signed manifest documenting the scan scope,
token ratios, resource counts, and integrity hashes. Enables auditors to
verify that reported numbers match actual discovery data.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from cloud_usage.counting.token_calculator import (
    DDI_PER_TOKEN,
    IPS_PER_TOKEN,
    ASSETS_PER_TOKEN,
)
from cloud_usage.schema.resource import CloudResource


def write_proof_manifest(
    filepath: str,
    resources: list[CloudResource],
    account_summaries: dict[str, dict],
    scan_metadata: dict[str, Any],
    provider: str,
) -> str:
    """Generate a SHA-256 proof manifest from discovery results.

    Creates a JSON file containing scan scope, token ratios, resource
    counts, token calculations, and cryptographic integrity hashes.

    The resource_hash is computed from sorted (resource_id, resource_type,
    counted, category) tuples. The manifest_hash is computed from the
    full manifest (excluding manifest_hash itself).

    Args:
        filepath: Output file path for the .json manifest.
        resources: All discovered CloudResource instances.
        account_summaries: Dict mapping account_id to token calculation
            results (from calculate_account_tokens).
        scan_metadata: Dict with scan_timestamp and scan_duration_seconds.
        provider: Cloud provider name (e.g., "aws").

    Returns:
        The filepath written.
    """
    # Build resource hash from sorted resource data
    resource_data = sorted([
        (r.resource_id, r.resource_type, r.counted, r.category)
        for r in resources
    ])
    resource_hash = hashlib.sha256(
        json.dumps(resource_data, sort_keys=True, default=str).encode()
    ).hexdigest()

    # Compute aggregate counts
    total_resources = len(resources)
    counted_resources = sum(1 for r in resources if r.counted)
    skipped_resources = total_resources - counted_resources

    ddi_objects = sum(1 for r in resources if r.counted and r.category == "ddi")
    active_ips = sum(s.get("ip_count", 0) for s in account_summaries.values())
    managed_assets = sum(1 for r in resources if r.counted and r.category == "asset")

    # Compute token totals from account summaries
    ddi_tokens = sum(s.get("ddi_tokens", 0) for s in account_summaries.values())
    ip_tokens = sum(s.get("ip_tokens", 0) for s in account_summaries.values())
    asset_tokens = sum(s.get("asset_tokens", 0) for s in account_summaries.values())
    total_tokens = sum(s.get("total_tokens", 0) for s in account_summaries.values())

    # Unique resource types discovered
    resource_types = sorted(set(r.resource_type for r in resources))

    # Unique accounts and regions
    accounts_scanned = len(set(r.account_id for r in resources))
    regions_scanned = len(set(r.region for r in resources))

    # Build manifest without manifest_hash
    manifest: dict[str, Any] = {
        "version": "1.0",
        "provider": provider,
        "scan_timestamp": scan_metadata.get("scan_timestamp", ""),
        "scan_duration_seconds": scan_metadata.get("scan_duration_seconds", 0),
        "scope": {
            "accounts_scanned": accounts_scanned,
            "regions_scanned": regions_scanned,
            "resource_types": resource_types,
        },
        "ratios": {
            "ddi_per_token": DDI_PER_TOKEN,
            "ips_per_token": IPS_PER_TOKEN,
            "assets_per_token": ASSETS_PER_TOKEN,
        },
        "counts": {
            "total_resources": total_resources,
            "counted_resources": counted_resources,
            "skipped_resources": skipped_resources,
            "ddi_objects": ddi_objects,
            "active_ips": active_ips,
            "managed_assets": managed_assets,
        },
        "tokens": {
            "ddi_tokens": ddi_tokens,
            "ip_tokens": ip_tokens,
            "asset_tokens": asset_tokens,
            "total_tokens": total_tokens,
        },
        "resource_hash": resource_hash,
    }

    # Compute manifest hash from all fields so far
    manifest_hash = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, default=str).encode()
    ).hexdigest()
    manifest["manifest_hash"] = manifest_hash

    # Write as indented JSON
    with open(filepath, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=False, default=str)

    return filepath
