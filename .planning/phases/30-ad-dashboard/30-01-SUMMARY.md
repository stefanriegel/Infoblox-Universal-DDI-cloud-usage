---
phase: 30-ad-dashboard
plan: "01"
subsystem: testing
tags: [pytest, fastapi, htmx, sse, ad, winrm]

# Dependency graph
requires:
  - phase: 29-microsoft-ad-core
    provides: AdOptions dataclass, providers/ad/options.py — wizard form fields map directly

provides:
  - tests/test_dashboard_ad.py — Wave 0 test scaffold covering AD-09 through AD-12
  - Failing import boundary signaling Plans 02-04 must create ad_manager.py and routes/ad.py

affects:
  - 30-02 (must create ad_manager.py to satisfy TestAdScanManager + TestAdRun)
  - 30-03 (must create routes/ad.py + templates to satisfy TestAdTab + TestAdProgress + TestAdSSE)
  - 30-04 (must wire complete/error state rendering to satisfy TestAdTab complete/error tests + TestAdDownload)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave 0 TDD RED gate: module-level imports cause ImportError at collection time, surfacing missing modules clearly"
    - "Mirror pattern: test structure mirrors test_dashboard_nios.py exactly for consistency"

key-files:
  created:
    - tests/test_dashboard_ad.py
  modified: []

key-decisions:
  - "Import ad_manager at module level (not inside test methods) so ImportError surfaces at collection — clear signal for Wave 0"
  - "Use set_last_options() helper method on AdScanManager to store retry pre-fill data, mirroring NiosScanManager pattern"
  - "SSE race-condition test injects COMPLETE state before stream connect and asserts ad_complete emitted in response body"

patterns-established:
  - "Wave 0 stub pattern: tests import from not-yet-created modules so collection fails with ImportError until implementation lands"
  - "State injection: client.app.state.ad_manager.start() / .set_complete() / .set_error() for route-level tests"

requirements-completed: [AD-09, AD-10, AD-11, AD-12]

# Metrics
duration: 5min
completed: 2026-03-08
---

# Phase 30 Plan 01: AD Dashboard Test Scaffold Summary

**pytest Wave 0 scaffold with 7 test classes and 20 test methods covering the full AD dashboard tab (wizard, SSE progress, results, error/retry) — fails at collection until Plan 02 creates ad_manager.py**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-08T10:43:29Z
- **Completed:** 2026-03-08T10:48:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created tests/test_dashboard_ad.py with all 7 required test classes (TestAdScanManager, TestAdRun, TestAdTab, TestAdProgress, TestAdSSE, TestAdDownload, TestAdIndependence)
- Module-level import from `cloud_usage.dashboard.services.ad_manager` ensures collection fails with ImportError — Wave 0 gate is active
- Python syntax verified clean via `ast.parse()`

## Task Commits

Each task was committed atomically:

1. **Task 1: Write complete AD dashboard test scaffold** - `f54ae29` (test)

## Files Created/Modified

- `tests/test_dashboard_ad.py` - Wave 0 test scaffold: 7 test classes, 20 test methods covering AD-09 through AD-12

## Decisions Made

- Imported `AdState, AdScanManager` from `ad_manager` at module level so the ImportError is immediately visible at collection time — this is the intended Wave 0 gate behavior
- Used `set_last_options()` as the method name for storing AdOptions on AdScanManager (mirrors the pre-fill pattern described in CONTEXT.md)
- SSE race-condition test uses `client.stream()` + `iter_bytes()` to read until `ad_complete` found in body
- `_make_fake_ad_options()` uses kerberos mode (no username/password) matching AdOptions validation rules

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Wave 0 complete — Plans 02, 03, and 04 now have a concrete automated verify target
- Plan 02 must create `src/cloud_usage/dashboard/services/ad_manager.py` with `AdState` enum and `AdScanManager` class
- Plan 03 must create `src/cloud_usage/dashboard/routes/ad.py` and templates for `/tab/ad`, `/api/ad/progress`, `/api/sse/ad`
- Plan 04 must wire complete/error state rendering + download endpoint

## Self-Check

- [x] tests/test_dashboard_ad.py exists: FOUND
- [x] Commit f54ae29 exists in git log
- [x] All 7 test classes present: TestAdScanManager, TestAdRun, TestAdTab, TestAdProgress, TestAdSSE, TestAdDownload, TestAdIndependence
- [x] Python syntax check passed

## Self-Check: PASSED

---
*Phase: 30-ad-dashboard*
*Completed: 2026-03-08*
