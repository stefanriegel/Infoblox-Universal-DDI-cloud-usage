---
phase: 25-ip-methodology-fix
plan: 02
subsystem: counting
tags: [categorizer, asset_dedup, ddi-types, eni, elastic-ip, nat-gateway, azure-nic, azure-public-ip, pipeline]

# Dependency graph
requires:
  - phase: 25-01
    provides: TDD scaffold for NIC-based IP counting and TestFoldEnisIntoParents already removed from test_asset_dedup.py
provides:
  - DDI_TYPES expanded with eni, elastic-ip, nat-gateway, azure-nic, azure-public-ip (5 new entries)
  - fold_enis_into_parents() deleted from asset_dedup.py
  - All three pipeline call sites (cli.py, scan.py, pages.py) clean of fold_enis_into_parents
affects:
  - 25-03 (NIC count tests now have correct categorization baseline)
  - 25-04 (ip_counter replacement can safely skip DDI types without special-casing ENI/EIP/NAT GW)
  - 26-27-28 (any new DDI types in cloud gap phases must be added to DDI_TYPES following this pattern)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - DDI_TYPES set literal is the single source of truth for DDI classification — add new types here, pipeline logic follows automatically
    - Rule 2 in _categorize_single fires before rule 4 (has_ips check), so DDI classification overrides asset classification even when ip_addresses is populated
    - Pipeline stages: exclude_managed_service_resources → deduplicate_assets → categorize_resources → deduplicate_ips_per_vpc (fold step removed permanently)

key-files:
  created: []
  modified:
    - src/cloud_usage/counting/categorizer.py
    - src/cloud_usage/counting/asset_dedup.py
    - src/cloud_usage/cli.py
    - src/cloud_usage/dashboard/routes/scan.py

key-decisions:
  - "ENI/EIP/NAT GW reclassified as DDI (not asset) — correct categorization replaces ad-hoc folding exclusion"
  - "fold_enis_into_parents() removed entirely — function and all three call sites deleted"
  - "ip_addresses fields not cleared on reclassified resources — remain populated for audit/Detail sheet display"

patterns-established:
  - "DDI reclassification pattern: add to DDI_TYPES set, remove any special-case handling at call sites"

requirements-completed: [METH-04]

# Metrics
duration: 3min
completed: 2026-03-03
---

# Phase 25 Plan 02: DDI Reclassification and ENI Folding Removal Summary

**ENI, elastic-ip, nat-gateway, azure-nic, azure-public-ip reclassified from asset to DDI in categorizer.py; fold_enis_into_parents() deleted from asset_dedup.py and all three pipeline call sites**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-03T22:34:10Z
- **Completed:** 2026-03-03T22:37:37Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added 5 new resource types to DDI_TYPES (eni, elastic-ip, nat-gateway, azure-nic, azure-public-ip) with Phase 25 comments
- Deleted fold_enis_into_parents() from asset_dedup.py (function + module docstring updated)
- Removed fold_enis_into_parents import and call from cli.py (pipeline renumbered Steps 1-4)
- Removed fold_enis_into_parents import and call from scan.py
- pages.py confirmed already clean — no changes needed
- 78 tests across test_categorizer.py and test_asset_dedup.py all GREEN

## Task Commits

Each task was committed atomically:

1. **Task 1: Add 5 resource types to DDI_TYPES in categorizer.py** - `7257048` (feat)
2. **Task 2: Remove fold_enis_into_parents from asset_dedup.py and all three call sites** - `402f1ce` (feat)

## Files Created/Modified

- `src/cloud_usage/counting/categorizer.py` - DDI_TYPES expanded with 5 new entries (7 lines added)
- `src/cloud_usage/counting/asset_dedup.py` - fold_enis_into_parents() function deleted; docstring updated to 2 pipeline stages
- `src/cloud_usage/cli.py` - Import and call removed; pipeline comments renumbered Steps 1-4
- `src/cloud_usage/dashboard/routes/scan.py` - Import and call removed

## Decisions Made

- ENI/EIP/NAT GW classified as DDI per METH-04: these are networking objects, not compute assets. Correct categorization is foundational — the new IP counter (plan 25-04) automatically excludes DDI types without any special-casing.
- ip_addresses fields left populated on reclassified resources for audit/Detail sheet display (no clearing needed — rule 2 fires before rule 4 in _categorize_single).
- pages.py was already clean; no changes required — the fold call was never added there.

## Deviations from Plan

None - plan executed exactly as written.

Note: test_cli.py has 5 pre-existing failures due to Python 3.9 venv vs. the Python 3.10+ version guard in cli.py main(). These failures existed before this plan and are unrelated to the fold_enis removal. STATE.md documents this as known non-blocking debt.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- categorizer.py DDI_TYPES is now correct baseline for plans 25-03 and 25-04
- Pipeline is clean: fold step gone, 3 remaining stages intact
- Plan 25-03 (NIC-counting tests) can proceed without risk of fold_enis conflicts
- Plan 25-04 (ip_counter replacement) will automatically exclude eni/elastic-ip/nat-gateway/azure-nic/azure-public-ip from IP count

---
*Phase: 25-ip-methodology-fix*
*Completed: 2026-03-03*

## Self-Check: PASSED

- FOUND: .planning/phases/25-ip-methodology-fix/25-02-SUMMARY.md
- FOUND: src/cloud_usage/counting/categorizer.py
- FOUND: src/cloud_usage/counting/asset_dedup.py
- FOUND commit: 7257048 (Task 1)
- FOUND commit: 402f1ce (Task 2)
