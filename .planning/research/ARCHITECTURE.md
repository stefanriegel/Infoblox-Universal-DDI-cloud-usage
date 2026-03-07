# Architecture Research

**Domain:** v1.8 Dashboard Analytics — AD tab, Top 5 DNS Zones panels, CLOUD-EXT-01
**Researched:** 2026-03-07
**Confidence:** HIGH — all findings derived from direct source reading of the production codebase

---

## Supersedes

Replaces v1.4 architecture (2026-03-03). The v1.4 architecture is fully shipped. This document covers only the v1.8 incremental changes.

---

## Context: What v1.8 Adds

Three new display and interaction features layered onto the existing FastAPI + HTMX dashboard:

1. **AD Dashboard Tab** (AD-09, AD-10) — connection wizard, WinRM autodiscovery progress via SSE, results display
2. **Top 5 DNS Zones panel** per scope (NIOS, Cloud, AD) — top 5 zones by token contribution
3. **CLOUD-EXT-01** — per-account breakdown for v1.7 DDI types in the attribution table (already partially satisfied by existing breakdown; likely a verification + template annotation task)

---

## System Overview (Current State, Post-v1.7)

```
Browser (HTMX + PicoCSS + vanilla JS)
    │
    │  GET /tab/{progress,results,summary,nios}
    │  SSE /api/sse/scan     SSE /api/sse/nios
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
    ├── scan_manager       (ScanManager)       — cloud scan lifecycle + resources
    ├── nios_manager       (NiosScanManager)   — NIOS analysis lifecycle + scenario_suite + family_breakdown
    ├── event_bridge       (EventBridge)       — cloud SSE events
    └── nios_event_bridge  (EventBridge)       — NIOS SSE events (SC-5 isolated)

Background threads (via loop.run_in_executor)
    ├── _run_scan_pipeline()  — cloud discovery + counting + XLS write
    └── _run_nios_pipeline()  — NIOS parse + count + scenarios + XLS write

Providers
    ├── providers/ad/runner.py       — run_ad_analysis() → (resources, errors)
    ├── providers/ad/collector.py    — MicrosoftAdCollector.collect_all()
    └── providers/ad/options.py      — AdOptions frozen dataclass
```

---

## Feature 1: AD Dashboard Tab (AD-09 + AD-10)

### What Is Missing

`run_ad_analysis()` exists and returns `(list[CloudResource], list[str])`. The CLI wires it via `_run_ad_cli()`. **Nothing in the dashboard currently touches `providers/ad/`**. The full AD dashboard flow needs to be created from scratch, following the NIOS tab pattern precisely.

### Integration Path

The NIOS tab pattern (`nios_manager + nios_event_bridge + routes/nios.py + pages/nios.html + partials/nios/`) is the direct model. Every component has an AD counterpart.

**New service: `services/ad_manager.py`**

Mirror of `NiosScanManager`. Required fields beyond the NIOS pattern:
- `_resources: list` — the `CloudResource` list from `run_ad_analysis()` (not needed in NIOS since NIOS results live in `scenario_suite`)
- `_errors: list[str]` — per-DC error strings from `run_ad_analysis()`
- `_options: None` — explicitly NOT stored (see Anti-Patterns)

```
AdState enum: IDLE | RUNNING | COMPLETE | ERROR
AdScanManager fields: _state, _lock, _output_path, _error, _resources, _errors,
                      _current_progress {step, total, label, elapsed_seconds}
Methods: set_progress(step, total, label, elapsed_seconds)
         set_complete(output_path, resources, errors)
         set_error(error)
         can_start() / start() / reset()
```

**New route module: `routes/ad.py`**

```
POST /ad/run            — accept connection form, build AdOptions, dispatch pipeline
GET  /api/sse/ad        — stream AdEventBridge events
GET  /api/ad/progress   — return progress fragment (partials/ad/progress_display.html)
GET  /tab/ad            — full AD tab render (state-driven)
```

Note: Unlike NIOS (which has a separate upload step before run), AD is a single step: the connection form IS the "run" trigger. No separate "connect" + "run" split needed — the form POST at `/ad/run` validates the form, builds `AdOptions`, and dispatches the pipeline in one step.

**Modify `app.py` lifespan**

Register the AD pair:
```python
ad_event_bridge = EventBridge()
await ad_event_bridge.start()
app.state.ad_event_bridge = ad_event_bridge

ad_manager = AdScanManager()
app.state.ad_manager = ad_manager
```

Close in shutdown: `await ad_event_bridge.close()`

Register router: `app.include_router(ad_router)` in `create_app()`.

**Modify `routes/pages.py`**

- Add `GET /tab/ad` route (`tab_ad()`) — reads `ad_manager.state`, `ad_manager.resources`, `ad_manager.errors`, `ad_manager.output_path`; passes to `pages/ad.html`
- Modify `_get_tab_context()` — add `ad_state: ad_manager.state.value` to the returned dict (needed for tab bar badge)

**Modify `templates/partials/tab_bar.html`**

Add AD tab link + badge after the NIOS Analysis entry:
```html
<a hx-get="/tab/ad" hx-target="#tab-container" ...>
  Microsoft AD
  {% if ad_state == 'running' %}<span class="badge badge-warning">running...</span>
  {% elif ad_state == 'complete' %}<span class="badge badge-success">done</span>
  {% elif ad_state == 'error' %}<span class="badge badge-error">error</span>{% endif %}
</a>
```

### New Templates

| Template | Purpose | State Variables |
|----------|---------|-----------------|
| `pages/ad.html` | AD tab state machine | `ad_state`, `error`, `output_path`, `resources`, `errors` |
| `partials/ad/step1_connect.html` | Connection form | servers, auth_mode (kerberos/ntlm), credentials, autodiscover toggle, port, ssl |
| `partials/ad/step2_run.html` | SSE progress container | `ad_state` |
| `partials/ad/progress_display.html` | Rendered step fragment | `progress` dict (step, total, label, elapsed_seconds) |
| `partials/ad/complete.html` | Results: token totals + zone/DHCP/user counts + download | `resources`, `errors`, `output_path`, `download_filename` |

**`pages/ad.html` structure** (mirrors `pages/nios.html`):
```
{% if ad_state == 'running' %}
  SSE-connected progress container (identical pattern to nios.html running branch)
  sse-connect="/api/sse/ad"
  hx-trigger="sse:ad_progress" → hx-get="/api/ad/progress"
  hx-trigger="sse:ad_complete" → hx-get="/tab/ad"
{% elif ad_state == 'complete' %}
  {% include "partials/ad/complete.html" %}
{% elif ad_state == 'error' %}
  error article + step1_connect.html for re-try
{% else %}   {# IDLE #}
  <div id="ad-wizard">
    {% include "partials/ad/step1_connect.html" %}
  </div>
{% endif %}
```

**`partials/ad/step2_run.html` SSE wiring** (exact pattern from `partials/nios/step2_run.html`):
```html
<div hx-ext="sse" sse-connect="/api/sse/ad">
  <div id="ad-progress-area"
       hx-trigger="sse:ad_progress"
       hx-get="/api/ad/progress"
       hx-target="#ad-progress-area"
       hx-swap="innerHTML">
    <progress></progress>
    <p>Starting AD collection…</p>
  </div>
  <div sse-swap="ad_complete" hx-swap="none"
       hx-trigger="sse:ad_complete"
       hx-get="/tab/ad" hx-target="#tab-container">
  </div>
</div>
```

### Background Pipeline: `_run_ad_pipeline()`

Lives in `routes/ad.py`. Called via `loop.run_in_executor(None, _run_ad_pipeline, ad_manager, options, ad_event_bridge)`.

**Progress step structure:**

AD collection has variable step count depending on autodiscovery. Use dynamic `total`:
- Step 1: "Connecting to {server}" (total = 2 if no autodiscover, else TBD after discovery)
- Step 2 (autodiscover): "Discovering Domain Controllers" → updates `total` to `2 + dc_count + 1`
- Step 3..N: "Collecting from DC {hostname} ({k}/{dc_count})"
- Step N+1: "Aggregating results"

**Key integration:** `run_ad_analysis()` calls `MicrosoftAdCollector.collect_all()` internally and does not provide per-DC progress callbacks. Options:

**Option A (recommended):** Inline the pipeline in `_run_ad_pipeline()` (do not call `run_ad_analysis()`). Mirror the pattern from `_run_nios_pipeline()` which inlines the NIOS pipeline rather than calling `run_nios_analysis()`. This allows progress emit between each DC.

**Option B:** Call `run_ad_analysis()` with a single pre/post progress step. Simpler code but no per-DC progress visibility.

For autodiscovery, Option A is required. For non-autodiscover mode, Option B is acceptable. Given the project's emphasis on progress transparency, Option A is recommended — call `MicrosoftAdCollector` directly and iterate DCs manually.

**Pipeline (Option A, inlined):**
```
1. ad_manager.set_progress(1, 2, "Connecting", elapsed)
   ad_event_bridge.emit("ad_progress", {...})
   Build AdOptions from stored options

2. (if autodiscover)
   ad_manager.set_progress(2, 3, "Discovering DCs", elapsed)
   ad_event_bridge.emit("ad_progress", {...})
   collector.autodiscover_servers()  → dc_list
   total = 2 + len(dc_list) + 1

3..N. Per-DC collection:
   for i, dc in enumerate(servers):
       ad_manager.set_progress(2 + i, total, f"Collecting {dc} ({i+1}/{len(servers)})", elapsed)
       ad_event_bridge.emit("ad_progress", {...})
       result = collector.collect_server(dc)
       server_results.append(result)

N+1. Aggregating:
   ad_manager.set_progress(total - 1, total, "Aggregating results", elapsed)
   aggregated = _aggregate_results(server_results)
   resources = _to_cloud_resources(aggregated, options)
   categorize_resources(resources)
   write XLS → output/ad_analysis_{ts}.xlsx

Finally:
   ad_manager.set_complete(output_path, resources, errors)
   ad_event_bridge.emit("ad_complete", {})
   ad_event_bridge.emit_done()
```

**Race condition guard** (same as `sse_nios()`): If `ad_manager.state` is already COMPLETE or ERROR when the SSE connection opens, emit `ad_complete` immediately.

**`partials/ad/complete.html` content:**

Derive summary counts from `resources` list passed in context:
- DNS zones: `resources | selectattr("resource_type", "==", "ad-dns-zone") | list | length`
- DNS records: `resources | selectattr("resource_type", "==", "ad-dns-record") | list | length`
- DHCP scopes: `resources | selectattr("resource_type", "==", "ad-dhcp-scope") | list | length`
- Active IPs (leases + reservations): `resources | selectattr("resource_type", "==", "ad-dhcp-ip") | list | length`
- AD Users: `resources | selectattr("resource_type", "==", "ad-user") | list | length`
- Token total: compute inline from DDI + IP + Asset counts using DDI_TYPES knowledge — OR call `_compute_summary()` subpath on `ad_manager.resources` from `tab_ad()`

Simplest approach: compute token totals in `tab_ad()` using `calculate_account_tokens()` on the AD resources, pass as `ad_summary` context dict.

---

## Feature 2: Top 5 DNS Zones Panel

### Data Sources Per Scope

| Scope | Where data lives | Zone name source | Token weight |
|-------|-----------------|------------------|--------------|
| Cloud (AWS) | `scan_manager.resources`, `resource_type == "route53-zone"` | `resource.name` | 1 DDI per zone |
| Cloud (Azure) | `resource_type in ("azure-dns-zone", "azure-private-dns-zone")` | `resource.name` | 1 DDI per zone |
| Cloud (GCP) | `resource_type == "gcp-dns-zone"` | `resource.name` | 1 DDI per zone |
| NIOS | NIOS pipeline — `NiosFamily.DNS_ZONE` objects | `raw_attrs.get("fqdn")` or similar | 1 DDI per zone |
| AD | `ad_manager.resources`, `resource_type == "ad-dns-zone"` | `resource.name` | 1 DDI per zone |

**"Top 5 by token contribution" definition:** Since all zones contribute exactly 1 DDI token each, "top 5 by contribution" means the 5 zones with the most associated DNS records (records amplify the zone's contribution to the DDI total). This is the useful interpretation — a zone with 10,000 records contributes far more than a zone with 2 records.

**Practical computation:** For each zone, count associated records in the same resource list:
- Cloud: group `resource_type == "route53-record"` by `resource.details["zone"]` (or derive from `resource.name`) — OR group by `account_id` as proxy. For Route53, `resource.account_id` gives the account, not the parent zone. Use `resource.details` which may contain zone info.
- AD: group `resource_type == "ad-dns-record"` by `resource.details["domain"]` — the AD zone name maps to domain.
- GCP/Azure: similar grouping by parent zone name from `resource.details`.

**Simpler approach:** Count the sum of (1 DDI for zone + 1 DDI for each record in zone). This gives "DDI tokens contributed by this zone and its records" — the most meaningful metric.

### NIOS Scope Gap

`CountResult` does not track per-zone counts. `IntegrityReport.families_found` gives `{dns_zone: N}` as a single integer — total count of DNS zone objects, not per-zone names. There is no existing mechanism to access individual zone names from the NIOS pipeline results.

**Options:**
1. **Add per-zone accumulator in `_run_nios_pipeline()`** — during the `count_objects()` pass, accumulate `{zone_fqdn: record_count}`. Requires access to the zone FQDN from `NiosObject.raw_attrs`. The zone FQDN is likely in `raw_attrs.get("fqdn")` for `NiosFamily.DNS_ZONE` objects. Needs verification against the NIOS schema. Store result in `nios_manager._top_dns_zones`.

2. **Show NIOS scope panel as "N total zones"** — display the zone count from `IntegrityReport.families_found.get(NiosFamily.DNS_ZONE, 0)` without per-zone breakdown. Simpler, requires no pipeline change.

**Recommendation:** Option 2 for v1.8, with a note that per-zone NIOS breakdown requires a counter enhancement. The panel shows "Top zones by record count" for Cloud and AD where zone-level data is available, and "Total DNS Zones: N" for NIOS where it is not.

If per-zone NIOS data is required: add `_top_dns_zones: list[dict]` to `NiosScanManager`, accumulate in `_run_nios_pipeline()` using a `{zone_fqdn: record_count}` dict built during the object stream traversal (in the `NiosFamily.DNS_ZONE` and `DNS_RECORD_*` branches of `count_objects()`).

### Where to Compute and Render

**Cloud zones:** Computed in `tab_summary()` in `pages.py`. New helper `_compute_top_dns_zones(resources)` returns `list[dict]` with `{zone_name, zone_type, record_count, ddi_total}`. Passed as `top_cloud_zones` to `pages/summary.html`.

**NIOS zones:** Computed in `tab_nios()`. Either read from `nios_manager.top_dns_zones` (if Option 1) or from `nios_manager.scenario_suite` + `family_breakdown` count (if Option 2). Passed as `top_nios_zones` to `pages/nios.html`.

**AD zones:** Computed in `tab_ad()` from `ad_manager.resources`. Same helper pattern as cloud zones. Passed as `top_ad_zones` to `pages/ad.html` → `partials/ad/complete.html`.

### Modified Components

| Component | Change |
|-----------|--------|
| `routes/pages.py` | Add `_compute_top_dns_zones(resources)` helper; call in `tab_summary()` + `tab_ad()` |
| `routes/pages.py:tab_nios()` | Add `top_nios_zones` to context (either from `nios_manager.top_dns_zones` or family count) |
| `templates/pages/summary.html` | Add Top 5 Cloud DNS Zones panel below Per-Provider Breakdown |
| `templates/pages/nios.html` | Add Top DNS Zones panel in complete branch |
| `templates/partials/ad/complete.html` | Include Top 5 AD DNS Zones panel |

---

## Feature 3: CLOUD-EXT-01 (Per-Account v1.7 DDI Type Attribution)

### Current State

The existing `_compute_summary()` already builds `resource_type_breakdown` per account:

```python
for r in by_account[account_id]:
    if r.counted and r.category in ("ddi", "ip", "asset"):
        rt = r.resource_type
        if rt not in breakdown:
            breakdown[rt] = {"count": 0, "category": r.category}
        breakdown[rt]["count"] += 1
```

The v1.7 DDI types (15 AWS, 5 Azure, 6 GCP) are all in `DDI_TYPES` in `categorizer.py`. `categorize_resources()` marks them `counted=True, category="ddi"`. They therefore already appear in `resource_type_breakdown` without any code change.

**The template already renders them:**

```html
{% for rt, info in acct.resource_type_breakdown.items() | sort %}
<div>{{ rt }}: {{ info.count }} <small>({{ info.category | upper }})</small></div>
{% endfor %}
```

### What CLOUD-EXT-01 Actually Requires

**Verification step:** Confirm that v1.7 type strings appear in `resource_type_breakdown` for accounts that contain them. This is a testing/validation task.

**Template enhancement:** The current breakdown row shows `rt: count (DDI)` without formula derivation. For v1.7 types, the per-type DDI contribution is the same formula: `count ÷ 25`. Adding the inline formula annotation (matching the style of the column-level formula already shown) is a template-only change:

```html
{% if info.category == "ddi" %}
  {{ rt }}: {{ info.count }}
  <small style="color: var(--ib-gray-600);">× 1 DDI = {{ info.count }} ÷ 25 = {{ "%.1f"|format(info.count / 25) }} tokens</small>
{% else %}
  {{ rt }}: {{ info.count }} <small>({{ info.category | upper }})</small>
{% endif %}
```

### Modified Components

| Component | Change |
|-----------|--------|
| `templates/pages/summary.html` | Add DDI formula annotation to breakdown rows for `category == "ddi"` rows |

**No Python changes required** for CLOUD-EXT-01.

---

## Component Boundary Summary

### New Components

| Component | File | Purpose |
|-----------|------|---------|
| AD state manager | `services/ad_manager.py` | Thread-safe AD lifecycle (mirrors NiosScanManager) |
| AD routes | `routes/ad.py` | `POST /ad/run`, `GET /api/sse/ad`, `GET /api/ad/progress`, `GET /tab/ad` |
| AD tab page | `templates/pages/ad.html` | State-driven AD tab (idle/running/complete/error) |
| AD connection form | `templates/partials/ad/step1_connect.html` | Servers, auth, credentials, autodiscover |
| AD run partial | `templates/partials/ad/step2_run.html` | SSE-connected progress container |
| AD progress fragment | `templates/partials/ad/progress_display.html` | Step bar rendered on SSE trigger |
| AD complete partial | `templates/partials/ad/complete.html` | Results: zone/DHCP/user counts, token summary, download |

### Modified Components

| Component | Change | Risk |
|-----------|--------|------|
| `app.py` | Register `ad_router`, add `ad_event_bridge` + `ad_manager` to lifespan | Low — additive |
| `routes/pages.py` `_get_tab_context()` | Add `ad_state` to context dict | Low — one new key |
| `routes/pages.py` | Add `tab_ad()` route; add `_compute_top_dns_zones()` helper; extend `tab_summary()` and `tab_nios()` with top zone data | Low — additive routes/helpers |
| `templates/partials/tab_bar.html` | Add AD tab link + badge | Low — additive HTML |
| `templates/pages/summary.html` | Add Top 5 Cloud DNS Zones panel + DDI formula annotation in breakdown rows | Low — template only |
| `templates/pages/nios.html` | Add Top DNS Zones section in complete branch | Low — template only, guarded by `{% if top_nios_zones %}` |

---

## Data Flow

### AD Tab: Form → Pipeline → Progress → Complete

```
Browser: POST /ad/run (connection form data)
  routes/ad.py: ad_run()
    → validate form: servers, auth_mode, port, ssl, credentials, autodiscover
    → build AdOptions(servers=[...], auth_mode="kerberos"|"ntlm", ...)
    → ad_manager.start()
    → loop.run_in_executor(None, _run_ad_pipeline, ad_manager, options, ad_event_bridge)
    → return partials/ad/step2_run.html (SSE div)

Background: _run_ad_pipeline(ad_manager, options, ad_event_bridge)
  Step 1: ad_manager.set_progress(1, 2, "Connecting…", elapsed)
          ad_event_bridge.emit("ad_progress", {step, total, label, elapsed_seconds})
  [Step 2 if autodiscover]: set_progress(2, 3, "Discovering DCs…", elapsed)
          emit "ad_progress"
          collector.autodiscover_servers()  → dc_list; update total
  Step 3..N: per-DC collection with progress emit per DC
  Step N+1: "Aggregating results"
          _aggregate_results(server_results)
          _to_cloud_resources(aggregated, options)
          categorize_resources(resources)
          write_xlsx_report(output_path, resources, {}, errors, "ad")
  ad_manager.set_complete(output_path, resources, errors)
  ad_event_bridge.emit("ad_complete", {})
  ad_event_bridge.emit_done()

Browser SSE: sse:ad_progress
  HTMX hx-get /api/ad/progress
  routes/ad.py: ad_progress_display()
    → ad_manager.current_progress
    → return partials/ad/progress_display.html

Browser SSE: sse:ad_complete
  HTMX hx-get /tab/ad hx-target="#tab-container"
  routes/pages.py: tab_ad()
    → ad_manager.resources → compute token summary
    → ad_manager.errors, ad_manager.output_path
    → compute top_ad_zones from ad_manager.resources
    → return pages/ad.html (complete branch)
```

### Top 5 Cloud DNS Zones: Computation

```
routes/pages.py: tab_summary()
  → scan_manager.resources (in memory, already available)
  → _compute_top_dns_zones(resources):
      DNS_ZONE_TYPES = {"route53-zone", "azure-dns-zone", "azure-private-dns-zone", "gcp-dns-zone"}
      DNS_RECORD_TYPES = {"route53-record", "azure-dns-record", "azure-private-dns-record", "gcp-dns-record"}
      zone_records: dict[str, int] = {}
      for r in resources:
          if r.resource_type in DNS_ZONE_TYPES:
              zone_records.setdefault(r.name, 0)  # ensure zone appears even with 0 records
      for r in resources:
          if r.resource_type in DNS_RECORD_TYPES:
              zone_name = r.details.get("zone") or r.account_id  # best-effort zone attribution
              if zone_name in zone_records:
                  zone_records[zone_name] += 1
      top_5 = sorted(zone_records.items(), key=lambda x: -x[1])[:5]
      return [{"zone_name": z, "record_count": c, "ddi_approx": 1 + c} for z, c in top_5]
  → top_cloud_zones passed to summary.html context
```

### CLOUD-EXT-01: No New Data Flow

V1.7 DDI types already flow through `categorize_resources()` → `resource_type_breakdown` dict → template. CLOUD-EXT-01 is purely a template rendering enhancement (add formula annotation for DDI rows in the breakdown `<details>` expansion).

---

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `routes/ad.py` ↔ `ad_manager` | `app.state.ad_manager` direct access | Same pattern as nios_manager |
| `routes/ad.py` ↔ `ad_event_bridge` | `ad_event_bridge.emit(event_type, data)` from background thread | Same pattern as nios_event_bridge |
| `_run_ad_pipeline()` ↔ `MicrosoftAdCollector` | Direct instantiation + per-DC collect calls | Bypasses `run_ad_analysis()` for progress granularity |
| `_run_ad_pipeline()` ↔ `categorize_resources()` | Direct call after `_to_cloud_resources()` | Same as cloud scan pipeline |
| `_run_ad_pipeline()` ↔ `write_xlsx_report()` | Direct call with `provider="ad"` | Already used by `run_ad_analysis()` |
| `tab_ad()` ↔ `ad_manager` | Read state, resources, errors, output_path | Same as tab_nios() ↔ nios_manager |
| `_compute_top_dns_zones()` ↔ `scan_manager.resources` | Read-only, pure computation | No new state |

### Key Reuse (No Changes to These)

| Module | How AD reuses it |
|--------|-----------------|
| `services/event_bridge.py` (EventBridge) | Third instance — `ad_event_bridge` — identical to `nios_event_bridge` |
| `providers/ad/collector.py` (MicrosoftAdCollector) | Called directly from `_run_ad_pipeline()` |
| `providers/ad/runner.py` (_aggregate_results, _to_cloud_resources) | Import and call from `_run_ad_pipeline()` |
| `counting/categorizer.py` (categorize_resources) | Called from `_run_ad_pipeline()` after `_to_cloud_resources()` |
| `output/xlsx_report.py` (write_xlsx_report) | Called from `_run_ad_pipeline()` with `provider="ad"` |

---

## Architectural Patterns

### Pattern 1: Manager + EventBridge Pair (Established)

Each long-running background source (cloud scan, NIOS, AD) gets an independent `Manager` + `EventBridge` pair on `app.state`. The pattern is fully proven for cloud and NIOS.

**AD application:** `app.state.ad_manager` (AdScanManager) + `app.state.ad_event_bridge` (EventBridge). Registered in `app.py` lifespan identically to the NIOS pair.

### Pattern 2: SSE-Triggered Fragment Fetch (Established)

Progress display uses a two-event SSE model:
- Named progress event (`ad_progress`) triggers `hx-get /api/ad/progress` → renders the progress bar HTML fragment
- Terminal event (`ad_complete`) triggers `hx-get /tab/ad hx-target="#tab-container"` → full tab refresh

Race guard: if `ad_manager.state` is already COMPLETE or ERROR when SSE connection opens, emit `ad_complete` immediately (same guard as in `sse_nios()`).

### Pattern 3: State-Driven Tab Page (Established)

`pages/ad.html` branches on `ad_state` string: idle→wizard form, running→SSE progress container, complete→results partial, error→error article + wizard reset. All state transitions are server-side.

### Pattern 4: Template-Owned Formula Constants (Established)

Formula divisors (÷25, ÷13, ÷3) are computed inline in Jinja2 arithmetic. `tab_ad()` passes raw counts; `partials/ad/complete.html` computes formatted strings. This applies to CLOUD-EXT-01 as well — formula annotation added to breakdown rows is template arithmetic only.

### Pattern 5: Pre-Computed Display Lists in Manager (Established)

`NiosScanManager` stores `_family_breakdown: list` (pre-computed in `_run_nios_pipeline()` before calling `set_complete()`). This avoids re-importing NIOS constants from the route handler.

**AD application:** `AdScanManager.set_complete()` stores the full `resources` list. Token summary for `complete.html` is computed in `tab_ad()` using `calculate_account_tokens()` over the AD resources — same pattern as `_compute_summary()` for cloud.

---

## Anti-Patterns

### Anti-Pattern 1: Sharing the AD EventBridge

**What:** Reusing `app.state.event_bridge` or `nios_event_bridge` for AD SSE events.

**Why wrong:** SC-5 — EventBridge fan-out sends all events to all subscribers. AD events on the cloud bridge would corrupt cloud scan progress state in the browser.

**Do this instead:** Always create a third independent `EventBridge()` instance.

### Anti-Pattern 2: Storing AdOptions in AdScanManager

**What:** Persisting the `AdOptions` object (which contains `username`/`password`) in `AdScanManager` after pipeline completion.

**Why wrong:** Credentials in process memory after use. Manager lives for the process lifetime. No legitimate need — options are used only during the pipeline run.

**Do this instead:** Build `AdOptions` in the route handler from the form POST. Pass directly to `_run_ad_pipeline()`. After the pipeline returns, only `resources`, `errors`, and `output_path` are stored in the manager.

### Anti-Pattern 3: Using `asyncio.to_thread` for AD Pipeline

**What:** `asyncio.to_thread(_run_ad_pipeline, ...)` to dispatch the background AD pipeline.

**Why wrong:** `asyncio.to_thread()` requires Python 3.10+. The project targets Python 3.9. The existing `_run_nios_pipeline()` explicitly uses `loop.run_in_executor(None, ...)` for this reason.

**Do this instead:** `loop.run_in_executor(None, _run_ad_pipeline, ad_manager, options, ad_event_bridge)`.

### Anti-Pattern 4: Calling `run_ad_analysis()` for Dashboard Pipeline

**What:** Calling `run_ad_analysis(options, output_path=path)` from `_run_ad_pipeline()` as a black-box call.

**Why wrong:** `run_ad_analysis()` performs all collection steps sequentially with no progress callbacks. No `set_progress()` calls can be injected. The dashboard would show an indeterminate spinner for the entire AD collection duration (potentially minutes for large forests).

**Do this instead:** Inline the pipeline (same approach as `_run_nios_pipeline()` inlines NIOS). Import `MicrosoftAdCollector`, `_aggregate_results`, `_to_cloud_resources` directly. This allows `set_progress()` + `emit("ad_progress", ...)` between each DC.

### Anti-Pattern 5: Computing Zone Panels in Background Threads

**What:** Adding a background task to compute Top 5 zones after scan completes.

**Why wrong:** Zone computation is a linear pass over an in-memory list (already loaded into `scan_manager.resources`). Even at 50k resources, this takes <10ms. Background threading adds complexity with no benefit.

**Do this instead:** Compute in the tab route handler synchronously, same as `_compute_summary()`.

---

## Build Order (Dependency-Aware)

### Phase 1: AdScanManager + app.py wiring

**Dependencies:** None. Foundation for all AD features.

- Create `services/ad_manager.py` — copy-adapt `NiosScanManager`; add `_resources` and `_errors` fields to `set_complete()`
- Modify `app.py` lifespan — register `ad_event_bridge`, `ad_manager`
- Modify `routes/pages.py` `_get_tab_context()` — add `ad_state`
- Modify `templates/partials/tab_bar.html` — add AD tab link + badge

### Phase 2: AD routes + templates

**Dependencies:** Phase 1 (state objects must be on app.state).

- Create `routes/ad.py` — `POST /ad/run`, `GET /api/sse/ad`, `GET /api/ad/progress`, `GET /tab/ad`
- Create `templates/pages/ad.html`
- Create `templates/partials/ad/step1_connect.html`
- Create `templates/partials/ad/step2_run.html`
- Create `templates/partials/ad/progress_display.html`
- Create `templates/partials/ad/complete.html`
- Register `ad_router` in `app.py`

### Phase 3: CLOUD-EXT-01

**Dependencies:** None (self-contained template enhancement).

- Read `templates/pages/summary.html` — verify v1.7 type strings appear in `resource_type_breakdown`
- Add DDI formula annotation to breakdown rows for `info.category == "ddi"` entries

### Phase 4: Top 5 DNS Zones panels

**Dependencies:** Phase 2 (AD zones panel needs `ad_manager.resources`).

**Cloud + AD zones (no pipeline changes):**
- Add `_compute_top_dns_zones(resources)` helper in `pages.py`
- Extend `tab_summary()` context: `top_cloud_zones`
- Extend `tab_ad()` context: `top_ad_zones`
- Add Top 5 panels to `pages/summary.html` and `partials/ad/complete.html`

**NIOS zones (decide: Option 2 first, Option 1 if time allows):**
- Option 2 (fast): Pass `top_nios_zones` as zone total count from `family_breakdown` — template shows "N DNS zones" without per-zone ranking
- Option 1 (full): Add per-zone accumulator to `_run_nios_pipeline()`, store in `nios_manager._top_dns_zones`, render per-zone in `pages/nios.html`

---

## Scaling Considerations

This is a local tool. Notes specific to AD:

| Concern | Approach |
|---------|----------|
| Large AD forest (50+ DCs) | Progress steps are dynamic — `total` updated when autodiscovery returns DC list. `set_progress()` already accepts `total` as parameter. |
| WinRM timeout per DC (30–120s) | All collection in background thread via `run_in_executor`. Route handler returns immediately with progress partial. |
| Many AD zones (10k+) | Top-5 computation is `O(n)` linear pass. <10ms even at 100k resources. |

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| NIOS pattern reusability for AD | HIGH | Source-read nios_manager.py, routes/nios.py, pages/nios.html — all patterns confirmed |
| `run_ad_analysis()` returns (resources, errors) | HIGH | Source-read providers/ad/runner.py — signature confirmed |
| AD types in DDI_TYPES → flow to breakdown | HIGH | Source-read counting/categorizer.py — ad-dns-zone, ad-dns-record, ad-dhcp-scope confirmed in DDI_TYPES |
| `resource_type_breakdown` already built in `_compute_summary()` | HIGH | Source-read routes/pages.py — breakdown loop confirmed at lines 138–156 |
| EventBridge SC-5 isolation pattern | HIGH | Source-read app.py lifespan — nios_event_bridge independent instance confirmed |
| Python 3.9 run_in_executor requirement | HIGH | Source-read routes/nios.py comment at line 8 — explicit Python 3.9 note |
| No per-zone data in NIOS pipeline currently | HIGH | Source-read nios/counter.py — CountResult.per_family_ddi is family-level, not zone-level |

---

## Sources

- Direct source reads: `services/nios_manager.py`, `services/scan_manager.py`, `services/event_bridge.py`
- Direct source reads: `routes/nios.py` (full file), `routes/scan.py` (full file), `routes/pages.py` (full file)
- Direct source reads: `routes/ad.py` — does not exist yet (confirmed by directory listing)
- Direct source reads: `app.py` — lifespan pattern confirmed
- Direct source reads: `providers/ad/runner.py`, `providers/ad/options.py`, `providers/ad/collector.py`
- Direct source reads: `counting/categorizer.py` — DDI_TYPES confirmed for all v1.7 AD/cloud types
- Direct source reads: `nios/counter.py`, `nios/schema.py` — CountResult, NiosFamily, per_family_ddi
- Direct source reads: `templates/pages/nios.html`, `templates/pages/summary.html`
- Direct source reads: `templates/partials/nios/step2_run.html`, `templates/partials/nios/complete.html`
- Direct source reads: `templates/partials/tab_bar.html`
- Project context: `.planning/PROJECT.md` — v1.8 milestone features and constraints

---
*Architecture research for: Infoblox Universal DDI Cloud Usage Estimator — v1.8 Dashboard Analytics*
*Researched: 2026-03-07*
