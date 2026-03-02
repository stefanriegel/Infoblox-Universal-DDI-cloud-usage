# Roadmap: Universal DDI Cloud Usage Estimator

## Milestones

- ✅ **v1.0 Cloud Discovery MVP** — Phases 1–9 (shipped 2026-02-26)
- ✅ **v1.1 NIOS Grid Analysis** — Phases 10–15 (shipped 2026-03-02)
- 🚧 **v1.2 DTC/LBDN DDI Support** — Phases 16–17 (in progress)

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

### 🚧 v1.2 DTC/LBDN DDI Support (In Progress)

**Milestone Goal:** All DTC object types recognized by the NIOS parser and counted toward DDI, flowing through all three scenarios and the XLS report unchanged.

- [x] **Phase 16: DTC Parser and Counter** — Add five DTC families to schema, parser, and counter (completed 2026-03-02)
- [ ] **Phase 17: DTC Integration Verification** — Confirm scenarios, XLS report, and inspect_backup all surface DTC counts correctly

## Phase Details

### Phase 16: DTC Parser and Counter
**Goal**: All five DTC object families are recognized by the parser and counted toward DDI
**Depends on**: Phase 15 (v1.1 NIOS stack)
**Requirements**: DTC-01, DTC-02, DTC-03, DTC-04, DTC-05, DTC-06, DTC-07, DTC-11
**Success Criteria** (what must be TRUE):
  1. Running the parser against a synthetic backup containing DTC XML objects produces non-zero counts for all five families: dtc_lbdn, dtc_pool, dtc_server, dtc_monitor, dtc_topology
  2. DTC object counts appear in the DDI bucket total — the counter adds them using +1 per object with no special expansion
  3. DTC objects carry member_hostname=None (grid-level) — no member attribution rows are produced
  4. Every DTC XML type string entry in `_XML_TYPE_TO_FAMILY` has the spec-derived annotation comment
  5. All existing v1.1 tests continue to pass — zero regressions from adding DTC families
**Plans**: TBD

### Phase 17: DTC Integration Verification
**Goal**: DTC counts flow end-to-end through scenarios, XLS report, and inspect_backup with no code changes required
**Depends on**: Phase 16
**Requirements**: DTC-08, DTC-09, DTC-10
**Success Criteria** (what must be TRUE):
  1. A NIOS analysis run with a DTC-containing backup produces DDI token estimates that include DTC objects in all three scenario outputs (current grid, hybrid UDDI split, full migration)
  2. The Object Counters sheet in the XLS report shows a row for each DTC family with the correct count
  3. `inspect_backup()` output lists all five DTC families in `families_found`, including zero-count families pre-populated from `ALL_EXPECTED_FAMILIES`
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Core Infrastructure | v1.0 | 4/4 | Complete | 2026-02-23 |
| 2. AWS Provider | v1.0 | 6/6 | Complete | 2026-02-23 |
| 2.1. Wire RateLimiter (INSERTED) | v1.0 | 2/2 | Complete | 2026-02-24 |
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
| 16. DTC Parser and Counter | v1.2 | Complete    | 2026-03-02 | 2026-03-02 |
| 17. DTC Integration Verification | v1.2 | 0/TBD | Not started | - |
