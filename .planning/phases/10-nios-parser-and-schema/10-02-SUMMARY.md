---
phase: 10-nios-parser-and-schema
plan: 02
subsystem: parser
tags: [lxml, nios, tarfile, xml, streaming-parser, tdd, two-pass, generator]

# Dependency graph
requires:
  - phase: 10-nios-parser-and-schema plan 01
    provides: "NiosFamily, NiosObject, NiosParseError, _families.py with empirical XML type mapping"
provides:
  - "parse_backup(path) -> Iterator[NiosObject]: two-pass streaming generator (public API)"
  - "_extractor.py: _open_onedb_xml() context manager — r:gz tarfile, exact basename match, snapshot_date from mtime"
  - "_xml_stream.py: _iter_raw_objects() — PROPERTY-based type extraction, lxml 6.x-compatible, two-step element cleanup"
  - "_member_map.py: _build_member_map() — Pass 1 virtual_oid -> hostname dict from virtual_node objects"
  - "_parse.py: parse_backup() — two-pass generator resolving member attribution via vnode_id on LEASE objects"
  - "tests/nios/test_nios_parser.py: 10 unit tests covering all parse_backup() behaviors"
affects:
  - "10-nios-parser-and-schema (Plan 03 — inspect_backup, reads same _extractor, _xml_stream)"
  - "11-nios-filter-and-counter (consumes NiosObject stream from parse_backup)"
  - "12-nios-report-generator"
  - "13-nios-cli-integration"
  - "14-nios-dashboard-upload"

# Tech tracking
tech-stack:
  added: []  # lxml already added in Plan 01
  patterns:
    - "Two-pass parse design: Pass 1 builds virtual_oid->hostname member map; Pass 2 yields resolved NiosObjects"
    - "PROPERTY-based XML type extraction: iterate PROPERTY children, match NAME='__type', read VALUE attribute"
    - "lxml iterparse with two-step element cleanup (elem.clear(keep_tail=True) + sibling deletion) for memory-flat streaming"
    - "r:gz tarfile mode (seeking) — 14x faster than r|gz pipe mode for random access on large archives"
    - "Exact basename match (Path(member.name).name == 'onedb.xml') — endswith would falsely match 'notonedb.xml'"
    - "lxml 6.x-compatible iterparse: options passed as direct kwargs, not via XMLParser object"

key-files:
  created:
    - "src/cloud_usage/nios/parser/_extractor.py"
    - "src/cloud_usage/nios/parser/_xml_stream.py"
    - "src/cloud_usage/nios/parser/_member_map.py"
    - "src/cloud_usage/nios/parser/_parse.py"
    - "tests/nios/__init__.py"
    - "tests/nios/test_nios_parser.py"
  modified: []

key-decisions:
  - "vnode_id is the confirmed attribution field on LEASE objects (not virtual_oid) — lease.vnode_id -> virtual_node.virtual_oid -> host_name"
  - "Exact basename match for onedb.xml (Path(member.name).name == 'onedb.xml') — endswith check falsely matched 'notonedb.xml'"
  - "lxml 6.x iterparse kwargs passed directly (not via XMLParser object) — Plan 01 discovery script revealed this incompatibility"
  - "PROPERTY VALUE attribute holds type string (not text content) — confirmed from 10-01 discovery; VALUE fallback to child.text only for non-type properties"
  - "parse_backup() is a true generator (uses yield) — test 10 verifies isinstance(result, types.GeneratorType)"
  - "Unresolvable vnode_id yields NiosObject with member_hostname=None (not skipped) — Phase 11 must not silently lose objects"

patterns-established:
  - "TDD RED/GREEN for streaming parsers: synthetic in-memory tar.gz fixtures via io.BytesIO + tarfile.open(mode='w:gz')"
  - "PROPERTY-based type extraction: for child in elem: if child.get('NAME') == '__type': obj_type = child.get('VALUE')"
  - "Two-step lxml cleanup: elem.clear(keep_tail=True) then sibling deletion loop — both steps required"

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

# Metrics
duration: 8min
completed: 2026-02-28
---

# Phase 10 Plan 02: NIOS Parser Core Implementation Summary

**Two-pass streaming NIOS backup parser: lxml iterparse with PROPERTY-based type extraction, member map Pass 1, and fully resolved NiosObject generator — all 10 TDD tests passing**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-02-28T20:01:28Z
- **Completed:** 2026-02-28T20:09:43Z
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 6 (6 created)

## Accomplishments

- Implemented `parse_backup()` as a true two-pass generator: Pass 1 builds virtual_oid -> hostname member map from virtual_node objects, Pass 2 streams resolved NiosObject instances for all 21 families
- Correctly applied PROPERTY-based XML type extraction discovered in Plan 01 — the `__type` PROPERTY child's `VALUE` attribute (not elem.get('type')) is the type discriminator
- Applied lxml 6.x iterparse compatibility fix: options passed as direct kwargs (not via XMLParser object), preventing CPython #102055 API incompatibility
- All 10 unit tests pass using synthetic in-memory tar.gz fixtures; smoke test parsed 200,000 real objects from ZF reference backup across 6 families correctly

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing tests for parse_backup() — RED phase** - `b434b96` (test)
2. **Task 2: Implement parse_backup() internals — GREEN phase** - `943b38a` (feat)

**Plan metadata:** (docs commit — follows below)

_Note: TDD tasks committed separately as test then feat per TDD protocol_

## Files Created/Modified

- `src/cloud_usage/nios/parser/_extractor.py` — `_open_onedb_xml()` context manager: r:gz tarfile, exact basename match for onedb.xml, mtime-based snapshot_date, NiosParseError on corruption
- `src/cloud_usage/nios/parser/_xml_stream.py` — `_iter_raw_objects()`: PROPERTY child iteration for type extraction, lxml 6.x-compatible iterparse kwargs, mandatory two-step element cleanup
- `src/cloud_usage/nios/parser/_member_map.py` — `_build_member_map()`: Pass 1 builder iterating virtual_node objects, collecting virtual_oid -> host_name pairs
- `src/cloud_usage/nios/parser/_parse.py` — `parse_backup()`: two-pass generator, LEASE vnode_id attribution, unresolvable OIDs yield None (not skipped), warning logged for unresolved count
- `tests/nios/__init__.py` — Empty package marker for nios test directory
- `tests/nios/test_nios_parser.py` — 10 TDD tests: family recognition, member resolution, unresolvable OID, grid-level families, empty member map, missing onedb.xml, corrupted archive, raw_attrs, unknown types skipped, generator contract

## Key Information for Plans 03 and 11

**Member attribution field (Plan 11 counter):**
- Only LEASE is MEMBER_SCOPED: `lease.vnode_id` -> `virtual_node.virtual_oid` -> `virtual_node.host_name`
- `vnode_id` is the field name (not `virtual_oid`) on LEASE objects

**PROPERTY extraction pattern (Plans 03, 11):**
```python
obj_type = ""
props = {}
for child in elem:
    name = child.get("NAME") or ""
    value = child.get("VALUE") or child.text or ""
    if name == "__type":
        obj_type = value
    elif name:
        props[name] = value
```

**Smoke test results (ZF reference backup, first 200,000 objects):**
- `dns_record_a`: 158,110
- `dns_record_ptr`: 36,929
- `dns_record_cname`: 3,859
- `dns_record_ns`: 889
- `dns_record_aaaa`: 196
- `dns_record_mx`: 17
- Total: 200,000 objects parsed, 6 families recognized

## Decisions Made

- **vnode_id on LEASE (not virtual_oid):** The member attribution field on LEASE objects is `vnode_id`, not `virtual_oid`. The `virtual_oid` is the key on the Member object itself. This distinction was confirmed in Plan 01 discovery and drives the `_parse.py` attribution lookup.
- **Exact basename match for onedb.xml:** `Path(member.name).name == "onedb.xml"` rather than `endswith("onedb.xml")` — the latter falsely matches filenames like `notonedb.xml`, which test 6 caught correctly.
- **lxml 6.x kwargs compatibility:** `iterparse()` options passed as direct keyword arguments (`resolve_entities=False, no_network=True, huge_tree=True, recover=True`) rather than via an `XMLParser` object. The `parser=` kwarg is not supported in lxml 6.x.
- **Unresolvable OIDs yield None:** Objects whose `vnode_id` cannot be resolved in the member map are still yielded with `member_hostname=None`. They are NOT skipped. Phase 11 must account for them.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed endswith() basename match causing false positives**
- **Found during:** Task 2 (GREEN phase — test 6 failed)
- **Issue:** `_extractor.py` used `member.name.endswith("onedb.xml")` which would match any file ending in "onedb.xml" (e.g., "notonedb.xml"), causing the missing-onedb.xml test to not raise NiosParseError
- **Fix:** Changed to `Path(member.name).name == "onedb.xml"` for exact basename match
- **Files modified:** `src/cloud_usage/nios/parser/_extractor.py`
- **Verification:** Test 6 (`test_parse_backup_missing_onedb_xml_raises`) now passes
- **Committed in:** `943b38a` (Task 2 GREEN phase commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - correctness bug in basename matching)
**Impact on plan:** The fix is essential for correctness — endswith would silently pass archives missing a proper "onedb.xml" entry. No scope creep.

## Issues Encountered

- IndentationError during Edit tool comment insertion in `_extractor.py` — resolved by rewriting the file cleanly via Write tool rather than Edit.
- lxml 6.x `parser=` kwarg incompatibility was anticipated from Plan 01 discovery; `_xml_stream.py` written with direct kwargs from the start (no fix needed).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `parse_backup()` is fully functional and tested — Plan 03 (`inspect_backup`) can reuse `_extractor.py` and `_xml_stream.py` directly
- Plan 03 needs to hook into the iterparse stream for DATABASE element to extract NIOS version string (`elem.get('VERSION')`) — documented in `_families.py` and `10-01-SUMMARY.md`
- Phase 11 counter can consume the NiosObject stream from `parse_backup()` with known field names for LEASE counting

## Self-Check: PASSED

All 7 files confirmed present. Both task commits (b434b96, 943b38a) confirmed in git log.

---

*Phase: 10-nios-parser-and-schema*
*Completed: 2026-02-28*
