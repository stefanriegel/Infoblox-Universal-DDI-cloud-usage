# Requirements: Universal DDI Cloud Usage Estimator

**Defined:** 2026-03-03
**Milestone:** v1.4 Audit Depth
**Core Value:** Accurate, auditable UDDI token estimation from any source — cloud or NIOS Grid — customers must trust the numbers and understand exactly how they were derived.

## v1.4 Requirements

Requirements for the Audit Depth milestone. Each maps to a roadmap phase.

### Cloud Attribution

- [x] **CLOUD-01**: User sees a per-account attribution table on the cloud scan Summary tab listing every scanned account with its Account ID, DDI Object count, Active IP count, Asset count, and Total Token contribution
- [x] **CLOUD-02**: Each per-account row shows inline formula derivation within the respective columns (e.g. `312 DDI ÷ 25 = 12.5 tokens`)
- [x] **CLOUD-03**: Each per-account row includes a resource-type breakdown sub-section showing the counted resource types and their counts (e.g. DNS Zones: 4, VPCs: 12, VMs: 38) that produced the DDI/IP/Asset totals
- [x] **CLOUD-04**: Account column label is provider-aware per row (Account for AWS, Subscription for Azure, Project for GCP)
- [x] **CLOUD-05**: Table includes footer notes that per-account Token and IP column totals are not summable (ceiling-division rounding and cross-account IP deduplication); DDI column total IS summable

### NIOS Analysis

- [x] **ANA-01**: NIOS complete screen shows an object family breakdown section listing all non-zero NIOS object families and their contribution to the token estimate
- [x] **ANA-02**: Family breakdown shows DDI-adjusted contribution per family (actual DDI records after `host_object` expansion — not raw XML object count)
- [x] **ANA-03**: Family breakdown includes a DDI flag column (Yes/No) indicating whether the family contributes to DDI
- [x] **ANA-04**: Non-DDI family rows include a reason column explaining why the family is counted but not as DDI (e.g. "Administrative/reference", "Active IP source")
- [x] **ANA-05**: Family breakdown includes a subtotal row for DDI-contributing families showing the sum of their DDI-adjusted contributions
- [x] **ANA-06**: Family breakdown section heading states the breakdown is scenario-independent (all three scenarios count the same objects under different formulas)

## Future Requirements

Acknowledged but deferred to v1.5+.

### Cloud Attribution

- **CLOUD-F01**: Per-account table rows are sortable by token contribution descending — add after SE feedback identifies navigation difficulty on large (50+ account) scans
- **CLOUD-F02**: Cloud formula derivation summary card in Results tab — deferred per v1.4 scope decision

### NIOS Analysis

- **ANA-F01**: Collapsible per-account resource-type breakdown rows using `<details>` — useful only at 50+ accounts simultaneously visible

## Out of Scope

Explicitly excluded from v1.4. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Sortable/filterable attribution table columns | Results tab already filters at resource level; complexity exceeds value for 10-100 row tables |
| Per-account XLS download | Existing XLS covers reporting; WebUI table is for in-session audit only |
| Account name lookup | Requires live cloud API calls during result browsing — tool is offline for display |
| Live recalculate on resource-type toggle | Risks divergence from the official XLS report |
| Chart/graph visualization | Explicitly excluded by PROJECT.md — text tables sufficient for enterprise audit context |
| Per-component DDI/IP/Asset percentage columns | Low urgency; percentage columns add visual noise for simple accounts |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CLOUD-01 | Phase 21 | Delivered |
| CLOUD-02 | Phase 21 | Delivered |
| CLOUD-03 | Phase 21 | Delivered |
| CLOUD-04 | Phase 21 | Delivered |
| CLOUD-05 | Phase 21 | Delivered |
| ANA-01 | Phase 22 | Delivered |
| ANA-02 | Phase 22 | Delivered |
| ANA-03 | Phase 22 | Delivered |
| ANA-04 | Phase 22 | Delivered |
| ANA-05 | Phase 22 | Delivered |
| ANA-06 | Phase 22 | Delivered |

**Coverage:**
- v1.4 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-03*
*Last updated: 2026-03-03 — CLOUD-01–05 marked Delivered after Phase 21 completion; ANA-01–06 marked Delivered after Phase 22 completion*
