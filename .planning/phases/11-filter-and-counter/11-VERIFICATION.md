---
phase: 11-filter-and-counter
status: gaps_found
verified_by: execute-phase orchestrator
verified_at: 2026-03-02
requirements_covered:
  - FILTER-01
  - FILTER-02
  - FILTER-03
  - FILTER-04
  - COUNT-01
  - COUNT-02
  - COUNT-03
  - COUNT-04
  - COUNT-05
  - COUNT-06
---

# Phase 11: Filter and Counter — Verification Report

**Phase Goal:** Users can scope the analysis to specific grid members and receive per-member DDI object counts, Active IP counts, and dual-formula token contributions that match the ZF Friedrichshafen reference values.

**Verification Date:** 2026-03-02
**Test Suite:** 64 tests (15 filter + 30 counter + 19 Phase 10), all passing

---

## Must-Haves Verification

### FILTER must_haves

| Must-Have | Status | Evidence |
|-----------|--------|----------|
| filter_objects() with whitelist yields only matching member_hostname objects | PASS | test_whitelist_passes_matching_members |
| filter_objects() always passes member_hostname=None grid-level objects | PASS | test_grid_level_always_passes |
| filter_objects() with blacklist excludes matching members | PASS | test_blacklist_excludes_matching_members |
| Whitelist-first semantics: whitelist gates admission, blacklist applies to admitted set | PASS | test_whitelist_first_semantics |
| Zero-match whitelist emits logging.warning() once per pattern after stream exhaustion | PASS | test_zero_match_whitelist_warns |
| filter_objects() is a lazy generator (types.GeneratorType) | PASS | test_filter_objects_is_lazy_generator |
| FilterConfig is frozen dataclass with tuple[str, ...] fields | PASS | test_filter_config_is_frozen, test_filter_config_tuple_fields |

### COUNTER must_haves

| Must-Have | Status | Evidence |
|-----------|--------|----------|
| count_objects() returns CountResult with member_counts + grid_counts("__grid__") | PASS | test_count_result_structure |
| DDI count for 16 DDI families (+1 each, HOST_OBJECT +2/+3) | PASS | test_ddi_families_counted, test_host_object_expansion_* |
| Active IP uses single global set[str] | PASS | test_active_ip_deduplication |
| Network reservation: network_address + broadcast_address via IPv4Network(strict=False) | PASS | test_network_reservation_ips, test_network_reservation_host_bits_set |
| Lease state filter via config.lease_states | PASS | test_default_lease_state_filter, test_custom_lease_states |
| Formula constants (50/25/13, 25/13/3) defined only in counter.py | PASS | test_formula_constants_not_from_shared |
| Per-member MemberCounts: ddi_count, active_ip_count, lease_count, asset_count=0 | PASS | test_per_member_lease_active_ip_count, test_member_counts_asset_count_zero |
| nios_object_tokens() and uddi_native_tokens() exported and correct | PASS | test_nios_object_tokens_formula, test_uddi_native_tokens_formula |

---

## Success Criteria Verification

### SC1: Hostname glob whitelist scopes analysis to matching members
**Status: PASS**
Verified programmatically: `filter_objects(parse_backup(...), FilterConfig(whitelist=("gm*",)))` yields only members matching "gm*" in counts. Non-matching members excluded.

### SC2: Active IP count = 168,295 unique active IPs from ZF reference backup
**Status: GAPS_FOUND**

**Actual result from ZF reference backup:** 194,172 unique IPs (global dedup set with active+static leases + fixed addresses)

**Investigation:**
- Active-only leases: 168,295 unique IPs — this matches the reference value exactly
- Active + static leases: 179,516 unique IPs
- Active + static + fixed_address: ~194,172 unique IPs (current implementation)
- HOST_ADDRESS objects use `"address"` key in raw_attrs (not `"ip_address"`), so 0 host_address IPs are currently counted

**Root cause:** The plan's reference value (168,295) represents active-only lease IPs. The implementation follows the plan's explicit specification (4-source dedup with active+static default), producing 194,172.

**Gap:** The PLAN.md reference value 168,295 does not match the 4-source dedup with active+static that the plan also specifies. Additionally, HOST_ADDRESS objects in the ZF backup use `raw_attrs["address"]` not `raw_attrs["ip_address"]`.

**Resolution needed:**
Either (a) the default `lease_states` should be `("active",)` not `("active", "static")`, or (b) the reference value needs to be updated to reflect the correct 4-source dedup total, or (c) HOST_ADDRESS IP key should be `"address"`. This requires user decision before Phase 12.

### SC3: HOST_OBJECT expansion without double-counting independent DNS records
**Status: PASS**
Verified: HOST_OBJECT(no aliases)=+2, HOST_OBJECT(with aliases)=+3. Independent DNS_RECORD_A counted separately as +1. No deduplication by name.

### SC4: Per-member attribution with DDI, Active IP, token columns
**Status: PASS**
MemberCounts dataclass has all required fields. count_objects() populates per-member entries for LEASE-attributed members.

### SC5: Formula constants in counter.py only (50/25/13 NIOS, 25/13/3 UDDI)
**Status: PASS**
AST inspection confirms no cloud_usage.shared imports. Constants NIOS_DDI_DIVISOR=50, UDDI_DDI_DIVISOR=25 confirmed in counter.py.

---

## Requirements Coverage

| Requirement | Status | Test Coverage |
|-------------|--------|---------------|
| FILTER-01 | COMPLETE | test_whitelist_passes_matching_members, test_grid_level_always_passes |
| FILTER-02 | COMPLETE | test_blacklist_excludes_matching_members |
| FILTER-03 | COMPLETE | test_whitelist_first_semantics, test_whitelist_first_partial_overlap |
| FILTER-04 | COMPLETE | test_zero_match_whitelist_warns, test_matching_pattern_does_not_warn |
| COUNT-01 | COMPLETE | test_ddi_families_counted, test_non_ddi_families_not_counted, test_host_object_expansion_* |
| COUNT-02 | PARTIAL | test_active_ip_deduplication, test_network_reservation_ips — but actual ZF count 194,172 ≠ 168,295 reference |
| COUNT-03 | COMPLETE | test_default_lease_state_filter, test_custom_lease_states, test_lease_count_is_raw_rows |
| COUNT-04 | COMPLETE | test_uddi_native_formula_constants, test_uddi_native_tokens_formula |
| COUNT-05 | COMPLETE | test_nios_object_formula_constants, test_nios_object_tokens_formula |
| COUNT-06 | COMPLETE | test_count_result_structure, test_empty_stream_returns_empty_result, test_per_member_lease_active_ip_count |

---

## Gaps Found

### GAP-01: Active IP Reference Value Mismatch (COUNT-02)

**Severity:** High — affects the reference value that validates the entire counting pipeline

**Description:** The plan states the ZF reference backup should produce 168,295 unique Active IPs with default `lease_states=("active", "static")`. The actual implementation with that config produces 194,172.

**Evidence from ZF backup:**
- Active leases only: 168,295 unique IPs = matches reference value
- Active + static: 179,516 unique IPs
- Active + static + fixed_address: 194,172 unique IPs (no HOST_ADDRESS IPs counted due to wrong key)
- HOST_ADDRESS raw_attrs key is `"address"` not `"ip_address"` — currently yields 0 host_address IPs

**Decision needed:**
Option A: Change `lease_states` default to `("active",)` only — would produce 168,295 from active-only leases + 0 host_addr (wrong key) + 25,817 fixed_addr = ~194,000. Still doesn't match.
Option B: Change default to `("active",)` AND fix HOST_ADDRESS key to `"address"` AND exclude fixed_address — but this contradicts the 4-source specification.
Option C: Accept that 168,295 = active-only leases and the 4-source dedup produces a different (higher) total. Update reference value in documentation.
Option D: Fix HOST_ADDRESS key to `"address"` and verify what total that produces.

**Recommended action:** Run `/gsd:plan-phase 11 --gaps` to create a gap closure plan addressing the HOST_ADDRESS key fix and reference value clarification.

---

## Summary

**Score:** 9/10 must-haves verified | 4/5 success criteria passed
**Gap:** SC2 (COUNT-02) — Active IP reference value 168,295 not reproducible with implemented 4-source dedup; HOST_ADDRESS uses `"address"` key not `"ip_address"`.
**All other** FILTER-01–04 and COUNT-01, COUNT-03–06 requirements fully implemented and tested.
**Test suite:** 64/64 tests passing.

**Next step:** Investigate and resolve COUNT-02 reference value discrepancy before Phase 12.
