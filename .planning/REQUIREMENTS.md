# Requirements: Universal DDI Cloud Usage Estimator

**Defined:** 2026-03-03
**Milestone:** v1.6 Wizard Navigation Fix
**Core Value:** Accurate, auditable UDDI token estimation from any source — cloud or NIOS Grid — customers must trust the numbers and understand exactly how they were derived.

## v1.6 Requirements

Requirements for the Wizard Navigation Fix milestone. Addresses the brittle JS-based navigation on wizard scan start.

### Navigation

- [x] **NAV-01**: Wizard scan-start endpoint returns `HX-Redirect: /tab/progress` header with empty 200 body on success (not JSON)
- [x] **NAV-02**: Step 4 review form uses plain `hx-post` with no `hx-target`, `hx-swap`, or `hx-on` attributes — HTMX follows HX-Redirect natively
- [x] **NAV-03**: Test asserts `HX-Redirect` header is present and points to `/tab/progress` on successful scan start

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Cancel/error navigation | Existing 409 JSON response on conflict is correct; no change needed |
| NIOS wizard scan start | NIOS analysis uses a separate endpoint unaffected by this fix |
| Client-side fallback JS | HX-Redirect is sufficient; no need for a non-HTMX fallback path |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| NAV-01 | Phase 24 | Complete |
| NAV-02 | Phase 24 | Complete |
| NAV-03 | Phase 24 | Complete |

**Coverage:**
- v1.6 requirements: 3 total
- Mapped to phases: 3
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-03*
*Last updated: 2026-03-03 after roadmap creation — traceability confirmed*
