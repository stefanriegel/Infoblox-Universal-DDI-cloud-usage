---
phase: 04-gcp-credential-chain-and-fail-fast
plan: 01
subsystem: auth
tags: [gcp, google-auth, credentials, singleton, threading, fail-fast]

# Dependency graph
requires: []
provides:
  - "Thread-safe GCP credential singleton with double-checked locking in gcp_discovery/config.py"
  - "Token validation via credentials.refresh(Request()) on startup"
  - "Credential type logging via [Auth] prefix (SA email, ADC, Compute Engine, generic)"
  - "Permission pre-check via compute_v1.RegionsClient.list() with IAM guidance on failure"
  - "Actionable fail-fast error messages for DefaultCredentialsError and RefreshError"
  - "Removal of all gcloud subprocess calls from gcp_discovery/config.py"
affects:
  - phase 05 (discover.py cleanup)
  - phase 06 (GCP multi-project discovery)
  - any phase using get_gcp_credential()

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Double-checked locking singleton: _gcp_credential_cache + _gcp_credential_lock (threading.Lock)"
    - "Typed exception catching: DefaultCredentialsError and RefreshError only in credential chain"
    - "Deferred imports in _check_gcp_compute_permission() to avoid circular imports"
    - "isinstance() hierarchy for credential type detection (service_account > oauth2.credentials > compute_engine > fallback)"

key-files:
  created: []
  modified:
    - gcp_discovery/config.py

key-decisions:
  - "Both SA and ADC remediation paths shown equally on DefaultCredentialsError (no preference)"
  - "except Exception in _check_gcp_compute_permission() is acceptable — it is not in the credential chain; only PermissionDenied and Forbidden trigger sys.exit(1)"
  - "except Exception in get_all_gcp_regions() remains — it is a discovery fallback, not an auth error"
  - "_log_gcp_credential_type() uses google.oauth2.credentials.Credentials for both ADC user creds and gcloud auth login (same Python class)"
  - "Compute imports deferred inside _check_gcp_compute_permission() to avoid circular imports"

patterns-established:
  - "GCP credential singleton pattern: get_gcp_credential() -> _build_gcp_credential() with double-checked lock (mirrors azure_discovery/config.py)"
  - "Auth fail-fast: _fail_gcp_auth() always calls sys.exit(1) and never returns"
  - "Permission pre-check: lightweight API call at singleton build time, not at discovery time"

requirements-completed: [CRED-01, CRED-02, CRED-04, CRED-05]

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 4 Plan 01: GCP Credential Chain and Fail-Fast Summary

**Thread-safe GCP credential singleton using google.auth.default() + credentials.refresh() with typed fail-fast exits and compute permission pre-check, eliminating all gcloud subprocess auth calls**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T09:49:09Z
- **Completed:** 2026-02-19T09:52:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Rewrote `get_gcp_credential()` as a thread-safe module-level singleton with double-checked locking pattern matching `azure_discovery/config.py`
- Added `_build_gcp_credential()` that validates via `credentials.refresh(Request())`, logs credential type with `[Auth]` prefix and default project, and pre-checks compute permissions before returning
- Replaced `GCPConfig._get_default_project_id()` subprocess fallback (gcloud config get-value project + "default-project" hardcoded) with `os.getenv("GOOGLE_CLOUD_PROJECT")` only
- Eliminated all gcloud subprocess calls from `gcp_discovery/config.py`; credential chain now catches only `DefaultCredentialsError` and `RefreshError` (CRED-05)

## Task Commits

Each task was committed atomically:

1. **Task 1 + Task 2: Rewrite get_gcp_credential() singleton and remove gcloud subprocess** - `7126406` (feat)

**Plan metadata:** (docs commit — see final commit)

## Files Created/Modified

- `gcp_discovery/config.py` - Complete rewrite: added singleton variables, _build_gcp_credential(), _log_gcp_credential_type(), _check_gcp_compute_permission(), _fail_gcp_auth(); replaced _get_default_project_id() with env-var-only version; removed all subprocess usage

## Decisions Made

- Used `except Exception` in `_check_gcp_compute_permission()` catch-all for transient errors (network, quota, 429) — these proceed silently; only `PermissionDenied` and `Forbidden` trigger `sys.exit(1)`. This is not a violation of CRED-05 because the credential chain (in `_build_gcp_credential()`) catches only typed exceptions.
- `google.oauth2.credentials.Credentials` covers both `gcloud auth application-default login` (ADC user) and `gcloud auth login` (end-user) — same Python class. Logged as "Application Default Credentials" per research recommendation.
- Kept `except Exception` in `get_all_gcp_regions()` — it's a discovery fallback for API availability, not an auth error handler. CRED-05 specifies "in credential chain" specifically.
- Deferred `compute_v1` and `api_exceptions` imports inside `_check_gcp_compute_permission()` to avoid circular imports and keep the function self-contained per plan specification.

## Deviations from Plan

None — plan executed exactly as written. The `except Exception` in `_check_gcp_compute_permission()` uses isinstance() checks for typed dispatch rather than typed except clauses — this is the approach recommended in the research document (Pattern 4) when the import must be deferred. Final implementation uses typed except clauses directly (`except api_exceptions.PermissionDenied` / `except api_exceptions.Forbidden`) since imports are at the top of the try block, which is cleaner than the research's bare-except-with-isinstance approach.

## Issues Encountered

- `python` command not available on the system (macOS system Python is `python3`); no virtual environment exists in the repo. Import verification was performed via Python's `ast` module to parse and walk the AST without requiring google-auth to be installed. All logical checks (function names, exception types caught, pattern structure) confirmed correct via AST analysis.

## User Setup Required

None — no external service configuration required. The credential singleton uses the google-auth library already in requirements.txt; no new packages added.

## Next Phase Readiness

- `get_gcp_credential()` singleton is ready; `discover.py` still calls `check_gcloud_version()` and `check_gcp_credentials()` subprocess functions (Phase 5 removes these)
- `GCPDiscovery._init_gcp_clients()` still has bare `except Exception` wrapping `get_gcp_credential()` (Phase 5 cleanup)
- Credential warming on main thread before workers spawn: Phase 5 adds explicit `get_gcp_credential()` call in `discover.py:main()` before `GCPDiscovery` construction

---
*Phase: 04-gcp-credential-chain-and-fail-fast*
*Completed: 2026-02-19*
