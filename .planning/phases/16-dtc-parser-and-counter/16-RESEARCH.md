# Phase 16: DTC Parser and Counter - Research

**Researched:** 2026-03-02
**Domain:** Python additive extension — NIOS backup XML parser + DDI counter
**Confidence:** HIGH (for implementation patterns), LOW (for DTC XML __type strings — spec-derived only)

## Summary

Phase 16 is a purely additive Python change: add five new `NiosFamily` string constants, extend two frozensets (`GRID_LEVEL_FAMILIES`, `_DDI_FAMILIES`), and add a new section to `_XML_TYPE_TO_FAMILY`. No architectural decisions are required — the existing patterns in `schema.py`, `parser/_families.py`, and `counter.py` are the template.

The critical research gap is the exact Java class name strings for DTC objects in the onedb.xml backup format. The WAPI-facing type strings (`dtc:lbdn`, `dtc:pool`, `dtc:server`, `dtc:monitor:http`, `dtc:topology:label`, etc.) are well-documented in Ansible modules and the Infoblox WAPI. However, the internal onedb.xml `__type` PROPERTY VALUE strings (Java class names like `.com.infoblox.dns.*`) are NOT publicly documented. No empirical backup containing DTC objects is available. Per DTC-11, ALL entries must carry the comment `# spec-derived, unverified — no empirical backup observed`.

The spec-derived Java class name candidates are derived from the WAPI object_type naming convention and the existing `.com.infoblox.dns.*` namespace pattern observed in the ZF backup.

**Primary recommendation:** Implement all five families using spec-derived type strings in a dedicated `# ---- DTC ----` block. Tests use synthetic backups with those strings — the annotation makes the unverified nature explicit. No hand-rolling required; all patterns are already established.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### XML type string annotation
- All DTC entries in `_XML_TYPE_TO_FAMILY` MUST carry comment: `# spec-derived, unverified — no empirical backup observed`
- This is a hard requirement from DTC-11; no deviation allowed
- Contrast with existing entries which have `# N observed` with empirical counts

#### DTC monitor subtypes
- Six monitor subtypes (http, icmp, pdp, sip, snmp, tcp) all map to the SAME `dtc_monitor` family
- Each subtype gets its own `_XML_TYPE_TO_FAMILY` entry pointing to `NiosFamily.DTC_MONITOR`
- No per-subtype family constants — explicitly out of scope per requirements

#### Topology subtypes
- Two topology subtypes (label, rule) both map to the SAME `dtc_topology` family
- Each gets its own `_XML_TYPE_TO_FAMILY` entry pointing to `NiosFamily.DTC_TOPOLOGY`

#### Counter behavior
- DTC families count +1 toward DDI per object — no special expansion (unlike HOST_OBJECT's +2/+3)
- DTC families are added to `_DDI_FAMILIES` frozenset in counter.py
- DTC objects carry `member_hostname=None` (grid-level) — counter handles this via existing grid_ddi accumulator

#### ALL_EXPECTED_FAMILIES
- All five DTC families MUST be added to `ALL_EXPECTED_FAMILIES`
- This is required for DTC-10 (Phase 17) to pre-populate zero baseline in IntegrityReport.families_found
- Consequence: non-DTC backups will see "missing family" warnings — acceptable per spec

### Claude's Discretion
- Exact Java class name strings for each DTC type (researcher should derive from NIOS DTC API docs or spec)
- Whether to group LBDN as a single type or multiple type strings (spec says "all DTC LBDN objects" — likely one type)
- Order of entries within `_XML_TYPE_TO_FAMILY` (follow existing grouping style)
- Test fixture complexity: minimal is fine — one object per family is sufficient to verify non-zero count

### Deferred Ideas (OUT OF SCOPE)
- DTC counts in XLS Object Counters sheet — Phase 17 (DTC-09)
- DTC counts flowing through scenarios — Phase 17 (DTC-08)
- inspect_backup() DTC integration — Phase 17 (DTC-10)
- Empirical validation of XML type strings against real DTC backup — future (DTC-V01)

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DTC-01 | Parser recognizes all DTC LBDN objects as a distinct `dtc_lbdn` family | Add `NiosFamily.DTC_LBDN` constant + `_XML_TYPE_TO_FAMILY` entry for `.com.infoblox.dns.dtc_lbdn` (spec-derived) |
| DTC-02 | Parser recognizes DTC Pool objects as a distinct `dtc_pool` family | Add `NiosFamily.DTC_POOL` constant + `_XML_TYPE_TO_FAMILY` entry for `.com.infoblox.dns.dtc_pool` |
| DTC-03 | Parser recognizes DTC Server objects as a distinct `dtc_server` family | Add `NiosFamily.DTC_SERVER` constant + `_XML_TYPE_TO_FAMILY` entry for `.com.infoblox.dns.dtc_server` |
| DTC-04 | Parser recognizes all DTC Monitor subtypes (http, icmp, pdp, sip, snmp, tcp) as a single `dtc_monitor` family | Add `NiosFamily.DTC_MONITOR` constant + 6 `_XML_TYPE_TO_FAMILY` entries (one per subtype), all mapping to `dtc_monitor` |
| DTC-05 | Parser recognizes DTC Topology objects (label, rule) as a single `dtc_topology` family | Add `NiosFamily.DTC_TOPOLOGY` constant + 2 entries (`dtc_topology_label`, `dtc_topology_rule`) |
| DTC-06 | All DTC families count +1 toward DDI per object | Add 5 DTC constants to `_DDI_FAMILIES` frozenset in `counter.py`; the existing `delta = 1` branch handles this |
| DTC-07 | DTC objects are grid-level (`member_hostname=None`) — no member attribution expected | Add 5 DTC constants to `GRID_LEVEL_FAMILIES` in `_families.py`; `ALL_EXPECTED_FAMILIES` auto-includes them |
| DTC-11 | All DTC XML type strings annotated with `# spec-derived, unverified — no empirical backup observed` | Annotation is a code comment discipline — enforced by plan + verified by plan-checker |

</phase_requirements>

## Standard Stack

### Core (existing — no new dependencies)
| Module | Purpose | Pattern |
|--------|---------|---------|
| `src/cloud_usage/nios/schema.py` | `NiosFamily` string constants | Plain class with `SNAKE_CASE = "snake_case"` constants |
| `src/cloud_usage/nios/parser/_families.py` | `_XML_TYPE_TO_FAMILY`, `GRID_LEVEL_FAMILIES`, `ALL_EXPECTED_FAMILIES` | Frozenset + dict with comment annotations |
| `src/cloud_usage/nios/counter.py` | `_DDI_FAMILIES` frozenset | Frozenset membership check in `count_objects()` |
| `tests/nios/test_nios_parser.py` | Parser unit tests | `_build_onedb_xml()` + `_make_backup()` helpers |
| `tests/nios/test_nios_counter.py` | Counter unit tests | `_obj()` helper builds `NiosObject` directly |

No new libraries, no new dependencies, no configuration changes needed.

## Architecture Patterns

### Pattern 1: NiosFamily Constant Addition
```python
# In src/cloud_usage/nios/schema.py — add after existing constants:
class NiosFamily:
    # ... existing constants ...
    DTC_LBDN = "dtc_lbdn"
    DTC_POOL = "dtc_pool"
    DTC_SERVER = "dtc_server"
    DTC_MONITOR = "dtc_monitor"
    DTC_TOPOLOGY = "dtc_topology"
```

### Pattern 2: _XML_TYPE_TO_FAMILY Block (spec-derived, unverified)
```python
# In src/cloud_usage/nios/parser/_families.py
# ---- DTC ---- (spec-derived, unverified — no empirical backup observed) -----------
".com.infoblox.dns.dtc_lbdn": NiosFamily.DTC_LBDN,  # spec-derived, unverified — no empirical backup observed
".com.infoblox.dns.dtc_pool": NiosFamily.DTC_POOL,  # spec-derived, unverified — no empirical backup observed
".com.infoblox.dns.dtc_server": NiosFamily.DTC_SERVER,  # spec-derived, unverified — no empirical backup observed
".com.infoblox.dns.dtc_monitor_http": NiosFamily.DTC_MONITOR,  # spec-derived, unverified — no empirical backup observed
".com.infoblox.dns.dtc_monitor_icmp": NiosFamily.DTC_MONITOR,  # spec-derived, unverified — no empirical backup observed
".com.infoblox.dns.dtc_monitor_pdp": NiosFamily.DTC_MONITOR,  # spec-derived, unverified — no empirical backup observed
".com.infoblox.dns.dtc_monitor_sip": NiosFamily.DTC_MONITOR,  # spec-derived, unverified — no empirical backup observed
".com.infoblox.dns.dtc_monitor_snmp": NiosFamily.DTC_MONITOR,  # spec-derived, unverified — no empirical backup observed
".com.infoblox.dns.dtc_monitor_tcp": NiosFamily.DTC_MONITOR,  # spec-derived, unverified — no empirical backup observed
".com.infoblox.dns.dtc_topology_label": NiosFamily.DTC_TOPOLOGY,  # spec-derived, unverified — no empirical backup observed
".com.infoblox.dns.dtc_topology_rule": NiosFamily.DTC_TOPOLOGY,  # spec-derived, unverified — no empirical backup observed
```

**Confidence: LOW** — These type strings are spec-derived guesses based on the `.com.infoblox.dns.*` namespace pattern observed in the ZF backup. The WAPI object type identifiers (`dtc:lbdn`, `dtc:pool`, etc.) confirm the DTC objects exist but do not expose the internal Java class names used in the onedb.xml. These MUST carry the DTC-11 annotation comment regardless.

### Pattern 3: GRID_LEVEL_FAMILIES Extension
```python
# Add to GRID_LEVEL_FAMILIES frozenset:
NiosFamily.DTC_LBDN,    # grid-level DTC object
NiosFamily.DTC_POOL,    # grid-level DTC object
NiosFamily.DTC_SERVER,  # grid-level DTC object
NiosFamily.DTC_MONITOR, # grid-level DTC object
NiosFamily.DTC_TOPOLOGY,# grid-level DTC object
```
`ALL_EXPECTED_FAMILIES = MEMBER_SCOPED_FAMILIES | GRID_LEVEL_FAMILIES` — no change needed to that line.

### Pattern 4: _DDI_FAMILIES Extension (counter.py)
```python
# Add to _DDI_FAMILIES frozenset in counter.py:
NiosFamily.DTC_LBDN,
NiosFamily.DTC_POOL,
NiosFamily.DTC_SERVER,
NiosFamily.DTC_MONITOR,
NiosFamily.DTC_TOPOLOGY,
```
The existing `delta = 1` path in `count_objects()` handles these (no HOST_OBJECT special case needed).
Since `member_hostname=None` for all DTC objects, the `grid_ddi += delta` path handles them automatically.

### Pattern 5: Test Fixture for Parser Tests
```python
# In tests/nios/test_nios_parser.py — helper functions following existing pattern:
def _dtc_lbdn_object(**extra_props: str) -> str:
    """Build an XML OBJECT snippet for a DTC LBDN object (grid-level family)."""
    extra = "".join(
        f'  <PROPERTY NAME="{n}" VALUE="{v}"/>\n' for n, v in extra_props.items()
    )
    return f"""<OBJECT>
  <PROPERTY NAME="__type" VALUE=".com.infoblox.dns.dtc_lbdn"/>
{extra}</OBJECT>"""
```
Similar helpers for each DTC type.

### Pattern 6: Test for Counter Tests
```python
# In tests/nios/test_nios_counter.py — using existing _obj() helper:
dtc_obj = _obj(NiosFamily.DTC_LBDN, member=None)  # grid-level, member_hostname=None
result = count_objects(iter([dtc_obj]), _default_config())
assert result.grid_counts.ddi_count == 1
assert result.member_counts == []  # no member attribution
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Member attribution for DTC | Any member resolution logic | DTC is grid-level — member_hostname=None by design; GRID_LEVEL_FAMILIES membership handles this automatically |
| Per-DTC-subtype family | Separate family for each monitor type | Single `dtc_monitor` family — multiple XML type strings → one NiosFamily constant (existing pattern allows N:1 mapping) |
| Special expansion for DTC | HOST_OBJECT-style expansion logic | Simple delta=1 in counter.py; DTC objects count exactly +1 per object |

## Common Pitfalls

### Pitfall 1: Forgetting the DTC-11 annotation comment
**What goes wrong:** DTC entries added to `_XML_TYPE_TO_FAMILY` without the required comment
**Why it happens:** Developer follows the `# N observed` pattern for existing entries
**How to avoid:** Plan explicitly requires the exact string `# spec-derived, unverified — no empirical backup observed` on every DTC entry
**Warning signs:** Checker reviews the comment strings; test doesn't verify comments (manual inspection)

### Pitfall 2: ALL_EXPECTED_FAMILIES not automatically updated
**What goes wrong:** Developer adds DTC to GRID_LEVEL_FAMILIES but forgets the union
**Why it happens:** Misreading the code
**How to avoid:** The union is computed as `MEMBER_SCOPED_FAMILIES | GRID_LEVEL_FAMILIES` — no explicit change needed. CONTEXT.md confirms this.

### Pitfall 3: DTC_MONITOR entries only partially added
**What goes wrong:** Adding only some of the 6 monitor subtypes (http, icmp, pdp, sip, snmp, tcp)
**Why it happens:** Forgetting one of the six
**How to avoid:** Plan enumerates all 6 explicitly; test creates an object for at least one (any one is sufficient per CONTEXT.md)

### Pitfall 4: DTC topology entries missing
**What goes wrong:** Only adding `dtc_topology` without adding both `dtc_topology_label` and `dtc_topology_rule`
**Why it happens:** CONTEXT.md says "two subtypes" but a developer might add only the parent
**How to avoid:** Plan enumerates both explicitly

### Pitfall 5: Wrong XML type string format (double-underscore vs hyphen vs dot)
**What goes wrong:** Using `dtc-lbdn` or `dtcLbdn` instead of `dtc_lbdn` (or using an underscore when the real type uses a dot)
**Why it happens:** Guessing the naming convention without a reference backup
**How to avoid:** All entries are annotated as spec-derived; the exact strings are a known unknown — use underscore-delimited lowercase matching WAPI convention

## Code Examples

### Verified patterns from existing codebase

```python
# Existing N:1 mapping — multiple XML types to one family (DNS records):
".com.infoblox.dns.bind_ptr": NiosFamily.DNS_RECORD_PTR,  # 172,715 observed
# DTC will follow the same pattern but with spec-derived annotation

# Existing grid-level frozenset membership:
GRID_LEVEL_FAMILIES: frozenset[str] = frozenset({
    NiosFamily.DNS_ZONE,  # zone is grid-level
    # ... add 5 DTC families here
})

# Existing DDI counting logic — delta=1 path that DTC will use:
if family in _DDI_FAMILIES:
    if family == NiosFamily.HOST_OBJECT:
        delta = 3 if aliases else 2
    else:
        delta = 1  # <-- DTC uses this path
    if hostname is None:
        grid_ddi += delta  # <-- DTC accumulates here (member_hostname=None)
```

## Open Questions

1. **Exact Java class name strings for DTC objects**
   - What we know: WAPI types are `dtc:lbdn`, `dtc:pool`, `dtc:server`, `dtc:monitor:http` etc.
   - What's unclear: Whether onedb.xml uses `.com.infoblox.dns.dtc_lbdn` or `.com.infoblox.dns.dtc.lbdn` or another format entirely
   - Recommendation: Use `dtc_lbdn` (underscore, matching WAPI snake_case), annotate as spec-derived per DTC-11. Empirical validation is DTC-V01 (future requirement). Tests will self-consistently use whichever strings the code defines.

2. **Whether LBDN maps to one or multiple XML type strings**
   - What we know: WAPI has only one `dtc:lbdn` object type
   - What's unclear: Whether the backup XML might differentiate LBDN variants
   - Recommendation: One entry per CONTEXT.md guidance ("all DTC LBDN objects" → one type)

## Sources

### Primary (HIGH confidence)
- Codebase: `src/cloud_usage/nios/parser/_families.py` — established patterns for XML type mapping
- Codebase: `src/cloud_usage/nios/schema.py` — NiosFamily constant pattern
- Codebase: `src/cloud_usage/nios/counter.py` — _DDI_FAMILIES and counting logic
- Codebase: `tests/nios/test_nios_parser.py` — test fixture pattern

### Secondary (MEDIUM confidence)
- Infoblox Ansible modules (github.com/infobloxopen/infoblox-ansible): confirms 6 monitor subtypes (http, icmp, pdp, sip, snmp, tcp) and 2 topology types (label, rule)
- Infoblox WAPI search results: confirm `dtc:lbdn`, `dtc:pool`, `dtc:server`, `dtc:monitor`, `dtc:topology`, `dtc:topology:rule`, `dtc:topology:label` as the WAPI-facing type names

### Tertiary (LOW confidence)
- Derived XML __type strings: `.com.infoblox.dns.dtc_lbdn` etc. — no empirical backup confirmation available (DTC-V01 deferred)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — existing codebase is the template; no new dependencies
- Architecture: HIGH — purely additive; existing patterns cover all cases
- DTC XML type strings: LOW — spec-derived from WAPI naming; no empirical backup available
- Pitfalls: HIGH — derived from reading the existing code directly

**Research date:** 2026-03-02
**Valid until:** No expiry — internal codebase patterns don't change unless Phase 15 is modified

## RESEARCH COMPLETE

**Phase:** 16 - DTC Parser and Counter
**Confidence:** HIGH (implementation patterns), LOW (DTC XML type strings — known unknown per spec)

### Key Findings
- Phase is purely additive: 5 new NiosFamily constants, 11 new _XML_TYPE_TO_FAMILY entries, 2 frozenset additions, 5 counter frozenset additions
- All DTC objects are grid-level (member_hostname=None) — existing grid_ddi path handles them automatically
- DTC XML __type strings are spec-derived (not empirically confirmed) — DTC-11 mandates annotation comment on all entries
- Test pattern is established: _build_onedb_xml() + _make_backup() for parser, _obj() for counter
- No external library research needed — this is a data extension, not a framework integration

### File Created
`.planning/phases/16-dtc-parser-and-counter/16-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | Existing codebase is the template; zero new dependencies |
| Architecture | HIGH | Pure additive extension; existing frozensets + dict + constants |
| DTC XML type strings | LOW | No empirical backup; spec-derived from WAPI naming convention |
| Test patterns | HIGH | Existing test helpers directly applicable |

### Open Questions
- DTC XML __type exact format (`.com.infoblox.dns.dtc_lbdn` vs other) — known unknown, annotated as spec-derived per DTC-11

### Ready for Planning
Research complete. Planner can now create PLAN.md files.
