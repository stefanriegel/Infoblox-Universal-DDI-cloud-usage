# Project Research Summary

**Project:** Universal DDI Cloud Usage Estimator — v1.1 NIOS Grid Analysis
**Domain:** NIOS Grid backup parsing and UDDI hybrid licensing token estimation
**Researched:** 2026-02-28
**Confidence:** HIGH

## Executive Summary

This milestone adds NIOS Grid backup analysis to an existing, validated Python tool that already handles cloud discovery (AWS/Azure/GCP), token calculation, and XLS report generation. The v1.1 addition is architecturally independent: a new `nios/` package under `src/cloud_usage/` that reads a `.tar.gz` NIOS backup file, streams the 2GB+ `onedb.xml` database using `lxml.etree.iterparse`, counts DDI objects and Active IPs per member, applies dual token formulas, and produces a 5-sheet XLS report with three licensing scenario views. The only new library dependency is `lxml>=5.3.0`; everything else (openpyxl, PyYAML, tarfile, Pydantic) is already in the stack. The project has a validated reference dataset — ZF Friedrichshafen (2.5M objects, 605K raw lease rows, 49K networks, 239 members) — that provides concrete acceptance criteria for every phase.

The recommended approach is a sequential 6-phase build: parser and schema first (foundation), then filter and counter (counting rules), then scenario engine (token math), then XLS output and runner (integration), then CLI wiring, and finally the web dashboard tab. This order respects strict data-flow dependencies: member identity must be resolved before filtering, filtering must gate object ingestion before counting begins, and counting must complete before scenarios are computed. The architecture enforces these constraints by making each phase's outputs the typed inputs of the next phase, so violations become compile-time (type checker) rather than runtime errors.

The dominant risks are correctness risks, not infrastructure risks. Three silent errors could produce plausible-looking but wrong numbers: counting raw lease rows instead of unique IPs inflates Active IP totals by 3-4x; failing to expand Host Objects to constituent DNS records produces wrong DDI totals at enterprise scale; applying UDDI native formula divisors to NIOS-remaining members (who should use NIOS Object divisors) overstates their token contribution by 2x. Each has a concrete prevention strategy with a verifiable acceptance test against the ZF reference numbers. Establishing these tests in the counting phase (Phase 11 in this numbering) before any output or integration work begins is the single most important schedule risk mitigation.

## Key Findings

### Recommended Stack

The existing stack handles everything this milestone needs. The single new dependency is `lxml>=5.3.0` — its C-backed `iterparse` keeps peak memory at 50-100MB while processing 2.5M objects, versus unbounded memory growth with stdlib `ElementTree.iterparse` due to a known CPython bug (issues #102055 and #35502). Two critical pattern decisions: use `tarfile.open(mode="r:gz")` (colon, not pipe) for seeking access to the compressed archive — the pipe mode `r|gz` has a known 14x performance regression (cpython #121109, open as of Feb 2026); and always call `elem.clear()` plus delete preceding siblings after processing each `<OBJECT>` element or RAM grows linearly to process completion on a 2GB file.

**Core technologies:**
- `lxml>=5.3.0`: Streaming XML parse of 2GB+ `onedb.xml` — C-backed iterparse with `huge_tree=True` and `recover=True`; `elem.clear()` + sibling deletion keeps memory flat at 50-100MB regardless of file size
- `tarfile` stdlib (`r:gz` mode): In-memory access to `onedb.xml` inside `.tar.gz` via `extractfile()` — no disk extraction, no new dependency, no temp files
- `PyYAML>=6.0.2`: Parse `--nios-config` YAML file (member filters, migration split, lease states) — already a transitive dependency; `yaml.safe_load()` only, never `yaml.load()`
- `openpyxl` (existing): 5-sheet XLS report output — same library as cloud output, separate new file `nios/output/nios_xlsx.py`
- `Pydantic v2` (existing): `NiosConfig` dataclass validation; existing `CloudResource` schema completely untouched

### Expected Features

See `.planning/research/FEATURES.md` for the full decision table, dependency graph, and edge cases.

**Must have (table stakes — v1.1 launch blockers):**
- Streaming `.tar.gz` / `onedb.xml` parser — handles 2GB+ without memory exhaustion (PARSE-01, PARSE-02)
- Member identity map — `virtual_oid` to hostname/FQDN resolution before filtering or counting (PARSE-04)
- DDI object extraction with Host Object expansion — A + PTR + optional CNAME per IP per Host Object, not counting the Host Object container row (COUNT-01)
- Active IP calculation — deduplicated leases (active+static default) + fixed addresses + host IPs + 2 per subnet network/broadcast reservations (COUNT-02, COUNT-03)
- Structural integrity check — mandatory object families present, member references resolvable, raw vs. unique IP counts reported (PARSE-13)
- Dual token formula — NIOS Object (DDI/50 + IPs/25 + Assets/13) for NIOS-remaining, UDDI native (DDI/25 + IPs/13 + Assets/3) for NIOSX-migrated (COUNT-04, COUNT-05)
- Three scenario views — current grid (NIOS Object for all), hybrid UDDI (split formula), full migration (UDDI native for all) (SCEN-01, SCEN-02, SCEN-03)
- Member attribution table — per member: `virtual_oid`, hostname, group, DDI count, Active IP count, token contribution (COUNT-06, OUT-03)
- XLS report (5 sheets) — Object Counters, DDI Objects, Active IP by Type, Scenario Comparison, Member Attribution (OUT-01 through OUT-05)
- CLI integration — `--nios <backup.tar.gz>` and `--nios-config <config.yaml>` (INTEG-01)
- Member whitelist/blacklist — hostname glob or `virtual_oid` list, whitelist-first semantics (FILTER-01 through FILTER-04)
- Migration split via YAML config file — `niosx:` member list, configurable default group (MIGR-01, MIGR-03)

**Should have (significant SE friction without — v1.1.x after core validated):**
- Web dashboard NIOS Analysis tab — file upload wizard, member list with group toggles, results display (INTEG-02, MIGR-02)
- Configurable default migration group — "all default to NIOSX except these few" reduces explicit assignments for 200+ member grids (MIGR-03 extended)

**Defer (v1.2+):**
- Confidence scoring per metric (NIOS-ADV-02) — needs governance sign-off first
- DTC/LBDN objects in DDI count (NIOS-ADV-05) — licensing semantics unconfirmed with Infoblox product team
- Cross-source reconciliation (NIOS-ADV-01) — second input file adds UI complexity
- Snapshot date delta comparison (NIOS-ADV-04) — manual XLS comparison is sufficient initially

**Anti-features explicitly excluded:**
- Count all lease states including expired/released/free — produces 3.6x overcount (605K rows vs 168K active IPs at ZF scale)
- Global IP deduplication across network views — undercounts environments with overlapping RFC1918 address ranges across NIOS Network Views
- Live NIOS API connection — requires credentials, network access to Grid Manager, and customer security approval; backup-based analysis is point-in-time, reproducible, and offline
- Count DTC/LBDN objects in v1.1 — licensing semantics not confirmed; count as informational-only in Object Counters sheet

### Architecture Approach

The NIOS pipeline is fully isolated in a new `src/cloud_usage/nios/` package. It imports nothing from `providers/`, `counting/`, `discovery/`, or `schema/resource.py`. The only shared infrastructure is openpyxl (same library, separate output file) and the entry points (`cli.py` with an additive `elif args.nios:` branch; `dashboard/` with additive routes). This isolation is enforced, not aspirational: the NIOS data model (`NiosObject` subclasses) is incompatible with `CloudResource`, and the token formulas have different divisors per licensing category. The pipeline is synchronous, single-threaded, and completes in seconds to low minutes for a 2GB file — it does not use `DiscoveryOrchestrator`, ThreadPoolExecutor, or SSE progress streaming (simple polling is sufficient).

**Major components:**
1. `nios/parser/` — `tarfile.extractfile()` yields `onedb.xml` file handle; `lxml.etree.iterparse` with `huge_tree=True` streams typed `NiosObject` instances; two-pass design builds member map first, then streams all other objects with member IDs resolvable
2. `nios/filter.py` — resolves effective member set from whitelist/blacklist patterns before any object counting; filter is applied at ingestion time, not display time
3. `nios/counter.py` — accumulates `MemberCounts` per `virtual_oid`; DDI (with Host Object expansion precedence rule), Active IPs (deduplicated set per network view), Assets (none in v1.1); NIOS Object and UDDI native formula constants defined here only
4. `nios/scenarios.py` — pure computation over `GridCounts`; applies correct formula per member group; hybrid sub-totals must sum to combined total; verified by unit test before any output work
5. `nios/output/nios_xlsx.py` — 5-sheet XLS using openpyxl; structurally separate from cloud `output/xlsx_report.py`; header block includes NIOS version, snapshot date, filter config, migration split, formula constants used
6. `nios/runner.py` — top-level orchestrator wiring parse → filter → count → scenarios → output; called directly from CLI or dashboard thread; no dependency on cloud pipeline

### Critical Pitfalls

1. **iterparse accumulates the entire XML tree unless elements are explicitly cleared** — stdlib `ElementTree.iterparse` builds a growing in-memory tree despite appearing to stream (CPython issues #102055, #35502). After processing each `<OBJECT>`, call `elem.clear()` and delete preceding siblings. With lxml, the sibling deletion loop (`while elem.getprevious(): del elem.getparent()[0]`) is also required. Without this, a 2.5M-object file OOM-kills the process. Must be established in Phase 10 before any performance testing — never retrofit.

2. **Counting raw lease rows instead of unique IPs inflates Active IP totals by 3-4x** — ZF reference: 605,489 raw rows vs 168,295 unique active-only IPs. NIOS stores one row per lease lifecycle event, not one row per currently-active IP. The Active IP pipeline must be: apply state filter → extract IP field → add to a `set` → `len(set)` is the contribution. Raw row count must never enter the token formula. Acceptance criterion: ZF reference produces exactly 168,295 active-only IPs, not 605,489.

3. **Host Object expansion double-counts DNS records if raw A/PTR/CNAME records are also counted** — `onedb.xml` stores Host Objects AND the DNS records they generate as independent objects. Counting both inflates DDI totals by hundreds of thousands at ZF scale. Prevention: collect all Host Object OIDs during the parse pass; when processing independent DNS record objects, skip any whose `parent_oid` is in the Host Object OID set.

4. **Filter applied after counting instead of before — member whitelist/blacklist has no effect on token totals** — filter must gate object ingestion during the parse pass, not filter the display table after counts are accumulated. The effective member set must be computed before the main parse begins. Verification: changing whitelist/blacklist config must change both member attribution table rows AND summary token totals.

5. **Dual formula misapplication in hybrid scenario** — the existing `token_calculator.py` uses UDDI native divisors (25/13/3); NIOS-remaining members require NIOS Object divisors (50/25/13). Passing NIOS counts to the existing calculator silently overstates NIOS-remaining tokens by 2x. Prevention: define NIOS Object formula constants in `nios/counter.py` only; never import or call the cloud `calculate_tokens()` function from the NIOS pipeline. Unit test: same input counts produce different totals under each formula.

6. **FastAPI `UploadFile` is closed before background thread reads it** — Starlette closes the `SpooledTemporaryFile` after the HTTP response is sent; the background thread receives a closed file handle and the parse silently produces zero objects. Prevention: save the uploaded file to a known disk path within the request handler (before returning); pass the path string — not the file handle — to the background thread via `run_in_executor`.

## Implications for Roadmap

The ARCHITECTURE.md build order maps directly to phases. The phase numbering continues from existing phases (the project is at Phase 9 of a prior roadmap).

### Phase 10: NIOS Parser and Schema (Foundation)

**Rationale:** Every subsequent module depends on the typed `NiosObject` stream and the member identity map. The parser is the only module that reads raw XML; schema defines the data model. The two-pass design (members first, all objects second) must be established here so filter and counter can rely on resolved member IDs at ingestion time. This phase carries the highest infrastructure risk (memory management, streaming correctness) and must be proven with memory profiling tests before building on top of it.

**Delivers:** `nios/schema.py` (typed dataclasses for all object types), `nios/parser/extractor.py` (tar.gz streaming via `tarfile.extractfile()`), `nios/parser/streaming_xml.py` (lxml iterparse with `elem.clear()` + sibling deletion), `nios/parser/object_types.py` (XML type name constants), two-pass member map build

**Addresses:** PARSE-01, PARSE-02, PARSE-04, PARSE-13 (structural integrity foundation)

**Avoids:** iterparse memory leak (Pitfall 1), tar.gz disk extraction double I/O (Pitfall 2), orphaned lease silent drop (Pitfall 3)

**Research flag:** No additional research needed. lxml iterparse and tarfile patterns are fully specified with verified code examples in STACK.md and PITFALLS.md.

### Phase 11: Filter and Counter (Counting Rules)

**Rationale:** Contains the highest correctness risk of the entire milestone. The counting rules — Host Object expansion, lease deduplication, network reservation derivation, whitelist-first filter semantics, and dual formula constants — must be unit-tested against the ZF reference values (168,295 active-only IPs from 605,489 rows) before any downstream work begins. A wrong count silently propagates through scenarios, XLS output, and customer-facing numbers. Acceptance tests here are the primary regression protection for the entire milestone.

**Delivers:** `nios/filter.py` (whitelist/blacklist resolution, effective member set, filter applied at ingestion), `nios/counter.py` (DDI/IP/Asset counting per member with Host Object expansion precedence rule, lease dedup set, network reservation derivation, both formula constant sets), `nios/config.py` (NiosConfig dataclass)

**Addresses:** FILTER-01 through FILTER-04, COUNT-01 through COUNT-06

**Avoids:** lease row count inflation (Pitfall 4), Host Object expansion double-count (Pitfall 5), filter-after-count (Pitfall 6), dual formula misapplication (Pitfall 7)

**Research flag:** No additional research needed. Counting rules are fully specified in FEATURES.md (object type table, lease state semantics, Host Object expansion rules, network reservation derivation) with ZF reference acceptance values.

### Phase 12: Scenario Engine

**Rationale:** Pure computation over `GridCounts` (output of Phase 11). No file I/O, no parsing, no output formatting. The most logic-rich module in isolation; benefits from clean unit testing with constructed `GridCounts` objects. The hybrid scenario (SCEN-02) requires explicit formula-per-group separation: NIOS-remaining members use NIOS Object divisors, NIOSX-migrated members use UDDI native divisors, and both sub-totals must sum to the combined total. This invariant must be a unit test before Phase 13 begins.

**Delivers:** `nios/scenarios.py` with three scenario computations: SCEN-01 (all members NIOS Object formula), SCEN-02 (dual formula with migration split, sub-totals independently calculated and summed), SCEN-03 (all members UDDI native formula)

**Addresses:** SCEN-01, SCEN-02, SCEN-03, MIGR-01, MIGR-03, MIGR-04

**Avoids:** hybrid sub-total blending error (SCEN-02 must apply formula per group, not blend counts then apply single formula)

**Research flag:** No additional research needed. Formula constants and scenario logic fully specified in FEATURES.md and ARCHITECTURE.md.

### Phase 13: Output and Runner

**Rationale:** XLS output depends on `ScenarioResults` (Phase 12). Runner wires all components and defines the public API (`run_nios_analysis()`) that CLI and dashboard both call. The dashboard upload endpoint (Phase 15) depends on this API being stable. Integration testing with the ZF reference backup (or a synthetic large fixture) validates the complete pipeline before CLI or UI work begins.

**Delivers:** `nios/output/nios_xlsx.py` (5-sheet XLS with header block, formula footnotes, member attribution table), `nios/runner.py` (parse → filter → count → scenarios → output orchestration), `nios/__init__.py` (public API export)

**Addresses:** OUT-01 through OUT-05

**Research flag:** No additional research needed. openpyxl multi-sheet pattern is identical to existing cloud output; runner wiring follows ARCHITECTURE.md component boundary definitions.

### Phase 14: CLI Integration

**Rationale:** Clean `elif` branch in `cli.py`. Minimal surface area — no existing code path is touched. Validates the full pipeline end-to-end via command line before dashboard adds UI complexity. Serves as the first integration acceptance test: `python -m cloud_usage.cli --nios backup.tar.gz` must produce `nios_analysis_<timestamp>.xlsx` containing correct counts per the ZF reference values.

**Delivers:** Modified `cli.py` with `--nios <backup.tar.gz>` and `--nios-config <config.yaml>` arguments; `elif args.nios:` branch calling `nios.runner.run_nios_analysis()`; end-to-end acceptance test (INTEG-01)

**Addresses:** INTEG-01

**Research flag:** No additional research needed. Additive argparse pattern with no existing code path touched.

### Phase 15: Dashboard Integration (NIOS Tab)

**Rationale:** Highest UI complexity phase; depends on all prior phases being stable. Introduces the `UploadFile` → disk → background thread pattern (Pitfall 8 prevention), new HTMX routes, `NiosAnalysisState` enum independent of cloud `ScanState`, and the migration split wizard. Building this last means the underlying pipeline is proven and the dashboard integration adds UI layer only, not logic changes.

**Delivers:** New routes in `dashboard/routes/` (upload, start, status, tab, wizard steps), `ScanManager` NIOS state fields (additive, independent from cloud scan state), NIOS tab templates (file upload wizard → member list with toggles → review → results), tab bar entry, path-based upload dispatch (file saved to disk before background thread starts)

**Addresses:** INTEG-02, MIGR-02

**Avoids:** UploadFile closed before background task (Pitfall 8) by saving to disk path first; SpooledTemporaryFile spool limit (Pitfall 9) by closing `UploadFile` after save; ScanManager/EventBridge coupling with cloud pipeline by using separate `NiosAnalysisState` enum and `nios_*` event names

**Research flag:** Review the existing `_run_scan_pipeline()` executor dispatch pattern in `scan.py` before implementation to ensure consistency. FastAPI UploadFile prevention pattern is fully specified in PITFALLS.md with code example.

### Phase Ordering Rationale

- Phases 10-12 are sequential with hard data-flow dependencies: typed schema before filter, effective member set before counter, `GridCounts` before `ScenarioResults`. There is no parallelism available within this core pipeline.
- Phase 13 (output + runner) is the integration point; it cannot begin until Phases 10-12 are complete and unit-tested.
- Phase 14 (CLI) begins as soon as Phase 13's public API is stable; it is the first integration validation and provides end-to-end test coverage before any UI work.
- Phase 15 (dashboard) is last because it has the highest surface area and can only be built on top of a stable Phase 13 `run_nios_analysis()` API. UI bugs are less costly than counting bugs.
- Correctness-critical code (counting rules, formula constants) is built and acceptance-tested in Phases 10-11 before any deadline pressure from UI implementation exists.

### Research Flags

**Phases needing deeper research during planning:** None. All patterns are fully specified in the research files with concrete code examples. The ZF reference dataset provides acceptance criteria for every counting rule. No novel technical decisions remain unresolved.

**Phases with standard patterns (all phases skip research-phase):**
- **Phase 10:** lxml iterparse and tarfile patterns are fully specified with code in STACK.md and PITFALLS.md; CPython memory bug behavior is traced to specific issue numbers
- **Phase 11:** All counting rules fully specified in FEATURES.md with ZF reference values as acceptance criteria
- **Phase 12:** Formula constants and scenario computation fully specified; only pure Python arithmetic
- **Phase 13:** openpyxl multi-sheet pattern matches existing cloud output; runner wiring is direct function composition
- **Phase 14:** Additive argparse pattern; no new technical decisions
- **Phase 15:** FastAPI upload-to-disk-then-thread pattern fully specified with code example in PITFALLS.md; HTMX tab pattern follows existing cloud scan tab

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Single new dependency (lxml 6.0.2). All patterns verified against official lxml docs, CPython issue tracker with specific issue numbers, PyPI version pages. No version conflicts with existing stack identified. tarfile and PyYAML are already present. |
| Features | HIGH | Canonical object-type decision table derived from validated customer backup (ZF Friedrichshafen) and authoritative internal framework doc (do_not_commit/CLAUDE.md). Lease state semantics confirmed by Infoblox WAPI 2.13.7 documentation. Host Object expansion confirmed by Infoblox community forum. ZF reference numbers provide quantitative acceptance criteria. |
| Architecture | HIGH | Based on direct codebase analysis of all relevant modules. Build order verified against REQUIREMENTS.md dependency graph. Component boundaries explicitly defined with rationale for anti-patterns. NIOS isolation from cloud pipeline is enforced by data model incompatibility, not just convention. |
| Pitfalls | HIGH | Nine critical pitfalls documented; six are critical, three are dashboard-specific. Each traced to a specific CPython or FastAPI issue number with an open/confirmed status. Prevention strategies are concrete code patterns with warning signs and a recovery cost table. Each pitfall maps to a specific phase. |

**Overall confidence:** HIGH

### Gaps to Address

- **Host Object parent-OID field name in onedb.xml:** The exact NIOS XML property name that identifies an independent DNS record as "generated by a Host Object" (used in Pitfall 5 / Host Object expansion double-count prevention) requires validation against the ZF reference backup. FEATURES.md rates this MEDIUM confidence. During Phase 11 implementation, inspect the actual `onedb.xml` structure for A/PTR/CNAME records that have a Host Object parent to confirm the field name before finalizing the precedence rule.

- **CNAME condition for Host Object expansion:** Whether a Host Object generates a CNAME record depends on whether a canonical name alias is defined on the host. The exact `onedb.xml` property that signals this condition requires confirmation from the ZF backup data. Phase 11 should validate the expansion rule against the reference backup before the DDI counter is finalized. FEATURES.md rates this MEDIUM confidence.

- **DTC/LBDN licensing semantics (deferred to v1.2):** Requires Infoblox product team sign-off on whether DTC Server, Pool, LBDN, Health Monitor, and Topology Rule objects count toward UDDI DDI tokens. Do not include in v1.1 DDI count. Parse and report them as informational-only in the Object Counters sheet so the data is available when governance decision is made.

- **Network Insight discovery IP policy (out of scope v1.1):** Excluded from Active IP count by default per FEATURES.md anti-features. Requires explicit customer confirmation of Network Insight licensing and deployment scope before enabling. Flag as "unresolved per do_not_commit/CLAUDE.md Section 11" in report output when the raw discovered IP count is shown.

## Sources

### Primary (HIGH confidence)
- `do_not_commit/CLAUDE.md` — authoritative framework from ZF Friedrichshafen customer meeting (Feb 27, 2026); defines Active IP components, NIOS-to-UDDI category mapping, lease state semantics, member attribution requirements, and verification gates
- `.planning/REQUIREMENTS.md` — 37 requirements across PARSE/FILTER/COUNT/MIGR/SCEN/OUT/INTEG families
- `.planning/PROJECT.md` — dual token formula constants, reference backup statistics, phase context
- [lxml PyPI page](https://pypi.org/project/lxml/) — version 6.0.2 confirmed, Python 3.9 wheel support confirmed
- [lxml performance benchmarks](https://lxml.de/performance.html) — iterparse throughput vs stdlib ElementTree
- [lxml API: iterparse](https://lxml.de/api/lxml.etree.iterparse-class.html) — `huge_tree`, `recover`, `resolve_entities` parameters
- [Python tarfile stdlib docs](https://docs.python.org/3/library/tarfile.html) — `extractfile()` behavior, seeking (`r:gz`) vs pipe (`r|gz`) mode distinction
- [PyYAML PyPI](https://pypi.org/project/PyYAML/) — version 6.0.3, `safe_load()` requirement
- [Infoblox WAPI Lease Object Docs](https://ipam.illinois.edu/wapidoc/objects/lease.html) — complete `binding_state` enumeration (ACTIVE, STATIC, BACKUP, EXPIRED, RELEASED, FREE, ABANDONED, DECLINED, OFFERED, RESET)

### Secondary (MEDIUM confidence)
- [Infoblox Community: Host Record A and PTR](https://community.infoblox.com/discussion/15621/host-record-a-and-ptr-entries) — constituent record composition per host IP confirmed
- [Universal DDI Licensing — Infoblox Docs](https://docs.infoblox.com/space/BloxOneDDI/846954761/Universal+DDI+Licensing) — NIOS Object vs Native Object token categories
- [Nick Janetakis: lxml 20x faster XML parsing](https://nickjanetakis.com/blog/how-i-used-the-lxml-library-to-parse-xml-20x-faster-in-python) — practical benchmark
- [WebScraping.AI: lxml memory management](https://webscraping.ai/faq/lxml/what-are-the-best-practices-for-managing-memory-usage-when-using-lxml) — `elem.clear()` + sibling deletion pattern

### Issue Trackers (HIGH confidence for specific bugs)
- CPython issue #102055 — ElementTree iterparse memory non-release root cause (open)
- CPython issue #35502 — iterparse memory leak historical context
- CPython issue #121109 — tarfile `r|gz` 14x slowdown bug (open, Feb 2026)
- FastAPI discussion #10936 — UploadFile closed before background task executes
- FastAPI issue #5777 — SpooledTemporaryFile spool limit ignored in UploadFile

---
*Research completed: 2026-02-28*
*Ready for roadmap: yes*
