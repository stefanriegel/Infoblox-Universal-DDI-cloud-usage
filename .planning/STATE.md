# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Every cloud resource across all projects/subscriptions must be discovered reliably — no project or subscription should silently fail due to credential or concurrency issues.
**Current focus:** v1.1 GCP Multi-Project Discovery — Phase 6: Concurrent Multi-Project Execution

## Current Position

Phase: 6 — Concurrent Multi-Project Execution
Plan: 1 of 2 complete
Status: In progress
Last activity: 2026-02-19 — Plan 06-01 complete (shared_compute_clients injection into GCPDiscovery.__init__)

```
v1.1 Progress: [███       ] 30% (1.5/5 phases — Phase 6 in progress)
Phase 4: [x] Phase 5: [x] Phase 6: [ ] Phase 7: [ ] Phase 8: [ ]
```

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
All v1 decisions archived — see .planning/milestones/v1-ROADMAP.md for full history.

**04-01 (GCP credential singleton):**
- `except Exception` in `_check_gcp_compute_permission()` is acceptable — not in the credential chain; only PermissionDenied/Forbidden trigger sys.exit(1)
- `google.oauth2.credentials.Credentials` covers both ADC user creds and gcloud auth login (same Python class); logged as "Application Default Credentials"
- `get_all_gcp_regions()` bare `except Exception` retained — it is a discovery fallback for API availability, not an auth error handler
- compute_v1 and api_exceptions imports deferred inside `_check_gcp_compute_permission()` to avoid circular imports

**04-02 (discover.py cleanup / singleton wiring):**
- Credential validation before banner: `get_gcp_credential()` called as first statement in `main()` so auth failures never produce misleading discovery output
- `GCPConfig(project_id=project)` receives ADC project — ensures discovery works without `GOOGLE_CLOUD_PROJECT` env var; `_get_default_project_id()` fallback handles `None`
- `RuntimeError` with `from e` for client construction failures (not bare `Exception`) — preserves exception chain and is more specific

**05-01 (GCP project enumeration — core logic):**
- `enumerate_gcp_projects()` takes explicit keyword args (not args namespace) for testability — no argparse coupling in the core function
- `ServiceUsageClient` created once in `enumerate_gcp_projects()` and passed to `_check_apis_enabled(client, project_id)` — avoids per-project client construction anti-pattern
- `PermissionDenied` from `search_projects` itself (fatal) vs from `batch_get_services` per-project (non-fatal, returns `(False, False)`) — different handling for enumeration error vs API-not-enabled
- `_apply_project_filters()` uses `is not None` check — empty list `[]` means "include nothing", `None` means "no filter applied"
- Count printed before pre-check loop; `[Skip]` lines appear beneath it — per locked decision

**05-02 (GCP project enumeration — CLI wiring):**
- `enumerate_gcp_projects()` called before banner in `discover.py:main()` — enumeration may sys.exit on zero projects (ENUM-02), so it must precede any output
- `org_id` resolved in `discover.py` via `getattr(args, 'org_id', None) or os.getenv('GOOGLE_CLOUD_ORG_ID')` — env var fallback lives at the call site, not inside `config.py`
- Phase 5 uses `projects[0].project_id` for backward-compatible single-project discovery — Phase 6 will iterate the full list
- `scanned_projects = [p.project_id for p in projects]` ensures proof manifest reflects all enumerated projects even in Phase 5 single-scan mode

**06-01 (shared compute client injection):**
- `Optional[dict]` used instead of `dict | None` for Python 3.9 compatibility
- `self.project_id = config.project_id or project` — falls back to ADC project if config has no explicit project_id, matching merge logic in `_init_gcp_clients()`
- `from google.cloud import dns` placed as deferred import inside shared-clients branch only
- `_build_zones_by_region()` called in shared-clients branch (uses `self.zones_client` now assigned from dict)

### Architecture Notes (from research)

- `get_gcp_credential()` in `config.py` — singleton with threading.Lock, `credentials.refresh()` warm-up, fail-fast on `RefreshError` / `DefaultCredentialsError`
- GCP Compute clients are project-agnostic — pass `project=project_id` per API call, not at construction. Only `dns.Client` requires per-project instantiation.
- Retry via `google.api_core.retry.Retry` (not a subclass like Azure's RetryPolicy) — applied per API call site as module-level `_GCP_RETRY` singleton
- GCP quota errors are 403 `rateLimitExceeded`, not HTTP 429 — Azure retry logic would silently miss these
- `dns.Client` pinned at `==0.35.1` — incompatible with google-cloud-dns >= 1.0.0 GAPIC interface

### Research Flags (resolve during planning)

- **Phase 6**: ~~Verify whether `dns.Client` at 0.35.1 exposes `.transport.close()` or relies on GC for gRPC cleanup~~ RESOLVED: No close() at 0.35.1; HTTP REST transport; GC handles cleanup
- **Phase 6**: ~~Confirm `resource_id` deduplication strategy in `ResourceCounter`~~ RESOLVED: Dedup by (ip_space, ip) pairs, not resource_id string; project_id prefix needed for proof manifest uniqueness
- **Phase 6**: ~~Shared VPC subnet deduplication~~ RESOLVED: API returns only project-native subnets; no cross-project dedup needed
- **Phase 7**: Verify exact Python exception field path for `rateLimitExceeded` reason in `google.api_core.exceptions.PermissionDenied` (`e.reason` vs `e.errors[0].get('reason')`) before writing retry predicate

### Pending Todos

None.

### Blockers/Concerns

None.

## Session Continuity

**Last session:** 2026-02-19T13:27:22Z
**Stopped at:** Completed 06-01-PLAN.md (shared_compute_clients injection into GCPDiscovery)
