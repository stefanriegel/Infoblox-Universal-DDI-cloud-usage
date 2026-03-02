---
phase: 14-cli-integration
plan: "01"
subsystem: nios
tags: [cli, argparse, pyyaml, dataclass, nios, config]

# Dependency graph
requires:
  - phase: 13-output-and-runner
    provides: run_nios_analysis() pipeline callable; nios/output.py with full parse→filter→count→scenarios→output pipeline
provides:
  - NiosConfig frozen dataclass with from_yaml() YAML loader in src/cloud_usage/nios/config.py
  - --nios and --nios-config CLI flags in cli.py argparse
  - elif args.nios additive branch in main() wired to _run_nios_cli() helper
  - NiosConfig and run_nios_analysis exported from cloud_usage.nios.__init__
  - pyyaml>=6.0 added to requirements.txt
affects: [14-cli-integration, 15-dashboard-integration]

# Tech tracking
tech-stack:
  added: [pyyaml>=6.0]
  patterns:
    - Lazy import pattern for NIOS modules inside _run_nios_cli() to avoid import cost on cloud scans
    - Frozen dataclass for config objects (NiosConfig, FilterConfig, MigrationSplitConfig) — consistency with Phase 11-12 patterns
    - elif branch for CLI mode selection (exclusive with --web) — additive, no existing code modified
    - yaml.safe_load() with "or {}" guard for None return on empty YAML

key-files:
  created:
    - src/cloud_usage/nios/config.py
    - tests/nios/test_nios_cli.py
  modified:
    - src/cloud_usage/nios/__init__.py
    - src/cloud_usage/cli.py
    - requirements.txt

key-decisions:
  - "Patch target for run_nios_analysis in tests is cloud_usage.nios.run_nios_analysis (not cloud_usage.nios.output.run_nios_analysis) because _run_nios_cli() uses lazy import from cloud_usage.nios"
  - "All main() tests must patch cloud_usage.cli.check_platform to return {'python_ok': True} because the system runs Python 3.9 which fails the preflight check before reaching the elif branch"
  - "pyyaml>=6.0 added to requirements.txt — was already installed in system Python but missing from declared dependencies"
  - "NiosConfig.from_yaml() uses tuple() conversion for all list fields to maintain frozen dataclass compatibility"

patterns-established:
  - "Lazy import pattern: from cloud_usage.nios import run_nios_analysis, NiosConfig inside _run_nios_cli() body — modules imported only when --nios flag is used"
  - "YAML list-to-tuple: tuple(section.get('field') or []) — handles missing key, None value, and empty list uniformly"
  - "Private helper pattern: _run_nios_cli(args) isolates NIOS CLI logic from main() for independent testability"

requirements-completed: [INTEG-01]

# Metrics
duration: 45min
completed: 2026-03-02
---

# Phase 14-01: CLI Integration — NiosConfig + CLI flags Summary

**Additive CLI wiring: NiosConfig frozen dataclass with YAML loader + --nios/--nios-config argparse flags + elif branch in main() calling _run_nios_cli() — 27 unit tests all pass**

## Performance

- **Duration:** ~45 min
- **Completed:** 2026-03-02
- **Tasks:** 3 completed
- **Files modified:** 5

## Accomplishments

- Created `src/cloud_usage/nios/config.py` with `NiosConfig` frozen dataclass bundling `FilterConfig` + optional `MigrationSplitConfig`, with `from_yaml()` class method using `yaml.safe_load()` that converts YAML lists to tuples
- Added `--nios BACKUP.tar.gz` and `--nios-config CONFIG.yaml` argparse flags to `cli.py` plus `elif args.nios:` branch in `main()` wired to `_run_nios_cli()` helper with full error handling (file not found, YAML error, NiosParseError, unexpected exception)
- Updated `cloud_usage.nios.__init__.py` to export `NiosConfig` and `run_nios_analysis`; added `pyyaml>=6.0` to `requirements.txt`; created 27 unit tests in `tests/nios/test_nios_cli.py`

## Task Commits

Committed inline during execution (not yet committed to git — pending Phase 14 final commit):

1. **Task 1: Create NiosConfig dataclass + unit tests** - feat: NiosConfig frozen dataclass with from_yaml() + 10 unit tests
2. **Task 2: Update __init__.py exports + requirements.txt** - feat: export NiosConfig + run_nios_analysis; add pyyaml>=6.0
3. **Task 3: Add CLI flags + elif branch + unit tests** - feat: --nios/--nios-config flags + _run_nios_cli() helper + 17 CLI tests

## Files Created/Modified

- `src/cloud_usage/nios/config.py` - NiosConfig frozen dataclass with from_yaml() YAML loader
- `src/cloud_usage/nios/__init__.py` - Updated to export NiosConfig and run_nios_analysis
- `src/cloud_usage/cli.py` - Added --nios/--nios-config flags, elif branch, _run_nios_cli() helper
- `requirements.txt` - Added pyyaml>=6.0 to NIOS dependencies section
- `tests/nios/test_nios_cli.py` - 27 unit tests: NiosConfig (10), parse_args (3), main() branch (11), error paths (3)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Python 3.9 preflight check blocks elif branch in tests**
- **Found during:** Task 3 (CLI main() tests)
- **Issue:** `check_platform()` returns `{"python_ok": False}` on Python 3.9 (project runs on system Python 3.9), causing `main()` to return 1 before reaching `elif args.nios:` branch in all tests
- **Fix:** Added `patch("cloud_usage.cli.check_platform", return_value={"python_ok": True})` and `patch("cloud_usage.cli.print_preflight_warnings")` to every test that calls `main()`
- **Files modified:** tests/nios/test_nios_cli.py
- **Verification:** All 11 main() tests pass after patch

**2. [Rule 3 - Blocking] Wrong patch target for run_nios_analysis**
- **Found during:** Task 3 (mocked pipeline tests)
- **Issue:** Plan said "patch `cloud_usage.cli.run_nios_analysis`" but `_run_nios_cli()` uses lazy import `from cloud_usage.nios import run_nios_analysis` — the name in the cli module namespace is `cloud_usage.nios.run_nios_analysis`, not `cloud_usage.cli.run_nios_analysis`
- **Fix:** Changed all patch targets to `cloud_usage.nios.run_nios_analysis`
- **Files modified:** tests/nios/test_nios_cli.py
- **Verification:** Mock intercepts correctly; mock_run.assert_called_once() passes

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 blocking)
**Impact on plan:** Both fixes required for test correctness. No scope creep.

## Issues Encountered

- pyyaml was already installed in system Python (`/Users/mustermann/Library/Python/3.9/lib/python/site-packages/yaml`) but not declared in `requirements.txt` — added to make dependency explicit

## Next Phase Readiness

- Plan 14-02 ready: conftest.py needed for pytest.mark.integration, ZF acceptance test ready to add
