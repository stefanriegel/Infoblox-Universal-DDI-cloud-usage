---
phase: 20-migration-wizard-ux
plan: 01
subsystem: ui
tags: [jinja2, htmx, picocss, javascript]

requires: []
provides:
  - Explanatory article block in NIOS wizard step 1 describing NIOS/NIOSX token formulas (WIZ-01)
  - Select All / Clear All batch assignment buttons wired to checkbox change events (WIZ-02)
  - Live NIOS/NIOSX member counter initialised from server-rendered count, updated client-side (WIZ-03)
  - Step 2 heading renamed to "Assign Members" (WIZ-04 partial)
  - Redundant small-p below member table removed
affects: [20-02, verification]

tech-stack:
  added: []
  patterns:
    - "Inline JS IIFE for scoped DOM counter logic in Jinja2 templates"
    - "dispatchEvent(new Event('change', {bubbles: true})) to keep live counter in sync with batch operations"
    - "PicoCSS <article> element for informational callouts (no role attribute)"

key-files:
  created: []
  modified:
    - src/cloud_usage/dashboard/templates/partials/nios/step1_upload.html

key-decisions:
  - "Explanatory article placed outside <form> in the member list container — informational, not a form element"
  - "Counter initialised via Jinja2 server-side {{ members|length }} rather than a separate DOM count on load"
  - "Counter span pluralises 'member'/'members' correctly for both NIOS and NIOSX counts"
  - "Select All / Clear All use type='button' to prevent accidental form submission"

patterns-established:
  - "Inline IIFE script at bottom of form section: scoped, no global pollution, runs after DOM ready"

requirements-completed:
  - WIZ-01
  - WIZ-02
  - WIZ-03
  - WIZ-04

duration: 8min
completed: 2026-03-03
---

# Phase 20: Migration Wizard UX — Plan 01 Summary

**NIOS wizard member assignment step now explains NIOS/NIOSX formulas, supports batch selection, and shows a live group counter.**

## Performance

- **Duration:** 8 min
- **Completed:** 2026-03-03
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added PicoCSS `<article>` callout above the run form explaining NIOS (DDI÷50) vs NIOSX (DDI÷25) token formulas (WIZ-01)
- Added "Select All" / "Clear All" buttons with inline `onclick` JS that sets all checkboxes and dispatches `change` events (WIZ-02)
- Added live `#nios-group-counter` span plus IIFE event listener that updates NIOS/NIOSX counts on every checkbox toggle including batch operations (WIZ-03)
- Renamed Step 2 heading from "Assign Migration Groups & Run" to "Assign Members" (WIZ-04 partial); removed redundant small-p below table

## Task Commits

1. **Task 1: Add explanatory article and rename Step 2 heading** — `530d097` (feat: WIZ-01, WIZ-04 partial + small-p removal)
2. **Task 2: Add Select All / Clear All buttons and live counter** — `530d097` (included in same commit)

## Files Created/Modified

- `src/cloud_usage/dashboard/templates/partials/nios/step1_upload.html` — Added explanatory article, Select All/Clear All buttons with counter div, and IIFE counter update script; renamed Step 2 heading; removed redundant small-p
