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

## Milestone: v1.7 — Reference Parity

**Shipped:** 2026-03-07
**Phases:** 5 (Phases 25–29) | **Plans:** 19 | **Timeline:** 5 days (2026-03-03 → 2026-03-07)

### What Was Built

- **IP methodology fix (Phase 25)** — `count_nics_per_account()` replaces `deduplicate_ips_per_vpc()` across all three cloud providers; AWS now counts EC2 NIC objects (`nic_ip_count`), Azure counts NIC card objects, GCP counts `network_interface_count`; standalone ENIs/EIPs/NAT GW IPs reclassified as DDI-only (not IP count)
- **AWS DDI expansion (Phase 26)** — 15 new DDI type strings added to `DDI_TYPES`; 13 new `_safe_collect()` calls in `AWSDiscoveryProvider.discover_account()`; covers Route53 Resolver endpoints/rules/associations, IPAM pools/scopes/allocations, Internet/Customer Gateways, Route Tables, Direct Connect Gateways, Health Checks, Traffic Policies
- **Azure DDI expansion (Phase 27)** — 5 new DDI types; 4 new `_safe_collect()` calls + tenant deduplication guard; covers VNet Gateways (VPN+ExpressRoute), Private Link Services, Virtual WANs, Route Tables, Tenants; fixed stale `SubscriptionClient` import in `client_factory.py`
- **GCP DDI expansion (Phase 28)** — 6 new DDI type strings; 5 new `_safe_collect()` calls; covers reserved Compute Addresses (DDI-only, no IPs), GKE CIDR ranges (control plane/pod/service), Router NAT configs, Target VPN Gateways; added `RoutersClient`/`TargetVpnGatewaysClient` to `client_factory.py`
- **Microsoft AD provider (Phase 29)** — `src/cloud_usage/providers/ad/` package: `MicrosoftAdCollector` (WinRM sessions, `Get-DnsServerZone`/`Get-DhcpServerv4Scope`/`Get-ADUser` cmdlets, Kerberos/NTLM auth, DC autodiscovery via `Get-ADForest`); `run_ad_analysis()` pipeline with cross-DC deduplication in `_aggregate_results()`; 12 `--ad-*` CLI flags; XLS report using same UDDI native formula

### What Worked

- **TDD RED/GREEN gate discipline** — Every phase opened with a scaffolding plan (01-PLAN) that wrote failing tests before any implementation. This was enforced across all 5 phases. By Phase 29 the pattern was automatic: test file → RED commit → implementation → GREEN commit.
- **Isolated providers/ad/ package** — Zero impact on existing cloud providers, NIOS package, or dashboard during Phase 29. The pattern from v1.1 (`nios/` isolation) replicated cleanly. Phase 29 shipped without a single regression test failure outside the AD test suite.
- **_safe_collect() pattern for DDI expansion** — Phases 26, 27, 28 all used `_safe_collect()` to add new collectors with graceful error handling. Consistent pattern made wiring plans (26-05, 27-03, 28-03) predictable and fast to execute.
- **Cross-DC deduplication at the runner level** — `_aggregate_results()` in `run_ad_analysis()` deduplicates DNS zones by name and DHCP scopes by `scope_id` after collecting from all DCs. Doing this at the runner (not collector) level means each DC collector stays simple and the aggregation logic is tested independently.
- **Lazy import pattern for AD CLI branch** — `_run_ad_cli()` uses `from cloud_usage.providers.ad import ...` inside the function body, matching the established `_run_nios_cli()` pattern. No import overhead on non-AD scans.

### What Was Inefficient

- **Nyquist VALIDATION.md files incomplete** — Phases 25–27 have VALIDATION.md files in `status: draft` with `nyquist_compliant: false`; Phases 28–29 have none. Post-execution validation was not finalized. Noted as `NYQ-V17` in technical debt. This has been a recurring pattern but now explicitly tracked.
- **Phase 26 test scaffolding (26-01) was over-broad** — The initial scaffolding plan added tests for all 7 AWSG requirements in one plan. Some tests required mock infrastructure that wasn't yet established, leading to more iteration than needed. For broad expansion phases, scaffolding tests in parallel with implementation waves (rather than front-loading all 7) would be more efficient.
- **gsd-tools accomplishment extraction** — Seventh milestone, still "(none recorded)". `milestone complete` CLI returned `accomplishments: []`. This is a documented persistent issue; accomplishments written manually for this entry.
- **AD live environment untested** — Phase 29 shipped with WinRM/PowerShell mocks only (via `unittest.mock`). No live AD environment available for integration validation. Explicitly tracked as `AD-LIVE` debt.

### Patterns Established

- **providers/{name}/ package structure** — New data source providers follow the pattern: `providers/{name}/__init__.py` (exports), `constants.py` (frozen sets/strings), `options.py` (frozen dataclass with validation), `collector.py` (main collector class), `runner.py` (pipeline function). AD followed this pattern; future providers (e.g., IPAM platforms) should too.
- **Cross-DC / cross-account deduplication at runner level** — When a provider can return overlapping objects from multiple endpoints (DCs, accounts), dedup happens in the runner's `_aggregate_results()` using a canonical key (zone name, scope_id, SID). Individual collectors stay simple.
- **DDI-only resource types** — Some resources are DDI objects but not IP sources (standalone ENIs, EIPs, Compute Addresses). These carry `ip_addresses=[]` and `resource_type=` the DDI type. This is now an established pattern; `_safe_collect()` + empty `ip_addresses` is the canonical form.
- **Staggered DDI expansion pattern** — For each cloud provider DDI expansion: (1) scaffolding tests (01-PLAN), (2) implement collectors (02-PLAN), (3) wire into provider + categorizer (03-PLAN). Three plans = one full DDI gap closure. Reusable for any future DDI gap phase.

### Key Lessons

1. **AD live validation is the v1.7 DTC-V01 equivalent** — Microsoft AD shipped without live WinRM testing, exactly as DTC shipped in v1.2 without a real DTC backup. Both are tracked as explicit technical debt. Pattern: when no live environment is available, ship with mock coverage + a named debt item with a verification trigger condition.
2. **Nyquist validation needs a post-execution pass** — Phases 25–29 all have incomplete or missing VALIDATION.md files. The pattern is: validation files are created during planning but not updated after execution. A post-execution `/gsd:validate-phase` pass should be a standard milestone-close step.
3. **DDI expansion phases are now a solved problem** — The three-plan pattern (scaffolding → collectors → wiring) worked identically for AWS, Azure, and GCP DDI gaps. Future DDI expansion phases for any provider can follow this template without redesign.
4. **Microsoft AD is a third co-equal scope** — Post-v1.7, the tool has three independent estimation scopes: NIOS Grid, Cloud (AWS+Azure+GCP), and Windows AD. These are not mutually exclusive; customers may run any combination. Future UI work (AD dashboard tab, Top 5 DNS Zones panel) must reflect this three-scope architecture.

### Cost Observations

- Sessions: ~8 focused sessions over 5 days
- Model: claude-sonnet-4-6 (balanced profile) throughout; no opus needed
- Notable: Phase 29 (Microsoft AD) was the most structurally novel work — new provider type, WinRM/PowerShell protocol, cross-DC aggregation. It shipped cleanly in 4 plans (~1 day) because the providers/ad/ package structure was planned up-front and the isolated package boundary kept blast radius minimal.

---

## Milestone: v1.8 — Dashboard Analytics

**Shipped:** 2026-03-08
**Phases:** 3 (Phases 30–32) | **Plans:** 10 | **Timeline:** 1 day (2026-03-08)

### What Was Built

- **AD Dashboard tab (Phase 30)** — Full HTMX wizard UI for AD connection (wizard.html), per-DC autodiscovery progress via SSE (progress_display.html), results screen with token formula derivation and download CTA (complete.html), error state with retry; `AdScanManager` thread-safe state machine with background thread execution; `routes/ad.py` (3 endpoints); wired into FastAPI lifespan, `_get_tab_context()`, and `tab_bar.html` badge
- **Top 5 DNS Zones panels (Phase 31)** — Cloud Summary tab panel (`_compute_top_cloud_dns_zones()` in pages.py, counting `gcp-dns-record` / AWS Route53 / Azure DNS records by zone); AD complete screen panel (Counter-based tally in `_run_ad_pipeline()`); NIOS complete screen panel (stream-intercept accumulator `_accumulate_dns_zones()` in parse pipeline, `NiosScanManager.top_dns_zones`); backward-compatible `set_complete(top_dns_zones=None)` across both managers
- **DDI display names (Phase 32)** — `DDI_DISPLAY_NAMES: dict[str, str]` with 68 type mappings (AWS/Azure/GCP/AD, pre-v1.7 and v1.7 types); `_compute_summary()` breakdown dict gains `"display_name": DDI_DISPLAY_NAMES.get(rt, rt)` fallback; `summary.html` renders `{{ info.display_name }}` in breakdown rows; `CloudResource.resource_type` never mutated

### What Worked

- **Three-source DNS panel pattern** — The same `top_dns_zones` data structure (list of `(zone_name, count)` tuples) was used identically across all three panels (Cloud, AD, NIOS). Designing the data contract once and reusing it across three screens cost almost nothing.
- **Backward-compatible manager kwarg pattern** — Adding `top_dns_zones=None` as a final keyword arg to `set_complete()` on both `AdScanManager` and `NiosScanManager` kept all 201+ existing tests passing without any fixture updates. The established pattern made Phase 31 risk-free.
- **Stream-intercept accumulator for NIOS** — Wrapping `filter_objects()` with `_accumulate_dns_zones()` (a generator that yields through while maintaining a running Counter) avoided a second parse pass on the NIOS backup file. Elegant, zero-memory-overhead, single-pass.
- **Display-layer separation (Phase 32)** — ATTR-01 touched zero backend models. `DDI_DISPLAY_NAMES.get(rt, rt)` fallback in `_compute_summary()` means unknown future types degrade to raw strings without any error or code change. Correct approach to display concerns.
- **xfail(strict=False) for Wave 0 scaffold** — Using `strict=False` on xfail stubs allowed tests to pass when implementation pre-existed (Phase 32-01 case) without breaking CI. The contract was established without any awkward fixture gymnastics.

### What Was Inefficient

- **Phase 30 template field name mismatch** — `wizard.html` field names did not match `form.get()` keys in `ad.py` (e.g., `servers` vs `server`, auth field naming). Required an unplanned fix pass. Root cause: template and route were developed by different agents with no shared field name contract. Fix: define field names in the plan, not discovered at render time.
- **No milestone audit** — v1.8 completed without `/gsd:audit-milestone`. All requirements were verified individually by the verifier agents, but cross-phase integration and E2E flows were not formally audited. The milestone was small enough (3 phases) that this wasn't critical, but the pattern should be maintained for larger milestones.
- **gsd-tools accomplishment extraction** — Eighth milestone, still `accomplishments: []`. The persistent mismatch between `provides:` SUMMARY.md frontmatter and the tool's expected `one_liner:` field remains unresolved.

### Patterns Established

- **SSE progress with asyncio.wait()** — `_sse_ad_progress()` generator uses `asyncio.wait()` with 1s timeout for compatibility with both real clients (streaming) and `TestClient` (disconnect detection). This is now the established pattern for SSE generators in this codebase; use it for any future streaming endpoint.
- **Top N panel data contract** — `top_dns_zones: list[tuple[str, int]]` — a list of `(name, count)` tuples sorted descending — is the universal data shape for "Top N" panels. `Counter.most_common(5)` produces it directly. Reuse for any future Top N panel (accounts, resource types, etc.).
- **Display name mapping at computation time** — `DDI_DISPLAY_NAMES` applied in `_compute_summary()`, never mutating `CloudResource.resource_type`. Display concerns are isolated to the summary dict. Future display-layer features follow the same pattern: add a key to the summary dict, render it in the template.

### Key Lessons

1. **Define shared field name contracts in plans, not discovered in templates** — Phase 30 template/route mismatch could have been avoided by listing the five `<form>` field names explicitly in the plan document. When multiple plans share a data contract, document the contract in the first plan and reference it in subsequent ones.
2. **Wave 0 xfail imports must be deferred inside test bodies** — Collection-time `ImportError` on module-level imports breaks the suite before any test runs. Deferring imports inside test bodies (Phase 31 lesson, reinforced in Phase 32) is the canonical pattern for Wave 0 scaffolds when the implementation doesn't yet exist.
3. **Template-first features are the fastest class of work** — Phase 32 (ATTR-01) was a display-layer-only change that shipped 2/2 plans in under 8 minutes of agent time. Whenever a requirement only needs a new key in `_compute_summary()` and a template substitution, that's the same pattern. Always check if the data is already available before adding backend work.
4. **SSE + TestClient compatibility requires care** — FastAPI `TestClient` doesn't behave identically to a real streaming client on disconnect. Using `asyncio.wait()` with explicit timeout (not `asyncio.sleep()`) and checking `done`/`pending` sets correctly handles both cases. Document this when designing new SSE endpoints.

### Cost Observations

- Sessions: 1 session (~3 hours)
- Model: claude-sonnet-4-6 (balanced profile) throughout; no opus needed
- Notable: All 10 plans executed in a single session with full parallel wave execution. v1.8 was the most concentrated milestone — 3 phases of dashboard work shipped in one continuous run. The three-scope architecture (Cloud, NIOS, AD) established in v1.7 was the key enabler; all three scopes had the same DNS panel data shape with zero cross-scope coupling.

---

## Milestone: v1.9 — Multi-Tool Suite UX

**Shipped:** 2026-03-08
**Phases:** 5 (Phases 33–37) | **Plans:** 16 | **Timeline:** single day (2026-03-08)

### What Was Built

- **Infoblox brand CSS design system** — `design-system.css` (12 sections, ~400 lines) with CSS custom properties (`--ib-*` tokens), self-hosted Inter v4.1 WOFF2 font, replacing PicoCSS's external CDN dependency; all `--pico-*` references purged from 6 templates
- **Home selector screen** — `home.html` at `/` with three calculator cards (Cloud, NIOS, AD), each with name, description, and entry button; root route swapped from Cloud Calculator to home; cards use `--ib-card-border` token and subtle shadow per DESIGN-02
- **Dedicated calculator routes** — `/cloud`, `/nios`, `/ad` handlers added to `pages.py`; `base.html` `active_tab` conditional enables per-route initial HTMX tab load; home screen is self-contained (no `base.html` extends) to avoid HTMX side-effects
- **Breadcrumb navigation** — conditional `Home > [Calculator Name]` breadcrumb in `base.html` using `calculator_name` context injection; plain `<a href="/">` (no HTMX) for correct full-page home navigation; visible across wizard, progress, and results screens
- **Per-calculator accent system** — `calc_theme` body class (`calc-cloud/nios/ad`) cascades `--calc-accent` CSS variable; wizard completed steps replaced with `::after` checkmark pseudo-element; `.completion-card` and `.section-header` layouts on results screens; 11 tests verified the full accent cascade
- **Persistent Cloud provider switcher** — AWS/Azure/GCP pill selector in `base.html` conditioned on `calc_theme="calc-cloud"`; three isolated `ScanManager` + `EventBridge` instances on `app.state` via lifespan startup; per-provider tab routes, SSE endpoint, scan start route, and 3-step wizard route all wired; backward-compatible `tab_bar.html` via `tab_base` context variable

### What Worked

- **Test-first wave pattern was highly effective** — Each phase opened with an xfail test scaffold (Wave 0 or Wave 1) before any implementation. This consistently surface the exact assertions needed and removed ambiguity about what "done" looked like. All 5 phases used this pattern; all 16 plans completed with passing tests.
- **`xfail(strict=True)` convention** — Using strict=True for all pre-implementation stubs creates an automatic enforcement: when implementation satisfies the assertion, the test XPASS-fails unless the xfail marker is removed. This forced cleanup on every implementation plan. Exception pattern (strict=False only when assertion already satisfied pre-implementation) was consistent across all 5 phases.
- **CSS custom property cascade for accent system** — A single `calc_theme` body class + CSS variable cascade produced all three per-calculator accent variants with zero Python branching. The `--calc-accent` fallback in `:root` kept shared components accent-neutral without extra logic.
- **Single-day milestone** — All 5 phases and 16 plans completed in one continuous session. The design-first sequencing (Phase 33 before all other phases) and the clear dependency chain (33 → 34 → 35 → 36 → 37) enabled this pace without blocking.

### What Was Inefficient

- **VALIDATION.md stubs not updated post-execution** — All 5 phases have VALIDATION.md files initialized as `draft` stubs during planning; none were updated after Wave 0 test scaffolds executed. Persistent pattern across v1.7, v1.8, v1.9 — `/gsd:validate-phase` should be run as part of the execute-phase commit, not deferred.
- **ROADMAP.md progress table columns out of sync** — Phases 33–37 rows in the progress table were missing the Milestone column at merge time (left as `| 33. Design Foundation | 3/3 | Complete | 2026-03-08 | - |`). Fixed at milestone close. Root cause: roadmap template for these phases was created before the Milestone column convention was added in earlier milestones.
- **gsd-tools accomplishment extraction (persistent)** — Same as v1.1–v1.8: `milestone complete` CLI returned "(none recorded)" because SUMMARY.md frontmatter uses `provides:/requires:` not `one_liner:`. Still not fixed after 8 milestones — either update the tool or add `one_liner:` to the executor's SUMMARY.md template.

### Patterns Established

- **Home screen self-contained (no base.html)** — Calculator home screens must not extend `base.html` if `base.html` carries HTMX auto-triggers for calculator tab loads. Home is a static page, not a calculator shell.
- **Plain anchor for cross-calculator navigation** — Links that navigate between top-level routes (e.g., breadcrumb Home link) use plain `<a href="/">` without any HTMX attributes. HTMX partial swaps are scoped to within a single calculator.
- **Isolated scan state per cloud provider** — Per-provider `ScanManager` + `EventBridge` instances on `app.state` (not module-level singletons) prevent cross-provider SSE bleed. The lifespan startup registration pattern is the standard for any future multi-instance scan state.
- **`tab_base` context variable for provider-scoped HTMX** — Templates that need provider-aware HTMX routes receive `tab_base` (e.g., `/cloud/aws`) in context; `{% if tab_base is defined %}` conditionals provide backward-compatible fallback. This pattern enables provider scoping without breaking NIOS/AD tabs.

### Key Lessons

1. **Design-first sequencing compounds** — Phase 33 (CSS variables) enabled all subsequent phases to reference `--calc-accent`, `--ib-*` tokens, and `calc_theme` body classes without backtracking. The one-day sprint was only possible because Phase 33 landed cleanly before Phase 36 needed the accent system.
2. **Strict xfail markers are a forcing function** — The `strict=True` pattern made test cleanup mandatory. Without it, stale xfail markers accumulate silently as XPASS. The `strict=False` exception (for assertions already satisfied pre-implementation) is the only safe carve-out.
3. **Run `/gsd:validate-phase` before milestone close** — VALIDATION.md stubs persist as draft in every milestone. Nyquist compliance is a non-blocking concern but the stubs mislead future readers into thinking wave tests were not implemented. Reserve 10 minutes at phase completion to update them.

### Cost Observations

- Sessions: 1 session (single day)
- Model: claude-sonnet-4-6 (balanced profile) throughout; no opus needed
- Notable: Phase 37 (Cloud Provider Switcher) was the most complex — 5 plans with isolated scan state, per-provider routes, SSE, and backward-compatible template changes — completed in ~75 minutes. The lifespan-scoped `app.state` pattern and the existing SSE infrastructure from v1.3 were the key enablers.

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
| v1.7 | 5 days | 5 | Reference parity — 26 new DDI types + Microsoft AD provider; largest methodology change (NIC counting) |
| v1.8 | 1 day | 3 | Dashboard analytics — AD tab, DNS zone panels, DDI display names; all dashboard-layer; three-scope architecture fully surfaced |
| v1.9 | 1 day | 5 | Multi-tool suite UX — home screen, breadcrumb, Infoblox brand design system, per-calculator accents, Cloud provider switcher |

### Cumulative Quality

| Milestone | New Tests | Total NIOS Tests | Zero-Dep Additions |
|-----------|-----------|------------------|--------------------|
| v1.0 | ~150+ | — | moto (test), HTMX/CSS (vendored) |
| v1.1 | 181 | 181 (182 in nios/, 32 dashboard) | pyyaml (runtime), lxml (runtime) |
| v1.2 | 13 (7 DTC + 2 DTC-10) | 188 | none (pure extension) |
| v1.3 | 20+ (Phase 19 dashboard tests) | 188+ | none (Jinja2 template additions only) |
| v1.4 | 21+ (Phase 21 attribution + Phase 22 breakdown) | 188+ | none (template additions only) |
| v1.5 | 10 (TestFormulaCards x5 + TestANA07 x1 + TestSortableTable x4) | 188+ | none (template + IIFE additions only) |
| v1.7 | 100+ (38 RED AD tests + AWS/Azure/GCP DDI tests across 5 phases) | 188+ | pywinrm (runtime, AD only) |
| v1.8 | ~16 (5 attribution + 7+4 DNS zone tests) | 188+ | none (dashboard-only additions) |
| v1.9 | ~50 (9 DESIGN-01 + 8 home/routing + 7 breadcrumb + 11 accent/cards + 14 provider switcher) | 188+ | none (dashboard CSS/HTML additions only) |

### Top Lessons (Verified Across Milestones)

1. **Isolated package boundaries prevent regressions** — v1.0 gap closure phases (7–9), v1.1 (Phases 10–15), and v1.2 (Phases 16–17) all completed with zero regressions in prior phases. The clear import boundaries (`cloud_usage.nios.*` never imports from cloud providers) made this possible across all milestones.
2. **Empirical reference data is irreplaceable** — v1.0 validated Azure with 13,363 real resources; v1.1 validated NIOS counting with the ZF Friedrichshafen 2.5M-object backup. Both caught issues unit tests missed. v1.2 shipped without a real DTC backup — DTC-V01/V02 are now tracked as explicit debt.
3. **Update requirements inline, not at close** — Five milestones, same pattern: checkboxes not ticked at execution time. The milestone close workflow corrects this retroactively. Fix: require executor to update REQUIREMENTS.md in the commit where each requirement is satisfied.
4. **gsd-tools `milestone complete` accomplishment extraction is broken** — Present across v1.1–v1.5. Tool expects `one_liner:` frontmatter; SUMMARY.md uses `provides:`. Fix either the tool or the template.
5. **Check template context before adding backend work** — v1.4 (Phases 21–22) and v1.5 (Phase 23) all shipped with zero backend changes because the data was already computed and available. The architectural investment in `_compute_summary()` returning rich per-provider/per-account dicts paid dividends across 5 consecutive phases.
6. **Close milestones formally before starting the next** — v1.4 was informally shipped before v1.5 started (same day). Retroactive archival works but loses traceability. One-milestone-at-a-time discipline keeps the planning files accurate and the archive links clean.
7. **Isolated package boundaries scale to new provider types** — The `nios/` isolation pattern from v1.1 replicated directly to `providers/ad/` in v1.7. Zero cross-provider regressions across all milestones. The pattern is proven: new data sources get their own package with clean import boundaries.
8. **Nyquist validation is a chronic gap** — Post-execution VALIDATION.md files remain incomplete across multiple milestones (v1.7: phases 25–29, v1.9: phases 33–37). Run `/gsd:validate-phase` as a standard step before milestone close, not as an optional follow-up.
9. **Design-first sequencing enables parallel sprint** — v1.9 shipped 5 phases in one day because Phase 33 (CSS foundation) resolved all token-level dependencies before Phase 36 (accent system) needed them. For any visual milestone, always sequence the design token phase first.
10. **`strict=True` xfail is a forcing function for cleanup** — Established across all v1.9 phases: strict xfail markers become pytest failures on XPASS, forcing removal at implementation time. The single carve-out (`strict=False` when assertion already satisfied) is the only safe exception.
