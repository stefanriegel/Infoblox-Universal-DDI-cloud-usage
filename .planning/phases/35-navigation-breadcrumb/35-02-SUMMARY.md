---
phase: 35-navigation-breadcrumb
plan: "02"
subsystem: dashboard-ui
tags: [breadcrumb, navigation, jinja2, css, htmx]
dependency_graph:
  requires: [35-01]
  provides: [NAV-01, NAV-02]
  affects: [base.html, pages.py, app.css]
tech_stack:
  added: []
  patterns:
    - "Jinja2 conditional block ({% if calculator_name %}) for feature-gated nav injection"
    - "calculator_name context key injected post _get_tab_context() — no shared function modification"
key_files:
  created: []
  modified:
    - src/cloud_usage/dashboard/routes/pages.py
    - src/cloud_usage/dashboard/templates/base.html
    - src/cloud_usage/dashboard/static/app.css
    - tests/test_dashboard_navigation.py
decisions:
  - "Plain <a href='/'> on Home breadcrumb link — no hx-* attributes; full-page navigation back to home is correct behavior"
  - "calculator_name injected after _get_tab_context() call, not inside it — keeps the helper generic"
  - "Breadcrumb CSS uses only existing --ib-* design tokens (no new tokens introduced)"
  - "test_integration_aws.py and test_integration_azure.py have a pre-existing ImportError (fold_enis_into_parents missing) — out of scope, logged as deferred"
metrics:
  duration_seconds: 132
  completed_date: "2026-03-08"
  tasks_completed: 2
  files_modified: 4
---

# Phase 35 Plan 02: Breadcrumb Navigation Implementation Summary

Implemented conditional breadcrumb nav ("Home > [Calculator Name]") on all three calculator pages using Jinja2 conditional block in base.html, calculator_name context injection in three route handlers, and breadcrumb CSS rules appended to app.css. All 7 navigation tests pass.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Inject calculator_name into /cloud, /nios, /ad handlers | 81e4ad1 | pages.py |
| 2 | Add breadcrumb nav to base.html and CSS; remove xfail markers | ed94ebe | base.html, app.css, test_dashboard_navigation.py |

## Verification Results

1. `python -m pytest tests/test_dashboard_navigation.py -v` — 7 passed, 0 failed, 0 xfailed
2. Dashboard test suite (navigation, home routing, app, design) — 36 passed, 1 xfailed, 10 xpassed (no regressions from this plan)
3. Breadcrumb is outside `#tab-container` in base.html — placed between `</header>` and `<main>` (line 18-27)
4. `home.html` unchanged — no breadcrumb reference added
5. No `hx-*` attributes on the Home breadcrumb link — confirmed by grep

## Deviations from Plan

None — plan executed exactly as written.

Pre-existing issue noted (out of scope): `test_integration_aws.py` and `test_integration_azure.py` fail with `ImportError: cannot import name 'fold_enis_into_parents'` — this was failing before this plan and is unrelated to breadcrumb changes. Logged to deferred items.

## Self-Check: PASSED

- pages.py: FOUND
- base.html: FOUND
- app.css: FOUND
- commit 81e4ad1: FOUND
- commit ed94ebe: FOUND
