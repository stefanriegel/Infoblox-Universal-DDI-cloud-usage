from dataclasses import dataclass
from datetime import datetime
import ipaddress
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

from .constants import (
    DDI_RESOURCE_TYPES,
    ERROR_MESSAGES,
    IP_DETAIL_KEYS,
    SUPPORTED_PROVIDERS,
)

# Source definitions for active IP extraction. DNS-derived keys are intentionally excluded.
# Maps detail key -> (source_category, ip_role)
_IP_KEY_MAP: Dict[str, Tuple[str, str]] = {
    # Attached / discovered
    "ip": ("discovered", "unknown"),
    "private_ip": ("discovered", "private"),
    "public_ip": ("discovered", "public"),
    "private_ips": ("discovered", "private"),
    "public_ips": ("discovered", "public"),
    "ipv6_ip": ("discovered", "private"),
    "ipv6_ips": ("discovered", "private"),
    "discovered_ips": ("discovered", "unknown"),
    # Allocated/reserved/fixed/lease sources (when present)
    "reserved_ips": ("allocated", "unknown"),
    "reservation_ips": ("allocated", "unknown"),
    "elastic_ip": ("allocated", "public"),
    "elastic_ips": ("allocated", "public"),
    "fixed_ips": ("fixed", "unknown"),
    "fixed_addresses": ("fixed", "unknown"),
    "dhcp_lease_ips": ("dhcp_lease", "unknown"),
    "lease_ips": ("dhcp_lease", "unknown"),
    # Azure/GCP common field name for allocated public IP resources.
    "ip_address": ("allocated", "unknown"),
}


@dataclass
class ResourceCount:
    total_objects: int
    ddi_objects: int
    ddi_breakdown: Dict[str, int]
    active_ips: int
    ip_sources: Dict[str, int]
    breakdown_by_region: Dict[str, int]
    timestamp: str

    # Extra details for transparency/auditing.
    # Note: counts can overlap and are not additive.
    active_ip_breakdown: Optional[Dict[str, int]] = None
    active_ip_breakdown_by_space: Optional[Dict[str, int]] = None


class ResourceCounter:
    def __init__(self, provider: str):
        self.provider = provider.lower()
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError(ERROR_MESSAGES["unsupported_provider"].format(provider=provider, supported=SUPPORTED_PROVIDERS))

    def count_resources(self, native_objects: List[Dict]) -> ResourceCount:
        if not native_objects:
            return self._create_empty_count()

        ddi_objects = self._get_ddi_objects(native_objects)

        active_ip_pairs = self._get_active_ip_pairs(native_objects)
        active_ip_breakdown = self._calculate_active_ip_breakdown(active_ip_pairs)
        active_ip_breakdown_by_space = self._calculate_active_ip_breakdown_by_space(active_ip_pairs)

        ddi_breakdown = self._calculate_ddi_breakdown(ddi_objects)
        ip_sources = self._calculate_ip_sources(native_objects)
        breakdown_by_region = self._calculate_breakdown_by_region(native_objects)

        return ResourceCount(
            total_objects=len(native_objects),
            ddi_objects=len(ddi_objects),
            ddi_breakdown=ddi_breakdown,
            active_ips=len(active_ip_pairs),
            ip_sources=ip_sources,
            breakdown_by_region=breakdown_by_region,
            timestamp=datetime.now().isoformat(),
            active_ip_breakdown=active_ip_breakdown,
            active_ip_breakdown_by_space=active_ip_breakdown_by_space,
        )

    def count_active_ip_metrics(
        self,
        resources: List[Dict],
    ) -> tuple[int, Dict[str, int], Dict[str, int]]:
        """Count active IPs with IP-space de-duplication.

        Returns:
          - total unique active IPs (deduped by inferred IP Space)
          - breakdown by source category (counts may overlap)
          - breakdown by inferred IP Space
        """
        pairs = self._get_active_ip_pairs(resources)
        return (
            len(pairs),
            self._calculate_active_ip_breakdown(pairs),
            self._calculate_active_ip_breakdown_by_space(pairs),
        )

    def _create_empty_count(self) -> ResourceCount:
        return ResourceCount(
            total_objects=0,
            ddi_objects=0,
            ddi_breakdown={},
            active_ips=0,
            ip_sources={},
            breakdown_by_region={},
            timestamp=datetime.now().isoformat(),
        )

    def _calculate_ddi_breakdown(self, ddi_objects: List[Dict]) -> Dict[str, int]:
        breakdown = {}
        for obj in ddi_objects:
            resource_type = obj.get("resource_type")
            if not resource_type or resource_type == "unknown":
                continue
            breakdown[resource_type] = breakdown.get(resource_type, 0) + 1
        return breakdown

    def _calculate_ip_sources(self, resources: List[Dict]) -> Dict[str, int]:
        sources = {}
        for resource in resources:
            details = resource.get("details", {})
            resource_type = resource.get("resource_type")

            has_ip = False
            for key in IP_DETAIL_KEYS:
                if details.get(key):
                    has_ip = True
                    break

            if has_ip:
                if not resource_type or resource_type == "unknown":
                    continue
                sources[resource_type] = sources.get(resource_type, 0) + 1

        return sources

    def _calculate_breakdown_by_region(self, resources: List[Dict]) -> Dict[str, int]:
        breakdown = {}
        for resource in resources:
            region = resource.get("region", "unknown")
            breakdown[region] = breakdown.get(region, 0) + 1
        return breakdown

    def _canonicalize_ip(self, value: Any) -> Optional[str]:
        """Return a canonical IPv4/IPv6 string or None."""
        if not isinstance(value, str):
            return None
        value = value.strip()
        if not value:
            return None
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            return None

    def _iter_ip_strings(self, value: Any) -> Iterable[str]:
        """Yield canonical IP strings from str|list|dict inputs."""
        if isinstance(value, str):
            ip = self._canonicalize_ip(value)
            if ip:
                yield ip
            return

        if isinstance(value, list):
            for item in value:
                yield from self._iter_ip_strings(item)
            return

        if isinstance(value, dict):
            # Common shapes: {"ip": "..."} or {"ip_address": "..."}
            for k in ("ip", "ip_address", "address"):
                if k in value:
                    yield from self._iter_ip_strings(value.get(k))
            return

    def _infer_network_space(self, details: Dict[str, Any]) -> Optional[str]:
        """Best-effort IP-space identifier derived from network context."""
        if self.provider == "aws":
            vpc_id = details.get("vpc_id") or details.get("VpcId")
            if isinstance(vpc_id, str) and vpc_id:
                return f"aws:vpc:{vpc_id}"
            return None

        if self.provider == "azure":
            vnet_id = details.get("vnet_id") or details.get("virtual_network_id")
            if not vnet_id:
                subnet_id = details.get("subnet_id") or details.get("subnetId") or details.get("id")
                if isinstance(subnet_id, str) and "/subnets/" in subnet_id.lower():
                    # Strip trailing "/subnets/<name>".
                    idx = subnet_id.lower().rfind("/subnets/")
                    vnet_id = subnet_id[:idx]
            if isinstance(vnet_id, str) and vnet_id:
                return f"azure:vnet:{vnet_id}"
            return None

        if self.provider == "gcp":
            network = details.get("network") or details.get("vpc_network")
            if isinstance(network, str) and network:
                return f"gcp:network:{network}"
            return None

        return None

    def _infer_ip_space(self, resource: Dict[str, Any], ip: str, ip_role: str) -> str:
        """Infer the IP Space for de-duplication.

        We de-duplicate by (ip_space, ip). This avoids undercounting when
        the same RFC1918/ULA IP exists in multiple VPCs/VNets.
        """
        details = (resource.get("details") or {}) if isinstance(resource, dict) else {}
        rtype = (resource.get("resource_type") or "").lower() if isinstance(resource, dict) else ""

        # Public addresses are treated as their own space.
        if ip_role == "public" or rtype in {"elastic-ip", "public-ip", "external-ip"}:
            return f"{self.provider}:public"

        # Prefer network-derived space when possible.
        net_space = self._infer_network_space(details)
        if net_space:
            return net_space

        # Heuristic fallback for unknown role.
        if ip_role != "private":
            try:
                ip_obj = ipaddress.ip_address(ip)
                if getattr(ip_obj, "is_global", False):
                    return f"{self.provider}:public"
            except ValueError:
                pass

        return f"{self.provider}:unknown"

    def _extract_active_ip_tuples(self, resource: Dict[str, Any]) -> Iterable[Tuple[str, str, str]]:
        """Yield (ip, role, source) tuples from a resource."""
        details = (resource.get("details") or {}) if isinstance(resource, dict) else {}

        for key, (source, role) in _IP_KEY_MAP.items():
            if key not in details:
                continue
            for ip in self._iter_ip_strings(details.get(key)):
                yield (ip, role, source)

    def _iter_cidr_strings(self, value: Any) -> Iterable[str]:
        if isinstance(value, str):
            v = value.strip()
            if v:
                yield v
            return
        if isinstance(value, list):
            for item in value:
                yield from self._iter_cidr_strings(item)

    def _parse_cidr(self, cidr: str) -> Optional[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
        try:
            return ipaddress.ip_network(cidr, strict=False)
        except ValueError:
            return None

    def _iter_subnet_cidrs(self, details: Dict[str, Any]) -> Iterable[str]:
        # Common CIDR fields across providers.
        for key in (
            "cidr_block",
            "CidrBlock",
            "ip_cidr_range",
            "ipCidrRange",
            "address_prefix",
            "addressPrefix",
            "address_prefixes",
            "addressPrefixes",
            "ipv6_cidr_block",
            "ipv6_cidr_blocks",
            "ipv6_cidr_range",
            "ipv6CidrRange",
        ):
            if key in details:
                yield from self._iter_cidr_strings(details.get(key))

        # AWS IPv6 association set shape (if present).
        assoc = details.get("ipv6_cidr_block_association_set") or details.get("Ipv6CidrBlockAssociationSet")
        if isinstance(assoc, list):
            for item in assoc:
                if isinstance(item, dict) and "Ipv6CidrBlock" in item:
                    yield from self._iter_cidr_strings(item.get("Ipv6CidrBlock"))

    def _iter_subnet_reservation_ips(self, resource: Dict[str, Any]) -> Iterable[str]:
        """Generate provider-reserved addresses for a subnet CIDR."""
        if (resource.get("resource_type") or "").lower() != "subnet":
            return

        details = resource.get("details") or {}
        seen: Set[str] = set()

        for cidr in self._iter_subnet_cidrs(details):
            net = self._parse_cidr(cidr)
            if not net:
                continue

            # Provider reservation rules are based on official provider docs.
            if self.provider in {"aws", "azure"}:
                # First four + last one (IPv4+IPv6).
                for offset in (0, 1, 2, 3):
                    if offset >= net.num_addresses:
                        continue
                    ip_s = str(net.network_address + offset)
                    if ip_s not in seen:
                        seen.add(ip_s)
                        yield ip_s
                # Last address in the CIDR.
                try:
                    ip_s = str(net[-1])
                    if ip_s not in seen:
                        seen.add(ip_s)
                        yield ip_s
                except IndexError:
                    continue

            elif self.provider == "gcp":
                # Google Cloud primary IPv4 range: first two + last two.
                if net.version != 4:
                    continue
                for idx in (0, 1, -2, -1):
                    try:
                        ip_s = str(net[idx])
                    except IndexError:
                        continue
                    if ip_s not in seen:
                        seen.add(ip_s)
                        yield ip_s

            else:
                # Conservative fallback: first + last for any CIDR.
                for idx in (0, -1):
                    try:
                        ip_s = str(net[idx])
                    except IndexError:
                        continue
                    if ip_s not in seen:
                        seen.add(ip_s)
                        yield ip_s

    def _get_active_ip_pairs(self, resources: List[Dict]) -> Dict[Tuple[str, str], Set[str]]:
        """Return mapping of (ip_space, ip) -> set(sources)."""
        pairs: Dict[Tuple[str, str], Set[str]] = {}
        for resource in resources:
            for ip, role, source in self._extract_active_ip_tuples(resource):
                ip_space = self._infer_ip_space(resource, ip, role)
                key = (ip_space, ip)
                pairs.setdefault(key, set()).add(source)

            # Include provider subnet reservations as active IPs.
            for ip in self._iter_subnet_reservation_ips(resource):
                ip_space = self._infer_ip_space(resource, ip, "private")
                key = (ip_space, ip)
                pairs.setdefault(key, set()).add("subnet_reservation")

        return pairs

    def _calculate_active_ip_breakdown(self, active_ip_pairs: Dict[Tuple[str, str], Set[str]]) -> Dict[str, int]:
        """Count unique IPs per source category (not additive)."""
        counts: Dict[str, int] = {}
        for _pair, sources in active_ip_pairs.items():
            for src in sources:
                counts[src] = counts.get(src, 0) + 1
        return counts

    def _calculate_active_ip_breakdown_by_space(self, active_ip_pairs: Dict[Tuple[str, str], Set[str]]) -> Dict[str, int]:
        """Count unique IPs per inferred IP space."""
        counts: Dict[str, int] = {}
        for (space, _ip), _sources in active_ip_pairs.items():
            counts[space] = counts.get(space, 0) + 1
        return counts

    def _get_ddi_objects(self, resources: List[Dict]) -> List[Dict]:
        ddi_types = DDI_RESOURCE_TYPES.get(self.provider, [])
        return [r for r in resources if r.get("resource_type") in ddi_types]
