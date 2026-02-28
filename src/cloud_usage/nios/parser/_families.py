"""NIOS Grid object family definitions and XML type-to-family mapping.

MEMBER_SCOPED_FAMILIES: families whose objects carry a vnode_id or virtual_oid attribute
    and should have a resolved member_hostname. Missing resolution generates a warning.
    NOTE: Based on the ZF Friedrichshafen reference backup (2026-02-28 discovery),
    only LEASE objects carry a direct member attribution field (vnode_id).
    Other DHCP families (NETWORK, FIXED_ADDRESS, DHCP_RANGE, etc.) use network_view
    references, not direct member IDs — they are classified as grid-level in this backup.
    If a different NIOS version or backup style uses virtual_oid on network objects,
    revisit this classification.

GRID_LEVEL_FAMILIES: families where member_hostname=None is valid by design.

ALL_EXPECTED_FAMILIES: union used by IntegrityReport to detect missing families.

_XML_TYPE_TO_FAMILY: maps raw __type PROPERTY VALUE strings to NiosFamily string constants.
    Each entry includes a comment citing the observed count from the ZF Friedrichshafen
    reference backup (do_not_commit/ZF-database-11_1752136302416.bak.reset.tar.gz,
    discovery run on 2026-02-28).

CRITICAL STRUCTURAL DISCOVERY (2026-02-28):
    The onedb.xml format does NOT use XML element attributes for type discrimination.
    Instead, every <OBJECT> element has a child <PROPERTY NAME="__type" VALUE="..."/> that
    carries the fully-qualified Java class name (e.g., ".com.infoblox.dns.lease").
    The VALUE attribute (not text content) holds the type string.
    The DATABASE element at the start of the file uses XML attributes: VERSION="..." etc.

MEMBER ATTRIBUTION DISCOVERY (2026-02-28):
    - virtual_node.virtual_oid: the member OID key (integer string, e.g., "101")
    - virtual_node.host_name: the resolved FQDN (e.g., "frdn77x00.emea.zf-world.com")
    - lease.vnode_id: references virtual_node.virtual_oid for member attribution
    - network, fixed_address, dhcp_range, network_container, host, host_address:
      NO direct member attribution field in this NIOS version — use network_view (int ref)
    - All DNS records, DNS zones, network_view: no member attribution by design

NIOS VERSION FIELD (for Plan 03):
    The DATABASE element has VERSION as an XML attribute (not a PROPERTY child):
    <DATABASE NAME="onedb" VERSION="9.0.6-53318-82020f7ffaad" ...>
    Parser must read elem.get('VERSION') on the DATABASE XML element, not from props dict.

SNAPSHOT DATE (for Plan 03):
    Derived from tar member mtime: datetime.fromtimestamp(member.mtime, utc).strftime('%Y-%m-%d')
    ZF reference backup: mtime=1755006724 -> 2025-08-12
"""

from __future__ import annotations

from cloud_usage.nios.schema import NiosFamily

# Member-scoped families: objects that carry a direct member attribution field.
# Based on ZF Friedrichshafen reference backup (2026-02-28):
# - LEASE is the only family with a direct vnode_id member attribution field.
# - Other DHCP objects (network, fixed_address, dhcp_range, network_container,
#   host, host_address) reference network_view (int ID), not a direct member OID.
# - If a future backup version adds virtual_oid to network objects, add them here.
# Unresolvable vnode_id for MEMBER_SCOPED_FAMILIES generates an IntegrityReport warning.
MEMBER_SCOPED_FAMILIES: frozenset[str] = frozenset(
    {
        NiosFamily.LEASE,  # lease.vnode_id -> virtual_node.virtual_oid
    }
)

# Grid-level families: member_hostname=None is valid by design, no attribution warning.
# Includes all object families from the ZF backup that have no direct member OID field.
GRID_LEVEL_FAMILIES: frozenset[str] = frozenset(
    {
        NiosFamily.MEMBER,  # member is its own identity; it IS the grid node
        NiosFamily.NETWORK,  # no vnode_id in ZF backup; uses network_view ref only
        NiosFamily.FIXED_ADDRESS,  # no vnode_id in ZF backup
        NiosFamily.HOST_ADDRESS,  # no vnode_id in ZF backup
        NiosFamily.HOST_OBJECT,  # no vnode_id in ZF backup
        NiosFamily.HOST_ALIAS,  # no vnode_id in ZF backup
        NiosFamily.DHCP_RANGE,  # no vnode_id in ZF backup
        NiosFamily.EXCLUSION_RANGE,  # no vnode_id in ZF backup
        NiosFamily.NETWORK_CONTAINER,  # no vnode_id in ZF backup
        NiosFamily.NETWORK_VIEW,  # grid-level container object
        NiosFamily.DNS_ZONE,  # zone is grid-level
        NiosFamily.DNS_RECORD_A,  # no member attribution in ZF backup
        NiosFamily.DNS_RECORD_AAAA,  # no member attribution in ZF backup
        NiosFamily.DNS_RECORD_CNAME,  # no member attribution in ZF backup
        NiosFamily.DNS_RECORD_MX,  # no member attribution in ZF backup
        NiosFamily.DNS_RECORD_NS,  # no member attribution in ZF backup
        NiosFamily.DNS_RECORD_PTR,  # no member attribution in ZF backup
        NiosFamily.DNS_RECORD_SOA,  # no member attribution in ZF backup
        NiosFamily.DNS_RECORD_SRV,  # no member attribution in ZF backup
        NiosFamily.DNS_RECORD_TXT,  # no member attribution in ZF backup
    }
)

ALL_EXPECTED_FAMILIES: frozenset[str] = MEMBER_SCOPED_FAMILIES | GRID_LEVEL_FAMILIES

# Observed __type PROPERTY VALUE strings from ZF Friedrichshafen reference backup (2026-02-28).
# Discovery command: iterated all 2,506,601 OBJECT elements; each type counted below.
# Format: "__type VALUE string": NiosFamily.CONSTANT  # N observed
# Families NOT observed in this backup are listed at the bottom with # 0 observed comment.
_XML_TYPE_TO_FAMILY: dict[str, str] = {
    # ---- LEASE ----------------------------------------------------------------
    ".com.infoblox.dns.lease": NiosFamily.LEASE,  # 605,489 observed
    # ---- DNS RECORDS ----------------------------------------------------------
    ".com.infoblox.dns.bind_ptr": NiosFamily.DNS_RECORD_PTR,  # 172,715 observed
    ".com.infoblox.dns.bind_a": NiosFamily.DNS_RECORD_A,  # 158,110 observed
    ".com.infoblox.dns.bind_txt": NiosFamily.DNS_RECORD_TXT,  # 148,272 observed
    ".com.infoblox.dns.bind_srv": NiosFamily.DNS_RECORD_SRV,  # 22,464 observed
    ".com.infoblox.dns.bind_soa": NiosFamily.DNS_RECORD_SOA,  # 18,987 observed
    ".com.infoblox.dns.bind_cname": NiosFamily.DNS_RECORD_CNAME,  # 3,859 observed
    ".com.infoblox.dns.bind_aaaa": NiosFamily.DNS_RECORD_AAAA,  # 196 observed
    ".com.infoblox.dns.bind_mx": NiosFamily.DNS_RECORD_MX,  # 17 observed
    ".com.infoblox.dns.bind_ns": NiosFamily.DNS_RECORD_NS,  # 889 observed
    # ---- HOST OBJECTS ---------------------------------------------------------
    ".com.infoblox.dns.host_address": NiosFamily.HOST_ADDRESS,  # 130,963 observed
    ".com.infoblox.dns.host": NiosFamily.HOST_OBJECT,  # 129,930 observed
    # ---- NETWORK OBJECTS ------------------------------------------------------
    ".com.infoblox.dns.network": NiosFamily.NETWORK,  # 49,437 observed
    ".com.infoblox.dns.fixed_address": NiosFamily.FIXED_ADDRESS,  # 25,817 observed
    ".com.infoblox.dns.host_alias": NiosFamily.HOST_ALIAS,  # 15,799 observed
    ".com.infoblox.dns.dhcp_range": NiosFamily.DHCP_RANGE,  # 7,430 observed
    ".com.infoblox.dns.network_container": NiosFamily.NETWORK_CONTAINER,  # 1,837 observed
    ".com.infoblox.dns.exclusion_range": NiosFamily.EXCLUSION_RANGE,  # 1,815 observed
    # ---- DNS ZONE -------------------------------------------------------------
    ".com.infoblox.dns.zone": NiosFamily.DNS_ZONE,  # 19,395 observed
    # ---- NETWORK VIEW ---------------------------------------------------------
    ".com.infoblox.dns.network_view": NiosFamily.NETWORK_VIEW,  # 1 observed
    # ---- MEMBER (virtual_node = Grid Member node) -----------------------------
    # NOTE: The Java class is .com.infoblox.one.virtual_node, NOT "Member:Grid".
    # The virtual_oid and host_name fields are the keys for the member map.
    # virtual_oid (integer string) is referenced by lease.vnode_id.
    ".com.infoblox.one.virtual_node": NiosFamily.MEMBER,  # 239 observed
}

# Which __type strings correspond to Member objects.
# Used in Pass 1 of the two-pass parser to build the virtual_oid -> hostname map.
# Pass 1 reads: virtual_node.virtual_oid (key) -> virtual_node.host_name (value).
_MEMBER_XML_TYPES: frozenset[str] = frozenset(
    t for t, f in _XML_TYPE_TO_FAMILY.items() if f == NiosFamily.MEMBER
)
