# Roadmap: Universal DDI Cloud Usage Estimator

## Milestones

- ✅ **v1.0 Cloud Discovery MVP** — Phases 1–9 (shipped 2026-02-26)
- ✅ **v1.1 NIOS Grid Analysis** — Phases 10–15 (shipped 2026-03-02)
- ✅ **v1.2 DTC/LBDN DDI Support** — Phases 16–17 (shipped 2026-03-02)
- ✅ **v1.3 Enhanced WebUI Experience** — Phases 18–20 (shipped 2026-03-03)
- 🚧 **v1.4 Audit Depth** — Phases 21–22 (in progress)

## Phases

<details>
<summary>✅ v1.0 Cloud Discovery MVP (Phases 1–9) — SHIPPED 2026-02-26</summary>

- [x] Phase 1: Core Infrastructure (4/4 plans) — completed 2026-02-23
- [x] Phase 2: AWS Provider and End-to-End Pipeline (6/6 plans) — completed 2026-02-23
- [x] Phase 2.1: Wire RateLimiter into Discovery Pipeline — INSERTED (2/2 plans) — completed 2026-02-24
- [x] Phase 3: Azure Provider (4/4 plans) — completed 2026-02-24
- [x] Phase 4: GCP Provider (4/4 plans) — completed 2026-02-24
- [x] Phase 5: Web Dashboard (4/4 plans) — completed 2026-02-24
- [x] Phase 6: Platform Hardening (2/2 plans) — completed 2026-02-25
- [x] Phase 7: Integration Gap Closure (2/2 plans) — completed 2026-02-25
- [x] Phase 8: Dashboard GCP Scan Fix (2/2 plans) — completed 2026-02-25
- [x] Phase 9: Integration Tech Debt Cleanup (1/1 plan) — completed 2026-02-26

Archive: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 NIOS Grid Analysis (Phases 10–15) — SHIPPED 2026-03-02</summary>

- [x] Phase 10: NIOS Parser and Schema (3/3 plans) — completed 2026-02-28
- [x] Phase 11: Filter and Counter (3/3 plans) — completed 2026-03-02
- [x] Phase 12: Scenario Engine (2/2 plans) — completed 2026-03-02
- [x] Phase 13: Output and Runner (2/2 plans) — completed 2026-03-02
- [x] Phase 14: CLI Integration (2/2 plans) — completed 2026-03-02
- [x] Phase 15: Dashboard Integration (2/2 plans) — completed 2026-03-02

Archive: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 DTC/LBDN DDI Support (Phases 16–17) — SHIPPED 2026-03-02</summary>

- [x] Phase 16: DTC Parser and Counter (2/2 plans) — completed 2026-03-02
- [x] Phase 17: DTC Integration Verification (2/2 plans) — completed 2026-03-02

Archive: `.planning/milestones/v1.2-ROADMAP.md`

</details>

<details>
<summary>✅ v1.3 Enhanced WebUI Experience (Phases 18–20) — SHIPPED 2026-03-03</summary>

- [x] Phase 18: NIOS Pipeline Progress Events (2/2 plans) — completed 2026-03-02
- [x] Phase 19: Token Breakdown WebUI (2/2 plans) — completed 2026-03-03
- [x] Phase 20: Migration Wizard UX (2/2 plans) — completed 2026-03-03

Archive: `.planning/milestones/v1.3-ROADMAP.md`

</details>

### 🚧 v1.4 Audit Depth (In Progress)

**Milestone Goal:** Surface formula derivation and object-level attribution in both cloud and NIOS WebUI so every token total is fully explainable without leaving the browser.

- [x] **Phase 21: Cloud Per-Account Attribution Table** — Per-account token attribution with inline formula derivation and resource-type breakdown on the cloud scan Summary tab (completed 2026-03-03)
- [x] **Phase 22: NIOS Object Family Breakdown** — Object-family breakdown table on the NIOS complete screen mirroring the XLS Object Counters sheet (completed 2026-03-03)

## Phase Details

### Phase 21: Cloud Per-Account Attribution Table
**Goal**: The cloud scan Summary tab exposes per-account token attribution with inline formula derivation and resource-type breakdown so pre-sales engineers can audit every token total without opening the XLS report
**Depends on**: Phase 20 (v1.3 shipped)
**Requirements**: CLOUD-01, CLOUD-02, CLOUD-03, CLOUD-04, CLOUD-05
**Success Criteria** (what must be TRUE):
  1. After a cloud scan completes, the Summary tab shows a table with one row per scanned account listing its Account ID, DDI Object count, Active IP count, Asset count, and Token contribution
  2. Each row's DDI, IP, and Asset count cells display inline formula derivation (e.g. `312 DDI ÷ 25 = 12.5 tokens`) so the contribution arithmetic is visible without external tooling
  3. Each row includes a resource-type sub-section showing the specific resource types and counts (e.g. DNS Zones: 4, VPCs: 12, VMs: 38) that produced the DDI/IP/Asset totals
  4. The account column label is provider-aware per row — "Account" for AWS rows, "Subscription" for Azure rows, "Project" for GCP rows
  5. The table footer carries explanatory notes that per-account Token and IP totals are not directly summable (ceiling-division rounding and cross-account IP deduplication), while explicitly stating the DDI column total is summable
**Plans**: TBD

### Phase 22: NIOS Object Family Breakdown
**Goal**: The NIOS complete screen shows a self-contained object-family breakdown table so customers can audit exactly which NIOS object types contributed to the DDI total without opening the XLS Object Counters sheet
**Depends on**: Phase 21
**Requirements**: ANA-01, ANA-02, ANA-03, ANA-04, ANA-05, ANA-06
**Success Criteria** (what must be TRUE):
  1. After NIOS analysis completes, the complete screen shows an object-family breakdown section listing every non-zero NIOS object family with its DDI-adjusted contribution
  2. Each family row includes a DDI flag column ("Yes"/"No") so it is immediately clear which families contribute to the DDI count and which do not
  3. Non-DDI family rows carry a reason column explaining why the family is counted but not as DDI (e.g. "Administrative/reference", "Active IP source")
  4. The breakdown includes a subtotal row summing only the DDI-contributing families, confirming the number feeds into the scenario token calculations
  5. The section heading states the breakdown is scenario-independent — the same object set is counted under all three scenarios, only the formula divisors differ
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Core Infrastructure | v1.0 | 4/4 | Complete | 2026-02-23 |
| 2. AWS Provider | v1.0 | 6/6 | Complete | 2026-02-23 |
| 2.1. Wire RateLimiter | v1.0 | 2/2 | Complete | 2026-02-24 |
| 3. Azure Provider | v1.0 | 4/4 | Complete | 2026-02-24 |
| 4. GCP Provider | v1.0 | 4/4 | Complete | 2026-02-24 |
| 5. Web Dashboard | v1.0 | 4/4 | Complete | 2026-02-24 |
| 6. Platform Hardening | v1.0 | 2/2 | Complete | 2026-02-25 |
| 7. Integration Gap Closure | v1.0 | 2/2 | Complete | 2026-02-25 |
| 8. Dashboard GCP Scan Fix | v1.0 | 2/2 | Complete | 2026-02-25 |
| 9. Integration Tech Debt Cleanup | v1.0 | 1/1 | Complete | 2026-02-26 |
| 10. NIOS Parser and Schema | v1.1 | 3/3 | Complete | 2026-02-28 |
| 11. Filter and Counter | v1.1 | 3/3 | Complete | 2026-03-02 |
| 12. Scenario Engine | v1.1 | 2/2 | Complete | 2026-03-02 |
| 13. Output and Runner | v1.1 | 2/2 | Complete | 2026-03-02 |
| 14. CLI Integration | v1.1 | 2/2 | Complete | 2026-03-02 |
| 15. Dashboard Integration | v1.1 | 2/2 | Complete | 2026-03-02 |
| 16. DTC Parser and Counter | v1.2 | 2/2 | Complete | 2026-03-02 |
| 17. DTC Integration Verification | v1.2 | 2/2 | Complete | 2026-03-02 |
| 18. NIOS Pipeline Progress Events | v1.3 | 2/2 | Complete | 2026-03-02 |
| 19. Token Breakdown WebUI | v1.3 | 2/2 | Complete | 2026-03-03 |
| 20. Migration Wizard UX | v1.3 | 2/2 | Complete | 2026-03-03 |
| 21. Cloud Per-Account Attribution Table | v1.4 | 2/2 | Complete | 2026-03-03 |
| 22. NIOS Object Family Breakdown | v1.4 | 2/2 | Complete | 2026-03-03 |
