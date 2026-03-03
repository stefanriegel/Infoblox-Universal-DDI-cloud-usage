---
phase: 19-token-breakdown-webui
plan: "02"
status: complete
completed: 2026-03-03
---

# Plan 19-02 Summary: Member Attribution Table

## What Was Built

Added a Member Attribution section to `complete.html` below the Download CTA. The section contains:

- Section heading "Member Attribution" (uppercase, gray, matching existing style)
- Subtitle note explaining that per-member Active IP counts are lease-only and should not be summed for scenario totals (prevents customer confusion)
- Scrollable table container: `max-height: 400px; overflow-y: auto` so large grids don't overflow the page
- Table columns: Member, Group, DDI Objects, Active IPs, Token Contribution
- Member hostnames displayed in monospace font
- Group labels "NIOS"/"NIOSX" displayed as small color-coded badges (gray for NIOS, blue-light/blue for NIOSX)
- Numeric counts comma-formatted; token_contribution shown to 2 decimal places

The section is guarded by `{% if scenario_suite and scenario_suite.member_attribution %}` so it only renders in COMPLETE state with data.

The "Run Another Analysis" button remains at the bottom of the article, after the attribution section.

## Files Modified

- `src/cloud_usage/dashboard/templates/partials/nios/complete.html` — member attribution section added
- `tests/test_dashboard_nios.py` — added `TestMemberAttribution` class (10 tests)

## Test Results

```
TestMemberAttribution: 10/10 passed
Full test_dashboard_nios.py: 52/52 passed
```

## Requirements Satisfied

- BRKDN-03: Per-member breakdown table with DDI/IP/Asset counts and token contribution
- BRKDN-04: NIOS vs NIOSX group label on each row (color-coded badge)

## Key Decisions Made

- Used `{{ row.group | upper }}` Jinja2 filter to display "NIOS"/"NIOSX" from lowercase stored values
- NIOSX badge uses `var(--ib-blue-light)` background and `var(--ib-blue)` text to visually distinguish from NIOS
- Jinja2 inline Jinja conditional used for badge styling: `{% if row.group == 'niosx' %}...{% else %}...{% endif %}` inline in style attribute
- No JavaScript needed — static rendering from template context
