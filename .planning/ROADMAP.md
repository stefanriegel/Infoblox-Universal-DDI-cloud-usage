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
- ✅ **v1.8 Dashboard Analytics** — Phases 30–32 (shipped 2026-03-08)
- 🚧 **v1.9 Multi-Tool Suite UX** — Phases 33–37 (in progress)

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

<details>
<summary>✅ v1.8 Dashboard Analytics (Phases 30–32) — SHIPPED 2026-03-08</summary>

- [x] Phase 30: AD Dashboard (5/5 plans) — completed 2026-03-08
- [x] Phase 31: DNS Zones Panels (3/3 plans) — completed 2026-03-08
- [x] Phase 32: Attribution Display Names (2/2 plans) — completed 2026-03-08

Archive: `.planning/milestones/v1.8-ROADMAP.md`

</details>

### 🚧 v1.9 Multi-Tool Suite UX (In Progress)

**Milestone Goal:** Restructure the dashboard as a home-screen-first multi-tool suite with self-contained calculator flows and a full visual redesign using the Infoblox brand design system.

- [x] **Phase 33: Design Foundation** — Replace PicoCSS with custom Infoblox brand CSS design system (completed 2026-03-08)
- [x] **Phase 34: Home Screen + Routing** — Home selector screen at `/` with calculator cards and dedicated routes (completed 2026-03-08)
- [x] **Phase 35: Navigation + Breadcrumb** — Breadcrumb nav on all calculator pages linking back to Home (completed 2026-03-08)
- [x] **Phase 36: Calculator Visual Redesign** — Apply design system accents and card layouts to all three calculators (completed 2026-03-08)
- [ ] **Phase 37: Cloud Provider Switcher** — Persistent provider selector throughout the Cloud Calculator flow

## Phase Details

### Phase 33: Design Foundation
**Goal**: The entire dashboard renders using a custom Infoblox-brand CSS design system instead of PicoCSS
**Depends on**: Phase 32 (v1.8 complete)
**Requirements**: DESIGN-01
**Success Criteria** (what must be TRUE):
  1. PicoCSS is removed from all templates; no PicoCSS classes or variables remain
  2. Pages render with `#0066CC` primary blue, `#1A1A2E` dark navy, `#00C389` accent green, and `#F8F9FA` page background applied via custom CSS variables
  3. Inter font is loaded and applied as the base typeface across all pages
  4. All existing calculator flows (Cloud, NIOS, AD) remain functional with the new CSS in place
**Plans**: 3 plans
Plans:
- [ ] 33-01-PLAN.md — Wave 0 test scaffold (xfail stubs for DESIGN-01)
- [ ] 33-02-PLAN.md — design-system.css + Inter variable font delivery
- [ ] 33-03-PLAN.md — CSS swap in base.html, app.css cleanup, --pico-* template fixes

### Phase 34: Home Screen + Routing
**Goal**: Users land on a home selector screen at `/` with three calculator cards, and each calculator is served at its own dedicated URL
**Depends on**: Phase 33
**Requirements**: HOME-01, HOME-02, ROUTE-01, ROUTE-02, DESIGN-02
**Success Criteria** (what must be TRUE):
  1. Visiting `/` shows a page titled "Infoblox UDDI Token Calculator" with three cards: Cloud, NIOS, and AD
  2. Each card displays the calculator name, a brief description, and an entry button
  3. Clicking a card entry button navigates to `/cloud`, `/nios`, or `/ad` respectively
  4. Cloud Calculator is served at `/cloud`, NIOS Calculator at `/nios`, AD Calculator at `/ad`
  5. Home screen cards use white background, `#E5E7EB` border, rounded corners, and subtle shadow matching the Infoblox card style
**Plans**: 3 plans
Plans:
- [ ] 34-01-PLAN.md — Wave 1: xfail test scaffold for all home/routing behaviors
- [ ] 34-02-PLAN.md — Wave 2: home.html template, card CSS, root route swap
- [ ] 34-03-PLAN.md — Wave 3: /cloud, /nios, /ad routes + base.html conditional tab fix

### Phase 35: Navigation + Breadcrumb
**Goal**: All calculator pages show a breadcrumb trail that lets users return to the home screen
**Depends on**: Phase 34
**Requirements**: NAV-01, NAV-02
**Success Criteria** (what must be TRUE):
  1. Every Cloud, NIOS, and AD calculator page displays a breadcrumb reading "Home > [Calculator Name]" at the top of the page
  2. Clicking "Home" in the breadcrumb navigates the user to `/`
  3. The breadcrumb is visible on all wizard steps, progress screens, and results screens within each calculator
**Plans**: 2 plans
Plans:
- [ ] 35-01-PLAN.md — Wave 1: xfail test scaffold for breadcrumb behaviors
- [ ] 35-02-PLAN.md — Wave 2: calculator_name injection, base.html breadcrumb block, app.css rules

### Phase 36: Calculator Visual Redesign
**Goal**: Each calculator has a distinct visual accent and polished card-based layouts for wizard steps and results screens, all within the shared design system
**Depends on**: Phase 35
**Requirements**: DESIGN-03, DESIGN-04, DESIGN-05
**Success Criteria** (what must be TRUE):
  1. Cloud Calculator uses blue (`#0066CC`) as its accent color, NIOS uses green (`#00C389`), and AD uses purple (`#8B5CF6`) — visually distinguishable on the wizard and results screens
  2. Wizard step indicators show numbered steps with clear active and complete visual states (not plain text)
  3. Results and complete screens display key metrics (token totals, formula derivations, attribution tables) in visually separated cards
**Plans**: 3 plans
Plans:
- [ ] 36-01-PLAN.md — Wave 1: xfail test scaffold (DESIGN-03, DESIGN-04, DESIGN-05)
- [ ] 36-02-PLAN.md — Wave 2: accent system — calc_theme injection, body class, wizard selectors
- [ ] 36-03-PLAN.md — Wave 3: card layouts — NIOS/AD completion-card, Cloud summary section headers

### Phase 37: Cloud Provider Switcher
**Goal**: Users can switch between AWS, Azure, and GCP within the Cloud Calculator without returning to the home screen
**Depends on**: Phase 36
**Requirements**: CLOUD-08, CLOUD-09
**Success Criteria** (what must be TRUE):
  1. The Cloud Calculator displays a persistent provider selector (AWS / Azure / GCP tabs or buttons) on the wizard, progress, and results screens
  2. Switching provider in the selector updates the active cloud flow without navigating away from `/cloud`
  3. The active provider is visually highlighted in the selector at all times
**Plans**: 4 plans
Plans:
- [ ] 37-01-PLAN.md — Wave 1: xfail test scaffold (CLOUD-08, CLOUD-09)
- [ ] 37-02-PLAN.md — Wave 2: three per-provider ScanManager + EventBridge instances in app.py
- [ ] 37-03-PLAN.md — Wave 2: provider-selector CSS in app.css + nav block in base.html
- [ ] 37-04-PLAN.md — Wave 3: per-provider tab routes, /cloud route update, tab_bar + progress template fixes

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
| 31. DNS Zones Panels | v1.8 | 3/3 | Complete | 2026-03-08 |
| 32. Attribution Display Names | v1.8 | 2/2 | Complete | 2026-03-08 |
| 33. Design Foundation | 3/3 | Complete    | 2026-03-08 | - |
| 34. Home Screen + Routing | 3/3 | Complete    | 2026-03-08 | - |
| 35. Navigation + Breadcrumb | 2/2 | Complete    | 2026-03-08 | - |
| 36. Calculator Visual Redesign | 3/3 | Complete    | 2026-03-08 | - |
| 37. Cloud Provider Switcher | v1.9 | 0/4 | Not started | - |
