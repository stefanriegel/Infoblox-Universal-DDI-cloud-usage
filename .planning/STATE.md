# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Every cloud resource across all projects/subscriptions must be discovered reliably — no project or subscription should silently fail due to credential or concurrency issues.
**Current focus:** v1.1 GCP Multi-Project Discovery — Phase 5: GCP Project Enumeration

## Current Position

Phase: 5 — GCP Project Enumeration
Plan: 1 of 2 complete
Status: In progress
Last activity: 2026-02-19 — Plan 05-01 complete (ProjectInfo dataclass + enumerate_gcp_projects())

```
v1.1 Progress: [██        ] 20% (1/5 phases)
Phase 4: [x] Phase 5: [ ] Phase 6: [ ] Phase 7: [ ] Phase 8: [ ]
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

### Architecture Notes (from research)

- `get_gcp_credential()` in `config.py` — singleton with threading.Lock, `credentials.refresh()` warm-up, fail-fast on `RefreshError` / `DefaultCredentialsError`
- GCP Compute clients are project-agnostic — pass `project=project_id` per API call, not at construction. Only `dns.Client` requires per-project instantiation.
- Retry via `google.api_core.retry.Retry` (not a subclass like Azure's RetryPolicy) — applied per API call site as module-level `_GCP_RETRY` singleton
- GCP quota errors are 403 `rateLimitExceeded`, not HTTP 429 — Azure retry logic would silently miss these
- `dns.Client` pinned at `==0.35.1` — incompatible with google-cloud-dns >= 1.0.0 GAPIC interface

### Research Flags (resolve during planning)

- **Phase 6**: Verify whether `dns.Client` at 0.35.1 exposes `.transport.close()` or relies on GC for gRPC cleanup
- **Phase 6**: Confirm `resource_id` deduplication strategy in `ResourceCounter` — does it deduplicate by content hash or string? If by string, `project_id` must be added to `resource_id` format
- **Phase 6**: Shared VPC subnet deduplication — subnets appear only in host project; verify dedup logic at collection time vs counter layer
- **Phase 7**: Verify exact Python exception field path for `rateLimitExceeded` reason in `google.api_core.exceptions.PermissionDenied` (`e.reason` vs `e.errors[0].get('reason')`) before writing retry predicate

### Pending Todos

None.

### Blockers/Concerns

None.

## Session Continuity

**Last session:** 2026-02-19T11:47:43Z
**Stopped at:** Completed 05-01-PLAN.md
