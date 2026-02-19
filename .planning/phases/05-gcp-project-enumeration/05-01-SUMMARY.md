---
phase: 05-gcp-project-enumeration
plan: 01
subsystem: infra
tags: [gcp, project-enumeration, resource-manager, service-usage, fnmatch, dataclass]

# Dependency graph
requires:
  - phase: 04-gcp-credential-singleton
    provides: get_gcp_credential() singleton and validated credentials object
provides:
  - ProjectInfo dataclass with project_id, compute_enabled, dns_enabled fields
  - enumerate_gcp_projects() function that returns curated List[ProjectInfo]
  - _fetch_active_projects() via search_projects with org scoping
  - _apply_project_filters() via fnmatch glob include/exclude
  - _check_apis_enabled() via batch_get_services (single RPC per project)
  - _log_api_status() with [Skip] lines for disabled APIs
affects:
  - 05-02 (Phase 5 plan 2 — discover.py wiring and CLI flags)
  - 06-concurrent-multi-project-discovery (consumes ProjectInfo list)

# Tech tracking
tech-stack:
  added:
    - google-cloud-resource-manager>=1.12.0 (resourcemanager_v3.ProjectsClient.search_projects)
    - google-cloud-service-usage>=1.3.0 (service_usage_v1.ServiceUsageClient.batch_get_services)
  patterns:
    - Deferred imports inside function bodies to avoid circular imports (established in Phase 4)
    - Single ServiceUsageClient created once in enumerate_gcp_projects() and passed to _check_apis_enabled() (avoid per-project client construction)
    - search_projects with query="state:ACTIVE" for org-wide traversal without folder recursion
    - batch_get_services for two-API check in a single RPC (halves quota usage vs two get_service calls)
    - fnmatch.fnmatch for shell-glob project filtering (no new dependency, zero regex complexity)

key-files:
  created: []
  modified:
    - gcp_discovery/config.py
    - requirements.txt

key-decisions:
  - "enumerate_gcp_projects() takes explicit keyword args (not args namespace) for testability — no argparse coupling in the core function"
  - "ServiceUsageClient created once in enumerate_gcp_projects() and passed to _check_apis_enabled() as client param — avoids per-project client construction anti-pattern"
  - "_check_apis_enabled() catches PermissionDenied as (False, False) and any other Exception as (True, True) — treats accessNotConfigured as disabled, transient errors as assumed-enabled"
  - "Priority chain: project param > GOOGLE_CLOUD_PROJECT env > adc_project — matches GCP SDK flag-overrides-env convention"
  - "Count printed before pre-check loop ('Found N ACTIVE projects') so [Skip] lines appear beneath context — per locked decision"
  - "Org scoping: org_id arg wins over GOOGLE_CLOUD_ORG_ID env var; org_id normalized to organizations/{id} format inside _fetch_active_projects()"

patterns-established:
  - "Deferred GCP imports: resourcemanager_v3 and service_usage_v1 imported inside function bodies, not at module level"
  - "Client reuse: heavy API clients created once and reused across loops (see enumerate_gcp_projects + _check_apis_enabled)"
  - "Defense-in-depth state comparison: server-side query=state:ACTIVE PLUS client-side project.state == ACTIVE enum check"

requirements-completed: [ENUM-01, ENUM-02, ENUM-03, ENUM-04, ENUM-05, ENUM-06]

# Metrics
duration: 2min
completed: 2026-02-19
---

# Phase 05 Plan 01: GCP Project Enumeration — Core Logic Summary

**ProjectInfo dataclass and enumerate_gcp_projects() added to config.py using search_projects, batch_get_services, and fnmatch for org-scoped multi-project enumeration with per-project API pre-checks**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-19T11:45:49Z
- **Completed:** 2026-02-19T11:47:43Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `ProjectInfo` dataclass (`project_id`, `compute_enabled`, `dns_enabled`) as the curated-project-list data structure for Phase 6 to consume
- Implemented `enumerate_gcp_projects()` covering all six ENUM requirements: auto-discovery (ENUM-01), zero-project error (ENUM-02), single-project bypass (ENUM-03), org scoping (ENUM-04), glob filtering (ENUM-05), and per-project API pre-checks (ENUM-06)
- Added both new GCP library dependencies to requirements.txt with correct minimum versions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add ProjectInfo dataclass, enumeration helpers, and enumerate_gcp_projects() to config.py** - `3e46d63` (feat)
2. **Task 2: Add google-cloud-resource-manager and google-cloud-service-usage to requirements.txt** - `fae8607` (chore)

## Files Created/Modified

- `gcp_discovery/config.py` — Added `ProjectInfo` dataclass, `_fetch_active_projects()`, `_apply_project_filters()`, `_check_apis_enabled()`, `_log_api_status()`, and `enumerate_gcp_projects()`; also added `fnmatch`, `dataclass`, and `Tuple` imports
- `requirements.txt` — Added `google-cloud-resource-manager>=1.12.0` and `google-cloud-service-usage>=1.3.0` in the GCP Dependencies section

## Decisions Made

- `enumerate_gcp_projects()` uses explicit keyword arguments rather than an `args` namespace — keeps the function testable without argparse coupling. The caller (discover.py, Phase 5 plan 2) extracts args fields and passes them individually.
- `_check_apis_enabled()` receives the `ServiceUsageClient` as a parameter (`client`) rather than creating one internally. A single client is constructed once in `enumerate_gcp_projects()` before the loop — avoids the per-project client construction anti-pattern flagged in the research doc.
- `PermissionDenied` from `_fetch_active_projects()` (on `search_projects` itself) is a fatal error — exits with message to enable `cloudresourcemanager.googleapis.com`. `PermissionDenied` inside `_check_apis_enabled()` (per-project pre-check) is non-fatal — returns `(False, False)` treating both APIs as unavailable.
- `_apply_project_filters()` uses `is not None` check rather than truthiness — an empty list `[]` for include_patterns means "include nothing" (filter everything out), which is different from `None` (no filter applied).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `enumerate_gcp_projects()` is fully implemented and ready for Phase 5 plan 2 (discover.py wiring and CLI args)
- Phase 5 plan 2 must: add `--project`, `--org-id`, `--include-projects`, `--exclude-projects` CLI flags; call `enumerate_gcp_projects()` with the right args; pass the resulting `List[ProjectInfo]` forward
- Phase 6 will iterate `ProjectInfo` objects and pass `project_info.project_id` to concurrent discovery workers

## Self-Check: PASSED

- gcp_discovery/config.py: EXISTS
- requirements.txt: EXISTS
- .planning/phases/05-gcp-project-enumeration/05-01-SUMMARY.md: EXISTS
- Commit 3e46d63 (Task 1): FOUND
- Commit fae8607 (Task 2): FOUND
- config.py syntax: CLEAN (ast.parse passed)
- google-cloud-resource-manager>=1.12.0 in requirements.txt: VERIFIED
- google-cloud-service-usage>=1.3.0 in requirements.txt: VERIFIED

---
*Phase: 05-gcp-project-enumeration*
*Completed: 2026-02-19*
