# Requirements: Universal DDI Cloud Usage Estimator

**Defined:** 2026-03-02
**Core Value:** Accurate, auditable UDDI token estimation from any source — cloud or NIOS Grid — customers must trust the numbers and understand exactly how they were derived.

## v1.2 Requirements

Requirements for the DTC/LBDN DDI Support milestone.

All DTC (DNS Traffic Control) object types from NIOS Grid backups must be recognized by the parser and counted toward the DDI bucket at the existing NIOS Object formula rate (DDI/50 for NIOS-managed, DDI/25 for NIOSX-native in hybrid scenarios). XML type strings are spec-derived — not empirically confirmed from a real DTC-containing backup.

### DTC Parser

- [x] **DTC-01**: Parser recognizes all DTC LBDN objects as a distinct `dtc_lbdn` family
- [x] **DTC-02**: Parser recognizes DTC Pool objects as a distinct `dtc_pool` family
- [x] **DTC-03**: Parser recognizes DTC Server objects as a distinct `dtc_server` family
- [x] **DTC-04**: Parser recognizes all DTC Monitor subtypes (http, icmp, pdp, sip, snmp, tcp) as a single `dtc_monitor` family
- [x] **DTC-05**: Parser recognizes DTC Topology objects (label, rule) as a single `dtc_topology` family

### DTC Counter

- [x] **DTC-06**: All DTC families count +1 toward DDI per object (no special expansion logic, unlike HOST_OBJECT)
- [x] **DTC-07**: DTC objects are grid-level (`member_hostname=None`) — no member attribution expected

### Scenario & Output

- [ ] **DTC-08**: DTC DDI counts flow through all three scenarios (current grid, hybrid, full migration) without changes to scenarios.py
- [ ] **DTC-09**: DTC families appear in the Object Counters sheet of the XLS report with correct per-family counts
- [ ] **DTC-10**: `inspect_backup()` includes all DTC families in `families_found` (zero-baseline pre-populated from `ALL_EXPECTED_FAMILIES`)

### Quality Gate

- [x] **DTC-11**: All DTC XML type strings in `_XML_TYPE_TO_FAMILY` are annotated with `# spec-derived, unverified — no empirical backup observed` comments

## Future Requirements

### Validation

- **DTC-V01**: Empirically confirm DTC XML __type strings against a real DTC-containing customer backup
- **DTC-V02**: Validate DTC object counts against a known reference (customer report or manual count)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-backup delta analysis (NIOS-ADV-04) | Not needed per v1.2 scope decision |
| GCP 87-project production validation (REF-01) | Still blocked — no live GCP environment |
| DTC-specific IP contribution | DTC objects are DNS/LB constructs — they do not contribute Active IPs |
| Per-DTC-type separate families (6 monitor types) | Grouped into dtc_monitor family — simpler, fewer constants, no counter difference |
| Discovery data as Active IP source | Outside DTC scope; UDDI spec confirmation still pending |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DTC-01 | Phase 16 | Complete |
| DTC-02 | Phase 16 | Complete |
| DTC-03 | Phase 16 | Complete |
| DTC-04 | Phase 16 | Complete |
| DTC-05 | Phase 16 | Complete |
| DTC-06 | Phase 16 | Complete |
| DTC-07 | Phase 16 | Complete |
| DTC-08 | Phase 17 | Pending |
| DTC-09 | Phase 17 | Pending |
| DTC-10 | Phase 17 | Pending |
| DTC-11 | Phase 16 | Complete |

**Coverage:**
- v1.2 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-02*
*Last updated: 2026-03-02 — traceability updated after roadmap creation*
