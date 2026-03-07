# Feature Research

**Domain:** Enterprise pre-sales licensing estimation tool — v1.8 Dashboard Analytics
**Researched:** 2026-03-07
**Confidence:** HIGH (grounded in existing codebase; no external dependencies)

---

## Scope

Three discrete feature areas for the v1.8 milestone. Each is analyzed independently because they have different scopes, dependencies, and complexity profiles. The tool already has NIOS Analysis (wizard + SSE + complete screen), Cloud Results (sortable attribution table + collapsible breakdowns), and Microsoft AD CLI (run_ad_analysis(), 12 CLI flags). v1.8 completes the AD dashboard experience and adds cross-source analytics depth.

---

## Feature Area 1: AD Dashboard Tab (AD-09 + AD-10)

### What It Is

A new tab ("Microsoft AD") in the existing HTMX tab bar that surfaces the Microsoft AD analysis as an in-browser wizard, mirroring what the NIOS Analysis tab does for NIOS Grid backups. The user configures a WinRM connection (host, port, credentials, auth mode), optionally enables DC autodiscovery, triggers the analysis, watches SSE progress, and sees results (DNS zones count, DHCP scopes, AD Users, token summary).

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Connection form — host, port, auth mode (Kerberos/NTLM), credentials | Every tool that connects to a remote service needs a connection form; NTLM requires username/password, Kerberos does not | MEDIUM | Must gate NTLM credential fields on auth mode selection; AdOptions validates this already; Kerberos is the default and requires no credentials |
| Autodiscovery toggle + seed server field | CLI already supports `--ad-autodiscover` and `--ad-discovery-server`; pre-sales engineers work in multi-DC forests where manual DC listing is impractical | LOW | Show/hide seed server field based on toggle state; mirrors existing wizard pattern from cloud scan wizard |
| Services scope selection (DNS / DHCP / Users) | CLI `--ad-services` already exposes this; dashboard form must be consistent with CLI capabilities | LOW | Checkbox group; values "dns", "dhcp", "user" — validated by AdOptions |
| SSE progress during analysis | NIOS tab already sets the expectation: long-running background operations show progress; AD analysis can take 30-120s against a live forest | MEDIUM | Needs new EventBridge (ad_event_bridge) and manager (AdScanManager) — same pattern as NiosEventBridge + NiosScanManager; AD pipeline has no discrete step count, so indeterminate bar is acceptable |
| Results summary — DNS zone count, DHCP scope count, AD user count, token total | The XLS report already contains this data; users need headline numbers without downloading a file | MEDIUM | run_ad_analysis() returns resources list; aggregate by resource_type ("ad-dns-zone", "ad-dhcp-scope", "ad-user") to get counts; token total from existing calculate_tokens() |
| Formula derivation inline (DDI ÷ 25 = X, IPs ÷ 13 = Y, Users ÷ 3 = Z) | Every other results screen in the tool shows inline formula derivation; AD results without it would be the only opaque results screen | LOW | Pattern already established by NIOS complete screen and Cloud Summary cards; AD resources use UDDI native divisors (25/13/3) |
| Download XLS CTA | NIOS tab has it; Cloud Summary tab has it; AD tab without a download button feels incomplete | LOW | Reuse existing /download/ route; run_ad_analysis() writes XLS when output_path is provided |
| Error display + retry | WinRM failures (auth, timeout, cert) are common in enterprise environments; user must be able to re-enter credentials and try again | LOW | Mirror NIOS error state: show error message + re-render connection form; AdOptions.__post_init__ validates inputs before any WinRM call |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Per-DC connection status during autodiscovery | When scanning a forest with 10+ DCs, users want to see each DC's status (connected / skipped / error) in real time, not just a spinner | HIGH | Would require per-DC SSE events; significant new complexity in collector.py; not needed for MVP |
| Token contribution breakdown by AD service (DNS tokens / DHCP tokens / User tokens) | Lets SE explain "why DNS contributes 80% of your AD tokens" before the customer asks | LOW | Computable from resources by resource_type category; add three sub-totals to the results screen |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Live WinRM credential test before submitting | "Test connection" button feels professional | Adds a separate WinRM round-trip that can itself time out or fail; the full analysis run is the implicit test; error paths multiply | Surface WinRM errors on the first real request; AdOptions validation catches malformed inputs before any network call |
| Saving/remembering AD server credentials | Users request it once they've typed credentials twice | Tool runs locally with no persistence layer; storing passwords on disk violates enterprise security policy; out of scope by design | Accept credentials fresh each session; keep form fields pre-populated only in app.state for the current process lifetime |
| Real-time record count while collecting | Feels responsive | AD collection is a single synchronous WinRM pipeline per DC; streaming partial counts requires refactoring the collector loop and emitting counts per-DC per-service | Show total counts on the complete screen after the pipeline finishes |

### Dependencies on Existing Code

- **AdOptions + run_ad_analysis()** already exist in `src/cloud_usage/providers/ad/`; the dashboard route will call `run_ad_analysis()` in `run_in_executor` (same pattern as `_run_nios_pipeline`).
- **EventBridge pattern** (`nios_event_bridge`) must be replicated as `ad_event_bridge`; must not be shared with cloud or NIOS SSE streams (SC-5 precedent established in `routes/nios.py` docstring).
- **NiosScanManager pattern** must be replicated as `AdScanManager` with the same state machine (idle/running/complete/error), output_path, and result storage.
- **Tab bar** (`partials/tab_bar.html`) needs a new "Microsoft AD" tab entry; `nios_state` is already passed via `_get_tab_context()`; `ad_state` must be added alongside it.
- **app.py** must initialize `ad_event_bridge` and `ad_manager` in `app.state` at startup.

---

## Feature Area 2: Top 5 DNS Zones Panel (per scope)

### What It Is

A new analytics panel showing the five DNS zones that contribute the most tokens for each data source (Cloud, AD). Rendered as a compact ranked list on the relevant results screen — not a full table. Answers the pre-sales question "which zones are costing the most?" without navigating to the Results tab.

### What "Top 5 DNS Zones" Means Per Scope

| Scope | DNS Zone Unit | Token Driver | Where Zone Name Lives |
|-------|--------------|-------------|----------------------|
| Cloud | Route53 hosted zone (AWS), Azure DNS zone (Azure), GCP Cloud DNS zone (GCP) | DDI tokens per zone object + DDI tokens for DNS records under it | `resource.name` for zone resource type; `resource.details["zone_name"]` for Route53 records (confirmed in `route53.py` line 121) |
| AD | AD DNS zone from Get-DnsServerZone | DDI tokens for the zone object + DDI tokens for all DNS records under it | `resource.details["zone"]` for `ad-dns-zone` resources; zone name = first `|`-delimited segment of `resource.details["record_key"]` for `ad-dns-record` resources |
| NIOS | DNS zone object (auth zone, stub, delegation) | DDI tokens; each zone object = 1 DDI | **Blocked:** `CountResult.per_family_ddi` is per object-family, not per-zone-name; no per-zone accumulator exists in the NIOS counter pipeline |

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Top 5 Cloud DNS zones panel on Summary tab after scan | Cloud scan collects zone resources (route53-zone, azure-dns-zone, gcp-dns-zone) and record resources; grouping records by parent zone is the natural next level of attribution below per-account | MEDIUM | Requires per-zone grouping: for each zone resource, count records with matching `details["zone_name"]` (AWS) or zone reference (Azure/GCP); per-zone token = ceil((zone_ddi_count + record_ddi_count) / 25). Azure/GCP zone name in details needs verification |
| Top 5 AD DNS zones panel on AD complete screen | AD runner creates `ad-dns-zone` and `ad-dns-record` resources; zone-to-record mapping is directly available from resource details | MEDIUM | Parse `ad-dns-record` resources: `zone_name = resource.details["record_key"].split("|")[0]`; group by zone; token = ceil((1 + record_count) / 25) per zone |
| Token count per zone shown (not just zone name) | A ranked list without numbers is not auditable; pre-sales engineers cite the specific token number when discussing a zone with a customer | LOW | Computed as part of the grouping; single integer to render |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Record count breakdown within the zone entry (zone itself + N records = M DDI → X tokens) | Shows exactly how the zone's token total was derived; eliminates "why does this zone cost so much?" follow-up | LOW | Already computed during the grouping pass; render as a secondary line below the zone name |
| Cross-scope zone name overlap indicator (same zone appears in Cloud + AD) | Identifies zones present in both cloud Route53 and AD — potential migration redundancy | HIGH | Requires zone name normalization across providers and a join across separate scan results; significant complexity; defer |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Configurable N (Top 3, Top 10) | Appears flexible | Adds a form element for minimal value; "Top 5" is a natural heuristic in pre-sales conversations | Hardcode to 5; label clearly as "Top 5 DNS Zones" |
| Full zone ranked table (all zones) | Complete data | Already available in the Results tab filtered by resource_type; duplicating it as a ranked table on Summary adds noise | The Top 5 panel links to the Results tab with a DNS zone type filter pre-applied |
| NIOS per-zone breakdown in v1.8 | Complete parity across all three sources | Blocked by NIOS pipeline gap: `count_objects()` in `nios/counter.py` accumulates per-family DDI totals, not per-zone-name counts. Wiring zone identity through the streaming filter pipeline is non-trivial and risks regressions on the validated NIOS pipeline | Scope NIOS per-zone to v1.9; v1.8 covers Cloud and AD only |

### Dependencies on Existing Code

- **Cloud scope:** `details["zone_name"]` confirmed in `route53.py` line 121 for `route53-record` resources. Zone resource type `route53-zone` stores zone name in `resource.name`. Azure and GCP zone name storage in `details` must be verified against their respective collector files before implementation.
- **AD scope:** `ad-dns-zone` resources have `details["zone"]`; `ad-dns-record` resources have `details["record_key"]` where zone is the first `|`-delimited segment. Both come from `run_ad_analysis()` output. No new collection needed.
- **NIOS scope:** Not feasible without pipeline changes. `CountResult` has `per_family_ddi` (dict keyed by family string, not by zone name). Adding per-zone tracking requires a new accumulator in `count_objects()` and changes to `CountResult`. Defer.
- **Summary tab route** (`tab_summary` in `pages.py`) already computes `per_account_details`; extending `_compute_summary()` to also return `per_zone_top5` for Cloud is additive.
- **AD complete screen** (new in v1.8) needs the zone panel as part of the initial results template; compute in the AD tab route after `run_ad_analysis()` completes.

---

## Feature Area 3: CLOUD-EXT-01 — Per-Account Attribution for v1.7 DDI Types

### What It Is

The per-account attribution table (Summary tab) already has a collapsible resource-type breakdown per account row. v1.7 added 26 new DDI types across AWS/Azure/GCP (15 AWS Route53 Resolver/IPAM/gateway/routing types, 5 Azure VNet gateway/Private Link/WANs/routing types, 6 GCP address/GKE/NAT/VPN types). These types are classified as "ddi" by the categorizer and will appear in the breakdown automatically — the data path is structurally correct. The gap is presentational: raw type strings ("aws-route53-resolver-endpoint") are dense and cryptic in a summary table designed for customer-facing conversations.

### What the Existing Code Does

`_compute_summary()` in `pages.py` builds `resource_type_breakdown` by iterating counted resources per account and grouping by `resource.resource_type`. The categorizer assigns `category="ddi"` to all v1.7 types (confirmed in `categorizer.py` lines 17-78). The breakdown renders in `summary.html` as `{{ rt }}: {{ info.count }} ({{ info.category | upper }})`. For a v1.7 scan with Route53 Resolver endpoints, IPAM pools, and Direct Connect gateways in the same account, this produces a flat list of opaque type strings.

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| All v1.7 DDI types appear in the collapsible breakdown for accounts that have them | Users who ran a v1.7 scan and see "aws-route53-resolver-endpoint" in the Results tab filter expect to find it in the Summary attribution breakdown | LOW | Already works structurally; requires only a test fixture to validate (no code changes to `_compute_summary()` or the categorizer) |
| Human-readable display names for v1.7 types in the breakdown | Raw type strings like "aws-route53-resolver-endpoint" or "gcp-gke-cidr-range" are not suitable for a customer-facing summary table | MEDIUM | A static `RESOURCE_TYPE_DISPLAY_NAMES` dict maps type strings to display names; used in the Jinja2 template via a filter or passed as context; similar to `_FAMILY_DISPLAY_NAMES` for NIOS families |
| DDI count per type shown inline | "Route53 Resolver Endpoint: 4 (DDI)" tells the SE how many resolver endpoints are contributing | LOW | Already rendered; count comes from `breakdown[rt]["count"]` |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Group v1.7 DDI types by functional category within the breakdown (e.g., "Route53 Resolver — 3 subtypes, 7 objects") | For AWS accounts with all 15 new DDI types, a flat list of 15 rows is hard to scan; grouping mirrors how engineers think about the environment | HIGH | Requires a static grouping map and additional template logic; borderline scope creep for v1.8; the display-name fix already addresses readability |
| Token contribution per DDI type (e.g., "4 resolver endpoints → 0.16 tokens") | Helps engineers explain IPAM or Direct Connect contribution in isolation | MEDIUM | Derivable from count + DDI divisor (25); additive to the breakdown row |

### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Edit/override counts per DDI type in the UI | Pre-sales engineers want "what-if" scenarios | Turns a read-only audit tool into an editor; undermines the "accurate, auditable" core value; creates liability if wrong numbers are exported | The XLS report is the edit surface; dashboard is read-only |
| Per-type sorting/filtering within the breakdown | Feels powerful | The breakdown is inside a `<details>` element scoped to one account row; sort controls inside it add DOM complexity disproportionate to value; the Results tab already provides full type-level filtering | Keep flat; Results tab provides filtering |

### Dependencies on Existing Code

- The data path in `_compute_summary()` already handles v1.7 types — no backend changes needed for the basic requirement.
- `RESOURCE_TYPE_DISPLAY_NAMES` is the main new artifact: a static dict in the template layer or as a context variable. The template currently renders `rt` directly; substituting a lookup is a one-line change.
- The categorizer (`categorizer.py`) already classifies all 26 v1.7 types as "ddi". No changes needed to the counting pipeline.
- The collapsible row template (`summary.html` lines 87-101) renders `rt` and `info.category`; display name substitution is purely a template change.

---

## Feature Dependencies

```
AD Dashboard Tab (AD-09)
    └──requires──> AdScanManager (new — mirrors NiosScanManager)
    └──requires──> ad_event_bridge (new EventBridge instance in app.state)
    └──requires──> /tab/ad route + pages/ad.html template (new)
    └──requires──> tab_bar.html updated with AD tab entry
    └──requires──> _get_tab_context() extended to include ad_state
    └──requires──> app.py startup initializes ad_manager + ad_event_bridge

AD SSE Progress (AD-10)
    └──requires──> AD Dashboard Tab (AD-09) [tab form submits to AD run route]
    └──uses──> run_ad_analysis() [already exists in providers/ad/runner.py]
    └──uses──> AdOptions [already exists in providers/ad/options.py]
    └──requires──> /api/sse/ad SSE endpoint (new)
    └──requires──> /ad/run POST route (new — dispatches run_ad_analysis in executor)

Top 5 DNS Zones — Cloud scope
    └──uses──> existing scan_manager.resources after scan complete
    └──requires──> per-zone grouping in _compute_summary() or a new helper
    └──requires──> Azure/GCP zone name in details [needs collector verification]

Top 5 DNS Zones — AD scope
    └──requires──> AD Dashboard Tab complete screen [shows on AD results screen]
    └──uses──> resources returned by run_ad_analysis() (ad-dns-zone + ad-dns-record)

Top 5 DNS Zones — NIOS scope
    └──requires──> CountResult per-zone-name accumulation [NOT YET BUILT]
    └──blocked by──> NIOS pipeline refactor (non-trivial scope, regression risk)
    └──DEFER to v1.9

CLOUD-EXT-01 v1.7 Type Display Names
    └──uses──> existing _compute_summary() data path [already correct]
    └──requires──> RESOURCE_TYPE_DISPLAY_NAMES dict (new, static)
    └──independent of AD tab and DNS zone panel
```

### Dependency Notes

- **AD tab requires isolated manager and event bridge:** The NiosScanManager/EventBridge isolation is the established pattern for preventing SSE cross-contamination (SC-5). Three separate pairs will exist: cloud, nios, ad. App.state must initialize all three at startup.
- **Top 5 DNS Zones (Cloud) requires zone_name in details:** Confirmed for Route53 (`route53.py` line 121). Azure (`azure-dns-zone`, `azure-private-dns-zone`) and GCP (`gcp-dns-zone`) zone name fields in details must be verified against their respective collector files before writing the per-zone grouping logic.
- **Top 5 DNS Zones (NIOS) is blocked:** `CountResult.per_family_ddi` is family-level, not zone-level. Adding per-zone tracking requires a new accumulator dict in `count_objects()` keyed by zone name, propagated through the streaming filter, and added as a new field on `CountResult`. This is a non-trivial change to the most performance-sensitive part of the NIOS pipeline and risks regressions on the validated ZF Friedrichshafen reference run.
- **CLOUD-EXT-01 is largely already working:** The collapsible breakdown data path is correct. The deliverable is display name polish plus a validation fixture to confirm v1.7 types surface correctly in a simulated scan.

---

## MVP Definition

This is a new milestone added to an already-shipped v1.7 product. "MVP" here means the minimum set that fully delivers the v1.8 milestone goal: AD is fully accessible from the dashboard, and the analytics panels surface zone-level and DDI-type-level token attribution.

### v1.8 Launch With

- [ ] **AD Dashboard Tab (AD-09):** Connection wizard (host, port, auth mode, credentials, services scope, autodiscovery toggle) — why essential: AD CLI has been in production since v1.7 with no dashboard surface; every other provider has a dashboard entry point
- [ ] **AD SSE Progress + Results (AD-10):** AdScanManager, ad_event_bridge, /api/sse/ad, complete screen with counts + formula derivation + download CTA + error state — why essential: without SSE, the UI blocks on a 30-120s synchronous analysis
- [ ] **Top 5 DNS Zones — Cloud scope:** Panel on Summary tab; top 5 Route53/Azure DNS/GCP zones by DDI token contribution — why essential: addresses "which zones cost the most?" for cloud customers; data is already available post-scan
- [ ] **Top 5 DNS Zones — AD scope:** Panel on AD complete screen; top 5 AD DNS zones by DDI contribution — why essential: AD forests often have dozens of zones; top-5 view adds immediate value; data directly available from run_ad_analysis() output
- [ ] **CLOUD-EXT-01:** Display names for v1.7 DDI types in per-account breakdown; validation that v1.7 types surface correctly — why essential: v1.7 shipped 26 new types that engineers now cite by name; raw type strings degrade the pre-sales audit experience

### Defer from v1.8

- [ ] **Top 5 DNS Zones — NIOS scope:** Blocked by NIOS pipeline refactor; adds regression risk to the most validated part of the codebase; defer to v1.9
- [ ] **Per-DC connection status during AD autodiscovery:** High complexity; requires per-DC SSE events and collector refactoring; not needed for core AD dashboard
- [ ] **Functional grouping of v1.7 DDI types in breakdown:** Useful for large AWS accounts; adds template complexity; the display-name fix already addresses readability in v1.8
- [ ] **Cross-scope zone overlap detection (Cloud + AD):** High complexity; no immediate pre-sales demand; future milestone

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| AD Dashboard Tab — wizard | HIGH | MEDIUM | P1 |
| AD SSE Progress + results screen | HIGH | MEDIUM | P1 |
| Top 5 DNS Zones — Cloud | HIGH | MEDIUM | P1 |
| Top 5 DNS Zones — AD | MEDIUM | LOW | P1 |
| CLOUD-EXT-01 display names + verification | MEDIUM | LOW | P1 |
| Top 5 DNS Zones — NIOS | MEDIUM | HIGH | P3 |
| Per-DC AD autodiscovery progress | LOW | HIGH | P3 |
| v1.7 DDI type functional grouping | LOW | MEDIUM | P3 |
| Cross-scope zone overlap detection | LOW | HIGH | P3 |

**Priority key:**
- P1: Required for v1.8 milestone completion
- P2: Improves usability noticeably; add when P1 features are stable
- P3: Nice to have; defer until user feedback confirms demand

---

## Sources

- `src/cloud_usage/providers/ad/runner.py` — AD pipeline output shape (resources list, aggregation, CloudResource types for ad-dns-zone/ad-dns-record/ad-dhcp-scope/ad-user)
- `src/cloud_usage/providers/ad/options.py` — AdOptions fields; auth mode validation; services tuple; autodiscovery fields
- `src/cloud_usage/providers/ad/constants.py` — AD_SERVICES = ("dns", "dhcp", "user")
- `src/cloud_usage/dashboard/routes/nios.py` — SSE + EventBridge + manager pattern to replicate for AD tab (NiosScanManager, nios_event_bridge, /api/sse/nios, /api/nios/progress)
- `src/cloud_usage/dashboard/routes/pages.py` — `_compute_summary()` data path; confirms CLOUD-EXT-01 already works structurally; `_get_tab_context()` extension point for ad_state
- `src/cloud_usage/dashboard/templates/partials/tab_bar.html` — confirmed four existing tabs (Progress, Results, Summary, NIOS Analysis); AD tab is the fifth entry
- `src/cloud_usage/dashboard/templates/partials/nios/complete.html` — NIOS complete screen pattern to mirror for AD results
- `src/cloud_usage/providers/aws/collectors/route53.py` line 121 — confirms `details["zone_name"]` exists for route53-record resources
- `src/cloud_usage/counting/categorizer.py` lines 17-78 — confirms all 26 v1.7 DDI types are classified as "ddi"; no categorizer changes needed for CLOUD-EXT-01
- `src/cloud_usage/nios/counter.py` — confirms `CountResult.per_family_ddi` is family-level with no per-zone accumulator; establishes the blocker for NIOS Top 5 DNS Zones
- `.planning/PROJECT.md` — v1.8 milestone requirements (AD-09, AD-10, Top 5 DNS Zones, CLOUD-EXT-01), existing feature set, constraints

---
*Feature research for: Infoblox Universal DDI Cloud Usage Estimator — v1.8 Dashboard Analytics*
*Researched: 2026-03-07*
