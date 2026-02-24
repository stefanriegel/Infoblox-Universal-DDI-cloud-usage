---
phase: 04-gcp-provider
plan: 03
subsystem: discovery
tags: [gcp, compute-engine, cloud-sql, aggregatedList, forwarding-rules, googleapiclient]

# Dependency graph
requires:
  - phase: 04-gcp-provider
    plan: 01
    provides: GCPClients (instances, forwarding_rules, sqladmin), GCPDiscoveryProvider skeleton, _safe_collect, CloudResource schema
provides:
  - collect_gcp_vms with aggregatedList and network_i_p/nat_i_p IP extraction (Pitfall 6)
  - collect_gcp_forwarding_rules with aggregatedList and I_p_address extraction
  - collect_gcp_cloud_sql with googleapiclient discovery API and list_next pagination
affects: [04-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [aggregatedList for VM and forwarding rule collectors, googleapiclient discovery pagination via list_next, zone-to-region mapping via rsplit("-" 1)[0], I_p_address SDK field for forwarding rules]

key-files:
  created:
    - src/cloud_usage/providers/gcp/collectors/compute.py
    - src/cloud_usage/providers/gcp/collectors/database.py
    - tests/test_gcp_collectors_compute.py
    - tests/test_gcp_collectors_database.py
  modified: []

key-decisions:
  - "Forwarding rule IP uses getattr fallback chain (I_p_address, i_p_address, ip_address) for SDK attribute name resilience"
  - "Cloud SQL collector returns [] when sqladmin_service is None (graceful fallback when google-api-python-client not installed)"
  - "Mock forwarding rules use spec= to prevent MagicMock auto-attribute creation on fallback getattr calls"

patterns-established:
  - "GCP aggregatedList collector: iterate (key, scoped_list) tuples, check scoped_list.{resource_field} not empty, extract region from key"
  - "GCP zone-to-region: zone_name.rsplit('-', 1)[0] (e.g. 'us-central1-a' -> 'us-central1')"
  - "GCP Cloud SQL pagination: request = service.instances().list(), while request: response = request.execute(), request = list_next()"
  - "GCP IP extraction Pitfall 6: network_i_p for private, access_configs[].nat_i_p for public (NOT network_ip/nat_ip)"

requirements-completed: [DISC-03]

# Metrics
duration: 9min
completed: 2026-02-24
---

# Phase 4 Plan 03: GCP Compute and Database Collectors Summary

**VM, forwarding rule, and Cloud SQL collectors using aggregatedList and discovery API with Pitfall 6 IP extraction (network_i_p/nat_i_p) and list_next pagination**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-24T19:28:35Z
- **Completed:** 2026-02-24T19:38:19Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- collect_gcp_vms discovers compute instances via aggregatedList with private IP from network_i_p and public IP from access_config nat_i_p per Pitfall 6
- collect_gcp_forwarding_rules discovers load balancer forwarding rules via aggregatedList with I_p_address extraction across all regions including global
- collect_gcp_cloud_sql discovers Cloud SQL instances via googleapiclient discovery API with list_next pagination and private+public IP extraction from ipAddresses list
- 36 unit tests covering IP extraction, zone-to-region mapping, empty scoped lists, pagination, None service fallback, labels, and fallback resource IDs
- All 800 tests pass (36 new + 764 existing, zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: VM and forwarding rule collectors** - `c5ba0f6` (feat)
2. **Task 2: Cloud SQL collector** - `168f609` (feat)

## Files Created/Modified
- `src/cloud_usage/providers/gcp/collectors/compute.py` - VM and forwarding rule collectors using aggregatedList
- `src/cloud_usage/providers/gcp/collectors/database.py` - Cloud SQL collector using googleapiclient discovery API
- `tests/test_gcp_collectors_compute.py` - 24 tests for VMs (15) and forwarding rules (9)
- `tests/test_gcp_collectors_database.py` - 12 tests for Cloud SQL instances

## Decisions Made
- Forwarding rule IP extraction uses `getattr(rule, "I_p_address", None)` with fallback chain to `i_p_address` and `ip_address` for SDK attribute name resilience (proto field `IPAddress` may auto-generate differently)
- Cloud SQL collector returns `[]` when `sqladmin_service is None` as graceful fallback when google-api-python-client is not installed
- Forwarding rule mocks use `MagicMock(spec=[...])` to prevent auto-attribute creation on fallback getattr calls, ensuring None IP behavior is correctly tested

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed forwarding rule mock returning MagicMock instead of None for IP**
- **Found during:** Task 1 (forwarding rule tests)
- **Issue:** MagicMock auto-creates attributes on getattr, so the fallback chain `getattr(rule, "i_p_address", None)` returned a truthy MagicMock when I_p_address was set to None
- **Fix:** Used `MagicMock(spec=[...])` to constrain mock attributes, and set all three potential IP field names in the mock factory
- **Files modified:** tests/test_gcp_collectors_compute.py
- **Verification:** test_forwarding_rule_no_ip passes with empty ip_addresses
- **Committed in:** c5ba0f6 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug in test mock)
**Impact on plan:** Auto-fix necessary for correct mock behavior. No scope creep.

## Issues Encountered
None beyond the mock auto-attribute issue documented above.

## User Setup Required
None - no external service configuration required. GCP SDK packages were already added in Plan 04-01.

## Next Phase Readiness
- Compute and database collectors complete, ready for Plan 04-04 (integration wiring)
- 3 collector functions exported: collect_gcp_vms, collect_gcp_forwarding_rules, collect_gcp_cloud_sql
- All collectors follow established pattern: @retry_with_backoff(max_retries=3), return list[CloudResource]
- Plan 04-02 (networking/DNS/token-free) provides remaining collectors needed before Plan 04-04 integration

## Self-Check: PASSED

All 4 files verified present. Both task commits (c5ba0f6, 168f609) verified in git log. All 800 tests pass (36 new + 764 existing).

---
*Phase: 04-gcp-provider*
*Completed: 2026-02-24*
