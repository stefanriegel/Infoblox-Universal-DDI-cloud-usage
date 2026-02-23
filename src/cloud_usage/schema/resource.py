"""
Unified cloud resource schema for all providers.

Defines the CloudResource dataclass that represents any discovered cloud
resource from AWS, Azure, or GCP in a provider-agnostic format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CloudResource:
    """Unified representation of a cloud resource from any provider.

    Every discovered resource (VM, subnet, DNS zone, etc.) is normalized
    into this shape regardless of originating cloud provider. Fields cover
    identity, location, networking, tagging, and categorization for token
    calculation.

    Args:
        resource_id: Provider-native ID (ARN, Azure resource ID, GCP self_link).
        resource_type: Normalized type (e.g., "vm", "subnet", "dns-zone").
        provider: Cloud provider identifier ("aws", "azure", "gcp").
        account_id: AWS account ID, Azure subscription ID, or GCP project ID.
        region: Cloud region where the resource resides.
        name: Human-readable resource name.
        ip_addresses: All IPs (private + public) associated with the resource.
        tags: Resource tags as key-value pairs.
        details: Provider-specific raw data for auditability.
        discovered_at: ISO timestamp of when the resource was discovered.
        counted: True if counted toward tokens, None until categorization.
        category: Token category ("ddi", "ip", "asset") or None if excluded.
        skip_reason: Why excluded from counting (e.g., "token-free: EBS Volume").
    """

    resource_id: str
    resource_type: str
    provider: str
    account_id: str
    region: str
    name: str
    ip_addresses: list[str] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    discovered_at: str = field(default_factory=lambda: datetime.now().isoformat())
    counted: bool | None = None
    category: str | None = None
    skip_reason: str | None = None

    def has_ips(self) -> bool:
        """Return True if this resource has any associated IP addresses."""
        return len(self.ip_addresses) > 0
