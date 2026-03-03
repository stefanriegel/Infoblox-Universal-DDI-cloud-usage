---
phase: 25-ip-methodology-fix
plan: 04
subsystem: counting
tags: [ip-counter, nic-counting, ec2, azure-nic, gcp-vm, ddi, xlsx-report, dashboard]

# Dependency graph
requires:
  - phase: 25-02
    provides: DDI reclassification of ENI/EIP/NAT GW/azure-nic/azure-public-ip
  - phase: 25-03
    provides: nic_ip_count (EC2) and network_interface_count (GCP) stored in resource.details
provides:
  - count_nics_per_account() function in ip_counter.py — NIC-based IP counting replacing deduplicate_ips_per_vpc()
  - All three call sites (cli.py, scan.py, pages.py) using count_nics_per_account()
  - "Address Records" label in XLS Detail sheet, XLS Summary sheet, dashboard summary cards, summary table headers
affects:
  - Phase 26 (AWS DDI Gaps) — IP counting pipeline complete; new resource types from Phase 26 can use len(ip_addresses) fallback
  - Phase 27 (Azure DDI Gaps) — same
  - Phase 28 (GCP DDI Gaps) — same

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "NIC-based IP counting: dispatch via resource_type to provider-specific details field; DDI category guard first; len(ip_addresses) fallback for non-VM assets"
    - "Drop-in function replacement: same return dict shape (total_unique_ips, per_account) allows replacing deduplicate_ips_per_vpc() without touching downstream consumers"

key-files:
  created: []
  modified:
    - src/cloud_usage/counting/ip_counter.py
    - src/cloud_usage/cli.py
    - src/cloud_usage/dashboard/routes/scan.py
    - src/cloud_usage/dashboard/routes/pages.py
    - src/cloud_usage/output/xlsx_report.py
    - src/cloud_usage/dashboard/templates/partials/summary_cards.html
    - src/cloud_usage/dashboard/templates/pages/summary.html

key-decisions:
  - "deduplicate_ips_per_vpc() retained in ip_counter.py as deprecated — not deleted, marked deprecated for reference"
  - "azure-nic branch kept in _get_nic_count() for defensive completeness even though azure-nic is now DDI (plan 25-02) and will be filtered before reaching _get_nic_count() in production"
  - "data-col='ips' and data-label in summary.html updated to 'Address Records' — JS sort logic uses data-col attribute, preserved unchanged"
  - "XLS Detail sheet header renamed IP Count -> Address Records; XLS Summary sheet Active IPs -> Address Records"
  - "Per-provider formula breakdown in summary_cards.html: '{{ data.ips }} Active IPs' label NOT changed — this is the raw data label in the formula breakdown, distinct from the card stat-label"

patterns-established:
  - "NIC dispatch pattern: check resource_type before returning details field count; always guard DDI category before calling dispatch"

requirements-completed: [METH-01, METH-02, METH-03, METH-04]

# Metrics
duration: 8min
completed: 2026-03-03
---

# Phase 25 Plan 04: IP Methodology Fix — Integration Summary

**count_nics_per_account() implemented and wired into all call sites; XLS report and dashboard labels updated from "Active IPs" to "Address Records"**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-03T22:43:14Z
- **Completed:** 2026-03-03T22:51:00Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 7

## Accomplishments

- Implemented count_nics_per_account() with full dispatch logic: EC2 reads nic_ip_count, Azure NICs read ip_configuration_count (VM-attached only; unattached contribute 0), GCP reads network_interface_count, DDI resources contribute 0, all other assets use len(ip_addresses) fallback
- Replaced deduplicate_ips_per_vpc() at all three call sites (cli.py, scan.py, pages.py) — return dict shape preserved for zero downstream changes
- Updated "Active IPs" label to "Address Records" in xlsx_report.py (2 places), summary_cards.html, and summary.html (2 headers) — data-col="ips" JS sort attributes preserved

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement count_nics_per_account() in ip_counter.py** - `69656a6` (feat)
2. **Task 2: Wire count_nics_per_account into all three call sites and update labels** - `7d9832b` (feat)

**Plan metadata:** (docs commit follows)

_Note: TDD tasks — tests already existed (RED on import error), implementation made them GREEN._

## Files Created/Modified

- `src/cloud_usage/counting/ip_counter.py` - Added count_nics_per_account() and _get_nic_count(); marked deduplicate_ips_per_vpc() deprecated
- `src/cloud_usage/cli.py` - Import and call updated; stderr label updated
- `src/cloud_usage/dashboard/routes/scan.py` - Import and call updated
- `src/cloud_usage/dashboard/routes/pages.py` - Import and call updated
- `src/cloud_usage/output/xlsx_report.py` - "IP Count" -> "Address Records" (Detail); "Active IPs" -> "Address Records" (Summary)
- `src/cloud_usage/dashboard/templates/partials/summary_cards.html` - "Active IPs" -> "Address Records" stat-label
- `src/cloud_usage/dashboard/templates/pages/summary.html` - "Active IPs" -> "Address Records" in both table headers

## Decisions Made

- deduplicate_ips_per_vpc() retained as deprecated (not deleted) for reference traceability
- azure-nic branch in _get_nic_count() kept for defensive completeness — it handles the case where an azure-nic resource reaches the function without DDI categorization (e.g., in unit tests with category="asset")
- data-col="ips" attributes in summary.html preserved — JavaScript sort logic depends on them

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Pre-existing Python 3.9 version guard causes 5 test_cli.py::TestMainFunction failures — documented in STATE.md as known non-blocking technical debt, not caused by this plan's changes
- Pre-existing integration test failures (test_integration_aws/azure/gcp.py import fold_enis_into_parents which was removed in plan 25-02) — not caused by this plan's changes

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 25 (IP Methodology Fix) is now complete — all 4 METH requirements fulfilled across plans 25-01 through 25-04
- Phase 26 (AWS DDI Gaps): IP counting pipeline ready; new resource types will use len(ip_addresses) fallback automatically
- Phase 27 (Azure DDI Gaps): same readiness
- Phase 28 (GCP DDI Gaps): same readiness

## Self-Check: PASSED

- FOUND: src/cloud_usage/counting/ip_counter.py
- FOUND: src/cloud_usage/cli.py
- FOUND: src/cloud_usage/dashboard/routes/scan.py
- FOUND: src/cloud_usage/output/xlsx_report.py
- FOUND: .planning/phases/25-ip-methodology-fix/25-04-SUMMARY.md
- FOUND commit 69656a6 (feat: implement count_nics_per_account)
- FOUND commit 7d9832b (feat: wire call sites, update labels)

---
*Phase: 25-ip-methodology-fix*
*Completed: 2026-03-03*
