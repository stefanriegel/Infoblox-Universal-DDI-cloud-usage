---
phase: 02-concurrent-execution-hardening
plan: "02"
subsystem: api
tags: [azure-mgmt, ComputeManagementClient, NetworkManagementClient, VisibleRetryPolicy, make_retry_policy, concurrent, threading, error-handling, progress-output, socket-lifecycle]

# Dependency graph
requires:
  - phase: 02-concurrent-execution-hardening
    plan: "01"
    provides: "VisibleRetryPolicy, make_retry_policy(), and AzureDiscovery with optional pre-built client kwargs"
  - phase: 01-credential-chain-and-code-correctness
    provides: "get_azure_credential() singleton, AzureConfig, checkpoint system"
provides:
  - "discover_subscription() with per-subscription client lifecycle using `with` blocks for all five management clients"
  - "Per-subscription progress output: [N/total] sub_id on success, [N/total] sub_id: FAILED -- error on failure"
  - "Resilient scan loop: failed subscriptions continue past, partial data preserved, not added to scanned_subs"
  - "Failure summary at end of scan with dict error format and backward-compat string format support"
  - "retry_on_failure decorator removed"
  - "Socket usage bounded by subscription_workers * 5 clients"
affects:
  - downstream-azure-scan-users

# Tech tracking
tech-stack:
  added:
    - "ComputeManagementClient, DnsManagementClient, NetworkManagementClient, PrivateDnsManagementClient, ResourceManagementClient imported directly in discover.py (previously only used inside AzureDiscovery)"
    - "make_retry_policy imported from .azure_discovery"
    - "get_azure_credential imported from .config (top-level, not deferred)"
  patterns:
    - "Per-subscription with block: all five clients created and closed atomically per subscription -- socket count bounded at subscription_workers*5"
    - "Credential singleton warmed once on main thread before ThreadPoolExecutor to avoid InteractiveBrowserCredential race condition"
    - "Error dict format: {sub_id, error} -- JSON-serializable, backward-compat string handling for resumed checkpoints"
    - "completed_count initialized from len(scanned_subs) to correctly count resumed subscriptions in progress display"

key-files:
  created: []
  modified:
    - "azure_discovery/discover.py"

key-decisions:
  - "Credential singleton obtained once before ThreadPoolExecutor block -- InteractiveBrowserCredential must not be called from worker threads (headless env raises ClientAuthenticationError since azure-identity 1.13.0)"
  - "reuse existing threading.Lock as print_lock for VisibleRetryPolicy -- one lock for all thread-safe output"
  - "errors list uses dict format {sub_id, error} for machine-readable structure; both dict and legacy string formats handled in summary/file output for checkpoint backward compat"
  - "Dummy AzureDiscovery at end of main() uses all_subs_total[0] (not all_subs[0]) -- all_subs may be empty when all subscriptions were resumed from checkpoint"
  - "Remove retry_on_failure decorator and unused imports (time, functools.wraps) -- SDK RetryPolicy from Plan 01 supersedes custom backoff"

patterns-established:
  - "Per-subscription client with block: ComputeManagementClient + 4 others all opened and closed together, progress printed after with-block exits"
  - "Failed subscription handling: increment counter, append error dict, print FAILED line, continue loop -- never re-raise"

requirements-completed: [CONC-01, CONC-02, CONC-03]

# Metrics
duration: 1min
completed: 2026-02-18
---

# Phase 2 Plan 2: Per-Subscription Client Lifecycle and Resilient Scan Loop Summary

**discover_subscription() refactored to create and close all five Azure management clients per subscription in `with` blocks with VisibleRetryPolicy, printing [N/total] progress, surviving failures, and preserving partial data**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-18T21:27:41Z
- **Completed:** 2026-02-18T21:29:08Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Refactored `discover_subscription()` to open all five management clients (Compute, Network, Resource, Dns, PrivateDns) inside a single `with` block -- clients are guaranteed closed after each subscription scan regardless of success or failure
- Passed `VisibleRetryPolicy` (from `make_retry_policy()`) to every client constructor, enabling Retry-After-aware backoff with visible throttle messages per subscription
- Warmed credential singleton once on main thread before `ThreadPoolExecutor` to prevent `InteractiveBrowserCredential` being called from worker threads
- Added `[N/total] sub_id` progress output on success and `[N/total] sub_id: FAILED -- error` on failure; `completed_count` correctly initialized from `len(scanned_subs)` for resumed scans
- Scan loop continues past failures -- failed subscriptions are NOT added to `scanned_subs` (retried on resume), partial data from partial failures is preserved in `all_native_objects`
- Updated failure summary and error log to handle both new dict format `{sub_id, error}` and legacy string format from old checkpoints
- Removed `retry_on_failure` decorator and unused `time`/`functools.wraps` imports

## Task Commits

Each task was committed atomically:

1. **Task 1: Refactor discover_subscription() with per-sub client lifecycle and retry policy** - `9d24614` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `azure_discovery/discover.py` - Removed `retry_on_failure`; added management client imports and `make_retry_policy`/`get_azure_credential` imports; refactored `discover_subscription()` with per-sub `with` block; added `completed_count` progress tracking; updated `as_completed` loop for resilient failure handling; updated error summary/log for dict/string compat; fixed dummy AzureDiscovery to use `all_subs_total[0]`

## Decisions Made
- Credential singleton obtained once before `ThreadPoolExecutor` block (not per-subscription) -- `InteractiveBrowserCredential` must not be called from worker threads
- Reuse existing `threading.Lock` as `print_lock` for `VisibleRetryPolicy` -- single lock for all thread-safe console output
- `errors` list now stores dicts `{sub_id, error}` for structured data; both dict and legacy string formats handled in failure summary and error log file for backward compatibility with existing checkpoints
- Dummy `AzureDiscovery` at end of `main()` uses `all_subs_total[0]` instead of `all_subs[0]` -- `all_subs` is empty when resuming a fully-completed scan
- Removed `retry_on_failure` decorator entirely -- SDK `RetryPolicy` from Plan 01 handles all retries with proper Retry-After header support

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed dummy AzureDiscovery to use all_subs_total[0] not all_subs[0]**
- **Found during:** Task 1 (reviewing dummy discovery section)
- **Issue:** Original code used `all_subs[0]` for the dummy AzureDiscovery subscription ID at end of main(). When resuming from a checkpoint where all subscriptions were already scanned, `all_subs` is empty (filtered to remaining subs) so `all_subs[0]` would raise IndexError
- **Fix:** Changed to `all_subs_total[0] if all_subs_total else ""` which uses the full pre-filtering list
- **Files modified:** azure_discovery/discover.py
- **Verification:** `all_subs_total` always holds the complete subscription list captured before checkpoint filtering
- **Committed in:** `9d24614` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The bug fix prevents a crash on checkpoint resume when all subscriptions were already completed. Necessary for correctness.

## Issues Encountered
- Azure packages not installed in system Python3 environment -- verified using `python3 -m py_compile` for syntax checks and `grep` content checks instead of runtime import checks. All structural verification passed. Runtime behavior requires packages installed per `requirements.txt`.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 2 is now complete: VisibleRetryPolicy (Plan 01) + per-subscription client lifecycle (Plan 02) fully implemented
- Socket usage is bounded: at most `subscription_workers * 5` management clients open simultaneously
- Retry events are visible during throttled scans
- Failed subscriptions are recoverable via resume
- No blockers for Phase 3 or downstream work

## Self-Check: PASSED
- SUMMARY.md exists at .planning/phases/02-concurrent-execution-hardening/02-02-SUMMARY.md
- azure_discovery/discover.py exists and modified
- Commit 9d24614 exists in git log

---
*Phase: 02-concurrent-execution-hardening*
*Completed: 2026-02-18*
