---
phase: 20-migration-wizard-ux
plan: 02
subsystem: ui
tags: [jinja2, htmx, picocss]

requires: []
provides:
  - "Step 3: Run Analysis" header in step2_run.html running state (WIZ-04)
  - "Step 3: Run Analysis" header in nios.html running state block (WIZ-04)
  - Complete wizard step label sequence: Step 1 Upload → Step 2 Assign Members → Step 3 Run Analysis
affects: [verification]

tech-stack:
  added: []
  patterns:
    - "Consistent step heading pattern (<header> inside <article>) across all wizard states"

key-files:
  created: []
  modified:
    - src/cloud_usage/dashboard/templates/partials/nios/step2_run.html
    - src/cloud_usage/dashboard/templates/pages/nios.html

key-decisions:
  - "step2_run.html (HTMX partial swap) and nios.html (full tab inline running block) both updated independently — they are separate rendering paths"
  - "Checkpoint auto-approved in auto-advance pipeline — visual verification available for manual testing"

patterns-established: []

requirements-completed:
  - WIZ-04

duration: 5min
completed: 2026-03-03
---

# Phase 20: Migration Wizard UX — Plan 02 Summary

**Step 3 running-state header updated to "Step 3: Run Analysis" in both rendering paths, completing the full wizard step label sequence.**

## Performance

- **Duration:** 5 min
- **Completed:** 2026-03-03
- **Tasks:** 2 (1 auto + 1 checkpoint, auto-approved)
- **Files modified:** 2

## Accomplishments

- Updated `step2_run.html` `<header>` from "NIOS Analysis Running" to "Step 3: Run Analysis" (WIZ-04)
- Updated `nios.html` running block `<header>` from "NIOS Analysis Running" to "Step 3: Run Analysis" (WIZ-04)
- Wizard now has consistent step labels across all states: Step 1 Upload Backup → Step 2 Assign Members → Step 3 Run Analysis

## Visual Verification (manual)

To verify all four WIZ requirements end-to-end:
1. Run: `uvicorn cloud_usage.main:app --reload` from `src/`
2. Open NIOS tab → upload a `.tar.gz` backup
3. Confirm explanatory article, "Step 2: Assign Members" heading, Select All/Clear All buttons, live counter
4. Test Select All / Clear All / individual toggles → counter updates
5. Click "Run Analysis" → verify "Step 3: Run Analysis" article header appears

## Task Commits

1. **Task 1: Update step2_run.html and nios.html headers** — `cf74815` (feat: WIZ-04 Step 3 labels)
2. **Task 2: Visual verification checkpoint** — auto-approved in auto-advance pipeline

## Files Created/Modified

- `src/cloud_usage/dashboard/templates/partials/nios/step2_run.html` — `<header>` updated to "Step 3: Run Analysis"
- `src/cloud_usage/dashboard/templates/pages/nios.html` — running state `<header>` updated to "Step 3: Run Analysis"
