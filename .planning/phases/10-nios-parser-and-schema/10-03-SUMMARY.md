---
phase: 10-nios-parser-and-schema
plan: 03
subsystem: parser
tags: [lxml, nios, tarfile, xml, dataclass, streaming-parser, integrity-report, tdd]

# Dependency graph
requires:
  - phase: 10-01-PLAN.md
    provides: "_families.py with ALL_EXPECTED_FAMILIES, _XML_TYPE_TO_FAMILY, _MEMBER_XML_TYPES; schema.py with IntegrityReport"
  - phase: 10-02-PLAN.md
    provides: "_extractor.py _open_onedb_xml(), _xml_stream.py _iter_raw_objects(), _member_map.py _build_member_map()"
provides:
  - "src/cloud_usage/nios/parser/_inspect.py — inspect_backup(path) -> IntegrityReport full implementation"
  - "tests/nios/test_nios_inspect.py — 9 TDD tests covering all IntegrityReport fields and warning conditions"
  - "Phase 10 complete: both parse_backup() and inspect_backup() functional and tested (19 total tests)"
affects:
  - "11-nios-filter-and-counter"
  - "12-nios-report-generator (uses nios_version + snapshot_date for report header)"
  - "13-nios-cli-integration"
  - "14-nios-dashboard-upload (member list pre-scan)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Three-pass inspect strategy: pre-scan (DATABASE tag) + Pass 1 (member map) + Pass 2 (family counts)"
    - "DATABASE VERSION extraction via separate lxml iterparse with events=('start',) tag='DATABASE' — stops after first element"
    - "Zero-baseline families_found dict: initialise all ALL_EXPECTED_FAMILIES at 0 before parsing"
    - "Warning generation pattern: sorted(ALL_EXPECTED_FAMILIES) iteration for deterministic warning order"

key-files:
  created:
    - "src/cloud_usage/nios/parser/_inspect.py"
    - "tests/nios/test_nios_inspect.py"
  modified: []

key-decisions:
  - "Three-pass design over two-pass: pre-scan reads DATABASE VERSION attribute separately because _iter_raw_objects only yields OBJECT elements (tag='OBJECT' iterparse); DATABASE is the root element, never an OBJECT child"
  - "lxml iterparse with events=('start',) tag='DATABASE' stops after first element — extremely fast, reads only first few bytes of XML stream"
  - "Unresolvable OID attribution field confirmed as vnode_id (not virtual_oid) — consistent with _parse.py Pass 2"
  - "Warning ordering: zero-row family warnings sorted alphabetically for deterministic output across Python versions"

patterns-established:
  - "DATABASE pre-scan pattern: _extract_database_version() isolates root-element attribute capture from OBJECT iteration"
  - "Zero-baseline initialisation: {f: 0 for f in ALL_EXPECTED_FAMILIES} ensures all expected families appear in output even with 0 count"

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
duration: 16min
completed: 2026-02-28
---

# Phase 10 Plan 03: inspect_backup() TDD Implementation Summary

**lxml three-pass inspect_backup() returning IntegrityReport with family counts, warnings, nios_version, and snapshot_date — validated against ZF reference backup (1,513,661 objects, 86s, consistent with parse_backup)**

## Performance

- **Duration:** ~16 min
- **Started:** 2026-02-28T20:12:46Z
- **Completed:** 2026-02-28T20:29:00Z
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 2 (1 created each phase)

## Accomplishments

- Implemented `inspect_backup()` with a three-pass strategy: pre-scan for DATABASE VERSION, Pass 1 for member map + snapshot_date, Pass 2 for family counts + unresolvable OID tracking
- Solved the DATABASE VERSION challenge: `_iter_raw_objects` only yields OBJECT elements (tag="OBJECT" iterparse), but VERSION is on the root DATABASE element — a separate iterparse with tag="DATABASE" + events=("start",) captures it after reading just the first bytes of the stream
- All 19 NIOS tests pass (9 new inspect tests + 10 parse_backup tests); no regressions in project
- ZF reference backup validated: 1,513,661 objects, nios_version="9.0.6-53318-82020f7ffaad", snapshot_date="2025-08-12", 1 warning (328 unresolvable vnode_id references), 86s elapsed
- parse_backup vs inspect_backup consistency check: both return exactly 1,513,661 objects (PASSED)
- Phase 10 complete: both public API functions (`parse_backup` and `inspect_backup`) functional, tested, and validated against the ZF reference backup

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing tests for inspect_backup() — RED phase** - `61641d3` (test)
2. **Task 2: Implement inspect_backup() and run full phase verification — GREEN phase** - `92209e9` (feat)

*Note: TDD plan — RED commit (test) then GREEN commit (feat)*

## Reference Backup Output (ZF backup, 2026-02-28)

```
inspect_backup: 86.1s
NIOS version: 9.0.6-53318-82020f7ffaad
Snapshot date: 2025-08-12
Families found (21 total):
       605,489  lease
       172,715  dns_record_ptr
       158,110  dns_record_a
       148,272  dns_record_txt
       130,963  host_address
       129,930  host_object
        49,437  network
        25,817  fixed_address
        22,464  dns_record_srv
        19,395  dns_zone
        18,987  dns_record_soa
        15,799  host_alias
         7,430  dhcp_range
         3,859  dns_record_cname
         1,837  network_container
         1,815  exclusion_range
           889  dns_record_ns
           239  member
           196  dns_record_aaaa
            17  dns_record_mx
             1  network_view
Warnings (1):
  WARNING: 328 objects reference a virtual_oid not found in Member objects

parse_backup: 83.9s, 1,513,661 objects yielded
CONSISTENCY CHECK: PASSED
```

**All 21 expected families present with non-zero counts — no zero-row family warnings on the ZF backup.**
**The 1 warning (328 unresolvable vnode_ids) is expected for a production NIOS backup.**

## Files Created/Modified

- `src/cloud_usage/nios/parser/_inspect.py` — Three-pass inspect_backup() implementation with _extract_database_version() helper
- `tests/nios/test_nios_inspect.py` — 9 TDD tests for inspect_backup() covering all IntegrityReport fields and warning conditions

## Decisions Made

- **Three-pass strategy over two-pass:** The DATABASE element VERSION attribute cannot be captured by _iter_raw_objects (which uses tag="OBJECT" iterparse). A separate pre-scan pass using events=("start",) tag="DATABASE" reads only the DATABASE opening tag (first ~200 bytes of XML), stopping immediately after — negligible overhead for accurate version capture.

- **_extract_database_version() as a separate helper:** Isolating DATABASE pre-scan into its own function keeps inspect_backup() readable and the strategy explicit in the module docstring. Future changes to version extraction (e.g., a different NIOS version using a different attribute name) require modifying only one function.

- **vnode_id as unresolvable OID attribution field:** Consistent with _parse.py — the attribution field on LEASE objects is vnode_id (not virtual_oid). The warning message uses "virtual_oid not found in Member objects" to describe what the vnode_id references (the member's virtual_oid key), which is the user-meaningful field name.

- **Sorted family iteration for warnings:** `sorted(ALL_EXPECTED_FAMILIES)` ensures deterministic warning order across Python versions (frozenset iteration order is undefined).

## Deviations from Plan

None — plan executed exactly as written. The DATABASE VERSION extraction approach (separate iterparse pre-scan) matched the plan's Implementation Note 2/3 guidance perfectly. No placeholder field names were used — all field names (virtual_oid, host_name, vnode_id) were confirmed from 10-01-SUMMARY.md and used directly.

## Issues Encountered

None — implementation worked on first attempt. The three-pass design, field names from 10-01-SUMMARY.md, and lxml iterparse patterns from _xml_stream.py were all directly applicable.

## PARSE Requirements Satisfied

All 13 PARSE requirements (PARSE-01 through PARSE-13) are satisfied by Phase 10 (Plans 01, 02, 03 combined):

| Requirement | Coverage |
|-------------|----------|
| PARSE-01 | NiosFamily constants (21 families) — schema.py |
| PARSE-02 | NiosObject dataclass — schema.py |
| PARSE-03 | IntegrityReport dataclass — schema.py |
| PARSE-04 | NiosParseError exception — errors.py |
| PARSE-05 | LEASE family — _families.py, _parse.py |
| PARSE-06 | NETWORK family — _families.py |
| PARSE-07 | FIXED_ADDRESS, HOST_ADDRESS families — _families.py |
| PARSE-08 | DNS zone families — _families.py |
| PARSE-09 | DNS record families (A, AAAA, CNAME, MX, NS, PTR, SOA, SRV, TXT) — _families.py |
| PARSE-10 | MEMBER family — _families.py, _member_map.py |
| PARSE-11 | parse_backup() generator — _parse.py |
| PARSE-12 | inspect_backup() -> IntegrityReport — _inspect.py |
| PARSE-13 | Member attribution resolution (vnode_id -> virtual_oid -> host_name) — _parse.py, _inspect.py |

## Next Phase Readiness

Phase 10 is **complete**. Phase 11 (nios-filter-and-counter) can now:
- Import `parse_backup(path)` from `cloud_usage.nios.parser` for streaming all 1.5M+ objects
- Import `inspect_backup(path)` from `cloud_usage.nios.parser` for structural validation and header data
- Use `NiosObject.family` (NiosFamily constants) and `NiosObject.raw_attrs` for counting logic
- Rely on `member_hostname` being resolved for LEASE objects (vnode_id attribution)

---
*Phase: 10-nios-parser-and-schema*
*Completed: 2026-02-28*
