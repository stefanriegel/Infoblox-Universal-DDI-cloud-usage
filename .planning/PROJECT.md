# Universal DDI Cloud Usage Estimator

## What This Is

A pre-sales licensing estimation tool that calculates Infoblox Universal DDI management tokens from two sources: (1) cloud discovery across AWS, Azure, and GCP, and (2) NIOS Grid backup analysis for customers migrating from NIOS to UDDI. Produces per-provider and per-scenario XLS reports with full traceability — what was counted, what was skipped, and exactly how every token total was derived. A polished HTMX web dashboard surfaces real-time progress, formula derivation, and per-member attribution so customers and pre-sales engineers can audit the numbers interactively. Built for enterprise environments: 100+ cloud accounts, multi-thousand-member NIOS Grids, and hybrid UDDI deployments where NIOS objects are licensed alongside NIOSX-native objects.

## Core Value

Accurate, auditable UDDI token estimation from any source — cloud or NIOS Grid — customers must trust the numbers and understand exactly how they were derived.

## Requirements

### Validated

- ✓ AWS discovery and token estimation — v1.0 (Phase 2)
- ✓ Azure discovery and token estimation — v1.0 (Phase 3)
- ✓ GCP discovery and token estimation — v1.0 (Phase 4)
- ✓ Web dashboard with real-time SSE progress and results browsing — v1.0 (Phase 5)
- ✓ Cross-platform: Windows 11, WSL, macOS — v1.0 (Phase 6)
- ✓ Rate limiting and checkpoint resilience — v1.0 (Phases 7–9)
- ✓ NIOS Grid backup parsing — streaming lxml iterparse, 2-pass member resolution, 26 object families (incl. 5 DTC) — v1.1/v1.2 (Phases 10, 16–17)
- ✓ Member whitelist/blacklist filter with whitelist-first semantics — v1.1 (Phase 11)
- ✓ Per-member DDI/IP/Asset counting with 4-source Active IP deduplication — v1.1 (Phase 11)
- ✓ Three licensing scenarios: current grid, hybrid UDDI split, full migration — v1.1 (Phase 12)
- ✓ 5-sheet NIOS XLS report with per-scenario comparison and member attribution — v1.1 (Phase 13)
- ✓ CLI `--nios` and `--nios-config` flags — v1.1 (Phase 14)
- ✓ Dashboard NIOS Analysis tab with file upload wizard and migration split toggles — v1.1 (Phase 15)
- ✓ Step-by-step progress feedback during NIOS analysis pipeline (named steps, step counter, elapsed time) — v1.3 (Phase 18)
- ✓ Token breakdown with formula derivation per scenario in WebUI (DDI÷N = X.X tokens inline) — v1.3 (Phase 19)
- ✓ Per-member attribution table with NIOS/NIOSX group labels in WebUI — v1.3 (Phase 19)
- ✓ Migration wizard with explanatory text, Select All/Clear All, live group counter, numbered step labels — v1.3 (Phase 20)
- ✓ Cloud per-account attribution table with formula derivation and resource-type breakdown on Summary tab — v1.4 (Phase 21)
- ✓ NIOS object family breakdown on complete screen with DDI-adjusted counts and DDI-flag column — v1.4 (Phase 22)
- ✓ Per-provider formula summary cards (DDI ÷ 25 / IPs ÷ 13 / Assets ÷ 3 inline) on cloud Results tab — v1.5 (Phase 23)
- ✓ Client-side sortable per-account attribution table (Tokens descending default, no server round-trip) — v1.5 (Phase 23)
- ✓ Collapsible resource-type breakdown rows via native `<details>/<summary>` — v1.5 (Phase 23)

### Active

<!-- v1.6 TBD — define via /gsd:new-milestone -->

(no active requirements — define next milestone with `/gsd:new-milestone`)

### Out of Scope

- DTC/LBDN objects from cloud APIs — not discoverable from cloud provider APIs
- DDNS Zones — NIOS-specific concept not mapped to UDDI
- Real-time / scheduled / recurring discovery — point-in-time estimation tool only
- Infoblox Portal API integration — standalone tool; no Portal dependency
- Multi-cloud aggregation in single report — one report per provider/source by design
- Mobile support — desktop/laptop browsers only
- NIOS live API discovery — tool is standalone, offline, backup-based; no live NIOS connections
- Multi-backup delta analysis — point-in-time only
- Live token impact preview while assigning members — requires re-running full pipeline on every toggle; too expensive for large grids
- Charts / visualizations — text tables sufficient for enterprise audit context

## Context

### Current State (after v1.5)

- **v1.5 shipped 2026-03-03** — Results Navigation: per-provider formula cards on Results tab, sortable attribution table (Tokens desc default), collapsible resource-type breakdown rows (CLOUD-06, CLOUD-07, ANA-07)
- **v1.4 shipped 2026-03-03** — Audit Depth: cloud per-account attribution table with formula derivation + resource-type breakdown (CLOUD-01–05); NIOS object family breakdown on complete screen with DDI-adjusted counts (ANA-01–06)
- **v1.3 shipped 2026-03-03** — Enhanced WebUI Experience: progress steps, formula derivation, member attribution table, wizard UX improvements
- **v1.2 shipped 2026-03-02** — DTC/LBDN DDI support; 26 NIOS object families now recognized
- **v1.1 shipped 2026-03-02** — NIOS Grid backup analysis fully integrated
- **v1.0 shipped 2026-02-26** — Cloud Discovery MVP (AWS, Azure, GCP)
- NIOS package: `src/cloud_usage/nios/` — ~2,500 lines of Python, 211+ tests passing
- Dashboard: `src/cloud_usage/dashboard/` — FastAPI routes + HTMX templates, SSE progress, NIOS wizard, sortable attribution tables with collapsible rows
- Full stack: FastAPI + HTMX dashboard, CLI, 3 cloud providers, NIOS analysis
- Total codebase: ~16,700+ LOC Python (+ HTML templates)
- Validated reference backup: ZF Friedrichshafen — 2.5M objects, 304,730 unique Active IPs (4-source dedup confirmed)
- Tech stack: Python 3.9+ (guarded), FastAPI, lxml, xlsxwriter, pyyaml, moto (tests)
- Platform validated: macOS (primary dev), CI matrix for Windows 11/WSL

### Enterprise Context

- Customers are enterprise organizations evaluating UDDI licensing before purchase
- Environments range from a handful of accounts to 100+ across providers; NIOS Grids from dozens to thousands of members
- Authentication: enterprise SSO / CLI-based auth (no service account keys); NIOS: offline backup files
- Output must be transparent: customers and their security teams audit the code and the results
- The tool runs locally on customer machines — no cloud hosting, no data leaves the machine

### Token Formulas

| Formula | Applies to | DDI divisor | IP divisor | Asset divisor |
|---------|-----------|-------------|------------|---------------|
| UDDI native | NIOSX-native objects, cloud resources | 25 | 13 | 3 |
| NIOS Object | NIOS-managed objects in hybrid UDDI | 50 | 25 | 13 |

### Known Technical Debt / Open Items

- REF-01: GCP 87-project production validation deferred — no live GCP environment available (v1.0 carry-over)
- Python 3.9 venv causes 8 pre-existing test failures on CLI `main()` version guard — known, non-blocking
- NIOS DHCP Range/Exclusion Range objects: included in DDI count as per UDDI spec; no customer validation yet
- DTC-V01/V02: DTC XML `__type` strings are spec-derived, unverified — empirical confirmation against a real DTC-containing customer backup still pending
- NIOS running-state on page-load path shows static indeterminate bar (design-bounded edge case — primary HTMX wizard path satisfies PROG-01/02/03)

## Constraints

- **Tech stack**: Python-only (FastAPI + HTML for web UI) — single language for auditability
- **Platform**: Must work on Windows 11, WSL on Windows 11, and macOS
- **Auth**: Cloud: leverage existing cloud CLI auth only (aws sso, az login, gcloud auth) — no credential storage. NIOS: offline backup files only — no live NIOS API connections
- **Access**: Read-only cloud permissions — tool must never request write access
- **Scale**: Must handle 100+ cloud accounts and 2GB+ NIOS backup files without hitting rate limits or running out of memory
- **Security**: PS1 scripts must be signed (self-signed acceptable); no secrets in code or output
- **Deployment**: Local execution only — no SaaS, no data exfiltration, runs entirely on customer machine

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Clean rewrite over incremental fix | v0 codebase had deep structural issues (error handling, checkpoint bugs, rate limiting) | ✓ Good — v1.0 shipped in 4 days, all core providers working |
| Python-native web (FastAPI + HTML) | Single language keeps audit story clean, no Node/npm complexity for customers to review | ✓ Good — HTMX vendored, zero npm/Node dependency |
| One CSV/XLS per cloud provider | Keeps output simple and provider-specific | ✓ Good — customers appreciated simplicity |
| NIOS analysis in same tool (not standalone) | Customers need both cloud and NIOS estimates in one tool for pre-sales conversations | ✓ Good — CLI flag and dashboard tab are fully additive |
| Isolated `nios/` package — no shared code with cloud | NIOS data model, formulas, and output are fundamentally different; sharing creates coupling risk | ✓ Good — zero regressions across v1.0 phases during v1.1 |
| Dual token formula (NIOS Object vs UDDI native) | Hybrid UDDI deployment licenses NIOS-managed objects at DDI/50 + IPs/25 + Assets/13; NIOSX-native at DDI/25 + IPs/13 + Assets/3 | ✓ Good — confirmed by UDDI spec; validated in scenario engine |
| Migration split via config file + dashboard wizard | CLI users need a config file; dashboard users need a wizard step — both inputs produce identical analysis | ✓ Good — `MigrationSplitConfig` frozen dataclass handles both inputs cleanly |
| 4-source Active IP deduplication | UDDI spec defines Active IPs from 4 sources; summing independently would double-count shared IPs | ✓ Good — single global set[str] dedup; empirically validated at 304,730 ZF total |
| FilterConfig default lease_states = ('active',) | Static binding_state is a manually-configured DHCP static assignment, not a dynamic lease per UDDI spec | ✓ Good — confirmed by ZF reference run; static leases were excluded |
| HOST_ADDRESS raw_attrs key = 'address' (not 'ip_address') | Empirically confirmed from ZF Friedrichshafen backup — wrong key caused COUNT-02 mismatch | ✓ Good — GAP-01 resolved; 304,730 confirmed |
| CLI auth only (no service accounts) | Enterprise customers use SSO/CLI auth; storing credentials adds security risk | ✓ Good — no credential storage ever added |
| `NiosScanManager.set_progress()` + GET endpoint for progress HTML | Avoids SSE payload size limits and keeps rendering in Python/Jinja2; clean separation of event trigger vs render | ✓ Good — HTMX hx-get on sse:nios_progress trigger works cleanly |
| Determinate `<progress value="N" max="6">` (not indeterminate spinner) | Concrete 6-step count warrants determinate bar; users see real forward progress, not just "working" | ✓ Good — more informative during 30s+ runs |
| Formula divisors hardcoded in template (not passed from backend) | Values are UDDI spec constants, immutable — passing them adds complexity without benefit | ✓ Good — Jinja2 template is self-documenting, no backend coupling |
| Member attribution subtitle warns IPs are not summable | Per-member IP counts are lease-only (not globally deduped per member); summing would exceed scenario totals and confuse customers | ✓ Good — prevents customer support questions about number discrepancy |
| Select All / Clear All use `type='button'` with bubbling `change` events | Prevents accidental form submission; dispatching change events keeps IIFE counter in sync with batch ops | ✓ Good — clean pattern; no jQuery or external JS needed |
| `data-col`/`data-value` attributes for sort key + raw value | Sort IIFE reads raw integers from `data-value` (not rendered text) — no need to strip formula fractions; `parseFloat` works cleanly | ✓ Good — reusable pattern for any future sortable table |
| Detail rows adjacent via `nextElementSibling` re-append after sort | After sorting `acct-row` elements, re-append the immediately following `acct-detail-row` sibling — preserves account↔breakdown adjacency through DOM reorder | ✓ Good — no CSS tricks required; robust to dynamic row counts |
| IIFE sort script embedded in Jinja2 template (not external JS file) | Keeps sort logic co-located with the table it controls; no globals, no load-order dependency; no build pipeline needed | ✓ Good — consistent with existing Select All IIFE pattern from v1.3 |

---
*Last updated: 2026-03-03 after v1.5 milestone*
