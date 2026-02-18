# Roadmap: Azure Large-Tenant Discovery Fix

## Overview

Three phases fix the 500+ subscription scanning failure on Windows. Phase 1 replaces the broken credential chain with classes that cache tokens in-process, eliminating the subprocess storm that crashes Azure CLI under concurrent load — this is the root cause fix. Phase 2 hardens the runtime against ARM throttling and socket exhaustion, the next failure modes that surface at scale after credentials work. Phase 3 adds observability and configurability so operations teams can diagnose and tune large-tenant scans without guessing.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Credential Chain and Code Correctness** - Replace subprocess-based credentials with MSAL-caching classes and fix two silent correctness bugs in discover.py
- [x] **Phase 2: Concurrent Execution Hardening** - Add Retry-After-aware backoff and management client lifecycle management to sustain 500+ subscription scans without throttle crashes or socket exhaustion
- [ ] **Phase 3: Observability and UX Polish** - Log credential selection, warn on high worker counts, and expose checkpoint TTL as a CLI flag

## Phase Details

### Phase 1: Credential Chain and Code Correctness
**Goal**: Tool authenticates reliably under concurrent load on Windows — every worker shares a warm, in-process token cache instead of spawning subprocess calls
**Depends on**: Nothing (first phase)
**Requirements**: CRED-01, CRED-02, CRED-03, CRED-04, CRED-05, CRED-06, CODE-01, CODE-02, CODE-03
**Success Criteria** (what must be TRUE):
  1. A user with 500+ subscriptions on Windows 11 using `az login` completes a full scan without CredentialUnavailableError failures
  2. A user with a service principal (env vars set) authenticates via ClientSecretCredential without being prompted interactively
  3. A user without a service principal is prompted once in the browser at startup, then all workers proceed without additional prompts or subprocess calls
  4. A scan interrupted midway and resumed with --checkpoint skips already-completed subscriptions (does not restart from the beginning)
  5. Credential errors surface as typed exceptions with specific messages, not bare Exception swallows
**Plans:** 3 plans (2 complete, 1 gap closure)
- [x] 01-01-PLAN.md -- Replace credential chain with MSAL-caching classes (ClientSecretCredential + InteractiveBrowserCredential/DeviceCodeCredential)
- [x] 01-02-PLAN.md -- Fix duplicate subscription/checkpoint blocks and improve checkpoint handling
- [ ] 01-03-PLAN.md -- Gap closure: fix undefined logger reference and remove stale checkpoint-interval references

### Phase 2: Concurrent Execution Hardening
**Goal**: Tool sustains multi-hundred subscription scans without crashing from ARM 429 responses or OS socket exhaustion
**Depends on**: Phase 1
**Requirements**: CONC-01, CONC-02, CONC-03
**Success Criteria** (what must be TRUE):
  1. A scan hitting ARM rate limits backs off for exactly the duration specified in the Retry-After header (not a fixed 1-4 second guess)
  2. A 500+ subscription scan on Windows completes without OSError socket exhaustion errors
  3. Management clients are released after each subscription so memory and socket usage remain bounded regardless of tenant size
**Plans:** 2 plans
- [x] 02-01-PLAN.md -- Add VisibleRetryPolicy (Retry-After-aware) and refactor AzureDiscovery to accept pre-built clients
- [x] 02-02-PLAN.md -- Refactor discover_subscription() with per-sub client lifecycle, progress output, and failure tracking

### Phase 3: Observability and UX Polish
**Goal**: Users can see which credential path was selected and tune scan behavior for large tenants without reading source code
**Depends on**: Phase 2
**Requirements**: OBSV-01, OBSV-02, OBSV-03
**Success Criteria** (what must be TRUE):
  1. Tool prints which credential class was selected (e.g., "Using ClientSecretCredential") before any subscription work begins
  2. Running with >200 subscriptions and --subscription-workers >2 prints a visible warning before scanning starts
  3. User can pass --checkpoint-ttl-hours to override the default 48-hour checkpoint expiry
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Credential Chain and Code Correctness | 2/3 | Gap closure | 2026-02-18 |
| 2. Concurrent Execution Hardening | 2/2 | Complete | 2026-02-18 |
| 3. Observability and UX Polish | 0/TBD | Not started | - |
