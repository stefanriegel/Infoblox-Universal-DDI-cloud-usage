---
plan: 12-02
phase: 12-scenario-engine
status: complete
completed: 2026-03-02
---

# Plan 12-02 Summary: Edge-Case Tests + Phase Success Criteria Acceptance Tests

## What was built

Extended `tests/nios/test_nios_scenarios.py` with 14 additional edge-case tests and 5 explicit Phase Success Criteria acceptance tests (SC-1 through SC-5). Confirmed scenarios.py implementation is correct against all boundary conditions.

## Key test additions

14 edge-case tests covering:
- `test_ip_total_uses_grid_counts_not_member_sum` — IP total correctness (grid not member sum)
- `test_hybrid_all_members_niosx` — boundary: all members NIOSX, only grid in NIOS sub
- `test_hybrid_all_members_nios` — boundary: no NIOSX members, niosx_sub.token_total == 0.0
- `test_scen01_scen03_same_ddi_and_ips` — DDI/IP equality across scenarios
- `test_migration_split_config_is_frozen` — FrozenInstanceError on mutation
- `test_hybrid_default_group_niosx` — default_group="niosx" routes unassigned to NIOSX
- `test_member_attribution_token_formula_by_group` — formula correctness per group
- `test_migration_split_config_default_group_is_nios` — MIGR-03 default
- `test_assignment_source_captured_in_suite` — MIGR-04 verbatim capture

5 explicit success criteria acceptance tests:
- `test_sc1_*` — current_grid with expected DDI/IP/token values
- `test_sc2_*` — combined_total exact arithmetic sum
- `test_sc3_*` — full_migration >= current_grid invariant
- `test_sc4_*` — default group recorded in member attribution
- `test_sc5_*` — migration_split_used identity capture

## Test results

- `test_nios_scenarios.py`: 27/27 passed (all Plan 01 + Plan 02 tests)
- Full nios suite: 92/92 passed (zero regressions)

## No code changes required

scenarios.py implementation from Plan 01 correctly passed all edge-case tests without modification. The implementation was correct from the first implementation.

## Spot-check verifications

- No formula constants (`DDI_DIVISOR`, `IP_DIVISOR`, `ASSET_DIVISOR`) redefined in scenarios.py
- `combined_total = nios_sub.token_total + niosx_sub.token_total` (exact additive assignment)
- All exports importable: compute_scenarios, MigrationSplitConfig, ScenarioResult, HybridScenarioResult, MemberScenarioRow, ScenarioSuite
- SC-3 invariant holds: full_migration.token_total (82.9231) >= current_grid.token_total (43.0000)
