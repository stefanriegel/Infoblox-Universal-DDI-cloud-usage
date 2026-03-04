---
phase: 26-aws-ddi-gaps
plan: "04"
subsystem: aws-collectors
tags: [aws, ipam, direct-connect, boto3, moto, ddi]

# Dependency graph
requires:
  - phase: 26-01
    provides: "TDD RED tests for AWSG-01..07 in test_collectors_ddi.py"
  - phase: 26-02
    provides: "ec2.py with _get_name_tag/_tags_to_dict helpers"
provides:
  - "ipam.py with five global IPAM collector functions (AWSG-03)"
  - "direct_connect.py with collect_direct_connect_gateways (AWSG-06)"
  - "All six functions use 2-arg signature and region='global'"
affects:
  - "26-05 (provider wiring — will need to call these collectors)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Global collector pattern: 2-arg (client, account_id), region='global', ip_addresses=[]"
    - "MagicMock test pattern for AWS services moto does not implement (ipam, direct connect)"

key-files:
  created:
    - src/cloud_usage/providers/aws/collectors/ipam.py
    - src/cloud_usage/providers/aws/collectors/direct_connect.py
  modified:
    - tests/test_collectors_ddi.py

key-decisions:
  - "IPAM tests rewritten from @mock_aws/create_ipam to MagicMock — moto 5.1.21 does not implement create_ipam"
  - "Direct Connect uses camelCase response keys (directConnectGateways, directConnectGatewayId) — distinct from EC2 PascalCase convention"
  - "All six new collectors set ip_addresses=[] — IPAM and DX are DDI resources, not counted in IP methodology"

patterns-established:
  - "MagicMock paginator pattern: mock_paginator.paginate.return_value = [{'Key': [...]}]"

requirements-completed:
  - AWSG-03
  - AWSG-06

# Metrics
duration: 2min
completed: "2026-03-04"
---

# Phase 26 Plan 04: IPAM and Direct Connect Collectors Summary

**Five global EC2-based IPAM collector functions and one Direct Connect Gateway collector, all using 2-arg global signatures and MagicMock-based tests (moto 5.x lacks create_ipam support)**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-04T05:26:33Z
- **Completed:** 2026-03-04T05:28:xx Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created `ipam.py` with five AWSG-03 collectors: collect_ipams, collect_ipam_scopes, collect_ipam_pools, collect_ipam_resource_discoveries, collect_ipam_resource_discovery_associations
- Created `direct_connect.py` with AWSG-06 collector: collect_direct_connect_gateways (camelCase DX response keys)
- All six functions use 2-arg signature (client, account_id), region="global", ip_addresses=[], @retry_with_backoff(max_retries=3)
- Fixed 3 IPAM tests from @mock_aws pattern to MagicMock (moto 5.1.21 lacks create_ipam)
- All 59 DDI tests pass GREEN

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ipam.py with five IPAM collector functions** - `9f07142` (feat)
2. **Task 2: Create direct_connect.py with collect_direct_connect_gateways** - `941414b` (feat)

## Files Created/Modified
- `src/cloud_usage/providers/aws/collectors/ipam.py` - Five global IPAM collectors (AWSG-03)
- `src/cloud_usage/providers/aws/collectors/direct_connect.py` - Direct Connect Gateway collector (AWSG-06)
- `tests/test_collectors_ddi.py` - Rewrote 3 IPAM tests from @mock_aws to MagicMock

## Decisions Made
- IPAM tests rewritten from @mock_aws/create_ipam to MagicMock — moto 5.1.21 does not implement create_ipam; consistent with Direct Connect and Traffic Policy test approach
- Direct Connect API uses camelCase response keys — documented prominently in module docstring and inline comments to prevent future KeyError bugs
- All six collectors set ip_addresses=[] — IPAM and Direct Connect are DDI-category resources that do not contribute to IP counts

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Rewrote IPAM tests from @mock_aws to MagicMock**
- **Found during:** Task 1 (Create ipam.py) verification
- **Issue:** Tests used `@mock_aws` + `ec2.create_ipam()` which moto 5.1.21 has not implemented (`NotImplementedError: The create_ipam action has not been implemented`). All 3 IPAM tests failed.
- **Fix:** Replaced all three IPAM test functions with MagicMock-based paginator pattern, consistent with existing Direct Connect and Traffic Policy tests in the same file.
- **Files modified:** tests/test_collectors_ddi.py
- **Verification:** All 4 IPAM/DX tests pass GREEN; full 59-test suite passes with no regressions
- **Committed in:** 9f07142 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - test infrastructure bug)
**Impact on plan:** Necessary fix — tests written for a future moto version. MagicMock approach validates the same behavior. No scope creep.

## Issues Encountered
- moto 5.1.21 (latest) does not implement `create_ipam`, `describe_ipam_scopes`, or `create_ipam_pool`. Tests from plan 26-01 were written optimistically assuming moto support. MagicMock pattern used instead (same approach already established for DX and traffic policy tests).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- AWSG-03 (IPAM collectors) and AWSG-06 (Direct Connect) requirements fulfilled
- Both new modules ready to be wired into the AWS provider's discover_account() in plan 26-05
- Pattern established: new global AWS collectors go in their own file, use 2-arg signature, MagicMock for services moto doesn't support

---
*Phase: 26-aws-ddi-gaps*
*Completed: 2026-03-04*

## Self-Check: PASSED

- FOUND: src/cloud_usage/providers/aws/collectors/ipam.py
- FOUND: src/cloud_usage/providers/aws/collectors/direct_connect.py
- FOUND: commit 9f07142 (feat: ipam.py)
- FOUND: commit 941414b (feat: direct_connect.py)
