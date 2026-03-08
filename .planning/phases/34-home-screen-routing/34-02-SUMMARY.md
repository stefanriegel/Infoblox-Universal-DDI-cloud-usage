---
phase: 34-home-screen-routing
plan: 02
subsystem: ui
tags: [jinja2, fastapi, css, htmx, design-system]

# Dependency graph
requires:
  - phase: 33-design-foundation
    provides: design-system.css with --ib-* tokens, .btn, .site-header, .container
  - phase: 34-01
    provides: xfail test scaffold for home screen (HOME-01, HOME-02, ROUTE-01, ROUTE-02, DESIGN-02)

provides:
  - home.html — self-contained selector screen with three calculator cards
  - --ib-card-border: #E5E7EB design token in design-system.css :root
  - .calculator-cards grid and .calculator-card component styles in app.css
  - GET / now renders home.html instead of base.html tab-dashboard

affects:
  - 34-03-plan (adds /cloud, /nios, /ad routes — depends on home screen links being correct)
  - 35-cloud-calculator (entry point is /cloud link from home screen)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Self-contained Jinja2 templates (no base.html inheritance) for distinct page types
    - TemplateResponse with minimal context dict {"request": request} for static screens

key-files:
  created:
    - src/cloud_usage/dashboard/templates/home.html
  modified:
    - src/cloud_usage/dashboard/static/design-system.css
    - src/cloud_usage/dashboard/static/app.css
    - src/cloud_usage/dashboard/routes/pages.py
    - tests/test_dashboard_home_routing.py

key-decisions:
  - "home.html is self-contained (no base.html extends) — inheriting base.html would trigger hx-get=/tab/progress on every home screen load"
  - "htmx.min.js included in home.html for consistency even though no HTMX triggers fire on home screen"
  - "sse.js intentionally omitted from home.html — no SSE on home screen"
  - "--ib-card-border: #E5E7EB added as separate token from --ib-gray-200: #e8eaed — spec mandates #E5E7EB exactly (DESIGN-02)"

patterns-established:
  - "Self-contained template pattern: distinct page types (home selector vs app shell) use separate full HTML files, not base.html inheritance"
  - "Minimal context pattern: static/informational routes use {'request': request} only, no _get_tab_context"

requirements-completed: [HOME-01, HOME-02, ROUTE-02, DESIGN-02]

# Metrics
duration: 7min
completed: 2026-03-08
---

# Phase 34 Plan 02: Home Screen Build Summary

**Self-contained home.html selector with three calculator cards, --ib-card-border CSS token, and GET / swapped from base.html tab-dashboard to home screen**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-03-08T15:14:00Z
- **Completed:** 2026-03-08T15:20:49Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added `--ib-card-border: #E5E7EB` to design-system.css :root (DESIGN-02 satisfied)
- Appended `.calculator-cards` grid and `.calculator-card` component styles to app.css
- Created self-contained `home.html` with three calculator cards linking to /cloud, /nios, /ad
- Swapped `index()` in pages.py to render `home.html` with minimal context (no _get_tab_context)
- Removed xfail markers from 5 home-screen tests — all 5 now PASS cleanly

## Task Commits

Each task was committed atomically:

1. **Task 1: Add --ib-card-border token and .calculator-card CSS** - `88a86c9` (feat)
2. **Task 2: Create home.html and swap root route** - `633629d` (feat)

## Files Created/Modified

- `src/cloud_usage/dashboard/templates/home.html` — Self-contained home selector screen; three .calculator-card divs linking to /cloud, /nios, /ad; no base.html inheritance
- `src/cloud_usage/dashboard/static/design-system.css` — Added --ib-card-border: #E5E7EB token to :root block
- `src/cloud_usage/dashboard/static/app.css` — Appended .calculator-cards grid and .calculator-card styles
- `src/cloud_usage/dashboard/routes/pages.py` — index() now renders home.html with {"request": request} instead of base.html with _get_tab_context
- `tests/test_dashboard_home_routing.py` — Removed xfail markers from 5 home-screen tests (PASSED); /cloud, /nios, /ad route tests remain xfail for Plan 03

## Decisions Made

- **Self-contained template:** home.html does not extend base.html. Inheriting base.html would trigger `hx-get="/tab/progress" hx-trigger="load"` on every home screen visit, firing an unwanted background Cloud Calculator load.
- **Separate card border token:** `--ib-card-border: #E5E7EB` added as its own token rather than reusing `--ib-gray-200: #e8eaed`. The two colors are different (#E5E7EB vs #e8eaed) and the spec mandates #E5E7EB exactly for DESIGN-02.
- **htmx.min.js included, sse.js omitted:** HTMX included for consistency (no harm, no auto-triggers); SSE excluded since there are no server-sent event streams on the home screen.

## Deviations from Plan

None — plan executed exactly as written. The xfail marker removal was part of the planned done criteria ("5 home-screen tests in test_dashboard_home_routing.py pass — no longer xfail").

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Home screen is complete and tests green (HOME-01, HOME-02, ROUTE-02, DESIGN-02)
- Plan 03 can proceed: add GET /cloud, /nios, /ad routes and remove their 3 remaining xfail stubs
- The three calculator card links (/cloud, /nios, /ad) are in place in home.html

---
*Phase: 34-home-screen-routing*
*Completed: 2026-03-08*
