---
phase: 26-aws-ddi-gaps
plan: "01"
subsystem: tests
tags: [tdd, aws, ddi, collectors, categorizer, red-state]
dependency_graph:
  requires: []
  provides:
    - "Failing tests for all 7 AWSG requirements (15 resource types)"
    - "RED gate: plans 26-02 through 26-05 implement against these tests"
  affects:
    - tests/test_collectors_ddi.py
    - tests/test_categorizer.py
tech_stack:
  added: []
  patterns:
    - "moto @mock_aws for AWS service mocking"
    - "unittest.mock.MagicMock for unsupported moto services (DX, traffic policies)"
    - "TDD RED gate pattern: imports fail before implementations exist"
key_files:
  created: []
  modified:
    - tests/test_collectors_ddi.py
    - tests/test_categorizer.py
decisions:
  - "Direct Connect and traffic policy tests use MagicMock (not @mock_aws) since moto DX/traffic-policy support is limited or absent"
  - "Route53 resolver rule tests use SYSTEM type (not FORWARD) to avoid needing a resolver endpoint dependency in moto"
  - "IPAM pool test reads the public scope from describe_ipam_scopes rather than hardcoding scope ID"
  - "collect_ipam_resource_discoveries and collect_ipam_resource_discovery_associations imports added but no dedicated tests (moto IPAM resource discovery support limited; covered by import-level RED gate)"
metrics:
  duration: "2 min"
  completed: "2026-03-04"
  tasks_completed: 2
  files_modified: 2
---

# Phase 26 Plan 01: Failing Tests (TDD RED Gate) Summary

**One-liner:** Failing tests for all 15 Phase 26 AWS DDI resource types — ImportError on collector imports, AssertionError on DDI_TYPES membership, both confirmed RED before any implementation.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add Phase 26 collector tests to test_collectors_ddi.py | e18a3f7 | tests/test_collectors_ddi.py |
| 2 | Add Phase 26 DDI_TYPES assertions to test_categorizer.py | 462dba2 | tests/test_categorizer.py |

## RED State Verification

### test_collectors_ddi.py
```
ImportError: cannot import name 'collect_customer_gateways' from
'cloud_usage.providers.aws.collectors.ec2'
```
- Cause: ec2.py, route53.py, ipam.py, direct_connect.py modules lack the Phase 26 functions
- NOT a syntax error — correct RED state

### test_categorizer.py
```
AssertionError: Phase 26 DDI type 'aws-route53-traffic-policy-instance' missing from DDI_TYPES
1 failed, 62 passed
```
- Cause: categorizer.py DDI_TYPES does not yet contain Phase 26 types
- All 62 existing tests continue to pass — no regressions

## New Test Functions Added

### tests/test_collectors_ddi.py (13 new test functions)

| Function | AWSG | Resource Type |
|----------|------|---------------|
| test_collect_internet_gateways_discovers_attached_igw | AWSG-04 | aws-internet-gateway |
| test_collect_customer_gateways_discovers_cgw | AWSG-04 | aws-customer-gateway |
| test_collect_route_tables_discovers_all_including_main | AWSG-05 | aws-route-table |
| test_collect_resolver_endpoints_discovers_endpoints | AWSG-01 | aws-resolver-endpoint |
| test_collect_resolver_rules_discovers_rules | AWSG-02 | aws-resolver-rule |
| test_collect_resolver_rule_associations_discovers_associations | AWSG-02 | aws-resolver-rule-association |
| test_collect_ipams_discovers_ipam | AWSG-03 | aws-ipam |
| test_collect_ipam_scopes_discovers_scopes | AWSG-03 | aws-ipam-scope |
| test_collect_ipam_pools_discovers_pools | AWSG-03 | aws-ipam-pool |
| test_collect_health_checks_discovers_health_checks | AWSG-07 | aws-route53-health-check |
| test_collect_traffic_policies_discovers_policies | AWSG-07 | aws-route53-traffic-policy |
| test_collect_traffic_policy_instances_discovers_instances | AWSG-07 | aws-route53-traffic-policy-instance |
| test_collect_direct_connect_gateways_returns_resources | AWSG-06 | aws-direct-connect-gateway |

### tests/test_categorizer.py (1 new test function)

`test_ddi_types_contains_phase26_aws_types()` — asserts all 15 Phase 26 type strings are in DDI_TYPES.

## Decisions Made

1. **MagicMock for Direct Connect and traffic policies** — moto's DX and Route53 traffic policy support is absent/incomplete; MagicMock pattern is used instead of @mock_aws for these two collectors. Pattern consistent with existing `test_collect_route53_zones_private_detection_logic`.

2. **Resolver rule type = SYSTEM** — moto's route53resolver requires a resolver endpoint when creating FORWARD rules but allows SYSTEM rules without one, simplifying test setup without losing coverage.

3. **IPAM pool uses describe_ipam_scopes** — IPAM public scope ID is read dynamically rather than hardcoded, making the test robust against moto scope ID generation.

4. **collect_ipam_resource_discoveries / collect_ipam_resource_discovery_associations** — imports added to test file (ensuring ImportError RED gate), but dedicated moto-backed tests omitted since moto does not support IPAM resource discovery. The import-level gate is sufficient for the Nyquist RED requirement.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files verified:
- tests/test_collectors_ddi.py: exists, imports fail with ImportError (RED)
- tests/test_categorizer.py: exists, new test fails with AssertionError (RED)

Commits verified:
- e18a3f7 (test(26-01): add Phase 26 collector tests)
- 462dba2 (test(26-01): add Phase 26 DDI_TYPES assertions)
