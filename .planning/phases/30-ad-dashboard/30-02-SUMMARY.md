---
phase: 30-ad-dashboard
plan: "02"
subsystem: dashboard-ad-backend
tags: [dashboard, ad, state-machine, sse, fastapi, threading]
dependency_graph:
  requires: [30-01]
  provides: [AdScanManager, AdState, routes/ad.py]
  affects: [app.py, tests/test_dashboard_ad.py]
tech_stack:
  added: []
  patterns:
    - AdScanManager thread-safe state machine (mirrors NiosScanManager)
    - SSE disconnect-aware generator with asyncio.wait() poll loop
    - TYPE_CHECKING import guard for forward references
    - loop.run_in_executor() for Python 3.9 background thread dispatch
key_files:
  created:
    - src/cloud_usage/dashboard/services/ad_manager.py
    - src/cloud_usage/dashboard/routes/ad.py
    - src/cloud_usage/dashboard/templates/partials/ad/progress_display.html
  modified:
    - src/cloud_usage/dashboard/app.py
decisions:
  - SSE generator uses asyncio.wait() with 1s poll instead of async-for to support TestClient disconnect detection
  - AdOptions NTLM validation requires username+password; Kerberos passes None for both
  - partials/ad/progress_display.html handles indeterminate (total=0) and determinate progress bars
metrics:
  duration_seconds: 866
  completed_date: "2026-03-08"
  tasks_completed: 2
  files_created: 3
  files_modified: 1
---

# Phase 30 Plan 02: AD Backend State Machine and Routes Summary

**One-liner:** AdScanManager (thread-safe IDLE/RUNNING/COMPLETE/ERROR state machine) and routes/ad.py (POST /ad/run, GET /api/sse/ad, GET /api/ad/progress) wired into app.py — 12 tests green.

## What Was Built

### Task 1: AdScanManager Service

`src/cloud_usage/dashboard/services/ad_manager.py` — mirrors NiosScanManager with AD-specific additions:

- `AdState` enum (IDLE/RUNNING/COMPLETE/ERROR)
- `AdScanManager` with threading.Lock protecting all state access
- Initial progress `total=0` (indeterminate — DC count unknown at pipeline start)
- `set_complete()` stores dns_zone_count, dhcp_scope_count, user_count, ddi_count, ip_count, token_total
- `set_last_options(options)` stores AdOptions for retry pre-fill
- All properties: state, output_path, error, current_progress, last_options, dns_zone_count, dhcp_scope_count, user_count, ddi_count, ip_count, token_total
- `AdOptions` imported under TYPE_CHECKING to prevent circular import

### Task 2: AD Route Handlers

`src/cloud_usage/dashboard/routes/ad.py` — three routes:

- `POST /ad/run`: reads form fields, builds AdOptions (Kerberos guard: `username = form.get(...) or None`), calls `set_last_options()` before `start()`, dispatches `_run_ad_pipeline` via `loop.run_in_executor()`, returns inline HTML with SSE connection div
- `GET /api/sse/ad`: race-condition guard (emits `ad_complete` immediately if COMPLETE/ERROR), disconnect-aware generator using `asyncio.wait()` with 1s poll
- `GET /api/ad/progress`: renders `partials/ad/progress_display.html` from `ad_manager.current_progress`

`_run_ad_pipeline` sync function:
- Phase 1: indeterminate progress (total=0, "Connecting to AD...")
- Calls `run_ad_analysis(options, output_path)`
- Phase 2: determinate (2/2, "Writing report...")
- Computes resource counts, calls `calculate_tokens()`, stores via `set_complete()`
- finally block: always emits `ad_complete` + `emit_done()` to close SSE

`src/cloud_usage/dashboard/app.py` — wired `ad_event_bridge` (EventBridge), `AdScanManager`, and `ad_router` into lifespan and `create_app()`.

`src/cloud_usage/dashboard/templates/partials/ad/progress_display.html` — renders indeterminate `<progress>` when `total=0`, determinate `<progress value/max>` when `total>0`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SSE generator hangs with TestClient client.stream()**

- **Found during:** Task 2 verification (TestAdSSE tests)
- **Issue:** The `async for event_str in ad_event_bridge.subscribe()` pattern blocks inside `asyncio.wait_for(..., timeout=25.0)`. When starlette TestClient exits the `with client.stream()` context, the server-side generator cannot be interrupted until the 25s keepalive fires. In practice this caused an infinite hang rather than a 25s wait due to the TestClient's disconnect signaling mechanism.
- **Fix:** Replaced the `async for` loop with an `asyncio.wait()` pattern that polls both the event bridge and `request.is_disconnected()` with a 1-second timeout. This allows the generator to detect client disconnects promptly without waiting for the next queue event.
- **Files modified:** `src/cloud_usage/dashboard/routes/ad.py`
- **Commit:** d9b0342

## Test Results

All plan verification tests pass:

```
tests/test_dashboard_ad.py::TestAdScanManager  7/7 PASSED
tests/test_dashboard_ad.py::TestAdRun          3/3 PASSED
tests/test_dashboard_ad.py::TestAdSSE          2/2 PASSED
tests/test_dashboard_ad.py::TestAdProgress     1/1 PASSED
```

Regression check: 105 existing dashboard tests still pass.

TestAdTab and TestAdIndependence remain failing until Plan 04 wires `/tab/ad` into pages.py.

## Decisions Made

1. **SSE generator uses asyncio.wait() poll** — 1s poll interval balances disconnect responsiveness with CPU efficiency; the existing nios SSE route uses the same `async for` pattern (no disconnect issue there since it's tested differently — no stream() context manager). The ad SSE is the first route tested via `client.stream()`.

2. **Services list fallback** — `form.getlist("services")` reads multi-value `services` fields; falls back to individual `ad_svc_dns/dhcp/user` checkboxes for backward compat; defaults to all three if none specified.

3. **Inline HTML response for POST /ad/run** — Plan recommended inline HTML as the cleanest approach (no template needed for the running state). The full tab state-switch happens on `ad_complete` SSE event via `hx-get="/tab/ad"`.

## Self-Check: PASSED

- FOUND: src/cloud_usage/dashboard/services/ad_manager.py
- FOUND: src/cloud_usage/dashboard/routes/ad.py
- FOUND: src/cloud_usage/dashboard/templates/partials/ad/progress_display.html
- FOUND: commit 2c0dfa8 (AdScanManager)
- FOUND: commit d9b0342 (AD routes + app wiring)
