---
phase: 24-wizard-navigation-fix
plan: 01
subsystem: ui
tags: [htmx, fastapi, wizard, navigation, hx-redirect]

# Dependency graph
requires: []
provides:
  - "scan_start endpoint returning empty 200 response with HX-Redirect: /tab/progress header"
  - "step4_review.html form with plain hx-post only — no JS event handlers"
  - "test asserting HX-Redirect header on successful scan start (NAV-01/02/03)"
affects: [wizard, scan-lifecycle, navigation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "HX-Redirect for server-driven HTMX navigation: return Response(content='', status_code=200, headers={'HX-Redirect': '/tab/progress'}) — HTMX follows as full-page navigate, no hx-on JS needed"

key-files:
  created: []
  modified:
    - src/cloud_usage/dashboard/routes/scan.py
    - src/cloud_usage/dashboard/templates/partials/wizard/step4_review.html
    - tests/test_dashboard_wizard.py
    - tests/test_dashboard_app.py

key-decisions:
  - "Use server-driven HX-Redirect instead of JS hx-on::after-request + htmx.ajax — HTMX natively follows HX-Redirect as full-page navigation, no JS involvement required"
  - "step4_review.html Back button retains hx-target='#wizard-content' (correct) — only the scan start form element needed to be stripped"

patterns-established:
  - "HX-Redirect pattern: return Response(content='', status_code=200, headers={'HX-Redirect': '/tab/progress'}) — HTMX follows as full-page navigate, no hx-on JS needed"

requirements-completed: [NAV-01, NAV-02, NAV-03]

# Metrics
duration: 1min
completed: 2026-03-03
---

# Phase 24 Plan 01: Wizard Navigation Fix Summary

**Server-driven HX-Redirect replaces brittle hx-on JS navigation on scan start: scan_start returns empty 200 with HX-Redirect header, step4_review form stripped to plain hx-post, test asserts header presence**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-03T20:45:28Z
- **Completed:** 2026-03-03T20:46:31Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- NAV-01: `scan_start` endpoint returns `Response(content="", status_code=200, headers={"HX-Redirect": "/tab/progress"})` — HTMX follows as full-page navigation to progress tab
- NAV-02: `step4_review.html` form element stripped to `hx-post="/api/scan/start"` only — no `hx-on`, `hx-target`, or `hx-swap` on the form element
- NAV-03: `test_scan_start_when_idle_returns_hx_redirect` passes asserting `response.headers.get("hx-redirect") == "/tab/progress"` with descriptive failure message

## Task Commits

Each task was committed atomically:

1. **Task 1: Verify all three requirements are satisfied** — verification only, no code changes needed
2. **Task 2: Commit the implementation** - `9199789` (feat)

**Plan metadata:** (docs: complete plan — created in final commit)

## Files Created/Modified

- `src/cloud_usage/dashboard/routes/scan.py` - scan_start endpoint returns HX-Redirect header instead of JSON
- `src/cloud_usage/dashboard/templates/partials/wizard/step4_review.html` - Form element has only hx-post, no JS event handlers
- `tests/test_dashboard_wizard.py` - Added test_scan_start_when_idle_returns_hx_redirect asserting HX-Redirect header
- `tests/test_dashboard_app.py` - Supporting test infrastructure for scan lifecycle

## Decisions Made

- Server-driven HX-Redirect chosen over client-side JS navigation: HTMX natively follows `HX-Redirect` as a full-page browser navigation, making the `hx-on::after-request` + `htmx.ajax` pattern unnecessary and error-prone. The server controls navigation destination.
- The Back button in step4_review.html retains `hx-target="#wizard-content"` which is correct — only the scan start `<form>` element needed to be stripped of extra HTMX attributes.

## Deviations from Plan

None - plan executed exactly as written. Implementation was already in the working tree; this plan verified correctness and committed.

## Issues Encountered

The verification grep check #4 (`grep -c "hx-on|hx-target|hx-swap" step4_review.html`) returned 1 instead of 0 because the Back button has `hx-target="#wizard-content"`. However, the actual NAV-02 requirement specifies "no hx-target, hx-swap, or hx-on **on the form element**" — the Back button's `hx-target` is intentional and correct. The requirement was fully satisfied.

The pre-existing `TestCLIWebFlag::test_web_flag_launches_uvicorn` failure (Python 3.9 version guard on CLI main()) is a known non-blocking issue per STATE.md. All dashboard tests (76/77) passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 24 is complete: wizard navigation uses clean server-driven HX-Redirect
- Clicking "Start Scan" in Step 4 navigates browser to /tab/progress via HTMX following HX-Redirect — no JS event handlers involved
- No blockers for future work

---
*Phase: 24-wizard-navigation-fix*
*Completed: 2026-03-03*
