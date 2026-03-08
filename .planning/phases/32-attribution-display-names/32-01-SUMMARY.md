---
phase: 32-attribution-display-names
plan: 01
subsystem: testing
tags: [pytest, xfail, wave0, display-names, attribution]

# Dependency graph
requires:
  - phase: 31-dns-zones-panels
    provides: Wave 0 xfail scaffold pattern (strict=False, deferred imports)
  - phase: 21-summary-attribution
    provides: _compute_summary() and resource_type_breakdown structure
provides:
  - Wave 0 xfail test scaffold for ATTR-01 (tests/test_dashboard_attribution.py)
  - Contract for DDI_DISPLAY_NAMES dict and display_name key in breakdown
affects:
  - 32-02 (implementation plan that must satisfy these tests)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave 0 deferred-import xfail pattern: all imports of not-yet-existing symbols deferred inside test body to prevent collection-time ImportError"
    - "strict=False xfail: XPASS is acceptable when implementation pre-exists; suite stays green"

key-files:
  created:
    - tests/test_dashboard_attribution.py
  modified: []

key-decisions:
  - "All DDI_DISPLAY_NAMES and _compute_summary imports deferred inside test bodies — prevents ImportError at collection time"
  - "strict=False chosen so XPASS does not break suite if implementation pre-exists (it does — DDI_DISPLAY_NAMES already in pages.py)"
  - "TestSummaryHTMLRendering uses set_resources() on scan_manager state (same pattern as test_dashboard_summary.py)"

patterns-established:
  - "Wave 0 scaffold: deferred imports inside xfail test bodies prevents collection errors for not-yet-existing symbols"

requirements-completed:
  - ATTR-01

# Metrics
duration: 4min
completed: 2026-03-08
---

# Phase 32 Plan 01: Attribution Display Names Wave 0 Scaffold Summary

**pytest xfail scaffold defining ATTR-01 contract: DDI_DISPLAY_NAMES dict lookup and display_name key in resource_type_breakdown with Route53 Resolver Endpoint HTML integration test**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-08T11:30:42Z
- **Completed:** 2026-03-08T11:34:22Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created `tests/test_dashboard_attribution.py` with 5 xfail tests across 2 classes
- TestDisplayNameMapping: covers DDI_DISPLAY_NAMES dict existence, v1.7 type lookup, fallback for unknown types, and display_name key in breakdown
- TestSummaryHTMLRendering: integration test asserting "Route53 Resolver Endpoint" appears in summary tab HTML
- All imports of DDI_DISPLAY_NAMES and _compute_summary deferred inside test bodies — zero collection-time ImportError
- Suite collected cleanly; all 5 tests appear as xpassed (strict=False) — implementation already exists in pages.py

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Wave 0 xfail scaffold** - `1d64f2c` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `tests/test_dashboard_attribution.py` - Wave 0 xfail scaffold: TestDisplayNameMapping (4 tests) + TestSummaryHTMLRendering (1 test)

## Decisions Made

- All DDI_DISPLAY_NAMES and _compute_summary imports deferred inside test bodies to prevent collection-time ImportError (DDI_DISPLAY_NAMES may not yet exist when tests are collected)
- strict=False xfail chosen so XPASS does not break suite when implementation pre-exists
- TestSummaryHTMLRendering uses `client.app.state.scan_manager.set_resources()` pattern (same as test_dashboard_summary.py)

## Deviations from Plan

### Observation (not a deviation — no fix needed)

**DDI_DISPLAY_NAMES already implemented in pages.py**
- **Found during:** Task 1 verification
- **Observation:** The plan expects tests to appear as xfail (x); they appear as xpassed (X) instead. This is because DDI_DISPLAY_NAMES dict and display_name in breakdown were already added to `pages.py` in a prior session.
- **Impact:** None — `strict=False` means XPASS is acceptable. Suite stays green. The test contract is correctly established for Plan 32-02 to verify.
- **Action:** No fix needed. Documented as observation only.

---

**Total deviations:** 0 auto-fixes needed. Pre-existing implementation caused XPASS (acceptable with strict=False).

## Issues Encountered

- `tests/test_integration_aws.py`, `test_integration_azure.py`, and `test_integration_gcp.py` have pre-existing ImportError (`fold_enis_into_parents` missing from `asset_dedup`). These are out of scope for this plan — pre-existing failures in unrelated files.

## Next Phase Readiness

- Wave 0 scaffold complete — RED gate established (contract defined)
- Plan 32-02 can proceed to implement DDI_DISPLAY_NAMES (or verify existing implementation satisfies all tests)
- Full suite (excluding pre-existing broken integration tests) passes: 97 tests + 5 xpassed

---
*Phase: 32-attribution-display-names*
*Completed: 2026-03-08*
