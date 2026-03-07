# Pitfalls Research

**Domain:** FastAPI + HTMX dashboard — adding AD tab, multi-source DNS zone panel, and expanded DDI attribution (v1.8)
**Researched:** 2026-03-07
**Confidence:** HIGH — derived from direct codebase inspection of all affected files

---

## Critical Pitfalls

### Pitfall 1: AD EventBridge Shared With Cloud Scan or NIOS

**What goes wrong:**
A third `EventBridge` is required for AD SSE. If the AD pipeline reuses
`app.state.event_bridge` (cloud) or `app.state.nios_event_bridge` (NIOS),
`scan_complete` / `nios_complete` events from a cloud or NIOS run will
prematurely close the AD SSE stream. The pattern precedent from `routes/nios.py`
is explicit: SC-5 forbids cross-source EventBridge sharing. This is an easy
copy-paste error when wiring `app.py`.

**Why it happens:**
Developer copies the NIOS route bootstrap from `app.py` but wires
`app.state.nios_event_bridge` into the new AD route instead of creating
`app.state.ad_event_bridge`. No runtime error fires — the stream just
closes at the wrong moment.

**How to avoid:**
In `app.py` lifespan: create `ad_event_bridge = EventBridge()`, await
`ad_event_bridge.start()`, assign to `app.state.ad_event_bridge`. Create
`AdScanManager()`, assign to `app.state.ad_manager`. Register both in
shutdown. Name everything `ad_*` by convention. Test: assert that a cloud
`scan_complete` event does NOT close the AD SSE stream.

**Warning signs:**
- AD tab freezes after a cloud scan completes
- AD progress disappears when NIOS analysis finishes
- A single `emit_done()` call closes all three SSE streams

**Phase to address:** AD Dashboard Tab phase (first AD UI phase)

---

### Pitfall 2: Race Condition — AD Pipeline Finishes Before SSE Connection Opens

**What goes wrong:**
The AD autodiscovery pipeline can be fast for small forests (a handful of
DCs, no WinRM latency in mocks). The background thread calls `emit_done()`
before the browser opens `GET /api/sse/ad`. The completion event is emitted
to an empty subscriber list and silently dropped. The browser SSE stream
opens, subscribes, and waits forever — the completion trigger never fires,
the tab never refreshes to show results.

**Why it happens:**
This exact bug exists in the NIOS SSE path and was already fixed (see
`sse_nios()` in `routes/nios.py`, lines 384–387): the guard checks
`nios_manager.state in (COMPLETE, ERROR)` and immediately yields
`nios_complete` if the pipeline already finished. The AD SSE route must
replicate this guard or the race silently breaks fast pipelines.

**How to avoid:**
In the AD SSE route: before subscribing to `ad_event_bridge`, check
`ad_manager.state in (COMPLETE, ERROR)`. If true, yield
`event: ad_complete\ndata: {}\n\n` immediately and return. Unit test:
run the AD pipeline synchronously, then open `/api/sse/ad`, assert
`ad_complete` arrives immediately without hanging.

**Warning signs:**
- AD tab spinner never resolves when the forest is small / WinRM is fast
- Works in development (slow mocked WinRM) but breaks in production (fast LAN)
- Tab only refreshes if you navigate away and back

**Phase to address:** AD Dashboard Tab phase

---

### Pitfall 3: SSE Keepalive Missing From New AD SSE Endpoint

**What goes wrong:**
`EventBridge.subscribe()` sends `: keepalive\n\n` every 25 seconds (line 86
in `event_bridge.py`). If a new AD SSE generator is written inline in the
route without the `asyncio.wait_for(..., timeout=25.0)` pattern, connections
through nginx or any reverse proxy drop after 60 seconds. AD WinRM collection
against a large forest (dozens of DCs) can take 3–5 minutes.

**Why it happens:**
Developer writes a custom `event_generator()` that reads directly from the
janus queue, or duplicates only part of the `subscribe()` pattern, omitting
the timeout/keepalive.

**How to avoid:**
Reuse `ad_event_bridge.subscribe()` exactly as the NIOS route does — do not
write a custom generator. The keepalive is inside `EventBridge.subscribe()`
already; it is not a route-level concern. Verify the three SSE headers are
present: `Cache-Control: no-cache`, `Connection: keep-alive`,
`X-Accel-Buffering: no`.

**Warning signs:**
- AD scan works on direct localhost but hangs through a reverse proxy
- Connection drops at exactly 60 seconds (nginx default read timeout)

**Phase to address:** AD Dashboard Tab phase

---

### Pitfall 4: AdScanManager Fields Copied From NiosScanManager Without Adaptation

**What goes wrong:**
If `AdScanManager` is created by copy-pasting `NiosScanManager` without
removing NIOS-specific fields (`_scenario_suite`, `_family_breakdown`,
`_current_progress` hardcoded to `total: 6`), the state manager becomes
misleading. Worse: if the developer stores state as module-level globals
instead (no manager class), concurrent calls corrupt state and the
architecture becomes untestable.

**Why it happens:**
The AD pipeline step count is unknown until implementation. Developers
stub `total: 1` to unblock work and forget to update it. NIOS-specific
fields are left in because "they don't hurt."

**How to avoid:**
Define the AD pipeline steps concretely first: (1) Validate options,
(2) Connect to seed DC / discover forest, (3) Collect per-DC data,
(4) Aggregate + convert to CloudResource, (5) Categorize + write XLS.
Use `total: 5`. Carry only AD-specific fields: `_resources`, `_errors`,
`_output_path`, `_dc_progress: list[dict]` for per-DC status. Remove
`_scenario_suite` and `_family_breakdown` entirely.

**Warning signs:**
- Progress bar shows wrong denominator (step 3 of 6 when 5 steps exist)
- Jinja2 template throws `AttributeError` accessing `scenario_suite` on
  the AD manager

**Phase to address:** AD Dashboard Tab phase

---

### Pitfall 5: DNS Zone "Name" Extraction Differs Across All Three Sources

**What goes wrong:**
The Top 5 DNS Zones panel needs a zone name string from three different
data shapes:

- **Cloud (Azure/GCP/AWS):** `CloudResource.name` — already a zone FQDN
  (confirmed: `azure-dns-zone`, `gcp-dns-zone`, `route53-zone` all set
  `name` to the zone FQDN in their respective collectors)
- **AD:** `CloudResource.details['zone']` for `ad-dns-zone` resources
  (set in `runner.py` `_to_cloud_resources()` — `name` is also the zone
  name here, so `resource.name` works too for AD zones)
- **NIOS:** Zone names are **not available** anywhere in the current
  dashboard pipeline. `NiosScanManager` stores only `scenario_suite` and
  `family_breakdown`. NIOS zone objects (`NiosFamily.DNS_ZONE`) are
  parsed-and-counted during `count_objects()`, then discarded — individual
  zone FQDNs are never persisted to dashboard state. The `per_family_ddi`
  dict shows a total DDI count for `DNS_ZONE`, not a list of zone names.

**Why it happens:**
Developer builds the panel against cloud resources (where `resource.name`
works), sees it work for all cloud and AD sources, and does not realize
NIOS zones are absent from `scan_manager.resources` entirely. NIOS uses a
separate parsing pipeline that never produces `CloudResource` objects.

**How to avoid:**
For cloud + AD: filter `scan_manager.resources` for `resource_type in
{"route53-zone", "azure-dns-zone", "azure-private-dns-zone", "gcp-dns-zone",
"ad-dns-zone"}`, use `resource.name`.

For NIOS: add `_dns_zone_names: list[str]` to `NiosScanManager`, populated
during `_run_nios_pipeline` by collecting zone names from the
`NiosFamily.DNS_ZONE` stream inline during step 3. This is a targeted
pipeline addition — the stream is already being consumed, just not saving
names. If this is deferred, show the zone count only:
"N DNS zones (names not available in current release)."

**Warning signs:**
- NIOS "Top 5 DNS Zones" section is empty even after successful NIOS analysis
- AD zones show correctly but NIOS section is blank
- Console shows `KeyError: 'zone'` when iterating NIOS resources (NIOS zones
  are never in `scan_manager.resources` — this error means wrong data source)

**Phase to address:** Top 5 DNS Zones phase

---

### Pitfall 6: "Top 5 DNS Zones by Token Contribution" Is Meaningless — Records Are the Signal

**What goes wrong:**
The feature says "token consumption breakdown." If implemented as "top 5 zones
ranked by their DDI token contribution," every DNS zone contributes exactly
`1 DDI ÷ 25 = 0.04 tokens` (cloud/AD) or `1 DDI ÷ 50 = 0.02 tokens` (NIOS).
The ranking is arbitrary — all zones tie. No useful insight is produced.

**Why it happens:**
"Token consumption breakdown" implies a proportional attribution. But the
volume driver for DNS-related tokens is DNS *records* (each record is 1 DDI),
not DNS *zones* (each zone is also 1 DDI regardless of record count). The
high-value insight is: which zones have the most records, because records
scale with the customer's actual DNS footprint.

**How to avoid:**
Define "Top 5 DNS Zones" as "Top 5 zones by DNS record count." Group
`route53-record` / `azure-dns-record` / `gcp-dns-record` / `ad-dns-record`
resources by their parent zone (extractable from `resource.details['zone']`
or by parsing the zone out of the resource name). Count records per zone.
Take top 5. Annotate each entry with: zone name, record count, DDI
contribution (`record_count ÷ 25`), source label. This is computable from
existing `scan_manager.resources` without any new pipeline.

**Warning signs:**
- Panel displays `0.04 tokens` for every zone (all zones tied)
- Ranking changes randomly on each page load because tied sort is unstable

**Phase to address:** Top 5 DNS Zones phase

---

### Pitfall 7: Attribution Table Becomes Unreadable After 26 New v1.7 DDI Types

**What goes wrong:**
The per-account breakdown `resource_type_breakdown` in `_compute_summary()`
already groups all DDI types for each account's collapsible `<details>` row.
Adding 26 new v1.7 DDI types (15 AWS, 5 Azure, 6 GCP) means an AWS account
breakdown expands to 20+ resource type lines. At 100 accounts × 20+ types,
the table body is a wall of raw type strings (`aws-resolver-rule-association`,
`aws-ipam-resource-discovery-association`, etc.) with no human-readable
labels. The UX regresses silently — no breakage, just unreadable output.

**Why it happens:**
The `resource_type_breakdown` design was built for ~5 DDI types per provider
(v1.4). After v1.7 adds 26 new types, the same `{% for rt, info in ... %}`
loop expands without any grouping or labeling. The template does not know
these are new types.

**How to avoid:**
Before surfacing per-account rows for new types, introduce a
`DDI_TYPE_DISPLAY_NAMES` dict in `categorizer.py` (alongside `DDI_TYPES`)
mapping technical type strings to human labels:
`"aws-resolver-rule-association": "Route53 Resolver Rule Association"`.
In `_compute_summary()`, replace raw `rt` keys in `resource_type_breakdown`
with display names, or pass the mapping to the template. At minimum, sort
by count descending so high-count types appear first, and add a group header
(e.g., "Route53 Resolver", "IPAM", "Networking") to bucket related types.

**Warning signs:**
- Collapsible breakdown expands to 15+ lines for any AWS account
- Customers ask what `aws-resolver-rule-association` means during a sales review

**Phase to address:** CLOUD-EXT-01 (per-account DDI attribution) phase

---

### Pitfall 8: Tab Bar Missing `ad_state` Causes UndefinedError on All Tabs

**What goes wrong:**
`_get_tab_context()` in `pages.py` currently passes `nios_state` to the
template for the NIOS tab badge. Adding an AD tab to `tab_bar.html` that
references `{{ ad_state }}` will throw Jinja2 `UndefinedError` on every
tab navigation if `_get_tab_context()` is not updated to include
`"ad_state": ad_manager.state.value`. This breaks ALL tabs, not just the
AD tab — `_get_tab_context()` is called by every tab route.

**Why it happens:**
Developer adds the AD tab link to `tab_bar.html` but forgets that
`_get_tab_context()` is the single shared context-builder for all tabs. The
template is updated; the backend is not.

**How to avoid:**
Update `_get_tab_context()` to read `ad_manager = request.app.state.ad_manager`
and include `"ad_state": ad_manager.state.value`. Every tab route
automatically receives `ad_state` once this function is updated — there are
5 callers (`index`, `tab_progress`, `tab_results`, `tab_summary`, `tab_nios`).
Add `tab_ad()` as a 6th caller. Test: navigate to each tab after an AD scan
completes and assert the badge renders without errors.

**Warning signs:**
- Jinja2 `UndefinedError: 'ad_state' is undefined` on any tab navigation
- The error appears on the NIOS tab, not just the AD tab (all tabs share `tab_bar.html`)

**Phase to address:** AD Dashboard Tab phase

---

### Pitfall 9: AD Credentials Logged or Persisted in Manager State

**What goes wrong:**
`AdOptions` is a frozen dataclass. Python's default `__repr__` for dataclasses
includes all fields — including `password`. If `AdOptions` is logged at any
level (debug, info, or exception), the WinRM password appears in server stdout
or log files. Additionally, if `AdScanManager` stores credentials (mirroring
how `NiosScanManager` stores `_upload_path`), the password lives in process
memory indefinitely and is accessible via `app.state.ad_manager`.

**Why it happens:**
Developers add `logger.debug("Starting AD analysis with options: %s", options)`
without thinking about the repr content. This is especially likely in
exception handlers: `logger.exception("AD pipeline failed: %s", exc)` where
`exc` may include the options object in its message.

**How to avoid:**
Add a `__repr__` override or `__str__` to `AdOptions` that masks the password:
`password='[REDACTED]'`. Never store `password` in `AdScanManager` state beyond
the single `run_ad_analysis()` call. Log only `auth_mode`, `servers`, and
`services`. Mark the password form field with `type="password"` and
`autocomplete="current-password"`. Test: run an NTLM connection attempt with
a known test password and grep all log output for that string.

**Warning signs:**
- Test logs show raw password strings in `AdOptions` repr output
- `AdScanManager` has a `_password` or `_credentials` field

**Phase to address:** AD Dashboard Tab phase

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode `total: 5` in `AdScanManager` before pipeline steps confirmed | Unblocks template development | Progress bar denominator wrong if steps change | Never — confirm steps first; one-line fix |
| Store AD result summary as raw `dict` in `AdScanManager` (not typed dataclass) | Faster to implement | Template `AttributeError` surfaces at render time, not test time | Acceptable for v1.8 MVP; replace with typed class in v1.9 |
| Derive NIOS DNS zone names via a second parse pass at panel render time | Simple, no pipeline changes | 30–120 second panel load for 2 GB backups on every tab switch | Never — pre-compute in `_run_nios_pipeline`, cache in `NiosScanManager` |
| Use `resource.name` for DNS zone display name across all sources without source-awareness | Works for cloud DDI types | NIOS zones not in `scan_manager.resources` at all — silently empty | Never — write source-aware extraction once |
| Module-level globals for AD state (no `AdScanManager`) | Zero new classes | Untestable; concurrent requests corrupt state | Never — the existing `ScanManager` / `NiosScanManager` pattern is the precedent |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| HTMX SSE + AD completion | Using `sse-swap` to swap content directly from the completion SSE event payload | Use `hx-trigger="sse:ad_complete"` + `hx-get="/tab/ad"` for a full tab refresh — mirrors NIOS pattern exactly; completion event payload is empty `{}` |
| `AdOptions` frozen dataclass + form POST | Treating absent form checkbox (`skip_cert_validation`) as falsy via `bool(form.get(...))` | Unchecked HTML checkboxes send no value — use `form.get("skip_cert_validation") == "on"` |
| AD pipeline in background thread | Calling `asyncio.to_thread()` (Python 3.10+ only) | Use `loop = asyncio.get_running_loop(); loop.run_in_executor(None, _run_ad_pipeline, ...)` — codebase targets Python 3.9 |
| DNS zone extraction for Top 5 panel | Querying NIOS zone names at render time via `get_member_map()` again | Pre-compute zone name list during `_run_nios_pipeline` step 3; store in `NiosScanManager._dns_zone_names` |
| CLOUD-EXT-01 new DDI type rows | Adding new `<tr>` elements next to `acct-row` for each new type | New types already flow into `resource_type_breakdown` dict via `_compute_summary()` — no new row structure needed, only display-name mapping |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| DNS Zones panel re-parses NIOS backup on every tab load | 30–120s panel load for 2 GB backups | Cache zone names in `NiosScanManager` after first parse; panel reads cache | Every load of DNS Zones panel if names are not pre-computed |
| `_compute_summary()` called on every Summary tab switch | Slow tab switches with 50,000+ resources | Memoize or cache result keyed on `len(resources)` | ~50,000+ resources (100 accounts × 500 resources is achievable post-v1.7) |
| Attribution table renders 100+ accounts × 20+ DDI type rows | Jinja2 takes 2–5s; browser DOM scroll lag | Group DDI types by category in `_compute_summary()`; limit breakdown to top 10 types per account | Any AWS scan with 50+ accounts and v1.7 DDI types |
| AD autodiscovery scans all DCs sequentially with no progress feedback | AD tab spinner for 5–10 minutes for large forests | Emit per-DC SSE progress events; `AdScanManager._dc_progress` list updated per DC | Forests with 20+ DCs |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `logger.debug("options: %s", options)` where `options` is `AdOptions` with NTLM password | Password in server logs or stdout | Add `AdOptions.__repr__` that returns `password='[REDACTED]'`; never log the options object directly |
| Storing WinRM password in `AdScanManager` state | Password lives in process memory indefinitely; accessible via `app.state` | Pass credentials to `run_ad_analysis()` only; do not retain in manager after pipeline completes |
| AD form binds to non-loopback address without origin check | CSRF from a malicious browser tab on same machine | Tool runs locally — low risk; still, validate `Origin` header on AD POST endpoint if server ever binds to non-loopback |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| AD wizard shows no feedback during slow WinRM connections | User clicks "Connect" and sees a spinner for 90+ seconds with no indication of progress | Emit granular SSE steps: "Connecting to DC1", "Running Get-ADForest", "Collecting DNS zones" — mirrors NIOS step labels |
| "Top 5 DNS Zones" shows zones from all sources mixed with no source label | User cannot tell if a zone is from NIOS, AWS Route53, or AD | Add a "Source" column (NIOS / AWS / Azure / GCP / AD) with color-coding or group by source |
| AD tab shows "idle" even though AD analysis already ran this session | User thinks they need to re-run to see results | Mirror NIOS tab: check `ad_manager.state` on load — if COMPLETE, show results directly |
| Attribution table breakdown uses raw type strings (`aws-resolver-rule-association`) | Enterprise customers cannot interpret type names during a sales review | Add `DDI_TYPE_DISPLAY_NAMES` dict mapping technical strings to human labels; use in template |

---

## "Looks Done But Isn't" Checklist

- [ ] **AD SSE race guard:** Verify `sse_ad()` checks `ad_manager.state in (COMPLETE, ERROR)` and emits `ad_complete` immediately — test by running pipeline before opening SSE connection
- [ ] **AD EventBridge isolation:** Verify a cloud `emit_done()` does NOT close the AD SSE subscriber — write a test where cloud scan completes and assert AD subscriber list is unchanged
- [ ] **Tab bar `ad_state`:** Verify every tab route passes `ad_state` — navigate to each tab after an AD scan completes and check the badge renders without Jinja2 errors
- [ ] **NIOS DNS zone names stored:** Verify `NiosScanManager` has `_dns_zone_names` populated after a NIOS analysis — inspect the attribute after a test run; it must not be empty when NIOS backup contains DNS zones
- [ ] **AD resources in attribution table:** Verify `ad-dns-zone`, `ad-dns-record`, `ad-dhcp-scope` appear in the per-account breakdown after an AD scan — AD `account_id` is the domain name (not a cloud account ID), confirm it renders correctly
- [ ] **AD password not logged:** Verify server stdout contains no password strings after an NTLM connection attempt — run with `--log-level debug` and grep for the test password
- [ ] **CLOUD-EXT-01 new types visible per account:** Verify that a post-v1.7 AWS scan shows `aws-resolver-endpoint`, `aws-route-table` etc. in the collapsible breakdown with human-readable labels — these are new in v1.7 and were not tested in v1.4's attribution design

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Shared EventBridge breaks AD SSE | MEDIUM | Add `ad_event_bridge` to `app.py` lifespan; update AD route handlers; 2–3 file changes |
| SSE race condition causes AD tab to hang | LOW | Add 4-line guard to `sse_ad()` route matching the pattern in `sse_nios()` |
| NIOS DNS zone names not stored | MEDIUM | Add `_dns_zone_names: list[str]` to `NiosScanManager`; populate during pipeline step 3 inline over `NiosFamily.DNS_ZONE` objects |
| Attribution table unreadable with 20+ types | MEDIUM | Add `DDI_TYPE_DISPLAY_NAMES` to `categorizer.py`; add grouping in `_compute_summary()`; template changes are additive |
| AD credentials logged | HIGH (security) | Audit all log calls in AD route and pipeline; add `AdOptions.__repr__` mask immediately |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| AD EventBridge shared with cloud or NIOS | AD Dashboard Tab | Test: cloud `emit_done()` does not close AD SSE subscriber |
| SSE race condition (pipeline beats SSE connection) | AD Dashboard Tab | Test: run pipeline, delay SSE open 100ms, assert `ad_complete` arrives immediately |
| SSE keepalive missing | AD Dashboard Tab | Test: no message for 30s, assert keepalive comment `": keepalive"` received |
| `AdScanManager` fields wrong or NIOS-specific | AD Dashboard Tab | Test: `AdScanManager` has no `_scenario_suite` / `_family_breakdown` fields |
| DNS zone name extraction per source | Top 5 DNS Zones | Test: NIOS zone names in `nios_manager._dns_zone_names` after parse; cloud zones via `resource.name`; AD zones via `resource.name` or `resource.details['zone']` |
| Token attribution misunderstood — records are the signal | Top 5 DNS Zones | Design review before implementation: confirm panel ranks zones by record count, not zone-level DDI contribution |
| Attribution table overwhelmed with 20+ types | CLOUD-EXT-01 | Manual review: open attribution table after scanning 10+ AWS accounts with v1.7 DDI types; count breakdown lines per account |
| Tab bar missing `ad_state` | AD Dashboard Tab | Test: navigate to every tab after AD scan completes, assert no Jinja2 `UndefinedError` |
| AD credentials logged | AD Dashboard Tab | Test: NTLM connection attempt with known password; grep all log output for that string |

---

## Sources

- Direct inspection: `src/cloud_usage/dashboard/services/event_bridge.py` (EventBridge fan-out, keepalive at line 86)
- Direct inspection: `src/cloud_usage/dashboard/routes/nios.py` (race-condition guard in `sse_nios()` lines 384–387; SC-5 comment)
- Direct inspection: `src/cloud_usage/dashboard/app.py` (lifespan pattern — two independent EventBridge instances for cloud and NIOS)
- Direct inspection: `src/cloud_usage/dashboard/routes/pages.py` (`_get_tab_context()` shared by all tab routes; `_compute_summary()` attribution table logic)
- Direct inspection: `src/cloud_usage/dashboard/templates/pages/summary.html` (attribution table with `<details>` breakdown and IIFE sort)
- Direct inspection: `src/cloud_usage/dashboard/templates/partials/tab_bar.html` (`nios_state` variable dependency pattern)
- Direct inspection: `src/cloud_usage/providers/ad/runner.py` (zone name in `details['zone']` at `_to_cloud_resources()` line 277)
- Direct inspection: `src/cloud_usage/counting/categorizer.py` (`DDI_TYPES` — 26 new v1.7 types now in set; no `DDI_TYPE_DISPLAY_NAMES` dict exists yet)
- Direct inspection: `src/cloud_usage/nios/counter.py` + `schema.py` (NIOS zone objects counted as aggregate in `per_family_ddi`, no per-zone name list stored anywhere in dashboard state)
- Project context: `.planning/PROJECT.md` (SC-5 constraint, v1.8 feature list, technical debt items, AD-LIVE caveat)

---
*Pitfalls research for: FastAPI+HTMX dashboard v1.8 (AD Tab, DNS Zones panel, CLOUD-EXT-01)*
*Researched: 2026-03-07*
