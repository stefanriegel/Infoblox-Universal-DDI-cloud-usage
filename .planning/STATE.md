# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Every cloud resource across all projects/subscriptions must be discovered reliably — no project or subscription should silently fail due to credential or concurrency issues.
**Current focus:** v1.1 GCP Multi-Project Discovery — Phase 4: GCP Credential Chain and Fail-Fast

## Current Position

Phase: 4 — GCP Credential Chain and Fail-Fast
Plan: —
Status: Not started
Last activity: 2026-02-19 — v1.1 roadmap created

```
v1.1 Progress: [          ] 0% (0/5 phases)
Phase 4: [ ] Phase 5: [ ] Phase 6: [ ] Phase 7: [ ] Phase 8: [ ]
```

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
All v1 decisions archived — see .planning/milestones/v1-ROADMAP.md for full history.

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

**Last session:** 2026-02-19T09:30:18.287Z
**Status:** v1.1 roadmap created. 25/25 requirements mapped across Phases 4-8. Ready to plan Phase 4.
