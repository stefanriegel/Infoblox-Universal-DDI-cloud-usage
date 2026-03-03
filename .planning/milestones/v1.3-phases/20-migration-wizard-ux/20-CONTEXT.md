# Phase 20: Migration Wizard UX - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Improve the NIOS member assignment wizard step with four targeted UX additions: explanatory text describing NIOS/NIOSX groups and their token formula impact (WIZ-01), a Select All / Clear All control for batch assignment (WIZ-02), a live member count showing NIOS vs NIOSX totals as the user toggles checkboxes (WIZ-03), and numbered step labels throughout the wizard (WIZ-04). No changes to pipeline logic, backend data structures, or any routes — all changes are purely in HTML templates.

</domain>

<decisions>
## Implementation Decisions

### Explanatory text placement (WIZ-01)
- A PicoCSS `<article>` callout block placed directly above the member assignment table in `step1_upload.html`
- Plain language first, formula second: "Unchecked members remain in NIOS (DDI ÷ 50 formula). Checked members are assigned to NIOSX — migrated to Universal DDI (DDI ÷ 25 formula). Assigning more members to NIOSX increases the token estimate for those members."
- Keep it brief — two to three sentences; customers are pre-sales context, not NIOS experts. Link to the formulas but don't make them mandatory reading.
- No collapsible — the explanation is short enough to always show

### Select All / Clear All (WIZ-02)
- Two buttons placed above the member table, on the same line: "Select All" (assigns all to NIOSX) and "Clear All" (removes all NIOSX assignments)
- Single scope: one pair of buttons controls all members in the table (no per-group variation — the assignment is binary NIOS vs NIOSX)
- Implemented with minimal inline JavaScript (`onclick` on each button iterates checkboxes and sets `.checked`), then fires a synthetic `change` event to keep the live counter in sync
- Button labels: "Select All" and "Clear All" — concise, matches common table patterns

### Live group counter (WIZ-03)
- A summary line displayed directly below the Select All / Clear All buttons: "NIOS: N members | NIOSX: N members"
- Updates immediately on each checkbox `change` event via a small inline `<script>` block attached to the form
- Counter initialises from the DOM on page load (all NIOS initially, so "NIOS: N | NIOSX: 0")
- No server roundtrip — purely client-side count of checked/unchecked checkboxes; consistent with the existing inline JS pattern already used in the upload form (`hx-on:htmx:beforeRequest` attribute)

### Step label display (WIZ-04)
- Inline `<h3>` step headings — consistent with the current pattern (`<h3>Step 1: Upload NIOS Grid Backup</h3>` already present)
- Three steps:
  - Step 1: Upload Backup (already present — no rename needed)
  - Step 2: Assign Members (rename from "Step 2: Assign Migration Groups & Run" — shorter and clearer)
  - Step 3: Run Analysis (add to the running state in `step2_run.html` `<header>` and to the nios.html running block `<header>`)
- No persistent breadcrumb or progress bar across steps — inline headings are sufficient given the wizard is short and linear

### Claude's Discretion
- Exact wording of the explanatory text (within the tone/length guidance above)
- CSS styling of the Select All / Clear All buttons (secondary vs outline style, inline vs block)
- Exact format of the live counter label (exact separator character, capitalisation)
- Whether the explanatory article uses a PicoCSS `role="note"` or plain `<article>` element

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `step1_upload.html`: The only file needing changes for WIZ-01, WIZ-02, WIZ-03 — member table is already here with `<input type="checkbox" name="niosx_member" ...>` per row
- `step2_run.html`: Needs `<header>` updated to "Step 3: Run Analysis" for WIZ-04
- `nios.html` running block: Also has `<header>NIOS Analysis Running</header>` — update to "Step 3: Run Analysis" as well (or just "Step 3: Run Analysis")
- Existing inline JS pattern: `hx-on:htmx:beforeRequest="..."` and `hx-on:htmx:responseError="..."` in `step1_upload.html` confirm inline JS is acceptable

### Established Patterns
- PicoCSS `<article>` element: used for callouts (e.g., error callout in step1_upload.html) — reuse for explanatory text
- `<figure>/<table>` pattern: member table already wrapped in `<figure>` — place select-all buttons and counter outside the `<figure>`, between the intro text and the table
- `<h3>` for step headings: already the pattern in step1_upload.html
- No separate CSS files — inline `style=""` attributes for any layout tweaks

### Integration Points
- `step1_upload.html`: Primary change target — explanatory article, select-all buttons, live counter, step 2 heading rename
- `step2_run.html`: Step 3 heading update only
- `nios.html`: Step 3 heading update in the running state block
- No backend changes, no new routes, no new endpoints

</code_context>

<specifics>
## Specific Ideas

- No specific user references — user delegated all decisions to Claude
- The existing small `<p>` below the table ("All members default to NIOS. Check to assign to NIOSX...") should be removed or absorbed into the new explanatory article to avoid duplicate messaging

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 20-migration-wizard-ux*
*Context gathered: 2026-03-03*
