# Roadmap: Universal DDI Cloud Usage Estimator

## Overview

This roadmap delivers a complete rewrite of the Infoblox Universal DDI Cloud Usage Estimator: a local-execution, Python-only tool that discovers cloud resources across AWS, Azure, and GCP, categorizes them, and calculates UDDI token estimates. The build order follows the dependency graph -- core infrastructure first (error taxonomy, rate limiter, checkpoint, result collector), then AWS as the first end-to-end pipeline proving the architecture, then Azure and GCP plugging into the proven pipeline, then the web dashboard on top, and finally cross-platform hardening. Phase 1 is the highest-leverage investment: four of six critical architectural pitfalls must be addressed there before any cloud API code is written.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Core Infrastructure** - Foundation abstractions: resource schema, error taxonomy, rate limiter, result collector, checkpoint engine, progress tracking
- [x] **Phase 2: AWS Provider and End-to-End Pipeline** - First complete vertical slice: AWS discovery through counting, token calculation, and CSV/XLS report output
- [x] **Phase 2.1: Wire RateLimiter into Discovery Pipeline** - INSERTED: Gap closure from v1.0 audit — activate RateLimiter coordination in orchestrator and collector decorators, remove dead code
- [ ] **Phase 3: Azure Provider** - Azure subscription discovery plugged into the proven pipeline with tenant-level rate limiting
- [ ] **Phase 4: GCP Provider** - GCP project discovery plugged into the proven pipeline, validated against 87-project reference environment
- [ ] **Phase 5: Web Dashboard** - FastAPI + HTMX dashboard with real-time SSE progress and results browsing
- [ ] **Phase 6: Platform Hardening** - Cross-platform validation (Windows 11, WSL, macOS) and PowerShell setup scripts

## Phase Details

### Phase 1: Core Infrastructure
**Goal**: A tested foundation layer that all three providers plug into -- resource schema, error handling, rate limiting, checkpointing, and progress tracking work correctly before any cloud API code is written
**Depends on**: Nothing (first phase)
**Requirements**: AUTH-04, AUTH-05, DISC-04, DISC-05, DISC-06, DISC-08, RESIL-01, RESIL-02, RESIL-03, PLAT-05
**Success Criteria** (what must be TRUE):
  1. Pre-flight auth validation ("auth doctor") checks credential validity for each configured provider and reports clear pass/fail before scan starts
  2. Concurrent discovery orchestrator can dispatch work to N account workers with provider-scoped semaphores, and a simulated failure in one worker does not affect others
  3. Rate limiter applies adaptive retry with exponential backoff and jitter, and checkpoint engine saves/loads scan progress atomically with configurable TTL expiry
  4. All infrastructure code is pure Python with no compiled dependencies, no obfuscation, and no telemetry -- auditability constraint satisfied
**Plans**: 4 plans

Plans:
- [x] 01-01-PLAN.md -- Foundation types: resource schema, error taxonomy, audit logger
- [x] 01-02-PLAN.md -- Resilience layer: retry decorator, rate limiter, checkpoint engine
- [x] 01-03-PLAN.md -- User-facing: auth doctor, progress tracker
- [x] 01-04-PLAN.md -- Integration: discovery orchestrator, CLI entry point, signal handler

### Phase 2: AWS Provider and End-to-End Pipeline
**Goal**: Users can run a complete AWS scan that discovers resources across all accounts, counts DDI objects/IPs/assets, calculates token estimates, and produces a CSV/XLS report with detail and summary sheets
**Depends on**: Phase 1
**Requirements**: AUTH-01, DISC-01, DISC-07, DDI-01, DDI-02, DDI-03, DDI-04, IP-01, IP-02, IP-03, ASSET-01, ASSET-02, ASSET-03, ASSET-06, TOKEN-01, TOKEN-02, TOKEN-03, OUT-01, OUT-02, OUT-03, OUT-04, OUT-05
**Success Criteria** (what must be TRUE):
  1. User can authenticate via AWS SSO profile and discover resources across multiple AWS accounts and regions concurrently
  2. Tool correctly counts DNS zones, DNS records, subnets, and DHCP option sets from AWS and categorizes each resource as DDI, IP, or Asset with a skip reason if excluded (EBS Volumes and S3 Buckets excluded as token-free)
  3. Active IPs (private and public) are de-duplicated per VPC IP space, and managed assets are de-duplicated across discovery paths
  4. Token calculation (DDI/25 + IPs/13 + Assets/3) produces correct totals per account and as a provider total, matching manual calculation
  5. Output XLS file contains a detail sheet (one row per resource with ID, type, account, region, IPs, counted yes/no, category, skip reason) and a summary sheet (totals per account by resource type), plus a SHA-256 proof manifest documenting scan integrity
**Plans**: 6 plans

Plans:
- [x] 02-01-PLAN.md -- AWS auth validator, Organizations multi-account, provider skeleton, CLI integration
- [x] 02-02-PLAN.md -- Counting, categorization, and token calculation (TDD)
- [x] 02-03-PLAN.md -- AWS resource collectors: DDI objects (VPCs, subnets, Route53, DHCP)
- [x] 02-04-PLAN.md -- AWS resource collectors: compute, database, and token-free resources
- [x] 02-05-PLAN.md -- Output pipeline: XLS report, estimator CSV, proof manifest
- [x] 02-06-PLAN.md -- End-to-end integration: wire pipeline and moto integration tests

### Phase 2.1: Wire RateLimiter into Discovery Pipeline (INSERTED — Gap Closure)
**Goal**: Activate the RateLimiter's adaptive per-provider tracking so concurrent workers coordinate throttle state, and clean up orphaned dead code from the counting module
**Depends on**: Phase 2
**Requirements**: DISC-05 (integration hardening)
**Gap Closure**: Closes DISC-05 integration gap from v1.0 milestone audit
**Success Criteria** (what must be TRUE):
  1. RateLimiter.record_rate_limit() is called by retry_with_backoff's on_retry callback when a collector hits a throttle error, updating per-provider backoff state
  2. DiscoveryOrchestrator checks RateLimiter.get_delay() before dispatching each worker and applies the delay, coordinating backoff across concurrent workers
  3. Orphaned count_ips() function is removed from ip_counter.py (dead code cleanup)
**Plans**: 2 plans

Plans:
- [x] 02.1-01-PLAN.md -- Wire RateLimiter into retry decorator and orchestrator dispatch loop
- [x] 02.1-02-PLAN.md -- Remove orphaned count_ips() dead code from counting module

### Phase 3: Azure Provider
**Goal**: Users can run a complete Azure scan across all subscriptions, with tenant-level rate limiting preventing ARM throttling cascades, producing the same quality of output as AWS
**Depends on**: Phase 2
**Requirements**: AUTH-02, DISC-02, ASSET-04
**Success Criteria** (what must be TRUE):
  1. User can authenticate via `az login` and discover resources across all accessible Azure subscriptions concurrently
  2. Azure-specific token-free resources (VM Disks, Management Groups, VM Monitoring Stats, Network Watcher Flow Logs, Network Watchers, Storage Accounts, Storage Containers, Subscription Tenants, Traffic Manager Profiles) are correctly excluded from token calculation
  3. Tenant-level rate limiting prevents ARM 429 cascades -- scan of 50+ subscriptions completes without throttling-induced failures
  4. Azure results flow through the same counting, token calculation, and report pipeline as AWS, producing a provider-specific XLS with detail and summary sheets
**Plans**: 4 plans

Plans:
- [x] 03-01-PLAN.md -- Azure auth validator, subscription enumeration, client factory, provider skeleton, CLI integration
- [x] 03-02-PLAN.md -- DDI collectors (VNets, subnets, DHCP) + DNS collectors (public/private zones/records) + core networking (NICs, public IPs)
- [x] 03-03-PLAN.md -- Compute (VMs, VMSS) + database (SQL, Cosmos, MySQL, PostgreSQL, Redis) + PaaS + hybrid networking collectors
- [x] 03-04-PLAN.md -- Token-free collectors, categorizer extension, provider wiring, integration tests, legacy deletion

### Phase 4: GCP Provider
**Goal**: Users can run a complete GCP scan across all projects, using aggregatedList endpoints for efficiency, validated against a known 87-project reference environment
**Depends on**: Phase 2
**Requirements**: AUTH-03, DISC-03, ASSET-05, REF-01
**Success Criteria** (what must be TRUE):
  1. User can authenticate via `gcloud auth application-default login` and discover resources across all accessible GCP projects concurrently
  2. GCP-specific token-free resources (Compute Persistent Disks, Instance Groups, URL Maps, Cloud Monitoring Metric Stats, Network Connectivity Locations, Cloud Storage Bucket Policies, Cloud Storage Buckets) are correctly excluded from token calculation
  3. GCP discovery uses aggregatedList endpoints where available, reducing API call volume compared to per-region listing
  4. GCP discovery results match expected counts when validated against a production environment with 87 projects (REF-01 reference implementation)
**Plans**: 4 plans

Plans:
- [x] 04-01-PLAN.md -- GCP auth validator, project enumeration, client factory, provider skeleton, CLI integration
- [x] 04-02-PLAN.md -- DDI collectors (VPCs, subnets) + DNS collectors (zones, records) + networking (reserved IPs)
- [x] 04-03-PLAN.md -- Compute (VMs, forwarding rules) + database (Cloud SQL) collectors
- [x] 04-04-PLAN.md -- Token-free collectors, categorizer extension, provider wiring, integration tests, legacy deletion

### Phase 5: Web Dashboard
**Goal**: Users can monitor discovery progress in real-time and browse results through a browser-based dashboard without CLI expertise
**Depends on**: Phase 2, Phase 3, Phase 4
**Requirements**: PLAT-02, PLAT-03
**Success Criteria** (what must be TRUE):
  1. Web dashboard (FastAPI + HTML) shows real-time discovery progress via SSE -- user sees per-provider account completion counts updating live during a scan
  2. Dashboard displays results with filtering by provider, account, resource type, and counted/skipped status, with token calculation summary visible
  3. Dashboard requires no JavaScript build toolchain -- HTMX and CSS are vendored, no npm/Node.js dependency
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

### Phase 6: Platform Hardening
**Goal**: Tool runs reliably on all target platforms (Windows 11, WSL, macOS) with signed PowerShell setup scripts for Windows onboarding
**Depends on**: Phase 1, Phase 2, Phase 3, Phase 4, Phase 5
**Requirements**: PLAT-01, PLAT-04
**Success Criteria** (what must be TRUE):
  1. Tool installs and runs correctly on Windows 11 (native Python), WSL on Windows 11, and macOS -- all file paths, process handling, and environment detection work cross-platform
  2. PowerShell setup scripts are provided and signed with a self-signed certificate, enabling Windows users to install dependencies and configure the tool without manual Python environment setup
**Plans**: TBD

Plans:
- [ ] 06-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 2.1 -> 3 -> 4 -> 5 -> 6
Note: Phase 2.1 is a gap closure insertion. Phases 3 and 4 both depend on Phase 2 but not on each other. Phase 5 depends on all provider phases.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Infrastructure | 4/4 | Complete    | 2026-02-23 |
| 2. AWS Provider and End-to-End Pipeline | 6/6 | Complete | 2026-02-23 |
| 2.1. Wire RateLimiter (Gap Closure) | 2/2 | Complete | 2026-02-24 |
| 3. Azure Provider | 4/4 | Complete | 2026-02-24 |
| 4. GCP Provider | 4/4 | Complete | 2026-02-24 |
| 5. Web Dashboard | 0/TBD | Not started | - |
| 6. Platform Hardening | 0/TBD | Not started | - |
