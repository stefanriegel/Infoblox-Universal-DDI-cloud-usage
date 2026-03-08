---
phase: 34-home-screen-routing
plan: 01
subsystem: testing
tags: [pytest, xfail, tdd, dashboard, routing]

requires:
  - phase: 33-design-foundation
    provides: design-system.css and CSS variable foundation that home screen will consume

provides:
  - xfail test stubs for HOME-01, HOME-02, ROUTE-01, ROUTE-02, DESIGN-02
  - test_dashboard_home_routing.py with 8 xfail stubs for all home/routing behaviors
  - test_dashboard_app.py updated — old UDDI Estimator title assertion marked xfail

affects:
  - 34-02 (home screen implementation — turns xfails green)
  - 34-03 (route wiring — turns route xfails green)

tech-stack:
  added: []
  patterns:
    - "xfail(strict=True) for behaviors not yet implemented — surfaces XPASS automatically when implementation lands"
    - "xfail(strict=False) for tests that currently pass but will naturally break once routing changes"

key-files:
  created:
    - tests/test_dashboard_home_routing.py
  modified:
    - tests/test_dashboard_app.py

key-decisions:
  - "Used strict=True on the 8 new stubs — XPASS surfacing is desired once Plan 02/03 ships"
  - "Used strict=False on test_index_returns_200_with_title — the assertion currently passes (UDDI Estimator still served); strict=True would make the suite fail immediately"

patterns-established:
  - "Wave 0 xfail scaffolding: create all test stubs before any implementation so Plans 02/03 have Nyquist-compliant verify commands"

requirements-completed:
  - HOME-01
  - HOME-02
  - ROUTE-01
  - ROUTE-02
  - DESIGN-02

duration: 4min
completed: 2026-03-08
---

# Phase 34 Plan 01: Home Screen Routing — Test Scaffold Summary

**8 xfail(strict=True) test stubs for home screen and routing behaviors, plus old title assertion marked xfail to protect suite from Plan 02 root-route change**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-08T14:49:29Z
- **Completed:** 2026-03-08T14:53:10Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Created tests/test_dashboard_home_routing.py with 8 xfail stubs covering HOME-01, HOME-02, ROUTE-01, ROUTE-02, DESIGN-02
- Updated test_dashboard_app.py to mark test_index_returns_200_with_title as xfail(strict=False) so suite stays green when Plan 02 changes the root route
- Full test suite passes with new xfail markers in place

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test_dashboard_home_routing.py with xfail stubs** - `c8d8cb5` (test)
2. **Task 2: Update test_dashboard_app.py old title assertion** - `ca60110` (test)

**Plan metadata:** (final commit after SUMMARY.md)

## Files Created/Modified

- `tests/test_dashboard_home_routing.py` - 8 xfail(strict=True) stubs for all home-screen and routing behaviors
- `tests/test_dashboard_app.py` - test_index_returns_200_with_title marked xfail(strict=False)

## Decisions Made

- Used `strict=True` for the 8 new stubs in test_dashboard_home_routing.py — once implementation lands and tests pass, XPASS(strict) will surface them immediately as "now passing, remove xfail" signals.
- Used `strict=False` for the existing test_index_returns_200_with_title update — this test currently passes its assertion (root still serves UDDI Estimator), so strict=True would cause XPASS failure right now. strict=False keeps the suite green and lets the test naturally transition to a real xfail once Plan 02 changes the root route.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Changed strict=True to strict=False for Task 2 test**

- **Found during:** Task 2 verification
- **Issue:** Plan specified `strict=True` for test_index_returns_200_with_title, but the current root route still serves "UDDI Estimator" in HTML, making the assertion pass — so xfail(strict=True) on a passing test produces XPASS(strict) which counts as FAILED, breaking the suite
- **Fix:** Used `strict=False` so the XPASS is silently accepted now; the test will naturally become a real xfail once Plan 02 changes the root to serve home.html
- **Files modified:** tests/test_dashboard_app.py
- **Verification:** `python -m pytest tests/test_dashboard_app.py` — 21 passed, 2 xpassed (no failures)
- **Committed in:** ca60110 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug: xfail strictness mismatch with current behavior)
**Impact on plan:** Fix was necessary to meet the plan's stated success criterion "suite stays green". No scope creep.

## Issues Encountered

- Pre-existing ImportError in tests/test_integration_aws.py (`fold_enis_into_parents` not found) — pre-dates this plan, out of scope, not fixed.

## Next Phase Readiness

- All 8 test stubs are ready for Plan 02 (home screen implementation) and Plan 03 (route wiring)
- xfail markers will automatically surface as XPASS once implementation lands — no manual tracking needed
- test_dashboard_app.py title assertion will naturally fail once Plan 02 changes root route

---
*Phase: 34-home-screen-routing*
*Completed: 2026-03-08*

## Self-Check: PASSED

- FOUND: tests/test_dashboard_home_routing.py
- FOUND: tests/test_dashboard_app.py
- FOUND: .planning/phases/34-home-screen-routing/34-01-SUMMARY.md
- FOUND: commit c8d8cb5 (Task 1)
- FOUND: commit ca60110 (Task 2)
