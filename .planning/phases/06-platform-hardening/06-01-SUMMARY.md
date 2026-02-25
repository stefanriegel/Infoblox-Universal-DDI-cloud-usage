---
phase: 06-platform-hardening
plan: 01
subsystem: infra
tags: [preflight, platform, windows, sigterm, setup-scripts, cli-detection]

# Dependency graph
requires:
  - phase: 05-web-dashboard
    provides: CLI entry point (cli.py) that preflight is wired into
provides:
  - Platform preflight checks (Python version, OS, ANSI, long-path, CLI presence)
  - Windows-safe SIGTERM guard in GracefulShutdown
  - Modernized setup scripts using consolidated requirements.txt with CLI detection
affects: [future phases using CLI or setup scripts on Windows]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "preflight.py gathers platform info as dict, print function renders warnings — separation of detection from presentation"
    - "sys.platform != 'win32' guard on SIGTERM registration — Windows-safe signal handling"
    - "Setup scripts use single top-level requirements.txt — no per-provider splits"

key-files:
  created:
    - src/cloud_usage/preflight.py
    - tests/test_preflight.py
    - tests/test_setup_scripts.py
  modified:
    - src/cloud_usage/cli.py
    - src/cloud_usage/discovery/shutdown.py
    - setup_venv.sh
    - setup_venv.ps1
    - setup_venv.bat

key-decisions:
  - "preflight check_platform() returns dict so callers can inspect results without re-running detection"
  - "print_preflight_warnings() hard-exits only on Python < 3.10; all other issues are warn-only on stderr"
  - "SIGTERM registered only on sys.platform != 'win32' — SIGINT is the primary interrupt on Windows"
  - "Bash setup script does NOT prompt to install CLIs (just prints URL) — Linux/macOS users use package managers"
  - "PowerShell Test-CLI() prompts to open browser in interactive mode, skips prompt when ProviderChoice is set (CI mode)"
  - "setup_venv.ps1 signature block removed — sign-ps1.yml workflow re-signs on push"
  - "Test test_python_ok_reflects_current_version checks actual runtime version dynamically — avoids hardcoded 3.10+ assumption"

patterns-established:
  - "Module-level private helpers with leading underscore (_check_long_path_registry, _check_ansi, _check_execution_policy)"
  - "from __future__ import annotations at top of all new modules"

requirements-completed: [PLAT-01]

# Metrics
duration: 3min
completed: 2026-02-25
---

# Phase 6 Plan 1: Platform Hardening Summary

**preflight.py module with cross-platform detection wired into CLI at startup, Windows-safe SIGTERM guard, and three modernized setup scripts using consolidated requirements.txt with cloud CLI detection**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T07:01:14Z
- **Completed:** 2026-02-25T07:04:30Z
- **Tasks:** 2
- **Files modified:** 7 (3 created: preflight.py, test_preflight.py, test_setup_scripts.py; 4 modified: cli.py, shutdown.py, setup_venv.sh, setup_venv.ps1, setup_venv.bat)

## Accomplishments

- Created `preflight.py` with `check_platform()` and `print_preflight_warnings()` — detects Python version, OS, WSL, ANSI capability, Windows long-path support, ExecutionPolicy, and all three cloud CLIs
- Wired preflight into `cli.py` `main()` immediately after `parse_args()` with warn-only behavior (only hard exit on Python < 3.10)
- Fixed SIGTERM registration in `GracefulShutdown` with `sys.platform != "win32"` guard so Windows users don't get AttributeError on SIGTERM
- Rewrote all three setup scripts to install from single top-level `requirements.txt` with cloud CLI detection and platform-specific warnings (34 tests passing)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create preflight module, wire into CLI, fix SIGTERM guard** - `f016e47` (feat)
2. **Task 2: Modernize setup scripts with CLI detection and platform warnings** - `1f91f22` (feat)

**Plan metadata:** (created below)

## Files Created/Modified

- `src/cloud_usage/preflight.py` - Platform detection: Python version, OS, WSL, ANSI, long-path, ExecutionPolicy, cloud CLI presence
- `src/cloud_usage/cli.py` - Added preflight import and call in main() before web dashboard check
- `src/cloud_usage/discovery/shutdown.py` - Added sys.platform guard on SIGTERM registration
- `tests/test_preflight.py` - 13 tests for check_platform() and print_preflight_warnings()
- `tests/test_setup_scripts.py` - 21 tests asserting no legacy paths and CLI detection presence
- `setup_venv.sh` - Removed provider menu, installs from requirements.txt, adds check_cli() and port check
- `setup_venv.ps1` - Added ExecutionPolicy detect-and-guide, Test-CLI(), long-path check, port check; removed provider menu
- `setup_venv.bat` - Installs from requirements.txt, adds 'where' CLI detection; removed provider menu

## Decisions Made

- `check_platform()` returns a dict (not prints) so callers can inspect individual fields without re-running detection
- `print_preflight_warnings()` only hard-exits on Python < 3.10; everything else prints to stderr and continues
- SIGTERM guard uses `sys.platform != "win32"` per plan spec — SIGINT is the primary interrupt mechanism on Windows
- Bash script doesn't prompt to open install URLs (non-interactive pattern for Linux/macOS); PowerShell script does prompt in interactive mode but skips in CI mode when `$ProviderChoice` is set
- Test renamed from `test_python_ok_true_on_current` to `test_python_ok_reflects_current_version` to work correctly on Python 3.9 test runner

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test assuming Python 3.10+ runtime**
- **Found during:** Task 1 (test execution)
- **Issue:** `test_python_ok_true_on_current` asserted `python_ok is True` but test runner uses system Python 3.9.6, causing immediate failure
- **Fix:** Renamed test and changed assertion to `sys.version_info >= (3, 10)` — dynamically checks the actual runtime
- **Files modified:** `tests/test_preflight.py`
- **Verification:** All 13 tests pass on Python 3.9.6
- **Committed in:** f016e47 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test assumption)
**Impact on plan:** Essential fix for CI correctness. No scope creep.

## Issues Encountered

None beyond the test runtime Python version mismatch above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Platform hardening plan 01 complete; ready for plan 02 (if any additional hardening tasks exist)
- preflight.py is importable from any future feature that wants to check platform conditions
- All three setup scripts are maintainable going forward — single requirements.txt path, no per-provider branches

---
*Phase: 06-platform-hardening*
*Completed: 2026-02-25*

## Self-Check: PASSED

- FOUND: src/cloud_usage/preflight.py
- FOUND: src/cloud_usage/cli.py
- FOUND: src/cloud_usage/discovery/shutdown.py
- FOUND: tests/test_preflight.py
- FOUND: tests/test_setup_scripts.py
- FOUND: setup_venv.sh
- FOUND: setup_venv.ps1
- FOUND: setup_venv.bat
- FOUND: .planning/phases/06-platform-hardening/06-01-SUMMARY.md
- FOUND commit f016e47 (Task 1: preflight module)
- FOUND commit 1f91f22 (Task 2: setup scripts)
