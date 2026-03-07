"""Microsoft AD analysis runner.

Orchestrates: resolve options -> collect from DCs -> aggregate across DCs ->
convert to CloudResource list -> categorize -> write XLS report.

When output_path is provided, the XLS report is written.
When output_path is None, the list of CloudResources and errors is returned
without writing a report (useful for programmatic callers).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator, Optional

from cloud_usage.schema.resource import CloudResource
from cloud_usage.counting.categorizer import categorize_resources
from cloud_usage.output.xlsx_report import write_xlsx_report
from .options import AdOptions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers for handling both set and dict containers from collector/mock data
# ---------------------------------------------------------------------------


def _iter_container(container: Any) -> Iterator:
    """Iterate over keys of a dict or items of a set/list."""
    if isinstance(container, dict):
        return iter(container.keys())
    return iter(container)


def _extract_ip_from_record_key(record_key: str, record_type: str) -> str:
    """Extract IP address from a record dedup key for A/AAAA records.

    The real collector encodes JSON record data as the 4th pipe-delimited segment.
    Mock data may encode the raw IP string directly as the 4th segment.

    Returns the IP string, or "" if not extractable.
    """
    if record_type not in ("A", "AAAA"):
        return ""
    parts = record_key.split("|", 3)
    if len(parts) < 4:
        return ""
    ip_field = parts[3]
    # Try JSON parse first (real collector format)
    try:
        data = json.loads(ip_field)
        if isinstance(data, dict):
            if record_type == "A":
                return str(data.get("IPv4Address") or "").strip()
            if record_type == "AAAA":
                return str(data.get("IPv6Address") or "").strip()
    except (json.JSONDecodeError, TypeError):
        pass
    # Fall back to treating the segment as a raw IP string (mock format)
    candidate = ip_field.strip()
    # Validate it looks like an IP (contains dots or colons)
    if candidate and ("." in candidate or ":" in candidate):
        return candidate
    return ""


def _extract_sid_from_user_entry(user_key: str, users_dict: Any) -> str:
    """Extract SID from a user entry.

    For dict containers (mock data), the value may contain SID info.
    For set containers, the key itself may be prefixed with 'sid:'.
    """
    # If the container is a dict, check the value for SID
    if isinstance(users_dict, dict):
        value = users_dict.get(user_key)
        if isinstance(value, dict):
            sid_raw = value.get("SID")
            if isinstance(sid_raw, dict):
                sid = (sid_raw.get("Value") or "").strip()
                if sid:
                    return sid
            elif sid_raw:
                return str(sid_raw).strip()
        # The key itself may be a raw SID string
        if user_key.startswith("S-") or user_key.startswith("s-"):
            return user_key
    # Set/string key format from real collector: "sid:S-1-5-..." / "upn:..." / "sam:..."
    if user_key.startswith("sid:"):
        return user_key[4:]
    return ""


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _aggregate_results(server_results: list[dict]) -> dict:
    """Aggregate per-DC collector results across all servers.

    Performs per-domain union of DNS/DHCP data and global union of user data.

    Args:
        server_results: List of per-DC result dicts from MicrosoftAdCollector.collect_all().

    Returns:
        {
            "domains": {
                domain_name: {
                    "dns": {"zone_keys": set, "record_keys": set_or_dict, ...} | None,
                    "dhcp": {"scope_keys": set, "lease_keys": set, "reservation_keys": set} | None,
                }
            },
            "users": {"user_keys": set_or_dict, "sid_map": dict},
        }
    """
    domains: dict[str, dict] = {}
    global_user_keys: Any = None  # set or dict — determined by first seen
    global_sid_map: dict[str, str] = {}

    for result in server_results:
        if result.get("status") == "error":
            continue

        # Derive domain from result dict (may have "domain" key, else fall back to server name)
        domain = (result.get("domain") or result.get("server") or "unknown").lower()

        if domain not in domains:
            domains[domain] = {"dns": None, "dhcp": None}

        # --- DNS aggregation ---
        dns_data = result.get("dns")
        if dns_data is not None:
            existing_dns = domains[domain]["dns"]
            if existing_dns is None:
                # Deep-copy the sets/dicts so we can mutate them
                existing_dns = {
                    "zone_keys": type(dns_data["zone_keys"])() if isinstance(dns_data["zone_keys"], set) else {},
                    "record_keys": type(dns_data["record_keys"])() if isinstance(dns_data["record_keys"], set) else {},
                    "unsupported_record_keys": set(),
                    "ip_addresses": [],
                }
                domains[domain]["dns"] = existing_dns

            # Union zone_keys
            if isinstance(dns_data["zone_keys"], dict):
                existing_dns["zone_keys"].update(dns_data["zone_keys"])
            else:
                if isinstance(existing_dns["zone_keys"], set):
                    existing_dns["zone_keys"] |= dns_data["zone_keys"]
                else:
                    for k in dns_data["zone_keys"]:
                        existing_dns["zone_keys"][k] = None

            # Union record_keys
            if isinstance(dns_data["record_keys"], dict):
                existing_dns["record_keys"].update(dns_data["record_keys"])
            else:
                if isinstance(existing_dns["record_keys"], set):
                    existing_dns["record_keys"] |= dns_data["record_keys"]
                else:
                    for k in dns_data["record_keys"]:
                        existing_dns["record_keys"][k] = None

            # Unsupported record keys (set only from real collector)
            unsupported = dns_data.get("unsupported_record_keys")
            if isinstance(unsupported, set):
                existing_dns["unsupported_record_keys"] |= unsupported

        # --- DHCP aggregation ---
        dhcp_data = result.get("dhcp")
        if dhcp_data is not None:
            existing_dhcp = domains[domain]["dhcp"]
            if existing_dhcp is None:
                existing_dhcp = {
                    "scope_keys": type(dhcp_data["scope_keys"])() if isinstance(dhcp_data["scope_keys"], set) else {},
                    "lease_keys": type(dhcp_data["lease_keys"])() if isinstance(dhcp_data["lease_keys"], set) else {},
                    "reservation_keys": type(dhcp_data["reservation_keys"])() if isinstance(dhcp_data["reservation_keys"], set) else {},
                }
                domains[domain]["dhcp"] = existing_dhcp

            for field in ("scope_keys", "lease_keys", "reservation_keys"):
                src = dhcp_data.get(field, set())
                if isinstance(src, dict):
                    existing_dhcp[field].update(src)
                else:
                    if isinstance(existing_dhcp[field], set):
                        existing_dhcp[field] |= src
                    else:
                        for k in src:
                            existing_dhcp[field][k] = None

        # --- User aggregation (global, not per-domain) ---
        users_data = result.get("users")
        if users_data is not None:
            src_user_keys = users_data.get("user_keys", set())
            src_sid_map = users_data.get("sid_map", {})

            if global_user_keys is None:
                global_user_keys = type(src_user_keys)() if isinstance(src_user_keys, set) else {}

            if isinstance(src_user_keys, dict):
                if isinstance(global_user_keys, dict):
                    global_user_keys.update(src_user_keys)
                else:
                    for k in src_user_keys:
                        global_user_keys.add(k)
            else:
                if isinstance(global_user_keys, set):
                    global_user_keys |= src_user_keys
                else:
                    for k in src_user_keys:
                        global_user_keys[k] = None

            global_sid_map.update(src_sid_map)

    return {
        "domains": domains,
        "users": {
            "user_keys": global_user_keys if global_user_keys is not None else set(),
            "sid_map": global_sid_map,
        },
    }


# ---------------------------------------------------------------------------
# CloudResource conversion
# ---------------------------------------------------------------------------


def _parse_record_key_parts(record_key: str) -> tuple[str, str, str]:
    """Parse a record dedup key into (zone, owner, record_type).

    Key format: "{zone}|{owner}|{record_type}|{record_data}"
    """
    parts = record_key.split("|", 3)
    zone = parts[0] if len(parts) > 0 else ""
    owner = parts[1] if len(parts) > 1 else ""
    record_type = parts[2] if len(parts) > 2 else ""
    return zone, owner, record_type


def _to_cloud_resources(aggregated: dict, options: AdOptions) -> list[CloudResource]:
    """Convert aggregated collector data to CloudResource objects.

    Args:
        aggregated: Output of _aggregate_results().
        options: AdOptions instance for service filtering.

    Returns:
        List of CloudResource instances for all collected data.
    """
    resources: list[CloudResource] = []

    for domain, domain_data in aggregated["domains"].items():
        account_id = domain
        region = domain

        # -- DNS Zones --
        if "dns" in options.services and domain_data["dns"] is not None:
            dns = domain_data["dns"]

            for zone_name in _iter_container(dns["zone_keys"]):
                resources.append(
                    CloudResource(
                        resource_id=f"ad:dns-zone:{domain}:{zone_name}",
                        resource_type="ad-dns-zone",
                        provider="ad",
                        account_id=account_id,
                        region=region,
                        name=zone_name,
                        ip_addresses=[],
                        tags={},
                        details={"zone": zone_name, "domain": domain},
                    )
                )

            # -- DNS Records --
            for record_key in _iter_container(dns["record_keys"]):
                _zone, owner, record_type = _parse_record_key_parts(record_key)
                ip_str = _extract_ip_from_record_key(record_key, record_type)
                ip_addresses = [ip_str] if ip_str else []
                resources.append(
                    CloudResource(
                        resource_id=f"ad:dns-record:{record_key}",
                        resource_type="ad-dns-record",
                        provider="ad",
                        account_id=account_id,
                        region=region,
                        name=owner,
                        ip_addresses=ip_addresses,
                        tags={},
                        details={
                            "record_key": record_key,
                            "record_type": record_type,
                            "domain": domain,
                        },
                    )
                )

        # -- DHCP --
        if "dhcp" in options.services and domain_data["dhcp"] is not None:
            dhcp = domain_data["dhcp"]

            # Scopes
            for scope_id in _iter_container(dhcp["scope_keys"]):
                resources.append(
                    CloudResource(
                        resource_id=f"ad:dhcp-scope:{domain}:{scope_id}",
                        resource_type="ad-dhcp-scope",
                        provider="ad",
                        account_id=account_id,
                        region=region,
                        name=scope_id,
                        ip_addresses=[],
                        tags={},
                        details={"scope_id": scope_id, "domain": domain},
                    )
                )

            # Leases
            for lease_key in _iter_container(dhcp["lease_keys"]):
                # lease_key format from real collector: "scope_id|ip"
                # Mock format may just be "scope_id.ip" — attempt both splits
                if "|" in lease_key:
                    scope_id, ip = lease_key.split("|", 1)
                else:
                    # Mock uses "scope.ip" format — take last segment as IP
                    parts = lease_key.rsplit(".", 1)
                    scope_id = parts[0] if len(parts) > 1 else domain
                    ip = parts[-1]
                resources.append(
                    CloudResource(
                        resource_id=f"ad:dhcp-lease:{domain}:{lease_key}",
                        resource_type="ad-dhcp-ip",
                        provider="ad",
                        account_id=account_id,
                        region=region,
                        name=ip,
                        ip_addresses=[ip],
                        tags={},
                        details={"scope_id": scope_id, "lease_type": "lease", "domain": domain},
                    )
                )

            # Reservations
            for res_key in _iter_container(dhcp["reservation_keys"]):
                if "|" in res_key:
                    scope_id, ip = res_key.split("|", 1)
                else:
                    parts = res_key.rsplit(".", 1)
                    scope_id = parts[0] if len(parts) > 1 else domain
                    ip = parts[-1]
                resources.append(
                    CloudResource(
                        resource_id=f"ad:dhcp-reservation:{domain}:{res_key}",
                        resource_type="ad-dhcp-ip",
                        provider="ad",
                        account_id=account_id,
                        region=region,
                        name=ip,
                        ip_addresses=[ip],
                        tags={},
                        details={"scope_id": scope_id, "lease_type": "reservation", "domain": domain},
                    )
                )

    # -- Users (global, not per-domain) --
    if "user" in options.services:
        global_users = aggregated["users"]
        user_keys_container = global_users["user_keys"]
        sid_map = global_users["sid_map"]

        for user_key in _iter_container(user_keys_container):
            # Extract SID — from sid_map (real collector) or container value (mock)
            sid = sid_map.get(user_key, "")
            if not sid:
                sid = _extract_sid_from_user_entry(user_key, user_keys_container)

            # Determine account_id hint from key format
            if ":" in user_key:
                # Format: "sid:...", "upn:user@domain.com", "sam:username"
                prefix, rest = user_key.split(":", 1)
                if prefix == "upn" and "@" in rest:
                    domain_hint = rest.split("@", 1)[1]
                else:
                    domain_hint = "global"
            else:
                # Raw SID or other key — no domain hint
                domain_hint = "global"

            resources.append(
                CloudResource(
                    resource_id=f"ad:user:{user_key}",
                    resource_type="ad-user",
                    provider="ad",
                    account_id=domain_hint,
                    region=domain_hint,
                    name=user_key,
                    ip_addresses=["0.0.0.0"],
                    tags={},
                    details={"user_key": user_key, "sid": sid},
                )
            )

    return resources


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_ad_analysis(
    options: AdOptions,
    output_path: Optional[str] = None,
) -> tuple[list[CloudResource], list[str]]:
    """Run the full Microsoft AD analysis pipeline.

    Collects DNS, DHCP, and user data from all configured Domain Controllers,
    converts results to CloudResource objects, runs the categorization pipeline,
    and optionally writes an XLS report.

    Args:
        options: AdOptions configuration for the collection run.
        output_path: If provided, write an XLS report to this path.

    Returns:
        Tuple of (resources, errors):
            resources: List of CloudResource objects.
            errors: List of error message strings from failed DCs.
    """
    # Look up MicrosoftAdCollector and write_xlsx_report through the package
    # namespace at call time so unit-test patches applied at
    # cloud_usage.providers.ad.MicrosoftAdCollector / .write_xlsx_report are
    # picked up correctly.
    import sys
    _ad_pkg = sys.modules.get("cloud_usage.providers.ad")
    if _ad_pkg is not None:
        CollectorClass = _ad_pkg.MicrosoftAdCollector
        _write_xlsx = _ad_pkg.write_xlsx_report
    else:
        from .collector import MicrosoftAdCollector as CollectorClass  # type: ignore[assignment]
        from cloud_usage.output.xlsx_report import write_xlsx_report as _write_xlsx  # type: ignore[assignment]

    collector = CollectorClass(options)
    server_results = collector.collect_all()

    # Collect DC-level errors
    errors: list[str] = []
    for result in server_results:
        if result.get("status") == "error":
            server = result.get("server", "unknown")
            error_msg = result.get("error", "Unknown error")
            errors.append(f"DC {server}: {error_msg}")

    aggregated = _aggregate_results(server_results)
    resources = _to_cloud_resources(aggregated, options)
    categorize_resources(resources)

    if output_path is not None:
        _write_xlsx(
            filepath=output_path,
            resources=resources,
            account_summaries={},
            errors=errors,
            provider="ad",
        )

    return resources, errors
