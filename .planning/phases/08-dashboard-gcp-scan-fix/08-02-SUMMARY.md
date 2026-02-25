---
phase: 08-dashboard-gcp-scan-fix
plan: 02
subsystem: testing
tags: [dashboard, gcp, azure, wizard, regression-tests, error-ux, parity]

# Dependency graph
requires:
  - phase: 08-dashboard-gcp-scan-fix
    plan: 01
    provides: Fixed _enumerate_accounts (6-arg GCP call, ProjectInfo.project_id, Azure 'id' key, error-transparent return structure)
  - phase: 05-web-dashboard
    provides: dashboard scan wizard routes (scan.py) and step3_accounts.html template
provides:
  - Regression tests: _enumerate_accounts GCP 6-arg call verification
  - Regression tests: ProjectInfo.project_id extraction (not raw object)
  - Regression tests: Azure 'id' key access and display_name fallback
  - Regression tests: _build_discovery_providers GCP 6-arg call with include/exclude patterns
  - Wizard error UX tests: inline error per provider, all-fail blocking, working-not-blocked
  - CLI-vs-dashboard parity test proving identical project_id extraction
  - Bug fix: Azure display_name empty-string fallback now uses 'or' operator
affects: [08-dashboard-gcp-scan-fix]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "sys.modules injection for google.auth and azure.identity stubs enables GCP/Azure tests without cloud SDKs installed"
    - "Pre-import provider modules before mock.patch to ensure lazy imports are resolved for patching"
    - "Mock at SDK function level (cloud_usage.providers.gcp.projects.enumerate_gcp_projects) to test real _enumerate_accounts code path"
    - "call_args.args tuple length checked to verify positional-not-keyword arg usage"

key-files:
  created: []
  modified:
    - tests/test_dashboard_scan.py
    - tests/test_dashboard_wizard.py
    - src/cloud_usage/dashboard/routes/scan.py

key-decisions:
  - "Azure display_name fallback uses 'or' operator (s.get('display_name') or s.get('id', '')) so empty-string display_name falls back to id — dict.get() default only triggers on missing key, not empty string"
  - "Parity test mocks at SDK level (not _enumerate_accounts level) to exercise the real dashboard code path and prove it processes ProjectInfo objects correctly"
  - "call_args.args tuple length assertion is the definitive check for positional vs keyword arg usage — len(call_args.args) == 6 proves no keyword args sneaked in"

patterns-established:
  - "Use _make_project_info() and _make_subscription_dict() factories in tests to decouple from ProjectInfo/dict structure details"
  - "Provider stub setup via helper method (_setup_google_auth_stub, _setup_azure_stub) for DRY test setup across multiple test methods"

requirements-completed: [DISC-02, DISC-03, DISC-07, PLAT-02]

# Metrics
duration: 7min
completed: 2026-02-25
---

# Phase 8 Plan 2: Dashboard GCP Scan Fix - Regression Tests Summary

**10 regression tests covering all 4 dashboard scan bugs, wizard error UX paths, and CLI-vs-dashboard parity; plus auto-fixed Azure display_name empty-string fallback bug.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-25T15:05:51Z
- **Completed:** 2026-02-25T15:12:50Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added TestEnumerateAccountsGCP (3 tests): verifies 6-arg call signature, ProjectInfo.project_id extraction, and error capture
- Added TestEnumerateAccountsAzure (3 tests): verifies 'id' key usage, display_name empty-string fallback, and error capture
- Added TestBuildDiscoveryProvidersGCPCallSignature (2 tests): verifies _build_discovery_providers passes 6 positional args including include/exclude patterns
- Added TestWizardErrorUX (4 tests): inline error for single-provider failure, blocking message for all-providers-fail, working provider not blocked, filter-accounts with new return structure
- Added TestCLIDashboardParity (1 test): proves dashboard extracts identical project_id strings as CLI path would
- Auto-fixed Bug: Azure display_name fallback now uses `or` operator to handle empty-string display_name values

## Task Commits

Each task was committed atomically:

1. **Task 1: Add _enumerate_accounts and _build_discovery_providers regression tests** - `38b42c3` (test)
2. **Task 2: Add wizard error UX tests and CLI-vs-dashboard parity test** - `480c723` (test)

## Files Created/Modified

- `tests/test_dashboard_scan.py` - Added module-level helpers (_make_project_info, _make_subscription_dict), TestEnumerateAccountsGCP (3 tests), TestEnumerateAccountsAzure (3 tests), TestBuildDiscoveryProvidersGCPCallSignature (2 tests)
- `tests/test_dashboard_wizard.py` - Added TestWizardErrorUX (4 tests), TestCLIDashboardParity (1 test)
- `src/cloud_usage/dashboard/routes/scan.py` - Fixed Azure display_name fallback from `s.get("display_name", s.get("id", ""))` to `s.get("display_name") or s.get("id", "")`

## Decisions Made

- Azure display_name fallback changed to use `or` operator: `dict.get(key, default)` only activates default when key is absent, but `or` also handles the empty-string case. This is the correct behavior per the display_name fallback intent.
- Parity test (TestCLIDashboardParity) mocks at `enumerate_gcp_projects` SDK level (not `_enumerate_accounts`) so the real dashboard code path runs — this is a stronger correctness proof than mocking the outer function.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Azure display_name empty-string fallback in _enumerate_accounts**
- **Found during:** Task 1 (test_enumerate_azure_display_name_fallback_uses_id)
- **Issue:** `s.get("display_name", s.get("id", ""))` does not fall back when display_name key exists but has value `""`. The existing code returns `""` instead of the subscription id.
- **Fix:** Changed to `s.get("display_name") or s.get("id", "")` which uses Python's `or` operator to handle both missing-key and empty-string cases
- **Files modified:** `src/cloud_usage/dashboard/routes/scan.py`
- **Verification:** test_enumerate_azure_display_name_fallback_uses_id passes; all 10 test_dashboard_scan.py tests pass
- **Committed in:** `38b42c3` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug: empty-string display_name not falling back to id)
**Impact on plan:** Necessary correctness fix. The test correctly exposed a gap in the original bug fix from plan 08-01. No scope creep.

## Issues Encountered

- Pre-existing test `test_web_flag_launches_uvicorn` continues to fail due to Python 3.9 vs 3.10+ runtime mismatch. All 39 other tests pass (29 from test_dashboard_wizard.py + 10 from test_dashboard_scan.py).

## Next Phase Readiness

- All 4 confirmed bugs from plan 08-01 are now covered by regression tests
- Error UX paths fully tested (inline error, blocking message, partial-failure scenario)
- CLI-vs-dashboard parity proven through SDK-level mock test
- Phase 8 complete: no remaining open items

## Self-Check: PASSED

- tests/test_dashboard_scan.py: FOUND
- tests/test_dashboard_wizard.py: FOUND
- src/cloud_usage/dashboard/routes/scan.py: FOUND
- Commit 38b42c3: FOUND
- Commit 480c723: FOUND

---
*Phase: 08-dashboard-gcp-scan-fix*
*Completed: 2026-02-25*
