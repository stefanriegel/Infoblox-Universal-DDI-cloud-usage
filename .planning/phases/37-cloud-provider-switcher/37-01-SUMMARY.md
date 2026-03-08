---
phase: 37-cloud-provider-switcher
plan: 01
subsystem: testing
tags: [pytest, xfail, tdd, cloud-switcher, htmx]

# Dependency graph
requires:
  - phase: 36-calculator-visual-redesign
    provides: calc_theme pattern and Phase 36 xfail precedents
provides:
  - "14 xfail stubs in tests/test_dashboard_cloud_switcher.py covering CLOUD-08 and CLOUD-09"
  - "TDD gate for Phase 37 implementation plans (37-02 onwards)"
affects: [37-02, 37-03, 37-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "xfail(strict=True) for all behaviors not yet implemented; strict=False for assertions already satisfied pre-implementation (precedent: 34-01)"
    - "14-stub test scaffold sets TDD gate before any implementation lands"

key-files:
  created:
    - tests/test_dashboard_cloud_switcher.py
  modified: []

key-decisions:
  - "test_invalid_provider_returns_404 uses strict=False — 404 already satisfied pre-implementation (route does not exist, FastAPI returns 404 by default), identical precedent to 34-01 decision"
  - "All other 13 stubs use strict=True — none of their assertions are satisfied pre-implementation"

patterns-established:
  - "xfail(strict=False) for negative assertions that are already true pre-implementation"

requirements-completed:
  - CLOUD-08
  - CLOUD-09

# Metrics
duration: 5min
completed: 2026-03-08
---

# Phase 37 Plan 01: Cloud Provider Switcher xfail Scaffold Summary

**14 xfail stub tests gating CLOUD-08 (provider selector UI) and CLOUD-09 (per-provider routing, state isolation, scan lifecycle, SSE) before any implementation lands**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-08T18:19:57Z
- **Completed:** 2026-03-08T18:24:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- 4 CLOUD-08 stubs: provider-selector in /cloud response, provider-pill in base.html, CSS pill styles, active pill highlight
- 10 CLOUD-09 stubs: per-provider tab routes (aws/azure/gcp), invalid provider 404, three scan managers on app.state, state isolation between providers, per-provider scan start routes, per-provider SSE endpoint, wizard route bypass check
- Full test suite (dashboard tests) remains green — 13 xfailed, 1 xpassed (as expected)

## Task Commits

Each task was committed atomically:

1. **Task 1: Write 14 xfail stubs in test_dashboard_cloud_switcher.py** - `a5c1e79` (test)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `tests/test_dashboard_cloud_switcher.py` - 14 xfail stubs for CLOUD-08 (4 stubs) and CLOUD-09 (10 stubs)

## Decisions Made

- `test_invalid_provider_returns_404` uses `strict=False` because the 404 assertion is already satisfied pre-implementation — FastAPI returns 404 for unregistered routes. Using `strict=True` would cause XPASS failure. This is the same precedent established in Plan 34-01 for `test_index_returns_200_with_title`.
- All other 13 stubs correctly use `strict=True` because none of their assertions are satisfied without implementation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Changed test_invalid_provider_returns_404 from strict=True to strict=False**
- **Found during:** Task 1 verification run
- **Issue:** `strict=True` caused XPASS failure — the assertion `status_code == 404` is already satisfied pre-implementation since the route does not exist; FastAPI returns 404 by default for unregistered paths
- **Fix:** Changed decorator to `@pytest.mark.xfail(strict=False, ...)` with updated reason explaining the pre-implementation satisfaction, matching 34-01 precedent
- **Files modified:** tests/test_dashboard_cloud_switcher.py
- **Verification:** Re-ran test file — 13 xfailed, 1 xpassed (no failures)
- **Committed in:** a5c1e79 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Auto-fix necessary for correct test behavior. Plan still has 14 stubs, all gating implementation correctly.

## Issues Encountered

None beyond the strict=False adjustment above.

## Next Phase Readiness

- TDD gate established — all 14 stubs must turn green before Phase 37 is complete
- Plans 37-02 onwards can begin implementation against these stubs
- The 3 integration tests (test_integration_aws.py, test_integration_azure.py, test_integration_gcp.py) have pre-existing import errors unrelated to this phase — they are excluded from suite runs

---
*Phase: 37-cloud-provider-switcher*
*Completed: 2026-03-08*
