# Roadmap: Universal DDI Cloud Usage Estimator

## Milestones

- ✅ **v1.0 Cloud Discovery MVP** — Phases 1–9 (shipped 2026-02-26)
- ✅ **v1.1 NIOS Grid Analysis** — Phases 10–15 (shipped 2026-03-02)
- ✅ **v1.2 DTC/LBDN DDI Support** — Phases 16–17 (shipped 2026-03-02)
- 🚧 **v1.3 Enhanced WebUI Experience** — Phases 18–20 (in progress)

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

### 🚧 v1.3 Enhanced WebUI Experience (In Progress)

**Milestone Goal:** Make the NIOS analysis feel polished and informative — progress steps during long runs, rich token breakdown with formula derivation, and a guided member assignment wizard.

- [x] **Phase 18: NIOS Pipeline Progress Events** — Emit step-level SSE events from the NIOS analysis pipeline and surface named steps, step counters, and elapsed time in the dashboard UI (completed 2026-03-02)
- [x] **Phase 19: Token Breakdown WebUI** — Enrich the NIOS results screen with per-scenario formula derivation and a per-member attribution table with NIOS/NIOSX group labels (completed 2026-03-03)
- [ ] **Phase 20: Migration Wizard UX** — Improve the NIOS member assignment step with explanatory text, select-all control, live group counts, and clearly numbered step labels

## Phase Details

### Phase 18: NIOS Pipeline Progress Events
**Goal**: Users see meaningful, named progress steps — with a step counter and elapsed time — while NIOS analysis runs, so long-running jobs feel responsive and trustworthy
**Depends on**: Phase 17 (v1.2 complete)
**Requirements**: PROG-01, PROG-02, PROG-03
**Success Criteria** (what must be TRUE):
  1. While NIOS analysis runs, the dashboard displays a named step label (e.g., "Inspecting backup", "Counting objects", "Writing report") that updates as each pipeline stage begins
  2. The progress area shows a step counter of the form "Step N of M" that advances through each stage of the pipeline
  3. An elapsed time indicator is visible and increments while the analysis is running
  4. The progress display clears or transitions to results when analysis completes
**Plans**: TBD

### Phase 19: Token Breakdown WebUI
**Goal**: The NIOS results screen exposes the full derivation of token totals — raw object/IP/asset counts, formula steps, and per-member attribution — so customers can audit and trust every number
**Depends on**: Phase 18
**Requirements**: BRKDN-01, BRKDN-02, BRKDN-03, BRKDN-04
**Success Criteria** (what must be TRUE):
  1. After analysis completes, the user can view DDI object count, Active IP count, and Asset count for each scenario (current grid, hybrid split, full migration) in the WebUI
  2. Each scenario block shows formula derivation inline — e.g., "1,234 DDI ÷ 50 = 24.7 tokens" — so the math is self-evident without opening the XLS report
  3. A per-member breakdown table is visible in the WebUI showing each member's DDI count, Active IP count, Asset count, and token contribution
  4. Each row in the member table is labeled with its group assignment — NIOS or NIOSX — so the licensing split is immediately visible
**Plans**: TBD

### Phase 20: Migration Wizard UX
**Goal**: The NIOS/NIOSX member assignment step in the dashboard wizard is clear, efficient, and self-explanatory — users understand what they are doing, can assign members quickly, and see the impact of their choices as they work
**Depends on**: Phase 19
**Requirements**: WIZ-01, WIZ-02, WIZ-03, WIZ-04
**Success Criteria** (what must be TRUE):
  1. Before assigning members to NIOS or NIOSX groups, the user sees explanatory text that describes what each group means for token calculation (NIOS Object formula vs UDDI native formula)
  2. A "Select All" / "Deselect All" control lets the user assign or clear all member assignments in the current group with a single click
  3. As the user toggles member assignments, a live counter updates to show the current count of NIOS-assigned members and NIOSX-assigned members
  4. The wizard step progression is labeled with clear step numbers and titles — e.g., "Step 1: Upload Backup", "Step 2: Assign Members", "Step 3: Run Analysis" — visible throughout the wizard
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 18. NIOS Pipeline Progress Events | 2/2 | Complete    | 2026-03-02 |
| 19. Token Breakdown WebUI | 0/TBD | Complete    | 2026-03-03 |
| 20. Migration Wizard UX | 0/TBD | Not started | - |
