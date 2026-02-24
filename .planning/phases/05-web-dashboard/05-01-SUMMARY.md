---
phase: 05-web-dashboard
plan: 01
subsystem: ui
tags: [fastapi, htmx, pico-css, sse, janus, uvicorn, jinja2, dashboard]

# Dependency graph
requires:
  - phase: 01-core-infrastructure
    provides: ProgressTracker, GracefulShutdown, DiscoveryOrchestrator interfaces
provides:
  - FastAPI app factory with lifespan-managed services
  - EventBridge sync-to-async SSE bridge with janus Queue fan-out
  - ScanManager thread-safe state machine with config persistence
  - Vendored HTMX 2.0.8, htmx-ext-sse 2.2.4, Pico CSS 2.1.1
  - Base HTML template with Pico CSS styling and HTMX loaded
affects: [05-02-PLAN, 05-03-PLAN, 05-04-PLAN]

# Tech tracking
tech-stack:
  added: [fastapi, uvicorn, jinja2, python-multipart, janus, httpx, htmx, htmx-ext-sse, pico-css]
  patterns: [app-factory-with-lifespan, sync-to-async-event-bridge, thread-safe-state-machine, vendored-frontend-assets]

key-files:
  created:
    - src/cloud_usage/dashboard/app.py
    - src/cloud_usage/dashboard/services/event_bridge.py
    - src/cloud_usage/dashboard/services/scan_manager.py
    - src/cloud_usage/dashboard/routes/pages.py
    - src/cloud_usage/dashboard/templates/base.html
    - src/cloud_usage/dashboard/static/htmx.min.js
    - src/cloud_usage/dashboard/static/sse.js
    - src/cloud_usage/dashboard/static/pico.min.css
    - src/cloud_usage/dashboard/static/app.css
    - tests/test_dashboard_app.py
  modified:
    - requirements.txt

key-decisions:
  - "EventBridge uses per-subscriber fan-out queues (not single shared queue) for multi-client SSE support"
  - "TemplateResponse uses new API with request as first parameter (avoids deprecation warning)"
  - "ScanManager accepts config_path parameter for testable config persistence via tmp_path"

patterns-established:
  - "App factory pattern: create_app() with asynccontextmanager lifespan for service lifecycle"
  - "Sync-to-async bridge: janus.Queue fan-out for thread-safe SSE event delivery"
  - "State machine pattern: enum-based states with threading.Lock for concurrent access"

requirements-completed: [PLAT-02, PLAT-03]

# Metrics
duration: 8min
completed: 2026-02-24
---

# Phase 5 Plan 01: Dashboard Foundation Summary

**FastAPI app factory with janus-bridged EventBridge, thread-safe ScanManager, and vendored HTMX 2.0.8 + Pico CSS 2.1.1 serving base template**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-24T21:55:39Z
- **Completed:** 2026-02-24T22:04:19Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- FastAPI app factory with lifespan managing EventBridge and ScanManager on app.state
- EventBridge sync-to-async bridge using janus Queue with per-subscriber fan-out for multi-client SSE
- ScanManager thread-safe state machine (IDLE/RUNNING/COMPLETE/CANCELLED/ERROR) with config persistence
- Vendored HTMX 2.0.8 (51KB), htmx-ext-sse 2.2.4 (9KB), Pico CSS 2.1.1 (83KB) committed to repo
- 23 tests covering app creation, page/static serving, EventBridge round-trip, ScanManager state machine

## Task Commits

Each task was committed atomically:

1. **Task 1: Create dashboard package, services, and app factory** - `c0a8992` (feat)
2. **Task 2: Vendor static assets, create base template, and write tests** - `fbeec45` (feat)

## Files Created/Modified
- `src/cloud_usage/dashboard/__init__.py` - Dashboard package init
- `src/cloud_usage/dashboard/app.py` - FastAPI app factory with lifespan, static mount, route registration
- `src/cloud_usage/dashboard/services/__init__.py` - Services package init
- `src/cloud_usage/dashboard/services/event_bridge.py` - Sync-to-async janus Queue bridge for SSE events
- `src/cloud_usage/dashboard/services/scan_manager.py` - Singleton scan state manager with thread-safe transitions
- `src/cloud_usage/dashboard/routes/__init__.py` - Routes package init
- `src/cloud_usage/dashboard/routes/pages.py` - GET / page route serving base.html
- `src/cloud_usage/dashboard/templates/base.html` - Base Jinja2 template with Pico CSS, HTMX, header, content block
- `src/cloud_usage/dashboard/static/htmx.min.js` - Vendored HTMX 2.0.8
- `src/cloud_usage/dashboard/static/sse.js` - Vendored htmx-ext-sse 2.2.4
- `src/cloud_usage/dashboard/static/pico.min.css` - Vendored Pico CSS 2.1.1
- `src/cloud_usage/dashboard/static/app.css` - Custom CSS for tabs, badges, cards, chips, wizard steps
- `tests/test_dashboard_app.py` - 23 tests for app, EventBridge, ScanManager
- `requirements.txt` - Added dashboard dependencies (fastapi, uvicorn, jinja2, python-multipart, janus, httpx)

## Decisions Made
- EventBridge uses per-subscriber fan-out queues (not single shared queue) for multi-client SSE support
- TemplateResponse uses new Starlette API with request as first parameter (avoids deprecation warning in Starlette 0.49+)
- ScanManager accepts config_path parameter for testable config persistence via tmp_path fixture
- EventBridge test uses subscriber-ready polling loop to avoid race condition between task scheduling and queue registration

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TemplateResponse deprecation warning**
- **Found during:** Task 2 (test writing)
- **Issue:** Starlette 0.49+ deprecates `TemplateResponse(name, {"request": request})` in favor of `TemplateResponse(request, name)`
- **Fix:** Updated pages.py to use new API: `templates.TemplateResponse(request, "base.html")`
- **Files modified:** src/cloud_usage/dashboard/routes/pages.py
- **Verification:** Tests pass without deprecation warnings
- **Committed in:** fbeec45 (Task 2 commit)

**2. [Rule 1 - Bug] Fixed EventBridge test race condition**
- **Found during:** Task 2 (test writing)
- **Issue:** Thread emitted events before async subscriber task registered its fan-out queue, causing events to be lost and test timeout
- **Fix:** Added polling loop waiting for `bridge._subscribers` to be non-empty before starting emitter thread
- **Files modified:** tests/test_dashboard_app.py
- **Verification:** EventBridge tests pass reliably without timeouts
- **Committed in:** fbeec45 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed items above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- App factory and services ready for Plan 02 (tab bar, progress view, SSE endpoint)
- EventBridge ready to receive events from orchestrator via DashboardProgressTracker subclass
- ScanManager ready for scan lifecycle routes (wizard, start, cancel)
- Base template ready for content block extension via Jinja2 inheritance
- 876 tests pass (853 existing + 23 new) confirming zero regressions

## Self-Check: PASSED

All 13 created files verified present. Both task commits (c0a8992, fbeec45) verified in git log.

---
*Phase: 05-web-dashboard*
*Completed: 2026-02-24*
