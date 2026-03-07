---
phase: 29-microsoft-ad-core
plan: 01
subsystem: testing
tags: [tdd, red-gate, ad, winrm, microsoft-ad, pytest]

requires:
  - phase: 28-gcp-ddi-gaps
    provides: "GCP DDI collectors and categorizer update establishing the provider pattern used by AD"

provides:
  - "38 RED test methods across 2 new test files defining the full AD provider contract"
  - "Module-level imports in test_ad_collector.py and test_ad_runner.py trigger ModuleNotFoundError (RED gate)"
  - "TestAdDdiTypesInCategorizer in test_categorizer.py with 4 assertions (3 FAIL, 1 PASS)"
  - "Complete contract for MicrosoftAdCollector, AdOptions, normalize_ad_servers, normalize_ad_services"
  - "Complete contract for run_ad_analysis() returning CloudResource objects with ad-dns-zone/ad-dns-record/ad-dhcp-scope/ad-user types"

affects: [29-02, 29-03]

tech-stack:
  added: []
  patterns:
    - "TDD RED gate via module-level imports: from cloud_usage.providers.ad.collector import MicrosoftAdCollector triggers collection-time ImportError"
    - "Contract documentation pattern: GREEN path logic as inline comments showing expected post-implementation assertions"
    - "Sentinel IP pattern for AD users: ip_addresses=['0.0.0.0'] forces asset categorization in existing pipeline"

key-files:
  created:
    - tests/test_ad_collector.py
    - tests/test_ad_runner.py
  modified:
    - tests/test_categorizer.py

key-decisions:
  - "Module-level imports (not per-method pytest.raises) used for RED gate — entire file fails collection, matching Phase 28 pattern"
  - "TestAdDdiTypesInCategorizer placed in test_categorizer.py as a class (not standalone function) for consistency with Phase 27/28 pattern"
  - "ad-user NOT in DDI_TYPES confirmed from day 1 — test_ad_user_not_in_ddi_types passes immediately (GREEN)"
  - "run_ad_analysis() returns tuple (resources, errors) — inferred from contract tests and CONTEXT.md resilience model"
  - "_collect_dns/_collect_dhcp/_collect_users all take (self, session) — session is the WinRM session object"
  - "_run_ps_json patched directly on collector instance in tests (not at module level) — allows per-test side_effect setup"
  - "ad-dhcp-ip resource type included as alternative shape for DHCP lease/reservation IP representation (runner test tolerates both shapes)"

patterns-established:
  - "AD test helper functions follow GCP pattern: _make_zone_data(), _make_a_record(), _make_scope_data(), _make_lease_data(), _make_user_data()"
  - "Mock collector result dict has keys: server, status, dns{zone_keys, record_keys, ip_addresses}, dhcp{scope_keys, lease_keys, reservation_keys}, users{user_keys}"

requirements-completed: []

duration: 4min
completed: 2026-03-07
---

# Phase 29 Plan 01: Microsoft AD RED gate tests Summary

**38 failing tests (ModuleNotFoundError + AssertionError) define the full AD provider contract — MicrosoftAdCollector, AdOptions, run_ad_analysis(), and categorizer DDI types — before any implementation exists**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-07T18:57:08Z
- **Completed:** 2026-03-07T18:57:08Z
- **Tasks:** 1 (TDD RED)
- **Files modified:** 3

## Accomplishments

- Created `tests/test_ad_collector.py` with 22 test methods covering AD-01 through AD-07: collector import, DNS collection (zones/records/IPs), DHCP collection (scopes/leases/reservations), user collection with SID dedup, autodiscovery, NTLM/Kerberos auth validation, server normalization, DC failure isolation
- Created `tests/test_ad_runner.py` with 16 test methods covering AD-01, AD-02, AD-03, AD-04, AD-08: run_ad_analysis() CloudResource return shape (provider, resource_type, ip_addresses, details), DNS zone/record/DHCP scope/user shapes, DHCP IP total count, XLS report integration
- Appended `TestAdDdiTypesInCategorizer` to `tests/test_categorizer.py` — 3 DDI type assertions fail (RED), 1 ad-user exclusion assertion passes immediately

## Task Commits

1. **RED gate: AD provider test files** - `1aa2ce7` (test)

## Files Created/Modified

- `tests/test_ad_collector.py` — 22 test methods; module-level import triggers ModuleNotFoundError (RED); covers collector, options, autodiscovery, auth (AD-01/02/03/04/05/06/07)
- `tests/test_ad_runner.py` — 16 test methods; module-level import triggers ModuleNotFoundError (RED); covers run_ad_analysis() output shapes and XLS integration (AD-01/02/03/04/08)
- `tests/test_categorizer.py` — Appended TestAdDdiTypesInCategorizer: ad-dns-zone/ad-dns-record/ad-dhcp-scope FAIL (RED), ad-user NOT in DDI_TYPES PASSES

## Decisions Made

- Module-level imports (not per-method `pytest.raises`) used for RED gate — matches Phase 28 pattern where entire file fails collection with ImportError/ModuleNotFoundError
- `run_ad_analysis()` signature: `run_ad_analysis(opts, output_path=None) -> tuple[list[CloudResource], list[str]]` inferred from context (resilience model requires separate errors return)
- `ad-user` sentinel IP `["0.0.0.0"]` forces asset categorization through existing pipeline without modifying categorizer for a non-DDI type
- `ad-dhcp-ip` resource type included as optional shape — test_ad_runner asserts total DHCP IP count regardless of whether IPs live in scope.ip_addresses or separate ad-dhcp-ip resources

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- RED gate established for all AD-01 through AD-08 requirements
- 29-02 creates `src/cloud_usage/providers/ad/` package — `MicrosoftAdCollector`, `AdOptions`, `normalize_ad_servers`, `normalize_ad_services`, `run_ad_analysis`; test files will transition from ERROR to PASS
- 29-03 wires AD into CLI and adds `ad-dns-zone`, `ad-dns-record`, `ad-dhcp-scope` to `DDI_TYPES` — categorizer tests will turn GREEN

## Self-Check: PASSED

- tests/test_ad_collector.py: FOUND
- tests/test_ad_runner.py: FOUND
- .planning/phases/29-microsoft-ad-core/29-01-SUMMARY.md: FOUND
- Commit 1aa2ce7: FOUND

---
*Phase: 29-microsoft-ad-core*
*Completed: 2026-03-07*
