# Requirements: Universal DDI Cloud Usage Estimator

**Defined:** 2026-03-03
**Milestone:** v1.5 Results Navigation
**Core Value:** Accurate, auditable UDDI token estimation from any source — cloud or NIOS Grid — customers must trust the numbers and understand exactly how they were derived.

## v1.5 Requirements

Requirements for the Results Navigation milestone. Each maps to a roadmap phase.

### Cloud Results Navigation

- [x] **CLOUD-06**: Cloud scan Results tab shows a per-provider formula summary card listing total DDI object count, Active IP count, Asset count, and their respective token derivations (DDI ÷ 25 = X, IPs ÷ 13 = X, Assets ÷ 3 = X, ceiling total) for each provider that was scanned
- [ ] **CLOUD-07**: Per-account attribution table is client-side sortable by token contribution column descending (default) so pre-sales engineers can instantly surface the highest-contributing accounts on 50+ account scans; sorting is interactive without a server round-trip

### NIOS Results Navigation

- [ ] **ANA-07**: Per-account resource-type breakdown rows within the cloud attribution table are collapsible using native `<details>/<summary>` so customers can expand only the accounts they want to inspect, reducing visual noise when many accounts are visible simultaneously

## Future Requirements

Acknowledged but deferred to v1.6+.

### Cloud Attribution

- **CLOUD-F03**: Account name resolution (friendly display name alongside Account ID) — requires live cloud API call during result browsing; tool is offline for display phase

### NIOS Analysis

- **ANA-F02**: NIOS member attribution table sortable by DDI object count descending — analogous to CLOUD-07 but for NIOS members

## Out of Scope

Explicitly excluded from v1.5. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Sortable/filterable columns beyond token contribution | Complexity exceeds value for the primary use case |
| Per-account XLS download | Existing XLS covers reporting; WebUI table is for in-session audit only |
| Account name lookup | Requires live cloud API calls during result browsing — tool is offline for display |
| Live recalculate on resource-type toggle | Risks divergence from the official XLS report |
| Chart/graph visualization | Explicitly excluded by PROJECT.md — text tables sufficient for enterprise audit context |
| Server-side sort (round-trip) | All sort state is client-side only — no new backend endpoints |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLOUD-06 | Phase 23 | Complete |
| CLOUD-07 | Phase 23 | Pending |
| ANA-07 | Phase 23 | Pending |

**Coverage:**
- v1.5 requirements: 3 total
- Mapped to phases: 3
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-03*
*Last updated: 2026-03-03 — traceability updated after roadmap creation (all 3 mapped to Phase 23)*
