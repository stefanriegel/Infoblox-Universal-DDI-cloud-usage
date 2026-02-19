---
phase: 04-gcp-credential-chain-and-fail-fast
plan: 02
subsystem: auth
tags: [gcp, google-auth, credentials, singleton, fail-fast, subprocess-removal, discover]

# Dependency graph
requires:
  - phase: 04-01
    provides: "Thread-safe GCP credential singleton (get_gcp_credential()) in gcp_discovery/config.py"
provides:
  - "discover.py cleaned of all gcloud subprocess calls (check_gcloud_version, check_gcp_credentials deleted)"
  - "subprocess and re imports removed from discover.py"
  - "get_gcp_credential() called on main thread in discover.py before GCPDiscovery construction (CRED-03)"
  - "ADC project passed to GCPConfig so discovery works without GOOGLE_CLOUD_PROJECT env var"
  - "Auth failures now exit before discovery banner (fail-fast guarantee CRED-02)"
  - "_init_gcp_clients() no longer wraps get_gcp_credential() in bare except Exception (CRED-05)"
  - "Client construction failures re-raised as RuntimeError with exception chaining"
affects:
  - phase 05 (GCP multi-project discovery)
  - phase 06 (resource counting and dedup)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Main-thread singleton warming: call get_gcp_credential() in main() before any GCPDiscovery construction"
    - "Credential-outside-try: get_gcp_credential() call placed before try block so auth exceptions propagate freely"
    - "RuntimeError with 'from e': client construction failures re-raised with exception chaining for traceback preservation"
    - "ADC project flow: project returned by get_gcp_credential() passed to GCPConfig(project_id=project)"

key-files:
  created: []
  modified:
    - gcp_discovery/discover.py
    - gcp_discovery/gcp_discovery.py

key-decisions:
  - "Credential validation before banner print: get_gcp_credential() called before the 'GCP Cloud Discovery...' header so auth failures never produce misleading output"
  - "Project from ADC passed to GCPConfig: GCPConfig(project_id=project) ensures discovery uses the ADC-supplied project when GOOGLE_CLOUD_PROJECT is not set"
  - "RuntimeError not bare Exception for client init failures: more specific type, preserves exception chain via 'from e'"

patterns-established:
  - "Fail-fast order: validate credentials -> print banner -> fetch regions -> start discovery"
  - "Credential call isolation: get_gcp_credential() always outside any try/except block in the call chain"

requirements-completed: [CRED-02, CRED-03, CRED-05]

# Metrics
duration: 5min
completed: 2026-02-19
---

# Phase 4 Plan 02: Wire Credential Singleton into Discovery Flow Summary

**Removed gcloud subprocess credential checks from discover.py and moved singleton warming before the discovery banner; fixed bare except wrapping get_gcp_credential() in _init_gcp_clients() to let auth exceptions propagate**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-19T09:54:11Z
- **Completed:** 2026-02-19T09:59:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Deleted `check_gcloud_version()` and `check_gcp_credentials()` from `discover.py` — two functions that ran `gcloud --version` and `gcloud auth list` subprocesses, neither of which validates ADC
- Removed `import re` and `import subprocess` from `discover.py` (both were only used by the deleted functions)
- Added `get_gcp_credential()` call in `discover.py:main()` before any banner output — credentials are now validated and the singleton is warmed on the main thread before any worker thread spawns (CRED-03)
- Passed `project` from `get_gcp_credential()` to `GCPConfig(project_id=project)` so the ADC project flows through to discovery even when `GOOGLE_CLOUD_PROJECT` is not set
- Moved `get_gcp_credential()` call outside the try/except block in `_init_gcp_clients()` — auth exceptions now propagate freely instead of being swallowed as `Exception("Failed to initialize GCP clients: ...")` (CRED-05)
- Changed client initialization failure re-raise from bare `Exception` to `RuntimeError` with `from e` for proper exception chaining

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove gcloud subprocess checks, wire credential singleton in discover.py** - `ccb8527` (feat)
2. **Task 2: Fix bare except wrapping get_gcp_credential() in _init_gcp_clients()** - `f701c1c` (fix)

**Plan metadata:** (docs commit — see final commit)

## Files Created/Modified

- `gcp_discovery/discover.py` - Removed two gcloud subprocess functions and their imports; added get_gcp_credential() import and main-thread warming call before banner; pass project to GCPConfig
- `gcp_discovery/gcp_discovery.py` - Moved get_gcp_credential() outside try block in _init_gcp_clients(); wrapped only client construction in try/except with RuntimeError re-raise and exception chaining

## Decisions Made

- Credential validation before banner: `get_gcp_credential()` is called as the very first statement in `main()` so the tool never prints the "GCP Cloud Discovery..." header if auth fails — consistent with fail-fast intent of CRED-02.
- `GCPConfig(project_id=project)` accepts `None` (handled by `_get_default_project_id()` fallback to `GOOGLE_CLOUD_PROJECT`), so passing the ADC project is additive and doesn't break the existing env-var override behavior.
- `RuntimeError` (not bare `Exception`) for client construction failures — slightly more specific type that signals a programming/infrastructure error rather than a user-facing application exception.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `python` command not available on the system (macOS, no virtualenv). Import verification (`python -c "from gcp_discovery.discover import main"`) was not runnable due to missing `google` module in system Python. All verification performed via grep/structural analysis of the changed files, which confirmed all plan requirements met.

## User Setup Required

None — no external service configuration required. Changes are pure code cleanup; no new packages added.

## Next Phase Readiness

- `gcp_discovery/config.py` — credential singleton (Plan 01) — complete
- `gcp_discovery/discover.py` — entry point wired to singleton (Plan 02) — complete
- `gcp_discovery/gcp_discovery.py` — auth exceptions propagate from `_init_gcp_clients()` (Plan 02) — complete
- Phase 4 credential chain is now fully wired end-to-end: main thread warms singleton, workers get cache hit, auth failures exit before any discovery output
- Ready for Phase 5: GCP multi-project discovery

---
*Phase: 04-gcp-credential-chain-and-fail-fast*
*Completed: 2026-02-19*
