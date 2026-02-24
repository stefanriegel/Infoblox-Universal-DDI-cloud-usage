# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-23)

**Core value:** Accurate, auditable UDDI token estimation from cloud discovery -- customers must trust the numbers and understand exactly how they were derived.
**Current focus:** Phase 3: Azure Provider

## Current Position

Phase: 3 of 6 (Azure Provider)
Plan: 1 of 4 in current phase
Status: Executing
Last activity: 2026-02-24 -- Completed 03-01-PLAN.md (Azure provider foundation)

Progress: [█████████████] 54%

## Performance Metrics

**Velocity:**
- Total plans completed: 13
- Average duration: 7min
- Total execution time: 1.44 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-core-infrastructure | 4 | 15min | 4min |
| 02-aws-provider-and-end-to-end-pipeline | 6 | 51min | 9min |
| 02.1-wire-ratelimiter-into-discovery-pipeline | 2 | 17min | 9min |
| 03-azure-provider | 1 | 7min | 7min |

**Recent Trend:**
- Last 5 plans: 02-05 (5min), 02-06 (22min), 02.1-02 (8min), 02.1-01 (9min), 03-01 (7min)
- Trend: Stable execution times for focused integration and cleanup tasks

*Updated after each plan completion*
| Phase 02 P01 | 6min | 2 tasks | 9 files |
| Phase 02 P03 | 7min | 2 tasks | 5 files |
| Phase 02 P04 | 7min | 2 tasks | 4 files |
| Phase 02 P05 | 5min | 2 tasks | 6 files |
| Phase 02 P06 | 22min | 3 tasks | 7 files (+15 deleted) |
| Phase 02.1 P02 | 8min | 1 task | 2 files |
| Phase 02.1 P01 | 9min | 2 tasks | 6 files |
| Phase 03 P01 | 7min | 2 tasks | 10 files |

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
- [02-03]: Route53 collectors set region="global" and omit region parameter since Route53 is account-global
- [02-03]: All ENIs collected regardless of attachment status -- asset_dedup module handles folding
- [02-03]: DHCP orphan detection uses set membership check against VPC-extracted DhcpOptionsId values
- [02-03]: Record resource_id format is zone_id/name/type for uniqueness across zones
- [02-04]: ECS tests use manual mocks due to moto 5.1.21 awsvpc bug (private_dns_name missing on NetworkInterface)
- [02-04]: RDS instances set ip_addresses=[] -- ENI discovery handles IP attribution
- [02-04]: Lambda VPC test checks non-empty vpc_id (moto returns synthetic vpc-123abc)
- [02-04]: Redshift uses ClusterNamespaceArn as resource_id when available
- [02-05]: xlsxwriter for write-only XLS generation (rich formatting, no read overhead); openpyxl only in tests
- [02-05]: .gitignore output/ exclusion scoped to root /output/ so src/cloud_usage/output/ is trackable
- [02-05]: Proof manifest uses two-phase hashing: resource_hash from sorted resource tuples, then manifest_hash over all fields
- [02-06]: Route53 and S3 collected once per account (global services), all other collectors run per-region
- [02-06]: Categorizer respects prior pipeline exclusions: resources with counted=False and skip_reason are not re-categorized
- [02-06]: Asset dedup and managed service exclusion check counted is False (explicit), not falsy None, to process uncategorized resources
- [02-06]: Legacy code (aws_discovery/, shared/, main.py) deleted after integration tests confirm Phase 2 works
- [02.1-02]: Removed import ipaddress from ip_counter.py -- only needed by deleted count_ips(), not by deduplicate_ips_per_vpc()
- [02.1-02]: Updated ip_counter module docstring to reflect per-VPC deduplication scope only (removed "IP extraction" reference)
- [02.1-01]: Thread-local _retry_context for runtime on_retry injection (zero changes to 20+ collector decorators)
- [02.1-01]: classify_error() called twice per retry (once in decorator, once in callback) -- acceptable for pure string matching
- [02.1-01]: Non-rate-limit transient errors (network, 503) do NOT affect RateLimiter state
- [02.1-01]: Dispatch loop refactored from dict comprehension to sequential for-loop for delay injection
- [03-01]: Auth validator uses exception class name matching for Azure SDK exceptions since SDK may not be installed
- [03-01]: Client factory uses _try_create wrapper so missing optional SDK packages set client to None
- [03-01]: _extract_resource_group uses case-insensitive segment matching per Azure ARM behavior
- [03-01]: Subscription filtering uses case-insensitive matching for display names
- [03-01]: PostgreSQL uses PostgreSQLFlexibleManagementClient (flexible servers API, not legacy single server)

### Pending Todos

None yet.

### Blockers/Concerns

- [Research]: Azure ARM tenant-level throttling behavior at 100-500 subscriptions needs pre-implementation research in Phase 3
- [Research]: GCP aggregatedList availability per resource type needs validation before Phase 4

## Session Continuity

Last session: 2026-02-24
Stopped at: Completed 03-01-PLAN.md (Azure provider foundation)
Resume file: None
