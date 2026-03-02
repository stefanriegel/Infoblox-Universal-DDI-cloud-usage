# Requirements: Universal DDI Cloud Usage Estimator

**Defined:** 2026-02-23
**Updated for v1.1:** 2026-02-28
**Core Value:** Accurate, auditable UDDI token estimation from any source — cloud or NIOS Grid — customers must trust the numbers and understand exactly how they were derived.

---

## v1.0 Requirements (Validated — all phases complete)

All cloud discovery requirements shipped in v1.0 (Phases 1–9). See ROADMAP.md for phase mapping.

- ✓ AWS discovery and token estimation — Phase 2
- ✓ Azure discovery and token estimation — Phase 3
- ✓ GCP discovery and token estimation — Phase 4
- ✓ Web dashboard with real-time SSE progress — Phase 5
- ✓ Cross-platform hardening (Windows 11, WSL, macOS) — Phase 6
- ✓ Integration gap closure (rate limiting, checkpointing, dashboard scan) — Phases 7–9

---

## v1.1 Requirements

NIOS Grid backup analysis integrated into the existing tool alongside cloud discovery.

### PARSE — Parse NIOS Grid backup

- [x] **PARSE-01**: User can load a NIOS Grid backup file (.tar.gz containing onedb.xml) as input to the tool via CLI flag and web dashboard upload
- [x] **PARSE-02**: Parser reads onedb.xml using streaming XML (SAX/iterparse) to handle files of 2 GB or larger without loading the full document into memory
- [x] **PARSE-03**: Parser extracts the NIOS version string from the DATABASE element header for inclusion in every output report
- [x] **PARSE-04**: Parser extracts Member objects (virtual_oid → hostname/FQDN mapping) so all per-member attribution uses human-readable names
- [x] **PARSE-05**: Parser extracts Network objects: subnet CIDR, network view, member attribution
- [x] **PARSE-06**: Parser extracts DHCP Lease objects with lease state field preserved (active, static, backup, expired, released)
- [x] **PARSE-07**: Parser extracts Fixed Address objects and Host Address objects
- [x] **PARSE-08**: Parser extracts DNS Zone objects (zone name, zone type, view assignment)
- [x] **PARSE-09**: Parser extracts DNS Record objects of all types: A, AAAA, CNAME, MX, NS, PTR, SOA, SRV, TXT
- [x] **PARSE-10**: Parser extracts Host Objects (each contributes A + PTR + optional CNAME records to DDI count) and Host Aliases (each contributes one CNAME record)
- [x] **PARSE-11**: Parser extracts DHCP Range and Exclusion Range objects
- [x] **PARSE-12**: Parser extracts Network Container objects and Network View objects
- [x] **PARSE-13**: Parser produces a structural integrity report: which object families were found, row count per type, and any missing expected families flagged as warnings

### FILTER — Member whitelist / blacklist

- [x] **FILTER-01**: User can define a member whitelist (by hostname glob pattern or virtual_oid list) — only whitelisted members and their objects are included in the analysis
- [x] **FILTER-02**: User can define a member blacklist (by hostname glob pattern or virtual_oid list) — blacklisted members and their objects are excluded from the analysis
- [x] **FILTER-03**: When both whitelist and blacklist are provided, whitelist takes precedence (whitelist-first semantics)
- [x] **FILTER-04**: Filter configuration (patterns used, member IDs matched, object counts excluded) is recorded in the output report for traceability

### COUNT — Apply NIOS→UDDI counting rules

- [x] **COUNT-01**: DDI object count aggregates: DNS records (A, AAAA, CNAME, MX, NS, PTR, SOA, SRV, TXT), Host Objects (expanded to constituent records), Host Aliases, DNS Zones, DNS Views, DHCP Ranges, Exclusion Ranges, Networks, Network Containers, Network Views — separated into Native Objects vs NIOS Objects columns
- [x] **COUNT-02**: Active IP calculation sums: active DHCP leases + fixed addresses + host addresses + network reservations (2 per subnet: network address + broadcast address)
- [x] **COUNT-03**: Lease state semantics are configurable: default counts active and static leases; user can expand to include backup, expired, or released states
- [x] **COUNT-04**: UDDI native token formula applied to NIOSX-migrated objects: DDI / 25 + Active IPs / 13 + Assets / 3
- [x] **COUNT-05**: NIOS Object token formula applied to NIOS-remaining objects in a hybrid UDDI deployment (NIOS Grid connected to UDDI platform): DDI / 50 + Active IPs / 25 + Assets / 13
- [x] **COUNT-06**: Per-member attribution computed for each member: DDI object count, Active IP count, and lease count reported separately to support hybrid split analysis

### MIGR — Member migration split

- [ ] **MIGR-01**: User can define a migration split via a YAML/JSON config file: list of member hostnames or virtual_oids assigned to `niosx` group; all others default to `nios` group
- [ ] **MIGR-02**: User can define the migration split via the web dashboard wizard: a dedicated step lists all resolved members (hostname + virtual_oid + lease count) with a toggle to mark each as NIOSX
- [ ] **MIGR-03**: Members not explicitly assigned to a group default to NIOS-remaining; the default group is configurable per analysis run
- [ ] **MIGR-04**: Migration split configuration is recorded verbatim in the output report (which members were assigned to which group and by which method)

### SCEN — Three scenario views

- [ ] **SCEN-01**: **Current grid view** — all grid objects (post-filter) counted under NIOS Object formula (DDI/50 + IPs/25 + Assets/13); produces DDI total, Active IP total, Assets total, and token total representing the full grid licensed as NIOS-managed objects today
- [ ] **SCEN-02**: **Hybrid UDDI view** — requires a migration split; NIOS-remaining members counted under NIOS Object formula; NIOSX-migrated members counted under UDDI native formula; output shows three sub-totals: NIOS-remaining tokens, NIOSX-native tokens, combined total
- [ ] **SCEN-03**: **Full migration view** — all grid objects (post-filter) counted under UDDI native formula (DDI/25 + IPs/13 + Assets/3); shows the token total if the entire grid migrates to NIOSX

### OUT — Output report

- [ ] **OUT-01**: XLS report produced with sheets: Object Counters (raw counts per object type with "in UDDI" flag), DDI Objects (Native vs NIOS column split), Active IP by Type (leases / fixed / host / reservations), Scenario Comparison (current / hybrid / full migration side-by-side), Member Attribution
- [ ] **OUT-02**: Scenario Comparison sheet shows for each scenario: DDI object count, Active IP count, Assets count, tokens per formula, and combined token total — one column per scenario
- [ ] **OUT-03**: Member Attribution sheet lists every member (post-filter) with: virtual_oid, hostname/FQDN, group assignment (nios / niosx / unassigned), DHCP lease count, DDI object count, Active IP count, token contribution under the applicable formula
- [ ] **OUT-04**: Every token total is traceable: source object counts → formula applied (NIOS Object or UDDI native) → token result; any unresolved items or assumptions logged as footnotes
- [ ] **OUT-05**: Report header captures: NIOS version, backup snapshot date, filter config applied, migration split used, analysis timestamp — so two reports from different runs are unambiguously comparable

### INTEG — Tool integration

- [ ] **INTEG-01**: User can run NIOS analysis via CLI: `python -m cloud_usage.cli --nios <backup.tar.gz>` with optional `--nios-config <config.yaml>` for migration split and filters
- [ ] **INTEG-02**: NIOS analysis is accessible via the web dashboard as a dedicated "NIOS Analysis" tab alongside the existing cloud provider tabs, with file upload, migration split wizard step, and results display

---

## Future Requirements (v1.2+)

### Advanced NIOS Analysis

- **NIOS-ADV-01**: Cross-source reconciliation — compare NIOS backup object counts against grid-exported summary reports and flag unexplained deltas by category
- **NIOS-ADV-02**: Confidence scoring — assign High/Medium/Low confidence to each metric based on data completeness and source conflicts
- **NIOS-ADV-03**: Assumption log — explicit logging when unresolved items require a default assumption (e.g., discovery IPs counted/not counted, lease state policy)
- **NIOS-ADV-04**: Snapshot date comparison — run two backups from different dates and show a delta report
- **NIOS-ADV-05**: DTC/LBDN objects in NIOS analysis — these appear in NIOS backups; include in DDI object count with explicit callout

---

## Out of Scope

| Feature | Reason |
|---------|--------|
| NIOS live API discovery | Tool is standalone, offline, backup-based — no live NIOS connections |
| Real-time / recurring NIOS analysis | Point-in-time estimation tool only |
| Infoblox Portal API integration | Standalone tool; no Portal dependency |
| Multi-cloud aggregation in single report | One report per provider/source by design |
| Mobile support | Desktop/laptop browsers only |
| DDNS Zones | NIOS-specific concept not mapped to UDDI |
| DTC/LBDN from cloud APIs | Not discoverable from cloud provider APIs |

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PARSE-01 | Phase 10 | Complete |
| PARSE-02 | Phase 10 | Complete |
| PARSE-03 | Phase 10 | Complete |
| PARSE-04 | Phase 10 | Complete |
| PARSE-05 | Phase 10 | Complete |
| PARSE-06 | Phase 10 | Complete |
| PARSE-07 | Phase 10 | Complete |
| PARSE-08 | Phase 10 | Complete |
| PARSE-09 | Phase 10 | Complete |
| PARSE-10 | Phase 10 | Complete |
| PARSE-11 | Phase 10 | Complete |
| PARSE-12 | Phase 10 | Complete |
| PARSE-13 | Phase 10 | Complete |
| FILTER-01 | Phase 11 | Complete |
| FILTER-02 | Phase 11 | Complete |
| FILTER-03 | Phase 11 | Complete |
| FILTER-04 | Phase 11 | Complete |
| COUNT-01 | Phase 11 | Complete |
| COUNT-02 | Phase 11 | Complete |
| COUNT-03 | Phase 11 | Complete |
| COUNT-04 | Phase 11 | Complete |
| COUNT-05 | Phase 11 | Complete |
| COUNT-06 | Phase 11 | Complete |
| MIGR-01 | Phase 12 | Pending |
| MIGR-02 | Phase 15 | Pending |
| MIGR-03 | Phase 12 | Pending |
| MIGR-04 | Phase 12 | Pending |
| SCEN-01 | Phase 12 | Pending |
| SCEN-02 | Phase 12 | Pending |
| SCEN-03 | Phase 12 | Pending |
| OUT-01 | Phase 13 | Pending |
| OUT-02 | Phase 13 | Pending |
| OUT-03 | Phase 13 | Pending |
| OUT-04 | Phase 13 | Pending |
| OUT-05 | Phase 13 | Pending |
| INTEG-01 | Phase 14 | Pending |
| INTEG-02 | Phase 15 | Pending |

**Coverage:**
- v1.1 requirements: 37 total
- Mapped to phases: 37
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-23*
*Last updated: 2026-02-28 after v1.1 roadmap creation*
