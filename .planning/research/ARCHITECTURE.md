# Architecture Research

**Domain:** FastAPI + HTMX dashboard — integration of cloud per-account attribution tables and NIOS object family breakdown (v1.4 Audit Depth)
**Researched:** 2026-03-03
**Confidence:** HIGH — all findings derived from direct source reading of the production codebase

---

## Supersedes

This document replaces the v1.1 NIOS Grid Analysis integration architecture (2026-02-28). The v1.1 architecture is fully shipped. This document covers only the v1.4 incremental changes.

---

## Context: What v1.4 Adds

Two new display features for the existing dashboard, both audit-depth additions:

1. **Cloud per-account attribution table** — per-account rows showing DDI / IP / Asset counts with inline formula derivation (DDI ÷ 25 = X.X, IPs ÷ 13 = X.X, Assets ÷ 3 = X.X) and resource type breakdown, in the cloud scan results UI.
2. **NIOS object family breakdown table** — per-family raw object counts (non-zero families only, ordered to match XLS Object Counters sheet), in the NIOS complete screen.

---

## System Overview (Current State)

```
Browser (HTMX + PicoCSS + vanilla JS)
    │
    │  GET /tab/nios               GET /tab/results or /tab/summary
    │  SSE /api/sse/nios           SSE /api/sse/scan
    │
    ▼
FastAPI (routes/)
    ├── pages.py       — full tab renders (/tab/*)
    ├── partials.py    — HTMX fragment swaps (/partials/*)
    ├── nios.py        — NIOS wizard + SSE + progress (/nios/*, /api/sse/nios, /api/nios/*)
    ├── scan.py        — cloud wizard + scan lifecycle (/wizard/*, /api/scan/*)
    ├── sse.py         — cloud SSE (/api/sse/scan)
    └── download.py    — file download (/download/*)

app.state (singleton managers, all thread-safe)
    ├── scan_manager   (ScanManager)
    │     ├── _state: ScanState
    │     ├── _resources: list[CloudResource]     ← cloud scan results live here
    │     ├── _errors: list
    │     ├── _output_paths: dict[str, str]
    │     └── _progress_data: dict                ← set via monkey-patch in _run_scan_pipeline
    │
    ├── nios_manager   (NiosScanManager)
    │     ├── _state: NiosState
    │     ├── _upload_path: str | None
    │     ├── _original_filename: str | None
    │     ├── _output_path: str | None
    │     ├── _error: str | None
    │     ├── _scenario_suite: ScenarioSuite | None   ← NIOS results live here
    │     └── _current_progress: dict
    │
    ├── event_bridge                — cloud SSE events
    └── nios_event_bridge           — NIOS SSE events (SC-5 isolated)

Business Logic (cloud path)
    ├── counting/token_calculator.py
    │     calculate_account_tokens(resources, dedup_ip_count)
    │       → {ddi_count, ip_count, asset_count, ddi_tokens, ip_tokens, asset_tokens, total_tokens}
    └── counting/ip_counter.py
          deduplicate_ips_per_vpc(resources) → {per_account: {acct_id: int}}

Business Logic (NIOS path)
    ├── nios/parser/   — parse_backup() → Iterator[NiosObject]
    ├── nios/counter.py
    │     count_objects() → CountResult
    │       CountResult.member_counts: list[MemberCounts]   (per-member DDI/IP/lease)
    │       CountResult.grid_counts: MemberCounts           (grid-level aggregate)
    │       NOTE: NO per-family breakdown in CountResult
    ├── nios/scenarios.py
    │     compute_scenarios() → ScenarioSuite
    │       ScenarioSuite holds scenario totals + member_attribution
    │       NOTE: NO per-family breakdown in ScenarioSuite
    └── nios/output.py
          write_nios_xlsx_report() — uses IntegrityReport.families_found for Object Counters sheet
          _ALL_FAMILIES_ORDERED: list[str]  — 26 families in display order
          _FAMILY_DISPLAY_NAMES: dict[str, str]  — human-readable names

    nios/schema.py
          IntegrityReport.families_found: dict[str, int]   ← THE family count source
          NiosFamily — 26 string constants

    nios/counter.py
          _DDI_FAMILIES: frozenset[str]   — families that contribute to DDI count
```

---

## Feature 1: Cloud Per-Account Attribution Table

### Where the Data Lives Now

The data is **already fully computed** at scan time. `_run_scan_pipeline()` in `routes/scan.py` (lines 311-323) produces:

```python
account_summaries: dict[str, dict]
# acct_id -> {ddi_count, ip_count, asset_count, ddi_tokens, ip_tokens, asset_tokens, total_tokens}
```

`pages.py:_compute_summary()` recomputes this same data on every tab render from `scan_manager.resources` (the resource list is the source of truth, not a cached aggregate). It already builds `per_account_details`:

```python
per_account_details.append({
    "account_id": account_id,
    "provider": account_provider[account_id],   # "aws" | "azure" | "gcp"
    "ddi_count": result["ddi_count"],
    "ip_count": result["ip_count"],
    "asset_count": result["asset_count"],
    "total_tokens": result["total_tokens"],      # only total — sub-totals dropped here
})
```

This list is passed to `pages/summary.html` which already renders a basic per-account table. The `results.html` (Results tab) receives this dict too but does not render the per-account section.

### What Is Missing for v1.4

**Gap 1 — Sub-totals dropped.** `_compute_summary()` keeps only `total_tokens` from `calculate_account_tokens()`. For inline formula cards (DDI ÷ 25 = X.X, IPs ÷ 13 = X.X), the template needs `ddi_tokens` and `ip_tokens` individually — or it can compute `ddi_count / 25` itself since divisors are template constants per project convention.

Given the established project decision that formula divisors are hardcoded in templates, **sub-totals do not need to be passed from Python** — the template computes `ddi_count / 25` inline. Only the raw counts (already in `per_account_details`) are needed.

**Gap 2 — Resource type breakdown missing.** The requirement includes "resource type breakdown" per account (e.g., vm=5, subnet=3). This is not computed or stored anywhere currently. It requires iterating `scan_manager.resources` grouped by account and tallying `r.resource_type` for counted resources.

### Integration Path: Cloud Attribution

**Modify `_compute_summary()` in `pages.py`** — add `resource_type_breakdown` to each `per_account_details` entry. The raw counts are already present; only the resource type tally is new.

```python
# Helper to add inside pages.py
def _count_resource_types(resources: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in resources:
        if r.counted:
            counts[r.resource_type] = counts.get(r.resource_type, 0) + 1
    return dict(sorted(counts.items()))

# In _compute_summary(), per-account loop:
per_account_details.append({
    "account_id": account_id,
    "provider": account_provider[account_id],
    "ddi_count": result["ddi_count"],
    "ip_count": result["ip_count"],
    "asset_count": result["asset_count"],
    "total_tokens": result["total_tokens"],
    "resource_type_breakdown": _count_resource_types(by_account[account_id]),  # ADD
})
```

**Modify `pages/summary.html`** — expand the per-account table to add:
- Inline formula derivation cells: `{{ acct.ddi_count }} DDI ÷ 25 = {{ "%.1f"|format(acct.ddi_count / 25) }}`
- Resource type breakdown (collapsed `<details>` or small pill badges per type)

**No new routes, no new SSE events, no new files.** Both `tab_summary` and `tab_results` already call `_compute_summary()` and pass the result to their templates.

### Data Flow: Cloud Attribution

```
scan_manager._resources: list[CloudResource]
    │
    └── pages.py:_compute_summary()               [MODIFY: add resource_type_breakdown]
            │
            ├── by_account dict        (group resources by account_id)
            ├── deduplicate_ips_per_vpc()
            ├── calculate_account_tokens()
            │     → {ddi_count, ip_count, asset_count, ddi_tokens, ip_tokens, asset_tokens, total_tokens}
            ├── _count_resource_types()            [ADD: new helper]
            │     → {resource_type: count, ...}
            └── per_account_details list
                    │
                    ├── pages/summary.html         [MODIFY: formula derivation + resource types]
                    └── pages/results.html         [no change — does not render per_account_details]
```

---

## Feature 2: NIOS Object Family Breakdown Table

### Where the Data Lives

The XLS "Object Counters" sheet (sheet 2 of the NIOS report) comes from `IntegrityReport.families_found` — a `dict[str, int]` mapping NiosFamily string constant to raw object count. This is returned by `inspect_backup()` in Step 1 of the NIOS pipeline.

**Critical gap: `NiosScanManager` does not store `IntegrityReport`.**

The pipeline (`_run_nios_pipeline()` in `nios.py`) calls `inspect_backup()` in Step 1 and passes the `IntegrityReport` directly to `write_nios_xlsx_report()` — but **does not persist it** to `nios_manager`. The only result stored on `nios_manager` is `scenario_suite` (a `ScenarioSuite`).

What `ScenarioSuite` contains (source-confirmed from `scenarios.py`):
- `current_grid`, `full_migration`, `hybrid_uddi` — scenario token totals (ScenarioResult)
- `member_attribution` — list of MemberScenarioRow
- Does NOT contain per-family raw counts

What `CountResult` contains (source-confirmed from `counter.py`):
- `member_counts` — per-member DDI/IP/lease counts (collapsed integers)
- `grid_counts` — global aggregate
- Does NOT expose per-family breakdowns — family counting is internal to `count_objects()`

**Conclusion:** `IntegrityReport.families_found` is the only existing data structure that holds raw per-family object counts. It must be stored in `NiosScanManager` to be available for template rendering.

### Integration Path: NIOS Family Breakdown

**Step 1 — Add `_integrity_report` to `NiosScanManager`**

```python
# services/nios_manager.py — additive changes only
class NiosScanManager:
    def __init__(self) -> None:
        ...
        self._integrity_report = None          # ADD field

    @property
    def integrity_report(self):               # ADD property
        with self._lock:
            return self._integrity_report

    def set_integrity_report(self, report) -> None:   # ADD setter
        with self._lock:
            self._integrity_report = report

    def reset(self) -> None:
        with self._lock:
            ...
            self._integrity_report = None     # ADD to reset
```

**Step 2 — Store it in `_run_nios_pipeline()`**

The `integrity` local already exists. One line addition after `inspect_backup()` returns:

```python
# routes/nios.py:_run_nios_pipeline() — Step 1 block
integrity = inspect_backup(backup_path)
nios_manager.set_integrity_report(integrity)   # ADD
```

**Step 3 — Add to `tab_nios()` context**

```python
# routes/pages.py:tab_nios()
context.update({
    ...
    "scenario_suite": scenario_suite,
    "integrity_report": nios_manager.integrity_report,   # ADD
})
```

**Step 4 — Render in `partials/nios/complete.html`**

Append a family breakdown section after the existing member attribution table. The template receives `integrity_report.families_found` (a plain dict) and filters it to non-zero families only.

For display order and display names, the template can use an inline ordered list or the Python route can pre-process into an ordered list. The cleaner approach is pre-processing in the route (or a helper), passing `family_rows: list[dict]` to the template rather than having the template import Python constants.

**Recommended approach:** Add a `_build_family_rows(integrity_report)` helper to `routes/pages.py` (or inline in `tab_nios()`) that produces:

```python
# Produced in tab_nios() or a helper:
family_rows = [
    {
        "name": family_name,           # NiosFamily constant string (e.g., "dns_record_a")
        "display_name": display_name,  # human-readable (e.g., "dns_record_a")
        "count": count,
        "is_ddi": family_name in _DDI_FAMILIES,
    }
    for family_name in _ALL_FAMILIES_ORDERED
    if integrity_report.families_found.get(family_name, 0) > 0
]
# Passed to template as context["family_rows"]
```

This keeps business logic (DDI classification, display order) in Python, not Jinja2.

**No new routes, no new SSE events.** The complete screen renders synchronously from `GET /tab/nios` (triggered by `nios_complete` SSE event + HTMX swap). All data is available at that point.

### Data Flow: NIOS Family Breakdown

```
nios/parser:inspect_backup(backup_path)
    → IntegrityReport.families_found: dict[str, int]
          │
          ├── routes/nios.py:_run_nios_pipeline()
          │     nios_manager.set_integrity_report(integrity)   [ADD]
          │
          └── NiosScanManager._integrity_report                [ADD field]
                    │
                    └── routes/pages.py:tab_nios()             [ADD to context]
                              │
                              ├── _build_family_rows(integrity_report)   [ADD helper]
                              │     filters non-zero families
                              │     orders by _ALL_FAMILIES_ORDERED (from nios/output.py)
                              │     tags is_ddi from _DDI_FAMILIES (from nios/counter.py)
                              │
                              └── pages/nios.html → partials/nios/complete.html
                                        family_rows: list[dict]
                                        → table: family_name | count | DDI? (yes/no)
```

---

## Component Boundary Summary

### Modified Components

| Component | Change | Risk |
|-----------|--------|------|
| `routes/pages.py` | Add `_count_resource_types()` helper; extend `per_account_details` entries in `_compute_summary()` with `resource_type_breakdown`; add `integrity_report` and `family_rows` to `tab_nios()` context; add `_build_family_rows()` helper | Low — all additive, no existing logic removed |
| `pages/summary.html` | Extend per-account table with formula derivation cells and resource type breakdown | Low — template-only, additive |
| `services/nios_manager.py` | Add `_integrity_report` field, `set_integrity_report()` setter, `integrity_report` property; clear in `reset()` | Low — additive, thread-safe pattern identical to existing fields |
| `routes/nios.py:_run_nios_pipeline()` | Add `nios_manager.set_integrity_report(integrity)` after Step 1 | Low — one line addition |
| `partials/nios/complete.html` | Add family breakdown section | Low — template-only, appended after existing content |

### New Components

None required. No new routes, no new services, no new files.

---

## Architectural Patterns to Follow

### Pattern 1: Additive Context Extension

**What:** Route handlers pass context dicts to templates. Templates use `{% if key %}` guards before rendering optional sections.

**When to use:** Adding display data to an existing render path without breaking other callers.

**Example from codebase:** `tab_nios()` calls `_get_tab_context()` and then `context.update({...})`. New keys in the update do not affect other tabs.

**Apply to:** Both features. Add keys to context dicts; templates check `{% if integrity_report %}` before rendering the family table.

### Pattern 2: Thread-Safe State Accumulation in Manager

**What:** `NiosScanManager` stores pipeline output using a single `threading.Lock`. All setters use `with self._lock`. Properties return copies where needed.

**When to use:** Any pipeline result that must outlive the background thread and be readable from async route handlers.

**Example from codebase:** `set_complete(output_path, scenario_suite)` — exactly this pattern.

**Apply to:** `set_integrity_report(report)` — same discipline, same lock.

### Pattern 3: Compute Display Aggregations on Render, Not at Scan Time

**What:** `_compute_summary()` recomputes token totals and per-account aggregates from raw `scan_manager.resources` on every tab render. `ScanManager` stores only the raw resource list, not derived display data.

**When to use:** Display aggregates that can be computed quickly from the raw data.

**Apply to:** `_count_resource_types()` — compute inside `_compute_summary()`. Do not store in `ScanManager`.

**Caveat on performance:** At 100+ accounts with thousands of resources, `_compute_summary()` recomputes on every tab load. The existing implementation already does this (it is the established pattern). `_count_resource_types()` adds one linear pass per account — same complexity as the existing token calculation loop.

### Pattern 4: Template-Owned Formula Constants

**What:** Formula divisors (DDI ÷ 25, IPs ÷ 13, Assets ÷ 3) are hardcoded in Jinja2 templates. This is an established project decision (PROJECT.md Key Decisions, entry: "Formula divisors hardcoded in template").

**When to use:** All inline formula derivation rendering.

**Apply to:** Cloud attribution formula cells. The template computes `ddi_count / 25` in Jinja2 arithmetic (`{{ "%.1f"|format(acct.ddi_count / 25) }}`). The backend passes only counts.

**Do not:** Pass `DDI_PER_TOKEN = 25` as a context variable or compute formatted strings in the route handler.

### Pattern 5: Business Logic Classification Stays in Python, Display in Templates

**What:** DDI family classification (`is_ddi`) and display ordering (`_ALL_FAMILIES_ORDERED`) are Python constants defined in `nios/counter.py` and `nios/output.py`. Templates should not import or re-implement these.

**When to use:** When template logic would require knowledge of domain constants.

**Apply to:** NIOS family breakdown — the `_build_family_rows()` helper in `pages.py` applies DDI classification and ordering before passing a clean list to the template.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Treating CountResult as the Family Breakdown Source

**What people might do:** Attempt to extract per-family counts from `ScenarioSuite` or `CountResult` rather than `IntegrityReport`.

**Why it's wrong:** `ScenarioSuite` has no family-level data. `CountResult.member_counts` exposes per-member DDI totals (collapsed integers). `CountResult.grid_counts.ddi_count` is the total grid-level DDI — not split by family. The counting logic in `count_objects()` accumulates family counts internally but does not expose them on the output struct.

**Do this instead:** Store `IntegrityReport` in `NiosScanManager`. `IntegrityReport.families_found` is the canonical source used by the XLS Object Counters sheet.

### Anti-Pattern 2: Async Partial Load for the Family Table

**What people might do:** Add an HTMX partial route (`GET /api/nios/family-breakdown`) that loads asynchronously after the complete screen renders.

**Why it's wrong:** The complete screen (`partials/nios/complete.html`) is not included until the pipeline finishes and HTMX swaps the tab from the `nios_complete` SSE event. All data is available at render time. An async partial adds round-trip latency and complexity with no benefit.

**Do this instead:** Include the family breakdown synchronously in `complete.html`. It is a static read from `IntegrityReport.families_found` stored in `nios_manager`.

### Anti-Pattern 3: Computing Resource-Type Breakdown at Scan Time

**What people might do:** Compute `resource_type_breakdown` inside `_run_scan_pipeline()` and store it in `ScanManager`.

**Why it's wrong:** Breaks the established pattern. `ScanManager` stores raw `_resources` and `_output_paths` only. All display aggregations are computed on render in `_compute_summary()`. Adding scan-time aggregations to `ScanManager` creates a split model where some display data is pre-computed and some is computed on render.

**Do this instead:** Compute `resource_type_breakdown` inside `_compute_summary()` alongside the other per-account aggregates.

### Anti-Pattern 4: Inline Formula Computation in Python Route Handlers

**What people might do:** Pre-compute formatted strings like `f"{ddi_count} ÷ 25 = {ddi_count/25:.1f}"` in the route handler and pass them as context strings.

**Why it's wrong:** Violates template-owns-display-logic. Hard to maintain. Mixes concerns. Inconsistent with how the existing NIOS formula cards work (`complete.html` does all arithmetic inline in Jinja2).

**Do this instead:** Pass raw integers; let Jinja2 format: `{{ "{:,}".format(acct.ddi_count) }} ÷ 25 = {{ "%.1f"|format(acct.ddi_count / 25) }}`.

### Anti-Pattern 5: New SSE Events for v1.4 Features

**What people might do:** Emit a new SSE event (e.g., `nios_family_ready`) after the pipeline completes to trigger an HTMX swap for the family table.

**Why it's wrong:** The existing `nios_complete` event already triggers `GET /tab/nios`, which renders the complete screen including all its sections. There is nothing to trigger separately.

**Do this instead:** Include the family breakdown in `complete.html` as a static section. It renders as part of the tab reload on `nios_complete`.

---

## Build Order and Dependencies

The two features are independent of each other (cloud and NIOS state share nothing). Either can be built first.

**Recommended order:**

1. **Cloud attribution table** — zero structural changes needed (no new manager fields, no new pipeline calls). Touches only `pages.py` logic and one template. Lower risk; establishes patterns before touching NIOS.

2. **NIOS family breakdown** — requires the `NiosScanManager` extension (new field + setter + property) and the `_run_nios_pipeline()` call site change. Build second.

### Step-by-step within each feature

**Cloud attribution:**
```
Step 1: Add _count_resource_types() helper to pages.py
Step 2: Extend per_account_details in _compute_summary() with resource_type_breakdown
Step 3: Update pages/summary.html — add formula derivation row + resource type breakdown
Step 4: Verify: run cloud scan, check Summary tab shows formula derivation and resource types
```

**NIOS family breakdown:**
```
Step 1: Add _integrity_report field + set_integrity_report() + integrity_report property + reset() clear to NiosScanManager
Step 2: Add nios_manager.set_integrity_report(integrity) call in _run_nios_pipeline() after inspect_backup
Step 3: Add _build_family_rows() helper to pages.py; add integrity_report + family_rows to tab_nios() context
Step 4: Add family breakdown section to partials/nios/complete.html
Step 5: Verify: run NIOS analysis, check complete screen shows family breakdown table
```

---

## Integration Points with Existing Routes/Templates

| Existing Component | v1.4 Touch | Change Type |
|-------------------|------------|-------------|
| `routes/pages.py:_compute_summary()` | Cloud attribution | Modify — add `_count_resource_types()` helper call per account |
| `routes/pages.py:tab_summary()` | Inherits automatically | No change — calls `_compute_summary()` |
| `routes/pages.py:tab_results()` | Inherits automatically | No change — calls `_compute_summary()` |
| `routes/pages.py:tab_nios()` | NIOS family | Modify — add `integrity_report` + `family_rows` to context |
| `pages/summary.html` | Cloud attribution | Modify — expand per-account table with formula + resource types |
| `partials/nios/complete.html` | NIOS family | Modify — append family breakdown section |
| `services/nios_manager.py` | NIOS family | Modify — add field + property + setter + reset clear |
| `routes/nios.py:_run_nios_pipeline()` | NIOS family | Modify — one line: call set_integrity_report after inspect_backup |

**No new files. No new routes. No new SSE events. No new services.**

---

## Scaling Considerations

| Concern | Current scale | v1.4 impact |
|---------|---------------|-------------|
| `_count_resource_types()` per account | O(resources-per-account) | Same complexity as existing token loop inside `_compute_summary()`. Negligible extra cost. |
| `IntegrityReport.families_found` dict | At most 26 keys | Zero cost. Written once at analysis start; stored as one dict reference. |
| Memory for `_integrity_report` in manager | One small dict | Negligible — replaces `None`. |
| `_build_family_rows()` filter + sort | At most 26 items | Instantaneous. |

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Cloud per-account data already computed | HIGH | Source-read `pages.py:_compute_summary()` + `counting/token_calculator.py:calculate_account_tokens()` return shape confirmed |
| `resource_type` field on CloudResource | HIGH | Source-read `schema/resource.py` — `resource_type: str` field confirmed |
| `resource_type_breakdown` not currently computed | HIGH | Source-read `_compute_summary()` — no such tally exists |
| `IntegrityReport` not stored in `NiosScanManager` | HIGH | Source-read `services/nios_manager.py` — confirmed no `_integrity_report` field |
| `families_found` as family breakdown source | HIGH | Source-read `nios/output.py` — Object Counters sheet uses `integrity_report.families_found` |
| `_ALL_FAMILIES_ORDERED` available for ordering | HIGH | Source-read `nios/output.py` lines 63-91 — confirmed list exists |
| `_DDI_FAMILIES` available for DDI tagging | HIGH | Source-read `nios/counter.py` lines 96-119 — confirmed frozenset exists |
| No new routes needed | HIGH | Complete screen renders synchronously on full tab GET; cloud summary already renders per-account |
| Formula constants belong in templates | HIGH | PROJECT.md Key Decisions entry confirmed; `complete.html` uses inline Jinja2 arithmetic for existing formula cards |

---

## Sources

- Direct source reads: `services/nios_manager.py`, `services/scan_manager.py`
- Direct source reads: `routes/nios.py` (`_run_nios_pipeline()` lines 97-242)
- Direct source reads: `routes/scan.py` (`_run_scan_pipeline()` lines 198-394)
- Direct source reads: `routes/pages.py` (`_compute_summary()` lines 71-159, `tab_nios()` lines 288-328)
- Direct source reads: `routes/partials.py`
- Direct source reads: `nios/counter.py` (`CountResult`, `MemberCounts`, `_DDI_FAMILIES`)
- Direct source reads: `nios/scenarios.py` (`ScenarioSuite` fields)
- Direct source reads: `nios/output.py` (`_ALL_FAMILIES_ORDERED`, `_FAMILY_DISPLAY_NAMES`, `write_nios_xlsx_report()` signature)
- Direct source reads: `nios/schema.py` (`IntegrityReport.families_found`, `NiosFamily`)
- Direct source reads: `counting/token_calculator.py` (`calculate_account_tokens` return shape)
- Direct source reads: `schema/resource.py` (`CloudResource` fields)
- Direct source reads: `templates/partials/nios/complete.html`, `templates/pages/nios.html`, `templates/pages/summary.html`, `templates/partials/summary_cards.html`
- Project context: `.planning/PROJECT.md` (v1.4 requirements, key decisions)

---

*Architecture research for: Infoblox Universal DDI Cloud Usage Estimator — v1.4 Audit Depth*
*Researched: 2026-03-03*
