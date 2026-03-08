---
quick_task: 7
type: bug-fix
tags: [tests, gcp, xlsx-output, test-isolation]
key_files:
  modified:
    - tests/test_output.py
    - tests/test_gcp_auth.py
decisions:
  - "Used patch.dict(sys.modules) with broken stubs instead of pop-and-reload for GCP missing-packages test — environment-independent and immune to real SDK presence"
metrics:
  duration: "~5 min"
  completed: "2026-03-08T16:24:45Z"
  tasks_completed: 3
  files_modified: 2
---

# Quick Task 7: Fix 3 Pre-existing Test Failures (GCP SDK) Summary

**One-liner:** Updated two stale xlsx column header assertions ("IP Count"/"Active IPs" → "Address Records") and replaced fragile sys.modules pop-and-reload GCP SDK test with environment-independent patch.dict stub injection.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Fix stale column header assertions in test_output.py | bbf30a2 | tests/test_output.py |
| 2 | Fix GCP missing-packages test to use patch.dict injection | 505c361 | tests/test_gcp_auth.py |
| 3 | Final regression run (verification only) | — | — |

## Changes Made

### Task 1 — test_output.py column header assertions

Two assertions updated to match production column names in `xlsx_report.py`:

- `test_detail_header_columns` (line ~203): index 6 changed from `"IP Count"` to `"Address Records"`
- `test_summary_headers` (line ~342): index 3 changed from `"Active IPs"` to `"Address Records"`

No production code touched. All other column-positional tests (which reference columns by number) left untouched.

### Task 2 — test_gcp_auth.py missing-packages test

Replaced the pop-and-reload approach in `test_create_shared_clients_handles_missing_packages` with `patch.dict("sys.modules", ...)` injecting broken MagicMock stubs. Each stub's client constructor attribute has `side_effect = ImportError(...)`, which causes `_try_create` (which catches `ImportError`) to return `None`. The `finally` block reloads `cf_mod` to restore real module state.

Key additions vs the original plan: also added `RoutersClient` and `TargetVpnGatewaysClient` stubs to match the two additional clients (`routers`, `target_vpn_gateways`) present in the current `client_factory.py` that were added in a later phase.

## Verification Results

```
77 passed in 0.38s
```

All three previously failing tests now PASSED:
- `tests/test_output.py::TestXlsxDetailSheet::test_detail_header_columns`
- `tests/test_output.py::TestXlsxSummarySheet::test_summary_headers`
- `tests/test_gcp_auth.py::TestGCPClientsFactory::test_create_shared_clients_handles_missing_packages`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] Added RoutersClient and TargetVpnGatewaysClient broken stubs**
- **Found during:** Task 2
- **Issue:** The plan's stub list did not include `RoutersClient` / `TargetVpnGatewaysClient` — two clients added to `client_factory.py` in a later phase. Without these stubs, the real SDK would be called and those fields would not be `None`, but the assertions only check `instances` and `sqladmin` so no assertion would fail. However the stubs were added for completeness and correctness of the test's stated intent (all fields None).
- **Fix:** Added both stubs to the broken MagicMock with appropriate `side_effect = ImportError(...)`.
- **Files modified:** tests/test_gcp_auth.py
- **Commit:** 505c361

## Self-Check: PASSED

- tests/test_output.py: modified, exists
- tests/test_gcp_auth.py: modified, exists
- Commit bbf30a2: exists (fix(quick-7): update stale column header expectations)
- Commit 505c361: exists (fix(quick-7): rewrite GCP missing-packages test)
- All 77 tests pass: confirmed
