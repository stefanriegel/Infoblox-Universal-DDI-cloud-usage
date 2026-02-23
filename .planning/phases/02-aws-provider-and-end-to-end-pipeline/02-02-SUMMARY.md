---
phase: 02-aws-provider-and-end-to-end-pipeline
plan: 02
subsystem: counting
tags: [tdd, categorizer, ip-counter, asset-dedup, token-calculator, ceiling-division]

# Dependency graph
requires:
  - phase: 01-core-infrastructure
    provides: "CloudResource dataclass schema (resource.py)"
provides:
  - "categorize_resources() -- DDI/IP/Asset/excluded classification"
  - "count_ips() -- private/public IP counting"
  - "deduplicate_ips_per_vpc() -- per-VPC IP space deduplication with per-account breakdown"
  - "fold_enis_into_parents() -- ENI attachment folding"
  - "exclude_managed_service_resources() -- EKS tag-based exclusion"
  - "deduplicate_assets() -- cross-account RAM-shared resource dedup"
  - "calculate_tokens() -- ceiling division formula (DDI/25 + IPs/13 + Assets/3)"
  - "calculate_account_tokens() -- per-account token calculation from resources"
  - "calculate_provider_tokens() -- provider-level aggregation"
affects: [02-05-output-pipeline, 02-06-integration]

# Tech tracking
tech-stack:
  added: [ipaddress (stdlib)]
  patterns: [TDD RED-GREEN-REFACTOR, ceiling division with zero guard, per-VPC IP space dedup]

key-files:
  created:
    - src/cloud_usage/counting/__init__.py
    - src/cloud_usage/counting/categorizer.py
    - src/cloud_usage/counting/ip_counter.py
    - src/cloud_usage/counting/asset_dedup.py
    - src/cloud_usage/counting/token_calculator.py
    - tests/test_categorizer.py
    - tests/test_ip_counter.py
    - tests/test_asset_dedup.py
    - tests/test_token_calculator.py
  modified: []

key-decisions:
  - "Categorizer uses type-to-category mapping dicts (DDI_TYPES, TOKEN_FREE_TYPES) for clarity and easy extension"
  - "IP counter uses ipaddress stdlib module for private/public classification and validation"
  - "Per-VPC dedup key is (vpc_id_or_account_id, ip_address) tuple in a set for O(1) dedup"
  - "Tag-based exclusion checks prefix match and exact match patterns separately for EKS tags"
  - "DDI and token-free types are exempt from tag-based managed service exclusion"
  - "Token ceiling division uses if count > 0 else 0 guard (not max(1, ...))"

patterns-established:
  - "TDD module pattern: test file first with all cases, then minimal implementation, then refactor"
  - "Counting pipeline stages are composable functions that mutate CloudResource in-place and return the list"
  - "Each dedup/exclusion function preserves existing skip_reason on already-excluded resources"

requirements-completed: [IP-01, IP-02, IP-03, ASSET-06, TOKEN-01, TOKEN-02, TOKEN-03]

# Metrics
duration: 5min
completed: 2026-02-23
---

# Phase 2 Plan 02: Counting Pipeline Summary

**TDD-built resource categorizer, per-VPC IP counter, ENI-folding asset dedup, and ceiling-division token calculator with 74 passing tests**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-23T20:58:31Z
- **Completed:** 2026-02-23T21:03:37Z
- **Tasks:** 4 (each with RED-GREEN TDD cycle)
- **Files created:** 9

## Accomplishments
- Resource categorizer classifies DDI/IP/Asset/excluded with special cases (orphaned DHCP, VPC-attached Lambda)
- IP counter extracts and de-duplicates IPs per VPC IP space with per-account breakdown
- Asset dedup pipeline: ENI folding, EKS tag-based exclusion, cross-account RAM-shared dedup
- Token calculator with ceiling division formula producing correct results (100 DDI + 200 IPs + 50 assets = 37 tokens verified)
- 74 tests covering all edge cases (boundaries, empty inputs, shared resources, IPv6)

## Task Commits

Each task was committed atomically with TDD RED then GREEN commits:

1. **Task 1: Resource Categorizer**
   - RED: `dcdb115` (test) -- 18 failing tests for categorization rules
   - GREEN: `2557a14` (feat) -- Implementation passing all 18 tests

2. **Task 2: IP Counter**
   - RED: `78c52a9` (test) -- 16 failing tests for IP counting and dedup
   - GREEN: `24aca32` (feat) -- Implementation passing all 16 tests

3. **Task 3: Asset De-duplication**
   - RED: `b0ff7b0` (test) -- 18 failing tests for ENI folding, tag exclusion, cross-account dedup
   - GREEN: `b898b55` (feat) -- Implementation passing all 18 tests

4. **Task 4: Token Calculator**
   - RED: `dd13b86` (test) -- 22 failing tests for ceiling division and aggregation
   - GREEN: `148280a` (feat) -- Implementation passing all 22 tests

## Files Created/Modified
- `src/cloud_usage/counting/__init__.py` -- Package init with module documentation
- `src/cloud_usage/counting/categorizer.py` -- DDI/IP/Asset categorization with DDI_TYPES and TOKEN_FREE_TYPES mappings
- `src/cloud_usage/counting/ip_counter.py` -- IP extraction with ipaddress stdlib, per-VPC dedup using (vpc_id, ip) tuples
- `src/cloud_usage/counting/asset_dedup.py` -- ENI folding, EKS tag exclusion, RAM-shared resource dedup
- `src/cloud_usage/counting/token_calculator.py` -- ceiling(DDI/25) + ceiling(IPs/13) + ceiling(Assets/3) with zero guard
- `tests/test_categorizer.py` -- 18 tests: DDI types, token-free, orphaned DHCP, assets, Lambda special case
- `tests/test_ip_counter.py` -- 16 tests: private/public, per-VPC dedup, IPv6, per-account breakdown
- `tests/test_asset_dedup.py` -- 18 tests: ENI folding, EKS tags, DDI exemption, cross-account dedup
- `tests/test_token_calculator.py` -- 22 tests: boundaries, zero-count, large mixed, per-account, provider aggregation

## Decisions Made
- Categorizer uses dict-based type mappings for easy extension when new resource types are added
- IP counter uses ipaddress stdlib module for IP validation and private/public classification
- Per-VPC dedup uses (vpc_id_or_account_id, ip_address) tuple as set key for O(1) membership check
- Tag-based exclusion exempts DDI and token-free types (only managed assets can be excluded)
- Token calculator uses `if count > 0 else 0` guard per user decision (not legacy `max(1, ...)` pattern)
- calculate_account_tokens accepts optional deduplicated_ip_count to integrate with per-VPC dedup pipeline

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Counting pipeline is complete and ready for integration with AWS resource collectors (Plans 03, 04)
- Output pipeline (Plan 05) can consume categorized resources and token calculations
- End-to-end integration (Plan 06) can wire discovery -> counting -> tokens -> report

## Self-Check: PASSED

- All 9 created files verified present on disk
- All 8 commit hashes (dcdb115, 2557a14, 78c52a9, 24aca32, b0ff7b0, b898b55, dd13b86, 148280a) verified in git log
- 74/74 tests passing
- Verification commands produce expected output (total_tokens=0 and total_tokens=37)

---
*Phase: 02-aws-provider-and-end-to-end-pipeline*
*Completed: 2026-02-23*
