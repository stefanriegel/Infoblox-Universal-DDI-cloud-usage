"""NIOS Grid backup typed schema.

Defines the three core types used throughout Phase 10-15:
- NiosFamily: string constants for all object families discovered in the ZF reference backup
- NiosObject: frozen dataclass yielded by parse_backup() for every extracted object
- IntegrityReport: frozen dataclass returned by inspect_backup() for structural analysis

Design notes:
- NiosFamily uses a plain class with string class variables for Python 3.9 compatibility
  (StrEnum requires Python 3.11+).
- NiosObject.frozen=True enforces immutability; raw_attrs is dict[str, str] that callers
  must not mutate after construction (frozen=True prevents field reassignment, not dict mutation).
- IntegrityReport.frozen=True with mutable fields (dict, list) follows the same convention;
  callers should treat families_found and warnings as read-only.
"""

from __future__ import annotations

from dataclasses import dataclass


class NiosFamily:
    """String constants for all 26 NIOS object families.

    These constants are used as the family field in NiosObject and as keys in
    IntegrityReport.families_found. All values are lowercase snake_case strings.

    The 13 minimum families required by PARSE-05 through PARSE-12 are present,
    plus additional families discovered in the ZF Friedrichshafen reference backup
    (do_not_commit/ZF-database-11_1752136302416.bak.reset.tar.gz, discovered 2026-02-28).
    Five DTC (DNS Traffic Control) families were added in Phase 16 (2026-03-02) based
    on spec derivation; their XML __type strings are unverified against a real backup.

    Note on member attribution (critical for Phase 10 two-pass parser design):
    - MEMBER is the identity object; its virtual_oid is the key in the member map.
    - LEASE carries vnode_id which is the member attribution field (maps to virtual_oid).
    - Other DHCP families (NETWORK, FIXED_ADDRESS, DHCP_RANGE, etc.) do not carry a direct
      member attribution field in this NIOS version — they reference network_view instead.
    - DNS families are grid-level: no member attribution by design.
    - DTC families are grid-level: no member attribution (DTC-07).
    """

    MEMBER = "member"
    NETWORK = "network"
    LEASE = "lease"
    FIXED_ADDRESS = "fixed_address"
    HOST_ADDRESS = "host_address"
    DNS_ZONE = "dns_zone"
    DNS_RECORD_A = "dns_record_a"
    DNS_RECORD_AAAA = "dns_record_aaaa"
    DNS_RECORD_CNAME = "dns_record_cname"
    DNS_RECORD_MX = "dns_record_mx"
    DNS_RECORD_NS = "dns_record_ns"
    DNS_RECORD_PTR = "dns_record_ptr"
    DNS_RECORD_SOA = "dns_record_soa"
    DNS_RECORD_SRV = "dns_record_srv"
    DNS_RECORD_TXT = "dns_record_txt"
    HOST_OBJECT = "host_object"
    HOST_ALIAS = "host_alias"
    DHCP_RANGE = "dhcp_range"
    EXCLUSION_RANGE = "exclusion_range"
    NETWORK_CONTAINER = "network_container"
    NETWORK_VIEW = "network_view"
    # ---- DTC (DNS Traffic Control) ----
    DTC_LBDN = "dtc_lbdn"
    DTC_POOL = "dtc_pool"
    DTC_SERVER = "dtc_server"
    DTC_MONITOR = "dtc_monitor"
    DTC_TOPOLOGY = "dtc_topology"


@dataclass(frozen=True)
class NiosObject:
    """A single extracted NIOS Grid object, fully member-resolved.

    Yielded by parse_backup() for every object across all 26 known families.
    The parser resolves member identity internally; callers receive only resolved instances.

    Args:
        family: Object family discriminator (NiosFamily constant, e.g. NiosFamily.NETWORK).
            Callers use this field to select counting logic in Phase 11.
        member_hostname: Resolved FQDN/hostname of the owning member, or None if:
            (a) the family is grid-level (DNS records, zones, network views), or
            (b) the object is member-scoped but its vnode_id/virtual_oid could not be
                resolved from the member map (unresolvable OID, also surfaces in
                IntegrityReport.warnings).
        raw_attrs: All XML PROPERTY elements from the OBJECT element, preserved verbatim.
            Keys are PROPERTY NAME values; values are PROPERTY VALUE (or text) strings.
            Phase 11 reads specific keys (e.g., 'ip_address', 'binding_state', 'cidr')
            from this dict. Do not mutate after construction.
    """

    family: str
    member_hostname: str | None
    raw_attrs: dict[str, str]


@dataclass(frozen=True)
class IntegrityReport:
    """Structural integrity report returned by inspect_backup().

    Callers (Phase 13 report generator, Phase 14 CLI) use this to display backup
    health information and to populate the report header block.

    Args:
        families_found: Map of family name -> object count for every family encountered
            during the full parse pass. Families with 0 objects are NOT included unless
            they are in ALL_EXPECTED_FAMILIES (the parser pre-populates them at 0).
        warnings: Human-readable warning strings. Populated for:
            (1) Any expected family in ALL_EXPECTED_FAMILIES has 0 rows.
            (2) N objects referenced a vnode_id/virtual_oid not in the member map.
            (3) Member map is empty (no virtual_node objects in backup).
        nios_version: NIOS version string extracted from the DATABASE element VERSION
            attribute (e.g., '9.0.6-53318-82020f7ffaad'). None if the element is absent.
        snapshot_date: Backup snapshot date derived from the onedb.xml tar member mtime,
            formatted as 'YYYY-MM-DD' in UTC (e.g., '2025-08-12'). None if not determinable.

    Note: frozen=True prevents field reassignment but not mutation of the dict/list values.
    Treat families_found and warnings as read-only after construction.
    """

    families_found: dict[str, int]
    warnings: list[str]
    nios_version: str | None
    snapshot_date: str | None
