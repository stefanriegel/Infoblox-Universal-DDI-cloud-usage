---
phase: 27-azure-ddi-gaps
plan: 02
subsystem: azure-collectors
tags: [azure, ddi, hybrid-networking, vpn-gateway, private-link, virtual-wan, route-tables, tenants]

# Dependency graph
requires:
  - phase: 27-01
    provides: RED failing tests for 5 new Azure DDI collector functions

provides:
  - collect_azure_vpn_gateways() rewritten: resource_type azure-vnet-gateway, IP extraction from ip_configurations, gateway_type/vpn_type in details
  - collect_azure_private_link_services(): list_by_subscription(), IPs from ip_configurations, resource_type azure-private-link-service
  - collect_azure_virtual_wans(): virtual_wans.list(), ip_addresses=[], resource_type azure-virtual-wan
  - collect_azure_route_tables(): route_tables.list_all(), ip_addresses=[], resource_type azure-route-table
  - collect_azure_tenants(): tenants.list(), region=global, ip_addresses=[], resource_type azure-tenant
  - Fixed SubscriptionClient import: azure.mgmt.subscription (not azure.mgmt.resource)

affects:
  - 27-03 (wiring into provider.py and DDI_TYPES categorizer update)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - DDI-only collectors set ip_addresses=[] regardless of API response
    - Tenant collector takes subscription_client not network_client; region hardcoded to global
    - Private Link Services use list_by_subscription() not per-RG listing

key-files:
  created: []
  modified:
    - src/cloud_usage/providers/azure/collectors/hybrid_networking.py
    - src/cloud_usage/providers/azure/client_factory.py

key-decisions:
  - "collect_azure_tenants placed in hybrid_networking.py (same module as other new collectors) to minimize import churn; Plan 03 wires it into provider.py via subscription_client"
  - "collect_azure_vpn_gateways function name kept unchanged (only resource_type changed azure-vpn-gateway -> azure-vnet-gateway); minimal import churn for callers"
  - "SubscriptionClient import corrected: azure.mgmt.subscription (not azure.mgmt.resource); enables clients.subscription to be non-None for tenant collection"

patterns-established:
  - "Tenant collector pattern: subscription_client.tenants.list(), region='global', name=tenant.tenant_id, resource_id=tenant.id or f'/tenants/{tenant.tenant_id}'"
  - "Virtual WAN parent object (azure-virtual-wan) is distinct from WAN hub (azure-vwan-hub); both discovered separately"

requirements-completed: [AZUG-01, AZUG-02, AZUG-03, AZUG-04, AZUG-05]

# Metrics
duration: 5min
completed: 2026-03-07
---

# Phase 27 Plan 02: Azure DDI Collectors Implementation Summary

**5 Azure DDI collector functions added to hybrid_networking.py (4 new, 1 rewritten) plus SubscriptionClient import fix that unblocks tenant collection**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-07T16:30:00Z
- **Completed:** 2026-03-07T16:35:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Rewrote `collect_azure_vpn_gateways()` to emit `resource_type="azure-vnet-gateway"` with IP extraction from `ip_configurations` and `gateway_type`/`vpn_type` in details
- Added `collect_azure_private_link_services()`, `collect_azure_virtual_wans()`, `collect_azure_route_tables()`, `collect_azure_tenants()` — all 25 tests GREEN
- Fixed silent `ImportError` in `client_factory._create_subscription()`: `azure.mgmt.resource` -> `azure.mgmt.subscription`

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite collect_azure_vpn_gateways() and add 4 new collector functions** - `d2c9d92` (feat)
2. **Task 2: Fix SubscriptionClient import in client_factory.py** - `902f2d3` (fix)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `src/cloud_usage/providers/azure/collectors/hybrid_networking.py` - Rewrote vpn_gateways function; added private_link_services, virtual_wans, route_tables, tenants collectors
- `src/cloud_usage/providers/azure/client_factory.py` - Fixed SubscriptionClient import from azure.mgmt.subscription

## Decisions Made
- `collect_azure_tenants` placed in `hybrid_networking.py` for minimal import churn; Plan 03 wires via subscription_client
- Function name `collect_azure_vpn_gateways` kept unchanged (only resource_type string changed) to minimize caller churn
- SubscriptionClient import corrected to `azure.mgmt.subscription` — was silently returning None via `_try_create`, blocking tenant collection

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- None.

## Next Phase Readiness
- All 5 new collector functions implemented and tested (25 tests GREEN)
- Plan 03 can wire these into `provider.py` via `_safe_collect()` and update `DDI_TYPES` in categorizer
- `test_azure_ddi_gaps_in_ddi_types` still fails (DDI_TYPES update is Plan 03) — expected per plan

---
*Phase: 27-azure-ddi-gaps*
*Completed: 2026-03-07*
