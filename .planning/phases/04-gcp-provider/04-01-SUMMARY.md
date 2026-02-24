---
phase: 04-gcp-provider
plan: 01
subsystem: auth, discovery
tags: [gcp, google-auth, google-cloud-resource-manager, google-cloud-compute, google-cloud-container, ADC]

# Dependency graph
requires:
  - phase: 01-core-infrastructure
    provides: AuthValidator ABC, DiscoveryProvider ABC, CloudResource schema, CLI entry point, AuthDoctor, DiscoveryOrchestrator
  - phase: 02-aws-provider-and-end-to-end-pipeline
    provides: Pattern reference for auth validator, discovery provider, CLI integration, _safe_collect
  - phase: 03-azure-provider
    provides: Pattern reference for Azure auth validator, client factory _try_create, subscription enumeration
provides:
  - GCPAuthValidator implementing AuthValidator ABC with ADC credential validation and contextual error suggestions
  - Project enumeration with single-project, org-scoped, and glob-filtered multi-project modes
  - Per-project API pre-checks for Compute, DNS, Cloud SQL Admin, and GKE Container APIs
  - GCPClients dataclass wrapping 11 shared SDK clients with graceful missing-package handling
  - GCPDiscoveryProvider implementing DiscoveryProvider ABC with project filtering and checkpoint support
  - _safe_collect with GCP-specific error detection (PermissionDenied, TooManyRequests, API disabled)
  - CLI --gcp, --project, --org-id, --include-projects, --exclude-projects flags
affects: [04-02, 04-03, 04-04]

# Tech tracking
tech-stack:
  added: [google-cloud-container, google-api-python-client]
  patterns: [ADC chain via google.auth.default(), search_projects for org-wide enumeration, ServiceUsageClient.batch_get_services for API pre-checks, per-project DNS client creation, _try_create wrapper for graceful SDK fallback]

key-files:
  created:
    - src/cloud_usage/providers/gcp/__init__.py
    - src/cloud_usage/providers/gcp/auth.py
    - src/cloud_usage/providers/gcp/projects.py
    - src/cloud_usage/providers/gcp/client_factory.py
    - src/cloud_usage/providers/gcp/provider.py
    - src/cloud_usage/providers/gcp/collectors/__init__.py
    - tests/test_gcp_auth.py
    - tests/test_gcp_provider.py
  modified:
    - src/cloud_usage/cli.py
    - requirements.txt

key-decisions:
  - "Auth validator uses exception class name matching (type(exc).__name__) for DefaultCredentialsError/RefreshError since GCP SDK may not be installed"
  - "Client factory uses _try_create wrapper with per-client try/except so missing optional SDK packages set that client to None"
  - "DNS client NOT shared across projects -- created per-project in discover_account() per Pitfall 1 (dns.Client requires project= at init)"
  - "Include/exclude glob filtering uses fnmatch.fnmatch -- include takes precedence, exclude only applied when no include"
  - "API pre-checks use batch_get_services for 4 APIs (compute, dns, sqladmin, container) -- PermissionDenied treats all as unavailable, transient errors assume enabled"
  - "GCPClients wraps 11 clients (9 compute, 1 container, 1 sqladmin) -- all project-agnostic"

patterns-established:
  - "GCP auth validation: google.auth.default() + credentials.refresh(Request()) for warm-up, search_projects for project counting"
  - "GCP project filtering: include takes precedence over exclude, uses fnmatch glob matching"
  - "_safe_collect GCP variant: detects PermissionDenied, Forbidden, TooManyRequests, API disabled ('has not been used' / 'is not enabled')"
  - "unittest.mock for GCP testing: mock SDK via patch.dict sys.modules with google/google.cloud parent modules"

requirements-completed: [AUTH-03, DISC-03]

# Metrics
duration: 11min
completed: 2026-02-24
---

# Phase 4 Plan 01: GCP Provider Foundation Summary

**GCPAuthValidator with ADC credentials, project enumeration with org-scoping and glob filtering, 11-client factory, GCPDiscoveryProvider skeleton with GCP-specific _safe_collect, and CLI --gcp flag integration**

## Performance

- **Duration:** 11 min
- **Started:** 2026-02-24T19:13:31Z
- **Completed:** 2026-02-24T19:24:58Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- GCPAuthValidator validates ADC credentials via google.auth.default() with contextual error suggestions for DefaultCredentialsError, RefreshError, SDK not installed, and generic failures
- Project enumeration supports single-project mode (--project flag, GOOGLE_CLOUD_PROJECT env, ADC project), org-scoped multi-project (--org-id), and glob-filtered modes (--include-projects, --exclude-projects)
- Per-project API pre-checks for Compute, DNS, Cloud SQL Admin, and GKE Container APIs using ServiceUsageClient.batch_get_services()
- GCPClients wraps 11 shared SDK clients (9 compute, 1 container, 1 sqladmin) with graceful missing-package handling
- GCPDiscoveryProvider implements DiscoveryProvider ABC with project filtering, checkpoint support, and per-project DNS client creation
- _safe_collect handles GCP-specific errors: PermissionDenied, Forbidden, TooManyRequests/429, API disabled, and generic errors
- CLI gains --project, --org-id, --include-projects, --exclude-projects flags
- 74 unit tests with unittest.mock covering all paths (no live GCP credentials needed)
- All 727 tests pass (74 new + 653 existing, zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: GCP auth validator, project enumeration, and client factory** - `c918948` (feat)
2. **Task 2: GCP discovery provider skeleton and CLI integration** - `a0e25aa` (feat)

## Files Created/Modified
- `src/cloud_usage/providers/gcp/__init__.py` - GCP provider package init with module docstring
- `src/cloud_usage/providers/gcp/auth.py` - GCPAuthValidator implementing AuthValidator ABC
- `src/cloud_usage/providers/gcp/projects.py` - Project enumeration with filtering, org-scoping, API pre-checks
- `src/cloud_usage/providers/gcp/client_factory.py` - GCPClients dataclass and create_shared_clients factory
- `src/cloud_usage/providers/gcp/provider.py` - GCPDiscoveryProvider implementing DiscoveryProvider ABC
- `src/cloud_usage/providers/gcp/collectors/__init__.py` - Collectors subpackage marker
- `src/cloud_usage/cli.py` - Updated with GCP auth validator, discovery provider, and project filter args
- `requirements.txt` - Added google-cloud-container and google-api-python-client dependencies
- `tests/test_gcp_auth.py` - 35 tests for auth, enumeration, filtering, API pre-checks, client factory
- `tests/test_gcp_provider.py` - 39 tests for provider, filtering, checkpoint, _safe_collect, CLI

## Decisions Made
- Auth validator uses exception class name matching (`type(exc).__name__`) for GCP SDK exceptions since the SDK may not be installed on all systems (consistent with Azure pattern)
- Client factory wraps each client creation in individual try/except via `_try_create` so a missing optional SDK package sets that client to None rather than failing the whole factory
- DNS client is NOT included in GCPClients because `google.cloud.dns.Client` requires `project=` at construction time (Pitfall 1 from RESEARCH.md). DNS clients are created per-project inside `discover_account()`
- Project filtering uses `fnmatch.fnmatch()` for glob matching -- include takes precedence over exclude (if include provided, exclude is ignored)
- API pre-checks use `batch_get_services()` for 4 APIs (compute, dns, sqladmin, container) in a single call -- PermissionDenied treats all as unavailable, transient errors assume enabled
- Google SDK logging suppressed at module level: `logging.getLogger("google").setLevel(logging.ERROR)`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None - all modules created and tests pass. Test fixes needed for sys.modules mocking to include parent google/google.cloud modules (standard pattern for testing without GCP SDK installed).

## User Setup Required
None - no external service configuration required. GCP SDK packages added to requirements.txt but are not needed until actual GCP credentials are used.

## Next Phase Readiness
- GCP provider foundation complete, ready for resource collectors (Plans 02-04)
- GCPDiscoveryProvider.discover_account() is a skeleton returning empty list -- Plans 02-04 will wire collectors
- GCPClients provides all 11 shared SDK clients needed by Plans 02-04 collectors
- CLI integration complete: --gcp flag creates and uses the real GCPDiscoveryProvider
- Auth doctor validates GCP credentials before scan starts
- _safe_collect handles GCP-specific errors for all future collectors
- Per-project DNS client creation pattern established in discover_account()

## Self-Check: PASSED

All 10 files verified present. Both task commits (c918948, a0e25aa) verified in git log. All 727 tests pass (74 new + 653 existing).

---
*Phase: 04-gcp-provider*
*Completed: 2026-02-24*
