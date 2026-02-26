---
phase: 09-integration-tech-debt-cleanup
plan: 01
subsystem: providers
tags: [aws, checkpoint, ddi-types, sse, asset-dedup, integration]

# Dependency graph
requires:
  - phase: 07-integration-gap-closure
    provides: Azure and GCP checkpoint symmetry patterns (reference implementation)
  - phase: 08-dashboard-gcp-scan-fix
    provides: Stable dashboard scan pipeline with working GCP enumeration
provides:
  - AWS checkpoint skip guard symmetric with Azure/GCP providers
  - DDI_TYPES single source of truth from categorizer (all 3 providers, 16 types)
  - Single scan_complete SSE emission ownership in _run_scan_pipeline finally block
  - 8 regression tests (3 INT-01, 3 INT-02, 2 INT-03)
affects: [10-any-future-provider, checkpoint-resume, asset-counting]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - checkpoint_engine threaded into all three provider constructors (AWS, Azure, GCP) symmetrically
    - DDI_TYPES imported from single canonical source (categorizer) across all counting modules
    - SSE scan_complete emission exclusively in finally block for reliable delivery on all exit paths

key-files:
  created: []
  modified:
    - src/cloud_usage/providers/aws/provider.py
    - src/cloud_usage/cli.py
    - src/cloud_usage/counting/asset_dedup.py
    - src/cloud_usage/dashboard/services/scan_manager.py
    - src/cloud_usage/dashboard/routes/scan.py
    - tests/test_aws_provider.py
    - tests/test_asset_dedup.py
    - tests/test_dashboard_scan.py
    - tests/test_dashboard_sse.py

key-decisions:
  - "[09-01]: AWSDiscoveryProvider.discover_account() checkpoint skip guard uses same pattern as Azure/GCP: load(), check providers.get('aws'), check account_id in completed_accounts"
  - "[09-01]: asset_dedup.DDI_TYPES replaced with import from categorizer -- removes 5-item AWS-only set and adds Azure/GCP DDI types (now 16 types covering all 3 providers)"
  - "[09-01]: DashboardProgressTracker.finish() docstring avoids the word 'emit_done' to pass source-inspection test asserting emit_done not in finish() source"
  - "[09-01]: test_dashboard_sse.py tests updated to add explicit bridge.emit_done() call after tracker.finish() to simulate the finally block -- tests now validate the correct ownership model"

patterns-established:
  - "All three providers (AWS, Azure, GCP) accept checkpoint_engine=None in constructor and skip discovered_account() for completed accounts"
  - "SSE scan_complete is always emitted by the finally block in _run_scan_pipeline -- not by finish() or early-return paths"

requirements-completed: [RESIL-01, ASSET-06, PLAT-02]

# Metrics
duration: 16min
completed: 2026-02-26
---

# Phase 9 Plan 1: Integration Tech Debt Cleanup Summary

**AWS checkpoint symmetry added, DDI_TYPES unified to 16-type cross-provider set, and scan_complete SSE emission fixed to exactly-once via finally block**

## Performance

- **Duration:** 16 min
- **Started:** 2026-02-26T12:32:27Z
- **Completed:** 2026-02-26T12:48:27Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- INT-01: AWSDiscoveryProvider now accepts `checkpoint_engine` and skips accounts in `completed_accounts`, matching Azure/GCP behavior exactly
- INT-01: Both CLI `_get_discovery_providers()` and dashboard `_build_discovery_providers()` pass `checkpoint_engine` to AWSDiscoveryProvider
- INT-02: `asset_dedup.DDI_TYPES` is now imported from `categorizer` (single source of truth) -- AWS-only 5-item set removed, replaced with 16-type all-provider set
- INT-03: `DashboardProgressTracker.finish()` no longer calls `emit_done()`; the `finally` block in `_run_scan_pipeline` is the sole owner
- INT-03: Redundant `event_bridge.emit_done()` removed from the `if not providers:` early-return path in `_run_scan_pipeline`
- 8 regression tests added confirming all three fixes; `test_dashboard_sse.py` updated to match new ownership model

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix all three integration gaps (INT-01, INT-02, INT-03)** - `b6d93ba` (fix)
2. **Task 2: Add regression tests for all three integration fixes** - `7161511` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/cloud_usage/providers/aws/provider.py` - Added `checkpoint_engine=None` param to `__init__`, stored as `self._checkpoint_engine`, added skip guard in `discover_account()`
- `src/cloud_usage/cli.py` - Added `checkpoint_engine=checkpoint_engine` to `AWSDiscoveryProvider(...)` call in `_get_discovery_providers()`
- `src/cloud_usage/counting/asset_dedup.py` - Replaced local 5-item `DDI_TYPES` set with `from cloud_usage.counting.categorizer import DDI_TYPES`
- `src/cloud_usage/dashboard/services/scan_manager.py` - Removed `self._event_bridge.emit_done()` from `DashboardProgressTracker.finish()`; updated docstring
- `src/cloud_usage/dashboard/routes/scan.py` - Added `checkpoint_engine=checkpoint_engine` to AWS provider call; removed `event_bridge.emit_done()` from early-return path
- `tests/test_aws_provider.py` - Added `TestAWSProviderCheckpointSkip` with 3 tests
- `tests/test_asset_dedup.py` - Added `TestDDITypesUnification` with 3 tests
- `tests/test_dashboard_scan.py` - Added `TestEmitDoneOwnership` with 2 tests (finish() no emit, AWS checkpoint wiring)
- `tests/test_dashboard_sse.py` - Updated 3 SSE tests to add explicit `bridge.emit_done()` after `tracker.finish()` to simulate the finally block; added `test_finish_does_not_emit_scan_complete` regression test

## Decisions Made

- `AWSDiscoveryProvider` docstring updated to document the new `checkpoint_engine` parameter, including the symmetry rationale.
- `asset_dedup.py` import order adjusted: `DDI_TYPES` import before `CloudResource` import (alphabetical, both from cloud_usage).
- The `finish()` docstring in `scan_manager.py` was written to avoid the string `emit_done` so the plan's automated verification test (`assert 'emit_done' not in src`) passes correctly.
- `test_dashboard_sse.py` tests were updated rather than removed -- the existing tests were relying on `finish()` calling `emit_done()` to unblock the SSE stream; fixed by adding explicit `bridge.emit_done()` to simulate the correct finally-block behavior.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SSE tests broken by INT-03 emit_done ownership change**
- **Found during:** Task 2 (adding regression tests)
- **Issue:** Three tests in `test_dashboard_sse.py` (`test_complete_account_emits_progress_event`, `test_finish_emits_scan_complete`, `test_multiple_providers_emit_separate_events`) were waiting for `emit_done()` to terminate the SSE consumer task. After INT-03 removed `emit_done()` from `finish()`, these tests timed out with `asyncio.exceptions.TimeoutError`.
- **Fix:** Added `bridge.emit_done()` call in each test's emit thread after `tracker.finish()`, simulating the `_run_scan_pipeline` finally block. Renamed `test_finish_emits_scan_complete` to `test_scan_complete_emitted_from_finally_block`. Added new `test_finish_does_not_emit_scan_complete` to explicitly document the new ownership model.
- **Files modified:** `tests/test_dashboard_sse.py`
- **Verification:** All 18 tests in `test_dashboard_sse.py` pass
- **Committed in:** `7161511` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** The SSE test fix was necessary for correctness -- the tests were testing behavior that INT-03 intentionally removed. No scope creep.

## Issues Encountered

- Python 3.9 test environment has 7 pre-existing failures in `test_cli.py` and `test_integration_aws.py` due to the preflight `Python 3.10+ required` check failing. These failures existed before this plan and are unrelated to the changes made here. Logged to `deferred-items.md`.

## Next Phase Readiness

- All three integration gaps closed. AWS checkpoint resume is now fully functional across CLI and dashboard.
- DDI_TYPES is unified -- any future provider adding DDI types only needs to update `categorizer.py`.
- scan_complete SSE is reliably emitted exactly once per scan (success, error, and cancellation paths all covered by the finally block).

---
*Phase: 09-integration-tech-debt-cleanup*
*Completed: 2026-02-26*

## Self-Check: PASSED

- FOUND: `.planning/phases/09-integration-tech-debt-cleanup/09-01-SUMMARY.md`
- FOUND: commit `b6d93ba` (fix: close INT-01, INT-02, INT-03)
- FOUND: commit `7161511` (test: regression tests)
