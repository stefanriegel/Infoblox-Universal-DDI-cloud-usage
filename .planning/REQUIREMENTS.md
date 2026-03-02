# Requirements: Universal DDI Cloud Usage Estimator

**Defined:** 2026-03-03
**Core Value:** Accurate, auditable UDDI token estimation from any source — cloud or NIOS Grid — customers must trust the numbers and understand exactly how they were derived.

## v1.3 Requirements

Requirements for the Enhanced WebUI Experience milestone. Phases 18–20.

### Progress Feedback

- [ ] **PROG-01**: User sees named step labels during NIOS analysis (e.g., "Inspecting backup", "Counting objects", "Writing report")
- [ ] **PROG-02**: User sees current step number out of total steps during NIOS analysis (e.g., "Step 3 of 6")
- [ ] **PROG-03**: User sees elapsed time while NIOS analysis is running

### Token Breakdown

- [ ] **BRKDN-01**: User can view DDI object count, Active IP count, and Asset count per scenario in the WebUI after NIOS analysis
- [ ] **BRKDN-02**: User can see formula derivation per scenario inline (e.g., "1,234 DDI ÷ 50 = 24.7 tokens") in the WebUI
- [ ] **BRKDN-03**: User can view a per-member breakdown table showing each member's DDI/IP/Asset counts and token contribution in the WebUI
- [ ] **BRKDN-04**: User can see NIOS vs NIOSX group label on each row in the member breakdown table

### Migration Wizard

- [ ] **WIZ-01**: User sees explanatory text describing what NIOS and NIOSX group assignments mean for token calculation before assigning members
- [ ] **WIZ-02**: User can select all or deselect all members with a single click in the migration assignment step
- [ ] **WIZ-03**: User sees a live count of NIOS vs NIOSX assigned members as they toggle assignments
- [ ] **WIZ-04**: The wizard steps are clearly numbered and labeled (Step 1: Upload Backup, Step 2: Assign Members, Step 3: Run Analysis)

## Future Requirements

### Extended Analytics

- **ANA-01**: User can view per-object-family DDI breakdown (HOST_RECORD: 234, DHCP_RANGE: 156, DTC_LBDN: 12, etc.) in the WebUI
- **ANA-02**: User can filter the member breakdown table by member name or group in the WebUI
- **ANA-03**: User can sort the member breakdown table by any column

### Cloud Scan UI

- **CLOUD-01**: Cloud Summary tab shows formula derivation for cloud token totals (DDI ÷ 25 + IPs ÷ 13 + Assets ÷ 3)
- **CLOUD-02**: Cloud Summary tab shows per-resource-type breakdown per provider

## Out of Scope

| Feature | Reason |
|---------|--------|
| Live token impact preview while assigning members | Requires re-running full pipeline on every toggle — too expensive for large grids |
| Re-run without re-upload | Backup file is streamed twice already; state management for cached runs adds complexity |
| Charts / visualizations | Text tables are sufficient and consistent with enterprise audit expectations |
| Copy-to-clipboard for token totals | Nice-to-have; deferred to future |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PROG-01 | Phase 18 | Pending |
| PROG-02 | Phase 18 | Pending |
| PROG-03 | Phase 18 | Pending |
| BRKDN-01 | Phase 19 | Pending |
| BRKDN-02 | Phase 19 | Pending |
| BRKDN-03 | Phase 19 | Pending |
| BRKDN-04 | Phase 19 | Pending |
| WIZ-01 | Phase 20 | Pending |
| WIZ-02 | Phase 20 | Pending |
| WIZ-03 | Phase 20 | Pending |
| WIZ-04 | Phase 20 | Pending |

**Coverage:**
- v1.3 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-03*
*Last updated: 2026-03-03 — traceability confirmed during roadmap creation*
