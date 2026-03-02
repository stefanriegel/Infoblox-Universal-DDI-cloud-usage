---
phase: quick-3
plan: "01"
subsystem: dashboard-frontend
tags: [htmx, bug-fix, ux, nios, upload]
key-files:
  modified:
    - src/cloud_usage/dashboard/templates/partials/nios/step1_upload.html
    - src/cloud_usage/dashboard/templates/base.html
decisions:
  - Use class="htmx-indicator" instead of inline style="display:none;" — HTMX v2 uses CSS opacity transitions, inline styles override them
  - Add element-level hx-on:htmx:responseError on the form for targeted UI error display (takes precedence over global handler)
  - Add global document.body htmx:responseError listener in base.html as safety net for all other HTMX requests
  - Move aria-busy from wrapper div to inner <p> element for semantic correctness
metrics:
  duration: ~5 min
  completed: "2026-03-02"
  tasks_completed: 2
  files_modified: 2
---

# Quick Task 3: Fix NIOS Dashboard Upload Button Summary

**One-liner:** Fixed HTMX v2 upload button silence by replacing inline `display:none` indicator with `class="htmx-indicator"` and adding `hx-on:htmx:responseError` error surfacing on the form.

## What Was Fixed

Two root causes made the "Upload & Read Members" button appear to do nothing:

1. **Indicator never showed:** The `#nios-upload-indicator` element had `style="display:none;"` — inline styles have higher CSS specificity than HTMX's `.htmx-indicator` class toggle (opacity 0 → 1), so the loading spinner was permanently hidden regardless of request state.

2. **Errors silently discarded:** HTMX v2's default `responseHandling` config is `{code:"[45]..",swap:false,error:true}` — 4xx/5xx responses are not swapped into the DOM and fire no visible feedback. Any server exception produced zero UI output.

## Changes Made

### Task 1 — `step1_upload.html` (commit `bafe2ce`)

**Fix 1:** Replace indicator element:
```html
<!-- Before (broken): inline style overrides HTMX CSS -->
<div id="nios-upload-indicator" aria-busy="true" style="display:none;">

<!-- After (fixed): HTMX manages visibility via .htmx-indicator class -->
<div id="nios-upload-indicator" class="htmx-indicator">
  <p aria-busy="true">Processing backup file and reading member list...</p>
</div>
```

**Fix 2:** Add error event handlers to the form element:
- `hx-on:htmx:beforeRequest` — clears any prior error message before each new attempt
- `hx-on:htmx:responseError` — populates and un-hides the error `<p>` with the HTTP status code on failure

**Fix 3:** Add error container paragraph (hidden by default):
```html
<p id="nios-upload-error" hidden style="color:var(--pico-color-red-500,#e74c3c);"></p>
```

### Task 2 — `base.html` (commit `285a6e2`)

Added global HTMX error listener before `</body>` as a safety net for any HTMX request across the whole dashboard:
```html
<script>
  document.body.addEventListener('htmx:responseError', function(evt) {
    console.error('[HTMX] Request failed:', evt.detail.requestConfig.path,
                  'Status:', evt.detail.xhr.status, evt.detail.xhr.statusText);
  });
</script>
```

Element-level handlers defined with `hx-on:` take precedence — this only catches unhandled failures.

## Verification

Automated checks both pass:
- `class="htmx-indicator"` present, no `style="display:none;"` remaining
- `hx-on:htmx:responseError`, `hx-on:htmx:beforeRequest`, `nios-upload-error` all present in upload form
- `htmx:responseError` and `console.error` present in base.html
- `create_app()` factory imports and instantiates without errors

## Expected Behavior After Fix

| Scenario | Before | After |
|----------|--------|-------|
| Request fires | No spinner, no feedback | Spinner shows (opacity transition) |
| Server 5xx error | Silent, nothing visible | Error message in UI + console |
| Valid .tar.gz | Member list may not appear if 500 | Member list renders |
| Invalid file (handled) | Error from template variable | Error from template variable (unchanged) |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `/Users/mustermann/Documents/coding/Infoblox-Universal-DDI-cloud-usage/src/cloud_usage/dashboard/templates/partials/nios/step1_upload.html` — FOUND
- `/Users/mustermann/Documents/coding/Infoblox-Universal-DDI-cloud-usage/src/cloud_usage/dashboard/templates/base.html` — FOUND
- Commit `bafe2ce` — FOUND
- Commit `285a6e2` — FOUND
