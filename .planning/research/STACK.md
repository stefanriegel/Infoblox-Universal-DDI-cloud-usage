# Stack Research

**Domain:** FastAPI + HTMX dashboard — v1.8 Dashboard Analytics additions
**Researched:** 2026-03-07
**Confidence:** HIGH

---

## Context: What Already Exists (Do Not Re-Add)

This is a v1.8 milestone on a fully operational codebase. The following stack is
already in place and must NOT be replaced or re-added:

| Existing | Role |
|----------|------|
| FastAPI >= 0.115.0 | Web framework, route handlers, HTMX partial endpoints |
| Jinja2 >= 3.1.0 | Server-side HTML templating |
| HTMX (vendored) | Partial swaps, SSE event wiring, hx-get/hx-target/sse patterns |
| PicoCSS (vendored) | Base styling — `<table>`, `<article>`, `<details>` all styled |
| janus >= 2.0.0 | Thread-safe sync-to-async queue (SSE EventBridge) |
| lxml >= 5.3.0 | NIOS backup XML streaming parser |
| xlsxwriter >= 3.1.0 | XLS report generation |
| PyYAML >= 6.0 | NIOS config file parsing |
| python-multipart >= 0.0.5 | File upload support |
| pywinrm (in use) | WinRM/PowerShell AD connectivity — AD provider already operational |
| pytest >= 8.0.0, moto >= 5.0.0 | Test framework |
| Python 3.9+ | Required minimum, guarded throughout |

All patterns for SSE progress, wizard tabs, manager state machines, and attribution
tables are established. The v1.8 features extend these patterns — they do not
introduce new patterns.

---

## Recommended Stack — New Additions for v1.8

**Answer: No new libraries required.** All three v1.8 features are pure routing,
state management, template, and data aggregation work within the existing stack.

### Core Technologies (unchanged, confirmed correct)

| Technology | Version | Purpose | Why Still Correct |
|------------|---------|---------|-------------------|
| FastAPI | >= 0.115.0 | New `/tab/ad`, `/ad/connect`, `/api/sse/ad` routes | Exact same route + StreamingResponse pattern used for NIOS. `run_in_executor` for sync AD runner. |
| Jinja2 | >= 3.1.0 | New AD tab templates, Top 5 DNS Zones panel | Template-only change. Existing `{% include %}`, `{% for %}`, and `{% if %}` coverage is sufficient. |
| HTMX (vendored) | 1.9.x | AD wizard step swaps, AD SSE subscription | `hx-ext="sse"`, `sse-connect`, `sse-swap` attributes already used in NIOS tab. Copy pattern verbatim. |
| janus | >= 2.0.0 | New `AdEventBridge` instance on `app.state` | `EventBridge` class is already generic and reusable. Instantiate a second copy for AD (identical to how `nios_event_bridge` is separate from `event_bridge`). |
| stdlib `collections.Counter` | stdlib | Top 5 DNS Zones aggregation across scopes | Groups zone names by token count. Used in pages.py already. Zero new import needed in context of dashboard. |
| stdlib `threading.Lock` | stdlib | `AdScanManager` thread safety | Exact same pattern as `NiosScanManager` — Lock + Enum state machine. |

### Supporting Libraries (unchanged)

| Library | Version | Integration Note |
|---------|---------|-----------------|
| pywinrm | in use | AD runner (`runner.py`) already uses it. Dashboard just calls `run_ad_analysis()` via `run_in_executor`. No new pywinrm surface area. |
| xlsxwriter | >= 3.1.0 | AD runner already writes XLS. Dashboard exposes download link same as NIOS. |

---

## Integration Points — Precise Wiring Per Feature

### Feature 1: AD Dashboard Tab (AD-09 + AD-10)

**Pattern source:** `src/cloud_usage/dashboard/routes/nios.py` +
`src/cloud_usage/dashboard/services/nios_manager.py` +
`src/cloud_usage/dashboard/templates/pages/nios.html` +
`src/cloud_usage/dashboard/templates/partials/nios/`

**What to add:**

1. **`AdScanManager` service** —
   `src/cloud_usage/dashboard/services/ad_manager.py`.
   Mirrors `NiosScanManager` exactly: Enum state (IDLE/RUNNING/COMPLETE/ERROR),
   `threading.Lock`, `set_running()`, `set_complete(output_path, ad_results)`,
   `set_error()`, properties for state/output_path/results/error.
   Store `ad_results` (the list of CloudResource or an aggregated summary dict)
   for results display. No new patterns.

2. **`AdEventBridge` instance** — In `app.py`, instantiate a second
   `EventBridge()` registered as `app.state.ad_event_bridge`.
   Exactly as `app.state.nios_event_bridge` is already separate from
   `app.state.event_bridge`.

3. **Routes** — `src/cloud_usage/dashboard/routes/ad.py`:
   - `POST /ad/connect` — accept host/credentials form, validate, start
     `run_ad_analysis()` in `run_in_executor`, return SSE progress partial.
   - `GET /api/sse/ad` — stream `ad_event_bridge` as `text/event-stream`.
     Copy `routes/sse.py` StreamingResponse pattern verbatim.
   - `GET /api/ad/progress` — return current progress HTML fragment.
     Copy `GET /api/nios/progress` pattern verbatim.

4. **Templates** —
   `src/cloud_usage/dashboard/templates/pages/ad.html` — outer tab shell with
   SSE subscription div (copy `pages/nios.html` structure).
   `src/cloud_usage/dashboard/templates/partials/ad/`:
   - `step1_connect.html` — hostname, username, password form (no file upload;
     replace upload widget with text inputs).
   - `step2_run.html` — SSE progress bar (copy `partials/nios/step2_run.html`
     with `sse-connect="/api/sse/ad"` and `ad_complete` event name).
   - `progress_display.html` — copy `partials/nios/progress_display.html`.
   - `complete.html` — results display: domain, DNS zone count, DHCP scope count,
     DHCP IP count, AD user count, token totals. Download link for XLS.
     Pattern: `partials/nios/complete.html` summary cards section.

5. **Tab bar** — Add 5th `<li>` to `partials/tab_bar.html` with
   `hx-get="/tab/ad"` and `ad_state` badge (running/complete/error).
   Pass `ad_state` in `_get_tab_context()` in `pages.py` (same as `nios_state`).

6. **Route for tab render** — `GET /tab/ad` in `pages.py`: read from
   `app.state.ad_manager`, render `pages/ad.html`.

**AD runner integration:** `run_ad_analysis()` in
`src/cloud_usage/providers/ad/runner.py` already returns
`(list[CloudResource], list[str])` when `output_path` is provided (writes XLS).
Call it via `loop.run_in_executor(None, run_ad_analysis, options)` from the
async route handler. The AD runner emits progress via a callback hook — wire this
to `ad_event_bridge.emit()` during the run. If the runner has no progress callback
yet (CLI-only path), add a lightweight `progress_callback` parameter to `run_ad_analysis()`
that the dashboard route passes in. This is a small, additive change to `runner.py`.

### Feature 2: Top 5 DNS Zones Panel (per scope: NIOS, Cloud, AD)

**Pattern source:** `_compute_summary()` in `src/cloud_usage/dashboard/routes/pages.py`
and `NiosScanManager.family_breakdown` data pattern.

**Data sources (all already available after analysis runs):**

| Scope | Data location | Zone name field |
|-------|---------------|-----------------|
| Cloud | `ScanManager.resources` — CloudResource list | `resource.name` where `resource.resource_type` ends in `"dns-zone"` |
| AD | `AdScanManager.ad_results` — CloudResource list | `resource.details["zone"]` where `resource.resource_type == "ad-dns-zone"` |
| NIOS | `NiosScanManager` — needs `family_counts` extended | NIOS `DNS_ZONE` objects carry zone FQDN in `raw_attrs`. Key is `"fqdn"` (standard NIOS property name). Parser currently counts zones but does not store names. Requires passing zone names list through NiosScanManager. |

**For Cloud and AD scopes:** Pure `collections.Counter` aggregation in
`_compute_summary()` or a new `_compute_dns_zones()` helper. Group
CloudResource objects by zone name, count records per zone, take top 5.
Token contribution per zone = `ceil(record_count / 25)`.

**For NIOS scope:** The NIOS parser yields `NiosObject` instances with
`family=NiosFamily.DNS_ZONE` and zone FQDN in `raw_attrs["fqdn"]`. Currently
only the count is stored in `IntegrityReport.families_found`. To surface per-zone
record counts, extend the NIOS pipeline to collect a `dict[zone_fqdn, record_count]`
during the parse pass and store it on `NiosScanManager` alongside `family_breakdown`.

**No new libraries:** `collections.Counter` (stdlib), dict sorting, and Jinja2
`{% for zone in top_zones | sort(attribute='tokens', reverse=True) | first(5) %}`
are sufficient.

**Template location:** Add a "Top 5 DNS Zones" section to
`templates/pages/summary.html` (or a dedicated `templates/partials/dns_zones.html`
included by summary.html). Three sub-tables side by side (NIOS | Cloud | AD) or
stacked if screen width is narrow — use PicoCSS grid columns
(`<div class="grid"> <div>...</div> <div>...</div> <div>...</div> </div>`).

### Feature 3: CLOUD-EXT-01 — Per-Account Breakdown for v1.7 DDI Types

**Status:** Structurally already working.

`resource_type_breakdown` on each account dict in `per_account_details` already
groups ALL counted resources by `resource_type` — including every v1.7 type
(Route53 Resolver endpoints, IPAM pools, VNet Gateways, Compute Addresses, etc.).
The template in `summary.html` already iterates:
```html
{% for rt, info in acct.resource_type_breakdown.items() | sort %}
<div>{{ rt }}: {{ info.count }} <small>({{ info.category | upper }})</small></div>
{% endfor %}
```

**What may still be needed:**

1. **Verify new v1.7 type strings reach the breakdown** — confirm that
   `categorize_resources()` marks v1.7 types as `counted=True` with correct
   `category`. If categorizer has gaps for any of the 26 new types, fix in
   `src/cloud_usage/counting/categorizer.py`. This is a categorizer bug fix, not
   a stack addition.

2. **Display labels** — The breakdown currently shows raw `resource_type` strings
   (e.g., `"aws-route53-resolver-endpoint"`). A display name map
   `DDI_TYPE_LABELS: dict[str, str]` in `pages.py` or `categorizer.py` can
   humanize these. Pure Python `dict` lookup — no library.

3. **No route or template structural change needed** — the existing
   `<details>/<summary>` collapse row already renders all types in the breakdown.

---

## What NOT to Add

| Do NOT add | Why | Use instead |
|------------|-----|-------------|
| Any new Python package | All three features are routing, state management, template, and data aggregation — 100% within existing stack | Existing FastAPI + Jinja2 + janus + stdlib |
| Alpine.js or any JS framework | No interactivity beyond what HTMX already provides; PROJECT.md: Python-only stack for auditability | HTMX SSE + hx-get patterns (already used in NIOS) |
| LDAP library (python-ldap, ldap3) | AD provider uses pywinrm/PowerShell — already operational; LDAP would require reimplementing counting logic | pywinrm (already in use) |
| asyncio.Queue (builtin) | Cannot safely bridge sync AD runner thread to async SSE; asyncio.Queue is not thread-safe from sync callers | janus.Queue (already in use — exact same reason as NIOS EventBridge) |
| A second EventBridge class | `EventBridge` in `services/event_bridge.py` is already generic; just instantiate a second copy for AD | Second `EventBridge()` instance on `app.state.ad_event_bridge` |
| pandas | `collections.Counter` + dict sorting handles all zone aggregation in stdlib | `collections.Counter` (stdlib) |
| Chart/visualization library | PROJECT.md: "Charts / visualizations — text tables sufficient for enterprise audit context" is explicitly out of scope | Plain `<table>` in Jinja2 template |
| Server-side session / cookie auth for AD credentials | Tool runs locally — no multi-user concern; credentials are only needed for the AD scan duration | Pass credentials directly from form POST to `run_ad_analysis()` via AdOptions; do not persist |

---

## Stack Patterns for v1.8

**Pattern: Second EventBridge instance for AD (established: NIOS already uses this)**

```python
# In app.py lifespan startup
app.state.ad_event_bridge = EventBridge()
await app.state.ad_event_bridge.start()
```

AD SSE endpoint copies `routes/sse.py` verbatim, pointing to
`request.app.state.ad_event_bridge`.

**Pattern: AdScanManager (mirrors NiosScanManager)**

```python
# services/ad_manager.py
class AdState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"

class AdScanManager:
    def __init__(self) -> None:
        self._state = AdState.IDLE
        self._lock = threading.Lock()
        self._output_path: Optional[str] = None
        self._error: Optional[str] = None
        self._ad_results: Optional[dict] = None  # aggregated summary for display
        self._current_progress: dict = {"step": 0, "total": 5, "label": "Starting..."}
```

**Pattern: Top 5 DNS Zones aggregation (stdlib only)**

```python
# In pages.py or a new _compute_dns_zones() helper
from collections import Counter

def _top5_zones_cloud(resources: list[CloudResource]) -> list[dict]:
    zone_record_counts: Counter = Counter()
    for r in resources:
        if r.counted and "dns-record" in r.resource_type:
            zone = r.details.get("zone") or r.name
            zone_record_counts[zone] += 1
    return [
        {"zone": zone, "records": count, "tokens": -(-count // 25)}
        for zone, count in zone_record_counts.most_common(5)
    ]
```

AD scope uses `r.details["zone"]` (already set in `runner.py` `details`).
Cloud scope uses zone name from provider-specific resource details.
NIOS scope requires extending the parse pipeline to collect per-zone DNS record
counts (see integration point above).

**Pattern: NIOS zone name collection (extend existing pipeline)**

The NIOS parser yields `NiosObject(family=DNS_ZONE, raw_attrs={"fqdn": "example.com", ...})`.
Collect a `Counter[str]` of zone FQDNs during the counter pass and store on
`NiosScanManager` via an extended `set_complete()` parameter `zone_counts`.
Access in the route handler and pass to the template as `nios_top_zones`.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| AD EventBridge | Second `EventBridge()` instance | Shared `event_bridge` with AD events multiplexed | Breaks isolation SC-5; AD scan and cloud scan events would interleave on the same SSE stream |
| AD credentials handling | Pass directly from POST form to `run_ad_analysis()` in executor; never store | Store in `AdScanManager` | Credentials in memory beyond request lifetime is a security anti-pattern for a local tool; password not needed after the scan starts |
| Top 5 DNS Zones location | In Summary tab (alongside existing per-account breakdown) | Separate "Analytics" tab | Adding a 6th tab increases navigation complexity; DNS zones data is naturally part of the summary/audit story |
| NIOS zone name source | Extend parser to collect per-zone record counts | Re-run parse on demand | Re-running a 2GB backup file to get zone names takes 30+ seconds; collect once during the existing pipeline run |
| AD progress in dashboard | Add `progress_callback` parameter to `run_ad_analysis()` | Emit progress events from within runner using a global | Callback parameter keeps runner testable without a live EventBridge; same design used in NIOS pipeline |

---

## Version Compatibility

| Package | Current in requirements.txt | Python 3.9 Compatible | Notes |
|---------|-----------------------------|-----------------------|-------|
| FastAPI | >= 0.115.0 | Yes | No version bump needed |
| Jinja2 | >= 3.1.0 | Yes | No version bump needed |
| janus | >= 2.0.0 | Yes | janus 2.x requires Python 3.8+ |
| pywinrm | in use | Yes | Already operational in AD provider |
| lxml | >= 5.3.0 | Yes | No change to parsing |
| stdlib (collections, threading, dataclasses) | stdlib | Yes | Python 3.7+ for dataclasses |

No version bumps required. No new packages required.

---

## Installation

No new packages to install. All capabilities needed for v1.8 are already in
the existing requirements.txt and virtual environment.

---

## Sources

- Direct codebase audit — `src/cloud_usage/dashboard/` routes, services, templates
  (HIGH confidence — code inspection of every file listed above)
- `src/cloud_usage/providers/ad/runner.py` — confirmed `run_ad_analysis()` return
  shape, `CloudResource` details fields for DNS zones, and absence of progress callback
  (HIGH confidence)
- `src/cloud_usage/dashboard/services/event_bridge.py` — confirmed `EventBridge` is
  generic, reusable; no AD-specific coupling (HIGH confidence)
- `src/cloud_usage/dashboard/templates/pages/summary.html` — confirmed
  `resource_type_breakdown` already rendered via `{% for rt, info in ... | sort %}`
  covering all resource types including v1.7 additions (HIGH confidence)
- `src/cloud_usage/nios/schema.py` — confirmed `NiosFamily.DNS_ZONE` exists;
  `raw_attrs["fqdn"]` key for zone FQDN is inferred from standard NIOS property
  naming (MEDIUM confidence — key name unverified against ZF backup; needs empirical
  check during implementation)
- `.planning/PROJECT.md` — Python-only constraint, no-charts decision, local execution
  model, AD provider status confirmed (HIGH confidence)
- `requirements.txt` — all current pinned versions confirmed (HIGH confidence)

---

*Stack research for: v1.8 Dashboard Analytics — AD tab, Top 5 DNS Zones panel, CLOUD-EXT-01*
*Researched: 2026-03-07*
