---
phase: 11-filter-and-counter
plan: "02"
subsystem: nios
tags: [counter, dataclass, ipaddress, defaultdict, tdd, formula]

requires:
  - phase: 10-nios-parser
    provides: NiosObject frozen dataclass and NiosFamily constants consumed by count_objects()
  - phase: 11-01
    provides: FilterConfig frozen dataclass (lease_states field used for binding_state filtering)

provides:
  - MemberCounts frozen dataclass with ddi_count, active_ip_count, lease_count, asset_count
  - CountResult frozen dataclass with member_counts list and grid_counts aggregate
  - Formula constants NIOS_DDI_DIVISOR=50, NIOS_IP_DIVISOR=25, NIOS_ASSET_DIVISOR=13
  - Formula constants UDDI_DDI_DIVISOR=25, UDDI_IP_DIVISOR=13, UDDI_ASSET_DIVISOR=3
  - nios_object_tokens() and uddi_native_tokens() formula functions
  - count_objects() single-pass counter returning CountResult from Iterator[NiosObject]

affects:
  - 12-scenario-engine (calls count_objects(), receives CountResult, applies token formulas)
  - 13-output (iterates CountResult.member_counts for Member Attribution sheet)

tech-stack:
  added: []
  patterns:
    - Single global set[str] for cross-source IP deduplication
    - ipaddress.IPv4Network(cidr, strict=False) for CIDR normalization
    - defaultdict(_MemberAcc) for per-member accumulation in single-pass
    - Internal mutable _MemberAcc separate from frozen output MemberCounts

key-files:
  created:
    - src/cloud_usage/nios/counter.py
    - tests/nios/test_nios_counter.py
  modified: []

key-decisions:
  - "Formula constants defined only in counter.py — NOT imported from cloud_usage.shared"
  - "NETWORK is both DDI-counted (+1) AND contributes IPs (network+broadcast via ipaddress)"
  - "HOST_OBJECT: raw_attrs.get('aliases', '').strip() — non-empty → +3, empty → +2"
  - "grid_counts.active_ip_count = len(global_ip_set) — global total across all 4 sources"
  - "Per-member active_ip_count = per-member lease IPs only (not fixed_address or host_address)"
  - "lease_count tracks ALL raw lease rows; active_ip_count is state-filtered unique IPs"
  - "grid_counts.member_hostname = '__grid__' sentinel to distinguish from real hostnames"
  - "asset_count = 0 always in Phase 11; Phase 12 Scenario Engine fills this"

patterns-established:
  - "Single-pass O(N) counting with defaultdict(_MemberAcc) accumulator"
  - "Two-level aggregation: per-member (lease-attributed) + global (grid-level) in same pass"

requirements-completed:
  - COUNT-01
  - COUNT-02
  - COUNT-03
  - COUNT-04
  - COUNT-05
  - COUNT-06

duration: 3min
completed: 2026-03-02
---

# Phase 11 Plan 02: nios.counter — MemberCounts + CountResult + count_objects() Summary

**Single-pass NIOS Grid counter with global IP deduplication, HOST_OBJECT expansion, lease state filtering, and NIOS/UDDI formula constants (no shared/ imports)**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-02T02:46:58Z
- **Completed:** 2026-03-02T02:49:36Z
- **Tasks:** 3 (RED, GREEN, REFACTOR)
- **Files modified:** 2

## Accomplishments

- `MemberCounts` frozen dataclass (member_hostname, ddi_count, active_ip_count, lease_count, asset_count)
- `CountResult` frozen dataclass (member_counts list + grid_counts with "__grid__" sentinel)
- Formula constants and functions: `nios_object_tokens()` (50/25/13) and `uddi_native_tokens()` (25/13/3), self-contained in counter.py
- `count_objects()`: single-pass iterator counting DDI families (+1 each, HOST_OBJECT +2/+3), deduplicating IPs across 4 sources in a global `set[str]`, filtering leases by `config.lease_states`
- All 30 counter tests pass; full nios suite (64 tests) green — no regressions

## Task Commits

1. **RED: Failing tests for CountResult, MemberCounts, count_objects()** - `1b26ae2` (test)
2. **GREEN: counter.py implementation** - `782c368` (feat)

No REFACTOR commit — implementation was clean as written.

## Files Created/Modified

- `src/cloud_usage/nios/counter.py` — MemberCounts, CountResult, formula constants/functions, _MemberAcc internal accumulator, count_objects() single-pass counter
- `tests/nios/test_nios_counter.py` — 30 TDD tests covering COUNT-01 through COUNT-06 and structural assertions

## Decisions Made

- Formula constants defined only in `counter.py` — confirmed via AST inspection that no `cloud_usage.shared` imports exist
- `NETWORK` is both DDI-counted and contributes IPs: `if family in _DDI_FAMILIES` handles DDI side, `elif family == NiosFamily.NETWORK` clause handles IP side. The `elif` means the IP contribution is only evaluated on non-LEASE/FIXED_ADDRESS/HOST_ADDRESS families — but NETWORK is already in `_DDI_FAMILIES` so DDI counting and CIDR parsing are both applied correctly via separate `if` checks
- Lease state filter uses `set(config.lease_states)` for O(1) membership testing rather than repeated tuple iteration
- `_MemberAcc.lease_ip_set` is a `set` (mutable) to enable deduplication; converted to `len()` when building frozen `MemberCounts`

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 11 complete: `filter_objects()` and `count_objects()` both implemented and tested
- Phase 12 Scenario Engine can call `count_objects(filter_objects(parse_backup(path), config), config)` to receive `CountResult`
- Phase 13 Output can iterate `CountResult.member_counts` for the Member Attribution sheet
- No blockers

---
*Phase: 11-filter-and-counter*
*Completed: 2026-03-02*

## Self-Check: PASSED

- [x] `src/cloud_usage/nios/counter.py` exists on disk
- [x] `tests/nios/test_nios_counter.py` exists on disk
- [x] `git log --oneline --all --grep="11-02"` returns ≥1 commit (1b26ae2, 782c368)
- [x] No `## Self-Check: FAILED` marker
