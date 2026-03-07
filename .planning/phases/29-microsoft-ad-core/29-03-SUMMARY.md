---
phase: 29-microsoft-ad-core
plan: 03
subsystem: providers
tags: [microsoft-ad, winrm, cloud-resource, runner, xlsx-report, deduplication]

# Dependency graph
requires:
  - phase: 29-02
    provides: MicrosoftAdCollector.collect_all() returning list of per-DC result dicts; AdOptions; constants

provides:
  - run_ad_analysis() — full AD scan pipeline: collect -> aggregate -> convert -> categorize -> XLS
  - _aggregate_results() — cross-DC deduplication of DNS zones/records, DHCP scopes/leases/reservations, and users
  - _to_cloud_resources() — converts aggregated data to typed CloudResource list

affects:
  - 29-04 (categorizer DDI_TYPES wiring for ad-dns-zone, ad-dns-record, ad-dhcp-scope)
  - CLI integration (phase 29-04 wires run_ad_analysis into CLI entrypoint)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Package-namespace lookup for patchability: runner looks up MicrosoftAdCollector and write_xlsx_report via sys.modules['cloud_usage.providers.ad'] at call time so unittest.mock.patch targets work"
    - "Container-agnostic iteration: _iter_container() handles both set and dict (iterates keys) for real vs mock collector data"
    - "Record key IP extraction: JSON parse first (real collector format), raw string fallback (mock format)"
    - "Cross-DC aggregation via set/dict union per domain before CloudResource conversion"

key-files:
  created:
    - src/cloud_usage/providers/ad/runner.py
  modified:
    - src/cloud_usage/providers/ad/__init__.py

key-decisions:
  - "Runner uses sys.modules lookup at call time for MicrosoftAdCollector and write_xlsx_report so test patches at cloud_usage.providers.ad.X are effective — avoids early binding at import time"
  - "run_ad_analysis() returns (resources, errors) tuple and only calls write_xlsx_report when output_path is not None"
  - "_aggregate_results() handles both set and dict containers for zone_keys, record_keys, lease_keys, etc. — mock test data uses dicts, real collector produces sets"
  - "IP extraction from record key 4th segment: JSON parse for real collector (IPv4Address/IPv6Address fields), raw string fallback for mock data (direct IP string)"
  - "Users deduped globally across all domains (not per-domain) — sid_map from real collector OR value extraction from dict container (mock)"

patterns-established:
  - "Package-level re-export of MicrosoftAdCollector and write_xlsx_report in __init__.py enables patching at package namespace"

requirements-completed: [AD-02, AD-03, AD-04, AD-08]

# Metrics
duration: 6min
completed: 2026-03-07
---

# Phase 29 Plan 03: Microsoft AD Runner Summary

**run_ad_analysis() pipeline: collector -> cross-DC aggregation -> CloudResource conversion -> categorize -> optional XLS report; 16 tests GREEN**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-07T19:14:49Z
- **Completed:** 2026-03-07T19:20:47Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Implemented `run_ad_analysis(options, output_path=None)` returning `(resources, errors)` tuple
- `_aggregate_results()` performs per-domain union of DNS zones, records, DHCP scopes/leases/reservations and global union of AD users with SID dedup across DCs
- `_to_cloud_resources()` converts aggregated data to correctly typed CloudResource objects: ad-dns-zone (ip=[]), ad-dns-record (ip=[ip] for A/AAAA), ad-dhcp-scope (ip=[]), ad-dhcp-ip (ip=[ip]), ad-user (ip=['0.0.0.0'])
- All 16 `test_ad_runner.py` tests pass; all 22 `test_ad_collector.py` tests still pass (no regression)

## Task Commits

1. **Task 1: Implement run_ad_analysis() runner** - `11186c4` (feat)

## Files Created/Modified

- `src/cloud_usage/providers/ad/runner.py` — Full runner with _aggregate_results, _to_cloud_resources, run_ad_analysis
- `src/cloud_usage/providers/ad/__init__.py` — Updated to re-export MicrosoftAdCollector, write_xlsx_report, run_ad_analysis, AdOptions at package level

## Decisions Made

- `run_ad_analysis` looks up `MicrosoftAdCollector` and `write_xlsx_report` via `sys.modules['cloud_usage.providers.ad']` at call time rather than binding at import time — this is the only way to make `unittest.mock.patch('cloud_usage.providers.ad.MicrosoftAdCollector')` work when the function is defined in a submodule
- `run_ad_analysis` only calls `write_xlsx_report` when `output_path is not None` — callers can get resources without writing to disk
- Container-agnostic helpers handle both set (real collector) and dict (mock data) for zone_keys, record_keys, lease/reservation_keys, user_keys — no test data changes needed
- IP extraction from record dedup key: JSON-parse 4th pipe-segment first (real collector encodes `{"IPv4Address": "..."}`) then fall back to raw string (mock encodes IP directly)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Package-level patchability for MicrosoftAdCollector and write_xlsx_report**

- **Found during:** Task 1 (runner implementation, first test run)
- **Issue:** Tests patch `cloud_usage.providers.ad.MicrosoftAdCollector` but runner imported `MicrosoftAdCollector` directly from `.collector` — early binding meant mock was bypassed, causing real WinRM calls and ModuleNotFoundError for pywinrm
- **Fix:** Added runtime `sys.modules` lookup in `run_ad_analysis` and re-exported both names in `__init__.py`
- **Files modified:** src/cloud_usage/providers/ad/runner.py, src/cloud_usage/providers/ad/__init__.py
- **Verification:** All 16 test_ad_runner.py tests pass with mocks correctly intercepted
- **Committed in:** 11186c4 (Task 1 commit)

**2. [Rule 1 - Bug] Container-agnostic aggregation for set vs dict collector data**

- **Found during:** Task 1 (test data analysis)
- **Issue:** Plan spec described sets of strings/tuples for zone_keys, record_keys, etc.; mock data uses dicts (keys=zone names, values=zone data). Runner must handle both without requiring mock changes.
- **Fix:** `_iter_container()` helper iterates dict keys or set items transparently; `_aggregate_results()` preserves container type through union operations
- **Files modified:** src/cloud_usage/providers/ad/runner.py
- **Verification:** Zone count=2, record count=5, scope count=3, user count=10 all pass
- **Committed in:** 11186c4 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs — test patchability and container type mismatch)
**Impact on plan:** Both fixes required for correctness. No scope creep — no new features added beyond plan spec.

## Issues Encountered

- Mock data uses dict containers (zone_keys, record_keys as dicts with zone/record data as values) while real collector produces sets — handled by container-agnostic iteration helpers

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `run_ad_analysis()` is fully importable from `cloud_usage.providers.ad` and ready for CLI wiring (plan 29-04)
- CloudResource types `ad-dns-zone`, `ad-dns-record`, `ad-dhcp-scope` need to be added to `DDI_TYPES` in categorizer (plan 29-04)
- `ad-dhcp-ip` and `ad-user` are correctly classified as assets via ip_addresses presence / sentinel IP

## Self-Check: PASSED

All files present and task commit verified.

---
*Phase: 29-microsoft-ad-core*
*Completed: 2026-03-07*
