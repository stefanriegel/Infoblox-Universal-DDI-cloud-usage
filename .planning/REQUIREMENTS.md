# Requirements: Infoblox Universal DDI Cloud Usage Tool

**Defined:** 2026-02-19
**Core Value:** Every cloud resource across all projects/subscriptions must be discovered reliably — no project or subscription should silently fail due to credential or concurrency issues.

## v1.1 Requirements

Requirements for GCP Multi-Project Discovery milestone. Each maps to roadmap phases.

### Credentials

- [x] **CRED-01**: Tool authenticates via Service Account key file or Application Default Credentials with actual token validation
- [x] **CRED-02**: Tool exits immediately with actionable message on invalid/expired credentials (no silent 0-resource "success")
- [x] **CRED-03**: Credential singleton warmed on main thread before worker threads spawn
- [x] **CRED-04**: Credential type logged at startup (`[Auth] Using service account: ...` or `[Auth] Using Application Default Credentials`)
- [x] **CRED-05**: Only typed exception catches in credential chain (RefreshError, DefaultCredentialsError)

### Project Enumeration

- [ ] **ENUM-01**: Tool auto-discovers all ACTIVE projects accessible to the credential
- [ ] **ENUM-02**: Tool warns explicitly when 0 projects found with IAM guidance
- [ ] **ENUM-03**: Single-project backward compat via `--project` flag or `GOOGLE_CLOUD_PROJECT` env var
- [ ] **ENUM-04**: Org/folder-aware enumeration when `GOOGLE_CLOUD_ORG_ID` is set
- [ ] **ENUM-05**: Project include/exclude via `--include-projects` / `--exclude-projects` glob patterns
- [ ] **ENUM-06**: `accessNotConfigured` errors classified and skipped gracefully (not treated as auth failure)

### Concurrent Execution

- [ ] **EXEC-01**: Per-project `dns.Client` lifecycle (created and closed per project worker)
- [ ] **EXEC-02**: Shared compute clients reused across projects with `project=` per API call
- [ ] **EXEC-03**: Progress output shows `[N/total] project-id` as each project completes
- [ ] **EXEC-04**: Each discovered resource attributed with project_id in details
- [ ] **EXEC-05**: `resource_id` format includes project_id to prevent multi-project collisions

### Retry & Observability

- [ ] **RTRY-01**: GCP 403 `rateLimitExceeded` retried with exponential backoff
- [ ] **RTRY-02**: Each retry attempt logged with project context
- [ ] **RTRY-03**: Failed projects collected and logged with error messages after scan
- [ ] **RTRY-04**: Large-org warning when project count exceeds threshold with high worker count

### Checkpoint/Resume

- [ ] **CHKP-01**: Checkpoint saved per project completion (JSON with completed_project_ids, resources, errors)
- [ ] **CHKP-02**: Resume on restart skips already-completed projects
- [ ] **CHKP-03**: `--checkpoint-ttl-hours` configurable (default 48)
- [ ] **CHKP-04**: Atomic checkpoint writes (temp file + rename)
- [ ] **CHKP-05**: SIGINT handler saves checkpoint before exit

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Cloud Asset Inventory

- **ASSET-01**: Enumerate resources across all projects via Cloud Asset Inventory API
- **ASSET-02**: Cross-reference Asset Inventory with per-project discovery for completeness check

### Async Rewrite

- **ASYNC-01**: Replace ThreadPoolExecutor with async/await using async Google Cloud clients

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| New GCP resource types | Current set (VMs, VPCs, subnets, IPs, DNS) sufficient for DDI licensing |
| Per-project credential objects | Anti-pattern; defeats singleton caching — one credential serves all projects |
| Azure/AWS discovery changes | Different providers, not in scope for this milestone |
| Async rewrite | Massive scope; threading model is correct for this use case |
| UI/CLI output format changes | Cosmetic, not reliability |
| gcloud CLI subprocess for project enumeration | Same problems as gcloud auth list — slow, wrong auth path, WSL issues |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CRED-01 | Phase 4 | Complete |
| CRED-02 | Phase 4 | Complete |
| CRED-03 | Phase 4 | Complete |
| CRED-04 | Phase 4 | Complete |
| CRED-05 | Phase 4 | Complete |
| ENUM-01 | Phase 5 | Pending |
| ENUM-02 | Phase 5 | Pending |
| ENUM-03 | Phase 5 | Pending |
| ENUM-04 | Phase 5 | Pending |
| ENUM-05 | Phase 5 | Pending |
| ENUM-06 | Phase 5 | Pending |
| EXEC-01 | Phase 6 | Pending |
| EXEC-02 | Phase 6 | Pending |
| EXEC-03 | Phase 6 | Pending |
| EXEC-04 | Phase 6 | Pending |
| EXEC-05 | Phase 6 | Pending |
| RTRY-01 | Phase 7 | Pending |
| RTRY-02 | Phase 7 | Pending |
| RTRY-03 | Phase 7 | Pending |
| RTRY-04 | Phase 7 | Pending |
| CHKP-01 | Phase 8 | Pending |
| CHKP-02 | Phase 8 | Pending |
| CHKP-03 | Phase 8 | Pending |
| CHKP-04 | Phase 8 | Pending |
| CHKP-05 | Phase 8 | Pending |

**Coverage:**
- v1.1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-19*
*Last updated: 2026-02-19 after roadmap creation (traceability complete)*
