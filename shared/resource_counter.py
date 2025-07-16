from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

from .constants import (
    DDI_RESOURCE_TYPES,
    ERROR_MESSAGES,
    IP_DETAIL_KEYS,
    SUPPORTED_PROVIDERS,
)


@dataclass
class ResourceCount:
    total_objects: int
    ddi_objects: int
    ddi_breakdown: Dict[str, int]
    active_ips: int
    ip_sources: Dict[str, int]
    breakdown_by_region: Dict[str, int]
    timestamp: str


class ResourceCounter:
    def __init__(self, provider: str):
        self.provider = provider.lower()
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                ERROR_MESSAGES["unsupported_provider"].format(
                    provider=provider, supported=SUPPORTED_PROVIDERS
                )
            )

    def count_resources(self, native_objects: List[Dict]) -> ResourceCount:
        if not native_objects:
            return self._create_empty_count()

        ddi_objects = self._get_ddi_objects(native_objects)
        active_ips = self._get_active_ips(native_objects)

        ddi_breakdown = self._calculate_ddi_breakdown(ddi_objects)
        ip_sources = self._calculate_ip_sources(native_objects)
        breakdown_by_region = self._calculate_breakdown_by_region(native_objects)

        return ResourceCount(
            total_objects=len(native_objects),
            ddi_objects=len(ddi_objects),
            ddi_breakdown=ddi_breakdown,
            active_ips=len(active_ips),
            ip_sources=ip_sources,
            breakdown_by_region=breakdown_by_region,
            timestamp=datetime.now().isoformat(),
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
            resource_type = obj.get("resource_type", "unknown")
            breakdown[resource_type] = breakdown.get(resource_type, 0) + 1
        return breakdown

    def _calculate_ip_sources(self, resources: List[Dict]) -> Dict[str, int]:
        sources = {}
        for resource in resources:
            details = resource.get("details", {})
            resource_type = resource.get("resource_type", "unknown")

            has_ip = False
            for key in IP_DETAIL_KEYS:
                if details.get(key):
                    has_ip = True
                    break

            if has_ip:
                sources[resource_type] = sources.get(resource_type, 0) + 1

        return sources

    def _calculate_breakdown_by_region(self, resources: List[Dict]) -> Dict[str, int]:
        breakdown = {}
        for resource in resources:
            region = resource.get("region", "unknown")
            breakdown[region] = breakdown.get(region, 0) + 1
        return breakdown

    def _get_ddi_objects(self, resources: List[Dict]) -> List[Dict]:
        ddi_types = DDI_RESOURCE_TYPES.get(self.provider, [])
        return [r for r in resources if r.get("resource_type") in ddi_types]

    def _get_active_ips(self, resources: List[Dict]) -> List[str]:
        ip_set = set()
        for resource in resources:
            details = resource.get("details", {})

            for key in IP_DETAIL_KEYS:
                ip = details.get(key)
                if ip and isinstance(ip, str):
                    ip_set.add(ip)

            for key in ["private_ips", "public_ips"]:
                ips = details.get(key)
                if ips and isinstance(ips, list):
                    for ip in ips:
                        if ip:
                            ip_set.add(ip)

            if resource.get("resource_type") == "subnet" and "discovered_ips" in details:
                for ip in details["discovered_ips"]:
                    if ip:
                        ip_set.add(ip)

        return list(ip_set)
