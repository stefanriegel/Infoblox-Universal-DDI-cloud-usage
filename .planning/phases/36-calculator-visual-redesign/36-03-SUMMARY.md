---
phase: 36-calculator-visual-redesign
plan: "03"
subsystem: ui
tags: [jinja2, css, htmx, templates, card-layout, visual-design]

requires:
  - phase: 36-02
    provides: calc-accent CSS variables and wizard step checkmark styles

provides:
  - ".completion-card CSS class: neutral card wrapper for NIOS and AD complete screens"
  - ".section-header CSS class: small uppercase label for Cloud Summary sections"
  - ".section-divider CSS class: horizontal rule separator between sections"
  - "partials/nios/complete.html: completion-card wrapper with hr dividers between header/body/download"
  - "partials/ad/complete.html: completion-card wrapper with hr dividers between header/body/download"
  - "pages/summary.html: Token Summary, Per-Provider Breakdown, Account Attribution, Download Reports section headers with hr.section-divider between each"

affects:
  - cloud-summary-tab
  - nios-complete-partial
  - ad-complete-partial

tech-stack:
  added: []
  patterns:
    - "completion-card replaces completion-banner on results screens — neutral gray border, no colored left accent"
    - "section-header + section-divider pattern for visual hierarchy in data-dense Cloud Summary tab"
    - "xfail strict=True markers removed on implementation (identical precedent to phases 34 and 35)"

key-files:
  created: []
  modified:
    - src/cloud_usage/dashboard/static/app.css
    - src/cloud_usage/dashboard/templates/partials/nios/complete.html
    - src/cloud_usage/dashboard/templates/partials/ad/complete.html
    - src/cloud_usage/dashboard/templates/pages/summary.html
    - tests/test_dashboard_visual_redesign.py

key-decisions:
  - "completion-card intentionally has no colored left border — results screens are accent-neutral per locked Phase 36 decision"
  - "xfail markers removed from three DESIGN-05 tests after implementation satisfies assertions (strict=True XPASS = pytest failure)"
  - "summary.html Per-Account Breakdown renamed to Account Attribution per CONTEXT.md spec"

patterns-established:
  - "Card-based results screens: outer article.completion-card with hr elements between header, body, and download CTA sections"
  - "Cloud Summary section hierarchy: h3.section-header + hr.section-divider before each data section"

requirements-completed:
  - DESIGN-05

duration: 7min
completed: 2026-03-08
---

# Phase 36 Plan 03: Calculator Visual Redesign — Card Layouts Summary

**Neutral .completion-card wrapper with hr section dividers on NIOS/AD complete screens, plus Token Summary/Account Attribution section headers on Cloud Summary tab — all 11 DESIGN-05 tests green**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-03-08T17:14:39Z
- **Completed:** 2026-03-08T17:21:00Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- Added `.completion-card`, `.section-header`, and `.section-divider` CSS classes to `app.css` (neutral styling — no accent colors on results screens)
- Restructured `partials/nios/complete.html` and `partials/ad/complete.html` outer `article` from `completion-banner` to `completion-card` with `<hr>` dividers between header, body content, and download CTA sections
- Added `Token Summary`, `Per-Provider Breakdown`, `Account Attribution`, and `Download Reports` section headers with `hr.section-divider` separators to `pages/summary.html`
- All 11 `test_dashboard_visual_redesign.py` tests pass (0 xfailed, 0 errors); full targeted suite (96 tests) green with no regressions

## Task Commits

1. **Task 1: Add CSS classes to app.css** - `ebd5b51` (feat)
2. **Task 2: Restructure NIOS and AD complete partials** - `6e765cf` (feat)
3. **Task 3: Add section headers to Cloud Summary template** - `8a777f8` (feat)

## Files Created/Modified

- `src/cloud_usage/dashboard/static/app.css` - Added `.completion-card`, `.completion-card hr`, `.section-header`, `.section-divider` rule blocks
- `src/cloud_usage/dashboard/templates/partials/nios/complete.html` - `completion-banner` → `completion-card`; `<hr>` dividers between three sections
- `src/cloud_usage/dashboard/templates/partials/ad/complete.html` - `completion-banner` → `completion-card`; `<hr>` dividers between three sections
- `src/cloud_usage/dashboard/templates/pages/summary.html` - `h3.section-header` + `hr.section-divider` added for all four sections; "Per-Account Breakdown" renamed to "Account Attribution"
- `tests/test_dashboard_visual_redesign.py` - Removed three `xfail(strict=True)` markers from DESIGN-05 tests

## Decisions Made

- `completion-card` has no colored left border — results/complete screens are intentionally accent-neutral per the locked Phase 36 decision (only wizard steps and primary UI elements use `calc-accent`)
- `xfail(strict=True)` markers removed on implementation — identical precedent to phases 34 and 35 (strict=True with XPASS causes pytest failure)
- "Per-Account Breakdown" renamed to "Account Attribution" as specified in CONTEXT.md

## Deviations from Plan

**1. [Rule 1 - Bug] Removed xfail markers from three DESIGN-05 tests**
- **Found during:** Task 2 verification
- **Issue:** Tests marked `xfail(strict=True, reason="Phase 36 Plan 03 not yet implemented")` — now that Plan 03 is implemented, tests XPASS which causes pytest failure with strict=True
- **Fix:** Removed the three `@pytest.mark.xfail(...)` decorators from `test_nios_complete_has_completion_card`, `test_ad_complete_has_completion_card`, and `test_summary_has_token_summary_header`
- **Files modified:** `tests/test_dashboard_visual_redesign.py`
- **Verification:** `pytest tests/test_dashboard_visual_redesign.py -q` → 11 passed
- **Committed in:** `6e765cf` (Task 2 commit, since that's when the first two XPASS issues were discovered; the third was part of Task 3 but committed in same file)

---

**Total deviations:** 1 auto-fixed (Rule 1 — inevitable xfail lifecycle, identical to phases 34/35 precedent)
**Impact on plan:** Required correction — not scope creep.

## Issues Encountered

- `test_integration_aws.py`, `test_integration_azure.py`, and `test_integration_gcp.py` have pre-existing import errors (`fold_enis_into_parents` missing from `asset_dedup`) — confirmed pre-existing, unrelated to Phase 36. Targeted suite (`test_dashboard_visual_redesign.py`, `test_dashboard_summary.py`, `test_dashboard_nios.py`) passes cleanly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DESIGN-05 complete — card-based layouts on all results/complete screens
- Phase 36 (all 3 plans: 36-01, 36-02, 36-03) fully executed
- v1.9 milestone visual redesign work complete; ready for next milestone phase

---
*Phase: 36-calculator-visual-redesign*
*Completed: 2026-03-08*
