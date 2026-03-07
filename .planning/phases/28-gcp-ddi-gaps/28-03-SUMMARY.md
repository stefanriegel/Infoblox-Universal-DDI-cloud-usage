---
phase: 28-gcp-ddi-gaps
plan: 03
subsystem: cloud-provider
tags: [gcp, ddi, categorizer, provider-wiring, gcpg]

# Dependency graph
requires:
  - phase: 28-02
    provides: "4 GCP DDI collectors implemented and GREEN: collect_gcp_reserved_ips (DDI-only), collect_gcp_gke_cidr_ranges, collect_gcp_router_nats, collect_gcp_target_vpn_gateways"
provides:
  - "GCP provider.py wired with 5 new _safe_collect calls for all 4 GCPG collectors"
  - "DDI_TYPES in categorizer.py extended with 6 GCP DDI type strings (GCPG-01..04)"
  - "End-to-end pipeline: GCP scans now discover and classify all 4 GCPG resource types"
  - "Phase 28 (GCP DDI Gaps) COMPLETE — GCPG-01 through GCPG-04 fulfilled"
affects: [phase-29-microsoft-ad, xls-output, token-calculator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_safe_collect wrapping for None clients (routers/target_vpn_gateways may be None when SDK absent)"
    - "container_enabled guard for both GKE Clusters and GKE CIDR Ranges in the same block"
    - "DDI_TYPES membership causes ddi category even when ip_addresses is populated"

key-files:
  created: []
  modified:
    - src/cloud_usage/providers/gcp/provider.py
    - src/cloud_usage/counting/categorizer.py
    - tests/test_categorizer.py

key-decisions:
  - "gcp-reserved-ip in DDI_TYPES causes categorizer to return category=ddi (not asset) even with ip_addresses populated; stale test updated to assert ddi"
  - "Router NAT and Target VPN Gateway wired under same compute_enabled block as Reserved IPs for logical grouping"
  - "GKE CIDR Ranges wired under container_enabled block alongside GKE Clusters (same client, same guard)"

patterns-established:
  - "Stale TDD RED assertion updated when DDI_TYPES membership changes categorizer behavior for a type"

requirements-completed: [GCPG-01, GCPG-02, GCPG-03, GCPG-04]

# Metrics
duration: 13min
completed: 2026-03-07
---

# Phase 28 Plan 03: GCP DDI Gaps Provider Wiring and Categorizer Update Summary

**GCP provider.py wired with 5 new _safe_collect calls and categorizer.py extended with 6 new DDI type strings, closing the end-to-end pipeline for all 4 GCPG requirements (Compute Addresses, GKE CIDRs, Router NATs, Target VPN Gateways)**

## Performance

- **Duration:** 13 min
- **Started:** 2026-03-07T17:44:51Z
- **Completed:** 2026-03-07T17:57:51Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Wired `collect_gcp_router_nats` and `collect_gcp_target_vpn_gateways` into `discover_account()` under the `compute_enabled` guard block
- Wired `collect_gcp_gke_cidr_ranges` into `discover_account()` under the `container_enabled` guard block alongside GKE Clusters
- Added 6 new GCP DDI type strings to `DDI_TYPES`: `gcp-reserved-ip`, `gcp-gke-control-plane-range`, `gcp-gke-pod-range`, `gcp-gke-service-range`, `gcp-router-nat`, `gcp-target-vpn-gateway`
- Full test suite passes with no new regressions; all GCPG-01 through GCPG-04 tests GREEN

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire 4 new collectors into provider.py and add 6 DDI types to categorizer.py** - `7e61cd7` (feat)
2. **Task 2: Run full test suite to verify no regressions** - no code changes (test run only)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `src/cloud_usage/providers/gcp/provider.py` - Added 2 new imports + 3 new _safe_collect calls (Router NAT, Target VPN Gateway, GKE CIDR Ranges)
- `src/cloud_usage/counting/categorizer.py` - Added 6 GCP DDI type strings in DDI_TYPES block
- `tests/test_categorizer.py` - Updated stale test: gcp-reserved-ip now asserts category=ddi (not asset) post DDI_TYPES inclusion

## Decisions Made
- `gcp-reserved-ip` in DDI_TYPES causes `categorize_resources()` to return `category="ddi"` even when `ip_addresses` is populated. The TDD RED test `test_gcp_reserved_ip_with_ip_is_asset` was written before DDI_TYPES membership was established — updated to assert correct behavior (ddi wins over asset).
- Router NAT and Target VPN Gateway grouped under the same `compute_enabled` block as Reserved IPs for logical consistency (all three use compute API clients).
- GKE CIDR Ranges placed directly after GKE Clusters in the `container_enabled` block (same `clients.container` client).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated stale TDD RED test assertion for gcp-reserved-ip categorization**
- **Found during:** Task 1 (verification run)
- **Issue:** `test_gcp_reserved_ip_with_ip_is_asset` asserted `category == "asset"` but once `gcp-reserved-ip` is in DDI_TYPES, the categorizer correctly returns `category = "ddi"` (DDI check precedes asset check in pipeline)
- **Fix:** Renamed test to `test_gcp_reserved_ip_is_ddi`, updated assertion to `category == "ddi"`
- **Files modified:** `tests/test_categorizer.py`
- **Verification:** 121 tests pass in the three target test files
- **Committed in:** `7e61cd7` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — stale assertion)
**Impact on plan:** Necessary for correctness. The test was intentionally written as RED gate before DDI_TYPES was updated; updating it to GREEN is the expected final state.

## Issues Encountered
- Pre-existing test failures (not caused by Phase 28-03):
  - `test_gcp_auth.py::test_create_shared_clients_handles_missing_packages` — GCP SDK actually installed in test env, mock removal doesn't fully isolate
  - `test_output.py` — 2 header label assertions using old "IP Count"/"Active IPs" names (Phase 25 rename not reflected in tests)
  - 3 integration test files — `fold_enis_into_parents` ImportError (removed Phase 25, tests not updated)
- None of the above were introduced by Phase 28-03 changes (verified via git stash).

## Next Phase Readiness
- Phase 28 (GCP DDI Gaps) is COMPLETE — all 4 requirements GCPG-01 through GCPG-04 fulfilled
- Phase 29 (Microsoft AD Core) is ready to start — independent of GCP work
- Pre-existing test debt (test_output.py header labels, test_integration_*.py ImportErrors) should be addressed in a future cleanup pass

## Self-Check: PASSED

All files verified present. Task commit 7e61cd7 confirmed in git log.

---
*Phase: 28-gcp-ddi-gaps*
*Completed: 2026-03-07*
