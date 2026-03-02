---
phase: 11-filter-and-counter
plan: "03"
subsystem: nios-counter-gap-closure
tags: [bug-fix, gap-closure, empirical-verification, count-02]
dependency_graph:
  requires: ["11-01", "11-02"]
  provides: ["correct-active-ip-count", "zf-reference-value"]
  affects: ["Phase 12 Scenario Engine", "REQUIREMENTS.md COUNT-02"]
tech_stack:
  added: []
  patterns:
    - "Separate elif clauses per family when raw_attrs keys differ between types"
    - "Empirical verification against real backup before locking reference values"
key_files:
  created: []
  modified:
    - src/cloud_usage/nios/filter.py
    - src/cloud_usage/nios/counter.py
    - tests/nios/test_nios_filter.py
    - tests/nios/test_nios_counter.py
    - .planning/REQUIREMENTS.md
decisions:
  - "FilterConfig default lease_states = ('active',) only — static binding_state is a manually-configured DHCP static assignment, not a 'new or renew DHCP lease' per UDDI licensing docs"
  - "HOST_ADDRESS raw_attrs key is 'address' (not 'ip_address') — empirically confirmed from ZF Friedrichshafen backup"
  - "ZF reference value after fix: 304,730 unique Active IPs (4-source dedup: active leases + fixed_address[ip_address] + host_address[address] + network reservations)"
  - "GAP-01 (COUNT-02 reference value mismatch) is RESOLVED"
metrics:
  duration: "~5 minutes (includes empirical ZF backup run)"
  completed_date: "2026-03-02"
  tasks: 3
  files_modified: 5
---

# Phase 11 Plan 03: GAP-01 Fix (COUNT-02 Root Causes) Summary

**One-liner:** Fixed two COUNT-02 root causes — FilterConfig default lease_states corrected to `('active',)` and HOST_ADDRESS raw_attrs key corrected to `'address'`; empirical ZF backup run confirms 304,730 unique Active IPs.

## What Was Built

This plan closed GAP-01 (COUNT-02 reference value mismatch) by fixing two bugs in the NIOS
counter implementation, updating all tests to reflect the corrections, and running an empirical
verification against the ZF Friedrichshafen reference backup to establish the definitive
Active IP reference value.

### Bug Fix 1: FilterConfig default lease_states

`FilterConfig` default was `("active", "static")`. Per UDDI licensing docs, only "new or
renew DHCP leases" count as Active IPs. A `static` binding_state is a manually-configured
DHCP static assignment — not a dynamic lease. Corrected default: `("active",)`.

The `COUNT-03` test `test_default_lease_state_filter` already used an explicit
`FilterConfig(..., lease_states=("active", "static"))` and was left unchanged — it correctly
tests configurable behavior, not the default.

### Bug Fix 2: HOST_ADDRESS raw_attrs key

The ZF backup stores host record IPs under the `"address"` key, not `"ip_address"`. The
original combined `elif family in (NiosFamily.FIXED_ADDRESS, NiosFamily.HOST_ADDRESS):` clause
used `attrs.get("ip_address", "")` for both families, yielding 0 host_address IPs.

Fix: Split into two separate `elif` clauses:
- `FIXED_ADDRESS`: `attrs.get("ip_address", "")`
- `HOST_ADDRESS`: `attrs.get("address", "")` — ZF backup confirmed

### Empirical ZF Reference Value

After both fixes, `count_objects()` was run against the full ZF Friedrichshafen backup
(`do_not_commit/ZF-database-11_1752136302416.bak.reset.tar.gz`):

| Metric | Value |
|--------|-------|
| Active IP count (4-source dedup) | **304,730** unique IPs |
| Raw LEASE rows | 605,489 |
| LEASE-attributed members | 216 |
| Grid DDI count | 881,083 |

REQUIREMENTS.md COUNT-02 updated with the correct IP source breakdown and the verified
reference value.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Fix FilterConfig default and HOST_ADDRESS key | e8250bf | filter.py, counter.py |
| 2 | Update tests for corrected defaults and key | 7d342c9 | test_nios_filter.py, test_nios_counter.py |
| 3 | Empirical ZF backup run + REQUIREMENTS.md update | e91305b | REQUIREMENTS.md |

## Test Results

- 65 tests pass in `tests/nios/` (was 64 — added `test_host_address_uses_address_key`)
- `test_filter_config_defaults` now asserts `lease_states == ("active",)`
- `test_host_address_uses_address_key` (new): verifies `'address'` key counts, `'ip_address'` does not
- `_host_addr()` helper updated to use `address=ip` key
- `_host_addr_real()` helper added (explicit address-key version for clarity)
- `_default_config()` updated to `lease_states=("active",)`
- No regressions in parser, inspect, filter, or counter tests

## Deviations from Plan

None — plan executed exactly as written.

## Success Criteria Verification

- [x] `FilterConfig().lease_states == ("active",)` — confirmed
- [x] `counter.py HOST_ADDRESS` uses `attrs.get("address", "")` — confirmed at line 258
- [x] `test_filter_config_defaults` passes asserting `("active",)` — confirmed
- [x] `test_host_address_uses_address_key` passes — confirmed
- [x] `_host_addr()` uses `address=ip` — confirmed
- [x] Empirical ZF backup run: 304,730 unique Active IPs recorded
- [x] REQUIREMENTS.md COUNT-02 documents correct key names, 4 source types, reference value
- [x] All 65 nios tests pass with no regressions
- [x] GAP-01 status: RESOLVED

## Self-Check: PASSED

Files verified:
- src/cloud_usage/nios/filter.py: FOUND
- src/cloud_usage/nios/counter.py: FOUND
- tests/nios/test_nios_filter.py: FOUND
- tests/nios/test_nios_counter.py: FOUND
- .planning/REQUIREMENTS.md: FOUND

Commits verified:
- e8250bf (Task 1): FOUND
- 7d342c9 (Task 2): FOUND
- e91305b (Task 3): FOUND
