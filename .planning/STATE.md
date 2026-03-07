---
gsd_state_version: 1.0
milestone: v1.7
milestone_name: Reference Parity
status: completed
stopped_at: Completed 28-03-PLAN.md
last_updated: "2026-03-07T17:59:53.791Z"
last_activity: "2026-03-07 — Completed 28-02: 4 GCP DDI collectors GREEN; 2 tasks, 4 files, 5 min"
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 15
  completed_plans: 15
  percent: 98
---

# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-03 after v1.7 milestone started)

**Core value:** Accurate, auditable UDDI token estimation from any source — cloud or NIOS Grid — customers must trust the numbers and understand exactly how they were derived.
**Current focus:** Phase 29 — Microsoft AD Core (Phase 28 complete)

## Current Position

Phase: 28 of 29 (GCP DDI Gaps) — COMPLETE (3/3 plans done)
Plan: 03 complete (28-03-PLAN.md) — provider wiring + 6 DDI types in categorizer; GCPG-01..04 fulfilled
Status: Phase 28 COMPLETE — proceed to Phase 29 (Microsoft AD Core)
Last activity: 2026-03-07 — Completed 28-03: GCP provider wiring + DDI_TYPES update; 2 tasks, 3 files, 13 min

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 4 (this milestone)
- Average duration: 5.3 min
- Total execution time: 21 min

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 25 | 01 | 4 min | 3 | 5 |
| 25 | 02 | 3 min | 2 | 4 |
| 25 | 03 | 6 min | 2 | 3 |
| 25 | 04 | 8 min | 2 | 7 |
| Phase 26 P01 | 2 | 2 tasks | 2 files |
| Phase 26 P02 | 5 | 2 tasks | 1 files |
| Phase 26 P03 | 4 min | 2 tasks | 2 files |
| Phase 26 P04 | 2min | 2 tasks | 3 files |
| Phase 26 P05 | 12min | 2 tasks | 2 files |
| Phase 27 P01 | 2 | 2 tasks | 2 files |
| Phase 27 P02 | 5 | 2 tasks | 2 files |
| Phase 27 P03 | 5 | 2 tasks | 2 files |
| Phase 28 P01 | 2 min | 2 tasks | 3 files |
| Phase 28 P02 | 5 | 2 tasks | 4 files |
| Phase 28 P03 | 13 min | 2 tasks | 3 files |

## Accumulated Context

### Patterns (carry forward)

- IIFE scripts in Jinja2 templates: scoped DOM logic, no globals, `data-col`/`data-value` for sort attributes
- `per_provider_details` (ddi/ips/assets/tokens) for formula display — always available from `_compute_summary()`
- Sort IIFE pattern: `querySelectorAll('tr.acct-row')` + `nextElementSibling` for detail row adjacency
- Section-scoped test assertions: slice relevant section from `response.text` before counting formula strings
- Template-only features: check what `_compute_summary()` already computes before adding backend work
- HX-Redirect pattern: return `Response(content="", status_code=200, headers={"HX-Redirect": "/tab/progress"})` — HTMX follows as full-page navigate, no hx-on JS needed

### Key v1.7 Decisions

- IP counting methodology: align with reference — count NIC/config objects (not unique IP addresses); remove standalone ENI/EIP/NAT GW IP counting from AWS
- Microsoft AD: full implementation matching reference `microsoft_ad.py` — DNS + DHCP + Users + Autodiscovery; CLI-only for v1.7 (dashboard tab deferred)
- Phase ordering: METH fix first (Phase 25) as it is foundational to correct IP counts in all providers; cloud DDI gap phases (26-28) can run in any order after 25; AD (Phase 29) is independent but placed last as it is a full new provider

### Key Phase 28 Decisions

- collect_gcp_gke_cidr_ranges imported at module level in token_free test — causes ImportError at collection time (stronger RED gate than in-method import) (plan 28-01)
- gcp-reserved-ip already in DDI_TYPES as asset type; GCPG-01 RED test asserts ip_addresses==[] on collector, not DDI_TYPES membership (plan 28-01)
- TestCollectGcpReservedIpsDdiOnly placed alongside existing TestCollectGcpReservedIps to group by collector module (plan 28-01)
- collect_gcp_reserved_ips: ip_addresses=[] (DDI-only); address string removed from collector output; details dict retains address_type/status/purpose for audit display (plan 28-02)
- RoutersClient and TargetVpnGatewaysClient use aggregated_list(project=project_id) not aggregated_list(request=Request(...)) — no AggregatedListRoutersRequest class needed (plan 28-02)
- GKE CIDR emission uses getattr chain for nested proto fields to safely handle missing private_cluster_config or ip_allocation_policy (plan 28-02)
- gcp-reserved-ip in DDI_TYPES causes category=ddi even with ip_addresses populated; stale TDD RED test updated to assert ddi (plan 28-03)
- Router NAT and Target VPN Gateway wired under compute_enabled block alongside Reserved IPs; GKE CIDR Ranges under container_enabled block alongside GKE Clusters (plan 28-03)

### Key Phase 27 Decisions

- collect_azure_tenants imported from hybrid_networking to trigger ImportError RED state; final module location confirmed in plan 27-02 (plan 27-01)
- azure-vnet-gateway replaces azure-vpn-gateway in AZUG-01; existing test updated with ExpressRoute gateway_type mock and ip 10.0.0.5 (plan 27-01)
- azure-vpn-gateway was never in DDI_TYPES — confirmed with not-in assertion that passes immediately (plan 27-01)
- collect_azure_vpn_gateways function name kept unchanged (only resource_type changed azure-vpn-gateway -> azure-vnet-gateway) for minimal import churn (plan 27-02)
- SubscriptionClient import corrected to azure.mgmt.subscription (was azure.mgmt.resource causing silent None via _try_create) (plan 27-02)
- collect_azure_tenants placed in hybrid_networking.py; takes subscription_client not network_client; region hardcoded to global (plan 27-02)
- Tenant deduplication via _tenants_collected instance bool on AzureDiscoveryProvider; skips re-collection on subsequent subscriptions to avoid inflated DDI count (plan 27-03)

### Key Phase 26 Decisions (so far)

- collect_route_tables counts ALL route tables including auto-created main route table — no filtering, matches reference implementation (plan 26-02)
- collect_customer_gateways uses direct API call — describe_customer_gateways does not support get_paginator() (plan 26-02)
- DDI-only collectors set ip_addresses=[] regardless of API response — no IP address concept in reference counting model (plan 26-02)
- Resolver functions use 3-arg signature (resolver_client, account_id, region) — route53resolver is per-region, distinct from global route53 (plan 26-03)
- collect_traffic_policies uses page.get('TrafficPolicySummaries') — real AWS API key, not 'TrafficPolicies' (plan 26-03)
- IPAM tests rewritten from @mock_aws/create_ipam to MagicMock — moto 5.1.21 does not implement create_ipam (plan 26-04)
- Direct Connect API uses camelCase response keys (directConnectGateways, directConnectGatewayId) — distinct from EC2 PascalCase (plan 26-04)
- Global collectors (IPAM, Direct Connect, Route53 Health Checks/Traffic Policies) placed ONCE per account before per-region loop (plan 26-05)
- IPAM uses ec2_global client (us-east-1), Route53 Resolver uses route53resolver client per-region, Direct Connect uses dx_client at us-east-1 (plan 26-05)

### Known Technical Debt (carry forward)

- DTC-V01/V02: DTC XML `__type` strings spec-derived, unverified against real DTC backup (v1.2 carry-over)
- REF-01: GCP 87-project production validation deferred — no live GCP environment available (v1.0 carry-over)
- Python 3.9 venv causes 8 pre-existing test failures on CLI `main()` version guard — known, non-blocking

### Key Phase 25 Decisions

- count_nics_per_account returns same dict shape as deduplicate_ips_per_vpc for drop-in compatibility
- DDI-category resources always contribute 0 regardless of ip_addresses or NIC count
- Azure unattached NICs (vm_id=None) contribute 0 — only VM-attached NICs count
- TestFoldEnisIntoParents removed — ENIs become DDI in Phase 25, folding is no longer needed
- ENI/EIP/NAT GW reclassified as DDI (not asset) — fold_enis_into_parents() removed entirely (plan 25-02)
- ip_addresses fields left populated on reclassified resources for audit/Detail sheet display (plan 25-02)
- nic_ip_count stored in details dict at collection time so ip_counter.py reads from CloudResource.details without re-iterating raw API data (plan 25-03)
- GCP ifaces list pre-computed before IP extraction loop to avoid double iteration over network_interfaces (plan 25-03)
- deduplicate_ips_per_vpc() retained as deprecated in ip_counter.py — not deleted, marked for reference (plan 25-04)
- azure-nic branch in _get_nic_count() kept for defensive completeness even though azure-nic is DDI and filtered before reaching it (plan 25-04)
- data-col="ips" JS sort attributes preserved in summary.html when label updated to "Address Records" (plan 25-04)

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 6 | Speed enhancement for large NIOS backup analysis | 2026-03-03 | c1de86a | [6-speed-enhancement-for-large-nios-backup-](./quick/6-speed-enhancement-for-large-nios-backup-/) |

## Session Log

- 2026-03-07: Phase 28 plan 03 complete — provider wiring + 6 DDI types in categorizer; Phase 28 (GCP DDI Gaps) COMPLETE; GCPG-01..04 fulfilled (2 tasks, 3 files, 13 min)
- 2026-03-07: Phase 28 plan 02 complete — 4 GCP DDI collectors GREEN; ip_addresses=[] fix, router_nats, target_vpn_gateways, gke_cidr_ranges; 56 tests pass (2 tasks, 4 files, 5 min)
- 2026-03-07: Phase 28 plan 01 complete — TDD RED gate: 13 new failing tests in 3 files; GCPG-01..04 covered; ImportError/AssertionError confirmed (2 tasks, 3 files, 2 min)
- 2026-03-07: Phase 27 plan 03 complete — provider wiring + 5 DDI types in categorizer; Phase 27 (Azure DDI Gaps) COMPLETE; AZUG-01..05 fulfilled (2 tasks, 2 files, 5 min)
- 2026-03-07: Phase 27 plan 02 complete — 5 Azure DDI collectors GREEN (1 rewritten, 4 new); SubscriptionClient import fixed (2 tasks, 2 files, 5 min)
- 2026-03-07: Phase 27 plan 01 complete — TDD RED gate: 4 new test classes + categorizer assertion for AZUG-01..05; ImportError/AssertionError confirmed (2 tasks, 2 files, 2 min)
- 2026-03-04: Phase 26 plan 05 complete — provider wiring: 15 DDI types in categorizer, 13 new _safe_collect() calls in provider; all AWSG-01..07 GREEN
- 2026-03-04: Phase 26 (AWS DDI Gaps) COMPLETE — all 5 plans done
- 2026-03-04: Phase 26 plan 04 complete — IPAM (5 collectors) and Direct Connect Gateway collector; AWSG-03/06 GREEN
- 2026-03-04: Phase 26 plan 03 complete — Route53 Resolver + health check/traffic policy collectors; AWSG-01/02/07 GREEN
- 2026-03-04: Phase 26 plan 02 complete — EC2 DDI collectors: collect_internet_gateways, collect_customer_gateways, collect_route_tables; AWSG-04/05 GREEN
- 2026-03-04: Phase 26 plan 01 complete — TDD RED gate for AWSG-01..07; 15 new types, 13 new collector tests, 1 new categorizer test
- 2026-03-03: Phase 25 (IP Methodology Fix) complete — all 4 plans done, METH-01 through METH-04 fulfilled
- 2026-03-03: v1.7 roadmap created — 5 phases (25–29), 28/28 requirements mapped, files written
- 2026-03-03: Milestone v1.7 Reference Parity started — defining requirements
- 2026-03-03: Phase 24 (v1.6 Wizard Navigation Fix) complete
- 2026-03-03: v1.5 milestone archived

## Session Continuity

Last session: 2026-03-07T17:59:53.789Z
Stopped at: Completed 28-03-PLAN.md
Resume file: None
