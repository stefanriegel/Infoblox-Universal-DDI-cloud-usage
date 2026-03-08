---
phase: 36-calculator-visual-redesign
plan: 01
subsystem: testing
tags: [pytest, xfail, tdd, dashboard, css, visual-redesign]

# Dependency graph
requires:
  - phase: 35-navigation-breadcrumb
    provides: breadcrumb nav and /cloud, /nios, /ad route handlers in place
provides:
  - "11 xfail(strict=True) stubs covering DESIGN-03 (6), DESIGN-04 (2), DESIGN-05 (3)"
  - "Acceptance criteria defined before implementation for Phase 36 Plans 02 and 03"
affects: [36-02-accent-system, 36-03-card-layout]

# Tech tracking
tech-stack:
  added: []
  patterns: [xfail(strict=True) scaffold — stubs fail before implementation, turn green on delivery]

key-files:
  created:
    - tests/test_dashboard_visual_redesign.py
  modified: []

key-decisions:
  - "Template file tests (DESIGN-05, tests 9–11) read HTML source directly via Path.read_text() — no HTTP client or manager state mock needed"
  - "strict=True on all 11 stubs — unlike 34-01 where strict=False was used for already-passing assertions, none of these assertions pass yet"

patterns-established:
  - "Template file tests: read source HTML via Path(__file__).parent.parent / 'src/...' — avoids complex wizard-state mocking for presence checks"

requirements-completed: [DESIGN-03, DESIGN-04, DESIGN-05]

# Metrics
duration: 3min
completed: 2026-03-08
---

# Phase 36 Plan 01: Calculator Visual Redesign Summary

**11 xfail(strict=True) stubs for accent body classes, per-calculator CSS rules, wizard checkmark, and completion-card layout — acceptance criteria locked before Plans 02/03 implement them**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-08T16:54:29Z
- **Completed:** 2026-03-08T16:57:30Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created `tests/test_dashboard_visual_redesign.py` with 11 xfail(strict=True) stubs
- DESIGN-03 covered: body class assertions for /cloud, /nios, /ad routes and CSS accent color rules (#0066CC, #00C389, #8B5CF6)
- DESIGN-04 covered: var(--calc-accent) and \\2713 checkmark unicode escape in app.css
- DESIGN-05 covered: completion-card in nios/ad complete.html partials and Token Summary heading in summary.html

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test_dashboard_visual_redesign.py with 11 xfail stubs** - `4951a1f` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `tests/test_dashboard_visual_redesign.py` — 11 xfail(strict=True) stubs for DESIGN-03/04/05

## Decisions Made
- Template file tests (DESIGN-05, stubs 9–11) use `Path.read_text()` directly on the source HTML files — avoids needing to mock full wizard manager state for simple string presence checks
- All 11 stubs use strict=True because none of the assertions are satisfied in current codebase (unlike 34-01 where some assertions were already passing)

## Deviations from Plan

None — plan executed exactly as written.

Pre-existing note: `test_integration_aws.py`, `test_integration_azure.py`, and `test_integration_gcp.py` have a pre-existing `ImportError` for `fold_enis_into_parents` from `asset_dedup`. This predates Phase 36 and was logged as out-of-scope. See deferred-items.md.

## Issues Encountered

None — 11 xfailed confirmed in 0.37s, dashboard test suite clean.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- Test scaffold is in place; Plans 02 and 03 can implement the accent system and card layout against these stubs
- When Plans 02 and 03 complete, `pytest tests/test_dashboard_visual_redesign.py` should report 11 passed, 0 xfailed

---
*Phase: 36-calculator-visual-redesign*
*Completed: 2026-03-08*

## Self-Check: PASSED

- tests/test_dashboard_visual_redesign.py: FOUND
- 36-01-SUMMARY.md: FOUND
- Commit 4951a1f: FOUND
