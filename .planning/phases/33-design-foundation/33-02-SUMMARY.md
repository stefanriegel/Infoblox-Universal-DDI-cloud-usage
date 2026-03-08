---
phase: 33-design-foundation
plan: "02"
subsystem: ui
tags: [css, design-system, inter-font, woff2, pico-css-replacement]

requires:
  - phase: 33-01
    provides: xfail test scaffold (test_dashboard_design.py) that defines acceptance criteria for design-system.css and inter font

provides:
  - "design-system.css: 12-section plain CSS file replacing PicoCSS for all current template patterns"
  - "inter-variable.woff2: self-hosted Inter v4.1 variable font (weights 100-900, 344KB)"
  - "CSS custom properties: all existing --ib-* tokens + --ib-navy, --ib-accent-green, --page-bg"

affects:
  - 33-03 (swaps pico.min.css link in base.html for design-system.css)
  - 33-04 (app.css cleanup — removes :root block now in design-system.css)
  - 34-37 (all future visual phases consume these CSS tokens)

tech-stack:
  added: ["Inter variable font v4.1 (self-hosted WOFF2)"]
  patterns:
    - "CSS design tokens in :root of design-system.css — single source of truth for all --ib-* variables"
    - "Flat plain CSS with numbered comment sections — no preprocessors, auditable"
    - "Self-hosted fonts in static/ — no CDN dependency, works offline on customer machines"
    - "PicoCSS pattern coverage via explicit selectors (table, figure, details/summary, progress, article, form controls)"

key-files:
  created:
    - src/cloud_usage/dashboard/static/design-system.css
    - src/cloud_usage/dashboard/static/inter-variable.woff2
  modified: []

key-decisions:
  - "Inter v4.1 InterVariable.woff2 used (roman/upright only — 344KB covers weights 100-900)"
  - "progress:not([value]) shimmer uses gradient animation, not pseudo-element spinner"
  - "a[role='button'] styled as primary button now; Plan 03 will convert to .btn class"
  - "aria-busy handled with opacity: 0.5 — acceptable since HTMX replaces element on completion"

patterns-established:
  - "design-system.css section pattern: numbered comment blocks (1-12) for easy auditing"
  - "Token migration: --ib-* variables live only in design-system.css :root, app.css references but does not define them (after Plan 04)"

requirements-completed:
  - DESIGN-01

duration: 2min
completed: 2026-03-08
---

# Phase 33 Plan 02: Design System Assets Summary

**Plain CSS design system (design-system.css, 12 sections) + self-hosted Inter v4.1 WOFF2 replacing PicoCSS's 83KB library for all patterns in current templates**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-08T14:15:29Z
- **Completed:** 2026-03-08T14:16:59Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments

- Downloaded Inter v4.1 `InterVariable.woff2` (344KB, weights 100-900, valid WOFF2 magic bytes confirmed) — served at /static/inter-variable.woff2
- Created `design-system.css` with all 12 sections: @font-face, design tokens, reset, typography, layout, tables, forms, buttons, details/summary, progress bar, article cards, aria-busy + header nav
- All three DESIGN-01 tokens verified (`--ib-navy`, `--ib-accent-green`, `--page-bg`) — 4 tests now XPASS (were xfail in Wave 0)
- Full test suite: 22 passed, 4 xfailed, 6 xpassed — HTML-related tests remain xfail (base.html not yet updated, expected)

## Task Commits

1. **Task 1: Download Inter variable font WOFF2** - `4eff442` (feat)
2. **Task 2: Write design-system.css** - `7a75e90` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/cloud_usage/dashboard/static/inter-variable.woff2` - Inter v4.1 variable font, 344KB WOFF2, weights 100-900, Latin+Latin-Ext unicode ranges
- `src/cloud_usage/dashboard/static/design-system.css` - 12-section plain CSS: font, tokens, reset, typography, layout, tables, forms, buttons, accordion, progress, articles, nav

## Decisions Made

- Downloaded from `web/InterVariable.woff2` in Inter-4.1.zip (zip structure differed from plan's documented path `extras/woff2/Inter.var.woff2` — found correct path by listing zip contents)
- `progress:not([value])` indeterminate state uses background gradient shimmer animation — matches RESEARCH.md specification
- `a[role="button"]` styled as primary button inline (Plan 03 will convert these to `.btn` class elements)
- `[aria-busy="true"]` uses `opacity: 0.5` + `pointer-events: none` — minimal and effective since HTMX replaces the element when the operation completes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Inter zip file path corrected**
- **Found during:** Task 1 (Download Inter variable font WOFF2)
- **Issue:** Plan specified `extras/woff2/Inter.var.woff2` but actual Inter-4.1.zip structure uses `web/InterVariable.woff2`
- **Fix:** Listed zip contents with `unzip -l` to find correct path, extracted from `web/InterVariable.woff2`
- **Files modified:** src/cloud_usage/dashboard/static/inter-variable.woff2 (correct file extracted)
- **Verification:** WOFF2 magic bytes confirmed (`wOF2`), size 344KB, test_inter_fonts_served XPASS
- **Committed in:** 4eff442 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — incorrect zip path in plan)
**Impact on plan:** Minor path correction only. Final artifact identical to plan specification.

## Issues Encountered

None beyond the zip path deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `design-system.css` and `inter-variable.woff2` ready for Plan 03 to reference
- Plan 03 will swap `pico.min.css` link for `design-system.css` in base.html and remove `data-theme="light"` attribute
- Plan 04 will remove the `:root` variable block from `app.css` (now defined only in design-system.css)

---

*Phase: 33-design-foundation*
*Completed: 2026-03-08*
