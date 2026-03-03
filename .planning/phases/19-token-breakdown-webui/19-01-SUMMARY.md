---
phase: 19-token-breakdown-webui
plan: "01"
status: complete
completed: 2026-03-03
---

# Plan 19-01 Summary: Scenario Formula Breakdown

## What Was Built

Added inline formula derivation rows to the three NIOS scenario cards in `complete.html`.

Each scenario card now shows:
- Raw DDI object count with formula: e.g., "1,234 DDI ÷ 50 = 24.7"
- Raw Active IP count with formula: e.g., "500 IPs ÷ 25 = 20.0"
- Asset count row (conditional — only when asset_count > 0)
- Divider line followed by "Total: X.X tokens"

The Hybrid UDDI card renders two labeled sub-blocks (NIOS-remaining with DDI÷50/IPs÷25 formula, NIOSX-migrated with DDI÷25/IPs÷13 formula) before the combined total.

Numbers use comma thousands separators via Jinja2 `"{:,}".format()` filter.

## Files Modified

- `src/cloud_usage/dashboard/templates/partials/nios/complete.html` — scenario card expansion
- `tests/test_dashboard_nios.py` — added `TestScenarioBreakdown` class (10 tests)

## Test Results

```
TestScenarioBreakdown: 10/10 passed
Full test_dashboard_nios.py: 52/52 passed
```

## Requirements Satisfied

- BRKDN-01: DDI, Active IP, Asset counts visible per scenario card
- BRKDN-02: Formula derivation format "N,NNN DDI ÷ 50 = X.X" rendered inline

## Key Decisions Made

- Divisor values hardcoded in template (50/25/13 for NIOS, 25/13/3 for UDDI native) rather than passed from backend — values come from immutable constants in counter.py
- Jinja2 `"%.1f"|format(value)` used for one-decimal rendering
- `.primary` card (full_migration) uses `color:rgba(255,255,255,0.9)` for formula text on blue background
