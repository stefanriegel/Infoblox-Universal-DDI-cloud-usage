# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-23)

**Core value:** Accurate, auditable UDDI token estimation from cloud discovery -- customers must trust the numbers and understand exactly how they were derived.
**Current focus:** Phase 2: AWS Provider and End-to-End Pipeline

## Current Position

Phase: 2 of 6 (AWS Provider and End-to-End Pipeline)
Plan: 2 of 6 in current phase
Status: In Progress
Last activity: 2026-02-23 -- Completed 02-02-PLAN.md (counting, categorization, token calculation TDD)

Progress: [██████░░░░] 25%

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: 4min
- Total execution time: 0.35 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-core-infrastructure | 4 | 15min | 4min |
| 02-aws-provider-and-end-to-end-pipeline | 2 | 10min | 5min |

**Recent Trend:**
- Last 5 plans: 01-03 (3min), 01-04 (4min), 02-01 (5min), 02-02 (5min)
- Trend: Stable

*Updated after each plan completion*
| Phase 02 P01 | 6min | 2 tasks | 9 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Phase 2 builds the full end-to-end pipeline (discovery -> counting -> tokens -> reports) with AWS as first provider, so Phases 3-4 only add provider-specific discovery
- [Roadmap]: Phase 1 addresses 4 of 6 critical pitfalls (auth expiry, exception masking, checkpoint corruption, signal handler state loss) before any cloud SDK code
- [01-01]: Used from __future__ import annotations for Python 3.10+ type hint syntax on Python 3.9 runtime
- [01-01]: Error classification uses strict priority ordering (AUTH > RATE_LIMIT > NETWORK > API > UNKNOWN) for deterministic resolution
- [01-01]: Audit logger clears existing handlers per setup call for per-scan file isolation
- [01-02]: Retry decorator delegates to classify_error() for category-based retry eligibility, not exception type matching
- [01-02]: RateLimiter uses exponential backoff (1s*2^n capped at 60s) when no Retry-After header present
- [01-02]: Checkpoint save uses fd-tracking with None sentinel to prevent double-close in error cleanup
- [01-02]: TTL=0 disables expiry check, allowing indefinite checkpoint validity for testing
- [01-03]: AuthResult.read_only defaults to True with no setter -- AUTH-05 enforced by design, not runtime checks
- [01-03]: ProgressTracker uses copy.deepcopy for get_summary() to prevent callers from mutating internal state
- [01-03]: register_provider accepts unit_label parameter so Azure uses 'subscriptions' and GCP uses 'projects'
- [01-04]: Orchestrator uses provider-scoped semaphores (not global) for independent per-provider concurrency control
- [01-04]: GracefulShutdown registers SIGINT/SIGTERM handlers in __init__ and uses threading.Lock for state updates
- [01-04]: CLI returns graceful message when no provider implementations exist (Phase 1 stub)
- [01-04]: select_providers() accepts both numbers (1,3) and names (aws,gcp) for user-friendly input
- [02-02]: Categorizer uses type-to-category mapping dicts (DDI_TYPES, TOKEN_FREE_TYPES) for clarity and easy extension
- [02-02]: IP counter uses ipaddress stdlib module for private/public classification and validation
- [02-02]: Per-VPC dedup key is (vpc_id_or_account_id, ip_address) tuple in a set for O(1) dedup
- [02-02]: Tag-based exclusion exempts DDI and token-free types (only managed assets can be excluded)
- [02-02]: Token ceiling division uses if count > 0 else 0 guard (not max(1, ...))
- [02-02]: calculate_account_tokens accepts optional deduplicated_ip_count for per-VPC dedup integration
- [Phase 02]: AWS Organizations API returns 'Id' not 'AccountId' -- code uses actual API field names
- [Phase 02]: Auth validator keeps account_count=1 fallback when Organizations returns 0 accounts
- [Phase 02]: SSOTokenLoadError handled via exception class name check since import path varies across botocore versions

### Pending Todos

None yet.

### Blockers/Concerns

- [Research]: Azure ARM tenant-level throttling behavior at 100-500 subscriptions needs pre-implementation research in Phase 3
- [Research]: GCP aggregatedList availability per resource type needs validation before Phase 4

## Session Continuity

Last session: 2026-02-23
Stopped at: Completed 02-02-PLAN.md (counting, categorization, token calculation TDD)
Resume file: None
