---
phase: 28-gcp-ddi-gaps
plan: 02
subsystem: gcp-collectors
tags: [gcp, compute_v1, container_v1, ddi, networking, collectors]

# Dependency graph
requires:
  - phase: 28-01
    provides: RED TDD tests for GCPG-01..04 collectors
provides:
  - collect_gcp_reserved_ips with ip_addresses=[] (DDI-only fix)
  - collect_gcp_router_nats: one DDI object per NAT config per router
  - collect_gcp_target_vpn_gateways: one DDI object per target VPN gateway
  - collect_gcp_gke_cidr_ranges: up to 3 DDI objects per GKE cluster (control-plane, pod, service)
  - GCPClients.routers and GCPClients.target_vpn_gateways SDK client fields
affects:
  - 28-03 (wiring these collectors into provider.py and DDI_TYPES in categorizer)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - aggregated_list(project=project_id) pattern for RoutersClient and TargetVpnGatewaysClient (no Request wrapper needed)
    - Conditional CIDR emission: getattr chain for nested cluster config fields before emitting DDI object

key-files:
  created: []
  modified:
    - src/cloud_usage/providers/gcp/collectors/networking.py
    - src/cloud_usage/providers/gcp/collectors/token_free.py
    - src/cloud_usage/providers/gcp/client_factory.py
    - tests/test_gcp_collectors_networking.py

key-decisions:
  - "collect_gcp_reserved_ips: ip_addresses=[] (DDI-only); address string removed from collector output; details dict retains address_type/status/purpose for audit display"
  - "RoutersClient and TargetVpnGatewaysClient use aggregated_list(project=project_id) not aggregated_list(request=Request(...)) — no AggregatedListRoutersRequest class needed"
  - "Existing TestCollectGcpReservedIps tests updated: two assertions changed from ip_addresses==[address] to ip_addresses==[] to align with DDI-only fix"

patterns-established:
  - "CIDR-range DDI pattern: getattr chain for nested proto fields (private_cluster_config.master_ipv4_cidr_block, ip_allocation_policy.cluster/services_ipv4_cidr_block) with conditional emission"

requirements-completed: [GCPG-01, GCPG-02, GCPG-03, GCPG-04]

# Metrics
duration: 5min
completed: 2026-03-07
---

# Phase 28 Plan 02: GCP DDI Collectors Implementation Summary

**Four GCP DDI gap collectors implemented GREEN: ip_addresses fix on reserved IPs, Router NAT and Target VPN Gateway aggregated_list collectors, and conditional GKE CIDR range emission (up to 3 objects per cluster)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-07T17:40:00Z
- **Completed:** 2026-03-07T17:45:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Fixed `collect_gcp_reserved_ips` to emit `ip_addresses=[]` on all resources (both regional and global loops) — GCPG-01 DDI-only compliance
- Added `collect_gcp_router_nats` with `aggregated_list(project=...)` pattern; one `gcp-router-nat` resource per NAT config; routers with no NATs skipped — GCPG-03
- Added `collect_gcp_target_vpn_gateways` with same aggregated_list pattern; one `gcp-target-vpn-gateway` per gateway — GCPG-04
- Added `collect_gcp_gke_cidr_ranges` to token_free.py; conditionally emits control-plane/pod/service CIDR objects per cluster — GCPG-02
- Added `GCPClients.routers` and `GCPClients.target_vpn_gateways` fields + factory functions to client_factory.py
- All 56 tests across both test files pass GREEN (28 + 28)

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix reserved IPs DDI-only + add router_nats/target_vpn_gateways + client_factory** - `138464d` (feat)
2. **Task 2: Add collect_gcp_gke_cidr_ranges to token_free.py** - `83e2a96` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `src/cloud_usage/providers/gcp/collectors/networking.py` - DDI-only fix on collect_gcp_reserved_ips; two new aggregated_list collectors added
- `src/cloud_usage/providers/gcp/collectors/token_free.py` - collect_gcp_gke_cidr_ranges added after collect_gcp_gke_clusters
- `src/cloud_usage/providers/gcp/client_factory.py` - GCPClients.routers/.target_vpn_gateways fields; two new _create_* factory functions
- `tests/test_gcp_collectors_networking.py` - Updated two existing ip_addresses assertions to == [] (DDI-only)

## Decisions Made

- `collect_gcp_reserved_ips` DDI-only: ip_addresses=[] on all resources; address value removed from output. Existing test assertions updated to match (test_regional_address_fields and test_ip_extraction_populates_ip_addresses).
- RoutersClient and TargetVpnGatewaysClient use `aggregated_list(project=project_id)` directly — no Request wrapper class needed (unlike SubnetworksClient/DisksClient which use `AggregatedList*Request`).
- GKE CIDR emission uses getattr chain for nested proto message fields to safely handle missing private_cluster_config or ip_allocation_policy without AttributeError.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated two conflicting existing test assertions in test_gcp_collectors_networking.py**
- **Found during:** Task 1 (after implementing the DDI-only ip_addresses=[] fix)
- **Issue:** `TestCollectGcpReservedIps.test_regional_address_fields` asserted `ip_addresses == ["10.128.0.5"]` and `test_ip_extraction_populates_ip_addresses` asserted `ip_addresses == ["192.168.1.10"]` — both would fail after the DDI-only fix
- **Fix:** Changed both assertions to `ip_addresses == []` with a comment noting the GCPG-01 fix
- **Files modified:** `tests/test_gcp_collectors_networking.py`
- **Verification:** 28 tests in test_gcp_collectors_networking.py all pass GREEN
- **Committed in:** 138464d (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug: contradictory test assertions)
**Impact on plan:** Required to keep existing test suite consistent with DDI-only behavior change. No scope creep.

## Issues Encountered

None - both collectors implemented cleanly following the aggregated_list pattern from networking.py context.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All four GCPG collector functions exist and are unit-tested GREEN
- GCPClients dataclass has routers and target_vpn_gateways fields ready for provider.py wiring
- Plan 28-03 (provider wiring + DDI_TYPES categorizer update) can proceed immediately
- Categorizer test for gcp_ddi_gaps remains RED as expected (Plan 03 fixes that)

---
*Phase: 28-gcp-ddi-gaps*
*Completed: 2026-03-07*
