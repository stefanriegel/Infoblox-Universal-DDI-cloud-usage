---
phase: 01-core-infrastructure
plan: 04
subsystem: infra
tags: [orchestrator, concurrency, semaphore, cli, argparse, signal-handler, threading, python-stdlib]

# Dependency graph
requires:
  - phase: 01-core-infrastructure/01
    provides: "CloudResource dataclass, ErrorRecord, create_error_record() for worker error handling"
  - phase: 01-core-infrastructure/02
    provides: "CheckpointEngine, CheckpointData, ProviderProgress for scan state persistence; RateLimiter for throttle tracking"
  - phase: 01-core-infrastructure/03
    provides: "AuthDoctor for pre-flight validation; ProgressTracker for counter-line display"
provides:
  - "DiscoveryOrchestrator concurrent dispatcher with provider-scoped semaphores (AWS=10, Azure=4, GCP=8)"
  - "DiscoveryProvider ABC defining list_accounts/discover_account interface for Phases 2-4"
  - "GracefulShutdown signal handler saving checkpoint on SIGINT/SIGTERM"
  - "CLI entry point with interactive provider selection and --aws/--azure/--gcp flags"
  - "Full scan lifecycle: auth doctor -> checkpoint detection -> orchestrator -> summary"
affects: [02-aws-provider, 03-azure-provider, 04-gcp-provider]

# Tech tracking
tech-stack:
  added: []
  patterns: [provider-scoped-semaphores, threadpool-with-as-completed, signal-handler-checkpoint, interactive-cli-prompt, argparse-flags]

key-files:
  created:
    - src/cloud_usage/discovery/orchestrator.py
    - src/cloud_usage/discovery/provider.py
    - src/cloud_usage/discovery/shutdown.py
    - src/cloud_usage/cli.py
    - tests/test_orchestrator.py
    - tests/test_cli.py
  modified: []

key-decisions:
  - "Orchestrator uses provider-scoped semaphores (not global) for independent per-provider concurrency control"
  - "GracefulShutdown registers SIGINT/SIGTERM handlers in __init__ and uses threading.Lock for state updates"
  - "CLI returns graceful message when no provider implementations exist (Phase 1 stub)"
  - "select_providers() accepts both numbers (1,3) and names (aws,gcp) for user-friendly input"

patterns-established:
  - "Provider-scoped semaphores: dict[str, threading.Semaphore] keyed by provider_name for independent concurrency limits"
  - "Error isolation via try/except per worker in _discover_account -- exceptions converted to ErrorRecord, not propagated"
  - "Signal handler state update pattern: orchestrator calls shutdown_handler.update_state() after each account"
  - "CLI dual-mode: interactive prompt (no flags) vs scripted mode (--aws/--azure/--gcp flags)"

requirements-completed: [DISC-04, DISC-06]

# Metrics
duration: 4min
completed: 2026-02-23
---

# Phase 1 Plan 04: Integration Layer Summary

**Concurrent discovery orchestrator with provider-scoped semaphores, SIGINT/SIGTERM checkpoint saving, and interactive CLI entry point with auth doctor + checkpoint resume integration**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-23T16:43:02Z
- **Completed:** 2026-02-23T16:47:10Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- DiscoveryOrchestrator dispatching concurrent work via ThreadPoolExecutor with per-provider semaphores (AWS=10, Azure=4, GCP=8 defaults) and complete error isolation (DISC-06)
- DiscoveryProvider ABC defining the interface (provider_name, list_accounts, discover_account) that cloud providers implement in Phases 2-4
- GracefulShutdown handler capturing SIGINT/SIGTERM and saving checkpoint state before exit (130 exit code)
- CLI with interactive provider selection prompt accepting numbers or names, plus --aws/--azure/--gcp flags for scripted use
- Full scan lifecycle in main(): parse args -> select providers -> audit logger -> auth doctor -> checkpoint detection -> orchestrator -> summary
- 49 tests total (19 orchestrator + 30 CLI) -- all passing
- 214 total Phase 1 tests all passing with zero third-party imports

## Task Commits

Each task was committed atomically:

1. **Task 1: Create discovery orchestrator with provider-scoped semaphores and error isolation** - `06a4635` (feat)
2. **Task 2: Create CLI entry point with interactive provider selection and scan orchestration** - `fed87ff` (feat)

## Files Created/Modified
- `src/cloud_usage/discovery/orchestrator.py` - DiscoveryOrchestrator with ThreadPoolExecutor, provider semaphores, checkpoint/progress integration
- `src/cloud_usage/discovery/provider.py` - DiscoveryProvider ABC with provider_name, list_accounts, discover_account
- `src/cloud_usage/discovery/shutdown.py` - GracefulShutdown with SIGINT/SIGTERM handlers and checkpoint save
- `src/cloud_usage/cli.py` - CLI entry point with parse_args, select_providers, main lifecycle
- `tests/test_orchestrator.py` - 19 tests: basic execution, error isolation, semaphores, checkpoint, progress, shutdown
- `tests/test_cli.py` - 30 tests: argument parsing, interactive selection, main function paths

## Decisions Made
- Orchestrator uses provider-scoped semaphores (one Semaphore per provider) rather than a global semaphore, allowing independent concurrency control per provider. This matches the Research recommendation for different API rate characteristics across AWS/Azure/GCP.
- GracefulShutdown registers signal handlers immediately in __init__ and uses a threading.Lock to protect state updates, ensuring the handler always has access to the most recent scan progress even when called from a signal context.
- CLI returns exit code 0 with a message "No discovery providers configured" in Phase 1 since no concrete DiscoveryProvider implementations exist yet. The _get_discovery_providers() stub will be populated in Phases 2-4.
- select_providers() accepts both numeric (1,2,3) and name-based (aws,azure,gcp) input for the interactive prompt, matching the CONTEXT.md requirement that "the tool should feel guided, not require CLI expertise."

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- DiscoveryProvider ABC ready for concrete implementations: AWSDiscoveryProvider (Phase 2), AzureDiscoveryProvider (Phase 3), GCPDiscoveryProvider (Phase 4)
- DiscoveryOrchestrator ready to dispatch real cloud discovery work once providers are implemented
- CLI ready for end-to-end scans -- _get_discovery_providers() is the only stub to populate
- All Phase 1 infrastructure complete: error taxonomy, retry/rate-limiter, checkpoint engine, auth doctor, progress tracker, orchestrator, CLI
- Phase 1 success criteria fully met: pre-flight auth validation, concurrent orchestrator with semaphores, adaptive rate limiter, atomic checkpoint with TTL, pure Python with zero third-party dependencies

## Self-Check: PASSED

- All 6 created files verified present on disk
- Commit 06a4635 (Task 1) verified in git log
- Commit fed87ff (Task 2) verified in git log
- All 49 plan tests pass (19 orchestrator + 30 CLI)
- All 214 Phase 1 tests pass
- Zero third-party imports in source code confirmed

---
*Phase: 01-core-infrastructure*
*Completed: 2026-02-23*
