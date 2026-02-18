# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-18)

**Core value:** Every enabled Azure subscription must be scanned successfully — no subscription should silently fail due to credential or concurrency issues.
**Current focus:** Phase 1 — Credential Chain and Code Correctness

## Current Position

**Current Phase:** 03
**Current Phase Name:** Observability and UX Polish
**Total Phases:** 3
**Current Plan:** 1
**Total Plans in Phase:** 1
**Status:** In progress
**Progress:** [██████████] 100%
**Last Activity:** 2026-02-18
**Last Activity Description:** Phase 03 Plan 01 complete — credential path logging, checkpoint TTL, and large-tenant warning

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 4.3 min
- Total execution time: 0.2 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-credential-chain-and-code-correctness | 1/2 | 4 min | 4 min |
| 02-concurrent-execution-hardening | 2/2 | 13 min | 6.5 min |
| 03-observability-and-ux-polish | 1/1 | 1 min | 1 min |

**Recent Trend:**
- Last 5 plans: 01-01 (4 min), 02-01 (12 min), 02-02 (1 min), 03-01 (1 min)
- Trend: -

*Updated after each plan completion*
| Phase 01 P01 | 4 | 2 tasks | 2 files |
| Phase 01 P02 | 2 | 2 tasks | 1 files |
| Phase 01 P03 | 1 | 1 tasks | 1 files |
| Phase 02-concurrent-execution-hardening P01 | 12 | 1 tasks | 1 files |
| Phase 02-concurrent-execution-hardening P02 | 1 | 1 tasks | 1 files |
| Phase 03-observability-and-ux-polish P01 | 1 | 2 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-phase]: Replace SharedTokenCacheCredential + AzureCliCredential with ClientSecretCredential + InteractiveBrowserCredential (TokenCachePersistenceOptions) — eliminates subprocess storm root cause
- [Pre-phase]: Catch only CredentialUnavailableError and ClientAuthenticationError in fallback chain — bare Exception swallow masks SDK bug #24032
- [Pre-phase]: Warm credential singleton on main thread before spawning workers — InteractiveBrowserCredential must never be called from a worker thread (raises ClientAuthenticationError in headless context since azure-identity 1.13.0)
- [01-01]: Partial env var handling: warn and fall through to interactive rather than hard fail — allows scan to proceed interactively with actionable warning
- [01-01]: ClientAuthenticationError from InteractiveBrowserCredential at startup raises SystemExit("Authentication timed out. Run again to retry.") — at startup any auth error is treated as timeout
- [01-01]: TokenCachePersistenceOptions construction wrapped in bare except Exception for Linux libsecret compatibility — falls back to allow_unencrypted_storage=True
- [Phase 01]: Removed SharedTokenCacheCredential + AzureCliCredential; replaced with ClientSecretCredential + InteractiveBrowserCredential/DeviceCodeCredential (TokenCachePersistenceOptions) in config.py — eliminates subprocess storm root cause
- [Phase 01]: Caught only typed exceptions (CredentialUnavailableError, ClientAuthenticationError) in _build_credential; bare Exception swallow removed from validate_azure_credentials() (re-raises after logging)
- [Phase 01]: Deleted second get_all_subscription_ids() call and second checkpoint resume block that silently overwrote filtered all_subs — checkpoint resume was effectively broken
- [Phase 01]: Per-subscription checkpoint saves replace periodic should_save_checkpoint() guard — minimizes progress loss on crash
- [Phase 01]: all_subs_total captures full subscription list before checkpoint filtering — checkpoint saves use captured list, not fresh API call
- [Phase 01]: Expired checkpoint message: 'Checkpoint expired (48h TTL). Starting fresh scan.' per user decision
- [Phase 01]: Corrupted checkpoint: typed catches print warning with error detail, always continue scan per user decision
- [Phase 01]: Use print() not logger.error() in validate_azure_credentials() unexpected-exception branch — file uses no logging module; consistent with all other error paths
- [Phase 01]: Remove --checkpoint-interval argparse argument entirely — dead code since 01-02 switched to per-subscription saves
- [Phase 02-concurrent-execution-hardening]: Subclass RetryPolicy (override sleep()) rather than use per_retry_policies kwarg — cross-version stable, retry_policy= kwarg is universally supported
- [Phase 02-concurrent-execution-hardening]: AzureDiscovery accepts all-or-nothing pre-built clients — partial provision falls through to _init_azure_clients() for backward compat
- [Phase 02-concurrent-execution-hardening]: make_retry_policy() explicitly sets retry_total=3 to override SDK default of 10 — prevents 10-minute worker thread blocking on heavy throttle
- [02-02]: Credential singleton obtained once before ThreadPoolExecutor block — InteractiveBrowserCredential must not be called from worker threads
- [02-02]: errors list uses dict format {sub_id, error}; both dict and legacy string formats handled in summary/file output for checkpoint backward compat
- [02-02]: Dummy AzureDiscovery at end of main() uses all_subs_total[0] not all_subs[0] — all_subs may be empty when all subscriptions were resumed from checkpoint
- [03-01]: [Auth] Using InteractiveBrowserCredential prints before browser popup; [Auth] Using DeviceCodeCredential prints before device code prompt — immediate feedback before blocking
- [03-01]: ttl_hours > 0 short-circuit in load_checkpoint() means 0 = never expire (no time comparison at all)
- [03-01]: Warning uses all_subs_total (full pre-checkpoint list) to reflect true tenant scale, not remaining subs after resume
- [03-01]: Warning is non-blocking (print and continue) — no user prompt, no sleep
- [03-01]: Removed stale --checkpoint-interval flag and azure_args.checkpoint_interval forwarding from main.py (dead code since Phase 01)

### Pending Todos

None.

### Blockers/Concerns

- [Research gap]: Verify all 5 management client types (Compute, Network, Resource, Dns, PrivateDns) expose close() before implementing Phase 2
- [Research gap]: Confirm parent_window_handle=0 behavior on Windows console (no GUI window) before finalizing WAM path in Phase 1
- [Research gap]: Verify current ARM throttle limits at learn.microsoft.com before Phase 2 implementation (figures from docs updated 2025-05-28, historically have changed)

## Session Continuity

**Last session:** 2026-02-18T22:05:07Z
**Paused At:** Completed Phase 03-observability-and-ux-polish Plan 01 (03-01-PLAN.md)
Resume file: .planning/phases/03-observability-and-ux-polish/03-01-SUMMARY.md
