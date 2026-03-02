---
plan: 12-01
phase: 12-scenario-engine
status: complete
completed: 2026-03-02
---

# Plan 12-01 Summary: nios.scenarios — Core Implementation + TDD

## What was built

Implemented `src/cloud_usage/nios/scenarios.py` — the Phase 12 scenario engine module — from scratch using TDD. All dataclasses and the public `compute_scenarios()` function are implemented and tested.

## Key files created

- `src/cloud_usage/nios/scenarios.py` — 270-line module with:
  - `MigrationSplitConfig` frozen dataclass (frozen tuple fields, default_group="nios", assignment_source="yaml")
  - `ScenarioResult`, `HybridScenarioResult`, `MemberScenarioRow`, `ScenarioSuite` frozen dataclasses
  - `compute_scenarios(count_result, split_config=None) -> ScenarioSuite` public API
- `tests/nios/test_nios_scenarios.py` — 27 tests covering all 5 success criteria, MIGR-01/03/04, and edge cases

## Test results

- `test_nios_scenarios.py`: 27/27 passed
- Full nios suite: 92/92 passed (zero regressions across Phases 10, 11, 12)

## Requirements addressed

- SCEN-01: `current_grid` — NIOS Object formula (DDI/50 + IPs/25 + Assets/13) applied to total DDI + global Active IPs
- SCEN-02: `hybrid_uddi` — sub-totals computed separately, `combined_total = nios_sub + niosx_sub` (exact arithmetic sum)
- SCEN-03: `full_migration` — UDDI native formula (DDI/25 + IPs/13 + Assets/3), always >= current_grid
- MIGR-01: `MigrationSplitConfig.niosx_members` — exact string match against member_hostname
- MIGR-03: `default_group="nios"` — configurable, default "nios"
- MIGR-04: `ScenarioSuite.migration_split_used` — identity capture of input split_config

## Key design decisions honored

- Grid-level objects (`grid_counts`, member_hostname="__grid__") always go to NIOS sub-total in hybrid scenario
- Active IP total for SCEN-01/03 uses `grid_counts.active_ip_count` (global dedup); never sums member IPs
- Formula functions imported from `counter.py`; no constants redefined in `scenarios.py`
- `combined_total` is arithmetic sum of sub-totals (not re-computed from aggregated inputs)
