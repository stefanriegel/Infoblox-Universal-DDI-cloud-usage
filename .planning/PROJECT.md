# Universal DDI Cloud Usage Estimator

## What This Is

A pre-sales licensing estimation tool that calculates Infoblox Universal DDI management tokens from two sources: (1) cloud discovery across AWS, Azure, and GCP, and (2) NIOS Grid backup analysis for customers migrating from NIOS to UDDI. Produces per-provider and per-scenario XLS reports with full traceability — what was counted, what was skipped, and exactly how every token total was derived. Built for enterprise environments: 100+ cloud accounts, multi-thousand-member NIOS Grids, and hybrid UDDI deployments where NIOS objects are licensed alongside NIOSX-native objects.

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

## Current Milestone: v1.2 DTC/LBDN DDI Support (COMPLETE)

**Goal:** Add all DTC (DNS Traffic Control) object types to the NIOS DDI counter so customers with DTC-enabled Grids receive correct token estimates.

**Delivered:**
- Recognize all DTC object families in the NIOS backup parser (LBDN, Pool, Server, Monitors, Topology)
- Count all DTC objects as +1 DDI using the existing NIOS Object formula (DDI/50 NIOS, DDI/25 NIOSX in hybrid)
- DTC counts flow through all three scenarios and XLS report unchanged

### Active

- [x] DTC/LBDN DDI support — all DTC object types recognized and counted toward DDI (v1.2, Phases 16–17)

### Out of Scope

- DTC/LBDN objects from cloud APIs — not discoverable from cloud provider APIs
- DDNS Zones — NIOS-specific concept not mapped to UDDI
- Real-time / scheduled / recurring discovery — point-in-time estimation tool only
- Infoblox Portal API integration — standalone tool; no Portal dependency
- Multi-cloud aggregation in single report — one report per provider/source by design
- Mobile support — desktop/laptop browsers only
- NIOS live API discovery — tool is standalone, offline, backup-based; no live NIOS connections
- Multi-backup delta analysis — point-in-time only (deferred to v1.2+ as NIOS-ADV-04)

## Context

### Current State (after v1.1)

- **v1.1 shipped 2026-03-02** — NIOS Grid backup analysis fully integrated
- NIOS package: `src/cloud_usage/nios/` — 2,417 lines of Python, 181 tests passing
- Full stack: FastAPI + HTMX dashboard, CLI, 3 cloud providers, NIOS analysis
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

- REF-01: GCP 87-project production validation deferred — no live GCP environment available (v1.0 carry-over, not a v1.2 blocker)
- Python 3.9 venv causes 8 pre-existing test failures on CLI `main()` version guard — known, non-blocking
- NIOS DHCP Range/Exclusion Range objects: included in DDI count as per UDDI spec; no customer validation yet
- DTC/LBDN objects in NIOS backups: present in ZF backup but excluded; need UDDI spec confirmation before adding

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

---
*Last updated: 2026-03-02 after v1.2 milestone complete*
