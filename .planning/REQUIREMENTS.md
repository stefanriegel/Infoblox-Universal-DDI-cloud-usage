# Requirements: Universal DDI Cloud Usage Estimator

**Defined:** 2026-03-08
**Core Value:** Accurate, auditable UDDI token estimation from any source — cloud or NIOS Grid — customers must trust the numbers and understand exactly how they were derived.

## v1.9 Requirements

Requirements for the Multi-Tool Suite UX milestone. Restructures the dashboard as a home-screen-first multi-tool experience with a full visual redesign using the Infoblox brand design system.

### Home Screen

- [x] **HOME-01**: User sees a home screen at `/` titled "Infoblox UDDI Token Calculator" with three named calculator cards (Cloud, NIOS, AD)
- [x] **HOME-02**: Each calculator card shows the calculator name, a brief description, and an entry button that navigates to its dedicated URL (`/cloud`, `/nios`, `/ad`)

### Navigation

- [x] **NAV-01**: All calculator pages display a breadcrumb "Home > [Calculator Name]" at the top of the page
- [x] **NAV-02**: Clicking "Home" in the breadcrumb navigates the user back to `/`

### Cloud Calculator

- [ ] **CLOUD-08**: Cloud Calculator displays a persistent provider selector (AWS / Azure / GCP) throughout the wizard, progress, and results screens
- [ ] **CLOUD-09**: Switching provider in the persistent selector updates the active flow without navigating back to Home

### Design System

- [x] **DESIGN-01**: Replace PicoCSS with a custom CSS design system implementing Infoblox brand tokens — `#0066CC` primary blue, `#1A1A2E` dark navy, `#00C389` accent green, `#F8F9FA` page background, Inter font
- [x] **DESIGN-02**: Home screen uses a polished card layout (white cards, `#E5E7EB` border, rounded corners, subtle shadow) matching the reference Infoblox design language
- [x] **DESIGN-03**: Each calculator has a distinct visual accent color (Cloud: blue `#0066CC`, NIOS: green `#00C389`, AD: purple `#8B5CF6`) within the shared design system
- [x] **DESIGN-04**: Wizard steps display numbered step indicators with clear visual progression (step counter, active/complete state)
- [x] **DESIGN-05**: Results/complete screens use a card-based layout with visual separation of key metrics (token totals, formula derivations, attribution tables)

### Routes

- [x] **ROUTE-01**: Cloud Calculator served at `/cloud`, NIOS Calculator at `/nios`, AD Calculator at `/ad`
- [x] **ROUTE-02**: Root `/` serves the home selector screen (current behavior at root removed)

## Future Requirements

### Possible v2.0 Additions

- **CROSS-01**: Cross-calculator combined summary view (aggregated tokens from all three sources run in one session)
- **CROSS-02**: Session persistence — remember last-used provider and calculator state across browser refresh
- **DARK-01**: Dark mode toggle using the design system dark variant

## Out of Scope

| Feature | Reason |
|---------|--------|
| Mobile-first responsive redesign | Desktop/laptop only by design; enterprise tool not used on mobile |
| React / Tailwind migration | Python-only constraint (FastAPI + HTML for auditability); no npm build pipeline |
| Dark mode | Deferred to future — light mode sufficient for pre-sales enterprise context |
| Per-calculator authentication | No auth model in this tool — local execution, no user accounts |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DESIGN-01 | Phase 33 | Complete |
| HOME-01 | Phase 34 | Complete |
| HOME-02 | Phase 34 | Complete |
| ROUTE-01 | Phase 34 | Complete |
| ROUTE-02 | Phase 34 | Complete |
| DESIGN-02 | Phase 34 | Complete |
| NAV-01 | Phase 35 | Complete |
| NAV-02 | Phase 35 | Complete |
| DESIGN-03 | Phase 36 | Complete |
| DESIGN-04 | Phase 36 | Complete |
| DESIGN-05 | Phase 36 | Complete |
| CLOUD-08 | Phase 37 | Pending |
| CLOUD-09 | Phase 37 | Pending |

**Coverage:**
- v1.9 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-08*
*Last updated: 2026-03-08 — traceability updated after roadmap creation*
