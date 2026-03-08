---
phase: 37-cloud-provider-switcher
plan: 02
subsystem: api
tags: [fastapi, lifespan, scan-manager, event-bridge, state-isolation, cloud-switcher]

# Dependency graph
requires:
  - phase: 37-01
    provides: 14 xfail stubs in test_dashboard_cloud_switcher.py gating CLOUD-09

provides:
  - "Three per-provider ScanManager instances on app.state: aws_scan_manager, azure_scan_manager, gcp_scan_manager"
  - "Three per-provider EventBridge instances on app.state: aws_event_bridge, azure_event_bridge, gcp_event_bridge"
  - "Shutdown teardown for all three per-provider EventBridges"

affects: [37-03, 37-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-provider state isolation: each cloud provider gets its own ScanManager + EventBridge instance on app.state"
    - "Additive lifespan extension: new per-provider blocks added after existing ad_manager block, preserving all existing state keys"
    - "xfail markers removed on implementation (strict=True XPASS = pytest failure) — same precedent as 36-01, 34-01"

key-files:
  created: []
  modified:
    - src/cloud_usage/dashboard/app.py
    - tests/test_dashboard_cloud_switcher.py

key-decisions:
  - "xfail markers removed from test_three_provider_managers_on_app_state and test_provider_scan_state_independent — assertions now satisfied, keeping strict=True would cause XPASS failure (same precedent as 34-01 and 36-01)"
  - "Per-provider ScanManager instances created with ScanManager() — no arguments — matching existing scan_manager pattern"

patterns-established:
  - "Per-provider state: app.state.{provider}_scan_manager and app.state.{provider}_event_bridge for aws/azure/gcp"

requirements-completed:
  - CLOUD-09

# Metrics
duration: 5min
completed: 2026-03-08
---

# Phase 37 Plan 02: Per-Provider State Isolation Summary

**Three isolated ScanManager + EventBridge instances registered on app.state (aws/azure/gcp) via lifespan startup, with full shutdown teardown — enabling per-provider scan isolation for Cloud Provider Switcher**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-08T18:34:58Z
- **Completed:** 2026-03-08T18:40:56Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Added `aws_event_bridge`, `azure_event_bridge`, `gcp_event_bridge` (each started in lifespan startup block)
- Added `aws_scan_manager`, `azure_scan_manager`, `gcp_scan_manager` (three distinct ScanManager objects on app.state)
- Added shutdown teardown closing all three per-provider EventBridge instances
- Removed xfail markers from two tests after implementation satisfied assertions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add three per-provider ScanManager + EventBridge instances to app.py lifespan** - `c617c32` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `src/cloud_usage/dashboard/app.py` - Added per-provider EventBridge + ScanManager blocks in lifespan startup and shutdown
- `tests/test_dashboard_cloud_switcher.py` - Removed xfail markers from test_three_provider_managers_on_app_state and test_provider_scan_state_independent

## Decisions Made

- Removed xfail markers from `test_three_provider_managers_on_app_state` and `test_provider_scan_state_independent` because implementation satisfies their assertions — keeping `strict=True` would cause XPASS failure. This follows the same precedent established in 34-01 (strict=False) and 36-01 (remove marker entirely).
- Per-provider ScanManager instances constructed with `ScanManager()` — same pattern as existing `scan_manager`. No special arguments needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed xfail markers from two tests after implementation satisfied assertions**
- **Found during:** Task 1 verification
- **Issue:** `strict=True` xfail tests became XPASS failures when implementation satisfied their assertions (`test_three_provider_managers_on_app_state`, `test_provider_scan_state_independent`)
- **Fix:** Removed `@pytest.mark.xfail(strict=True, ...)` decorator from both tests
- **Files modified:** tests/test_dashboard_cloud_switcher.py
- **Verification:** Re-ran targeted tests — 2 passed; full dashboard suite 304 passed, 13 xfailed, 15 xpassed (no failures)
- **Committed in:** c617c32 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Auto-fix required for correct test behavior. Identical precedent to 34-01 and 36-01 xfail removal patterns.

## Issues Encountered

None beyond the xfail marker removal above.

## Next Phase Readiness

- Per-provider state foundation complete — app.state has all six per-provider objects (3 ScanManagers + 3 EventBridges)
- Plans 37-03 and 37-04 can proceed implementing per-provider route handlers that read from app.state.{provider}_scan_manager
- Two CLOUD-09 stubs (test_three_provider_managers_on_app_state, test_provider_scan_state_independent) now passing
- Remaining 12 stubs in test_dashboard_cloud_switcher.py still gating further implementation

---
*Phase: 37-cloud-provider-switcher*
*Completed: 2026-03-08*
