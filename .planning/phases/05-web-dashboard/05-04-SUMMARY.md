---
phase: 05-web-dashboard
plan: 04
subsystem: ui
tags: [htmx, fastapi, wizard, scan-lifecycle, download, cli-web, uvicorn, jinja2]

# Dependency graph
requires:
  - phase: 05-web-dashboard
    provides: FastAPI app factory, EventBridge, ScanManager, DashboardProgressTracker, tab bar, SSE streaming, results/summary tabs
  - phase: 01-core-infrastructure
    provides: ProgressTracker, AuthDoctor, AuthValidator, GracefulShutdown
  - phase: 02-aws-provider-and-end-to-end-pipeline
    provides: Discovery orchestrator, counting pipeline, output generation (XLS, CSV, manifest)
provides:
  - 4-step scan wizard (auth check, provider select, account select, review & start)
  - Scan lifecycle management (start in background thread, cancel with graceful shutdown)
  - File download endpoints with path traversal prevention
  - CLI --web flag launching uvicorn dashboard on configurable port
  - Saved scan config persistence and restoration
  - Download buttons on Summary tab wired to output files
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [wizard-step-htmx-swap, background-scan-pipeline, download-path-validation, cli-web-mode]

key-files:
  created:
    - src/cloud_usage/dashboard/routes/scan.py
    - src/cloud_usage/dashboard/routes/download.py
    - src/cloud_usage/dashboard/templates/partials/wizard/step1_auth.html
    - src/cloud_usage/dashboard/templates/partials/wizard/step2_providers.html
    - src/cloud_usage/dashboard/templates/partials/wizard/step3_accounts.html
    - src/cloud_usage/dashboard/templates/partials/wizard/step4_review.html
    - tests/test_dashboard_wizard.py
  modified:
    - src/cloud_usage/dashboard/app.py
    - src/cloud_usage/dashboard/routes/pages.py
    - src/cloud_usage/dashboard/templates/pages/progress.html
    - src/cloud_usage/dashboard/templates/pages/summary.html
    - src/cloud_usage/cli.py

key-decisions:
  - "Auth check runs all 3 providers via asyncio.to_thread to avoid blocking async loop"
  - "Scan pipeline runs in executor thread, reuses full CLI counting pipeline for consistency"
  - "Download endpoint validates basename==filename and extension whitelist for path traversal prevention"
  - "CLI --web flag early-exits before provider selection, handles ImportError gracefully"
  - "Wizard steps use HTMX hx-post/hx-target for server-controlled step progression"
  - "New Scan button shown in idle/complete/cancelled/error states, hidden during running"

patterns-established:
  - "Wizard step pattern: HTMX hx-post swaps #wizard-content div with next step template"
  - "Background scan: asyncio.get_running_loop().run_in_executor for blocking pipeline"
  - "Download security: os.path.basename check + extension whitelist + resolved path containment"
  - "CLI --web mode: early return after uvicorn.run, before interactive prompts"

requirements-completed: [PLAT-02, PLAT-03]

# Metrics
duration: 8min
completed: 2026-02-24
---

# Phase 5 Plan 04: Scan Wizard, Downloads, and CLI --web Summary

**4-step scan wizard with auth check, account selection, background scan pipeline, download endpoints with path traversal prevention, and CLI --web flag for one-command dashboard launch**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-24T22:27:19Z
- **Completed:** 2026-02-24T22:35:45Z
- **Tasks:** 2
- **Files modified:** 12 (7 created, 5 modified)

## Accomplishments
- 4-step scan wizard: auth check (green/red per provider with CLI instructions), provider select (only authenticated), account select (searchable checkbox list with Select All/Deselect All), review & start
- Scan lifecycle: start (background thread via run_in_executor), cancel (sets CANCELLED state), 409 guard when already running
- Download endpoint serving XLS/CSV/JSON with path traversal prevention and extension whitelist
- CLI --web flag launching uvicorn dashboard with configurable --port (default 8080)
- 25 new tests covering wizard flow, scan lifecycle, download security, CLI args, saved config
- All 951 tests pass (zero regressions from existing 926 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Scan wizard routes and templates** - `96eba9a` (feat)
2. **Task 2: Download endpoints, CLI --web flag, and wizard tests** - `5ddad31` (feat)

## Files Created/Modified
- `src/cloud_usage/dashboard/routes/scan.py` - Wizard steps, scan start/cancel, background pipeline
- `src/cloud_usage/dashboard/routes/download.py` - File download with path traversal prevention
- `src/cloud_usage/dashboard/templates/partials/wizard/step1_auth.html` - Auth check with green/red indicators
- `src/cloud_usage/dashboard/templates/partials/wizard/step2_providers.html` - Provider selection checkboxes
- `src/cloud_usage/dashboard/templates/partials/wizard/step3_accounts.html` - Searchable account selection
- `src/cloud_usage/dashboard/templates/partials/wizard/step4_review.html` - Review & start configuration
- `src/cloud_usage/dashboard/templates/pages/progress.html` - Added New Scan button for non-running states
- `src/cloud_usage/dashboard/templates/pages/summary.html` - Functional download buttons from output paths
- `src/cloud_usage/dashboard/routes/pages.py` - Summary tab passes download links to template
- `src/cloud_usage/dashboard/app.py` - Registered scan and download routers
- `src/cloud_usage/cli.py` - Added --web and --port flags with uvicorn launch
- `tests/test_dashboard_wizard.py` - 25 tests for wizard, lifecycle, download, CLI

## Decisions Made
- Auth check runs all 3 providers via asyncio.to_thread() to avoid blocking the async event loop (Pitfall 2)
- Scan pipeline runs in background thread via run_in_executor, reusing the full CLI counting pipeline (fold ENIs, dedup, categorize, IP count, tokens) for CLI-dashboard output consistency
- Download endpoint uses three-layer security: basename equality check, extension whitelist (.xlsx/.csv/.json), and resolved path containment within output directory
- CLI --web flag is checked early in main() before provider selection/auth checks, with graceful ImportError handling for missing dashboard dependencies
- Wizard uses HTMX hx-post to swap #wizard-content div, keeping all step state server-side (no client-side JS state)
- New Scan button appears in idle, complete, cancelled, and error states; hidden during running (scan in progress shows Cancel instead)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 5 (Web Dashboard) is now complete: all 4 plans delivered
- Dashboard provides full scan lifecycle: wizard setup, real-time progress via SSE, filterable results, token summary, file downloads
- CLI --web flag provides single-command launch: `python -m cloud_usage.cli --web`
- Ready for Phase 7 (Integration Hardening) gap closure per roadmap

## Self-Check: PASSED

All 7 created files and 5 modified files verified present. Both task commits (96eba9a, 5ddad31) verified in git log.

---
*Phase: 05-web-dashboard*
*Completed: 2026-02-24*
