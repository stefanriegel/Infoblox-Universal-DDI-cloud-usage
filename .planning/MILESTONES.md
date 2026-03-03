# Milestones

## v1.3 Enhanced WebUI Experience (Shipped: 2026-03-03)

**Phases:** 18–20 (3 phases, 6 plans)
**Files changed:** ~7 src files (+270 / -16 lines in dashboard templates/routes/services)
**Codebase:** 17,601 total LOC (16,418 Python + 1,183 HTML)
**Timeline:** 2026-03-03 (same day)
**Git range:** feat(18-01) → feat(20-02)
**Requirements:** 11/11 complete (PROG-01–03, BRKDN-01–04, WIZ-01–04)

**Delivered:**
Made the NIOS analysis experience polished and auditable — real-time named progress steps during long runs, inline formula derivation in results, per-member attribution table with NIOS/NIOSX labels, and a guided migration wizard with explanatory text and bulk controls.

**Key accomplishments:**
1. Backend SSE pipeline — `_run_nios_pipeline` emits `nios_progress` events at each of 6 named steps (step N/6, label, elapsed seconds from monotonic timer); `NiosScanManager` gains thread-safe `set_progress()` / `current_progress` property
2. Frontend progress display — HTMX `#nios-progress-area` polls `GET /api/nios/progress` on `sse:nios_progress` events; `progress_display.html` renders determinate `<progress>` bar, "Step N of 6: [label]", and "Elapsed: Xs"
3. Per-scenario formula derivation — NIOS complete screen shows raw DDI/IP/Asset counts with inline formula ("1,234 DDI ÷ 50 = 24.7 tokens") for each scenario; Hybrid UDDI card renders dual sub-blocks (NIOS-remaining / NIOSX-migrated formula)
4. Member attribution table — scrollable table below Download CTA with Member, Group, DDI Objects, Active IPs, Token Contribution columns; NIOS/NIOSX color-coded badges; dedup note prevents customer misinterpretation of per-member IP sums
5. Migration wizard explanatory article — PicoCSS `<article>` callout explains NIOS (DDI÷50) vs NIOSX (DDI÷25) formulas before member assignment; Select All / Clear All batch controls with bubbling `change` events keep live counter in sync
6. Wizard step labels — consistent "Step 1: Upload Backup → Step 2: Assign Members → Step 3: Run Analysis" across all rendering paths (HTMX partial swap + full-page nios.html running block)

**Archives:**
- `.planning/milestones/v1.3-ROADMAP.md`
- `.planning/milestones/v1.3-REQUIREMENTS.md`
- `.planning/milestones/v1.3-MILESTONE-AUDIT.md`

---

## v1.2 DTC/LBDN DDI Support (Shipped: 2026-03-02)

**Phases:** 16–17 (2 phases, 4 plans)
**Files changed:** 41 files (+2,564 / -4,428 lines)
**NIOS package:** 2,463 lines of Python; 16,287 total Python LOC
**Timeline:** 2026-03-02 (same day)
**Git range:** feat(16-01) → test(17-02)
**Requirements:** 11/11 complete (DTC-01–11)

**Delivered:**
Extended the NIOS DDI estimator to recognize and count all DTC (DNS Traffic Control) object types from NIOS Grid backups — customers with DTC-enabled Grids now receive correct token estimates.

**Key accomplishments:**
1. Five DTC NiosFamily constants added — `dtc_lbdn`, `dtc_pool`, `dtc_server`, `dtc_monitor`, `dtc_topology`; 11 `_XML_TYPE_TO_FAMILY` entries covering all DTC subtypes (monitor x6, topology x2) with spec-derived annotations per DTC-11
2. DTC counter integration — all five families added to `GRID_LEVEL_FAMILIES` (member_hostname=None), `ALL_EXPECTED_FAMILIES`, and `_DDI_FAMILIES` (+1 DDI/object, no expansion logic)
3. DTC flows end-to-end — XLS Object Counters sheet extended from 21 to 26 family rows; DTC DDI verified in all three scenario outputs (current grid, hybrid split, full migration) via targeted unit tests; no changes required to scenarios.py or counter.py
4. `inspect_backup()` pre-population — all five DTC families zero-baseline in `families_found` from `ALL_EXPECTED_FAMILIES`; confirmed by DTC-10 tests
5. 7 new DTC tests (3 parser + 3 counter + 1 output); 105 tests pass across nios_output/scenarios/inspect suites; zero regressions in full 188-test suite
6. README rewritten — accurate CLI documentation for v1.2 with How To Use section covering Cloud Scan, Web Dashboard, and NIOS Grid Analysis modes

**Archives:**
- `.planning/milestones/v1.2-ROADMAP.md`
- `.planning/milestones/v1.2-REQUIREMENTS.md`

---

## v1.1 NIOS Grid Analysis (Shipped: 2026-03-02)

**Phases:** 10–15 (6 phases, 14 plans)
**Files changed:** 60 files (+11,897 / -369 lines)
**NIOS package:** 2,417 lines of Python
**Timeline:** 2026-02-28 → 2026-03-02 (3 days)
**Git range:** feat(10-01) → feat(15-02)
**Requirements:** 37/37 complete (PARSE-01–13, FILTER-01–04, COUNT-01–06, MIGR-01–04, SCEN-01–03, OUT-01–05, INTEG-01–02)

**Delivered:**
Added NIOS Grid backup analysis to the estimator — customers can now calculate UDDI tokens from their existing NIOS Grid data, model hybrid migration scenarios, and understand the licensing impact of connecting a NIOS Grid to the UDDI platform.

**Key accomplishments:**
1. Streaming NIOS Grid backup parser — lxml iterparse handles 2GB+ onedb.xml with flat memory; 2-pass member resolution maps virtual_oid → hostname; 21 object families; validated against 2.5M-object ZF Friedrichshafen backup
2. Member filter engine — hostname glob whitelist/blacklist with whitelist-first semantics and fnmatch case-insensitive matching; filter config recorded in output for traceability
3. Per-member DDI/IP/Asset counter — 4-source Active IP deduplication (active leases + fixed addresses + host addresses + network reservations); validated at 304,730 unique Active IPs against ZF reference backup
4. Three-scenario engine — current grid (NIOS Object formula DDI/50+IPs/25+Assets/13), hybrid UDDI (per-member formula split), full migration (UDDI native DDI/25+IPs/13+Assets/3)
5. 5-sheet XLS report — Object Counters, DDI Objects, Active IP by Type, Scenario Comparison, Member Attribution — with full traceability header block
6. End-to-end integration — `--nios backup.tar.gz` CLI flag + dedicated NIOS Analysis tab in web dashboard with file upload wizard, member nios/niosx toggle UI, SSE progress, and results display

**Archives:**
- `.planning/milestones/v1.1-ROADMAP.md`
- `.planning/milestones/v1.1-REQUIREMENTS.md`
- `.planning/milestones/v1.1-MILESTONE-AUDIT.md`

---

## v1.0 Cloud Discovery MVP (Shipped: 2026-02-26)

**Phases:** 1–9 (10 phases including 2.1, 14 plans for v1.0 core + gap closure phases)
**Timeline:** 2026-02-23 → 2026-02-26 (4 days)

**Delivered:**
Complete cloud discovery and UDDI token estimation across AWS, Azure, and GCP with a FastAPI + HTMX web dashboard, cross-platform support (Windows 11, WSL, macOS), and rate limiting/checkpoint resilience.

**Key accomplishments:**
1. Core infrastructure — resource schema, error taxonomy, adaptive rate limiter, checkpoint engine, auth doctor, progress tracking, discovery orchestrator
2. AWS provider — Organizations multi-account, Route53/VPC/subnet/DHCP collectors, compute/database collectors, XLS report pipeline with proof manifest
3. Azure provider — ARM multi-subscription, DDI/DNS/compute/database collectors, tenant-level rate limiting, integration tests
4. GCP provider — aggregatedList endpoints, DDI/DNS/compute collectors, project enumeration via Resource Manager
5. FastAPI + HTMX web dashboard — real-time SSE progress, results table with filtering/pagination, scan wizard, vendored static assets (no npm)
6. Cross-platform hardening — Windows 11/WSL/macOS preflight, PowerShell setup scripts with self-signed certificate signing

---
