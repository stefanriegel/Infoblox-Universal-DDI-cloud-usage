---
phase: 37-cloud-provider-switcher
plan: "04"
subsystem: ui
tags: [fastapi, htmx, jinja2, routing, cloud-switcher]

# Dependency graph
requires:
  - phase: 37-02
    provides: three per-provider ScanManager instances on app.state (aws/azure/gcp)
  - phase: 37-03
    provides: provider-pill CSS and base.html provider-selector markup

provides:
  - _get_provider_tab_context() helper building provider-aware Jinja2 context with tab_base and provider
  - /cloud/{provider}/tab/{tab_name} route returning per-provider tab HTML
  - /cloud route updated to default to AWS via _get_provider_tab_context()
  - tab_bar.html cloud tab links parameterized via tab_base variable
  - progress.html scan_complete hx-get using tab_base conditional for per-provider reload

affects: [phase 37-05, any future tab routes]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "VALID_CLOUD_PROVIDERS frozenset guards invalid provider names at route level"
    - "getattr(app.state, f'{provider}_scan_manager') dynamic per-provider manager lookup"
    - "tab_base Jinja2 variable pattern for backward-compatible URL parameterization"
    - "Jinja2 {% set base = tab_base if tab_base is defined else '' %} for graceful degradation"

key-files:
  created: []
  modified:
    - src/cloud_usage/dashboard/routes/pages.py
    - src/cloud_usage/dashboard/templates/partials/tab_bar.html
    - src/cloud_usage/dashboard/templates/pages/progress.html
    - tests/test_dashboard_cloud_switcher.py

key-decisions:
  - "TestClient used with lifespan (with TestClient(app) as client:) for per-provider route tests — lifespan registers scan managers"
  - "tab_bar.html backward compatible via base = '' when tab_base undefined; NIOS/AD links remain hardcoded /tab/nios and /tab/ad"
  - "progress.html scan_complete uses tab_base conditional — SSE sse-connect URL unchanged (no per-provider SSE endpoint yet)"
  - "xfail(strict=True) markers removed from 6 implemented tests; xfail(strict=False) removed from invalid-provider test once explicit 404 route exists"

patterns-established:
  - "Pattern: Jinja2 tab_base variable for provider-scoped HTMX URLs — set in _get_provider_tab_context(), resolved in tab_bar.html via base local"

requirements-completed: [CLOUD-08, CLOUD-09]

# Metrics
duration: 15min
completed: 2026-03-08
---

# Phase 37 Plan 04: Per-Provider Tab Routes and Template Parameterization Summary

**Per-provider tab routes (/cloud/{aws|azure|gcp}/tab/{tab_name}) wired end-to-end with backward-compatible tab_bar.html parameterization via tab_base variable**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-08T18:49:14Z
- **Completed:** 2026-03-08T18:55:26Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added VALID_CLOUD_PROVIDERS frozenset and `_get_provider_tab_context()` helper in pages.py, building a provider-aware context with `tab_base`, `provider`, `active_provider`, and per-provider scan manager state
- Added `/cloud/{provider}/tab/{tab_name}` route returning 200 for aws/azure/gcp and 404 for invalid providers; updated `/cloud` route to default to AWS via the new helper
- Parameterized tab_bar.html cloud tab links via `{{ base }}/tab/progress|results|summary` (NIOS and AD links unchanged); fixed progress.html `scan_complete` hx-get to use `tab_base` conditional

## Task Commits

Each task was committed atomically:

1. **Task 1: Add _get_provider_tab_context() and per-provider tab route** - `73329b2` (feat)
2. **Task 2: Parameterize tab_bar.html and fix progress.html scan_complete route** - `7a11d7f` (feat)

**Plan metadata:** (to follow in final commit)

## Files Created/Modified

- `src/cloud_usage/dashboard/routes/pages.py` - Added VALID_CLOUD_PROVIDERS, _get_provider_tab_context(), /cloud/{provider}/tab/{tab_name} route, updated /cloud route
- `src/cloud_usage/dashboard/templates/partials/tab_bar.html` - Added tab_base variable; cloud tab links use {{ base }}/tab/*
- `src/cloud_usage/dashboard/templates/pages/progress.html` - scan_complete hx-get uses tab_base conditional
- `tests/test_dashboard_cloud_switcher.py` - Removed xfail markers from 6 implemented tests; switched to lifespan TestClient pattern

## Decisions Made

- Used `with TestClient(app) as client:` lifespan pattern for per-provider route tests — plain `TestClient(create_app())` doesn't run lifespan so scan managers are absent; this was a bug in the test scaffold that needed fixing as part of implementation
- tab_bar.html backward compatible: `{% set base = tab_base if tab_base is defined else "" %}` ensures NIOS/AD calculator tab bars still link to `/tab/progress` etc. without `tab_base` in context
- progress.html SSE sse-connect left unchanged at `/api/sse/progress` — per-provider SSE endpoint is not created in this phase; the `scan_complete` hx-get is the only fix needed for correct tab reload

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test scaffold used TestClient without lifespan context**
- **Found during:** Task 1 (running the target tests)
- **Issue:** `test_aws_tab_progress_returns_200` and 5 other tests used `TestClient(create_app())` without `with` — lifespan never ran, so `aws_scan_manager` was absent from app.state causing AttributeError → tests remained XFAIL even after routes were added
- **Fix:** Changed all 6 affected tests to `with TestClient(app) as client:` pattern (matching home_routing and wizard test precedents); removed xfail markers since assertions now pass
- **Files modified:** tests/test_dashboard_cloud_switcher.py
- **Verification:** All 6 tests pass; 10/14 cloud_switcher tests green, 4 remaining xfail (future routes)
- **Committed in:** 73329b2 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 bug)
**Impact on plan:** Required to make tests pass at all — tests would never leave XFAIL state without lifespan. No scope creep.

## Issues Encountered

None beyond the test scaffold lifespan issue documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Per-provider tab routes fully functional: clicking a provider pill will reload the tab container pointing to /cloud/{provider}/tab/* routes
- tab_bar.html and progress.html are backward compatible — NIOS and AD calculators unaffected
- Remaining CLOUD-09 tests (scan start routes, per-provider SSE, wizard) are the next implementation targets

---
*Phase: 37-cloud-provider-switcher*
*Completed: 2026-03-08*
