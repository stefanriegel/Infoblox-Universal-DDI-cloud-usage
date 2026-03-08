---
phase: 36-calculator-visual-redesign
plan: 02
subsystem: dashboard/ui
tags: [css, jinja2, accent-system, wizard, design-tokens]
dependency_graph:
  requires:
    - 36-01 (xfail scaffold)
    - 35-02 (calculator_name pattern)
  provides:
    - calc_theme body class injection in route handlers
    - --calc-accent CSS custom property system
    - wizard step checkmark pseudo-element
  affects:
    - base.html body element rendering
    - app.css wizard active/completed selectors
tech_stack:
  added: []
  patterns:
    - CSS custom property cascade via body class (per-calculator accent theme)
    - Jinja2 | default filter for optional context variables
key_files:
  created: []
  modified:
    - src/cloud_usage/dashboard/routes/pages.py
    - src/cloud_usage/dashboard/templates/base.html
    - src/cloud_usage/dashboard/static/app.css
    - tests/test_dashboard_visual_redesign.py
decisions:
  - calc_theme injected after calculator_name in each handler — keeps _get_tab_context() generic (consistent with Phase 35 decision)
  - --calc-accent fallback in :root points to var(--ib-blue) so non-calc routes retain existing blue accent
  - wizard completed .step-number uses font-size:0/color:transparent to hide digit; ::after renders checkmark at 0.85rem
  - xfail markers removed from 8 tests upon implementation (strict=True means XPASS = pytest failure)
metrics:
  duration: 11 minutes
  completed: "2026-03-08"
  tasks: 2
  files_modified: 4
---

# Phase 36 Plan 02: Per-Calculator Accent System and Wizard Checkmark Summary

Per-calculator accent system using CSS custom properties cascaded from body class, with wizard completed steps replaced by Unicode checkmark pseudo-element.

## What Was Done

### Task 1: Inject calc_theme in Route Handlers and Body Class in base.html

Added `context["calc_theme"] = "calc-{calculator}"` to each of the three page-level route handlers (`/cloud`, `/nios`, `/ad`) immediately after the existing `context["calculator_name"]` line. Updated `base.html` body tag from `<body>` to `<body class="{{ calc_theme | default('') }}">`. Removed xfail markers from 3 body-class tests.

### Task 2: Add Accent CSS Rules and Update Wizard Selectors in app.css

Four changes to `app.css`:

1. Added `:root { --calc-accent: var(--ib-blue); }` as fallback at top of file
2. Added Per-Calculator Themes section: `.calc-cloud { --calc-accent: #0066CC; }`, `.calc-nios { --calc-accent: #00C389; }`, `.calc-ad { --calc-accent: #8B5CF6; }`
3. Replaced `var(--ib-blue)` with `var(--calc-accent)` in all four wizard active/completed selector blocks
4. Updated `.wizard-steps li.completed .step-number` to hide step number (`font-size: 0; color: transparent; position: relative`) and added `::after { content: '\2713'; ... }` pseudo-element

Removed xfail markers from 5 CSS tests.

## Verification Results

```
tests/test_dashboard_visual_redesign.py: 8 passed, 3 xfailed in 0.29s
```

- DESIGN-03: 6 tests pass (3 body class, 3 CSS accent rules)
- DESIGN-04: 2 tests pass (calc-accent usage, checkmark pseudo-element)
- DESIGN-05: 3 xfailed (Plan 03 scope)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] `src/cloud_usage/dashboard/routes/pages.py` — calc_theme injected in /cloud, /nios, /ad
- [x] `src/cloud_usage/dashboard/templates/base.html` — body class renders calc_theme
- [x] `src/cloud_usage/dashboard/static/app.css` — .calc-cloud/.calc-nios/.calc-ad, var(--calc-accent), \2713
- [x] Commit f012c22 — Task 1 (routes + base.html)
- [x] Commit ca9c8f2 — Task 2 (app.css + test markers)
