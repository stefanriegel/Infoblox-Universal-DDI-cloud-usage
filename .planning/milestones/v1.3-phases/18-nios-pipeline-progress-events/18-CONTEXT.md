# Phase 18: NIOS Pipeline Progress Events - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Emit step-level SSE progress events from the NIOS analysis pipeline (`_run_nios_pipeline`) and surface them in the dashboard: named step label, "Step N of M" counter, and elapsed time. No changes to pipeline logic, output, or results — purely observability on top of the existing 7-step pipeline.

</domain>

<decisions>
## Implementation Decisions

### Step granularity and naming
- Emit 6 named steps (the 7th "step" is completion, not a progress event):
  - Step 1: "Inspecting backup"
  - Step 2: "Reading members"
  - Step 3: "Counting objects"
  - Step 4: "Counting IP records"
  - Step 5: "Computing scenarios"
  - Step 6: "Writing report"
- Each step emits an SSE event at the START of that step (not after completion)
- Total step count (6) is included in every event payload so the frontend always knows M in "Step N of M"

### SSE event shape
- Single event type: `nios_progress`
- Payload: `{ "step": N, "total": 6, "label": "...", "elapsed_seconds": X.X }`
- `elapsed_seconds` is a float, calculated from pipeline start time in the background thread
- Existing `nios_complete` event at the end is unchanged — still triggers tab refresh

### Progress display style
- Determinate `<progress>` bar: `value=N max=6` — updates via `sse-swap` on `nios_progress` events
- Step label line below the bar: "Step N of 6: [label]"
- Elapsed time line: "Elapsed: Xs" — derived from SSE payload (no JS timer needed)
- All three elements update together on each `nios_progress` SSE swap

### Elapsed time source
- Backend-driven: pipeline records `start_time = time.monotonic()` before Step 1
- Each `emit()` call includes `elapsed_seconds = round(time.monotonic() - start_time, 1)`
- No JavaScript timer — frontend just renders the value from the SSE payload
- Simple, always in sync with actual pipeline progress

### Completion transition
- Keep existing behavior: `nios_complete` event triggers `hx-get="/tab/nios"` full tab refresh
- No additional "Done!" flash or manual dismiss step

### Claude's Discretion
- Exact HTML/CSS layout of the progress area (within PicoCSS conventions)
- Whether `elapsed_seconds` is shown as integer seconds or one decimal place
- Whether the progress bar uses PicoCSS `<progress>` element or a custom div
- Keepalive handling for SSE — already handled by EventBridge

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `EventBridge.emit(event_type, data)`: sync-callable from background thread — ready to use for `nios_progress` events. No changes needed to EventBridge.
- `nios_event_bridge` (app.state): dedicated EventBridge instance for NIOS SSE, already wired to `/api/sse/nios`
- `step2_run.html`: existing SSE-connected template with `hx-ext="sse"` and `sse-connect="/api/sse/nios"` — add `sse-swap="nios_progress"` to new progress elements

### Established Patterns
- HTMX `sse-swap` pattern: already used for `nios_complete` event in `step2_run.html` — same pattern applies for `nios_progress` swaps
- `_run_nios_pipeline` runs in `loop.run_in_executor(None, ...)` — sync thread, `nios_event_bridge` is available as a parameter, `emit()` is sync-safe
- PicoCSS `<progress>` element: already used (`<progress></progress>` — indeterminate). Switch to `<progress value="N" max="6">` for determinate display.

### Integration Points
- `_run_nios_pipeline` function in `src/cloud_usage/dashboard/routes/nios.py` — add `emit()` calls at each step start
- `step2_run.html` in `src/cloud_usage/dashboard/templates/partials/nios/` — add `sse-swap` targets for progress elements
- No changes needed to `EventBridge`, `NiosScanManager`, or the SSE route handler

</code_context>

<specifics>
## Specific Ideas

- "Step N of M" counter uses total=6 (hardcoded in both backend and template) — simple and accurate
- Progress bar starts at step=1 on first emit (not at 0) — user sees immediate movement when pipeline starts
- The `nios_complete` event already triggers full tab refresh; no duplicate "done" signal needed

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 18-nios-pipeline-progress-events*
*Context gathered: 2026-03-03*
