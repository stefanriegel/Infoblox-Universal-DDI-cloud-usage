# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Every cloud resource across all projects/subscriptions must be discovered reliably — no project or subscription should silently fail due to credential or concurrency issues.
**Current focus:** v1.1 GCP Multi-Project Discovery — Phase 4: GCP Credential Chain and Fail-Fast

## Current Position

Phase: 4 — GCP Credential Chain and Fail-Fast
Plan: 2 of 3
Status: In progress
Last activity: 2026-02-19 — Completed 04-02 credential singleton wiring in discover.py and gcp_discovery.py

```
v1.1 Progress: [          ] 0% (0/5 phases)
Phase 4: [ ] Phase 5: [ ] Phase 6: [ ] Phase 7: [ ] Phase 8: [ ]
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

**Last session:** 2026-02-19T09:59:00Z
**Stopped at:** Completed 04-02-PLAN.md
**Status:** Phase 4 Plan 02 complete. discover.py cleaned of gcloud subprocess calls; credential singleton warmed on main thread before workers; _init_gcp_clients() no longer wraps get_gcp_credential() in bare except. Requirements CRED-02, CRED-03, CRED-05 fulfilled. Ready for Plan 03.
