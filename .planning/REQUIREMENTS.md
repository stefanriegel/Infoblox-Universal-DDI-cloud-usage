# Requirements: Azure Large-Tenant Discovery Fix

**Defined:** 2026-02-18
**Core Value:** Every enabled Azure subscription must be scanned successfully — no subscription should silently fail due to credential or concurrency issues.

## v1 Requirements

Requirements for the bug fix release. Each maps to roadmap phases.

### Credential Chain

- [x] **CRED-01**: Credential chain uses classes with built-in MSAL token caching (no subprocess-based credentials under concurrent load)
- [x] **CRED-02**: ServicePrincipal authentication via `ClientSecretCredential` works as primary path when env vars are set
- [x] **CRED-03**: Interactive authentication via `InteractiveBrowserCredential` with `TokenCachePersistenceOptions` works as fallback when no service principal is configured
- [x] **CRED-04**: Credential singleton is warmed up (token acquired) before any worker threads are spawned
- [x] **CRED-05**: Credential fallback catches only typed exceptions (`CredentialUnavailableError`, `ClientAuthenticationError`), not bare `Exception`
- [x] **CRED-06**: Tool works correctly on Windows 11, macOS, and Linux (backward compatibility preserved)

### Concurrency

- [x] **CONC-01**: ARM 429 responses are retried using the `Retry-After` header value instead of fixed exponential backoff
- [x] **CONC-02**: Management clients (`ComputeManagementClient`, `NetworkManagementClient`, etc.) are explicitly closed after each subscription completes
- [x] **CONC-03**: Tool scans 500+ subscriptions without socket exhaustion or credential failures on Windows

### Code Correctness

- [x] **CODE-01**: Duplicate `get_all_subscription_ids()` calls in `discover.py` are eliminated (single call, result reused)
- [x] **CODE-02**: Checkpoint resume correctly filters already-completed subscriptions (second subscription listing no longer overwrites filtered list)
- [x] **CODE-03**: Existing checkpoint/resume functionality continues to work for interrupted large-tenant scans

### Observability

- [x] **OBSV-01**: Credential type selected at startup is logged (e.g., "Using ClientSecretCredential" or "Using InteractiveBrowserCredential")
- [x] **OBSV-02**: Warning printed when subscription count >200 and `--subscription-workers` >2
- [x] **OBSV-03**: Checkpoint TTL is configurable via `--checkpoint-ttl-hours` (default 48h)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Performance

- **PERF-01**: Azure Resource Graph integration for batch cross-subscription resource enumeration
- **PERF-02**: Proactive rate-limit throttling via `x-ms-ratelimit-remaining-subscription-reads` response header
- **PERF-03**: Adaptive worker count auto-tuning based on tenant size and credential type

### Platform

- **PLAT-01**: WAM broker integration (`InteractiveBrowserBrokerCredential`) for silent SSO on Windows 10+
- **PLAT-02**: Async/asyncio discovery mode using `azure.mgmt.*.aio` clients

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Adding new Azure resource types to discovery | Separate enhancement, not related to credential bug |
| Changing licensing calculation logic | Unrelated to the bug |
| AWS or GCP discovery changes | Different providers, unaffected |
| UI/CLI output format changes | Cosmetic, not the bug |
| Full async/asyncio rewrite | Massive scope; threading model is correct after credential fix |
| Azure Resource Graph replacement | Requires new dependency, parallel code paths for DNS types not in ARG; v2+ optimization |
| Per-subscription credential objects | Anti-pattern — defeats singleton caching, creates more subprocess calls |
| Mandatory service principal requirement | Breaks developer/SE workflow using `az login` |

## Traceability

Which phases cover which requirements. Confirmed during roadmap creation 2026-02-18.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CRED-01 | Phase 1 | Complete |
| CRED-02 | Phase 1 | Complete |
| CRED-03 | Phase 1 | Complete |
| CRED-04 | Phase 1 | Complete |
| CRED-05 | Phase 1 | Complete |
| CRED-06 | Phase 1 | Complete |
| CODE-01 | Phase 1 | Complete |
| CODE-02 | Phase 1 | Complete |
| CODE-03 | Phase 1 | Complete |
| CONC-01 | Phase 2 | Complete |
| CONC-02 | Phase 2 | Complete |
| CONC-03 | Phase 2 | Complete |
| OBSV-01 | Phase 3 | Complete |
| OBSV-02 | Phase 3 | Complete |
| OBSV-03 | Phase 3 | Complete |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0

---
*Requirements defined: 2026-02-18*
*Last updated: 2026-02-18 — traceability confirmed against ROADMAP.md*
