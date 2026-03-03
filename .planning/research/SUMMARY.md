# Project Research Summary

**Project:** Infoblox Universal DDI Cloud Usage Estimator — v1.4 Audit Depth
**Domain:** FastAPI + HTMX + Jinja2 dashboard — additive per-account attribution tables and NIOS object family breakdown
**Researched:** 2026-03-03
**Confidence:** HIGH

---

## Executive Summary

This is a v1.4 milestone on a fully-validated existing tool. The codebase is mature: cloud
discovery, NIOS Grid backup parsing, SSE-driven progress, and XLS report generation all ship
and work. What is missing is the WebUI's ability to explain token totals without requiring the
user to open the XLS file. The two v1.4 features are purely additive: a cloud per-account
attribution table (with inline formula derivation and resource-type breakdown) and a NIOS object
family breakdown table (mirroring the XLS Object Counters sheet). Neither feature changes
existing behaviour; both add new display sections below existing content.

The recommended approach requires zero new libraries, zero new routes, and zero new service
files. The cloud attribution table is achieved by extending `_compute_summary()` in `pages.py`
and updating `pages/summary.html`. The NIOS family breakdown is achieved by storing
`IntegrityReport.families_found` on `NiosScanManager` (one new field, one new setter, one
property) and extending `partials/nios/complete.html`. All four key architectural patterns from
the existing codebase apply directly: additive context extension, thread-safe state accumulation
in managers, compute-on-render (not at scan time), and template-owned formula constants.

The primary risks are not technical but presentational. Ceiling-division rounding means
per-account token totals cannot be summed to the grand total; cross-account IP deduplication
means per-account IP totals cannot be summed either. Both must be flagged in the templates with
explanatory notes rather than raw sum footers, or enterprise auditors will immediately lose
trust. The NIOS family breakdown carries an additional semantic risk: `IntegrityReport
.families_found` stores raw object counts, not DDI-adjusted counts — the `host_object` family
expands to 2-3 DDI records each, so the "Object Count" column must be clearly labeled and a
prominent note must explain that the displayed totals differ from the scenario DDI total.

---

## Key Findings

### Recommended Stack

No new dependencies are required for v1.4. The existing stack — FastAPI >= 0.115.0, Jinja2 >=
3.1.0, HTMX (vendored), PicoCSS (vendored), lxml >= 5.3.0, xlsxwriter >= 3.1.0 — is fully
capable of delivering both features. The only new Python capability needed is
`collections.Counter` from the standard library, already used elsewhere in the codebase.

**Core technologies (all unchanged):**
- **FastAPI >= 0.115.0**: Route handlers — extend `_compute_summary()` and `tab_nios()` context; no new routes
- **Jinja2 >= 3.1.0**: Renders both new tables using the scrollable-div + `<table>` pattern established in `complete.html`
- **HTMX (vendored)**: No new attributes needed; existing `hx-get`/`hx-target`/`hx-swap` patterns cover both features
- **PicoCSS (vendored)**: `<table role="grid">` and scrollable-div styling already handles both new tables
- **collections.Counter (stdlib)**: Per-account resource-type counting; three-line extension of the existing `_compute_summary()` loop

**Integration points confirmed by direct source read:**

- **Cloud attribution data**: Already computed. `_compute_summary()` builds `per_account_details`
  (account_id, provider, ddi_count, ip_count, asset_count, total_tokens). Only `resource_type_breakdown`
  dict is missing — add a `Counter` pass in the same per-account loop. No new route needed.
- **NIOS family data**: `IntegrityReport.families_found` is computed by `inspect_backup()` in Step 1
  of the pipeline but currently discarded. Must be stored on `NiosScanManager`. The canonical display
  order and DDI classification already exist in `nios/output.py` (`_ALL_FAMILIES_ORDERED`) and
  `nios/counter.py` (`_DDI_FAMILIES`).

### Expected Features

**Must have — v1.4 launch (all three required for milestone goal):**
- **Cloud per-account formula derivation** — inline `DDI ÷ 25 = X.X, IPs ÷ 13 = X.X, Assets ÷ 3 = X.X` per account row; data already present, template-only work following the existing NIOS scenario card pattern
- **Cloud per-account resource-type count breakdown** — show VM/subnet/DNS zone counts that produced the DDI total; requires `_compute_summary()` extension with `Counter` per account
- **NIOS object family breakdown table** — non-zero families only, DDI vs. non-DDI flag, reason column; mirrors XLS Object Counters sheet; requires storing `IntegrityReport.families_found` on `NiosScanManager`

Also required for milestone completeness (low-complexity additions within the two main features):
- **Grand total reconciliation footnote** (cloud) — note that per-account token rows do not sum to the grand total due to ceiling division; no new code, template-only
- **DDI-only family subtotal row** (NIOS) — subtotal row for DDI families using `_DDI_FAMILIES` frozenset; template logic
- **Informational-only family reason text** (NIOS) — reason column for non-DDI families; values from `_UDDI_FLAG_REASON` in `output.py`

**Should have — add after v1.4 validation:**
- **Top-N sort for cloud per-account table** — sort by token contribution descending; one-line change in `_compute_summary()`; implement when SE feedback identifies navigation difficulty on large scans
- **HOST_OBJECT expansion note** — footnote on the NIOS family table explaining that raw object count expands to 2-3 DDI records; implement when first customer confusion about HOST_OBJECT vs. DDI total is reported

**Defer to v1.5+:**
- Collapsible per-account resource-type rows using `<details>` — useful only at 50+ accounts simultaneously visible
- Per-component DDI/IP/Asset percentage annotation — low urgency; percentage columns add visual noise for simple accounts
- Cloud formula derivation card in Results tab — explicitly out of scope per PROJECT.md v1.4

**Anti-features (confirmed do not implement):**
- Sortable/filterable attribution table columns — Results tab already provides this at resource level; complexity exceeds value for 10-100 row tables
- Per-account XLS download — existing XLS covers reporting; WebUI table is for in-session audit only
- Live recalculate on resource type toggle — risks divergence from the official XLS report
- Chart/graph visualization — explicitly excluded by PROJECT.md
- Account name lookup — requires live cloud API calls; tool is offline for result display

### Architecture Approach

Both features follow the same additive extension pattern established throughout the existing
codebase. No new routes, no new SSE events, no new service files, no new source files. Modified
components are limited to five existing files.

**Modified components and their changes:**
1. **`routes/pages.py`** — add `_count_resource_types()` helper; extend `_compute_summary()` to produce `resource_type_breakdown` per account; add `_build_family_rows()` helper; add `integrity_report` and `family_rows` to `tab_nios()` context
2. **`pages/summary.html`** — extend per-account table with formula derivation cells and resource-type breakdown section; include non-summable footer notes
3. **`services/nios_manager.py`** — add `_families_found` field, `families_found` property, `set_families_found()` setter; update `reset()` to clear field
4. **`routes/nios.py`** — add one line after `inspect_backup()` to call `nios_manager.set_families_found(integrity.families_found)`
5. **`partials/nios/complete.html`** — append family breakdown section with `{% if family_rows %}` guard after member attribution table

**Architectural patterns to follow:**
- Additive context extension: route handlers add new keys; templates use `{% if key %}` guards before rendering optional sections
- Thread-safe state accumulation: new `NiosScanManager` field must use existing `threading.Lock` exactly as `_scenario_suite` does
- Compute-on-render: `resource_type_breakdown` computed inside `_compute_summary()`, not stored in `ScanManager`
- Template-owned formula constants: divisors (25/13/3) hardcoded in Jinja2; raw counts passed from Python
- Business logic in Python: DDI family classification (`_DDI_FAMILIES`) and ordering (`_ALL_FAMILIES_ORDERED`) resolved in route handler before passing clean list to template

**Anti-patterns confirmed to avoid:**
- Do not treat `CountResult` or `ScenarioSuite` as the family breakdown source — neither exposes per-family counts
- Do not add an async HTMX partial route for the family table — data is available synchronously at tab render time
- Do not compute resource-type breakdown at scan time inside `_run_scan_pipeline()` — breaks the established compute-on-render pattern
- Do not pre-format formula strings in Python route handlers — template owns display logic

### Critical Pitfalls

The pitfalls document covers both v1.1 (NIOS parsing infrastructure, all resolved) and v1.4
(attribution tables). The v1.4-specific pitfalls are:

1. **Ceiling-division rounding makes per-account token totals non-summable (A1)** — `math.ceil()` means two accounts each with 12 DDI produce `ceil(12/25) = 1` token apiece (sum = 2), while the grand total via a single combined call on 24 DDI also produces `ceil(24/25) = 1` token. Any "Total" footer on the token column will exceed the hero summary card. Prevention: omit a summable token footer; show a note that token totals are computed on combined counts. The existing `complete.html` member attribution table handles the analogous NIOS case — follow that pattern exactly.

2. **Cross-account IP deduplication makes per-account IP totals non-summable (A2)** — the global IP deduplication in `deduplicate_ips_per_vpc()` prevents RFC1918 addresses shared across accounts from inflating the grand total, but summing the per-account IP column in the attribution table undoes that deduplication. Prevention: DDI column footer IS summable (DDI objects cannot be shared across accounts); IP column footer is NOT summable. Make this distinction explicit with different treatment for each column.

3. **`families_found` stores raw object counts, not DDI-adjusted counts (A6)** — `host_object` expands to 2-3 DDI records per object in the counting pipeline, but `families_found["host_object"]` reflects the raw XML object count. Building the family breakdown column from `families_found` and labeling it "DDI Objects" produces a column that does not sum to the scenario DDI total. Prevention: decide before implementation whether to use raw counts (labeled "Object Count") with a HOST_OBJECT expansion note, OR extend `count_objects()` to return DDI-adjusted per-family counts (`per_family_ddi` dict). Either is viable; the label and footnotes must be consistent with the choice.

4. **`reset()` must clear new `NiosScanManager` fields or stale data persists on re-analysis (A8)** — if `reset()` is not updated when `_families_found` is added, a re-uploaded backup shows stale family data from the previous run until the new analysis completes. Prevention: add `self._families_found = None` to `reset()` in the same commit as the field addition to `__init__()`.

5. **`family_rows` context variable must be guarded against `None` in templates (A8)** — `tab_nios()` passes `family_rows` to the template context before any analysis has run; without `{% if family_rows %}` guards the page errors on the initial pre-analysis tab load. Prevention: all new context variables added to `tab_nios()` must have explicit template guards.

**v1.1 pitfalls (resolved in shipped code, not applicable to v1.4):**
- iterparse memory management (elem.clear()) — resolved Phase 10
- tar.gz streaming without disk extraction — resolved Phase 10
- Lease row count vs. unique IP deduplication — resolved Phase 11
- HOST_OBJECT expansion double-count — resolved Phase 11
- Dual token formula misapplication — resolved Phase 11/12
- FastAPI UploadFile closed before background task — resolved Phase 13

---

## Implications for Roadmap

Both v1.4 features are independent of each other (cloud and NIOS pipelines share no state).
Either can be built first. Research recommends cloud first (zero structural changes, lower blast
radius) then NIOS (requires the small `NiosScanManager` API extension).

### Phase 1: Cloud Per-Account Attribution Table

**Rationale:** Zero structural changes required. Touches only `pages.py` logic and one template.
Establishes the display patterns (formula derivation, resource-type breakdown, non-summable
footers) before touching the NIOS path. Delivers the higher-frequency use case — cloud scans are
the primary workflow for most SEs. All data is already computed; this is template work plus a
`Counter` loop.

**Delivers:** Cloud Summary tab per-account rows with inline formula derivation (DDI ÷ 25, IPs
÷ 13, Assets ÷ 3) and counted resource-type breakdown (VM/subnet/DNS zone counts). Clear
non-summable footer notes for token and IP columns.

**Features addressed:**
- Cloud per-account formula derivation (P1)
- Cloud per-account resource-type count breakdown (P1)
- Skipped vs. counted split per account (P1)
- Grand total reconciliation footnote (P1)

**Pitfalls to avoid:**
- A1: No summable token footer — explanatory note only
- A2: DDI footer is summable; IP footer is not — differentiate explicitly
- A3: Use provider-appropriate column label per row (Account / Subscription / Project)
- A4: Breakdown counts only `r.counted == True` resources; label clearly

**Build steps:**
1. Add `_count_resource_types()` helper to `pages.py`
2. Extend `per_account_details` in `_compute_summary()` with `resource_type_breakdown`
3. Update `pages/summary.html` — formula derivation cells + resource-type breakdown + footer notes
4. Verify: run cloud scan, confirm Summary tab formula derivations are correct and hero token total matches the table's grand total note

### Phase 2: NIOS Object Family Breakdown Table

**Rationale:** Requires extending `NiosScanManager` (one new field + setter + property + reset
clear) and one new call in `_run_nios_pipeline()`. Builds on patterns proven in Phase 1.
Completes the v1.4 milestone — the NIOS complete screen becomes fully self-contained for audit
without needing the XLS.

**Delivers:** NIOS complete screen family breakdown section: non-zero families only, DDI vs.
non-DDI flag, reason column for excluded families, HOST_OBJECT raw count note, scenario-
independence label. Ordered to match XLS Object Counters sheet.

**Features addressed:**
- NIOS object family breakdown table (P1)
- DDI-only family subtotal row (P1)
- Informational-only family reason text (P1)
- HOST_OBJECT expansion note (P2 — include in initial implementation given low cost)

**Pitfalls to avoid:**
- A6: Decide raw vs. DDI-adjusted count before implementation; label column to match
- A7: Section heading must state explicitly "applies to all scenarios — same object set counted under different formulas"
- A8: Follow exact `_scenario_suite` pattern for thread safety; update `reset()` in same commit as field addition

**Build steps:**
1. Add `_families_found` field + property + `set_families_found()` + `reset()` clear to `NiosScanManager`
2. Add `nios_manager.set_families_found(integrity.families_found)` in `_run_nios_pipeline()` after `inspect_backup()`
3. Add `_build_family_rows()` helper to `pages.py`; add `family_rows` to `tab_nios()` context
4. Add family breakdown section to `partials/nios/complete.html` with `{% if family_rows %}` guard
5. Verify: run NIOS analysis, confirm complete screen shows family breakdown; rerun analysis with a new backup, confirm `reset()` clears previous data

### Phase Ordering Rationale

- Cloud first because it has zero structural changes and proves display patterns before the `NiosScanManager` extension
- NIOS second because the manager API change is the only structural risk in the milestone
- No Phase 3 — both features are complete after Phase 2; P2/P3 polish items (sort order, collapsible rows, percentage annotations) are single-task additions not warranting separate phases

### Research Flags

**Both phases: skip research-phase.** Both features follow well-documented, established codebase
patterns. The research files contain complete implementation blueprints with exact file names,
function signatures, and code sketches. No niche domain knowledge, external API integration, or
new technology is involved.

- **Phase 1:** Standard pattern. `_compute_summary()` extension is fully specified in ARCHITECTURE.md with working code examples. Template pattern is identical to the existing `complete.html` member attribution scrollable table.
- **Phase 2:** Standard pattern. `NiosScanManager` extension follows the `_scenario_suite` model exactly. The one open decision (raw vs. DDI-adjusted counts for the family column) is a design choice to make at planning time, not a research gap.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All findings from direct codebase inspection; confirmed zero new libraries needed; no version conflicts |
| Features | HIGH | Derived from PROJECT.md milestone spec + direct source reads of all route handlers and templates; XLS report as reference for NIOS family breakdown confirmed |
| Architecture | HIGH | All integration points source-confirmed: `_compute_summary()` signature, `NiosScanManager` fields, `IntegrityReport.families_found` type, `_ALL_FAMILIES_ORDERED` list, `_DDI_FAMILIES` frozenset |
| Pitfalls | HIGH | v1.4 pitfalls derived from direct code reading; v1.1 pitfalls verified against CPython and FastAPI issue trackers (all resolved in shipped code) |

**Overall confidence:** HIGH

### Gaps to Address

- **Raw counts vs. DDI-adjusted counts for NIOS family breakdown (Pitfall A6):** This is the one
  open design decision in the milestone. ARCHITECTURE.md recommends using raw counts from
  `families_found` with a clear "Object Count" label and a HOST_OBJECT expansion note (simpler;
  no changes to `counter.py`). The alternative — extending `count_objects()` to return
  DDI-adjusted per-family counts — is more precise but adds scope by touching the counting core.
  Decide before Phase 2 begins; document the decision in a template comment and the section
  heading.

- **Cloud per-account attribution table placement in `summary.html`:** The Summary tab already
  has a per-provider summary table distinct from the per-account detail rows. Confirm during
  Phase 1 planning exactly where the formula derivation and resource-type breakdown appear — as
  new columns in the existing per-account table, or as a new expandable section per row. The
  research files describe both options; pick one before coding the template.

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)

- `src/cloud_usage/dashboard/routes/pages.py` — `_compute_summary()`, `tab_nios()`, `tab_summary()`, `tab_results()`
- `src/cloud_usage/dashboard/services/nios_manager.py` — `NiosScanManager` fields, `set_complete()` signature, `reset()`
- `src/cloud_usage/dashboard/routes/nios.py` — `_run_nios_pipeline()`: what is computed vs. discarded
- `src/cloud_usage/nios/schema.py` — `IntegrityReport.families_found: dict[str, int]`
- `src/cloud_usage/nios/output.py` — `_ALL_FAMILIES_ORDERED`, `_FAMILY_DISPLAY_NAMES`, `_UDDI_FLAG_REASON`
- `src/cloud_usage/nios/counter.py` — `CountResult`, `_DDI_FAMILIES`
- `src/cloud_usage/counting/token_calculator.py` — `DDI_PER_TOKEN = 25`, `IPS_PER_TOKEN = 13`, `ASSETS_PER_TOKEN = 3`
- `src/cloud_usage/schema/resource.py` — `CloudResource.account_id` (confirmed: no `account_name` field)
- `src/cloud_usage/dashboard/templates/partials/nios/complete.html` — scrollable-div + table pattern, member attribution table
- `src/cloud_usage/dashboard/templates/pages/summary.html` — existing `per_account_details` table structure
- `.planning/PROJECT.md` — v1.4 milestone definition, key decisions, out-of-scope items, Python 3.9+ constraint

### Secondary (HIGH confidence — issue trackers, used for v1.1 pitfall validation)

- CPython issue #102055 — ElementTree iterparse memory non-release (v1.1 pitfall, resolved in shipped code)
- FastAPI discussion #10936 — UploadFile closed before background task (v1.1 pitfall, resolved in shipped code)
- FastAPI issue #5777 — SpooledTemporaryFile spool limit (v1.1 pitfall, resolved in shipped code)
- `do_not_commit/CLAUDE.md` — ZF reference backup validated numbers (v1.1 verification data)

---

*Research completed: 2026-03-03*
*Ready for roadmap: yes*
