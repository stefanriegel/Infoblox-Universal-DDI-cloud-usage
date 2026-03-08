---
phase: 35-navigation-breadcrumb
plan: 01
subsystem: testing
tags: [pytest, xfail, breadcrumb, navigation, fastapi, testclient]

# Dependency graph
requires:
  - phase: 34-home-screen-routing
    provides: /cloud /nios /ad route handlers and base.html as the full-page shell
provides:
  - xfail test contract for NAV-01 and NAV-02 breadcrumb behaviors (7 stubs)
affects:
  - 35-02 (Plan 02 implements breadcrumb — removes xfail markers to turn tests green)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "xfail(strict=True) for positive assertions not yet implemented"
    - "xfail(strict=False) for negative assertions already true — same precedent as 34-01"

key-files:
  created:
    - tests/test_dashboard_navigation.py
  modified: []

key-decisions:
  - "test_home_has_no_breadcrumb uses strict=False (not strict=True) because the negative assertion is already satisfied (no breadcrumb-nav exists yet); identical precedent to 34-01 decision for test_index_returns_200_with_title"

patterns-established:
  - "Negative-assertion xfail stubs use strict=False when the condition is already true pre-implementation"

requirements-completed:
  - NAV-01
  - NAV-02

# Metrics
duration: 4min
completed: 2026-03-08
---

# Phase 35 Plan 01: Navigation Breadcrumb Test Scaffold Summary

**pytest xfail scaffold for "Home > [Calculator Name]" breadcrumb — 7 stubs covering NAV-01 (breadcrumb text on /cloud /nios /ad; absent on /) and NAV-02 (href="/" Home link)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-08T15:49:22Z
- **Completed:** 2026-03-08T15:53:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created `tests/test_dashboard_navigation.py` with 7 xfail stubs — Nyquist contract before Plan 02 implementation
- 6 stubs use `strict=True` (assertions not yet satisfied); 1 uses `strict=False` (negative assertion already holds)
- Full dashboard test suite unaffected — 8 pre-existing tests still pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test_dashboard_navigation.py with 7 xfail stubs** - `e3f76fa` (test)

## Files Created/Modified

- `tests/test_dashboard_navigation.py` — 7 xfail stubs covering NAV-01 and NAV-02 breadcrumb behaviors

## Decisions Made

- `test_home_has_no_breadcrumb` uses `strict=False` instead of `strict=True` because the assertion (`"breadcrumb-nav" not in response.text`) is already true pre-implementation — using `strict=True` causes XPASS (pytest failure). This is the same situation as Phase 34-01's `test_index_returns_200_with_title` decision.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Changed test_home_has_no_breadcrumb to strict=False**
- **Found during:** Task 1 verification (pytest run)
- **Issue:** Plan specified strict=True for all 7 stubs, but `test_home_has_no_breadcrumb` asserts a negative condition that is already true (no breadcrumb-nav exists yet). strict=True + passing test = XPASS = pytest failure.
- **Fix:** Changed this single stub's decorator to `strict=False` with an explanatory reason string. All other 6 stubs retain `strict=True`.
- **Files modified:** tests/test_dashboard_navigation.py
- **Verification:** pytest reports 6 xfailed + 1 xpassed (not a failure), 0 errors
- **Committed in:** e3f76fa (task commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug: strict=True on already-passing negative assertion)
**Impact on plan:** Essential fix for suite health. No scope creep. 7 stubs still present.

## Issues Encountered

- `tests/test_integration_aws.py` has a pre-existing `ImportError` for `fold_enis_into_parents` — unrelated to this plan, out of scope. Logged to deferred-items.

## Next Phase Readiness

- Test contract locked for Plan 02: implement `calculator_name` context injection in `pages.py`, breadcrumb block in `base.html`, breadcrumb CSS in `app.css`
- Plan 02 removes xfail markers (all 7 stubs turn green)

---
*Phase: 35-navigation-breadcrumb*
*Completed: 2026-03-08*

## Self-Check: PASSED

- tests/test_dashboard_navigation.py: FOUND
- .planning/phases/35-navigation-breadcrumb/35-01-SUMMARY.md: FOUND
- Commit e3f76fa: FOUND
