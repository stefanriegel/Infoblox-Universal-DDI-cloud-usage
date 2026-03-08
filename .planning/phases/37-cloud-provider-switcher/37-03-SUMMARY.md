---
phase: 37-cloud-provider-switcher
plan: "03"
subsystem: ui
tags: [htmx, css, jinja2, provider-switcher, breadcrumb, cloud-calculator]

# Dependency graph
requires:
  - phase: 37-01
    provides: xfail test stubs for CLOUD-08/CLOUD-09 provider switcher
  - phase: 36-calculator-visual-redesign
    provides: calc_theme injection, breadcrumb-nav CSS block, base.html structure

provides:
  - Provider selector strip CSS (.provider-selector, .provider-pill, .provider-pill.active)
  - Provider selector nav block in base.html conditioned on calc_theme == 'calc-cloud'
  - Per-provider hx-get on #tab-container (cloud uses /cloud/{active_provider}/tab/{active_tab})

affects:
  - 37-04 (per-provider routes need tab-container hx-get to load from /cloud/{provider}/tab/progress)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CSS design tokens for theming: --calc-accent, --ib-gray-* used in new pill components"
    - "Jinja2 conditional block: {% if calc_theme == 'calc-cloud' %} guards provider-selector nav and tab-container hx-get"
    - "HTMX pill switcher: hx-get on buttons targeting #tab-container, no hx-push-url"

key-files:
  created: []
  modified:
    - src/cloud_usage/dashboard/static/app.css
    - src/cloud_usage/dashboard/templates/base.html
    - tests/test_dashboard_cloud_switcher.py

key-decisions:
  - "37-03: xfail markers removed from test_css_has_provider_pill_styles and test_base_html_has_provider_pills — assertions now satisfied, strict=True XPASS = pytest failure (same precedent as 34-01, 36-01)"
  - "37-03: tab-container else branch preserves /tab/{active_tab} conditional (including 'progress'/'nios'/'ad' guard) for NIOS and AD calculators — no backward-compat breakage"

patterns-established:
  - "Provider pill pattern: .provider-pill button with hx-get, hx-target, hx-push-url=false for HTMX tab switching"

requirements-completed:
  - CLOUD-08

# Metrics
duration: 8min
completed: 2026-03-08
---

# Phase 37 Plan 03: Provider Selector CSS and Nav Block Summary

**Provider pill switcher CSS and base.html nav block wired to per-provider HTMX routes, with backward-compatible tab-container hx-get for NIOS and AD calculators**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-08T18:42:35Z
- **Completed:** 2026-03-08T18:50:55Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added complete provider selector CSS to app.css: `.provider-selector`, `.provider-selector .container`, `.provider-selector-label`, `.provider-pill`, `.provider-pill:hover`, `.provider-pill.active` — all using design tokens
- Inserted provider-selector nav block in base.html between breadcrumb and main, conditioned on `calc_theme == 'calc-cloud'`, with active-class logic for each pill
- Updated `#tab-container` `hx-get` to use `/cloud/{{ active_provider }}/tab/{{ active_tab }}` for cloud and existing `/tab/...` path for NIOS/AD (backward-compatible)
- Removed two xfail markers (`test_css_has_provider_pill_styles`, `test_base_html_has_provider_pills`) after implementation satisfied assertions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add .provider-selector and .provider-pill CSS to app.css** - `297340a` (feat)
2. **Task 2: Add provider-selector nav block to base.html and fix tab-container hx-get** - `be30a4e` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/cloud_usage/dashboard/static/app.css` - Appended provider selector strip CSS block after .section-divider
- `src/cloud_usage/dashboard/templates/base.html` - Added provider-selector nav block + fixed #tab-container hx-get with calc_theme conditional
- `tests/test_dashboard_cloud_switcher.py` - Removed xfail from two CLOUD-08 tests now satisfied

## Decisions Made

- Removed xfail markers from `test_css_has_provider_pill_styles` and `test_base_html_has_provider_pills` — assertions now satisfied by implementation; strict=True XPASS = pytest failure (same precedent as 34-01, 36-01)
- `tab-container` else branch preserves the existing active_tab guard (`active_tab in ('progress', 'nios', 'ad')`) for NIOS and AD calculators — no backward-compatibility breakage

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Provider selector strip and pills are now visible on all Cloud Calculator pages (wizard, progress, results)
- HTMX wiring ready for per-provider route handlers (Phase 37 Plan 04)
- All NIOS/AD dashboard tests pass — backward compatibility confirmed

---
*Phase: 37-cloud-provider-switcher*
*Completed: 2026-03-08*
