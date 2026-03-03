---
phase: 23-results-navigation
plan: 01
subsystem: ui
tags: [jinja2, htmx, fastapi, formula-cards, per-provider, tdd]

# Dependency graph
requires:
  - phase: 21-cloud-attribution
    provides: per_provider_details context var in _compute_summary() already passed to both Results and Summary tabs
provides:
  - Per-provider formula cards in summary_cards.html showing DDI/IP/Asset counts with ÷ 25/÷ 13/÷ 3 inline derivations
  - tests/test_dashboard_results_navigation.py with TestFormulaCards (5 tests) and TestANA07 (1 test)
affects: [23-results-navigation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-provider formula card pattern: loop per_provider_details.items()|sort, guard each formula line with {% if data.field > 0 %}"
    - "TDD RED/GREEN: write failing tests first, then update template to pass them"

key-files:
  created:
    - tests/test_dashboard_results_navigation.py
  modified:
    - src/cloud_usage/dashboard/templates/partials/summary_cards.html

key-decisions:
  - "Use per_provider_details (ddi/ips/assets/tokens) instead of provider_breakdown (tokens only) — richer data already available from _compute_summary()"
  - "IP resources need ip_addresses populated to register in dedup counter — tests use network-interface with ip_addresses=['10.0.0.1'] rather than bare vpc"
  - "Suppress formula line with {% if data.field > 0 %} guard — consistent with existing complete.html and summary.html patterns"
  - "Divisors 25, 13, 3 hardcoded in template — spec constants, not passed from backend (matches Phase 21 pattern)"

patterns-established:
  - "Formula card zero-suppression: {% if data.ddi > 0 %} wraps each formula derivation line"
  - "Per-provider card sort: per_provider_details.items() | sort for deterministic alphabetical order"

requirements-completed: [CLOUD-06]

# Metrics
duration: 12min
completed: 2026-03-03
---

# Phase 23 Plan 01: Per-Provider Formula Cards Summary

**Per-provider formula breakdown in summary_cards.html now shows DDI/IP/Asset counts with ÷ 25/÷ 13/÷ 3 inline derivations, replacing the sparse token-only card list**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-03T18:33:00Z
- **Completed:** 2026-03-03T18:45:00Z
- **Tasks:** 2 (TDD: 1 RED commit + 1 GREEN commit)
- **Files modified:** 2

## Accomplishments

- Template `summary_cards.html` now iterates `per_provider_details` (not `provider_breakdown`) and renders a collapsible "Per-Provider Formula Breakdown" section with per-provider cards
- Each provider card displays DDI count + ÷ 25 = X.X, Active IPs + ÷ 13 = X.X, Managed Assets + ÷ 3 = X.X, and ceiling token total — all formula lines suppressed when the count is zero
- 6 new tests (TestFormulaCards x5 + TestANA07 x1) confirm rendering on both Results and Summary tabs, zero-count suppression, provider name display, and no-error behavior on empty scan

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing tests for formula card rendering (RED)** - `c813b1e` (test)
2. **Task 2: Replace provider_breakdown block with per_provider_details formula cards (GREEN)** - `fd8c547` (feat)

**Plan metadata:** (docs commit follows)

_Note: TDD tasks have RED test commit then GREEN implementation commit._

## Files Created/Modified

- `tests/test_dashboard_results_navigation.py` - New test file: TestFormulaCards (5 tests) + TestANA07 (1 test) verifying formula cards on Results and Summary tabs
- `src/cloud_usage/dashboard/templates/partials/summary_cards.html` - Replaced provider_breakdown block (lines 24-36) with per_provider_details formula card block; guard pattern with {% if data.ddi > 0 %} / {% if data.ips > 0 %} / {% if data.assets > 0 %}

## Decisions Made

- Used `per_provider_details` (carries ddi/ips/assets/tokens) instead of `provider_breakdown` (token counts only) — data was already computed and passed to both tabs by `_compute_summary()`; no backend changes needed
- IP resources in tests require `ip_addresses` to be populated — VPC-type resources without addresses produce zero IP count in the deduplication pipeline; switched to `network-interface` with `ip_addresses=["10.0.0.1"]`
- Assertion for zero-suppression test uses AZURE section slice search rather than global count, since the per-account attribution table (Phase 21) also renders `÷ 13 =` for AWS account

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test resource type for IP counting corrected**
- **Found during:** Task 2 (GREEN verification)
- **Issue:** Plan specified `("vpc", "ip", ...)` resources but VPC resources without `ip_addresses` produce `ips=0` in `_compute_summary()` because `deduplicate_ips_per_vpc` uses `ip_addresses` attribute; formula line `÷ 13 =` never rendered
- **Fix:** Switched IP test resources to `("network-interface", "ip", ...)` with `ip_addresses=["10.0.0.1"]` so deduplication pipeline registers the IP count
- **Files modified:** `tests/test_dashboard_results_navigation.py`
- **Verification:** `test_formula_card_shows_on_summary_tab` passes; `data.ips == 1` in per_provider_details for aws
- **Committed in:** `fd8c547` (Task 2 commit)

**2. [Rule 1 - Bug] Zero-suppression test assertion corrected**
- **Found during:** Task 2 (GREEN verification)
- **Issue:** Test asserted `response.text.count("÷ 13 =") == 1` but the per-account attribution table (from Phase 21) also renders `÷ 13 =` for the AWS account, producing count of 2
- **Fix:** Changed assertion to slice the AZURE section from the HTML and verify `÷ 13 =` is absent within that section
- **Files modified:** `tests/test_dashboard_results_navigation.py`
- **Verification:** `test_formula_card_suppresses_zero_count_lines` passes with precise AZURE-section check
- **Committed in:** `fd8c547` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug)
**Impact on plan:** Both fixes corrected test construction errors; the template implementation was correct as specified. No scope creep.

## Issues Encountered

None — template edit straightforward; deviations were in test construction (IP resource type and assertion logic), not in the implementation.

## Next Phase Readiness

- CLOUD-06 satisfied: formula cards render on both Results and Summary tabs
- Plan 23-02 (sortable attribution table — CLOUD-07) can proceed immediately; same summary.html template context, no backend changes
- ANA-07 verified: `<details>` collapsibles already present from Phase 21

## Self-Check: PASSED

All files confirmed present and all commits verified in git log.

---
*Phase: 23-results-navigation*
*Completed: 2026-03-03*
