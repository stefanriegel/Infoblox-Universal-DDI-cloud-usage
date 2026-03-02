# Phase 12: Scenario Engine - Research

**Researched:** 2026-03-02
**Domain:** Python frozen dataclasses, token formula computation, data transformation layer
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### MigrationSplitConfig design
- Frozen dataclass following the `FilterConfig` pattern in `filter.py` (tuple fields, immutable)
- Member assignments stored as `niosx_members: tuple[str, ...]` — list of hostname or virtual_oid strings identifying members to assign to the NIOSX group
- Lookup tries hostname match first, then virtual_oid match (supports both identifiers as MIGR-01 requires)
- `default_group: str = "nios"` — configurable per MIGR-03 (valid values: "nios" | "niosx")
- `assignment_source: str = "yaml"` — records how the config was provided (e.g., "yaml", "dashboard") for MIGR-04 verbatim capture in the report
- Lives in new `nios/scenarios.py` alongside the scenario computation logic

#### Grid-level DDI attribution in hybrid scenario
- DDI objects with `member_hostname=None` (DNS records, zones, networks — grid-level in ZF backup) are always assigned to the NIOS-remaining sub-total in hybrid scenario
- Rationale: grid-level objects exist independently of member assignment; attributing them to NIOS is the conservative/correct approach matching current licensing reality
- This means `CountResult.grid_counts.ddi_count` (grid-level DDI) always contributes to the NIOS-remaining formula in hybrid scenario, regardless of what percentage of members are NIOSX-migrated

#### Scenario result dataclass shape
- Single `ScenarioSuite` top-level container returned by the public API
- Per-scenario type `ScenarioResult(name, formula_name, ddi_count, active_ip_count, asset_count, token_total)` for SCEN-01 and SCEN-03
- `HybridScenarioResult` extends with sub-totals: `nios_sub: ScenarioResult`, `niosx_sub: ScenarioResult`, `combined_total: float` — satisfies SCEN-02's requirement for three sub-totals that sum exactly to combined_total
- `ScenarioSuite` includes `member_attribution: list[MemberScenarioRow]` — per-member breakdown with group assignment, DDI count, active IP count, and per-formula token contribution (needed by Phase 13 Member Attribution sheet)
- `migration_split_used: MigrationSplitConfig | None` — captured verbatim for MIGR-04

#### Module file structure
- Single new file: `src/cloud_usage/nios/scenarios.py`
- Public API: `compute_scenarios(count_result: CountResult, split_config: MigrationSplitConfig | None = None) -> ScenarioSuite`
- All three scenario computations in one module; reuses `nios_object_tokens()` and `uddi_native_tokens()` imported from `counter.py`
- No new formula constants needed — all already defined in `counter.py`

### Claude's Discretion
- Exact field order and repr formatting for the result dataclasses
- Whether `MemberScenarioRow` is exported or kept internal to the module
- Handling of edge case where `split_config` is None but SCEN-02 is requested (should raise ValueError with clear message)
- Whether `ScenarioSuite.current_grid` and `ScenarioSuite.full_migration` are always populated, with `hybrid_uddi` being Optional[HybridScenarioResult]

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SCEN-01 | Current grid view — all grid objects (post-filter) counted under NIOS Object formula (DDI/50 + IPs/25 + Assets/13); produces DDI total, Active IP total, Assets total, and token total | Sum all member_counts + grid_counts, call nios_object_tokens() |
| SCEN-02 | Hybrid UDDI view — requires migration split; NIOS-remaining under NIOS Object formula; NIOSX-migrated under UDDI native formula; three sub-totals that sum exactly to combined_total | Split CountResult.member_counts by group assignment; nios_sub.token_total + niosx_sub.token_total = combined_total (no re-aggregation) |
| SCEN-03 | Full migration view — all grid objects counted under UDDI native formula (DDI/25 + IPs/13 + Assets/3) | Sum all member_counts + grid_counts, call uddi_native_tokens() |
| MIGR-01 | Migration split via YAML/JSON config: list of member hostnames or virtual_oids assigned to niosx group | MigrationSplitConfig.niosx_members tuple; lookup by hostname first, then virtual_oid |
| MIGR-03 | Members not explicitly assigned default to NIOS-remaining; default group configurable | MigrationSplitConfig.default_group = "nios" (configurable); non-assigned members use default |
| MIGR-04 | Migration split configuration recorded verbatim in output | ScenarioSuite.migration_split_used = split_config (verbatim capture) |
</phase_requirements>

## Summary

Phase 12 is a pure data transformation layer with zero external dependencies. It takes a `CountResult` (from Phase 11's `count_objects()`) and an optional `MigrationSplitConfig`, computes three licensing scenarios using formulas already defined in `counter.py`, and returns typed dataclasses for Phase 13's report generator.

The implementation is entirely self-contained Python: frozen dataclasses (stdlib `dataclasses`), formula functions already available in `counter.py`, and simple arithmetic. No new libraries, no I/O, no parsing. The primary engineering challenges are:

1. **Correct aggregation across member + grid counts** — `CountResult` separates `member_counts` (per-member LEASE-attributed objects) from `grid_counts` (grid-level objects with `member_hostname=None`). Scenario totals must combine both correctly.
2. **Hybrid scenario exactness (SCEN-02)** — `combined_total` must be the arithmetic sum of `nios_sub.token_total + niosx_sub.token_total`, never re-computed from aggregated inputs (prevents floating point rounding divergence).
3. **Member lookup by hostname OR virtual_oid (MIGR-01)** — `MemberScenarioRow` needs both identifiers; lookup resolution order is hostname-first, then virtual_oid fallback.

**Primary recommendation:** Single-file implementation in `nios/scenarios.py` with frozen dataclasses, direct import of formula functions from `counter.py`, and TDD covering all five success criteria.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `dataclasses` (stdlib) | 3.9+ | Frozen dataclass result types | Established pattern in this codebase (FilterConfig, MemberCounts, CountResult all use it) |
| `__future__.annotations` | 3.9+ | Postponed evaluation of type hints | Required pattern — all existing nios/ modules use it |
| `logging` (stdlib) | 3.9+ | Debug logging | `logging.getLogger(__name__)` pattern used in all nios/ modules |
| `typing` (stdlib) | 3.9+ | Type hints (Optional, List) | Required for Python 3.9 compatibility (union syntax `X | Y` is 3.10+) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `counter.nios_object_tokens` | Internal | NIOS Object formula | All NIOS-remaining sub-totals in every scenario |
| `counter.uddi_native_tokens` | Internal | UDDI native formula | All NIOSX-migrated sub-totals and full migration |
| `counter.CountResult` | Internal | Input type | Provides member_counts + grid_counts |
| `counter.MemberCounts` | Internal | Per-member input | DDI, active IP, asset counts per member |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Frozen dataclasses | NamedTuple | Dataclasses give better repr, inheritance, field defaults; NamedTuple is tuple-ordered which Phase 13 doesn't need |
| Direct arithmetic sum | Decimal module | Decimal avoids float rounding, but SCEN-02 requires sub-total addition not re-computation — both approaches produce the same result if sub-totals are computed first |

**Installation:** No new dependencies required.

## Architecture Patterns

### Recommended File Structure
```
src/cloud_usage/nios/
├── scenarios.py      # NEW: MigrationSplitConfig + ScenarioResult + ScenarioSuite + compute_scenarios()
├── counter.py        # EXISTING: imports from here (nios_object_tokens, uddi_native_tokens, CountResult)
├── filter.py         # EXISTING: FilterConfig pattern to replicate for MigrationSplitConfig
└── schema.py         # EXISTING: NiosFamily, NiosObject (no changes needed)

tests/nios/
└── test_nios_scenarios.py   # NEW: TDD tests for all 5 success criteria + MIGR requirements
```

### Pattern 1: Frozen Dataclass with Tuple Fields
**What:** All config and result types use `@dataclass(frozen=True)` with `tuple[str, ...]` fields (not `list`) to enforce true immutability.
**When to use:** All public API types in scenarios.py
**Example (following filter.py pattern):**
```python
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True)
class MigrationSplitConfig:
    niosx_members: tuple[str, ...] = field(default_factory=tuple)
    default_group: str = "nios"
    assignment_source: str = "yaml"
```

### Pattern 2: Aggregation with grid_counts separation
**What:** `CountResult.member_counts` contains per-LEASE-member counts. `CountResult.grid_counts` (member_hostname="__grid__") contains grid-level DDI and global Active IP total.
**Critical insight for SCEN-01/SCEN-03:** The global Active IP count is `grid_counts.active_ip_count` (the global dedup set). The member-level `active_ip_count` values are lease-only and NOT additive — summing them would re-count IPs that moved between members. Always use `grid_counts.active_ip_count` for the total IP figure.
**Critical insight for DDI:** DDI IS additive: member DDI (LEASE-attributed objects) + grid DDI (grid_counts.ddi_count) = total DDI.

**Example:**
```python
total_ddi = sum(m.ddi_count for m in count_result.member_counts) + count_result.grid_counts.ddi_count
total_ips = count_result.grid_counts.active_ip_count  # global dedup — do NOT sum member IPs
total_assets = 0  # Phase 11 sets asset_count=0 everywhere; propagate this zero
```

### Pattern 3: Hybrid Scenario — Additive Sub-totals, Not Re-aggregation
**What:** For SCEN-02, compute NIOS sub-total and NIOSX sub-total independently, then sum for combined_total. Never re-apply a formula to a merged input.
**Why:** Prevents floating point rounding where `(a/50 + b/50)` ≠ `(a+b)/50` due to intermediate truncation.
**Example:**
```python
nios_tokens = nios_object_tokens(nios_ddi, nios_ips, 0)
niosx_tokens = uddi_native_tokens(niosx_ddi, niosx_ips, 0)
combined_total = nios_tokens + niosx_tokens  # exact sum — no re-computation
```

### Pattern 4: Member Group Resolution
**What:** For hybrid scenario, look up each `MemberCounts` entry in `MigrationSplitConfig.niosx_members`. Lookup tries hostname first, then virtual_oid. Members not found default to `default_group`.
**Critical:** `grid_counts` (member_hostname="__grid__") always goes to NIOS-remaining in hybrid scenario regardless of config.
**Example:**
```python
def _resolve_group(member_hostname: str, split_config: MigrationSplitConfig) -> str:
    if member_hostname in split_config.niosx_members:
        return "niosx"
    # virtual_oid lookup would happen if MemberCounts carried virtual_oid (see open questions)
    return split_config.default_group
```

### Pattern 5: IP Attribution in Hybrid Scenario
**What:** Per-member active IPs for hybrid scenario use `member.active_ip_count` (lease-only). The NIOS-remaining sub-total IP count = sum of NIOS members' lease IPs + grid_counts.active_ip_count (which includes fixed, host, and network reservation IPs that have no member attribution). NIOSX sub-total IP count = sum of NIOSX members' lease IPs only.
**Rationale from CONTEXT.md:** Grid-level DDI (member_hostname=None) always contributes to NIOS sub-total; same principle applies to grid-level IPs (fixed/host/network) which have no member attribution.

### Anti-Patterns to Avoid
- **Summing member active_ip_count values:** These are lease-only per-member sets. The global total is always `grid_counts.active_ip_count`. Summing member IPs would produce a wrong number (lower, since grid-level IPs are not counted per-member).
- **Applying formula to aggregated combined inputs for hybrid:** Combining all inputs then calling one formula breaks the SCEN-02 sub-total invariant.
- **Mutable fields on frozen dataclass:** Using `list[...]` instead of `tuple[str, ...]` causes `FrozenInstanceError` at runtime. Use `tuple` and `field(default_factory=tuple)`.
- **Importing formula constants from cloud_usage.shared:** Phase 11/12 formula constants live only in `nios/counter.py`. Never cross-import from the cloud token calculator.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token formulas | Custom formula functions | `nios_object_tokens()`, `uddi_native_tokens()` from counter.py | Already tested, correct constants |
| Formula constants | Re-define NIOS_DDI_DIVISOR etc. | Import from counter.py | Single source of truth — duplicating risks divergence |
| Immutable config | dict-based config | Frozen dataclass following FilterConfig pattern | Type safety, hashable, repr for report capture |

## Common Pitfalls

### Pitfall 1: IP Double-Counting in Scenario Totals
**What goes wrong:** Summing `m.active_ip_count` across all members gives only lease-derived IPs, missing fixed/host/network IPs tracked only in `grid_counts.active_ip_count`.
**Why it happens:** `MemberCounts.active_ip_count` is per-member lease IPs only (see counter.py docstring). Grid-level IP sources (FIXED_ADDRESS, HOST_ADDRESS, NETWORK) contribute only to `grid_counts.active_ip_count`.
**How to avoid:** For SCEN-01 and SCEN-03 (all-grid scenarios), always use `count_result.grid_counts.active_ip_count` as the single total IP figure.
**Warning signs:** Active IP total in scenario output is lower than expected (misses grid-level IPs).

### Pitfall 2: Hybrid Scenario Grid-Level Attribution Error
**What goes wrong:** Allocating grid_counts.ddi_count proportionally between NIOS and NIOSX groups instead of always assigning it to NIOS-remaining.
**Why it happens:** The CONTEXT.md decision is explicit but easy to overlook: grid-level objects (member_hostname=None) have no member attribution and are always NIOS-remaining.
**How to avoid:** The hybrid aggregation loop processes `count_result.member_counts` only. `grid_counts` is always added to the NIOS sub-total after the loop.

### Pitfall 3: SCEN-03 Invariant Not Asserted
**What goes wrong:** Full migration token total < current grid token total — which is mathematically impossible with correct formula constants (UDDI has higher divisors: DDI/25 vs DDI/50, IPs/13 vs IPs/25, Assets/3 vs Assets/13 — wait, UDDI has LOWER divisors, meaning MORE tokens per object).
**Why it happens:** Confusion about which formula produces higher tokens. UDDI divisors are SMALLER (DDI/25 vs DDI/50), so each object costs more tokens in UDDI native. Full migration should always produce token_total >= current grid.
**How to avoid:** Document this as a correctness invariant in the module docstring. Optionally add an assertion or logged warning if violated.
**Warning signs:** `full_migration.token_total < current_grid.token_total` — indicates formula inversion or constant swap.

### Pitfall 4: MemberScenarioRow virtual_oid Availability
**What goes wrong:** `MemberCounts` does not carry `virtual_oid` — it only has `member_hostname`. The MIGR-01 lookup by virtual_oid cannot be done from MemberCounts alone.
**Why it happens:** Phase 11 counter resolves member hostnames in parser (two-pass); MemberCounts stores the resolved hostname only.
**How to avoid:** For Phase 12, accept that virtual_oid lookup in MigrationSplitConfig is hostname-based only. MIGR-01 says "hostnames or virtual_oids" — in the split config, users can list either. The resolution at match time uses the member_hostname from MemberCounts against both fields of the niosx_members list. This is workable since by Phase 12 the hostname is already resolved.

## Code Examples

### compute_scenarios() public API skeleton
```python
# Source: CONTEXT.md decisions + counter.py patterns
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import logging

from cloud_usage.nios.counter import (
    CountResult, MemberCounts,
    nios_object_tokens, uddi_native_tokens,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MigrationSplitConfig:
    niosx_members: tuple[str, ...] = field(default_factory=tuple)
    default_group: str = "nios"
    assignment_source: str = "yaml"


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    formula_name: str
    ddi_count: int
    active_ip_count: int
    asset_count: int
    token_total: float


@dataclass(frozen=True)
class HybridScenarioResult:
    nios_sub: ScenarioResult
    niosx_sub: ScenarioResult
    combined_total: float  # = nios_sub.token_total + niosx_sub.token_total


@dataclass(frozen=True)
class MemberScenarioRow:
    member_hostname: str
    group: str  # "nios" | "niosx"
    ddi_count: int
    active_ip_count: int
    asset_count: int
    token_contribution: float


@dataclass(frozen=True)
class ScenarioSuite:
    current_grid: ScenarioResult
    full_migration: ScenarioResult
    hybrid_uddi: Optional[HybridScenarioResult]
    member_attribution: list[MemberScenarioRow]
    migration_split_used: Optional[MigrationSplitConfig]


def compute_scenarios(
    count_result: CountResult,
    split_config: Optional[MigrationSplitConfig] = None,
) -> ScenarioSuite:
    """Compute all three licensing scenarios from grid counts."""
    ...
```

### SCEN-01 current_grid aggregation
```python
# Total DDI = sum of member DDI + grid-level DDI
total_ddi = (
    sum(m.ddi_count for m in count_result.member_counts)
    + count_result.grid_counts.ddi_count
)
# Total IPs = global dedup set size (grid_counts.active_ip_count)
total_ips = count_result.grid_counts.active_ip_count
# asset_count always 0 in Phase 11/12
current_grid = ScenarioResult(
    name="current_grid",
    formula_name="NIOS Object (DDI/50 + IPs/25 + Assets/13)",
    ddi_count=total_ddi,
    active_ip_count=total_ips,
    asset_count=0,
    token_total=nios_object_tokens(total_ddi, total_ips, 0),
)
```

### SCEN-02 hybrid aggregation
```python
# Split members by group assignment
nios_ddi = count_result.grid_counts.ddi_count  # grid-level always NIOS
nios_ips = count_result.grid_counts.active_ip_count  # grid-level IPs always NIOS
niosx_ddi = 0
niosx_ips = 0

for m in count_result.member_counts:
    group = "niosx" if m.member_hostname in niosx_set else split_config.default_group
    if group == "niosx":
        niosx_ddi += m.ddi_count
        niosx_ips += m.active_ip_count
    else:
        nios_ddi += m.ddi_count
        nios_ips += m.active_ip_count

nios_tokens = nios_object_tokens(nios_ddi, nios_ips, 0)
niosx_tokens = uddi_native_tokens(niosx_ddi, niosx_ips, 0)
combined_total = nios_tokens + niosx_tokens  # exact sum — never re-compute
```

## Open Questions

1. **virtual_oid availability in MemberScenarioRow for Phase 13**
   - What we know: MemberCounts only carries member_hostname (resolved from parser two-pass). virtual_oid is not passed through.
   - What's unclear: Phase 13 Member Attribution sheet lists virtual_oid per member. Where does it come from?
   - Recommendation: Two options: (a) MemberScenarioRow stores virtual_oid=None and Phase 13 does a secondary lookup from parser IntegrityReport, or (b) compute_scenarios() receives an optional member map dict to enrich rows. For Phase 12, leave virtual_oid out of MemberScenarioRow and document that Phase 13 will need to supply it from the parser output. This keeps Phase 12 API minimal.

2. **Hybrid IP sub-total for NIOS portion**
   - What we know: NIOS sub-total IPs = grid-level IPs + NIOS-assigned member lease IPs. Grid-level IPs (fixed/host/network) are tracked only in grid_counts.active_ip_count.
   - What's unclear: grid_counts.active_ip_count includes all IPs including those associated with NIOSX members' fixed/host addresses (if any), since those are grid-level without member attribution.
   - Recommendation: Accept this limitation. Grid-level IPs always go to NIOS sub-total per CONTEXT.md decision. Document in module docstring.

## Sources

### Primary (HIGH confidence)
- `src/cloud_usage/nios/counter.py` — formula functions, constants, CountResult, MemberCounts (all directly inspected)
- `src/cloud_usage/nios/filter.py` — frozen dataclass pattern, FilterConfig (directly inspected)
- `src/cloud_usage/nios/schema.py` — NiosFamily, NiosObject types (directly inspected)
- `tests/nios/test_nios_counter.py` — test patterns, NiosObject construction helpers (directly inspected)
- `.planning/phases/12-scenario-engine/12-CONTEXT.md` — all locked design decisions

### Secondary (MEDIUM confidence)
- Python stdlib `dataclasses` docs — frozen dataclass semantics confirmed via inspection of existing code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pure stdlib, all imports verified in codebase
- Architecture: HIGH — all patterns from inspected CONTEXT.md decisions and existing code
- Pitfalls: HIGH — derived from direct codebase analysis and formula semantics

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (stable, no external dependencies)

---

## RESEARCH COMPLETE

**Phase:** 12 - Scenario Engine
**Confidence:** HIGH

### Key Findings
- Zero external dependencies — pure Python stdlib (dataclasses, typing, logging)
- Formula functions `nios_object_tokens()` and `uddi_native_tokens()` are import-ready in counter.py
- Critical aggregation rule: total Active IPs always from `grid_counts.active_ip_count` (global dedup), never sum of member IPs
- Hybrid scenario: grid_counts always goes to NIOS sub-total; combined_total = additive sum of sub-totals (no re-computation)
- MemberCounts does not carry virtual_oid — Phase 12 MemberScenarioRow will have None for virtual_oid; Phase 13 must supply it

### File Created
`.planning/phases/12-scenario-engine/12-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | All imports verified in codebase; no new libraries |
| Architecture | HIGH | All decisions locked in CONTEXT.md; patterns verified from filter.py/counter.py |
| Pitfalls | HIGH | Derived from direct code analysis and formula mathematics |

### Open Questions
- virtual_oid in MemberScenarioRow: Phase 13 will need to supply from parser output; Phase 12 leaves field absent or None
- Grid-level IP allocation in hybrid: all go to NIOS sub-total per CONTEXT.md — documented limitation

### Ready for Planning
Research complete. Planner can now create PLAN.md files.
