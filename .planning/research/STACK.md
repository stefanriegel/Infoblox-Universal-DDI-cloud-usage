# Stack Research

**Domain:** FastAPI + HTMX dashboard — adding audit depth tables to existing app
**Researched:** 2026-03-03
**Confidence:** HIGH

---

## Context: What Already Exists (Do Not Re-Add)

This is a v1.4 milestone on an existing, validated codebase. The following stack is
fully in place and must NOT be replaced or re-added:

| Existing | Role |
|----------|------|
| FastAPI >= 0.115.0 | Web framework, route handlers, HTMX partial endpoints |
| Jinja2 >= 3.1.0 | Server-side HTML templating — all rendering lives here |
| HTMX (vendored) | Partial swaps, SSE event wiring, hx-get/hx-target patterns |
| PicoCSS (vendored) | Base styling — `<table>`, `<article>`, `<details>` all styled |
| lxml >= 5.3.0 | NIOS backup XML streaming parser |
| xlsxwriter >= 3.1.0 | XLS report generation (NIOS and cloud output) |
| PyYAML >= 6.0 | NIOS config file parsing |
| python-multipart >= 0.0.5 | File upload support |
| janus >= 2.0.0 | Thread-safe async queue (SSE event bridge) |
| pytest >= 8.0.0, moto >= 5.0.0 | Test framework |
| Python 3.9+ | Required minimum (3.9 guarded throughout) |

The existing `_compute_summary()` function in `pages.py` already computes
`per_account_details` (list with account_id, provider, ddi_count, ip_count,
asset_count, total_tokens) and `per_provider_details`. This data is passed to
templates but only rendered in the Summary tab. The cloud attribution table feature
reuses this existing data — no new data pipeline is needed.

---

## Recommended Stack — New Additions for v1.4

**Answer: No new libraries required.** Both new features are pure template + data
plumbing work within the existing FastAPI + HTMX + Jinja2 stack.

### Core Technologies (unchanged)

| Technology | Version | Purpose | Why Still Correct |
|------------|---------|---------|-------------------|
| FastAPI | >= 0.115.0 | Route handlers for new partials | Existing pattern: add route, pass data to template. No framework change needed. |
| Jinja2 | >= 3.1.0 | Render new table partials | Both new tables are HTML `<table>` elements in Jinja2 templates — identical to `complete.html` member attribution table already shipped. |
| HTMX (vendored) | 1.9.x | Tab swap, optional scroll target | No new HTMX attributes needed; existing `hx-get`, `hx-target`, `hx-swap` patterns cover both features. |
| PicoCSS (vendored) | 2.x | Table, article, scrollable div styling | PicoCSS `<table role="grid">` and the inline `max-height + overflow-y: auto` pattern already used in `complete.html` member attribution section. |

### Supporting Libraries (unchanged)

| Library | Version | Purpose | Integration Note |
|---------|---------|---------|------------------|
| xlsxwriter | >= 3.1.0 | XLS Object Counters sheet (existing) | Source of truth for family names and display order via `_ALL_FAMILIES_ORDERED` and `_FAMILY_DISPLAY_NAMES` in `nios/output.py`. WebUI table mirrors this ordering. |
| lxml | >= 5.3.0 | NIOS XML parsing (existing) | `inspect_backup()` returns `IntegrityReport.families_found` — the per-family counts needed for the NIOS WebUI table. No change to parsing. |
| stdlib `collections.defaultdict` | stdlib | Per-account resource type counting | Already used in `pages.py` `_compute_summary()`. Extend same function to add resource_type breakdown per account. |
| stdlib `dataclasses` | stdlib | NiosScanManager state extension | Store `integrity_report` (or a `dict[str, int]` family_counts snapshot) on `NiosScanManager` via a new `set_complete()` parameter. |

---

## Integration Points — Where to Wire the New Features

### Cloud Per-Account Attribution Table

**Data is already computed.** `_compute_summary()` in
`src/cloud_usage/dashboard/routes/pages.py` builds `per_account_details` (a list of
dicts: account_id, provider, ddi_count, ip_count, asset_count, total_tokens) and
passes it to the Results tab context. The Summary tab already renders this list as a
table.

**What is missing and where to add it:**

1. **Resource type breakdown per account** — `_compute_summary()` iterates resources
   by account already. Add a secondary dict `{account_id: Counter(resource_type: count)}`
   in the same loop. Attach it as `resource_type_breakdown` on each account dict.
   No new library: `collections.Counter` (stdlib) suffices.

2. **Formula derivation display** — DDI ÷ 25, IPs ÷ 13, Assets ÷ 3 inline text.
   These are UDDI spec constants already hardcoded in `token_calculator.py`
   (`DDI_PER_TOKEN = 25`, `IPS_PER_TOKEN = 13`, `ASSETS_PER_TOKEN = 3`). The
   template renders them directly (same pattern as `complete.html` which hardcodes
   divisors as Jinja2 template literals per the v1.3 decision: "Formula divisors
   hardcoded in template — values are UDDI spec constants, immutable").

3. **Template location** — Add a new partial
   `templates/partials/account_attribution.html` rendered inside the Results tab
   (`pages/results.html`). Follow the same scrollable-div + `<table>` pattern used
   in `partials/nios/complete.html` member attribution section (max-height: 400px,
   overflow-y: auto, 1px border, border-radius 6px).

4. **No new route needed** — `tab_results` in `pages.py` already passes `per_account_details`
   to the template (via `**summary`). Extend the dict to include resource type breakdown
   and the data is available in the template. The partial just needs to be included.

**Account name vs account ID:** `CloudResource.account_id` stores AWS account IDs,
Azure subscription IDs, and GCP project IDs — no human-readable account name is
fetched or stored by any provider. The table heading should be "Account ID" (or
"Account / Subscription / Project") not "Account Name". Do not attempt to add a
name lookup — it requires live cloud API calls which are out of scope for this tool's
offline result-browsing model.

### NIOS Object Family Breakdown Table

**Data is available from `IntegrityReport.families_found` but not stored in
`NiosScanManager`.** The pipeline in `routes/nios.py` computes `integrity_report`
from `inspect_backup()` in Step 1, uses it only for the XLS report, and does not
store it on `NiosScanManager`. Currently only `scenario_suite` is stored via
`set_complete(output_path, scenario_suite=scenario_suite)`.

**What is missing and where to add it:**

1. **Store family counts on NiosScanManager** — extend `set_complete()` in
   `src/cloud_usage/dashboard/services/nios_manager.py` with an additional parameter
   `family_counts: dict[str, int] | None = None`. Store it as `self._family_counts`.
   Expose via a `family_counts` property. In `_run_nios_pipeline()` in
   `routes/nios.py`, pass `integrity_report.families_found` to the updated
   `set_complete()` call. This is a minimal, backwards-compatible change.

2. **Filter to non-zero families only** — the template iterates
   `family_counts.items()` and skips rows where count == 0, matching the "non-zero
   families only" requirement. No backend filtering needed; Jinja2 `{% if count > 0 %}`
   suffices.

3. **Display order** — mirror the XLS Object Counters sheet ordering. The canonical
   order is `_ALL_FAMILIES_ORDERED` from `nios/output.py`. For the WebUI, pass the
   family counts as an ordered list rather than a raw dict so Jinja2 renders in the
   correct sequence. Build this ordered list in the route handler by iterating
   `_ALL_FAMILIES_ORDERED` and looking up counts from `family_counts`.

4. **Template location** — add to `templates/partials/nios/complete.html`, below
   the existing member attribution section. Use the same scrollable-div + `<table>`
   pattern. Columns: Object Family | Object Count | Counted in UDDI (Yes/No).

5. **No new route needed** — `tab_nios` in `pages.py` reads from `nios_manager`
   and passes context to `pages/nios.html` which includes `partials/nios/complete.html`.
   Add `family_counts` (the ordered list) to the context dict. The partial template
   reads it directly.

---

## What NOT to Add

| Do NOT add | Why | Use instead |
|------------|-----|-------------|
| Any JavaScript charting library | PROJECT.md explicitly calls out "Charts / visualizations — text tables sufficient for enterprise audit context" as out of scope | Plain `<table>` in Jinja2 template |
| pandas | Already avoided throughout codebase; `collections.Counter` and `defaultdict` handle the resource type breakdown in 3 lines | `collections.Counter` (stdlib) |
| Any new Python web framework feature | FastAPI + Jinja2 + HTMX pattern is established and consistent across all existing features; adding anything new (e.g., Alpine.js, htmx extensions) creates maintenance burden | Existing HTMX + Jinja2 partial pattern |
| Live account name lookup | Requires cloud API calls during result-browsing (post-scan); tool is offline for result display, and CloudResource.account_id carries no name — fetching at browse time would require re-auth | Show account_id as-is; label column "Account ID" |
| A new `family_counts` dataclass | `dict[str, int]` (already the type of `IntegrityReport.families_found`) is sufficient for storage and template consumption | Raw `dict[str, int]` stored on NiosScanManager |
| `openpyxl` | Already replaced by xlsxwriter in this codebase | xlsxwriter (already in stack) |

---

## Stack Patterns for These Features

**Pattern: Extend `_compute_summary()` for resource type breakdown**

`_compute_summary()` already iterates `by_account` (dict of account_id -> list of
CloudResource). Extend the per-account loop to count `resource.resource_type` for
counted resources using `collections.Counter`. Attach as `resource_type_breakdown`
in the `per_account_details` dicts.

```python
# Inside the per-account loop in _compute_summary()
from collections import Counter
type_breakdown = Counter(
    r.resource_type for r in acct_resources if r.counted
)
per_account_details.append({
    "account_id": account_id,
    "provider": account_provider[account_id],
    "ddi_count": result["ddi_count"],
    "ip_count": result["ip_count"],
    "asset_count": result["asset_count"],
    "total_tokens": result["total_tokens"],
    "resource_type_breakdown": dict(sorted(type_breakdown.items())),
})
```

**Pattern: Ordered family counts for Jinja2**

Build an ordered list in the route handler so Jinja2 doesn't need to know about
`_ALL_FAMILIES_ORDERED`:

```python
# In tab_nios route handler (pages.py)
from cloud_usage.nios.output import _ALL_FAMILIES_ORDERED, _DDI_FAMILIES

raw_family_counts = nios_manager.family_counts or {}
ordered_families = [
    {
        "family": family,
        "count": raw_family_counts.get(family, 0),
        "is_ddi": family in _DDI_FAMILIES,
    }
    for family in _ALL_FAMILIES_ORDERED
    if raw_family_counts.get(family, 0) > 0  # non-zero only
]
context["ordered_families"] = ordered_families
```

**Pattern: Scrollable attribution table (established in complete.html)**

```html
<div style="max-height: 400px; overflow-y: auto; border: 1px solid var(--ib-gray-200); border-radius: 6px;">
  <table style="margin: 0; font-size: 0.85rem;">
    <thead>...</thead>
    <tbody>
      {% for row in rows %}
      <tr>...</tr>
      {% endfor %}
    </tbody>
  </table>
</div>
```

This pattern already exists in `partials/nios/complete.html` (member attribution
table). Both new tables should use it identically.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| Family counts storage | Extend `NiosScanManager.set_complete()` with `family_counts` param | Re-run `inspect_backup()` in the route handler on demand | Re-running requires the backup file to still exist on disk and takes seconds on large backups. Storing the dict is zero-cost. |
| Resource type breakdown | Extend `_compute_summary()` in the existing request/response cycle | New API endpoint that computes breakdown lazily | The scan is already complete when the user views results; computing in `_compute_summary()` is the existing pattern (called by both `tab_results` and `tab_summary`). |
| Family ordering in template | Build ordered list in route handler, pass to template | Import `_ALL_FAMILIES_ORDERED` directly in template | Jinja2 templates cannot import Python modules. The route handler is the correct layer for data transformation. |
| Account name display | Show account_id only | Attempt to cache account names during scan | CloudResource has no account name field. Adding name lookup during scan would require new cloud API calls per account and change the discovery pipeline. Not warranted for a table-label improvement. |

---

## Version Compatibility

| Package | Current in requirements.txt | Python 3.9 Compatible | Notes |
|---------|-----------------------------|-----------------------|-------|
| FastAPI | >= 0.115.0 | Yes | 0.115+ supports Python 3.8+ |
| Jinja2 | >= 3.1.0 | Yes | 3.x supports Python 3.7+ |
| xlsxwriter | >= 3.1.0 | Yes | Pure Python, no version constraint |
| lxml | >= 5.3.0 | Yes | 5.3+ has cp39 wheels on Windows, macOS, Linux |
| stdlib (collections, dataclasses) | stdlib | Yes | dataclasses available since Python 3.7 |

No version bumps required. No new packages required.

---

## Installation

No new packages to install. All capabilities needed for v1.4 are already in the
existing requirements.txt and virtual environment.

---

## Sources

- Codebase audit of `src/cloud_usage/dashboard/` — routes/pages.py, services/nios_manager.py,
  templates/partials/nios/complete.html, templates/pages/summary.html (HIGH confidence — direct
  code inspection)
- `src/cloud_usage/nios/output.py` — `_ALL_FAMILIES_ORDERED`, `_FAMILY_DISPLAY_NAMES`,
  `_DDI_FAMILIES` confirmed as authoritative ordering/classification (HIGH confidence)
- `src/cloud_usage/nios/schema.py` — `IntegrityReport.families_found: dict[str, int]`
  confirmed as the family count source (HIGH confidence)
- `src/cloud_usage/schema/resource.py` — `CloudResource.account_id` confirmed as the only
  account identifier; no account_name field exists (HIGH confidence)
- `.planning/PROJECT.md` — "Charts / visualizations — text tables sufficient" out-of-scope
  decision confirmed; Python 3.9+ constraint confirmed (HIGH confidence)
- requirements.txt — current pinned versions confirmed (HIGH confidence)

---

*Stack research for: v1.4 Audit Depth — cloud per-account attribution tables + NIOS object family breakdown*
*Researched: 2026-03-03*
