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
- [x] **Phase 3: Azure Provider** - Azure subscription discovery plugged into the proven pipeline with tenant-level rate limiting
- [x] **Phase 4: GCP Provider** - GCP project discovery plugged into the proven pipeline, validated against 87-project reference environment (completed 2026-02-24)
- [x] **Phase 5: Web Dashboard** - FastAPI + HTMX dashboard with real-time SSE progress and results browsing (completed 2026-02-24)
- [x] **Phase 6: Platform Hardening** - Cross-platform validation (Windows 11, WSL, macOS) and PowerShell setup scripts (completed 2026-02-25)
- [x] **Phase 7: Integration Gap Closure** - Wire orphaned RateLimiter.record_success() and checkpoint_engine to Azure/GCP providers (completed 2026-02-25)
- [x] **Phase 8: Dashboard GCP Scan Fix** - Fix GCP scan path in web dashboard: correct enumerate_gcp_projects args, ProjectInfo iteration, and Azure dict key lookup (completed 2026-02-25)
- [x] **Phase 9: Integration Tech Debt Cleanup** - Close 3 non-critical integration gaps: AWS checkpoint symmetry, DDI_TYPES unification, double emit_done removal (completed 2026-02-26)
- [ ] **Phase 10: NIOS Parser and Schema** - Streaming tar.gz/onedb.xml parser with lxml iterparse, typed NiosObject schema, two-pass member map, structural integrity report
- [ ] **Phase 11: Filter and Counter** - Member whitelist/blacklist with whitelist-first semantics, per-member DDI/IP/Asset counting with Host Object expansion and lease deduplication, dual formula constants
- [ ] **Phase 12: Scenario Engine** - Three scenario computations: current grid (NIOS Object formula), hybrid UDDI (per-group dual formula), full migration (UDDI native formula)
- [ ] **Phase 13: Output and Runner** - 5-sheet XLS report with per-scenario comparison and member attribution, runner wiring parse-filter-count-scenarios-output pipeline
- [ ] **Phase 14: CLI Integration** - Additive --nios and --nios-config CLI flags wired to runner, end-to-end acceptance test
- [ ] **Phase 15: Dashboard Integration** - NIOS Analysis tab with file upload wizard, migration split toggles, and results display

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
**Plans**: 4 plans

Plans:
- [x] 05-01-PLAN.md -- FastAPI app factory, vendored static assets, base template, EventBridge, ScanManager
- [x] 05-02-PLAN.md -- HTMX tab navigation, SSE progress endpoint, DashboardProgressTracker
- [x] 05-03-PLAN.md -- Results table with filtering/pagination, Summary tab with token cards
- [x] 05-04-PLAN.md -- Scan wizard, download endpoints, CLI --web flag

### Phase 6: Platform Hardening
**Goal**: Tool runs reliably on all target platforms (Windows 11, WSL, macOS) with signed PowerShell setup scripts for Windows onboarding
**Depends on**: Phase 1, Phase 2, Phase 3, Phase 4, Phase 5
**Requirements**: PLAT-01, PLAT-04
**Success Criteria** (what must be TRUE):
  1. Tool installs and runs correctly on Windows 11 (native Python), WSL on Windows 11, and macOS -- all file paths, process handling, and environment detection work cross-platform
  2. PowerShell setup scripts are provided and signed with a self-signed certificate, enabling Windows users to install dependencies and configure the tool without manual Python environment setup
**Plans**: 2 plans

Plans:
- [x] 06-01-PLAN.md -- Cross-platform Python hardening: preflight module, SIGTERM guard, setup script modernization with CLI detection
- [x] 06-02-PLAN.md -- CI multi-platform Python 3.10+ matrix, PowerShell signing (2-year cert), enterprise re-signing guide

### Phase 7: Integration Gap Closure
**Goal**: Wire orphaned integration points so RateLimiter success tracking and Azure/GCP checkpoint resume are functional, closing dead code paths identified by v1.0 audit
**Depends on**: Phase 2.1, Phase 3, Phase 4
**Requirements**: DISC-05 (integration hardening), RESIL-01 (checkpoint hardening)
**Gap Closure**: Closes 2 integration gaps from v1.0 milestone audit
**Success Criteria** (what must be TRUE):
  1. RateLimiter.record_success() is called by collectors on successful API responses, decaying backoff state after throttle recovery
  2. checkpoint_engine is passed to AzureDiscoveryProvider and GCPDiscoveryProvider constructors, enabling per-subscription/per-project checkpoint skip logic
  3. No orphaned methods or dead internal code paths remain for rate limiting or checkpointing
**Plans**: 2 plans

Plans:
- [x] 07-01-PLAN.md -- Wire record_success() immediate reset into orchestrator + thread checkpoint_engine into CLI and dashboard provider construction
- [x] 07-02-PLAN.md -- Update tests for immediate-reset semantics, remove dead constant references, add integration tests for wiring

### Phase 8: Dashboard GCP Scan Fix
**Goal**: Fix the web dashboard's GCP scan path so users can initiate GCP scans through the wizard, matching the working CLI path
**Depends on**: Phase 5, Phase 7
**Requirements**: DISC-02, DISC-03, DISC-07, PLAT-02 (dashboard path hardening)
**Gap Closure**: Closes INT-01, INT-02, INT-03 and Dashboard GCP Scan flow from v1.0 audit
**Success Criteria** (what must be TRUE):
  1. `enumerate_gcp_projects` is called with all 6 required positional args in both `_enumerate_accounts` and `_build_discovery_providers`
  2. GCP wizard displays project IDs extracted from `ProjectInfo.project_id`, not raw `ProjectInfo` objects
  3. Azure wizard uses the correct `id` key from `list_subscriptions()` return dicts (removes dead `subscription_id` primary lookup)
  4. Dashboard GCP scan flow works end-to-end: wizard enumerates projects -> user selects -> scan starts -> SSE progress -> results
**Plans**: 2 plans

Plans:
- [x] 08-01-PLAN.md -- Fix all provider bugs in scan.py (GCP 6-arg calls, ProjectInfo iteration, Azure dict key) and add inline error UX
- [ ] 08-02-PLAN.md -- Regression tests for all bug fixes, error UX paths, and CLI-vs-dashboard parity

### Phase 9: Integration Tech Debt Cleanup
**Goal**: Close 3 non-critical integration gaps from v1.0 audit: add AWS checkpoint guard for provider-level symmetry, unify DDI_TYPES across modules, and remove double emit_done in dashboard scan pipeline
**Depends on**: Phase 7, Phase 8
**Requirements**: RESIL-01, ASSET-06, PLAT-02 (integration hardening)
**Gap Closure**: Closes INT-01, INT-02, INT-03 from v1.0 tech debt audit
**Success Criteria** (what must be TRUE):
  1. AWSDiscoveryProvider.discover_account() accepts checkpoint_engine and skips already-completed accounts, symmetric with Azure/GCP providers
  2. asset_dedup.DDI_TYPES imports from or mirrors the canonical categorizer.DDI_TYPES, covering AWS, Azure, and GCP DDI resource types
  3. DashboardProgressTracker.finish() emits scan_complete exactly once — no duplicate emission in the finally block
**Plans**: 1 plan

Plans:
- [ ] 09-01-PLAN.md -- Fix all 3 integration gaps (INT-01 AWS checkpoint, INT-02 DDI_TYPES unification, INT-03 double emit_done) + regression tests

---

## Milestone v1.1: NIOS Grid Analysis

Phases 10–15 deliver NIOS Grid backup analysis integrated into the existing tool. The NIOS pipeline is fully isolated in a new `src/cloud_usage/nios/` package. It shares no code with the cloud providers — the data model, token formulas, and output pipeline are all independent. The build order respects strict data-flow dependencies: member identity resolved before filtering (Phase 10), filtering gates ingestion before counting (Phase 11), counting completes before scenarios are computed (Phase 12), output and runner wired after pipeline is validated (Phase 13), CLI integration first (Phase 14), then dashboard tab last (Phase 15).

- [ ] **Phase 10: NIOS Parser and Schema** - Streaming tar.gz/onedb.xml parser with lxml iterparse, typed NiosObject schema, two-pass member map, structural integrity report
- [ ] **Phase 11: Filter and Counter** - Member whitelist/blacklist with whitelist-first semantics, per-member DDI/IP/Asset counting with Host Object expansion and lease deduplication, dual formula constants
- [ ] **Phase 12: Scenario Engine** - Three scenario computations: current grid (NIOS Object formula), hybrid UDDI (per-group dual formula), full migration (UDDI native formula)
- [ ] **Phase 13: Output and Runner** - 5-sheet XLS report with per-scenario comparison and member attribution, runner wiring parse-filter-count-scenarios-output pipeline
- [ ] **Phase 14: CLI Integration** - Additive --nios and --nios-config CLI flags wired to runner, end-to-end acceptance test
- [ ] **Phase 15: Dashboard Integration** - NIOS Analysis tab with file upload wizard, migration split toggles, and results display

## Phase Details (v1.1)

### Phase 10: NIOS Parser and Schema
**Goal**: Users can load a NIOS Grid backup file and have all object families extracted into typed Python objects with member identity fully resolved, memory usage flat regardless of file size
**Depends on**: Phase 9 (v1.0 complete)
**Requirements**: PARSE-01, PARSE-02, PARSE-03, PARSE-04, PARSE-05, PARSE-06, PARSE-07, PARSE-08, PARSE-09, PARSE-10, PARSE-11, PARSE-12, PARSE-13
**Success Criteria** (what must be TRUE):
  1. User can pass a .tar.gz backup path to the parser and receive a complete stream of typed NiosObject instances without extracting any file to disk
  2. Parser processes a 2GB+ onedb.xml without exceeding 150MB peak memory — verified by profiling against the ZF Friedrichshafen reference backup (2.5M objects)
  3. All 13 object families are extracted: Members, Networks, Leases, Fixed Addresses, Host Addresses, DNS Zones, DNS Records (A/AAAA/CNAME/MX/NS/PTR/SOA/SRV/TXT), Host Objects, Host Aliases, DHCP Ranges, Exclusion Ranges, Network Containers, Network Views
  4. Every extracted object references a resolved member hostname/FQDN (not a raw virtual_oid integer) where member attribution exists in the backup
  5. Structural integrity report lists each object family found, row count per type, and emits a warning for any expected family with zero rows
**Plans**: TBD

### Phase 11: Filter and Counter
**Goal**: Users can scope the analysis to specific grid members and receive per-member DDI object counts, Active IP counts, and dual-formula token contributions that match the ZF Friedrichshafen reference values
**Depends on**: Phase 10
**Requirements**: FILTER-01, FILTER-02, FILTER-03, FILTER-04, COUNT-01, COUNT-02, COUNT-03, COUNT-04, COUNT-05, COUNT-06
**Success Criteria** (what must be TRUE):
  1. User can specify a hostname glob whitelist and only matching members' objects appear in all counts and output — changing the whitelist changes the token totals, not just the display table
  2. Active IP count for the ZF reference backup produces exactly 168,295 unique active-only IPs (not 605,489 raw lease rows) when default lease state filter (active + static) is applied
  3. DDI object count correctly expands Host Objects to constituent A + PTR + optional CNAME records without double-counting independent DNS record objects that share the same parent
  4. Per-member attribution table lists each member with separate DDI count, Active IP count, and token contribution computed under the applicable formula (NIOS Object or UDDI native)
  5. NIOS Object formula constants (DDI/50 + IPs/25 + Assets/13) and UDDI native constants (DDI/25 + IPs/13 + Assets/3) are defined only in nios/counter.py and never imported from the cloud token calculator
**Plans**: TBD

### Phase 12: Scenario Engine
**Goal**: Users can compute three licensing scenarios from a single set of grid counts and see the token impact of keeping members on NIOS, migrating all to NIOSX, or splitting the grid between the two
**Depends on**: Phase 11
**Requirements**: SCEN-01, SCEN-02, SCEN-03, MIGR-01, MIGR-03, MIGR-04
**Success Criteria** (what must be TRUE):
  1. Current grid scenario applies NIOS Object formula to all members and produces a single DDI total, Active IP total, and token total representing the full grid as licensed today
  2. Hybrid UDDI scenario requires a migration split config; NIOS-remaining sub-total (NIOS Object formula) plus NIOSX-migrated sub-total (UDDI native formula) sums exactly to the combined token total — no rounding error or blending
  3. Full migration scenario applies UDDI native formula to all members and produces a token total strictly higher than or equal to the current grid scenario total (higher divisors per token mean fewer tokens)
  4. Members not listed in the migration split config default to the configured default group (nios unless overridden), and the default group assignment is recorded in the output
  5. Migration split config used (member-to-group assignments, default group, assignment method) is captured verbatim for inclusion in the report
**Plans**: TBD

### Phase 13: Output and Runner
**Goal**: Users receive a 5-sheet XLS file from a single run_nios_analysis() call that contains all scenario totals, full member attribution, and a traceable header block identifying exactly what data was analyzed
**Depends on**: Phase 12
**Requirements**: OUT-01, OUT-02, OUT-03, OUT-04, OUT-05
**Success Criteria** (what must be TRUE):
  1. XLS report contains all 5 required sheets: Object Counters, DDI Objects, Active IP by Type, Scenario Comparison, Member Attribution — each sheet non-empty when the backup contains the corresponding object families
  2. Scenario Comparison sheet shows all three scenarios side-by-side with DDI count, Active IP count, Assets count, formula applied, and token total per scenario — all six cells traceable to the counter output without manual calculation
  3. Member Attribution sheet lists every post-filter member with virtual_oid, hostname, group assignment, DHCP lease count, DDI object count, Active IP count, and token contribution under the applicable formula
  4. Report header block captures: NIOS version string, backup snapshot date, filter config applied, migration split used, formula constants, and analysis timestamp — two reports from different runs are unambiguously distinguishable
  5. run_nios_analysis(backup_path, config) completes the full parse-filter-count-scenarios-output pipeline and returns the output file path, callable identically from CLI and dashboard
**Plans**: TBD

### Phase 14: CLI Integration
**Goal**: Users can run a complete NIOS Grid analysis from the command line with a single command and receive an XLS report without touching the dashboard
**Depends on**: Phase 13
**Requirements**: INTEG-01
**Success Criteria** (what must be TRUE):
  1. `python -m cloud_usage.cli --nios backup.tar.gz` produces a timestamped nios_analysis_<timestamp>.xlsx file in the output directory
  2. `--nios-config config.yaml` flag reads member filter and migration split configuration from a YAML file and passes it to run_nios_analysis() — the XLS output reflects the config
  3. No existing CLI code path is modified — the --nios branch is an additive elif that does not touch AWS/Azure/GCP provider selection, auth doctor, or scan orchestration
  4. End-to-end acceptance test confirms ZF reference backup produces expected object family counts and the 168,295 active-only IP figure in the output XLS
**Plans**: TBD

### Phase 15: Dashboard Integration
**Goal**: Users can run a NIOS Grid analysis entirely through the web dashboard: uploading a backup file, assigning members to migration groups via UI toggles, and viewing results in the browser
**Depends on**: Phase 13, Phase 14
**Requirements**: INTEG-02, MIGR-02
**Success Criteria** (what must be TRUE):
  1. Dashboard shows a "NIOS Analysis" tab in the tab bar alongside the existing cloud provider tabs — navigating to it does not affect any cloud scan state
  2. User can upload a .tar.gz backup file through the dashboard and see a member list rendered with each member's hostname, virtual_oid, and DHCP lease count
  3. User can toggle each member between NIOS and NIOSX groups in the wizard and download the resulting XLS with the migration split reflected in the Scenario Comparison and Member Attribution sheets
  4. Uploaded file is saved to a known disk path within the HTTP request handler before the analysis background thread starts — the background thread receives a path string, not a file handle
  5. NIOS analysis state (upload, running, complete, error) is tracked independently of cloud scan state — a NIOS analysis and a cloud scan can coexist without state collision
**Plans**: TBD

## Progress

**Execution Order (v1.0):**
Phases execute in numeric order: 1 -> 2 -> 2.1 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9
Note: Phase 2.1 is a gap closure insertion. Phases 3 and 4 both depend on Phase 2 but not on each other. Phase 5 depends on all provider phases. Phases 7, 8, and 9 are gap closure phases from v1.0 audit.

**Execution Order (v1.1):**
Phases execute sequentially: 10 -> 11 -> 12 -> 13 -> 14 -> 15
Each phase has a hard data-flow dependency on the prior phase output.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Core Infrastructure | 4/4 | Complete    | 2026-02-23 |
| 2. AWS Provider and End-to-End Pipeline | 6/6 | Complete | 2026-02-23 |
| 2.1. Wire RateLimiter (Gap Closure) | 2/2 | Complete | 2026-02-24 |
| 3. Azure Provider | 4/4 | Complete | 2026-02-24 |
| 4. GCP Provider | 4/4 | Complete    | 2026-02-24 |
| 5. Web Dashboard | 4/4 | Complete    | 2026-02-24 |
| 6. Platform Hardening | 2/2 | Complete    | 2026-02-25 |
| 7. Integration Gap Closure | 2/2 | Complete    | 2026-02-25 |
| 8. Dashboard GCP Scan Fix | 2/2 | Complete   | 2026-02-25 |
| 9. Integration Tech Debt Cleanup | 1/1 | Complete   | 2026-02-26 |
| 10. NIOS Parser and Schema | 1/3 | In Progress|  |
| 11. Filter and Counter | 0/TBD | Not started | - |
| 12. Scenario Engine | 0/TBD | Not started | - |
| 13. Output and Runner | 0/TBD | Not started | - |
| 14. CLI Integration | 0/TBD | Not started | - |
| 15. Dashboard Integration | 0/TBD | Not started | - |
