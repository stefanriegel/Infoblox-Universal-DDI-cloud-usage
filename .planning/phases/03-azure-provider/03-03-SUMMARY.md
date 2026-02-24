---
phase: 03-azure-provider
plan: 03
subsystem: discovery
tags: [azure, compute, database, paas, hybrid-networking, vmss, aks, cosmos-db, sql, redis, app-service, functions, load-balancer, firewall, bastion, expressroute, vpn, vwan]

# Dependency graph
requires:
  - phase: 01-core-infrastructure
    provides: CloudResource schema, retry_with_backoff decorator, error taxonomy
  - phase: 03-azure-provider (plan 01)
    provides: _extract_resource_group utility, AzureClients factory, provider skeleton
provides:
  - VM collector with NIC ID cross-reference (no inline resolution)
  - VMSS instance enumerator with per-instance IP extraction
  - 10 hybrid networking collectors (LBs, app gateways, firewalls, NAT gateways, private endpoints, VNet peerings, ExpressRoute, VPN gateways, Virtual WAN hubs, Bastion hosts)
  - 5 database collectors (Azure SQL server+DB, Cosmos DB, MySQL Flexible, PostgreSQL Flexible, Redis)
  - 6 PaaS collectors (App Service, Functions, Container Instances, Container Apps, AKS, API Management)
affects: [03-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [VMSS per-instance enumeration with NIC IP extraction, PaaS databases with ip_addresses=[] (IPs via private endpoints), App Service inbound+outbound IP parsing from comma-separated strings, Container Apps soft dependency with graceful SDK fallback, VPN gateway per-RG iteration from VNet resource groups]

key-files:
  created:
    - src/cloud_usage/providers/azure/collectors/compute.py
    - src/cloud_usage/providers/azure/collectors/hybrid_networking.py
    - src/cloud_usage/providers/azure/collectors/database.py
    - src/cloud_usage/providers/azure/collectors/paas.py
    - tests/test_azure_collectors_compute.py
    - tests/test_azure_collectors_hybrid_networking.py
    - tests/test_azure_collectors_database.py
    - tests/test_azure_collectors_paas.py
  modified: []

key-decisions:
  - "VMs set ip_addresses=[] with NIC IDs in details for cross-reference -- NICs are collected separately as standalone assets"
  - "VMSS instances enumerated individually per scale set with per-instance NIC IP extraction for accurate counting"
  - "All PaaS databases (SQL, Cosmos, MySQL, PostgreSQL) set ip_addresses=[] -- IPs attributed via private endpoints per CONTEXT.md"
  - "Redis includes static_ip in ip_addresses when set, otherwise empty (host_name is DNS)"
  - "App Services and Functions parse both inbound_ip_addresses and outbound_ip_addresses (comma-separated) with deduplication"
  - "Container Apps uses collect_azure_container_apps_with_client pattern -- accepts pre-created client from factory, returns [] if client is None"
  - "VPN gateways iterated per unique resource group derived from VNet discovery (no subscription-level API)"
  - "VNet peerings iterated per discovered VNet with per-VNet error isolation"

patterns-established:
  - "Azure compute: VMs reference NICs by ID, VMSS enumerates instances individually"
  - "Azure PaaS databases: ip_addresses=[] universally, private endpoints handle IP attribution"
  - "Azure web apps: kind-based filtering separates App Services from Functions"
  - "Azure hybrid networking: per-VNet and per-RG iteration for resources without subscription-level list"

requirements-completed: [DISC-02]

# Metrics
duration: 14min
completed: 2026-02-24
---

# Phase 3 Plan 03: Azure Compute, Database, PaaS, and Hybrid Networking Collectors Summary

**20+ Azure collectors covering VMs, VMSS instances, 5 database types, 6 PaaS services, and 10 hybrid networking resource types with 52 unit tests**

## Performance

- **Duration:** 14 min
- **Started:** 2026-02-24T17:01:48Z
- **Completed:** 2026-02-24T17:16:42Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- VM collector discovers VMs with NIC ID references without inline resolution (consistent with NICs-as-standalone-assets pattern)
- VMSS collector enumerates individual instances per scale set with per-instance NIC IP extraction for accurate IP counting
- 10 hybrid networking collectors: load balancers (public/internal detection), app gateways, firewalls, NAT gateways, private endpoints (with custom DNS IP extraction), VNet peerings, ExpressRoute circuits, VPN gateways, Virtual WAN hubs, and Bastion hosts
- 5 database collectors: Azure SQL (server + database resources), Cosmos DB, MySQL Flexible Servers, PostgreSQL Flexible Servers, Redis Cache (with static_ip support)
- 6 PaaS collectors: App Services and Functions with inbound+outbound IP parsing, Container Instances with IP extraction, Container Apps with graceful SDK fallback, AKS clusters with node count aggregation, API Management with public+private IP extraction
- All collectors use @retry_with_backoff(max_retries=3) and return list[CloudResource]
- 52 unit tests covering all resource types, edge cases, error handling, and IP extraction

## Task Commits

Each task was committed atomically:

1. **Task 1: Compute and hybrid networking collectors** - `50ab49a` (feat)
2. **Task 2: Database and PaaS collectors** - `03c7555` (feat)

## Files Created/Modified
- `src/cloud_usage/providers/azure/collectors/compute.py` - VM and VMSS instance collectors
- `src/cloud_usage/providers/azure/collectors/hybrid_networking.py` - 10 networking/infrastructure collectors (LBs, gateways, firewalls, endpoints, peerings, ExpressRoute, VPN, VWAN, Bastion)
- `src/cloud_usage/providers/azure/collectors/database.py` - SQL, Cosmos DB, MySQL, PostgreSQL, Redis collectors
- `src/cloud_usage/providers/azure/collectors/paas.py` - App Service, Functions, Container Instances, Container Apps, AKS, API Management collectors
- `tests/test_azure_collectors_compute.py` - 9 tests for VM and VMSS collectors
- `tests/test_azure_collectors_hybrid_networking.py` - 20 tests for all hybrid networking collectors
- `tests/test_azure_collectors_database.py` - 8 tests for all database collectors
- `tests/test_azure_collectors_paas.py` - 15 tests for all PaaS collectors

## Decisions Made
- VMs store NIC IDs in details but set ip_addresses=[] -- IPs are attributed via NIC collector (consistent with NICs-as-standalone-assets from CONTEXT.md)
- VMSS instances are individually enumerated per scale set with per-instance NIC IP extraction (per CONTEXT.md: "Enumerate individual VM instances within each VMSS for accurate IP counting")
- All PaaS databases set ip_addresses=[] because IPs are attributed via private endpoints collected separately (per CONTEXT.md PaaS IP extraction decision)
- Redis includes static_ip when present, otherwise ip_addresses=[] (host_name is DNS, not IP)
- App Services and Functions use shared _extract_web_app_ips() helper parsing comma-separated inbound/outbound IP strings with deduplication
- Container Apps provides both a no-client fallback (collect_azure_container_apps) and a client-based collector (collect_azure_container_apps_with_client) for graceful SDK degradation
- VPN gateways use per-RG iteration derived from discovered VNet resource groups (no subscription-level API exists)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added sys.path.insert for test imports**
- **Found during:** Task 1
- **Issue:** Test files couldn't import cloud_usage module because the package is not installed via pip (it's in src/ directory). Existing Plan 01 tests use `sys.path.insert(0, str(Path(__file__).parent.parent / "src"))` pattern.
- **Fix:** Added the same sys.path.insert pattern to all 4 new test files
- **Files modified:** All 4 test files
- **Verification:** Tests import and pass correctly
- **Committed in:** 50ab49a, 03c7555

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for test execution. No scope creep.

## Issues Encountered
None -- all modules created and tests pass on first run.

## User Setup Required
None -- no external service configuration required.

## Next Phase Readiness
- All Azure resource collectors complete (Plans 02 + 03 cover DDI, DNS, networking, compute, database, PaaS, and hybrid networking)
- Plan 04 will wire collectors into AzureDiscoveryProvider.discover_account(), add token-free collectors, extend categorizer, and delete legacy code
- 20+ collector functions ready for wiring with ~52 tests from this plan + ~67 tests from Plan 02

## Self-Check: PASSED
