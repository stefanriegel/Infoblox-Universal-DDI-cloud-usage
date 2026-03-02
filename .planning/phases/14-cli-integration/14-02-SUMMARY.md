---
phase: 14-cli-integration
plan: "02"
subsystem: nios
tags: [pytest, acceptance-test, integration, openpyxl, cli, zf-reference]

# Dependency graph
requires:
  - phase: 14-01
    provides: NiosConfig, --nios/--nios-config CLI flags, _run_nios_cli() helper, test_nios_cli.py structure
provides:
  - tests/conftest.py with pytest.mark.integration registration (no PytestUnknownMarkWarning)
  - ZF reference backup acceptance test: test_cli_nios_e2e_zf_reference — end-to-end CLI → xlsx validation
  - Confirmed reference figure: 304,730 unique Active IPs (4-source dedup, default active-only lease filter)
affects: [14-cli-integration, 15-dashboard-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - pytest.mark.integration for external-data acceptance tests (skip when file absent)
    - openpyxl row scanning for dynamic cell location (scan column A for label, not hardcoded row)
    - pytest.mark.skipif(not os.path.exists(path)) for conditional integration tests

key-files:
  created:
    - tests/conftest.py
  modified:
    - tests/nios/test_nios_cli.py

key-decisions:
  - "Reference figure is 304,730 (not 168,295): 304,730 is the confirmed 4-source dedup total (active leases + fixed addresses + host addresses + network reservations) per STATE.md COUNT-02 decision and REQUIREMENTS.md COUNT-02; 168,295 was an outdated active-lease-only subset figure in CONTEXT.md"
  - "Acceptance test skips cleanly (not errors) when ZF backup absent via @pytest.mark.skipif(not os.path.exists(path))"
  - "Scenario Comparison Active IPs cell found by scanning column A for exact string 'Active IPs' — no hardcoded row number"

patterns-established:
  - "Integration test skip pattern: @pytest.mark.skipif(not os.path.exists(_ZF_BACKUP_PATH), reason=...) — consistent with project's external-data strategy"
  - "Dynamic cell location: scan ws.iter_rows() for label in column A, then read first non-None value in that row — resilient to sheet structure changes"

requirements-completed: [INTEG-01]

# Metrics
duration: 20min
completed: 2026-03-02
---

# Phase 14-02: CLI Integration — ZF Acceptance Test Summary

**End-to-end acceptance test confirms CLI produces valid xlsx from ZF reference backup with 304,730 Active IPs in Scenario Comparison sheet — all 181 NIOS tests pass (154 pre-existing + 27 new)**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-03-02
- **Tasks:** 3 completed
- **Files modified:** 2

## Accomplishments

- Created `tests/conftest.py` with `pytest_configure()` registering `pytest.mark.integration` marker — eliminates `PytestUnknownMarkWarning` across all test runs
- Added `test_cli_nios_e2e_zf_reference` acceptance test in `tests/nios/test_nios_cli.py`: calls `main(["--nios", zf_backup_path, "--output-dir", str(tmp_path)])`, verifies exit 0, valid xlsx, `Scenario Comparison` sheet present, `Active IPs` row == 304,730 — skips when backup file absent
- Completed full regression: 181 NIOS tests pass (154 pre-existing phases 10-13 + 27 new phase 14), acceptance test passes in 295 seconds against ZF backup

## Task Commits

Committed inline during execution (pending Phase 14 final git commit):

1. **Task 1: Create tests/conftest.py** - feat: pytest.mark.integration registration
2. **Task 2: Add ZF acceptance test** - test: test_cli_nios_e2e_zf_reference end-to-end acceptance test
3. **Task 3: Full regression verification** - 181 tests pass, CLI help confirmed, acceptance test 304,730 validated

## Files Created/Modified

- `tests/conftest.py` - pytest_configure() with integration marker registration
- `tests/nios/test_nios_cli.py` - Added test_cli_nios_e2e_zf_reference at end of file (section: Acceptance tests — ZF reference backup)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Wrong reference figure] Plan specified 168,295 but actual pipeline produces 304,730**
- **Found during:** Task 2 (acceptance test initial run — assertion failure)
- **Issue:** CONTEXT.md stated "active IP count in Scenario Comparison sheet matches 168,295" — this was an outdated figure from an earlier analysis stage. The acceptance test initially asserted `== 168_295` and failed.
- **Fix:** Cross-referenced STATE.md key decision "(11-03): ZF reference value: 304,730 unique Active IPs (4-source dedup)" and REQUIREMENTS.md COUNT-02 which documents the 4-source dedup. Corrected assertion to `int(active_ip_value) == 304_730`.
- **Root cause:** CONTEXT.md was written with an older figure (168,295 = active leases only, before HOST_ADDRESS key fix). The 304,730 figure is the empirically verified value after fixing HOST_ADDRESS raw_attrs key to 'address' in Phase 11-03.
- **Files modified:** tests/nios/test_nios_cli.py
- **Verification:** Acceptance test passes (295 seconds runtime)

---

**Total deviations:** 1 auto-fixed (wrong reference figure from CONTEXT.md)
**Impact on plan:** No scope creep. The correct figure (304,730) is documented in STATE.md and REQUIREMENTS.md — the plan had a stale value.

## Issues Encountered

- Acceptance test runtime: 295 seconds (4m 55s) — expected for a full pipeline run against the 2.5M object ZF backup; acceptable for integration test that runs separately from unit test suite

## Next Phase Readiness

- Phase 14 complete: CLI integration fully wired and acceptance-tested
- Phase 15 (Dashboard Integration) can proceed: `run_nios_analysis()` is callable from any Python context; `NiosConfig` is importable from `cloud_usage.nios`
- No blockers for dashboard tab implementation
