# Roadmap: Universal DDI Cloud Usage Estimator

## Milestones

- ✅ **v1.0 Cloud Discovery MVP** — Phases 1–9 (shipped 2026-02-26)
- ✅ **v1.1 NIOS Grid Analysis** — Phases 10–15 (shipped 2026-03-02)
- ✅ **v1.2 DTC/LBDN DDI Support** — Phases 16–17 (shipped 2026-03-02)
- ✅ **v1.3 Enhanced WebUI Experience** — Phases 18–20 (shipped 2026-03-03)
- ✅ **v1.4 Audit Depth** — Phases 21–22 (shipped 2026-03-03)
- ✅ **v1.5 Results Navigation** — Phase 23 (shipped 2026-03-03)
- ✅ **v1.6 Wizard Navigation Fix** — Phase 24 (shipped 2026-03-03)
- ✅ **v1.7 Reference Parity** — Phases 25–29 (shipped 2026-03-07)
- 🚧 **v1.8 Dashboard Analytics** — Phases 30–32 (in progress)

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

<details>
<summary>✅ v1.4 Audit Depth (Phases 21–22) — SHIPPED 2026-03-03</summary>

- [x] Phase 21: Cloud Per-Account Attribution Table (2/2 plans) — completed 2026-03-03
- [x] Phase 22: NIOS Object Family Breakdown (2/2 plans) — completed 2026-03-03

Archive: `.planning/milestones/v1.4-ROADMAP.md`

</details>

<details>
<summary>✅ v1.5 Results Navigation (Phase 23) — SHIPPED 2026-03-03</summary>

- [x] Phase 23: Results Navigation (2/2 plans) — completed 2026-03-03

Archive: `.planning/milestones/v1.5-ROADMAP.md`

</details>

<details>
<summary>✅ v1.6 Wizard Navigation Fix (Phase 24) — SHIPPED 2026-03-03</summary>

- [x] Phase 24: Wizard Navigation Fix (1/1 plan) — completed 2026-03-03

</details>

<details>
<summary>✅ v1.7 Reference Parity (Phases 25–29) — SHIPPED 2026-03-07</summary>

- [x] Phase 25: IP Methodology Fix (4/4 plans) — completed 2026-03-03
- [x] Phase 26: AWS DDI Gaps (5/5 plans) — completed 2026-03-04
- [x] Phase 27: Azure DDI Gaps (3/3 plans) — completed 2026-03-07
- [x] Phase 28: GCP DDI Gaps (3/3 plans) — completed 2026-03-07
- [x] Phase 29: Microsoft AD Core (4/4 plans) — completed 2026-03-07

Archive: `.planning/milestones/v1.7-ROADMAP.md`

</details>

### v1.8 Dashboard Analytics (In Progress)

**Milestone Goal:** Complete the AD dashboard experience and add cross-source DNS zone analytics and expanded DDI type attribution display names.

- [x] **Phase 30: AD Dashboard** - Connection wizard, autodiscovery progress, results screen, and retry flow for the AD tab (completed 2026-03-08)
- [ ] **Phase 31: DNS Zones Panels** - Top 5 DNS zones by record count on Cloud Summary, AD complete, and NIOS complete screens
- [ ] **Phase 32: Attribution Display Names** - Human-readable display names for v1.7 DDI types in per-account breakdown rows

## Phase Details

### Phase 30: AD Dashboard
**Goal**: Users can run an AD analysis entirely from the dashboard — connecting via wizard, watching per-DC autodiscovery progress, reviewing counts and token derivation on the results screen, and recovering from errors with a retry button
**Depends on**: Phase 29 (AD provider is fully functional; this phase surfaces it in the web UI)
**Requirements**: AD-09, AD-10, AD-11, AD-12
**Success Criteria** (what must be TRUE):
  1. User can open the AD tab, fill in host/port/auth/domain/services fields in a connection wizard, and submit to start an analysis
  2. User sees a progress screen that updates per DC via SSE — each update shows a step counter and elapsed time
  3. User sees a results screen that displays DNS zone count, DHCP scope count, AD user count, the token formula derivation (DDI÷25), and a download CTA for the XLS report
  4. When an AD analysis fails, user sees an error state and a retry button that returns them to the wizard to re-submit
**Plans**: 4 plans
Plans:
- [ ] 30-01-PLAN.md — Wave 0: AD dashboard test scaffold (all test classes)
- [ ] 30-02-PLAN.md — Wave 1: AdScanManager service + routes/ad.py route handlers
- [ ] 30-03-PLAN.md — Wave 1: AD Jinja2 templates (pages/ad.html + 3 partials)
- [ ] 30-04-PLAN.md — Wave 2: Integration wiring (app.py lifespan + pages.py tab route + tab_bar.html)

### Phase 31: DNS Zones Panels
**Goal**: Users can see which DNS zones are the heaviest token consumers across every analysis source — Cloud, AD, and NIOS — as a Top 5 list by record count on each source's results screen
**Depends on**: Phase 30 (AD results screen exists to host DNS-02 panel; independent of Phase 30 for DNS-01 and DNS-03)
**Requirements**: DNS-01, DNS-02, DNS-03
**Success Criteria** (what must be TRUE):
  1. The cloud Summary tab displays a Top 5 DNS zones panel listing zone names and record counts sourced from the current cloud scan
  2. The AD complete screen displays a Top 5 AD DNS zones panel listing zone names and record counts from the completed AD analysis
  3. The NIOS complete screen displays a Top 5 NIOS DNS zones panel listing zone names and record counts, requiring per-zone record count accumulation in the NIOS parse pipeline
**Plans**: 3 plans
Plans:
- [ ] 31-01-PLAN.md — Wave 1: Wave 0 test scaffold (all 7 DNS zone test classes)
- [ ] 31-02-PLAN.md — Wave 2: DNS-01 Cloud + DNS-02 AD panels (pages.py, ad_manager.py, ad.py, summary.html, ad/complete.html)
- [ ] 31-03-PLAN.md — Wave 3: DNS-03 NIOS pipeline extension + complete screen panel (nios_manager.py, nios.py, pages.py, nios/complete.html)

### Phase 32: Attribution Display Names
**Goal**: Users reading the per-account attribution breakdown on the cloud Summary tab see human-readable display names for the v1.7 DDI types rather than raw internal type strings
**Depends on**: Nothing (independent of Phases 30–31; touches only display layer)
**Requirements**: ATTR-01
**Success Criteria** (what must be TRUE):
  1. Every v1.7 DDI type string (aws-route53-resolver-endpoint, azure-vnet-gateway, gcp-reserved-ip, etc.) is rendered as a readable label in the breakdown rows (e.g., "Route53 Resolver Endpoint", "VNet Gateway", "Reserved IP Address")
  2. Existing pre-v1.7 DDI types are unaffected and continue to render as before
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
| 23. Results Navigation | v1.5 | 2/2 | Complete | 2026-03-03 |
| 24. Wizard Navigation Fix | v1.6 | 1/1 | Complete | 2026-03-03 |
| 25. IP Methodology Fix | v1.7 | 4/4 | Complete | 2026-03-03 |
| 26. AWS DDI Gaps | v1.7 | 5/5 | Complete | 2026-03-04 |
| 27. Azure DDI Gaps | v1.7 | 3/3 | Complete | 2026-03-07 |
| 28. GCP DDI Gaps | v1.7 | 3/3 | Complete | 2026-03-07 |
| 29. Microsoft AD Core | v1.7 | 4/4 | Complete | 2026-03-07 |
| 30. AD Dashboard | v1.8 | 5/5 | Complete | 2026-03-08 |
| 31. DNS Zones Panels | 1/3 | In Progress|  | - |
| 32. Attribution Display Names | v1.8 | 0/TBD | Not started | - |
