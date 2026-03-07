---
phase: 29-microsoft-ad-core
plan: 02
subsystem: ad-provider
tags: [ad, winrm, microsoft-ad, collector, options, constants, tdd, green]

requires:
  - phase: 29-microsoft-ad-core
    plan: 01
    provides: "38 failing tests defining the full AD provider contract (RED gate)"

provides:
  - "src/cloud_usage/providers/ad/ package with 4 files (init, constants, options, collector)"
  - "SUPPORTED_DNS_RECORD_TYPES frozenset with 13 types"
  - "AdOptions frozen dataclass with auth_mode/NTLM/port/retry validation"
  - "normalize_ad_servers and normalize_ad_services helpers"
  - "MicrosoftAdCollector with lazy winrm import, DNS/DHCP/User collection, autodiscovery"
  - "WinRMError exception class for DC failure handling"
  - "run_ad_analysis() stub in __init__.py (full implementation in 29-03)"

affects: [29-03]

tech-stack:
  added: []
  patterns:
    - "Lazy winrm import via importlib.import_module('winrm') — module importable without pywinrm installed"
    - "Frozen dataclass pattern for immutable options (same as GCP/Azure patterns)"
    - "Per-DC error isolation: WinRMError caught in collect_all(), status='error' recorded, collection continues"
    - "Dedup key pattern: f'{zone}|{owner}|{type}|{data_json}' for DNS record deduplication"

key-files:
  created:
    - src/cloud_usage/providers/ad/__init__.py
    - src/cloud_usage/providers/ad/constants.py
    - src/cloud_usage/providers/ad/options.py
    - src/cloud_usage/providers/ad/collector.py
  modified: []

key-decisions:
  - "record_keys (not supported_record_entries) used as return key in _collect_dns — matches actual test assertions from 29-01"
  - "_resolve_targets() takes no arguments — uses self.options; tests call it with no args"
  - "collect_all() returns list of dicts (not tuple); adds server key to result if missing from mock returns"
  - "run_ad_analysis() stub added to __init__.py now (not 29-03) because test_ad_collector.py imports it at module level for TestAllDcsFail"
  - "_collect_dns returns ip_addresses as list (not set) to preserve extraction order and allow duplicate filtering via seen_ips set"

requirements-completed:
  - AD-01
  - AD-02
  - AD-03
  - AD-04
  - AD-05
  - AD-06
  - AD-07

duration: 7min
completed: 2026-03-07
---

# Phase 29 Plan 02: Microsoft AD Collector Implementation Summary

**AD provider package implemented: constants (13 DNS types), AdOptions dataclass with validation, MicrosoftAdCollector with lazy WinRM/PowerShell-based DNS/DHCP/User collection and autodiscovery — all 22 test_ad_collector.py tests GREEN**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-07T19:05:21Z
- **Completed:** 2026-03-07T19:13:00Z
- **Tasks:** 2 (TDD GREEN for Task 1 + Task 2)
- **Files modified:** 4

## Accomplishments

- Created `src/cloud_usage/providers/ad/constants.py`: `SUPPORTED_DNS_RECORD_TYPES` frozenset with 13 types (A, AAAA, CNAME, MX, TXT, CAA, SRV, SVCB, HTTPS, PTR, NS, SOA, NAPTR), `AD_SERVICES` tuple
- Created `src/cloud_usage/providers/ad/options.py`: `AdOptions` frozen dataclass with `__post_init__` validation (auth_mode, NTLM credentials, port range, retries, backoff); `normalize_ad_servers` (lowercase + dedup); `normalize_ad_services` (validate against AD_SERVICES); `cert_validation` property
- Created `src/cloud_usage/providers/ad/collector.py`: `MicrosoftAdCollector` with lazy `winrm` import via `importlib`; `WinRMError` class; `_build_session` (endpoint URL + auth/timeout kwargs); `_run_ps_text` (retry with exponential backoff); `_run_ps_json` (PS → JSON parser); `_collect_dns` (zones + records + IPs); `_collect_dhcp` (scopes/leases/reservations); `_collect_users` (SID/UPN/SAM dedup); `_resolve_targets` (static or autodiscovery); `collect_all` (per-DC with failure isolation)
- Created `src/cloud_usage/providers/ad/__init__.py`: package marker + `run_ad_analysis()` stub (full implementation in 29-03)
- All 22 `test_ad_collector.py` tests GREEN; `test_ad_runner.py` and `test_categorizer.py` AD DDI type tests remain RED (planned — 29-03 scope)

## Task Commits

1. **feat(29-02): implement AD constants, AdOptions dataclass, normalization helpers** - `309f746`
2. **feat(29-02): implement MicrosoftAdCollector with WinRM session and DNS/DHCP/User collection** - `889ea17`

## Files Created/Modified

- `src/cloud_usage/providers/ad/__init__.py` — package marker + run_ad_analysis() stub for TestAllDcsFail
- `src/cloud_usage/providers/ad/constants.py` — SUPPORTED_DNS_RECORD_TYPES (13), AD_SERVICES ("dns","dhcp","user")
- `src/cloud_usage/providers/ad/options.py` — AdOptions frozen dataclass + normalize helpers
- `src/cloud_usage/providers/ad/collector.py` — MicrosoftAdCollector: session, DNS/DHCP/User collection, autodiscovery

## Decisions Made

- `record_keys` used as return key in `_collect_dns()` (plan said `supported_record_entries` but actual test assertions from 29-01 use `record_keys`) — auto-aligned with test contract
- `_resolve_targets()` takes no arguments — test calls `collector._resolve_targets()` with no args, uses `self.options` internally
- `collect_all()` returns a flat list of result dicts (not a tuple) — test iterates list directly
- `run_ad_analysis()` added to `__init__.py` now (not deferred to 29-03) because `TestAllDcsFail` in test_ad_collector.py imports it at module level
- `_collect_server(server, session)` signature matches test's mock which calls with 2 positional args

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] record_keys vs supported_record_entries key name mismatch**
- **Found during:** Task 2 (implementing collector)
- **Issue:** Plan spec named return key `supported_record_entries` but test assertions (written in 29-01) use `result["record_keys"]`
- **Fix:** Used `record_keys` as the dict key in `_collect_dns()` return value to match actual test assertions
- **Files modified:** `src/cloud_usage/providers/ad/collector.py`

**2. [Rule 2 - Missing critical functionality] run_ad_analysis() needed in 29-02 scope**
- **Found during:** Task 2 (TestAllDcsFail test imports from cloud_usage.providers.ad)
- **Issue:** `TestAllDcsFail` is in `test_ad_collector.py` (29-02 scope) but imports `run_ad_analysis` — plan deferred this to 29-03
- **Fix:** Added `run_ad_analysis()` stub to `__init__.py` that handles error-only results; full CloudResource conversion left to 29-03
- **Files modified:** `src/cloud_usage/providers/ad/__init__.py`

**3. [Rule 1 - Bug] collect_all() result dict missing server key**
- **Found during:** Task 2 (TestDcFailureContinue test)
- **Issue:** Test's mock `_collect_server` returns `{"status": "ok", ...}` without `"server"` key; test then filters `r["server"]`
- **Fix:** `collect_all()` adds `"server"` key to result dict if missing before appending to results list
- **Files modified:** `src/cloud_usage/providers/ad/collector.py`

## Issues Encountered

None beyond the 3 auto-fixed deviations above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- 29-03 can import `MicrosoftAdCollector`, `AdOptions`, `run_ad_analysis` from `cloud_usage.providers.ad`
- 29-03 should implement full `run_ad_analysis()` CloudResource conversion (replacing stub in `__init__.py`)
- 29-03 wires AD provider into CLI + adds `ad-dns-zone`, `ad-dns-record`, `ad-dhcp-scope` to `DDI_TYPES`

## Self-Check: PASSED

- src/cloud_usage/providers/ad/__init__.py: FOUND
- src/cloud_usage/providers/ad/constants.py: FOUND
- src/cloud_usage/providers/ad/options.py: FOUND
- src/cloud_usage/providers/ad/collector.py: FOUND
- Commit 309f746: FOUND
- Commit 889ea17: FOUND

---
*Phase: 29-microsoft-ad-core*
*Completed: 2026-03-07*
