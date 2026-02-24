---
phase: 04-gcp-provider
plan: 02
subsystem: discovery, networking, dns
tags: [gcp, google-cloud-compute, google-cloud-dns, vpc, subnet, reserved-ip, dns-zone, dns-record, aggregatedList]

# Dependency graph
requires:
  - phase: 01-core-infrastructure
    provides: CloudResource schema, retry_with_backoff decorator
  - phase: 04-gcp-provider
    provides: GCPClients dataclass (networks, subnetworks, addresses, global_addresses), per-project DNS client creation, _safe_collect
provides:
  - collect_gcp_vpcs: VPC networks as DDI objects via global list()
  - collect_gcp_subnets: Subnets as DDI objects via aggregatedList across all regions
  - collect_gcp_reserved_ips: Reserved IPs from regional aggregatedList + global list combined
  - collect_gcp_dns_zones: DNS zones per-project via dns.Client.list_zones()
  - collect_gcp_dns_records: DNS records per-zone with full type enumeration and A/AAAA IP extraction
affects: [04-03, 04-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [aggregatedList for subnets and addresses, global list() for VPCs, per-project dns.Client for DNS, per-zone error isolation in DNS records, A/AAAA IP extraction from rrdatas]

key-files:
  created:
    - src/cloud_usage/providers/gcp/collectors/networking.py
    - src/cloud_usage/providers/gcp/collectors/dns.py
    - tests/test_gcp_collectors_networking.py
    - tests/test_gcp_collectors_dns.py
  modified: []

key-decisions:
  - "VPC networks use global list() (no aggregatedList for networks) with self_link as resource_id"
  - "Subnets use aggregatedList with empty scoped list skip per Pitfall 2"
  - "Reserved IPs combine regional aggregatedList + global list in a single collector function"
  - "DNS zones discovered via per-project dns.Client.list_zones() with visibility metadata"
  - "DNS records enumerate all types (SOA, NS, A, AAAA, CNAME, MX, TXT, etc.) per CONTEXT.md decision"
  - "A/AAAA record IP addresses extracted from rrdatas into ip_addresses field"
  - "Per-zone error isolation wraps each zone's record enumeration in try/except (consistent with Azure DNS pattern)"

patterns-established:
  - "GCP aggregatedList iteration: for region_key, scoped_list in client.aggregated_list() with empty-check before iteration"
  - "GCP DNS per-zone collection: dns_client.zone(zone_name).list_resource_record_sets() with try/except per zone"
  - "GCP resource_id format: self_link preferred, fallback to projects/{project}/regions/{region}/{type}/{name}"

requirements-completed: [DISC-03]

# Metrics
duration: 7min
completed: 2026-02-24
---

# Phase 4 Plan 02: GCP DDI & DNS Collectors Summary

**VPC, subnet, reserved IP, DNS zone, and DNS record collectors using aggregatedList for efficiency, with A/AAAA IP extraction and per-zone error isolation**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-24T19:28:30Z
- **Completed:** 2026-02-24T19:35:10Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- VPC networks collected as "gcp-vpc" DDI objects via global list() with self_link as resource_id
- Subnets collected as "gcp-subnet" DDI objects via aggregatedList across all regions in a single API call
- Reserved IPs collected from both regional aggregatedList and global list sources, with actual IP in ip_addresses field
- DNS zones discovered per-project via dns.Client.list_zones() with visibility metadata (public/private)
- DNS records enumerate all types including SOA and NS (no filtering), with A/AAAA IPs extracted from rrdatas
- Per-zone error isolation prevents single zone failure from blocking entire project DNS collection
- All 5 collector functions use @retry_with_backoff(max_retries=3) for transient error resilience
- 37 unit tests with unittest.mock covering all collectors (21 networking + 16 DNS)
- All 764 tests pass (37 new + 727 existing, zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: VPC, subnet, and reserved IP collectors** - `f24274f` (feat)
2. **Task 2: DNS zone and record collectors** - `6c9ab44` (feat)

## Files Created/Modified
- `src/cloud_usage/providers/gcp/collectors/networking.py` - VPC, subnet, and reserved IP collectors using aggregatedList
- `src/cloud_usage/providers/gcp/collectors/dns.py` - DNS zone and record collectors with per-zone error isolation
- `tests/test_gcp_collectors_networking.py` - 21 tests for VPC, subnet, and reserved IP collectors
- `tests/test_gcp_collectors_dns.py` - 16 tests for DNS zone and record collectors

## Decisions Made
- VPC networks use global `list()` (not aggregatedList, which is not available for networks) with `self_link` as resource_id, falling back to constructed path when self_link is None
- Subnets use `aggregatedList` with empty scoped list skip per Pitfall 2 (GCP returns empty scoped lists for regions with no resources)
- Reserved IPs combine two sources in a single collector function: regional addresses via `aggregatedList` and global addresses via `list()`
- DNS zones use per-project `dns.Client.list_zones()` -- the dns.Client is created per-project in `discover_account()` per Pitfall 1
- DNS records enumerate ALL record types (SOA, NS, A, AAAA, CNAME, MX, TXT, SRV, etc.) per CONTEXT.md decision -- no filtering
- A/AAAA record IP addresses extracted from `record_set.rrdatas` into `ip_addresses` field; other record types get empty list
- Per-zone error isolation wraps each zone's record enumeration in try/except, logs warning, and continues to next zone (consistent with Azure DNS pattern)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None - all modules created and tests pass. The PYTHONPATH=src approach is required for running tests (no conftest.py or pyproject.toml with path configuration).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- DDI collectors (VPCs, subnets) and DNS collectors (zones, records) complete and ready for wiring into discover_account()
- Reserved IP collector combines both regional and global sources for comprehensive coverage
- Plans 03-04 will add compute, database, and token-free collectors, then wire all collectors into the provider
- All 5 collector functions follow the established pattern: @retry_with_backoff, return list[CloudResource], provider="gcp"

## Self-Check: PASSED

All 4 files verified present. Both task commits (f24274f, 6c9ab44) verified in git log. All 764 tests pass (37 new + 727 existing).

---
*Phase: 04-gcp-provider*
*Completed: 2026-02-24*
