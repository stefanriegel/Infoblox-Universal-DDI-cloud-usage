# Roadmap: Infoblox Universal DDI Cloud Usage Tool

## Milestones

- ✅ **v1 Azure Large-Tenant Discovery Fix** — Phases 1-3 (shipped 2026-02-19)
- [ ] **v1.1 GCP Multi-Project Discovery** — Phases 4-8 (current)

## Phases

<details>
<summary>✅ v1 Azure Large-Tenant Discovery Fix (Phases 1-3) — SHIPPED 2026-02-19</summary>

- [x] Phase 1: Credential Chain and Code Correctness (3/3 plans) — completed 2026-02-18
- [x] Phase 2: Concurrent Execution Hardening (2/2 plans) — completed 2026-02-18
- [x] Phase 3: Observability and UX Polish (1/1 plan) — completed 2026-02-18

</details>

**v1.1 GCP Multi-Project Discovery**

- [ ] **Phase 4: GCP Credential Chain and Fail-Fast** — Replace broken gcloud-based credential check with validated singleton; exits immediately on invalid/expired tokens
- [ ] **Phase 5: GCP Project Enumeration** — Auto-discover all ACTIVE projects accessible to the credential; backward-compatible single-project path preserved
- [ ] **Phase 6: Concurrent Multi-Project Execution** — Outer project worker pool with per-project DNS client lifecycle and shared compute clients; full multi-project discovery
- [ ] **Phase 7: Retry and Observability** — GCP rate-limit retry with visible logging; failed-project summary; large-org warnings
- [ ] **Phase 8: Checkpoint and Resume** — Per-project checkpoint with atomic writes and SIGINT handler; resume skips completed projects

## Phase Details

### Phase 4: GCP Credential Chain and Fail-Fast
**Goal**: GCP discovery uses a validated credential singleton that fails fast on invalid or expired tokens — no silent 0-resource success
**Depends on**: Nothing (first v1.1 phase)
**Requirements**: CRED-01, CRED-02, CRED-03, CRED-04, CRED-05
**Success Criteria** (what must be TRUE):
  1. Running the tool with an expired or invalid GCP token prints an actionable error message and exits non-zero — never reports "Discovery completed successfully!" with 0 resources
  2. Running the tool with a valid Service Account key file authenticates and logs `[Auth] Using service account: <path-or-email>` before any discovery work begins
  3. Running the tool with valid Application Default Credentials authenticates and logs `[Auth] Using Application Default Credentials` at startup
  4. The credential object is created once on the main thread; worker threads receive the same validated credential instance without re-authenticating
  5. A credential chain failure raises a typed exception (RefreshError or DefaultCredentialsError) — bare `except Exception` blocks do not swallow auth errors
**Plans:** 2 plans
Plans:
- [ ] 04-01-PLAN.md — Build credential singleton in config.py (validation, logging, permission pre-check)
- [ ] 04-02-PLAN.md — Wire singleton into discover.py and fix bare exception catches in gcp_discovery.py

### Phase 5: GCP Project Enumeration
**Goal**: The tool discovers all ACTIVE GCP projects accessible to the credential and handles edge cases cleanly before any per-project discovery work
**Depends on**: Phase 4
**Requirements**: ENUM-01, ENUM-02, ENUM-03, ENUM-04, ENUM-05, ENUM-06
**Success Criteria** (what must be TRUE):
  1. Running the tool with org-level credentials lists all ACTIVE projects and begins discovery — not just the single project in `GOOGLE_CLOUD_PROJECT`
  2. Running the tool when the credential has no project access prints an explicit warning with IAM remediation guidance and exits cleanly — not a silent empty result
  3. Running the tool with `--project my-project-id` or `GOOGLE_CLOUD_PROJECT` set bypasses enumeration and scans that single project (backward compatibility preserved)
  4. Setting `GOOGLE_CLOUD_ORG_ID` causes enumeration to scope to that organization's projects
  5. Running with `--include-projects "prod-*"` or `--exclude-projects "test-*"` filters the project list before discovery begins
  6. A project where the Compute API is disabled is skipped with an INFO log — it is not treated as a permission error or auth failure
**Plans**: TBD

### Phase 6: Concurrent Multi-Project Execution
**Goal**: The tool discovers resources across all enumerated GCP projects concurrently, with each resource attributed to its project and no socket exhaustion
**Depends on**: Phase 5
**Requirements**: EXEC-01, EXEC-02, EXEC-03, EXEC-04, EXEC-05
**Success Criteria** (what must be TRUE):
  1. Running a multi-project scan creates a new `dns.Client` per project inside the worker and closes it after that project completes — the same `dns.Client` instance is never shared across projects
  2. Compute API clients (InstancesClient, SubnetworksClient, etc.) are shared across all project workers; each API call passes `project=project_id` rather than constructing a new client per project
  3. As each project completes, the console prints `[N/total] project-id` progress output in order of completion
  4. Every discovered resource in the output includes a `project_id` field identifying which project it came from
  5. No two resources from different projects share the same `resource_id` — the ID format includes the project identifier to prevent collisions
**Plans**: TBD

### Phase 7: Retry and Observability
**Goal**: Transient GCP API failures are retried with visible logging, and operators see a complete summary of which projects failed and why after each scan
**Depends on**: Phase 6
**Requirements**: RTRY-01, RTRY-02, RTRY-03, RTRY-04
**Success Criteria** (what must be TRUE):
  1. When a GCP Compute API call returns 403 `rateLimitExceeded`, the tool retries with exponential backoff and does not surface the error to the operator unless retries are exhausted
  2. Each retry attempt produces a visible log line identifying the project being retried and the attempt number
  3. After the scan completes, any projects that failed after all retries are listed with their error messages — the summary is written to `output/gcp_failed_projects_{timestamp}.txt`
  4. When the project count exceeds the warning threshold and worker count is high, the tool prints a large-org advisory before discovery begins
**Plans**: TBD

### Phase 8: Checkpoint and Resume
**Goal**: A scan interrupted mid-run can be resumed from where it stopped — already-completed projects are not re-scanned
**Depends on**: Phase 7
**Requirements**: CHKP-01, CHKP-02, CHKP-03, CHKP-04, CHKP-05
**Success Criteria** (what must be TRUE):
  1. After each project completes, a checkpoint JSON file is written containing the list of completed project IDs and accumulated resources — a crash loses at most one project's work
  2. Re-running the tool after a crash with the same checkpoint file skips already-completed projects and continues from where the scan stopped
  3. `--checkpoint-ttl-hours` controls how long a checkpoint is considered valid before being ignored (default 48 hours)
  4. The checkpoint file is written atomically via temp file rename — a crash mid-write never produces a corrupt checkpoint
  5. Pressing Ctrl+C during a scan saves the checkpoint before exiting — restarting afterwards resumes correctly
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Credential Chain and Code Correctness | v1 | 3/3 | Complete | 2026-02-18 |
| 2. Concurrent Execution Hardening | v1 | 2/2 | Complete | 2026-02-18 |
| 3. Observability and UX Polish | v1 | 1/1 | Complete | 2026-02-18 |
| 4. GCP Credential Chain and Fail-Fast | v1.1 | 0/2 | Planned | — |
| 5. GCP Project Enumeration | v1.1 | 0/? | Not started | — |
| 6. Concurrent Multi-Project Execution | v1.1 | 0/? | Not started | — |
| 7. Retry and Observability | v1.1 | 0/? | Not started | — |
| 8. Checkpoint and Resume | v1.1 | 0/? | Not started | — |
