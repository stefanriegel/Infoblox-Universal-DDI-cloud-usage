"""Constants for the Microsoft AD provider.

SUPPORTED_DNS_RECORD_TYPES: DNS record types collected and counted as DDI objects.
AD_SERVICES: Valid service identifiers for the --ad-services CLI option.
"""

from __future__ import annotations

# 13 DNS record types matching the reference microsoft_ad.py implementation.
SUPPORTED_DNS_RECORD_TYPES: frozenset[str] = frozenset(
    {
        "A",
        "AAAA",
        "CNAME",
        "MX",
        "TXT",
        "CAA",
        "SRV",
        "SVCB",
        "HTTPS",
        "PTR",
        "NS",
        "SOA",
        "NAPTR",
    }
)

# Valid service names for --ad-services CLI option.
AD_SERVICES: tuple[str, ...] = ("dns", "dhcp", "user")
