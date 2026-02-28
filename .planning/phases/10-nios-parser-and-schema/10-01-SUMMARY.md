---
phase: 10-nios-parser-and-schema
plan: 01
subsystem: parser
tags: [lxml, nios, tarfile, xml, dataclass, streaming-parser, schema]

# Dependency graph
requires: []
provides:
  - "src/cloud_usage/nios/ package skeleton with NiosFamily, NiosObject, IntegrityReport, NiosParseError"
  - "Empirical _XML_TYPE_TO_FAMILY mapping from ZF Friedrichshafen reference backup"
  - "MEMBER_SCOPED_FAMILIES and GRID_LEVEL_FAMILIES frozensets validated against actual backup"
  - "parser/__init__.py stub exporting parse_backup and inspect_backup for Plans 02/03"
affects:
  - "10-nios-parser-and-schema (Plans 02, 03, 04)"
  - "11-nios-filter-and-counter"
  - "12-nios-report-generator"
  - "13-nios-cli-integration"
  - "14-nios-dashboard-upload"

# Tech tracking
tech-stack:
  added:
    - "lxml>=5.3.0 (6.0.2 installed) — C-backed streaming XML parser for 2GB+ onedb.xml"
  patterns:
    - "PROPERTY NAME='__type' VALUE pattern — NIOS onedb.xml type discrimination (NOT XML element attribute)"
    - "lxml iterparse with tag='OBJECT', recover=True, huge_tree=True — memory-flat streaming"
    - "tarfile.open('r:gz') + extractfile() — no disk extraction for .tar.gz archives"
    - "Frozen dataclass (frozen=True) for read-only parsed objects"
    - "Plain class with string constants for Python 3.9-compatible enum-like discriminator"

key-files:
  created:
    - "src/cloud_usage/nios/__init__.py"
    - "src/cloud_usage/nios/errors.py"
    - "src/cloud_usage/nios/schema.py"
    - "src/cloud_usage/nios/parser/__init__.py"
    - "src/cloud_usage/nios/parser/_families.py"
  modified:
    - "requirements.txt"

key-decisions:
  - "XML type discovery revealed PROPERTY NAME='__type' VALUE pattern (not XML type= attribute) — required changing all parser logic"
  - "LEASE is the only MEMBER_SCOPED family — lease.vnode_id -> virtual_node.virtual_oid is the only direct member attribution in ZF backup"
  - "All other DHCP families (network, fixed_address, dhcp_range, network_container, host, host_address) have no vnode_id — classified as GRID_LEVEL"
  - "Member identity type is .com.infoblox.one.virtual_node (not 'Member:Grid' as hypothesized in RESEARCH.md)"
  - "Member hostname field is virtual_node.host_name; member key is virtual_node.virtual_oid"
  - "DATABASE version is a XML element attribute VERSION='9.0.6-53318-82020f7ffaad' (read via elem.get('VERSION'), not from PROPERTY children)"
  - "Snapshot date derived from tar member mtime (1755006724 -> 2025-08-12)"

patterns-established:
  - "Type extraction pattern: iterate PROPERTY children, match NAME='__type', read VALUE attribute"
  - "All 21 families covered: 1 MEMBER_SCOPED (lease), 20 GRID_LEVEL"

requirements-completed:
  - PARSE-01
  - PARSE-02
  - PARSE-03
  - PARSE-04
  - PARSE-05
  - PARSE-06
  - PARSE-07
  - PARSE-08
  - PARSE-09
  - PARSE-10
  - PARSE-11
  - PARSE-12
  - PARSE-13

# Metrics
duration: 35min
completed: 2026-02-28
---

# Phase 10 Plan 01: NIOS Schema and XML Type Discovery Summary

**lxml-based NIOS package skeleton with 21 empirically-discovered XML type mappings from the ZF Friedrichshafen reference backup, plus frozen NiosObject/IntegrityReport dataclasses and NiosParseError**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-02-28T19:20:00Z
- **Completed:** 2026-02-28T19:58:37Z
- **Tasks:** 2
- **Files modified:** 6 (5 created, 1 modified)

## Accomplishments

- Ran full XML type discovery against the ZF reference backup (2,506,601 objects), revealing the PROPERTY NAME='__type' VALUE= pattern — a critical structural difference from the hypothesized XML attribute format
- Built empirical `_XML_TYPE_TO_FAMILY` with 21 actual type strings and counts, eliminating all "requires backup validation" uncertainty from the phase
- Validated MEMBER_SCOPED vs GRID_LEVEL classification: only LEASE carries `vnode_id` for member attribution; all other families are grid-level in this NIOS version
- Confirmed virtual_node as the member object type (not "Member:Grid"), with `host_name` and `virtual_oid` fields as the member map keys

## Task Commits

Each task was committed atomically:

1. **Task 1: Discover XML type strings and create schema files** - `4eade18` (feat)
2. **Task 2: Build _families.py with empirical XML type mapping and parser stub** - `043eacc` (feat)

## Files Created/Modified

- `src/cloud_usage/nios/__init__.py` — Package marker with docstring
- `src/cloud_usage/nios/errors.py` — NiosParseError(Exception) for unrecoverable backup failures
- `src/cloud_usage/nios/schema.py` — NiosObject (frozen, 3 fields), IntegrityReport (frozen, 4 fields), NiosFamily (21 string constants, Python 3.9 compatible)
- `src/cloud_usage/nios/parser/__init__.py` — Lazy-import stubs for parse_backup and inspect_backup (Plans 02/03)
- `src/cloud_usage/nios/parser/_families.py` — Empirical _XML_TYPE_TO_FAMILY, MEMBER_SCOPED_FAMILIES, GRID_LEVEL_FAMILIES, ALL_EXPECTED_FAMILIES, _MEMBER_XML_TYPES
- `requirements.txt` — Added `lxml>=5.3.0`

## Critical Discovery: XML Format

**The onedb.xml format does NOT use XML element type attributes.** Every `<OBJECT>` uses:
```xml
<OBJECT>
  <PROPERTY NAME="__type" VALUE=".com.infoblox.dns.lease"/>
  <PROPERTY NAME="ip_address" VALUE="10.225.35.85"/>
  ...
</OBJECT>
```
The `__type` PROPERTY's VALUE attribute (not text, not the OBJECT's XML attributes) holds the type string. This changes the parser in Plan 02 from `elem.get('type')` to iterating PROPERTY children.

## Complete XML Type-to-Family Mapping (from ZF reference backup, 2026-02-28)

| XML __type Value | NiosFamily Constant | Count Observed |
|------------------|---------------------|----------------|
| `.com.infoblox.dns.lease` | LEASE | 605,489 |
| `.com.infoblox.dns.bind_ptr` | DNS_RECORD_PTR | 172,715 |
| `.com.infoblox.dns.bind_a` | DNS_RECORD_A | 158,110 |
| `.com.infoblox.dns.bind_txt` | DNS_RECORD_TXT | 148,272 |
| `.com.infoblox.dns.host_address` | HOST_ADDRESS | 130,963 |
| `.com.infoblox.dns.host` | HOST_OBJECT | 129,930 |
| `.com.infoblox.dns.bind_srv` | DNS_RECORD_SRV | 22,464 |
| `.com.infoblox.dns.zone` | DNS_ZONE | 19,395 |
| `.com.infoblox.dns.bind_soa` | DNS_RECORD_SOA | 18,987 |
| `.com.infoblox.dns.host_alias` | HOST_ALIAS | 15,799 |
| `.com.infoblox.dns.network` | NETWORK | 49,437 |
| `.com.infoblox.dns.fixed_address` | FIXED_ADDRESS | 25,817 |
| `.com.infoblox.dns.dhcp_range` | DHCP_RANGE | 7,430 |
| `.com.infoblox.dns.network_container` | NETWORK_CONTAINER | 1,837 |
| `.com.infoblox.dns.exclusion_range` | EXCLUSION_RANGE | 1,815 |
| `.com.infoblox.dns.bind_cname` | DNS_RECORD_CNAME | 3,859 |
| `.com.infoblox.dns.bind_ns` | DNS_RECORD_NS | 889 |
| `.com.infoblox.dns.bind_aaaa` | DNS_RECORD_AAAA | 196 |
| `.com.infoblox.dns.bind_mx` | DNS_RECORD_MX | 17 |
| `.com.infoblox.dns.network_view` | NETWORK_VIEW | 1 |
| `.com.infoblox.one.virtual_node` | MEMBER | 239 |

## Key Information for Plans 02 and 03

**Member hostname extraction (Plan 02, Pass 1):**
- Object type: `.com.infoblox.one.virtual_node`
- Key field: `virtual_oid` (integer string, e.g., "101") — this is the map key
- Value field: `host_name` (FQDN, e.g., "frdn77x00.emea.zf-world.com")

**Member attribution on scoped objects (Plan 02, Pass 2):**
- Only LEASE is MEMBER_SCOPED: `lease.vnode_id` maps to `virtual_node.virtual_oid`
- All other families have no direct member OID field

**DATABASE element (Plan 03):**
- NIOS version: XML attribute `VERSION` on the `<DATABASE>` element (read via `elem.get('VERSION')`, not from PROPERTY children)
- Format: `"9.0.6-53318-82020f7ffaad"`
- This requires Plan 02/03 to hook into the iterparse event stream for non-OBJECT elements

**Snapshot date (Plan 03):**
- From tar member mtime: `datetime.fromtimestamp(member.mtime, tz=utc).strftime('%Y-%m-%d')`
- ZF backup: mtime=1755006724 → `2025-08-12`

**PROPERTY extraction pattern (Plan 02):**
```python
# For each OBJECT element:
obj_type = None
props = {}
for child in elem:
    name = child.get('NAME')
    value = child.get('VALUE') or child.text or ''
    if name == '__type':
        obj_type = value
    elif name:
        props[name] = value
```

## Decisions Made

- **PROPERTY NAME='__type' VALUE pattern confirmed empirically** — the hypothesized `elem.get('type')` approach in RESEARCH.md Pattern 1 would return None for all objects. Plans 02/03 must use the PROPERTY child iteration approach.
- **Only LEASE is MEMBER_SCOPED** — the ZF backup shows no vnode_id on network, fixed_address, dhcp_range, or host objects. RESEARCH.md Pattern 3 hypothesis (DHCP families as member-scoped) is incorrect for this NIOS version.
- **21 families tracked** — 13 required minimum from PARSE-05 to PARSE-12 all present; 8 additional confirmed in the backup.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed lxml 6.x API incompatibility in discovery script**
- **Found during:** Task 1 (running the plan's exact discovery command)
- **Issue:** Plan's discovery script passed `parser=parser` keyword argument to `etree.iterparse()`, which is not supported in lxml 6.x (only direct keyword args like `recover=`, `huge_tree=` are accepted)
- **Fix:** Removed separate XMLParser instantiation, passed options directly to `iterparse()` keyword args
- **Files modified:** Discovery script only (not committed — ephemeral)
- **Verification:** Discovery ran successfully and enumerated all 2,506,601 objects

**2. [Empirical correction] XML structure differs from RESEARCH.md hypothesis**
- **Found during:** Task 1 (first discovery run returned "(no type)" for all objects)
- **Issue:** RESEARCH.md assumed `<OBJECT type="...">` attribute pattern; actual format uses `<PROPERTY NAME="__type" VALUE="..."/>` child
- **Impact:** Schema and families files built using correct empirical format; Plan 02 parser will need PROPERTY iteration, not `elem.get('type')`
- **Note:** This is a planned discovery task per the plan — "the most uncertain step in this entire phase"

---

**Total deviations:** 2 (1 API bug auto-fixed, 1 structural discovery corrected by design)
**Impact on plan:** The XML format discovery is the primary purpose of this plan. The RESEARCH.md uncertainty is now resolved. All artifacts reflect empirical findings from the actual backup.

## Issues Encountered

- Discovery script had `parser=` kwarg incompatibility with lxml 6.x — fixed inline before proceeding
- Initial type counts showed all objects as "(no type)" — quickly diagnosed by reading the first 3000 bytes of onedb.xml to reveal the PROPERTY-based format

## Next Phase Readiness

- Plans 02 and 03 can now import `_XML_TYPE_TO_FAMILY`, `MEMBER_SCOPED_FAMILIES`, `_MEMBER_XML_TYPES` from `_families.py`
- Plan 02 must use PROPERTY child iteration (not `elem.get('type')`) for type extraction
- Plan 02 must use `elem.get('VERSION')` on DATABASE element for NIOS version (not from PROPERTY children)
- All 21 family type strings are confirmed and documented with observed counts

---
*Phase: 10-nios-parser-and-schema*
*Completed: 2026-02-28*
