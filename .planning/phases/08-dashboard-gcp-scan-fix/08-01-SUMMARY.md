---
phase: 08-dashboard-gcp-scan-fix
plan: 01
subsystem: ui
tags: [dashboard, gcp, azure, aws, wizard, jinja2, bug-fix, error-ux]

# Dependency graph
requires:
  - phase: 05-web-dashboard
    provides: dashboard scan wizard routes (scan.py) and step3_accounts.html template
  - phase: 04-gcp-provider
    provides: enumerate_gcp_projects (6-arg signature, returns list[ProjectInfo])
  - phase: 03-azure-provider
    provides: list_subscriptions (returns dicts with 'id' key)
provides:
  - Fixed _enumerate_accounts: correct 6-arg enumerate_gcp_projects call, ProjectInfo.project_id access, Azure 'id' key
  - Fixed _build_discovery_providers: correct 6-arg enumerate_gcp_projects call with all positional args
  - Error-transparent _enumerate_accounts returning {"accounts": [...], "error": str|None} per provider
  - Inline per-provider error display in step3_accounts.html with actual API error message
  - All-providers-fail blocking message and disabled Next button in wizard step 3
affects: [08-dashboard-gcp-scan-fix]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_enumerate_accounts returns structured dict with 'accounts' and 'error' keys per provider for error transparency"
    - "Jinja2 namespace() used for cross-loop boolean accumulation (has_any_accounts.value)"

key-files:
  created: []
  modified:
    - src/cloud_usage/dashboard/routes/scan.py
    - src/cloud_usage/dashboard/templates/partials/wizard/step3_accounts.html
    - tests/test_dashboard_wizard.py

key-decisions:
  - "_enumerate_accounts return type changed from dict[str, list[dict]] to dict[str, dict] with 'accounts' and 'error' keys for error transparency without breaking caller structure"
  - "enumerate_gcp_projects called with 6 positional args (credentials, adc_project, None, None, include, exclude) in both _enumerate_accounts and _build_discovery_providers to match function signature"
  - "Azure dict uses 'id' key directly (no dead 'subscription_id' fallback) matching list_subscriptions() actual return structure"
  - "Failed providers show inline error but do not block wizard for other working providers; only all-providers-fail blocks with disabled Next button"

patterns-established:
  - "Provider enumeration errors: capture with str(exc), surface in per-provider dict under 'error' key, render inline in template"

requirements-completed: [DISC-02, DISC-03, DISC-07, PLAT-02]

# Metrics
duration: 2min
completed: 2026-02-25
---

# Phase 8 Plan 1: Dashboard GCP Scan Fix Summary

**Fixed 4 confirmed call-signature/type-iteration bugs in dashboard scan.py and added inline error UX to wizard step 3 so users can self-diagnose authentication and permission failures.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T15:00:08Z
- **Completed:** 2026-02-25T15:02:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Fixed Bug 1: `enumerate_gcp_projects` now called with all 6 positional args in `_enumerate_accounts` (was missing `project`, `org_id`, `include_patterns`, `exclude_patterns`)
- Fixed Bug 2: `ProjectInfo.project_id` accessed (not raw `ProjectInfo` object) in GCP account list construction
- Fixed Bug 3: `enumerate_gcp_projects` now called with all 6 positional args in `_build_discovery_providers` (was using wrong keyword args `include_patterns=`, `exclude_patterns=`)
- Fixed Bug 4: Azure uses `s.get("id", "")` directly (removed dead `s.get("subscription_id", ...)` fallback that mapped to nonexistent key)
- `_enumerate_accounts` returns `{"accounts": [...], "error": str|None}` per provider so callers can surface enumeration failures
- `step3_accounts.html` renders inline error blocks with actual API error text when a provider fails; shows blocking message and disables Next button when all providers fail

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix all provider bugs in scan.py and add error UX return structure** - `3c42997` (fix)
2. **Task 2: Update step3_accounts.html template for inline error display** - `7b3c714` (feat)

## Files Created/Modified

- `src/cloud_usage/dashboard/routes/scan.py` - Fixed 4 bugs, changed _enumerate_accounts return type to include error field, updated wizard_filter_accounts caller
- `src/cloud_usage/dashboard/templates/partials/wizard/step3_accounts.html` - Updated for new accounts structure, added per-provider inline errors, all-providers-fail blocking message and disabled button
- `tests/test_dashboard_wizard.py` - Updated _enumerate_accounts mock to new return structure

## Decisions Made

- `_enumerate_accounts` return type changed from `dict[str, list[dict]]` to `dict[str, dict]` with `accounts` and `error` keys: allows callers to distinguish empty-due-to-error from empty-by-design without exception bubbling
- Both call sites of `enumerate_gcp_projects` now use positional args matching the function's 6-arg signature (not keyword args for the middle positional args)
- Failed providers show error inline but the form still allows submission for working providers; only all-fail blocks the wizard

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing test mock to match new _enumerate_accounts return structure**
- **Found during:** Task 1 verification (running test suite)
- **Issue:** `test_accounts_step_returns_200` mocked `_enumerate_accounts` with old `{"aws": [...]}` list format; after return type change to `{"aws": {"accounts": [...], "error": None}}` the mock would cause template rendering to fail
- **Fix:** Updated mock return value in `tests/test_dashboard_wizard.py` to new dict structure
- **Files modified:** `tests/test_dashboard_wizard.py`
- **Verification:** 26 tests pass (1 pre-existing unrelated failure excluded)
- **Committed in:** `3c42997` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug: stale test mock)
**Impact on plan:** Necessary to keep test suite correct with code changes. No scope creep.

## Issues Encountered

- Pre-existing test `test_web_flag_launches_uvicorn` fails due to Python 3.9 vs 3.10+ runtime mismatch (CI guard exits early). This is unrelated to this plan's changes and existed before this work.

## Next Phase Readiness

- All 4 confirmed bugs fixed in dashboard scan path
- GCP wizard will correctly enumerate projects and display them by ID
- Azure wizard will correctly reference subscription IDs
- Inline error UX enables users to self-diagnose auth failures during wizard flow
- All existing tests pass (excluding the pre-existing Python version failure)
- No blockers for remaining phases

## Self-Check: PASSED

- scan.py: FOUND
- step3_accounts.html: FOUND
- SUMMARY.md: FOUND
- Commit 3c42997: FOUND
- Commit 7b3c714: FOUND

---
*Phase: 08-dashboard-gcp-scan-fix*
*Completed: 2026-02-25*
