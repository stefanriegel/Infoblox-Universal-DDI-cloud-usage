---
phase: 25-ip-methodology-fix
plan: "01"
subsystem: testing
tags: [tdd, ip-counting, nic-methodology, phase-25]
dependency_graph:
  requires: []
  provides:
    - test scaffold for count_nics_per_account() function (25-04)
    - test scaffold for DDI reclassification of eni/elastic-ip/nat-gateway/azure-nic/azure-public-ip (25-02)
    - test scaffold for nic_ip_count in EC2 collector (25-03)
    - test scaffold for network_interface_count in GCP VM collector (25-03)
  affects:
    - tests/test_ip_counter.py
    - tests/test_categorizer.py
    - tests/test_asset_dedup.py
    - tests/test_collectors_compute.py
    - tests/test_gcp_collectors_compute.py
tech_stack:
  added: []
  patterns:
    - TDD Wave 0 scaffold (RED tests before implementation)
    - pytest class-based test organization by provider/behavior
    - _make_resource() / _make_ddi_resource() helper pattern
key_files:
  created: []
  modified:
    - tests/test_ip_counter.py
    - tests/test_categorizer.py
    - tests/test_asset_dedup.py
    - tests/test_collectors_compute.py
    - tests/test_gcp_collectors_compute.py
decisions:
  - "count_nics_per_account returns same dict shape as deduplicate_ips_per_vpc for drop-in compatibility"
  - "DDI-category resources always contribute 0 regardless of ip_addresses or NIC count"
  - "Azure unattached NICs (vm_id=None) contribute 0 — only VM-attached NICs count"
  - "EC2 fallback: when no nic_ip_count in details, contribute 0 (plan 25-03 sets the field)"
  - "TestFoldEnisIntoParents removed — ENIs become DDI in Phase 25, folding is no longer needed"
metrics:
  duration_minutes: 4
  completed_date: "2026-03-03"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 5
---

# Phase 25 Plan 01: Test Scaffold for IP Methodology Fix Summary

**One-liner:** TDD Wave 0 scaffold for NIC-based IP counting and DDI reclassification of eni/elastic-ip/nat-gateway/azure-nic/azure-public-ip — all tests RED pending plans 25-02 through 25-04.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | Rewrite test_ip_counter.py for NIC-based counting | 4498ea8 | RED (ImportError on count_nics_per_account) |
| 2 | Update test_categorizer.py + test_asset_dedup.py for reclassification | 7d035a4 | MIXED (RED on 8 DDI tests, GREEN otherwise) |
| 3 | Add nic_ip_count + network_interface_count assertions to collector tests | 506424b | RED (KeyError/ModuleNotFoundError expected) |

## What Was Built

### Task 1: test_ip_counter.py (complete rewrite)

Replaced `TestDeduplicateIpsPerVpc` with six new test classes targeting `count_nics_per_account()`:

- `TestCountNicsPerAccountAWS` — EC2 nic_ip_count, fallback cases, multi-account per_account breakdown
- `TestCountNicsPerAccountAzure` — VM-attached vs unattached NIC (vm_id=None contributes 0)
- `TestCountNicsPerAccountGCP` — GCP VM network_interface_count, multi-project breakdown
- `TestCountNicsPerAccountDDIExclusion` — eni/elastic-ip/nat-gateway/azure-nic/azure-public-ip all contribute 0 when category=ddi
- `TestCountNicsPerAccountFallback` — rds-instance/ecs-task fall back to len(ip_addresses)
- `TestCountNicsPerAccountReturnShape` — dict shape compatibility with deduplicate_ips_per_vpc

### Task 2: test_categorizer.py + test_asset_dedup.py

**test_categorizer.py changes:**
- Added `TestCategorizeReclassifiedDDIResources` class with 5 tests for eni/elastic-ip/nat-gateway/azure-nic/azure-public-ip → category="ddi"
- Updated `test_azure_nic_with_ips_is_asset` → `test_azure_nic_with_ips_is_ddi` (assert category="ddi")
- Updated `test_azure_public_ip_with_ips_is_asset` → `test_azure_public_ip_with_ips_is_ddi` (assert category="ddi")
- Updated mixed batch assertion for azure-nic to expect "ddi" (was "asset")

**test_asset_dedup.py changes:**
- Removed `TestFoldEnisIntoParents` class (5 test methods deleted)
- Removed `fold_enis_into_parents` from import statement
- Added module docstring explaining removal rationale

### Task 3: test_collectors_compute.py + test_gcp_collectors_compute.py

**test_collectors_compute.py:**
- Added `TestEC2CollectorNicIpCount` with 4 tests:
  - 2 NICs with 1 IP each → nic_ip_count=2 (moto mock)
  - 1 NIC with 2 private IPs → nic_ip_count=2 (moto mock with secondary IP)
  - Fallback: no NetworkInterfaces + PrivateIpAddress only → nic_ip_count=1 (manual mock)
  - Fallback: no NetworkInterfaces + both addresses → nic_ip_count=2 (manual mock)

**test_gcp_collectors_compute.py:**
- Added `TestGCPVMCollectorNetworkInterfaceCount` with 4 tests:
  - 3 interfaces → network_interface_count=3
  - 1 interface → network_interface_count=1
  - No interfaces → network_interface_count=0
  - ip_addresses still populated alongside count (audit behavior preserved)

## Verification Results

| Command | Result |
|---------|--------|
| `pytest tests/test_ip_counter.py -x` | ImportError (RED — correct) |
| `pytest tests/test_categorizer.py -x` | 8 FAILED, 54 passed (RED on DDI reclassification tests — correct) |
| `pytest tests/test_asset_dedup.py -x` | 16 passed (GREEN — correct) |
| `pytest tests/test_collectors_compute.py -k "nic_ip_count"` | 1 FAILED, collected (RED — correct) |
| `pytest tests/test_gcp_collectors_compute.py -k "network_interface_count"` | 3 FAILED, collected (RED — correct) |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| tests/test_ip_counter.py | FOUND |
| tests/test_categorizer.py | FOUND |
| tests/test_asset_dedup.py | FOUND |
| tests/test_collectors_compute.py | FOUND |
| tests/test_gcp_collectors_compute.py | FOUND |
| Commit 4498ea8 (Task 1) | FOUND |
| Commit 7d035a4 (Task 2) | FOUND |
| Commit 506424b (Task 3) | FOUND |
