# Phase 16: DTC Parser and Counter - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning
**Source:** Requirements + codebase analysis (no user discussion — proceed by spec)

<domain>
## Phase Boundary

Add five DTC object families to the NIOS schema, parser, and counter. This phase delivers:
1. Five new `NiosFamily` string constants: `dtc_lbdn`, `dtc_pool`, `dtc_server`, `dtc_monitor`, `dtc_topology`
2. `_XML_TYPE_TO_FAMILY` entries for all DTC Java class name type strings (spec-derived, annotated as unverified)
3. All five DTC families classified as grid-level (`GRID_LEVEL_FAMILIES`, `member_hostname=None`)
4. All five DTC families added to `ALL_EXPECTED_FAMILIES` (pre-populates zero baseline for IntegrityReport)
5. All five DTC families added to `_DDI_FAMILIES` in counter (+1 per object, no special expansion)
6. Tests: synthetic backup with DTC objects confirms non-zero counts for all five families

Out of scope for this phase: scenarios, XLS report, inspect_backup() integration (those are Phase 17).

</domain>

<decisions>
## Implementation Decisions

### XML type string annotation
- All DTC entries in `_XML_TYPE_TO_FAMILY` MUST carry comment: `# spec-derived, unverified — no empirical backup observed`
- This is a hard requirement from DTC-11; no deviation allowed
- Contrast with existing entries which have `# N observed` with empirical counts

### DTC monitor subtypes
- Six monitor subtypes (http, icmp, pdp, sip, snmp, tcp) all map to the SAME `dtc_monitor` family
- Each subtype gets its own `_XML_TYPE_TO_FAMILY` entry pointing to `NiosFamily.DTC_MONITOR`
- No per-subtype family constants — explicitly out of scope per requirements

### Topology subtypes
- Two topology subtypes (label, rule) both map to the SAME `dtc_topology` family
- Each gets its own `_XML_TYPE_TO_FAMILY` entry pointing to `NiosFamily.DTC_TOPOLOGY`

### Counter behavior
- DTC families count +1 toward DDI per object — no special expansion (unlike HOST_OBJECT's +2/+3)
- DTC families are added to `_DDI_FAMILIES` frozenset in counter.py
- DTC objects carry `member_hostname=None` (grid-level) — counter handles this via existing grid_ddi accumulator

### ALL_EXPECTED_FAMILIES
- All five DTC families MUST be added to `ALL_EXPECTED_FAMILIES`
- This is required for DTC-10 (Phase 17) to pre-populate zero baseline in IntegrityReport.families_found
- Consequence: non-DTC backups will see "missing family" warnings — acceptable per spec

### Claude's Discretion
- Exact Java class name strings for each DTC type (researcher should derive from NIOS DTC API docs or spec)
- Whether to group LBDN as a single type or multiple type strings (spec says "all DTC LBDN objects" — likely one type)
- Order of entries within `_XML_TYPE_TO_FAMILY` (follow existing grouping style)
- Test fixture complexity: minimal is fine — one object per family is sufficient to verify non-zero count

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `NiosFamily` class in `src/cloud_usage/nios/schema.py`: plain class with string constants — add 5 new constants following `SNAKE_CASE = "snake_case"` pattern
- `_XML_TYPE_TO_FAMILY` dict in `src/cloud_usage/nios/parser/_families.py`: add new section block `# ---- DTC ----` with all DTC type strings
- `GRID_LEVEL_FAMILIES` frozenset: add all 5 DTC constants
- `ALL_EXPECTED_FAMILIES`: derived as `MEMBER_SCOPED_FAMILIES | GRID_LEVEL_FAMILIES` — adding to GRID_LEVEL_FAMILIES automatically includes them
- `_DDI_FAMILIES` frozenset in `src/cloud_usage/nios/counter.py`: add all 5 DTC constants

### Established Patterns
- Type string format: `.com.infoblox.dns.<type>` for DNS/DHCP objects, `.com.infoblox.one.virtual_node` for Member — DTC likely uses `.com.infoblox.one.dtc.<type>` or `.com.infoblox.dns.dtc.<type>`
- Test pattern: `_build_onedb_xml()` + `_make_backup()` helpers in `tests/nios/test_nios_parser.py` — DTC tests follow the same synthetic fixture pattern
- Comment style: `# N observed` for empirical, `# spec-derived, unverified — no empirical backup observed` for DTC (DTC-11 mandates this exact phrase)

### Integration Points
- `src/cloud_usage/nios/schema.py` — NiosFamily constants (new constants needed here first)
- `src/cloud_usage/nios/parser/_families.py` — XML type mapping + family classification sets
- `src/cloud_usage/nios/counter.py` — `_DDI_FAMILIES` set
- `tests/nios/test_nios_parser.py` — parser unit tests for DTC recognition
- `tests/nios/test_nios_counter.py` — counter unit tests for DTC +1 DDI behavior

</code_context>

<specifics>
## Specific Ideas

- The `ALL_EXPECTED_FAMILIES` set is computed as `MEMBER_SCOPED_FAMILIES | GRID_LEVEL_FAMILIES` — no explicit union to update; just add DTC to GRID_LEVEL_FAMILIES
- DTC-10 (inspect_backup pre-populating DTC zero baseline) is Phase 17 scope, NOT Phase 16; Phase 16 only needs the families defined, not the inspect integration
- Phase success criteria specifies "synthetic backup" — tests do NOT need a real DTC backup file

</specifics>

<deferred>
## Deferred Ideas

- DTC counts in XLS Object Counters sheet — Phase 17 (DTC-09)
- DTC counts flowing through scenarios — Phase 17 (DTC-08)
- inspect_backup() DTC integration — Phase 17 (DTC-10)
- Empirical validation of XML type strings against real DTC backup — future (DTC-V01)

</deferred>

---

*Phase: 16-dtc-parser-and-counter*
*Context gathered: 2026-03-02 via requirements + codebase analysis*
