# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

---

## Milestone: v1.1 — NIOS Grid Analysis

**Shipped:** 2026-03-02
**Phases:** 6 (Phases 10–15) | **Plans:** 14 | **Timeline:** 3 days (2026-02-28 → 2026-03-02)

### What Was Built

- **Streaming parser** — lxml iterparse processes 2GB+ NIOS Grid backup files (onedb.xml inside tar.gz) with flat memory; 2-pass architecture resolves virtual_oid → hostname without holding all objects in memory
- **Filter engine** — `FilterConfig` with hostname glob whitelist/blacklist and whitelist-first semantics; filter telemetry (matched patterns, excluded counts) recorded in output for traceability
- **Per-member counter** — `count_objects()` single-pass counter producing `CountResult` with member-attributed DDI, Active IP, and Asset counts; 4-source Active IP deduplication validated at 304,730 unique IPs against ZF Friedrichshafen reference backup
- **Three-scenario engine** — `compute_scenarios()` computes current grid, hybrid UDDI split, and full migration; dual formula constants isolated in `nios/counter.py` only; arithmetic sum for hybrid ensures no rounding error
- **5-sheet XLS report** — Object Counters, DDI Objects, Active IP by Type, Scenario Comparison, Member Attribution; full traceability header block makes two reports from different runs unambiguously comparable
- **Full integration** — `--nios` / `--nios-config` CLI flags; dedicated NIOS Analysis tab in web dashboard with file upload wizard, per-member nios/niosx toggle checkboxes, SSE progress stream, and results display

### What Worked

- **Frozen dataclass pattern** — Using `@dataclass(frozen=True)` with `tuple[str, ...]` fields throughout the NIOS package (FilterConfig, MigrationSplitConfig, MemberCounts, ScenarioResult) prevented mutation bugs and made tests predictable. Pattern was consistent across all 6 phases.
- **Empirical validation loop** — Running against the ZF Friedrichshafen reference backup during Phase 11 gap closure immediately surfaced the HOST_ADDRESS key bug (was `ip_address`, should be `address`) and the COUNT-02 lease state mismatch. No amount of unit testing against fixtures would have caught these without a real backup.
- **Strict data-flow phase ordering** — Parser → filter → counter → scenarios → output dependency chain meant each phase had a clear, testable interface contract. Phase 13 could be planned independently of Phase 11 because `CountResult` was the only coupling point.
- **Isolated `nios/` package** — Zero shared code between NIOS analysis and cloud providers. Despite 6 phases of NIOS work, there were zero regressions in the cloud dashboard tests throughout the milestone.
- **Phase 11-03 gap closure pattern** — Having an explicit gap closure plan within a phase (rather than a separate phase) was efficient for small fixups (2 bug fixes + empirical validation = 1 plan).

### What Was Inefficient

- **Stale REQUIREMENTS.md** — MIGR-02 and INTEG-02 were not checked off after Phase 15 executed. REQUIREMENTS.md is only useful at milestone completion if it's updated as phases complete. The milestone complete workflow had to correct this retroactively.
- **Stale milestone audit** — v1.1-MILESTONE-AUDIT.md was created at the start of the milestone (Phase 10 only). Its `gaps_found` status was technically correct at creation time but misleading at milestone completion. Consider re-running the audit after all phases complete rather than only at milestone start.
- **ROADMAP.md progress table** — The progress table had a stale `0/TBD` entry for Phase 15 at completion. Phase completion should update the table as part of the execute-phase commit, not left for milestone close.
- **Accomplishment extraction** — gsd-tools `milestone complete` found no accomplishments because SUMMARY.md files use a dependency-graph frontmatter format (provides/requires) rather than a `one_liner` field. The tool's extractor expected a different schema. Accomplishments had to be written manually.

### Patterns Established

- **NIOS formula constants isolation** — NIOS Object and UDDI native formula divisors are defined once in `nios/counter.py` (`NIOS_DDI_DIVISOR`, `UDDI_IP_DIVISOR`, etc.) and never imported from the cloud token calculator. Any future NIOS-adjacent feature must follow this rule.
- **4-source Active IP dedup** — One global `set[str]` across active leases, fixed addresses, host addresses (`raw_attrs["address"]`), and network reservations (network + broadcast from `IPv4Network(cidr)`). Dedup happens once in `count_objects()`. This is the canonical UDDI-spec-compliant count.
- **Background thread receives path string, not file handle** — Upload handler saves the .tar.gz to disk (`output/nios_upload_<timestamp>.tar.gz`) before dispatching background analysis. Background thread receives a `str` path. This is required for Python 3.9 compatibility and prevents file handle lifecycle bugs.
- **Lazy imports for NIOS CLI branch** — `_run_nios_cli()` in `cli.py` uses lazy imports (`from cloud_usage.nios import ...`) to avoid import overhead on cloud-only scans. Same pattern should apply to any future optional analysis module.

### Key Lessons

1. **Run empirical validation early** — Unit tests against fixtures can't catch field name mismatches (e.g., HOST_ADDRESS `address` vs `ip_address`) that only appear in real backup data. Schedule one empirical validation run per phase when a reference dataset exists.
2. **Update REQUIREMENTS.md as phases complete** — Mark requirements `[x]` at the time the plan is committed, not at milestone close. At milestone close there are often 10+ plans to review; tracking completion in-flight keeps the traceability table accurate.
3. **Keep formula constants in the leaf module** — Dual formulas tempt you to share a single `formulas.py` module. Resist: NIOS Object and UDDI native formulas apply to different object families with different semantics. Sharing creates accidental coupling. Duplication is acceptable here.
4. **`assignment_source` in MigrationSplitConfig** — Recording how the migration split was specified (`yaml` vs `dashboard`) as a metadata field in the frozen config dataclass costs nothing and makes the traceability story clear in the output report.

### Cost Observations

- Sessions: ~6 focused sessions over 3 days
- Model: claude-sonnet-4-6 (balanced profile) throughout; no opus needed
- Notable: Phase 12 (scenario engine) was the most complex logic and took a single 45-minute session end-to-end — the frozen dataclass pattern and clear CountResult interface made it straightforward

---

## Milestone: v1.2 — DTC/LBDN DDI Support

**Shipped:** 2026-03-02
**Phases:** 2 (Phases 16–17) | **Plans:** 4 | **Timeline:** same day (2026-03-02)

### What Was Built

- **Five DTC NiosFamily constants** — `dtc_lbdn`, `dtc_pool`, `dtc_server`, `dtc_monitor`, `dtc_topology`; 11 `_XML_TYPE_TO_FAMILY` entries covering all subtypes (6 monitor, 2 topology) collapsed to single family constants per spec
- **DTC DDI integration** — all five families added to `GRID_LEVEL_FAMILIES`, `ALL_EXPECTED_FAMILIES`, and `_DDI_FAMILIES`; +1 DDI per object using existing NIOS Object formula; no changes to scenarios.py or counter.py
- **XLS Object Counters sheet extended** — `_ALL_FAMILIES_ORDERED` and `_FAMILY_DISPLAY_NAMES` in `output.py` extended from 21 to 26 entries; DTC rows appear with correct counts and DDI flag
- **Verification tests** — 7 new tests covering DTC-08 (3 scenario flow-through), DTC-09 (1 output), DTC-10 (2 inspect pre-population); 105 tests pass across nios_output/scenarios/inspect suites
- **README rewrite** — accurate How To Use documentation for all three tool modes (Cloud Scan, Web Dashboard, NIOS Grid Analysis); updated CLI flags and project structure

### What Worked

- **No architectural change required** — Because Phase 16 added DTC to `_DDI_FAMILIES` and `GRID_LEVEL_FAMILIES`, the DTC counts automatically flowed through `compute_scenarios()` without any code changes. The frozen dataclass + clean data-flow architecture established in v1.1 paid dividends immediately.
- **Spec-derived annotation discipline (DTC-11)** — Requiring all unverified `_XML_TYPE_TO_FAMILY` entries to carry a `# spec-derived, unverified — no empirical backup observed` comment is a low-cost, high-value audit trail. Future maintainers can distinguish confirmed vs inferred type strings at a glance.
- **Two-phase split was right-sized** — Phase 16 (schema/parser/counter additions) and Phase 17 (verification) were appropriately sized. Phase 17 was almost entirely test-only with one surgical code change. Two phases > one monolithic phase for clarity of what was done vs what was verified.
- **Synthetic backup test pattern** — DTC-containing backup unavailable; synthetic `.tar.gz` test data built inline in pytest fixtures using the existing helper pattern. All 11 DTC-specific tests pass against spec-derived type strings. Confidence is high for the counter logic, deferred for the XML type strings themselves.

### What Was Inefficient

- **REQUIREMENTS.md checkboxes not updated after Phase 17** — DTC-08, DTC-09, DTC-10 remained `[ ]` after Phase 17 completed. Same pattern as v1.1 (MIGR-02, INTEG-02). The root cause is that GSD executor commits don't touch REQUIREMENTS.md. Either the executor should update requirements, or a post-plan checklist step should prompt for it.
- **README fell far behind** — The README still documented v0 architecture at v1.2 ship time. A quick task (quick-1) fixed it, but ideally README updates would be part of the milestone completion checklist rather than discovered at archive time.
- **gsd-tools one_liner extraction** — `milestone complete` CLI found "(none recorded)" because SUMMARY.md files use `provides:` frontmatter, not `one_liner`. This has been consistent across v1.1 and v1.2. Either the tool should parse `provides:` fields, or SUMMARY.md templates should add a `one_liner` field.

### Patterns Established

- **Spec-derived annotation as a first-class field** — When `_XML_TYPE_TO_FAMILY` entries are added from spec rather than empirical observation, annotate them `# spec-derived, unverified — no empirical backup observed`. When verified, replace with `# N observed` (N = observed count from reference backup).
- **N:1 XML type mapping** — Multiple `__type` strings can map to a single `NiosFamily` constant (e.g., six monitor subtypes → `dtc_monitor`). This is the correct pattern when subtypes are conceptually one family for DDI counting purposes.
- **Additive-only verification phases** — Phase 17 added tests and one targeted code change but modified zero production logic files. This "verify without touching" pattern is efficient for integration verification and keeps test commits clearly separate from feature commits.

### Key Lessons

1. **Update REQUIREMENTS.md inline** — Mark requirements `[x]` in the plan commit where they're satisfied. At milestone close, there's no memory of which commit addressed which requirement. The executor should be prompted to update REQUIREMENTS.md as part of plan execution.
2. **README as living artifact** — Treat README as a phase deliverable, not an afterthought. Schedule a README review as part of milestone pre-completion (before `/gsd:complete-milestone`).
3. **DTC-V01/V02 as canonical deferred debt** — The spec-derived XML type strings need empirical confirmation against a real DTC-containing customer backup. This is explicitly tracked as DTC-V01/V02 in PROJECT.md Known Technical Debt. Pattern to follow: record unverified assumptions as named debt items with a verification trigger condition.

### Cost Observations

- Sessions: 1 focused session (~4 hours including README rewrite)
- Model: claude-sonnet-4-6 (balanced profile) throughout; no opus needed
- Notable: v1.2 was deliberately narrow in scope — 2 phases, same-day execution. The clean v1.1 architecture made it frictionless. Smaller milestones shipped faster and with higher confidence.

---

## Milestone: v1.3 — Enhanced WebUI Experience

**Shipped:** 2026-03-03
**Phases:** 3 (Phases 18–20) | **Plans:** 6 | **Timeline:** same day (2026-03-03)

### What Was Built

- **SSE progress pipeline** — `_run_nios_pipeline` emits `nios_progress` events at 6 named steps (step N/6, label, elapsed seconds from monotonic timer); `NiosScanManager` gains thread-safe `set_progress()` / `current_progress` property
- **HTMX progress display** — `#nios-progress-area` polls `GET /api/nios/progress` on `sse:nios_progress` trigger; `progress_display.html` renders determinate `<progress>` bar, step label, and elapsed time; no JavaScript timers needed
- **Per-scenario formula derivation** — NIOS complete screen shows raw DDI/IP/Asset counts with inline formula ("1,234 DDI ÷ 50 = 24.7 tokens"); Hybrid UDDI card renders two labeled sub-blocks (NIOS-remaining / NIOSX-migrated)
- **Member attribution table** — Scrollable table with Member, Group, DDI Objects, Active IPs, Token Contribution; NIOS/NIOSX color-coded badges; dedup subtitle prevents customer confusion about per-member IP sum vs scenario total
- **Migration wizard UX** — PicoCSS `<article>` callout explains NIOS/NIOSX formulas before member assignment; Select All / Clear All batch controls with bubbling `change` events; live group counter via IIFE script
- **Consistent step labels** — "Step 1: Upload Backup → Step 2: Assign Members → Step 3: Run Analysis" across both rendering paths (HTMX partial swap + full-page nios.html running block)

### What Worked

- **Server-side progress state + GET endpoint** — Storing progress in `NiosScanManager` and rendering via a GET endpoint (rather than embedding state in the SSE event payload) kept the HTMX integration clean. `hx-get="/api/nios/progress"` on `sse:nios_progress` trigger is a clear, testable pattern.
- **Determinate `<progress>` element** — Using native HTML `<progress value="N" max="6">` (determinate) instead of an indeterminate spinner was more informative and required zero JavaScript. The step count was always known.
- **Formula divisors in template (not backend)** — Hardcoding UDDI spec constants directly in `complete.html` avoided a new backend data flow. Constants are immutable by spec definition; the template becomes self-documenting.
- **IIFE for counter script** — Inline IIFE at the bottom of the form section kept the Select All counter logic scoped, with no global pollution and no dependency on load order. Clean pattern for small UI interactions in Jinja2 templates.
- **Both rendering paths identified early** — Phase 20 plan correctly identified that `step2_run.html` (HTMX partial swap) and `nios.html` (full-page inline block) are separate rendering paths requiring independent fixes. Catching this in the plan avoided a half-complete fix.
- **Short, focused plans** — 6 plans, each 5–15 minutes of execution. Tight scoping meant no plan required mid-flight decisions.

### What Was Inefficient

- **gsd-tools accomplishment extraction still broken** — For the third milestone in a row, `milestone complete` CLI output "(none recorded)" because SUMMARY.md uses `provides:` frontmatter, not `one_liner`. Accomplishments had to be written manually. This should be fixed in the tool or the SUMMARY template should be updated.
- **REQUIREMENTS.md checkboxes again late** — All 11 requirements were checked off in the `docs(v1.3): close tech debt` commit rather than inline with execution. Same pattern as v1.1 and v1.2. The root cause is the executor does not prompt for REQUIREMENTS.md updates.
- **SUMMARY frontmatter for Phase 18 missing requirements-completed** — Plans 18-01 and 18-02 shipped with empty `requirements-completed: []`. These were patched in the tech debt commit but should have been populated at execution time.

### Patterns Established

- **Server-side progress state for long-running SSE flows** — When a background thread emits SSE events, store progress server-side in the manager class and expose a GET render endpoint. The SSE event is just a trigger; the rendering is a normal HTTP response. More testable than embedding HTML in the event payload.
- **IIFE script at bottom of form section** — For small, scoped UI interactions (counters, batch controls) in Jinja2 templates: use inline IIFE, `dispatchEvent(new Event('change', {bubbles: true}))` for batch operations, no globals. Pattern is reusable for any future wizard step.
- **`type='button'` for batch control buttons** — Any button inside a `<form>` that does not submit should be `type='button'`. Required for Select All / Clear All; prevents hard-to-debug accidental submissions.

### Key Lessons

1. **Fix gsd-tools SUMMARY extraction** — Either update the tool to extract from `provides:` frontmatter, or add `one_liner:` as a required field to SUMMARY.md frontmatter. Three milestones of manual accomplishment writing is a consistent friction point.
2. **Executor should prompt for REQUIREMENTS.md** — After each plan executes, the executor should check which requirements the plan's `requires:` / `provides:` fields satisfy and update REQUIREMENTS.md checkboxes in the same commit. No more retroactive cleanup at milestone close.
3. **Check both rendering paths at plan time** — For any UI feature that has multiple rendering paths (HTMX partial vs full-page), identify all paths in the plan before execution. The fix is always simple per path but missing one produces a partial, confusing result.

### Cost Observations

- Sessions: 1 focused session (~2 hours, same day as v1.2)
- Model: claude-sonnet-4-6 (balanced profile) throughout
- Notable: v1.3 was the fastest milestone to date — 3 phases, 6 plans, same day. Clear HTMX + FastAPI patterns from v1.1/v1.2 meant no architectural decisions needed; every plan was execution-only.

---

## Milestone: v1.4 — Audit Depth

**Shipped:** 2026-03-03
**Phases:** 2 (Phases 21–22) | **Plans:** 4 | **Timeline:** same day (2026-03-03)

### What Was Built

- **Cloud per-account attribution table** — `summary.html` renders one row per scanned account with Account/Subscription/Project ID, DDI count + inline formula derivation (e.g. `312 DDI ÷ 25 = 12.5 tokens`), Active IPs, Assets, and Token contribution; resource-type sub-rows show exactly which types generated each count; collapsible via `<details>` (Phase 21)
- **NIOS object family breakdown** — `nios_complete.html` renders a full DDI-adjusted breakdown table with 26 object families, DDI flag column (Yes/No), non-DDI reason column, and subtotal row confirming the count feeds into scenario token calculations; scenario-independence note at top (Phase 22)

### What Worked

- **Backend data already available** — `_compute_summary()` already produced `per_provider_details` and `per_account_details`; Phase 21 was template-only (no backend changes). Clean data architecture from Phase 2 continued paying dividends in v1.4.
- **TDD cycle for attribution table** — Writing failing tests for each new HTML attribute/element before implementing kept Phase 21 disciplined. Each test failure was precise and the corresponding template change was surgical.
- **Tight phase scope** — Phase 21 = cloud attribution (dashboard), Phase 22 = NIOS breakdown (analysis complete screen). Clean boundary; no cross-contamination.

### What Was Inefficient

- **v1.4 never went through `complete-milestone`** — Phases 21–22 were shipped but the milestone was never formally closed before starting v1.5. The ROADMAP.md v1.4 `<details>` block lacked an Archive link. Fixed retroactively during v1.5 completion.
- **gsd-tools accomplishment extraction broken** — Fifth milestone, still broken. Pattern is now well-established and documented.

### Patterns Established

- **Template-only audit features** — Both Phase 21 and 22 shipped with zero backend changes. The backend data was already computed; the gap was in surface area. Pattern: check what's already in the template context before adding backend work.
- **DDI-adjusted family count** — For `HOST_OBJECT` (which contains multiple objects per family entry), use the DDI-adjusted count (integer division by family multiplier) rather than the raw object count. Pattern established in Phase 22 for all future NIOS display work.

### Key Lessons

1. **Close milestones before starting the next one** — v1.4 and v1.5 were started back-to-back on the same day. The lack of a formal v1.4 close meant it was archived retroactively during v1.5 completion. One missed archive step doesn't break anything, but it reduces traceability.
2. **Archive link in `<details>` block** — Each collapsed milestone `<details>` in ROADMAP.md should include the `Archive: .planning/milestones/vX.Y-ROADMAP.md` line at creation time, not retroactively.

### Cost Observations

- Sessions: 1 focused session (same day as v1.3)
- Model: claude-sonnet-4-6 (balanced profile) throughout
- Notable: Back-to-back milestones (v1.3 → v1.4 → v1.5 same day) showed the compounding effect of clean architecture — each new phase required only template/test changes, no backend rework.

---

## Milestone: v1.5 — Results Navigation

**Shipped:** 2026-03-03
**Phases:** 1 (Phase 23) | **Plans:** 2 | **Timeline:** same day (~38 min total execution)

### What Was Built

- **Per-provider formula cards** — `summary_cards.html` iterates `per_provider_details` and renders a "Per-Provider Formula Breakdown" section with one card per provider; each card shows DDI count + ÷ 25 = X.X, Active IPs + ÷ 13 = X.X, Managed Assets + ÷ 3 = X.X, and ceiling token total; zero-count lines suppressed with `{% if data.field > 0 %}` guard (Plan 23-01, CLOUD-06)
- **Sort IIFE** — embedded IIFE after closing `</table>` tag in `summary.html`; calls `sortTable('tokens', 'desc')` on page load for Tokens-descending default; column header click toggles direction and resets to desc on column switch; `data-col`/`data-value` on `<th>`/`<td>` elements carry sort key and raw integer value (Plan 23-02, CLOUD-07)
- **Detail row adjacency** — sort IIFE uses `nextElementSibling` check to re-append `acct-detail-row` rows immediately after their parent `acct-row` after each sort — preserves account↔breakdown relationship through DOM reorder (Plan 23-02, ANA-07 verified)

### What Worked

- **Data already in template context** — `per_provider_details` (carrying ddi/ips/assets/tokens) was already computed and passed to both Results and Summary tabs by `_compute_summary()`. Formula card plan (23-01) required zero backend changes. Same pattern as Phase 21.
- **TDD RED/GREEN discipline** — Plan 23-01: wrote 6 failing tests for formula card rendering, then updated template to pass them. Plan 23-02: wrote 4 failing tests for `data-col`/`data-value`/CSS class presence, then added those attributes to the template. Both plans produced clean atomic commits: RED test commit → GREEN implementation commit.
- **IIFE pattern from v1.3 carried over** — The Select All IIFE pattern from Phase 20 translated directly to the sort IIFE in Phase 23. Inline, scoped, no globals, no build pipeline. Consistent with the project's "no Node/npm" constraint.
- **Native `<details>` confirmed** — ANA-07 (collapsible resource-type rows) was already satisfied by Phase 21's implementation. Plan 23-02 verified it with a dedicated `TestANA07` test. Zero implementation work required.
- **Single-phase milestone was right-sized** — All three requirements (CLOUD-06, CLOUD-07, ANA-07) share the same dashboard templates and test context. Grouping into one phase eliminated setup overhead and allowed the two plans to build on each other's context directly.

### What Was Inefficient

- **IP resource type in formula card tests** — Plan 23-01 initially used `("vpc", "ip", ...)` test resources but VPC resources without `ip_addresses` produce `ips=0` in `_compute_summary()`. Corrected to `("network-interface", "ip", ...)` with `ip_addresses=["10.0.0.1"]` during GREEN verification. A note in the test helpers or a shared fixture would prevent this pattern from repeating.
- **Zero-suppression test assertion** — Initial assertion `response.text.count("÷ 13 =") == 1` failed because the per-account attribution table (Phase 21) also renders `÷ 13 =` for AWS accounts. Required a AZURE-section slice assertion. The test is correct but the initial design didn't account for content elsewhere on the page.
- **gsd-tools accomplishment extraction broken** — Sixth milestone, still "(none recorded)". Accomplishments manually written for this entry. This is a persistent process friction point.

### Patterns Established

- **`per_provider_details` for formula display (not `provider_breakdown`)** — When displaying formula derivations per provider, use `per_provider_details` (ddi/ips/assets/tokens) rather than `provider_breakdown` (token counts only). The richer dict is always available from `_compute_summary()`.
- **Sort IIFE pattern** — `getElementById` + `querySelectorAll('th[data-col]')` + `querySelectorAll('tr.acct-row')` + `nextElementSibling` for detail rows. Reusable for any future sortable table without external dependencies.
- **Section-scoped test assertions** — When a page has multiple tables that render similar formula text (e.g., `÷ 13 =`), slice the relevant section from `response.text` before asserting counts. Avoids false positives from other sections.

### Key Lessons

1. **Check template context before planning backend work** — Two plans in a row (23-01 and 23-02) shipped with zero backend changes because the data was already in the context. Before any UI plan, the first question should be: "what does `_compute_summary()` already pass to this template?" Answer before writing the plan.
2. **ANA-07 verification as a test** — Pre-existing `<details>` collapsible behavior (from Phase 21) was verified via `TestANA07` in Plan 23-02. This is the right pattern: when a requirement is satisfied by prior work, add a test to lock it in rather than relying on manual review.
3. **IIFE sort patterns for tables** — The sort IIFE pattern (data attributes + DOM reorder + detail row adjacency) is now established and well-tested. Future sortable tables should reuse this pattern verbatim rather than introducing a JS framework.

### Cost Observations

- Sessions: 1 focused session (~38 min execution, same day as v1.4)
- Model: claude-sonnet-4-6 (balanced profile) throughout
- Notable: Fastest milestone to date — 1 phase, 2 plans, ~38 minutes. The clean data architecture and established patterns meant zero architectural decisions; both plans were pure execution.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Timeline | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | 4 days | 9+1 (incl. 2.1) | Initial build — full rewrite from v0; established core patterns |
| v1.1 | 3 days | 6 | Additive — isolated `nios/` package; zero v1.0 regressions |
| v1.2 | 1 day | 2 | Micro-milestone — narrow scope, same-day execution; architecture absorbs additive features cleanly |
| v1.3 | 1 day | 3 | WebUI polish — no new data model; all plans were execution-only with clear HTMX + FastAPI patterns |
| v1.4 | 1 day | 2 | Audit depth — template-only, backend data already available; back-to-back with v1.3 |
| v1.5 | 1 day | 1 | Results navigation — template + IIFE; fastest milestone; all reqs satisfied in 38 min |

### Cumulative Quality

| Milestone | New Tests | Total NIOS Tests | Zero-Dep Additions |
|-----------|-----------|------------------|--------------------|
| v1.0 | ~150+ | — | moto (test), HTMX/CSS (vendored) |
| v1.1 | 181 | 181 (182 in nios/, 32 dashboard) | pyyaml (runtime), lxml (runtime) |
| v1.2 | 13 (7 DTC + 2 DTC-10) | 188 | none (pure extension) |
| v1.3 | 20+ (Phase 19 dashboard tests) | 188+ | none (Jinja2 template additions only) |
| v1.4 | 21+ (Phase 21 attribution + Phase 22 breakdown) | 188+ | none (template additions only) |
| v1.5 | 10 (TestFormulaCards x5 + TestANA07 x1 + TestSortableTable x4) | 188+ | none (template + IIFE additions only) |

### Top Lessons (Verified Across Milestones)

1. **Isolated package boundaries prevent regressions** — v1.0 gap closure phases (7–9), v1.1 (Phases 10–15), and v1.2 (Phases 16–17) all completed with zero regressions in prior phases. The clear import boundaries (`cloud_usage.nios.*` never imports from cloud providers) made this possible across all milestones.
2. **Empirical reference data is irreplaceable** — v1.0 validated Azure with 13,363 real resources; v1.1 validated NIOS counting with the ZF Friedrichshafen 2.5M-object backup. Both caught issues unit tests missed. v1.2 shipped without a real DTC backup — DTC-V01/V02 are now tracked as explicit debt.
3. **Update requirements inline, not at close** — Five milestones, same pattern: checkboxes not ticked at execution time. The milestone close workflow corrects this retroactively. Fix: require executor to update REQUIREMENTS.md in the commit where each requirement is satisfied.
4. **gsd-tools `milestone complete` accomplishment extraction is broken** — Present across v1.1–v1.5. Tool expects `one_liner:` frontmatter; SUMMARY.md uses `provides:`. Fix either the tool or the template.
5. **Check template context before adding backend work** — v1.4 (Phases 21–22) and v1.5 (Phase 23) all shipped with zero backend changes because the data was already computed and available. The architectural investment in `_compute_summary()` returning rich per-provider/per-account dicts paid dividends across 5 consecutive phases.
6. **Close milestones formally before starting the next** — v1.4 was informally shipped before v1.5 started (same day). Retroactive archival works but loses traceability. One-milestone-at-a-time discipline keeps the planning files accurate and the archive links clean.
