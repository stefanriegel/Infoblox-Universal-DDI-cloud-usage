# Phase 19: Token Breakdown WebUI - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Enrich the existing NIOS results screen (`complete.html`) with per-scenario formula derivation (raw DDI/IP/Asset counts + formula steps) and a per-member attribution table with NIOS/NIOSX group labels. No changes to pipeline logic, formulas, backend data structures, or the `ScenarioSuite` shape — all needed data is already available in the existing template context.

</domain>

<decisions>
## Implementation Decisions

### Scenario breakdown layout
- Expand the existing 3 scenario cards in-place — formula derivation appears inline within each card, below the hero token number
- Each card shows: raw counts (DDI, Active IPs, Assets), then formula steps, then token total
- Formula format: "1,234 DDI ÷ 50 = 24.7" per component, then "Total: 24.7 tokens" — matching the inline example from BRKDN-02 requirement
- No collapsible/expandable section — breakdown is always visible; this is an audit tool and customers need to see the math without extra clicks
- Assets row only shown when asset_count > 0 (always 0 in current implementation, but keep logic correct for future)

### Hybrid scenario display
- Hybrid UDDI card (SCEN-02) only renders when `scenario_suite.hybrid_uddi` is not None
- Within the Hybrid card: show two sub-blocks — "NIOS-remaining" and "NIOSX-migrated" — each with their own DDI/IP counts and formula, then combined total at bottom
- When hybrid is absent (no migration split configured): show 2 scenario cards (Current Grid, Full Migration)
- When hybrid is present: show all 3 scenario cards

### Member table scope and content
- Show all members — no artificial row cap; this is an audit table and truncation would undermine trust
- Table is wrapped in a scrollable container with CSS `max-height` (~400px) and `overflow-y: auto`
- Columns: Member, Group, DDI Objects, Active IPs, Token Contribution
- Group column shows "NIOS" or "NIOSX" label (from `member_attribution[i].group`)
- When no migration split was configured: `member_attribution` has all members with `group = "nios"` — table still renders with Group column showing "NIOS" for all rows; no special-case needed
- Sort order: original order from `member_attribution` (as returned by compute_scenarios — no additional client-side sort for v1.3; sorting is a deferred future requirement per REQUIREMENTS.md ANA-03)

### Page structure and reading order
1. Header: "NIOS Analysis Complete" (existing)
2. Scenario cards with inline formula breakdown (expanded from current)
3. Download CTA (keep near top — primary action)
4. Member Attribution section — labeled "Member Attribution" with a subtitle clarifying that per-member IP counts are lease-only (not the global deduplicated total used for scenario totals)
5. "Run Another Analysis" button at bottom

### Template scope
- All changes are in `complete.html` only — the template already receives `scenario_suite` in context
- No new routes, no new API endpoints, no backend changes needed
- Existing scenario card CSS classes (`scenario-grid`, `scenario-card`, `sc-label`, `hero-tokens`) can be extended with new child elements

### Claude's Discretion
- Exact CSS for formula rows within cards (font size, color, indentation)
- Whether to use a `<table>` or CSS grid for the member attribution section
- Whether to add a subtle divider between scenario cards and the Download CTA
- Exact formatting of large numbers (comma thousands separator via Jinja filter or Python-side formatting)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scenario_suite` (template variable): already passed to `complete.html` — `ScenarioSuite` with `current_grid`, `full_migration`, `hybrid_uddi`, `member_attribution`
- `ScenarioResult` fields available: `ddi_count`, `active_ip_count`, `asset_count`, `token_total`, `formula_name`
- `MemberScenarioRow` fields: `member_hostname`, `group`, `ddi_count`, `active_ip_count`, `asset_count`, `token_contribution`
- `HybridScenarioResult` fields: `nios_sub` (ScenarioResult), `niosx_sub` (ScenarioResult), `combined_total`
- Formula constants (for rendering): NIOS = DDI/50 + IPs/25 + Assets/13; UDDI native = DDI/25 + IPs/13 + Assets/3 — these are in `counter.py` but the human-readable strings can be hardcoded in the template since they match the `formula_name` fields already on ScenarioResult
- Existing scenario card CSS: `.scenario-grid`, `.scenario-card`, `.scenario-card.primary`, `.sc-label`, `.hero-tokens`

### Established Patterns
- PicoCSS + inline style attributes for layout tweaks — no separate CSS files for one-off adjustments (consistent with existing complete.html)
- Jinja2 template with `{{ value | int }}` for integer display — extend with `{:,}` format or a custom filter for thousands-separated numbers
- No JavaScript — all interactivity via HTMX; static breakdown display needs no JS

### Integration Points
- `complete.html` is the only file to modify — rendered by `GET /tab/nios` when `nios_state == "complete"`
- Template context already has `scenario_suite` (ScenarioSuite | None) — Phase 19 only adds rendering of existing data fields

</code_context>

<specifics>
## Specific Ideas

- Formula display format from BRKDN-02: "1,234 DDI ÷ 50 = 24.7 tokens" — the `÷` symbol with comma-formatted input numbers makes the math self-evident without opening the XLS
- The member table subtitle about per-member IP counts being "lease-only" is important: the `scenarios.py` docstring explicitly warns that summing member.active_ip_count is wrong for scenario totals. A note in the UI prevents customer confusion when the member IP column sum doesn't equal the scenario IP total.
- BRKDN-04 requirement ("NIOS vs NIOSX group label on each row") is satisfied by the Group column — no additional special styling needed beyond the label text

</specifics>

<deferred>
## Deferred Ideas

- Per-object-family breakdown (HOST_RECORD: 234, DHCP_RANGE: 156, etc.) — ANA-01 in REQUIREMENTS.md future requirements
- Member table column sorting — ANA-03 in REQUIREMENTS.md future requirements
- Member table name/group filter — ANA-02 in REQUIREMENTS.md future requirements

</deferred>

---

*Phase: 19-token-breakdown-webui*
*Context gathered: 2026-03-03*
