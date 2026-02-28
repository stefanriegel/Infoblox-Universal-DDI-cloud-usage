# Architecture Research

**Domain:** Multi-cloud resource discovery & UDDI licensing estimation tool — v1.1 NIOS Grid Analysis integration
**Researched:** 2026-02-28
**Confidence:** HIGH (direct codebase analysis, requirements verified against REQUIREMENTS.md)

---

## Context: What Changed in v1.1

The v1.0 architecture (researched 2026-02-23) covers cloud discovery. This document extends it for v1.1: adding NIOS Grid backup analysis as a parallel, independent capability alongside the existing cloud providers. The key design constraint is **do not couple the new NIOS pipeline to cloud provider internals**. The NIOS path must be addable without touching any existing `providers/`, `counting/`, `discovery/`, or `output/` cloud code.

---

## Existing Architecture Summary (v1.0 — Do Not Break)

The existing system has four layers:

| Layer | Modules | Role |
|-------|---------|------|
| Entry | `cli.py`, `dashboard/` | User-facing. CLI via argparse. Dashboard via FastAPI + HTMX. |
| Discovery | `discovery/orchestrator.py`, `discovery/provider.py`, `providers/aws|azure|gcp/` | Cloud scanning. Concurrent via ThreadPoolExecutor. Emits `CloudResource` objects. |
| Counting | `counting/categorizer.py`, `counting/ip_counter.py`, `counting/token_calculator.py`, `counting/asset_dedup.py` | Categorize resources as DDI/IP/Asset. Compute tokens. |
| Output | `output/xlsx_report.py`, `output/estimator_csv.py`, `output/proof_manifest.py` | Serialize results to XLS/CSV/JSON files. |

The `schema/resource.py` `CloudResource` dataclass is the lingua franca between discovery and counting. The cloud providers speak `CloudResource`; the counters read `CloudResource`. **The NIOS pipeline must not use `CloudResource`** — it has a fundamentally different data model (XML objects, not cloud API resources).

---

## v1.1 System Overview

```
+----------------------------------------------------------+
|                     Entry Layer                           |
|                                                          |
|  cli.py (argparse)          dashboard/ (FastAPI + HTMX)  |
|  --nios <file>              /tab/nios  (new tab)         |
|  --nios-config <yaml>       /wizard/nios (new wizard)    |
+--------+----------------------------------+--------------+
         |                                  |
         |           Cloud path (unchanged) |
         |         +------------------------+
         |         |                        |
+--------v---------v-------+    +-----------v-----------+
|    Cloud Discovery        |    |   NIOS Analysis        |
|    (existing, unchanged)  |    |   (new, independent)   |
|                           |    |                        |
|   discovery/orchestrator  |    |  nios/runner.py        |
|   providers/aws|azure|gcp |    |  (orchestrates the     |
|   counting/ pipeline      |    |   NIOS pipeline)       |
+---------------------------+    +-----------+------------+
                                             |
         +-----------------------------------+
         |           |             |         |
+--------v--+  +-----v-----+  +---v----+  +-v----------+
| nios/     |  | nios/     |  | nios/  |  | nios/      |
| parser/   |  | filter.py |  |counter.|  | scenarios. |
| (SAX XML, |  | (whitelist|  | py     |  | py         |
|  .tar.gz) |  |  /blackl.)|  |(NIOS & |  |(current/   |
|           |  |           |  | UDDI   |  | hybrid/    |
|           |  |           |  | rates) |  | full migr.)|
+-----------+  +-----------+  +--------+  +-----+------+
                                                |
                                         +------v------+
                                         | output/     |
                                         | nios_xlsx.py|
                                         | (new file,  |
                                         |  xlsxwriter)|
                                         +-------------+
```

---

## New Module Layout: `src/cloud_usage/nios/`

All NIOS code lives under a single new top-level package. This isolates it completely from the cloud provider modules. No existing file in `providers/`, `counting/`, `discovery/`, or `schema/` is modified.

```
src/cloud_usage/nios/
├── __init__.py                  # Exports: run_nios_analysis(), NiosConfig
├── runner.py                    # Top-level orchestrator: .tar.gz -> XLS
├── config.py                    # NiosConfig dataclass (parsed from YAML/dict)
├── parser/
│   ├── __init__.py              # Exports: parse_backup()
│   ├── extractor.py             # Extracts onedb.xml from .tar.gz (streaming)
│   ├── streaming_xml.py         # SAX/iterparse event handler -> NiosObject stream
│   └── object_types.py          # Constants: XML type names -> internal type keys
├── schema.py                    # Dataclasses: NiosMember, NiosNetwork, NiosLease,
│                                #   NiosFixedAddress, NiosDnsZone, NiosDnsRecord,
│                                #   NiosHostObject, NiosDhcpRange — all immutable
├── filter.py                    # Member whitelist/blacklist filtering logic
├── counter.py                   # Count DDI objects, Active IPs per member; dual formula
├── scenarios.py                 # Build current / hybrid / full-migration scenario results
└── output/
    ├── __init__.py
    └── nios_xlsx.py             # Write the NIOS XLS report (xlsxwriter, matches v1.0 style)
```

### Why a separate `nios/` package at the top level

The NIOS pipeline is architecturally independent: different input format (XML vs cloud APIs), different data model (NiosObject vs CloudResource), different output schema (scenario comparison vs per-account resource table), and different token formulas (dual NIOS/UDDI rates vs single UDDI rate). Colocating NIOS code with cloud providers would create false coupling. A separate `nios/` package makes the dependency graph clear: `nios/` imports from nothing in `providers/` or `counting/`; only `output/nios_xlsx.py` shares the xlsxwriter pattern with `output/xlsx_report.py` (same library, separate file).

---

## Data Flow: `.tar.gz` to XLS

```
Input: backup.tar.gz
           |
           v
nios/parser/extractor.py
  tarfile.open() streaming read
  locate onedb.xml within archive
  yield file handle (never extract to disk)
           |
           v
nios/parser/streaming_xml.py
  xml.etree.ElementTree.iterparse() — constant memory
  accumulate OBJECT+PROPERTY pairs per element
  emit typed NiosObject instances via generator
  (NiosMember, NiosNetwork, NiosLease, NiosDnsZone, etc.)
           |
           v
nios/schema.py  (NiosObject dataclasses)
  NiosMember(virtual_oid, hostname)
  NiosNetwork(cidr, network_view, member_oid)
  NiosLease(ip, state, member_oid)
  NiosFixedAddress(ip, member_oid)
  NiosHostObject(name, ips, member_oid)
  NiosDnsZone(name, type, view, member_oid)
  NiosDnsRecord(type, name, member_oid)
  NiosDhcpRange(start, end, member_oid)
  NiosExclusionRange(start, end, member_oid)
           |
           v
nios/filter.py
  FilterConfig(whitelist_patterns, blacklist_patterns)
  resolve member IDs from NiosMember objects
  apply whitelist-first semantics (FILTER-03)
  record: matched members, excluded count per type
  yield only objects whose member_oid is in allowed set
           |
           v
nios/counter.py
  iterate filtered objects
  build MemberCounts(virtual_oid, hostname, group,
                     ddi_objects, active_ips, assets)
  DDI object count:
    dns_records + host_object_expanded_records + host_aliases
    + dns_zones + dns_views + dhcp_ranges + exclusion_ranges
    + networks + network_containers + network_views
  Active IP count:
    active/static leases + fixed_addresses + host_addresses
    + (2 per subnet: network addr + broadcast addr)
  Note: lease states included are configurable (COUNT-03)
  Output: GridCounts (per-member + aggregate totals)
           |
           v
nios/scenarios.py
  ScenarioEngine(grid_counts, migration_split)
  Scenario 1 — Current Grid:
    all members -> NIOS Object formula (DDI/50 + IPs/25 + Assets/13)
  Scenario 2 — Hybrid UDDI (requires migration split):
    nios group -> NIOS Object formula
    niosx group -> UDDI native formula (DDI/25 + IPs/13 + Assets/3)
    output: nios_tokens + niosx_tokens + combined
  Scenario 3 — Full Migration:
    all members -> UDDI native formula (DDI/25 + IPs/13 + Assets/3)
  Output: ScenarioResults (three ScenarioTotals + per-member attribution)
           |
           v
nios/output/nios_xlsx.py
  xlsxwriter.Workbook (write-only, matches existing output/xlsx_report.py style)
  Sheet 1: Object Counters (raw counts per type, "in UDDI" flag)
  Sheet 2: DDI Objects (Native vs NIOS column split)
  Sheet 3: Active IP by Type (leases / fixed / host / reservations)
  Sheet 4: Scenario Comparison (current / hybrid / full migration, side-by-side)
  Sheet 5: Member Attribution (per-member: oid, hostname, group, counts, tokens)
  Header block: NIOS version, snapshot date, filter config, migration split, timestamp
  Output: nios_analysis_<timestamp>.xlsx
```

---

## New Files

| File | Status | Purpose |
|------|--------|---------|
| `src/cloud_usage/nios/__init__.py` | **NEW** | Package entry; exports `run_nios_analysis()`, `NiosConfig` |
| `src/cloud_usage/nios/runner.py` | **NEW** | Orchestrates parse → filter → count → scenarios → output |
| `src/cloud_usage/nios/config.py` | **NEW** | `NiosConfig` dataclass loaded from YAML or dict |
| `src/cloud_usage/nios/schema.py` | **NEW** | Dataclasses for all NIOS object types |
| `src/cloud_usage/nios/parser/__init__.py` | **NEW** | Package init |
| `src/cloud_usage/nios/parser/extractor.py` | **NEW** | Streaming .tar.gz → onedb.xml file handle |
| `src/cloud_usage/nios/parser/streaming_xml.py` | **NEW** | SAX/iterparse XML → NiosObject stream |
| `src/cloud_usage/nios/parser/object_types.py` | **NEW** | XML type name constants |
| `src/cloud_usage/nios/filter.py` | **NEW** | Whitelist/blacklist member filtering |
| `src/cloud_usage/nios/counter.py` | **NEW** | DDI/IP/Asset counting with dual token formula |
| `src/cloud_usage/nios/scenarios.py` | **NEW** | Three scenario computations |
| `src/cloud_usage/nios/output/__init__.py` | **NEW** | Package init |
| `src/cloud_usage/nios/output/nios_xlsx.py` | **NEW** | XLS report writer (xlsxwriter) |

---

## Modified Files

Only the integration points are touched. All modifications are additive (new `elif` branches, new imports, new routes) — existing cloud paths are unchanged.

| File | Change | Risk |
|------|--------|------|
| `src/cloud_usage/cli.py` | Add `--nios`, `--nios-config` args; add `elif args.nios:` branch in `main()` that calls `nios.runner.run_nios_analysis()` | LOW — new elif branch, no existing code path touched |
| `src/cloud_usage/dashboard/routes/scan.py` | Add `/api/nios/start` and `/api/nios/status` POST/GET endpoints for file upload and analysis trigger | LOW — new router endpoints, no existing endpoint modified |
| `src/cloud_usage/dashboard/routes/pages.py` | Add `/tab/nios` GET route for the NIOS tab content | LOW — new route handler |
| `src/cloud_usage/dashboard/services/scan_manager.py` | Add `nios_state` and `nios_result` fields to `ScanManager` for NIOS analysis lifecycle tracking | LOW — additive field additions to existing dataclass |
| `src/cloud_usage/dashboard/app.py` | Register new NIOS route file if split into separate module | LOW — `app.include_router(nios_router)` |
| `src/cloud_usage/dashboard/templates/partials/tab_bar.html` | Add "NIOS Analysis" tab entry | LOW — add `<li>` entry to tab list |
| `src/cloud_usage/dashboard/templates/pages/nios.html` | **NEW** — NIOS tab page (upload, wizard, results) | NEW — no existing template modified |
| `src/cloud_usage/dashboard/templates/partials/wizard/nios_step1_upload.html` | **NEW** — file upload step | NEW |
| `src/cloud_usage/dashboard/templates/partials/wizard/nios_step2_members.html` | **NEW** — member list + migration group toggle | NEW |
| `src/cloud_usage/dashboard/templates/partials/wizard/nios_step3_review.html` | **NEW** — analysis config review | NEW |
| `pyproject.toml` | Add `pyyaml>=6.0` for NIOS config file parsing | LOW — new dependency, no version conflicts |

---

## Integration Points: CLI

The CLI integration is a clean `elif` branch in the `main()` function. No existing argument parsing or provider path is touched:

```python
# cli.py — additive only, no existing code modified

parser.add_argument(
    "--nios",
    type=str,
    default=None,
    metavar="BACKUP.tar.gz",
    help="Run NIOS Grid backup analysis on the given .tar.gz file",
)
parser.add_argument(
    "--nios-config",
    type=str,
    default=None,
    metavar="CONFIG.yaml",
    help="NIOS analysis config: member filters, migration split, lease states",
)

# In main():
if args.nios:
    from cloud_usage.nios import run_nios_analysis, NiosConfig
    config = NiosConfig.from_yaml(args.nios_config) if args.nios_config else NiosConfig()
    run_nios_analysis(backup_path=args.nios, config=config, output_dir=args.output_dir)
    return 0
```

The NIOS path exits before the cloud provider selection logic, so there is no interaction between the two paths at all.

---

## Integration Points: Dashboard

The dashboard integration follows the same HTMX tab pattern used for cloud discovery. The NIOS tab is additive — it does not share state with the cloud scan wizard.

### New route structure

```
POST /api/nios/upload          # Accept .tar.gz, store to temp path, return member list
POST /api/nios/start           # Start analysis with config (migration split, filters)
GET  /api/nios/status          # Poll analysis state (idle/running/complete/error)
GET  /download/<filename>      # Reuse existing download route (already generic)
GET  /tab/nios                 # HTMX tab swap — NIOS analysis tab
POST /wizard/nios/upload       # Step 1: file upload + member extraction
POST /wizard/nios/members      # Step 2: member list with group toggles
POST /wizard/nios/review       # Step 3: config review before run
```

### State management in ScanManager

NIOS analysis state is tracked as separate fields on `ScanManager`, independent from cloud scan state. This means a user can run a cloud scan and a NIOS analysis sequentially without state collision:

```python
# scan_manager.py — additive fields
@dataclass
class NiosAnalysisState(Enum):
    IDLE = "idle"
    PARSING = "parsing"
    COMPLETE = "complete"
    ERROR = "error"

class ScanManager:
    # Existing cloud scan fields unchanged
    _state: ScanState = ScanState.IDLE
    _resources: list[CloudResource] = ...

    # New NIOS fields
    _nios_state: NiosAnalysisState = NiosAnalysisState.IDLE
    _nios_result: dict | None = None        # ScenarioResults serialized to dict
    _nios_output_path: str | None = None    # Path to generated .xlsx
    _nios_temp_path: str | None = None      # Uploaded .tar.gz temp location
```

No SSE is needed for NIOS analysis. Unlike cloud discovery (which runs for 30+ minutes across 100+ accounts), NIOS analysis completes in seconds to low minutes even for 2GB files. Simple polling via `/api/nios/status` is sufficient.

---

## Architectural Patterns for NIOS

### Pattern 1: SAX/iterparse for Streaming XML

**What:** Use `xml.etree.ElementTree.iterparse()` to process onedb.xml as a stream of SAX-like events. Accumulate properties within a single `<OBJECT>` element, then emit a typed `NiosObject` and discard the element from memory with `elem.clear()`.

**When to use:** The primary parse pattern. The validated reference backup (ZF Friedrichshafen) is 2.5M objects, 2GB+ on disk. Loading the full document into memory would require 4-8GB RAM, which is not viable on customer laptops.

**Trade-offs:**
- Pro: O(1) memory per object; total memory is bounded by the largest single OBJECT element (typically a few KB)
- Pro: Works on 2GB+ files without OS-level file mapping
- Con: No random access; must make a full pass to build indexes (member map, then object filtering)
- Con: Cannot use XPath or full document traversal patterns

**Implementation sketch:**
```python
import xml.etree.ElementTree as ET

def iter_nios_objects(xml_fileobj):
    """Yield (type_name, properties_dict) for each OBJECT element."""
    context = ET.iterparse(xml_fileobj, events=("start", "end"))
    current_type = None
    current_props = {}
    inside_object = False

    for event, elem in context:
        if event == "start" and elem.tag == "OBJECT":
            inside_object = True
            current_type = None
            current_props = {}
        elif event == "end" and elem.tag == "OBJECT":
            if current_type:
                yield current_type, current_props
            inside_object = False
            elem.clear()  # release memory
        elif inside_object and event == "end" and elem.tag == "PROPERTY":
            name = elem.get("name") or elem.tag
            val = elem.text or ""
            if name == "NIOS_OBJECT_TYPE":
                current_type = val
            else:
                current_props[name] = val
```

### Pattern 2: Two-Pass Processing (Members First)

**What:** Make one forward pass through the XML to collect all `NiosMember` objects. Build the `virtual_oid → hostname` map. Then make a second pass (or continue the same stream with the map available) to emit all other object types with member attribution resolved.

**When to use:** The member map is needed to attribute every other object. Since members may appear anywhere in the XML, a two-pass approach is the safe design. In practice, members appear early in the file (they are a small object family), so the first pass completes quickly.

**Trade-offs:**
- Pro: Every object emitted by pass 2 has a resolved `hostname` field — no post-hoc resolution needed
- Pro: Filter can apply during pass 2 using the already-built member map, avoiding storing all objects before filtering
- Con: Requires two passes over the file — for a 2GB file this means reading the compressed archive twice; mitigate by storing the decompressed stream to a temp file or by holding only the member-offset map in memory for a seek-based approach

**Simplification:** For the ZF reference size (2.5M objects), two sequential passes over the compressed .tar.gz complete in under 60 seconds on a typical laptop SSD. Simplicity wins over a streaming single-pass approach.

### Pattern 3: Member-Attributed Counting

**What:** Assign every parsed object to its owning member via `virtual_oid`. Aggregate counts into a `MemberCounts` dict keyed by `virtual_oid`. This allows per-member attribution (SCEN-02 hybrid split) and the global grid view to both be computed from the same counts structure.

**When to use:** Always. Counting at member granularity first, then aggregating for scenarios, is the only design that supports all three scenario views without re-parsing.

**Trade-offs:**
- Pro: Single counting pass produces data for all three scenarios
- Pro: Member-level counts are independently auditable
- Con: Objects with no member attribution (grid-level objects) need a sentinel member ID (e.g., `virtual_oid=0` → "Grid-Level")

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Reusing `CloudResource` for NIOS Objects

**What people do:** Add NIOS-specific fields to `CloudResource` or map NIOS objects into the cloud resource schema to reuse the existing counting and output pipeline.

**Why it's wrong:** `CloudResource` has `provider`, `account_id`, `region`, `resource_type`, `ip_addresses`, and `counted/category/skip_reason` — none of which map cleanly to NIOS objects. NIOS objects have `virtual_oid`, `network_view`, `lease_state`, `zone_type`, and member attribution. Forcing the NIOS data model into `CloudResource` creates either a bloated schema (many None fields) or misleading field repurposing. The NIOS token formula also differs fundamentally (dual NIOS/UDDI rates vs single UDDI rate).

**Do this instead:** Introduce `nios/schema.py` with purpose-built dataclasses. Keep `CloudResource` untouched.

### Anti-Pattern 2: Loading the Entire XML into Memory

**What people do:** `tree = ET.parse(xml_fileobj)` or `lxml.etree.parse()`. This loads the full document tree into RAM before any processing begins.

**Why it's wrong:** The validated reference backup is 2.5M objects. Parsed into an lxml element tree, this requires 3-5GB of RAM. Customer laptops typically have 8-16GB total, and the tool may compete with their browser, IDE, and VPN client.

**Do this instead:** `ET.iterparse()` with `elem.clear()` after each OBJECT is emitted. Constant memory usage regardless of file size.

### Anti-Pattern 3: Sharing Scan State Between Cloud and NIOS Pipelines

**What people do:** Add `nios` as a fourth "provider" in `ScanConfig.providers` and run it through the existing `DiscoveryOrchestrator`.

**Why it's wrong:** The `DiscoveryOrchestrator` is built for concurrent account-level discovery with rate limiting, checkpoint/resume, and `CloudResource` output. NIOS analysis is single-file, sequential, has no API rate limits, produces no `CloudResource` objects, and completes in under a minute. Forcing it into the orchestrator adds all that machinery for zero benefit, and requires the orchestrator to know about NIOS types — breaking its provider-agnostic design.

**Do this instead:** `nios/runner.py` is a standalone synchronous function. The CLI and dashboard call it directly, not via the orchestrator.

### Anti-Pattern 4: Treating Migration Split as a Filter

**What people do:** Treat the NIOSX member group as a filter that excludes those members from counting, then compute the "rest" as NIOS-remaining.

**Why it's wrong:** The hybrid scenario requires counting NIOSX-assigned members under one formula AND NIOS-remaining members under another formula, then reporting both sub-totals plus the combined total. If you filter NIOSX members out, you lose their contribution to the hybrid total. The member attribution table must include every member.

**Do this instead:** The migration split is a group assignment, not an exclusion filter. `scenarios.py` receives all member counts plus the split config, then applies the appropriate formula per group.

### Anti-Pattern 5: Computing NIOS Tokens in `counting/token_calculator.py`

**What people do:** Add NIOS formula constants and a NIOS-specific function to the existing `token_calculator.py` to avoid code duplication.

**Why it's wrong:** `token_calculator.py` is used by the cloud pipeline and is tested against cloud-specific scenarios. Adding NIOS constants (`DDI_PER_TOKEN_NIOS = 50`) and a parallel function conflates two independent licensing domains. Future changes to either formula become hazardous.

**Do this instead:** `nios/counter.py` contains its own formula constants and token math. A single `_ceil_div()` helper is identical to the one in `token_calculator.py` but is defined locally — four lines of code duplication is better than cross-domain coupling.

---

## Component Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `cli.py` → `nios/runner.py` | Direct function call with `NiosConfig` | No orchestrator, no cloud code involved |
| `dashboard/routes/scan.py` → `nios/runner.py` | `asyncio.to_thread()` with `NiosConfig` | Same pattern as cloud scan pipeline in background thread |
| `nios/runner.py` → `nios/parser/` | Pass file path; receive NiosObject stream via generator | Parser never imports runner |
| `nios/runner.py` → `nios/filter.py` | Pass NiosObject stream + FilterConfig; receive filtered stream | Pure function on the stream |
| `nios/runner.py` → `nios/counter.py` | Pass filtered NiosObject stream; receive `GridCounts` | Pure function, no side effects |
| `nios/runner.py` → `nios/scenarios.py` | Pass `GridCounts` + `MigrationSplit`; receive `ScenarioResults` | Pure computation |
| `nios/runner.py` → `nios/output/nios_xlsx.py` | Pass `ScenarioResults` + file path; receive written file path | File I/O only |
| `nios/` → `output/xlsx_report.py` | **No import** — separate output module | NIOS XLS format is entirely different from cloud XLS format |
| `nios/` → `counting/` | **No import** | Counting logic is NIOS-specific |
| `nios/` → `providers/` | **No import** | No cloud SDK dependencies |
| `nios/` → `schema/resource.py` | **No import** | `CloudResource` is for cloud providers only |

---

## Build Order

This sequence respects data dependencies. Each phase has no forward dependencies on phases above it.

### Phase 10: Parser + Schema (foundation)
**Builds:** `nios/schema.py`, `nios/parser/`
**Why first:** Every subsequent module depends on the typed `NiosObject` stream. The schema defines the data model. The parser is the only module that reads raw XML. No other module should know about XML structure.
**Testable alone:** Unit tests with a minimal synthetic `onedb.xml` fixture (50 objects of each type). Test that each object type parses correctly. Test that 2GB+ file iteration does not exhaust memory.
**No dependencies on:** anything else in `nios/`

### Phase 11: Filter + Counter
**Builds:** `nios/filter.py`, `nios/counter.py`, `nios/config.py`
**Why second:** Filter and counter take the `NiosObject` stream as input. `config.py` is needed by filter and counter (lease state config, whitelist/blacklist patterns).
**Depends on:** Phase 10 (`nios/schema.py`, `nios/parser/`)
**Testable alone:** Unit tests with synthetic object streams. Test whitelist-first semantics (FILTER-03). Test all DDI object types contribute to DDI count (COUNT-01). Test active IP calculation (COUNT-02). Test configurable lease states (COUNT-03). Test per-member attribution (COUNT-06).

### Phase 12: Scenarios
**Builds:** `nios/scenarios.py`
**Why third:** Scenarios are pure computation over `GridCounts` (output of counter). No file I/O. No parsing. This is the most logic-rich module and benefits from clean isolated testing.
**Depends on:** Phase 11 (`nios/counter.py` for `GridCounts` type)
**Testable alone:** Unit tests with constructed `GridCounts` objects. Verify all three formula outputs (SCEN-01, SCEN-02, SCEN-03). Verify hybrid sub-totals sum to combined total. Verify that members with no explicit group assignment default to NIOS-remaining (MIGR-03).

### Phase 13: Output + Runner
**Builds:** `nios/output/nios_xlsx.py`, `nios/runner.py`, `nios/__init__.py`
**Why fourth:** Output depends on `ScenarioResults` (Phase 12 output). Runner wires all phases together and is the last piece before integration.
**Depends on:** Phases 10–12 for data types; `xlsxwriter` (already a project dependency from `output/xlsx_report.py`)
**Testable alone:** Integration test with the ZF reference backup or a synthetic large fixture. Verify XLS sheet structure and content (OUT-01 through OUT-05).

### Phase 14: CLI Integration
**Builds:** Modified `cli.py` (new `--nios`, `--nios-config` args and `elif` branch)
**Depends on:** Phase 13 (`nios.run_nios_analysis`)
**Test:** End-to-end CLI invocation: `python -m cloud_usage.cli --nios backup.tar.gz` produces `nios_analysis_<timestamp>.xlsx` in the output dir. INTEG-01 acceptance.

### Phase 15: Dashboard Integration
**Builds:** New routes in `dashboard/routes/`, new templates, `ScanManager` NIOS state fields, tab bar update
**Depends on:** Phase 13 (`nios.run_nios_analysis`), existing dashboard infrastructure
**Test:** Dashboard NIOS tab renders. Upload wizard accepts .tar.gz. Member list displays. Analysis runs. XLS download works. INTEG-02 acceptance.

---

## Scaling Considerations

NIOS analysis does not have the same scaling concerns as cloud discovery. There are no external APIs, no rate limits, and no concurrent workers. The scale challenge is file size.

| Concern | Approach |
|---------|----------|
| 2GB+ onedb.xml (inside .tar.gz) | `ET.iterparse()` with `elem.clear()`. Constant memory regardless of file size. Validated ref: 2.5M objects. |
| 2GB compressed archive | `tarfile.open()` in streaming mode (`r|gz`). Decompress on the fly; never extract full file to disk. |
| Member attribution for 2.5M objects | `dict[int, MemberCounts]` keyed by `virtual_oid`. With 168 members (ZF reference), the dict stays tiny. |
| Counter memory | Running totals only (one `MemberCounts` per member). Never holds more than one `NiosObject` in memory at a time during counting pass. |
| Dashboard file upload | Write .tar.gz to a named temp file in `output/.nios_temp/`. Delete after analysis completes or on new upload. Do not hold the file bytes in process memory. |

---

## Sources

- Direct codebase analysis of `src/cloud_usage/` (HIGH confidence — read every relevant module)
- `REQUIREMENTS.md` v1.1 requirements (HIGH confidence — authoritative spec)
- `PROJECT.md` context and constraints (HIGH confidence)
- Python `xml.etree.ElementTree.iterparse()` documentation — stdlib, HIGH confidence
- Validated reference data: ZF Friedrichshafen backup, 2.5M objects, 2GB+, cited in PROJECT.md

---

*Architecture research for: NIOS Grid Analysis integration into Universal DDI Cloud Usage Estimator*
*Researched: 2026-02-28*
