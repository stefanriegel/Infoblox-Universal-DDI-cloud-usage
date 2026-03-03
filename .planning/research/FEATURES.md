# Feature Research

**Domain:** Audit-depth attribution tables — "explain how the number was derived" UI for enterprise pre-sales token estimation tool (WebUI, HTMX + FastAPI)
**Researched:** 2026-03-03
**Confidence:** HIGH — findings drawn directly from the existing codebase, existing XLS output that already implements these patterns, PROJECT.md milestone definition, and the enterprise audit context documented in CLAUDE.md.

---

## Context: What This Milestone Adds

This is v1.4 of an existing, validated tool. The core computation already runs and produces correct numbers. What is missing is the WebUI's ability to fully explain those numbers without the user opening the XLS report. Two surfaces need audit-depth treatment:

1. **Cloud per-account attribution tables** — the Summary tab already shows a `per_account_details` list (`account_id`, `provider`, `ddi_count`, `ip_count`, `asset_count`, `total_tokens`) computed by `_compute_summary()`. It does not show formula derivation or resource-type breakdown per account.

2. **NIOS object family breakdown** — the XLS report already has an "Object Counters" sheet with all 26 NIOS families, counts, and "Counted in UDDI" flags. The NIOS complete screen in the WebUI shows scenario cards and member attribution but does not surface any object-family breakdown.

Both features answer the same question: "Where exactly does that token number come from?" That question is the primary source of customer distrust in pre-sales licensing conversations.

---

## What Already Exists (Do Not Re-Implement)

### Cloud side — already in WebUI
- Summary tab: `per_account_details` list (`account_id`, `provider`, `ddi_count`, `ip_count`, `asset_count`, `total_tokens`) — correct data, missing formula and resource-type breakdown
- Summary tab: `per_provider_details` table (Provider, Accounts Scanned, DDI, IPs, Assets, Tokens)
- Results tab: full paginated resource-level table with `resource_type`, `category`, `counted`, `skip_reason` per row
- `_compute_summary()` in `pages.py` already groups resources by account and calls `calculate_account_tokens()` + `deduplicate_ips_per_vpc()`

### NIOS side — already in WebUI
- Complete screen: scenario cards with inline formula derivation (DDI ÷ 50 = X.X, etc.)
- Complete screen: per-member attribution table (member, group, DDI objects, Active IPs, token contribution)
- XLS: Object Counters sheet (family, object count, counted in UDDI flag, reason) — all 26 families
- XLS: DDI Objects sheet (DDI families only, NIOS/UDDI token contribution per family)
- `IntegrityReport.families_found` dict — already computed during analysis, keys = family name strings, values = raw object counts

### Data available but not yet surfaced in WebUI
- Cloud: resource-type breakdown per account is computable from `scan_manager.resources` — group by `(account_id, resource_type, category)` in `_compute_summary()`
- Cloud: formula derivation (DDI ÷ 25, IPs ÷ 13, Assets ÷ 3) with inline math is straightforward from existing counts — divisors are constants in `token_calculator.py`
- NIOS: `integrity_report` is available inside `_run_nios_pipeline()` but not stored on `NiosScanManager` — currently only `scenario_suite` is retained post-analysis; `integrity_report` (which contains `families_found`) is not passed to `set_complete()`

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features an enterprise audit tool must have for the "explain the number" screen to be credible. If any of these are missing, the user still needs to open the XLS — which defeats the purpose of the WebUI.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Per-account formula derivation (cloud)** | The top-line token number is meaningless without its derivation. Enterprise customers and their security teams expect to see the arithmetic, not just the result. "2,450 tokens" needs to become "614 DDI ÷ 25 = 24.6 + 8,127 IPs ÷ 13 = 625.2 + 45 Assets ÷ 3 = 15.0 → 665 tokens" inline. | LOW | Divisor constants are already in `token_calculator.py`. Template already does this for NIOS scenario cards — same pattern applies to cloud per-account rows. Data is already in `per_account_details`. |
| **Per-account resource-type count breakdown (cloud)** | Within a single AWS account or Azure subscription, customers need to see "how many VMs, how many subnets, how many DNS zones contributed to the DDI count." Without this, "614 DDI objects" is opaque — it could be all VMs or all subnets and the customer cannot validate it. | MEDIUM | Requires grouping `scan_manager.resources` by `(account_id, resource_type, category)` in `_compute_summary()`. New field `resource_type_breakdown` on each per-account entry — list of `{resource_type, category, count}` dicts. Template renders as a nested sub-table or collapsible `<details>` block per account row. |
| **Skipped vs. counted split per account (cloud)** | Enterprise customers will immediately ask "why is this account contributing fewer DDI objects than that one?" The answer is almost always in the skip reasons. Showing counted and skipped counts per account lets the SE explain it without navigating the Results tab. | MEDIUM | Extend the resource-type breakdown to include skipped resources. Each entry: `{resource_type, category, counted_count, skipped_count, skip_reason_sample}`. Skipped rows with no category are currently represented in Results tab but not in summary. |
| **NIOS object family breakdown table (non-zero families)** | The member attribution table shows who contributed. The object family table shows what was counted — which of the 26 NIOS families actually had objects, which counted as DDI, which were IP-only sources. Without this, the total DDI count is an unexplained integer. The XLS "Object Counters" sheet is the reference. | MEDIUM | `IntegrityReport.families_found` is already computed in the pipeline. Needs to be stored on `NiosScanManager` at `set_complete()` time alongside `scenario_suite`. Template renders a table filtered to non-zero families only, with a "Counted in UDDI" column and reason for families that do not count. |
| **Grand total reconciliation row (cloud per-account)** | The sum of per-account tokens must visually reconcile with the grand total shown in the summary cards. If the numbers don't add up (e.g., due to ceiling division rounding), the user will lose trust. A "Total" row at the bottom of the per-account table, matching the summary card, is required. | LOW | Already computable from existing `per_account_details`. Template adds a `<tfoot>` row with column sums. Ceiling division rounding means the sum of per-account tokens may differ from the grand total (which uses aggregate counts); this needs a footnote. |
| **DDI-only family subtotal (NIOS)** | The object family breakdown should clearly distinguish which families contribute to DDI tokens and what their contribution is. A subtotal row for "DDI families only" with the total DDI count lets the customer reconcile the family table against the scenario totals. | LOW | `_DDI_FAMILIES` frozenset is already defined in `counter.py` and used in `output.py`. Template filters families by membership in this set and shows a subtotal. |
| **Informational-only family explanation (NIOS)** | Non-DDI families (member, lease, fixed_address, host_address) confuse customers — "why is LEASE not counted?" Each non-DDI family needs a brief reason. The XLS already has a "Reason" column with values from `_UDDI_FLAG_REASON`. This must appear in the WebUI too. | LOW | `_UDDI_FLAG_REASON` dict already exists in `output.py`. Pass to template or hardcode in template (template-side is simpler — reasons are immutable spec constants). |

### Differentiators (Competitive Advantage)

Features that go beyond what the XLS already provides, adding real audit value that the spreadsheet format cannot easily express.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Collapsible per-account resource-type rows** | Large cloud scans (100+ accounts) produce attribution tables too long to scan. Collapsible `<details>` blocks per account — showing summary by default, expanding to resource-type detail on click — let users focus on outliers without scrolling past irrelevant accounts. | LOW | Pure HTML `<details>`/`<summary>` — no JS needed. No HTMX round-trip required; data is already present in the page. Consistent with the existing "Per-Provider Breakdown" collapsible in `summary_cards.html`. |
| **"Top N accounts by token contribution" sort** | In a 100+ account scan, the SEs and customers only care about the biggest contributors. Sorting the per-account table by `total_tokens` descending (instead of alphabetically by account ID) surfaces the accounts worth discussing. | LOW | Sort in `_compute_summary()` — change `sorted(account_results.items())` to sort by `result["total_tokens"]` descending. Simple one-line change with high audit value. |
| **Formula card with component contribution percentages (cloud)** | "614 DDI = 24.6 tokens = 3.7% of total" — showing each component's percentage contribution to the total helps the SE quickly explain which drivers are dominant (IP-heavy vs DDI-heavy accounts look very different). | MEDIUM | Computable from existing per-account data. Add `ddi_pct`, `ip_pct`, `asset_pct` to per-account entries. Template renders as a simple percentage annotation. Value: immediately answers "which lever matters most for this account?" |
| **NIOS family breakdown with HOST_OBJECT expansion note** | HOST_OBJECT expands to +2 or +3 DDI objects per object (A+PTR, or A+PTR+CNAME). The family count in `families_found` is the raw XML object count, not the expanded DDI count. Without a note, customers will see "HOST_OBJECT: 48,273" and expect the DDI total to include 48,273 — it will include ~96,546 to ~144,819. This confusion is predictable and high-stakes. | LOW | Add a footnote row or tooltip-style note below the HOST_OBJECT row in the family table: "HOST_OBJECT expands to 2–3 DDI records per object (A + PTR + optional CNAME). Expansion is included in the DDI total above." |
| **Scroll-anchored attribution sections** | When the NIOS complete screen shows scenario cards, member attribution, and object family breakdown all stacked vertically, users need in-page navigation. Section anchors (`id="object-families"`, `id="member-attribution"`) with a jump link from the formula cards let users navigate directly to the audit detail they need. | LOW | Pure HTML anchors. No backend changes. Zero JS required. Pattern: "View full object family breakdown" link jumps to the table below. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Sortable/filterable attribution table columns in WebUI** | "Let me sort per-account table by DDI count, or filter by provider." | This is a full HTMX table with server-side sort/filter, mirroring the Results tab. For the attribution tables — which are typically 10–100 rows for cloud, and up to 26 rows for NIOS object families — client-side complexity exceeds the value. The Results tab already provides full filtering at the resource level. | Pre-sort on the highest-value field (tokens desc for cloud, DDI count desc for NIOS families). The audience is SEs in a customer meeting, not power users querying a database. |
| **Per-account XLS download (separate file per account)** | "I want to share just one account's numbers with the customer." | Adds file management complexity. The existing XLS report already contains per-account data in the CSV/XLSX output. The goal of the WebUI table is interactive audit, not report generation. | The existing XLS download already covers the reporting use case. The WebUI table is for in-session audit only. |
| **Live-recalculate token preview when toggling resource types in/out** | "Let me see what happens to the total if I exclude all VMs." | This requires re-running the categorization pipeline on every toggle — expensive for large scans. It also risks producing numbers that diverge from the official XLS report (which was produced at a fixed point in time). Divergence destroys trust. | The Results tab already lets users filter by resource type to see the subset. The Summary tab shows the official computed totals. These are complementary, not conflicting. |
| **Chart/graph visualization of token breakdown** | "A pie chart showing DDI vs IP vs Asset contribution would look great." | PROJECT.md explicitly excludes charts/visualizations: "text tables sufficient for enterprise audit context." Adding charts requires bundling a charting library (e.g., Chart.js) or inline SVG generation — both add complexity for an audience that will screenshot the table for their slide deck anyway. | Percentage columns in the text table convey the same proportional information without adding dependencies. |
| **All 26 NIOS families shown regardless of count** | "Show all families so I can confirm they were checked." | Showing 26 rows when 18 are zero clutters the table and buries the meaningful data. The XLS shows all families — the WebUI table is a summary for human comprehension, not a completeness audit. | Show non-zero families in the WebUI table. Add a single footnote: "N families with 0 objects not shown." This preserves completeness signaling without cluttering the table. |
| **Per-account token trend over time (delta from previous scan)** | "Show me how this account's contribution changed since last month." | PROJECT.md explicitly excludes multi-backup delta analysis: "point-in-time estimation tool only." Adding trend data requires storing previous scan results, managing scan history, and defining "same account" identity across scans. All out of scope for a local estimation tool. | The XLS download includes a timestamp. Running two scans and comparing the XLS files is the documented approach. |

---

## Feature Dependencies

```
[NIOS Object Family Breakdown — WebUI]
    └──requires──> [IntegrityReport stored on NiosScanManager]
                       └──requires──> [set_complete() extended to accept integrity_report]
                                          └──requires──> [_run_nios_pipeline() passes integrity to set_complete()]

[Cloud Per-Account Formula Derivation]
    └──requires──> [per_account_details already in _compute_summary()]
                       (dependency already satisfied — LOW complexity)

[Cloud Per-Account Resource-Type Breakdown]
    └──requires──> [_compute_summary() extended to group by (account_id, resource_type, category)]
    └──requires──> [per_account_details dict extended with resource_type_breakdown list]

[Cloud Grand Total Reconciliation Row]
    └──requires──> [Cloud Per-Account Formula Derivation]
    └──enhances──> [existing summary_cards.html grand totals]

[NIOS Family Breakdown — DDI Subtotal]
    └──requires──> [NIOS Object Family Breakdown — WebUI]
    └──requires──> [_DDI_FAMILIES set accessible in template context or computed in route]

[HOST_OBJECT Expansion Note]
    └──requires──> [NIOS Object Family Breakdown — WebUI]
    └──enhances──> [family table by making HOST_OBJECT count interpretable]

[Top-N Sort for Cloud Per-Account Table]
    └──requires──> [Cloud Per-Account Formula Derivation]
    └──enhances──> [per_account_details by changing sort order]
```

### Dependency Notes

- **The biggest backend change is NIOS:** `NiosScanManager.set_complete()` currently accepts only `output_path` and `scenario_suite`. To surface `families_found` in the WebUI, `integrity_report` must also be stored. This is a small, isolated change — one new field on `NiosScanManager`, one update to `_run_nios_pipeline()` to pass it.

- **Cloud backend changes are additive to `_compute_summary()`:** The resource-type breakdown can be computed in the same loop that already groups by account. No new API calls, no new data sources. The existing `scan_manager.resources` list contains all needed fields (`account_id`, `resource_type`, `category`, `counted`).

- **Both features are purely additive:** No existing routes change behavior. New data is added to existing template contexts and rendered in new sections below existing content. No risk of regressions on the already-working scenario cards, member attribution table, or results tab.

- **Formula derivation in templates follows the existing NIOS pattern:** The NIOS complete screen already renders `{{ scenario_suite.current_grid.ddi_count }} DDI ÷ 50 = {{ "%.1f"|format(scenario_suite.current_grid.ddi_count / 50) }}` inline. The cloud attribution table applies the same pattern with UDDI native divisors (25/13/3) — divisors are spec constants already present in `token_calculator.py`.

---

## MVP Definition

This is a v1.4 milestone added to an already-shipped v1.3 product. "MVP" here means the minimum set of features that fully delivers the milestone goal: every token total explainable without leaving the browser.

### Launch With (v1.4 — All Three Required Features)

- [ ] **Cloud per-account formula derivation** — inline math for each account row in the cloud Summary tab (DDI ÷ 25, IPs ÷ 13, Assets ÷ 3). Data already present in `per_account_details`. Template change only. — *why essential: without this, the Summary tab per-account table is opaque numbers with no derivation*
- [ ] **Cloud per-account resource-type count breakdown** — show how many VMs, subnets, DNS zones etc. contributed to each account's DDI/IP/Asset counts. Requires `_compute_summary()` extension. — *why essential: customers cannot validate "614 DDI objects" without knowing what they are*
- [ ] **NIOS object family breakdown table** — non-zero families only, with DDI vs. non-DDI flag and reason, on the NIOS complete screen. Requires storing `integrity_report` on `NiosScanManager`. — *why essential: mirrors the XLS Object Counters sheet; without it the NIOS complete screen is incomplete for audit purposes*

### Add After Validation (v1.4.x — If Customer Feedback Indicates Need)

- [ ] **Top-N sort for cloud per-account table** — sort by token contribution descending instead of account ID alphabetically. Trigger: SE feedback that large scans are hard to navigate.
- [ ] **HOST_OBJECT expansion note** — footnote on the NIOS family table explaining that HOST_OBJECT raw count is expanded to 2–3 DDI records in the total. Trigger: first customer confusion about the HOST_OBJECT row vs. DDI total.

### Future Consideration (v1.5+)

- [ ] **Per-account DDI/IP/Asset component percentage annotation** — "DDI = 3.7% of total tokens". Defer: low urgency; percentage columns add visual noise for simple accounts.
- [ ] **Collapsible per-account resource-type rows** — `<details>` blocks per account row. Defer: useful only when scanning 50+ accounts with per-account breakdown visible simultaneously; implement if performance or scroll-length becomes a complaint.
- [ ] **Cloud formula derivation card in Results tab** — per-provider formula card at the top of the Results tab (labelled CLOUD-01/02 in PROJECT.md backlog). Defer: out of scope per PROJECT.md "Out of Scope" section for v1.4; can be revisited separately.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Cloud per-account formula derivation | HIGH | LOW | P1 |
| Cloud per-account resource-type breakdown | HIGH | MEDIUM | P1 |
| NIOS object family breakdown table | HIGH | MEDIUM | P1 |
| Grand total reconciliation footnote (cloud) | MEDIUM | LOW | P1 |
| DDI-only subtotal row (NIOS family table) | MEDIUM | LOW | P1 |
| Informational-only family reason text (NIOS) | MEDIUM | LOW | P1 |
| HOST_OBJECT expansion note (NIOS) | MEDIUM | LOW | P2 |
| Top-N sort for cloud per-account table | LOW | LOW | P2 |
| Collapsible per-account resource-type detail | LOW | LOW | P3 |
| Per-component percentage annotation | LOW | LOW | P3 |

**Priority key:**
- P1: Required for v1.4 milestone completion — without it the milestone goal ("every token total fully explainable in the browser") is not met
- P2: Improves usability noticeably; add when P1 features are stable
- P3: Nice to have; defer until user feedback confirms demand

---

## Implementation Shape (Backend Changes Required)

### Change 1: Cloud — extend `_compute_summary()` in `pages.py`

The existing per-account loop already has all resources for each account. Extend it to also build a resource-type breakdown:

```python
# Inside the by_account loop:
type_counts = defaultdict(lambda: {"counted": 0, "skipped": 0})
for r in acct_resources:
    key = (r.resource_type, r.category or "unknown")
    if r.counted:
        type_counts[key]["counted"] += 1
    else:
        type_counts[key]["skipped"] += 1
# Add to per_account_details entry:
"resource_type_breakdown": [
    {"resource_type": rt, "category": cat, "counted": v["counted"], "skipped": v["skipped"]}
    for (rt, cat), v in sorted(type_counts.items())
]
```

No new routes. No new data sources. The template receives the extended `per_account_details` and renders the breakdown inline.

### Change 2: NIOS — store `integrity_report` on `NiosScanManager`

`NiosScanManager.set_complete()` currently signature: `(output_path, scenario_suite=None)`. Extend to: `(output_path, scenario_suite=None, integrity_report=None)`. Store as `self._integrity_report`.

`_run_nios_pipeline()` in `routes/nios.py` already has `integrity` in scope after Step 1. Pass it to `set_complete()`:

```python
nios_manager.set_complete(output_path, scenario_suite=scenario_suite, integrity_report=integrity)
```

Add `integrity_report` property to `NiosScanManager`. The `tab_nios()` route reads it and passes `families_found` (filtered to non-zero) to the template context alongside `scenario_suite`.

### Change 3: Templates — two new sections

**Cloud Summary tab** (`pages/summary.html`): Add formula derivation row and collapsible resource-type breakdown within the existing per-account table `<tr>`. The existing table already has all needed columns — add a formula string column and a `<details>` block inside the account row.

**NIOS complete screen** (`partials/nios/complete.html`): Add a new `<section>` below the member attribution table, conditionally rendered when `families_found` is non-empty. Table columns: Object Family, Object Count, Counted in UDDI (Yes/No), Reason. Filter to non-zero counts. Add subtotal row for DDI families only.

---

## What Users Need to Trust the Numbers

Based on the enterprise pre-sales audit context (customers are evaluating a licensing purchase, often with security team review):

1. **Every total must trace to its formula** — no integer appears without the arithmetic that produced it. This is already done for NIOS scenarios. Cloud per-account totals are the gap.

2. **Every formula must show its inputs** — not just "2,450 tokens" but "614 DDI ÷ 25 + 8,127 IPs ÷ 13 + 45 Assets ÷ 3 = 665 tokens" (where 665 ≈ 2,450 only with correct ceiling rounding). This makes the formula checkable by hand.

3. **Every input must trace to its source type** — "614 DDI objects" must break down to "423 VMs + 147 subnets + 44 DNS zones." Without this, the customer cannot confirm the scan found what it should have found.

4. **Skipped resources must be visible near the counted resources** — the Results tab provides this at the resource level. The attribution table needs to echo it at the account/family level so the SE can explain "this account has 87 skipped resources of type X" without leaving the summary view.

5. **Numbers must match the XLS report** — the WebUI is trusted only if it produces the same numbers as the downloadable XLS. Any discrepancy (e.g., ceiling rounding differences) must be explained with a footnote. The WebUI is an interactive view of the XLS data, not an independent calculation.

---

## Sources

- `/Users/mustermann/Documents/coding/Infoblox-Universal-DDI-cloud-usage/.planning/PROJECT.md` — v1.4 milestone definition, existing features, out-of-scope items (HIGH confidence)
- `src/cloud_usage/dashboard/services/scan_manager.py` — existing `ScanManager` state and `DashboardProgressTracker` (HIGH confidence — direct source read)
- `src/cloud_usage/dashboard/routes/pages.py` — `_compute_summary()` implementation, `per_account_details` structure (HIGH confidence — direct source read)
- `src/cloud_usage/dashboard/services/nios_manager.py` — `NiosScanManager.set_complete()` signature, stored state (HIGH confidence — direct source read)
- `src/cloud_usage/dashboard/routes/nios.py` — `_run_nios_pipeline()` — what is computed vs. what is discarded (HIGH confidence — direct source read)
- `src/cloud_usage/nios/schema.py` — `IntegrityReport.families_found` dict definition (HIGH confidence — direct source read)
- `src/cloud_usage/nios/output.py` — `_ALL_FAMILIES_ORDERED`, `_DDI_FAMILIES`, `_UDDI_FLAG_REASON`, `_FAMILY_DISPLAY_NAMES` — all needed data for the family breakdown table (HIGH confidence — direct source read)
- `src/cloud_usage/counting/token_calculator.py` — `DDI_PER_TOKEN = 25`, `IPS_PER_TOKEN = 13`, `ASSETS_PER_TOKEN = 3` — formula constants (HIGH confidence — direct source read)
- `src/cloud_usage/dashboard/templates/partials/nios/complete.html` — existing NIOS complete screen (scenario cards + member attribution table) — pattern to extend (HIGH confidence — direct source read)
- `src/cloud_usage/dashboard/templates/pages/summary.html` — existing cloud Summary tab — `per_account_details` table structure to extend (HIGH confidence — direct source read)

---
*Feature research for: v1.4 audit-depth attribution tables — cloud per-account and NIOS object family breakdown*
*Researched: 2026-03-03*
