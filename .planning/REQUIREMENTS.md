# Requirements: Universal DDI Cloud Usage Estimator

**Defined:** 2026-03-07
**Core Value:** Accurate, auditable UDDI token estimation from any source — cloud or NIOS Grid — customers must trust the numbers and understand exactly how they were derived.

## v1.8 Requirements

Requirements for the Dashboard Analytics milestone. Each maps to roadmap phases.

### AD Dashboard

- [x] **AD-09**: User can initiate AD analysis from dashboard via connection wizard (host, port, auth mode, domain, services scope)
- [x] **AD-10**: User sees per-DC SSE autodiscovery progress (step counter + elapsed time)
- [x] **AD-11**: User sees AD results screen with DNS zone count, DHCP scope count, AD user count, token formula derivation, and download CTA
- [x] **AD-12**: User can retry AD analysis from error state

### DNS Zones

- [ ] **DNS-01**: User sees Top 5 Cloud DNS zones by record count on Summary tab
- [ ] **DNS-02**: User sees Top 5 AD DNS zones by record count on AD complete screen
- [ ] **DNS-03**: User sees Top 5 NIOS DNS zones by record count on NIOS complete screen (requires extending NIOS parse pipeline to accumulate per-zone record counts)

### Attribution

- [ ] **ATTR-01**: User sees human-readable display names for v1.7 DDI types in per-account attribution table breakdown

## Future Requirements

### DNS Zones (v1.9+)

- **DNS-04**: NIOS per-zone record count accumulator exposed in XLS report
- **DNS-05**: Cross-scope zone overlap detection (same zone name in Cloud + AD)

### AD Dashboard (v1.9+)

- **AD-13**: Per-DC connection status display during AD autodiscovery (individual DC success/fail badges)

### Attribution (v1.9+)

- **ATTR-02**: DDI formula annotation per type in breakdown rows (count ÷ 25 = X.X tokens inline)
- **ATTR-03**: Functional grouping of v1.7 DDI types within breakdown (Route53 Resolver / IPAM / Networking)

## Out of Scope

| Feature | Reason |
|---------|--------|
| NIOS DNS zones in XLS report | Point-in-time analysis tool; report format locked to existing 5-sheet structure |
| Real-time token impact preview | Requires re-running full pipeline on every toggle; too expensive for large datasets |
| Charts / visualizations | Text tables sufficient for enterprise audit context; consistent with existing design |
| Cross-scope zone overlap detection | High complexity; no immediate pre-sales demand; v1.9+ |
| Per-DC connection status SSE | High complexity; requires collector refactoring; not needed for core AD dashboard v1.8 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AD-09 | Phase 30 | Complete |
| AD-10 | Phase 30 | Complete |
| AD-11 | Phase 30 | Complete |
| AD-12 | Phase 30 | Complete |
| DNS-01 | Phase 31 | Pending |
| DNS-02 | Phase 31 | Pending |
| DNS-03 | Phase 31 | Pending |
| ATTR-01 | Phase 32 | Pending |

**Coverage:**
- v1.8 requirements: 8 total
- Mapped to phases: 8
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-07*
*Last updated: 2026-03-07 — traceability confirmed during roadmap creation*
