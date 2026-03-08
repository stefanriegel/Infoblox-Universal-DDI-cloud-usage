---
phase: 34-home-screen-routing
plan: 03
subsystem: ui
tags: [fastapi, htmx, jinja2, routing]

# Dependency graph
requires:
  - phase: 34-02
    provides: home.html selector screen and GET / home route (this plan adds /cloud /nios /ad)
  - phase: 33-design-foundation
    provides: design-system.css and base.html shell used by all calculator routes
provides:
  - "GET /cloud route — renders base.html with active_tab=progress (Cloud Calculator)"
  - "GET /nios route — renders base.html with active_tab=nios (NIOS Calculator auto-load)"
  - "GET /ad route — renders base.html with active_tab=ad (AD Calculator auto-load)"
  - "base.html conditional HTMX initial tab load via active_tab Jinja2 expression"
affects:
  - 35-cloud-calculator-polish
  - 36-nios-calculator-polish
  - 37-ad-calculator-polish

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "HTMX conditional initial load: hx-get driven by Jinja2 active_tab expression in base.html"
    - "Calculator URL pattern: /cloud /nios /ad each render base.html shell with appropriate active_tab"

key-files:
  created: []
  modified:
    - src/cloud_usage/dashboard/routes/pages.py
    - src/cloud_usage/dashboard/templates/base.html
    - tests/test_dashboard_home_routing.py

key-decisions:
  - "base.html uses active_tab (already in context from _get_tab_context) rather than a new initial_tab variable — avoids redundant context key"
  - "/cloud uses active_tab=progress not active_tab=cloud — progress is the existing tab key for the Cloud Calculator initial state"
  - "xfail markers removed from routing tests on implementation (strict=True XPASS = failure, tests must run green)"

patterns-established:
  - "Calculator deep-link pattern: GET /cloud|nios|ad renders base.html with active_tab, HTMX fires initial load to /tab/progress|nios|ad"

requirements-completed:
  - ROUTE-01

# Metrics
duration: 5min
completed: 2026-03-08
---

# Phase 34 Plan 03: Home Screen Routing Summary

**Three dedicated calculator URLs (/cloud, /nios, /ad) with conditional HTMX initial tab auto-load via base.html active_tab expression**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-08T15:21:00Z
- **Completed:** 2026-03-08T15:26:41Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- base.html tab-container hx-get replaced from hardcoded `/tab/progress` to Jinja2 expression mapping active_tab to correct route
- Three route handlers added to pages.py: cloud_calculator, nios_calculator, ad_calculator
- All 8 tests in test_dashboard_home_routing.py pass (xfail markers removed from now-implemented routes)

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix base.html conditional HTMX initial tab load** - `cf5a53c` (feat)
2. **Task 2: Add /cloud, /nios, /ad route handlers to pages.py** - `5e157bc` (feat)

## Files Created/Modified

- `src/cloud_usage/dashboard/templates/base.html` - tab-container hx-get now uses active_tab Jinja2 expression
- `src/cloud_usage/dashboard/routes/pages.py` - three new GET route handlers inserted after index()
- `tests/test_dashboard_home_routing.py` - xfail markers removed, unused pytest import removed

## Decisions Made

- Used existing `active_tab` context key (already returned by `_get_tab_context`) rather than adding a new `initial_tab` key — avoids redundant context variable
- `/cloud` passes `active_tab="progress"` (not `"cloud"`) because `"progress"` is the existing tab key for the Cloud Calculator initial state that maps to `/tab/progress`
- xfail markers with `strict=True` make XPASS a test failure; removed markers when routes were implemented so tests turn genuinely green

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed xfail markers from routing tests after implementation**
- **Found during:** Task 2 (route handler verification)
- **Issue:** Tests marked `xfail(strict=True)` now XPASS (routes implemented) which pytest treats as FAILED — suite would not be green
- **Fix:** Removed xfail markers from test_cloud_route_returns_200, test_nios_route_returns_200, test_ad_route_returns_200; removed now-unused pytest import
- **Files modified:** tests/test_dashboard_home_routing.py
- **Verification:** All 8 tests PASSED (not XPASS) after marker removal
- **Committed in:** 5e157bc (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — xfail markers blocking green suite)
**Impact on plan:** Essential fix — plan's done criteria requires "full suite green". No scope creep.

## Issues Encountered

Pre-existing test_integration_aws.py / test_integration_azure.py / test_integration_gcp.py failures (`fold_enis_into_parents` import error) confirmed pre-existing via git stash check — out of scope. Logged to deferred-items per deviation rules.

## Next Phase Readiness

- All three calculator URLs functional: /cloud, /nios, /ad each load correct tab content
- HTMX navigation within each calculator (tab switching) still uses existing /tab/* routes — untouched
- Ready for Phase 35/36/37 calculator polish phases

---
*Phase: 34-home-screen-routing*
*Completed: 2026-03-08*
