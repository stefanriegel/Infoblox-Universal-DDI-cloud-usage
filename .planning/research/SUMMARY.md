# Project Research Summary

**Project:** Infoblox Universal DDI Cloud Usage Estimator — v1.8 Dashboard Analytics
**Domain:** FastAPI + HTMX local audit tool — incremental milestone on a fully shipped v1.7 codebase
**Researched:** 2026-03-07
**Confidence:** HIGH

---

## Executive Summary

This is a v1.8 milestone adding three dashboard analytics features to an already-operational tool: an AD Dashboard Tab (connecting the existing Microsoft AD CLI analysis to a browser UI), a Top 5 DNS Zones panel (per-source zone attribution), and CLOUD-EXT-01 (human-readable display names and verification for the 26 new v1.7 DDI types in the per-account attribution table). All three features are purely additive — they extend existing, proven patterns without introducing new libraries, new architectural concepts, or new data pipelines. The work is almost entirely routing, state management, and template work within the existing FastAPI + HTMX + Jinja2 stack.

The recommended approach is to follow the NIOS Analysis tab as the direct implementation model for the AD tab. Every pattern needed — Manager/EventBridge pair, SSE progress streaming, state-machine tab pages, background thread wiring via `run_in_executor` — exists in the NIOS tab and has been validated in production. The AD tab is a targeted adaptation, not a new design. Top 5 DNS Zones is a pure aggregation/display layer over data already in memory after a scan. CLOUD-EXT-01 is largely complete at the data layer; the deliverable is a display-name mapping dict and template annotation.

The primary risks are implementation-time copy-paste errors: sharing the AD EventBridge with cloud or NIOS SSE (silently breaks progress), missing the SSE race-condition guard (AD tab hangs on fast forests), omitting `ad_state` from `_get_tab_context()` (breaks all tabs with a Jinja2 UndefinedError), and logging `AdOptions` with a plaintext password. All four risks have known prevention strategies and explicit test conditions defined in the research.

---

## Key Findings

### Recommended Stack

No new libraries are required for v1.8. All three features are routing, state management, template, and data aggregation work that sits entirely within the existing stack: FastAPI, Jinja2, HTMX (vendored), PicoCSS (vendored), janus, and Python stdlib (`collections.Counter`, `threading.Lock`). The `pywinrm` dependency for AD is already operational in the existing CLI provider. The `xlsxwriter` dependency for XLS output is already in use. No version bumps. No new packages to install.

**Core technologies:**
- **FastAPI >= 0.115.0**: New routes `/tab/ad`, `/ad/run`, `/api/sse/ad`, `/api/ad/progress` — same route + StreamingResponse pattern already used for NIOS
- **Jinja2 >= 3.1.0**: New AD tab templates and DNS zones panel — template-only additions using existing `{% include %}` / `{% for %}` / `{% if %}` patterns
- **HTMX (vendored 1.9.x)**: AD wizard step swaps, AD SSE subscription — `hx-ext="sse"` / `sse-connect` / `sse-swap` pattern already used in NIOS tab; copy verbatim
- **janus >= 2.0.0**: Third `EventBridge()` instance (`ad_event_bridge`) registered on `app.state` — the `EventBridge` class is already generic and reusable
- **stdlib `collections.Counter`**: Top 5 DNS Zones aggregation — zero new imports
- **stdlib `threading.Lock`**: `AdScanManager` thread safety — same pattern as `NiosScanManager`

### Expected Features

**Must have (table stakes — v1.8 launch):**
- AD connection wizard (host, port, auth mode, credentials, services scope, autodiscovery toggle) — every other provider has a dashboard entry point; AD CLI has been production since v1.7 with no UI
- AD SSE progress + results screen with token formula derivation, download CTA, error state + retry — without SSE the UI blocks on a 30–120s synchronous WinRM analysis
- Top 5 Cloud DNS Zones panel on Summary tab — answers "which zones cost the most?" for cloud customers; data is already in `scan_manager.resources`
- Top 5 AD DNS Zones panel on AD complete screen — AD forests commonly have dozens of zones; top-5 view adds immediate pre-sales value; data directly available from `run_ad_analysis()` output
- CLOUD-EXT-01 human-readable display names and validation — v1.7 shipped 26 new DDI types that engineers now cite by name; raw type strings (`aws-resolver-rule-association`) degrade the customer-facing summary table

**Should have (competitive differentiators):**
- Token contribution breakdown by AD service type (DNS tokens / DHCP tokens / User tokens) on AD complete screen — low-complexity sub-total addition that eliminates "why does DNS dominate?" follow-up questions
- DDI formula annotation per type in the collapsible breakdown rows (`count ÷ 25 = X tokens`) — already supported by CLOUD-EXT-01 architecture; template-only change

**Defer to v1.9+:**
- Top 5 DNS Zones — NIOS scope: blocked by pipeline gap (`CountResult` has no per-zone accumulator); adding it risks regression on the most validated part of the codebase
- Per-DC connection status during AD autodiscovery: high complexity; requires per-DC SSE events and collector refactoring; not needed for core AD dashboard
- Functional grouping of v1.7 DDI types within the breakdown (Route53 Resolver vs. IPAM vs. Networking): display-name fix already addresses readability in v1.8
- Cross-scope zone overlap detection (same zone in Cloud + AD): high complexity; no immediate pre-sales demand

### Architecture Approach

v1.8 adds a third Manager/EventBridge pair (`AdScanManager` + `ad_event_bridge`) following the exact pattern established by cloud (`ScanManager` + `event_bridge`) and NIOS (`NiosScanManager` + `nios_event_bridge`). The AD tab page is a state-machine template branching on `ad_state` (idle/running/complete/error), identical to `pages/nios.html`. The background pipeline (`_run_ad_pipeline`) is inlined — calling `MicrosoftAdCollector` directly rather than `run_ad_analysis()` — to enable per-DC SSE progress events, the same design decision made for `_run_nios_pipeline()`. Top 5 DNS Zones and CLOUD-EXT-01 require no pipeline changes; they are pure route-handler helpers and template additions.

**Major components:**
1. **`services/ad_manager.py` (new)** — `AdScanManager` with `AdState` enum, `threading.Lock`, `_resources`/`_errors`/`_output_path` fields; mirrors `NiosScanManager` with NIOS-specific fields removed
2. **`routes/ad.py` (new)** — `POST /ad/run`, `GET /api/sse/ad`, `GET /api/ad/progress`, `GET /tab/ad`; AD background pipeline inlined as `_run_ad_pipeline()` called via `loop.run_in_executor`
3. **`routes/pages.py` (modified)** — Add `tab_ad()` route; add `_compute_top_dns_zones()` helper; extend `_get_tab_context()` with `ad_state`; extend `tab_summary()` and `tab_ad()` with top-zone data
4. **`app.py` (modified)** — Register `ad_event_bridge` + `ad_manager` in lifespan; include `ad_router`
5. **AD templates (new)** — `pages/ad.html`, `partials/ad/step1_connect.html`, `step2_run.html`, `progress_display.html`, `complete.html`; mirror NIOS template directory structure
6. **`templates/partials/tab_bar.html` (modified)** — Fifth tab entry with AD state badge
7. **`templates/pages/summary.html` (modified)** — Top 5 Cloud DNS Zones panel + DDI formula annotation in breakdown rows

### Critical Pitfalls

1. **AD EventBridge shared with cloud or NIOS SSE** — Create a third independent `EventBridge()` instance (`app.state.ad_event_bridge`); verify with a test that cloud `emit_done()` does not close the AD SSE subscriber; this is an easy copy-paste error in `app.py` with no runtime error — the stream silently closes at the wrong moment
2. **SSE race condition: pipeline finishes before browser opens SSE connection** — In `sse_ad()`, check `ad_manager.state in (COMPLETE, ERROR)` before subscribing; emit `ad_complete` immediately if already done; the fix is 4 lines copied from `sse_nios()` lines 384–387
3. **`_get_tab_context()` missing `ad_state` breaks ALL tabs** — Every tab route calls this shared function; adding `ad_state` to `tab_bar.html` without updating the backend throws Jinja2 `UndefinedError` on every tab; update `_get_tab_context()` first, before adding the tab link to the template
4. **AD credentials logged via `AdOptions.__repr__`** — Python dataclass default repr includes all fields including `password`; add `__repr__` override masking the password field; never store credentials in `AdScanManager` beyond the pipeline run
5. **Top 5 DNS Zones ranked by zone-level DDI contribution produces a meaningless tied list** — Every zone contributes exactly 1 DDI; the correct metric is record count per zone (records scale with DNS footprint); rank zones by DNS record count, not by zone object DDI

---

## Implications for Roadmap

Based on research, the suggested phase structure follows the dependency graph from ARCHITECTURE.md: AD foundation first (no dependencies), then AD routes + templates (depends on foundation), then the standalone CLOUD-EXT-01 enhancement, then the Top 5 DNS Zones panels (AD scope depends on AD tab being complete).

### Phase 1: AD Foundation — Manager, EventBridge, App Wiring

**Rationale:** All AD UI work depends on `AdScanManager` and `ad_event_bridge` existing on `app.state`. This phase has no external dependencies and eliminates the highest-risk integration errors (shared EventBridge, missing `ad_state` in shared context) before any templates are written. Gets the tab link rendering in idle state immediately.
**Delivers:** `services/ad_manager.py` fully defined; `app.py` lifespan registers `ad_event_bridge` + `ad_manager`; `_get_tab_context()` extended with `ad_state`; AD tab link added to `tab_bar.html` (badge renders from state — idle on first load)
**Addresses:** AD-09 foundation, AD-10 prerequisite
**Avoids:** Pitfall 1 (shared EventBridge), Pitfall 8 (tab bar UndefinedError), Pitfall 4 (NIOS-specific fields in manager)

### Phase 2: AD Routes and Templates — Full Wizard + SSE + Results

**Rationale:** With the foundation in place, this phase wires the complete AD user flow: form submission, background pipeline dispatch, SSE progress, completion screen. The NIOS tab is the direct model — every component has a documented AD counterpart.
**Delivers:** `routes/ad.py` with all 4 routes; `_run_ad_pipeline()` inlined with per-DC progress; all AD templates (`pages/ad.html`, 4 partials); AD results screen with DNS zone, DHCP scope, AD user counts, token formula, download CTA, error + retry state
**Uses:** `MicrosoftAdCollector` directly (not `run_ad_analysis()`) for per-DC SSE progress granularity; `loop.run_in_executor` (not `asyncio.to_thread`) for Python 3.9 compatibility
**Avoids:** Pitfall 2 (SSE race guard), Pitfall 3 (SSE keepalive via `EventBridge.subscribe()`), Pitfall 9 (credentials not stored/logged)

### Phase 3: CLOUD-EXT-01 — v1.7 DDI Type Display Names

**Rationale:** Fully independent of AD tab work; data path is already correct. The deliverable is a static dict and template annotation. Can be developed in parallel with Phase 2 or immediately after.
**Delivers:** `DDI_TYPE_DISPLAY_NAMES` dict in `categorizer.py` mapping all 26 v1.7 type strings to human labels; DDI formula annotation (`count ÷ 25 = X tokens`) added to breakdown rows in `summary.html`; validation fixture confirming v1.7 types appear in breakdown for accounts that have them
**Avoids:** Pitfall 7 (attribution table unreadable with 20+ raw type strings)

### Phase 4: Top 5 DNS Zones Panels

**Rationale:** Cloud and AD zone panels depend on AD tab completion (Phase 2) for the AD scope. The zone computation is a linear in-memory pass — no new pipeline needed. NIOS scope deferred to v1.9 due to pipeline complexity and regression risk.
**Delivers:** `_compute_top_dns_zones(resources)` helper in `pages.py`; Top 5 Cloud DNS Zones panel in `summary.html` (ranked by record count); Top 5 AD DNS Zones panel in `partials/ad/complete.html`; NIOS scope shows zone count only ("N DNS zones") without per-zone breakdown
**Avoids:** Pitfall 5 (source-aware zone name extraction), Pitfall 6 (ranking by record count not zone DDI)

### Phase Ordering Rationale

- Phase 1 before Phase 2: `app.state` objects must exist before routes can reference them; `_get_tab_context()` must include `ad_state` before any template references it
- Phase 3 is independent: no dependency on AD tab; parallelizable if capacity allows
- Phase 4 after Phase 2: AD zones panel reads `ad_manager.resources` which only exists after the AD tab pipeline is complete; Cloud zones panel is independent but benefits from being implemented in the same pass
- NIOS per-zone deferred: `CountResult` has no per-zone accumulator; adding it risks regressions on the ZF Friedrichshafen reference run; not worth the scope in v1.8

### Research Flags

Phases with well-documented patterns — skip research-phase, all patterns exist in codebase:
- **Phase 1:** Direct mirror of NIOS foundation; all patterns confirmed via source reads with exact file/line citations
- **Phase 2:** Direct mirror of NIOS tab; all integration points documented in ARCHITECTURE.md with specific file names, method signatures, and code sketches
- **Phase 3:** Self-contained dict + template change; no external dependencies
- **Phase 4:** In-memory aggregation using stdlib; zone name fields confirmed in source reads for cloud (Route53 confirmed at `route53.py` line 121) and AD (`runner.py` line 277)

Phases needing implementation-time verification (not full research — empirical check at start of phase):
- **Phase 2:** Verify `MicrosoftAdCollector` API surface for direct calling (currently called only via `run_ad_analysis()`); confirm per-DC collect method signature before writing `_run_ad_pipeline()`
- **Phase 4 (Cloud scope):** Verify Azure and GCP DNS zone name field in `resource.details` for `azure-dns-zone` and `gcp-dns-zone` collectors; confirmed for Route53, not yet verified for Azure/GCP

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Direct source inspection of all affected files; no new dependencies; all stack decisions confirmed against `requirements.txt` and existing route code |
| Features | HIGH | Grounded in existing codebase; features derived from direct inspection of `runner.py`, `options.py`, `routes/nios.py`, `routes/pages.py`; no external documentation needed |
| Architecture | HIGH | All patterns confirmed via source reads with specific file + line citations; component boundaries precisely mapped; no inferred dependencies |
| Pitfalls | HIGH | Every pitfall derived from direct code inspection; race condition guard located at specific line (`sse_nios()` lines 384–387); UndefinedError root cause confirmed in `_get_tab_context()` |

**Overall confidence:** HIGH

### Gaps to Address

- **Azure/GCP DNS zone name field in `resource.details`**: Confirmed for Route53 (`route53.py` line 121) and AD (`runner.py` line 277). For Azure and GCP zone collectors, read the collector files before writing `_compute_top_dns_zones()` in Phase 4. If the field name differs from `"zone"`, the extraction will silently produce empty zone panels for Azure/GCP scans.
- **`MicrosoftAdCollector` per-DC collection API**: The recommended pipeline design calls `MicrosoftAdCollector` directly for per-DC progress events. The exact per-DC collect method signature should be verified before writing `_run_ad_pipeline()` in Phase 2. If the collector does not expose a per-DC method, fall back to `run_ad_analysis()` with indeterminate progress (acceptable for v1.8 MVP).
- **NIOS zone FQDN key in `raw_attrs`**: The NIOS schema stores zone FQDNs in `NiosObject.raw_attrs`, likely under the key `"fqdn"`. This is inferred from standard NIOS property naming and has not been verified against a real backup. Relevant only if NIOS per-zone panel is prioritized — currently deferred to v1.9.

---

## Sources

### Primary (HIGH confidence — direct source inspection)
- `src/cloud_usage/dashboard/routes/nios.py` — NIOS tab pattern; SSE race guard at lines 384–387; SC-5 isolation
- `src/cloud_usage/dashboard/routes/pages.py` — `_compute_summary()` attribution table; `_get_tab_context()` shared context builder
- `src/cloud_usage/dashboard/services/nios_manager.py` — Manager pattern to replicate for `AdScanManager`
- `src/cloud_usage/dashboard/services/event_bridge.py` — EventBridge generic reusability; keepalive at line 86
- `src/cloud_usage/dashboard/app.py` — Lifespan pattern; two independent EventBridge instances confirmed
- `src/cloud_usage/providers/ad/runner.py` — `run_ad_analysis()` return shape; zone name at `_to_cloud_resources()` line 277
- `src/cloud_usage/providers/ad/options.py` — `AdOptions` fields; auth mode; services tuple
- `src/cloud_usage/counting/categorizer.py` — All 26 v1.7 DDI types in `DDI_TYPES`; no display names dict yet exists
- `src/cloud_usage/nios/counter.py` — `CountResult.per_family_ddi` is family-level; no per-zone accumulator
- `src/cloud_usage/providers/aws/collectors/route53.py` line 121 — `details["zone_name"]` confirmed for Route53 records
- `src/cloud_usage/dashboard/templates/pages/summary.html` — Attribution breakdown already renders `resource_type_breakdown`
- `src/cloud_usage/dashboard/templates/partials/tab_bar.html` — Four existing tabs; `nios_state` dependency pattern
- `.planning/PROJECT.md` — Python-only constraint; no-charts decision; SC-5; v1.8 feature list

### Secondary (MEDIUM confidence — inferred from codebase patterns)
- NIOS `raw_attrs["fqdn"]` for DNS zone FQDN — standard NIOS property naming; not verified against a live backup
- Azure/GCP DNS zone name field in `resource.details` — confirmed pattern for AWS Route53; inferred for Azure/GCP

---
*Research completed: 2026-03-07*
*Ready for roadmap: yes*
