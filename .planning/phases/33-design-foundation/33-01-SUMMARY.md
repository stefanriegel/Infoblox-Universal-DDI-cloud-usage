---
phase: 33-design-foundation
plan: 01
subsystem: testing
tags: [pytest, xfail, tdd, wave-0, scaffold, pico, design-system]

# Dependency graph
requires: []
provides:
  - "Wave 0 xfail test scaffold for DESIGN-01 (9 stubs in test_dashboard_design.py)"
  - "Renamed test_static_pico_css_served to test_static_design_system_css_served in test_dashboard_app.py"
affects: [33-02, 33-03, 33-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "xfail wave scaffold: strict=False xfail with descriptive reason string marks acceptance criteria before implementation"
    - "module-level app = create_app() in test file for reuse across test functions"

key-files:
  created:
    - tests/test_dashboard_design.py
  modified:
    - tests/test_dashboard_app.py

key-decisions:
  - "xfail strict=False so tests degrade gracefully (xpass counts as pass, not failure) — safe for CI during wave 0"
  - "Module-level app instance in test_dashboard_design.py avoids repeated create_app() calls per test"

patterns-established:
  - "Wave 0 scaffold: write all acceptance-criteria tests as xfail stubs before any implementation begins"

requirements-completed: [DESIGN-01]

# Metrics
duration: 1min
completed: 2026-03-08
---

# Phase 33 Plan 01: Design Foundation Wave 0 Scaffold Summary

**9 xfail stubs in tests/test_dashboard_design.py define all DESIGN-01 acceptance criteria before any CSS implementation begins**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-03-08T14:13:09Z
- **Completed:** 2026-03-08T14:14:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created `tests/test_dashboard_design.py` with 9 xfail stubs covering: no-pico HTML reference, design-system.css link, no-data-theme, --ib-navy/--ib-accent-green/--page-bg CSS tokens, no :root in app.css, no --pico- vars, inter-variable.woff2 served
- Renamed `test_static_pico_css_served` to `test_static_design_system_css_served` in `test_dashboard_app.py`, updated URL to `/static/design-system.css`, marked xfail
- Full suite (32 tests) exits 0: 22 passed, 9 xfailed, 1 xpassed

## Task Commits

Each task was committed atomically:

1. **Task 1: Create tests/test_dashboard_design.py with xfail stubs** - `df6aff6` (test)
2. **Task 2: Rename pico test in test_dashboard_app.py** - `d3ee4c9` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `tests/test_dashboard_design.py` - 9 xfail stubs covering all DESIGN-01 acceptance criteria
- `tests/test_dashboard_app.py` - Renamed pico test to design-system.css, marked xfail

## Decisions Made
- Used `strict=False` on xfail so unexpected passes (xpass) do not fail the build — safe during incremental wave delivery
- Module-level `app = create_app()` instance shared across test functions instead of per-test instantiation (consistent with plan spec)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Wave 0 scaffold complete — all DESIGN-01 acceptance tests in place
- Wave 1 (33-02) can now create `design-system.css` and the CSS token tests will turn green
- Wave 2 (33-03/04) will migrate variables out of `app.css` and update `base.html`

## Self-Check: PASSED

- `tests/test_dashboard_design.py` exists and collected 9 tests
- `tests/test_dashboard_app.py` has `test_static_design_system_css_served` (no `test_static_pico_css_served`)
- Commits df6aff6 and d3ee4c9 exist in git log
- `pytest tests/test_dashboard_design.py tests/test_dashboard_app.py -q` exits 0 (22 passed, 9 xfailed, 1 xpassed)

---
*Phase: 33-design-foundation*
*Completed: 2026-03-08*
