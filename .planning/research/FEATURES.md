# Feature Research

**Domain:** NIOS Grid backup parsing and UDDI hybrid licensing analysis (pre-sales, enterprise, on-premises CLI tool)
**Researched:** 2026-02-28
**Confidence:** HIGH — domain definition from validated customer backup (ZF: 2.5M objects, 49K subnets, 605K leases), authoritative internal framework doc (do_not_commit/CLAUDE.md), and cross-referenced Infoblox WAPI/NIOS documentation.

---

## Existing Features (v1.0 — Do Not Re-Research)

The following are already built and validated. This research covers only what v1.1 adds.

- Cloud discovery (AWS/Azure/GCP), token calculation, XLS output, web dashboard (FastAPI + HTMX)

---

## NIOS Object Type → UDDI Category Mapping

This is the canonical decision table governing what counts and where. Derived from do_not_commit/CLAUDE.md (the validated framework) and confirmed by Infoblox Universal DDI Licensing documentation.

| NIOS Object Type | UDDI Category | DDI Object | Active IP | Asset | Notes |
|------------------|--------------|-----------|-----------|-------|-------|
| DNS Zone | DDI Object | YES | no | no | All zone types: forward, reverse, stub, delegation, forward-only |
| DNS View | DDI Object | YES | no | no | Each view counts separately |
| DNS Record (A, AAAA, PTR, CNAME, MX, NS, SOA, SRV, TXT) | DDI Object | YES | no | no | Each record row counts as 1 DDI object |
| Host Object | DDI Object | YES (expanded) | no | no | Expands to constituent records — see Host Object Expansion below |
| Host Alias | DDI Object | YES | no | no | Each alias = 1 CNAME record = 1 DDI object |
| DHCP Range | DDI Object | YES | no | no | Each range row = 1 DDI object |
| Exclusion Range | DDI Object | YES | no | no | Each exclusion range row = 1 DDI object |
| Network (subnet) | DDI Object | YES | no | no | Each /N subnet = 1 DDI object |
| Network Container | DDI Object | YES | no | no | Each address block = 1 DDI object |
| Network View | DDI Object | YES | no | no | Each IP space = 1 DDI object |
| DHCP Lease (active/static) | Active IP | no | YES | no | State-filtered — see Lease State Semantics below |
| Fixed Address | Active IP | no | YES | no | Always counted regardless of state |
| Host Address (IP portion) | Active IP | no | YES | no | The IP bound to the Host Object |
| Network Reservation (per subnet) | Active IP | no | YES | no | 2 per subnet: .0 network address + .255/.last broadcast — derived, not a stored object |
| DTC Server / Pool / LBDN | DDI Object | YES (future) | no | no | Present in backups; v1.1 deferred to v1.2 (NIOS-ADV-05) |
| NIOS Member / Physical Node | Informational | no | no | no | Used for attribution and split only; not counted toward tokens |

---

## Host Object Expansion Logic

A NIOS Host Object is a composite record that expands into constituent DNS records. This expansion is mandatory — a Host Object must never be counted as a single DDI object.

**Expansion rule (per IP address bound to the host):**
- 1× A record (IPv4) OR 1× AAAA record (IPv6) — always created
- 1× PTR record — always created (reverse DNS)
- 1× CNAME record — created only if a canonical name alias is defined on the host

**Per-host alias:**
- Each alias on a Host Object (host alias) = 1 additional CNAME record = 1 additional DDI object

**Counting example:**
- Host Object with 1 IPv4 address, no alias: 2 DDI objects (A + PTR)
- Host Object with 1 IPv4 address, 1 alias: 3 DDI objects (A + PTR + CNAME)
- Host Object with 2 IPv4 addresses, no alias: 4 DDI objects (A + PTR + A + PTR)

**Why this matters for scale:**
At the ZF reference backup scale, the difference between counting Host Objects as 1 each vs. expanding them to 2+ each can represent 100K–500K DDI objects. Expansion is required for licensing accuracy.

**Confidence:** MEDIUM — the constituent record composition (A + PTR + optional CNAME) is confirmed by Infoblox NIOS documentation and the community forum (https://community.infoblox.com/discussion/15621/host-record-a-and-ptr-entries). The exact CNAME condition requires validation against the ZF backup data.

---

## Lease State Semantics

NIOS DHCP leases carry a `binding_state` field. The set of valid states (confirmed by Infoblox WAPI 2.13.7 documentation at https://ipam.illinois.edu/wapidoc/objects/lease.html):

| State | Meaning | Default: Count as Active IP? |
|-------|---------|------------------------------|
| ACTIVE | Lease currently in use by a DHCP client | YES |
| STATIC | Fixed-address lease (bound to a specific MAC) | YES |
| BACKUP | Owned by the secondary peer in a DHCP failover pair — not currently serving | NO (configurable) |
| EXPIRED | Lease existed but client never renewed; no longer valid | NO |
| RELEASED | Client explicitly returned the lease | NO |
| FREE | Available for assignment; no client | NO |
| ABANDONED | IP cannot be leased — appliance received a ping response when it tried | NO |
| DECLINED | Client explicitly rejected the address | NO |
| OFFERED | Address offered to a client but DHCP handshake not yet complete | NO |
| RESET | Lease being reset (transient administrative state) | NO |

**Default counting policy (v1.1):** Count ACTIVE + STATIC. This matches the validated framework from do_not_commit/CLAUDE.md ("IP addresses found in new or renew DHCP leases") and is the Infoblox-recommended baseline for licensing sizing.

**Why STATIC is included:** STATIC leases represent fixed-address bindings that are always consuming an IP assignment. Excluding them would undercount managed IPs.

**Why BACKUP is excluded by default:** BACKUP leases belong to the secondary peer in a failover pair — only one peer "owns" the lease at a time. Counting both would double-count failover environments. This is configurable per COUNT-03.

**Raw vs. active count distinction (validated from ZF):**
- 605,489 raw lease rows in ZF backup
- 168,295 unique IPs from active-only leases
- 182,873 unique IPs from active+static+backup
- This 3.6:1 ratio between raw rows and active-unique IPs is the primary source of "conflicting numbers" in the field

**Deduplication requirement:** Even within active leases, the same IP can appear multiple times (lease renewals create new rows). Final active IP count must deduplicate by IP address within a network view.

---

## Network Reservation Calculation

Network and broadcast addresses are "reserved" by the IP protocol itself — no DHCP client can receive them. They count toward Active IPs because they represent consumed address space managed by NIOS.

**Rule:** For every Network object (subnet), add 2 to the Active IP count:
- `.0` address (network address)
- `.255` or last address (broadcast address for /24; varies for other prefix lengths)

**Why this matters:** For a grid with 49,437 networks (ZF), reservations add 98,874 Active IPs to the count — comparable to the entire fixed-address population. Omitting reservations is a systematic undercount.

**Implementation note:** This is a derived count (subnets × 2), not parsed from stored objects. There are no "reservation" rows in onedb.xml — they are implicit.

**Confidence:** HIGH — confirmed by do_not_commit/CLAUDE.md Section 7 ("Reservations (including network and broadcast addresses)") as an agreed Active IP component.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that any NIOS backup analysis tool must have. Missing these = the tool cannot be used for pre-sales sizing conversations.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Streaming parse of .tar.gz / onedb.xml** | Backup files are 2 GB+ for enterprise grids (ZF: 2.5M objects). Loading the full XML into memory is impractical. Any analysis tool that can't handle the actual backup file is dead on arrival. | HIGH | Use `tarfile` + `xml.etree.ElementTree.iterparse` with `elem.clear()` after each object. Alternatively SAX for true streaming. Must handle the flat `<OBJECT><PROPERTY>` structure of NIOS onedb.xml. |
| **Member identity map (virtual_oid → hostname/FQDN)** | Member IDs are integers (e.g., 83, 102) in object rows. A report showing member "83" is not actionable in a customer meeting. Identity resolution is required before any per-member output. | MEDIUM | Parse Member and PhysicalNode objects first (or in pass-1 of a two-pass parse). Build virtual_oid→hostname map before attributing objects. |
| **Per-object-type counts with "counts toward DDI?" flag** | Customers need to understand what was counted. A raw number of 2.5M objects without breakdown destroys trust. The Object Counters sheet (OUT-01) is the transparency layer. | MEDIUM | Maintain per-type counters. Track separately: total parsed, total counted as DDI, total counted as Active IP, total informational-only. |
| **Active IP calculation (leases + fixed + host + reservations)** | This is the most-contested number in the field. "605K leases" vs "168K active IPs" — the tool must produce the defensible number with clear derivation. | HIGH | Four components, each with different source: leases (state-filtered), fixed addresses (all), host addresses (all IP-bound hosts), reservations (2 × subnet count). Deduplicate final set by IP address within each network view. |
| **DDI object count with correct Host Object expansion** | Host Objects are the most common source of miscounting. A customer with 50K Host Objects expects ~100K–150K DDI records from expansion, not 50K. Wrong expansion = wrong token total. | HIGH | Per NIOS docs: each Host Object → at minimum A + PTR = 2 DDI objects per IP address. CNAME added if alias defined. Must not count the Host Object container row itself. |
| **Dual token formula (NIOS Object vs UDDI native)** | The hybrid licensing model has two formulas: NIOS Object (DDI/50 + IPs/25 + Assets/13) for NIOS-remaining members; UDDI native (DDI/25 + IPs/13 + Assets/3) for NIOSX-migrated members. Applying only one formula is wrong for hybrid analysis. | MEDIUM | Both formulas must be available. Formula selection is per-member-group. Token ceiling division: `ceil(count / divisor)` with 0-guard (no minimum-of-1 rule). |
| **Three scenario views** | Pre-sales customers need to see: what they have today, what hybrid costs, and what full migration costs — as three side-by-side numbers. Showing only one number ends the conversation. | MEDIUM | SCEN-01 (current grid, NIOS Object formula for all), SCEN-02 (hybrid split, dual formula), SCEN-03 (full migration, UDDI native for all). SCEN-02 requires migration split input; SCEN-01 and SCEN-03 do not. |
| **Member attribution table** | Without per-member breakdown, customers cannot validate whether the big-DDI-count members are going to NIOS or NIOSX. The member attribution table is the audit trail for the hybrid scenario. | MEDIUM | Per member: virtual_oid, hostname/FQDN, group (nios/niosx/unassigned), DHCP lease count, DDI object count, Active IP count, token contribution. Must resolve virtual_oid→hostname before outputting. |
| **XLS report with multiple sheets** | Output must be a file customers can attach to a deal. A text blob or single-tab spreadsheet is not usable in a licensing discussion. The multi-sheet XLS is the deliverable. | MEDIUM | Sheets: Object Counters, DDI Objects, Active IP by Type, Scenario Comparison, Member Attribution. Use `xlsxwriter` (same library as v1.0 cloud output). |
| **Report traceability headers** | Two reports from different backup dates must be unambiguously distinguishable. NIOS version, backup date, filter config, and migration split must appear in the report header. | LOW | Parse NIOS version from DATABASE element in onedb.xml. Backup snapshot date from tar archive metadata. Filter/split config recorded verbatim. |
| **Configurable lease state inclusion** | The "active only vs active+static+backup" decision affects licensing totals by ~8% (ZF: 168K vs 183K). Customers and their Infoblox SEs need to agree on this before the number is final. Default is active+static; expanding to backup is a toggle. | LOW | COUNT-03: configurable per analysis run via CLI flag or config file. Must log the policy applied in the report. |
| **Structural integrity check** | A corrupted or partial backup must not silently produce wrong counts. The parser must report which object families were found, what row counts are present, and flag missing expected families (e.g., a backup with no Member rows is suspicious). | MEDIUM | PARSE-13: output a parse_summary dict before computing tokens. Check: members found (≥1), networks found, leases found. Warn if any expected family has 0 rows. |

### Differentiators (Competitive Advantage)

Features that distinguish a good hybrid licensing analysis tool from a basic object-counter.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Member whitelist/blacklist filtering** | Enterprise grids include lab members, retired members, and dev environments that should not count toward production licensing. Without filtering, every analysis is an overestimate. This is required for any grid-to-UDDI sizing engagement. | MEDIUM | FILTER-01/02: glob pattern or virtual_oid list. Whitelist-first semantics (FILTER-03). All excluded objects logged in the filter summary for the output report. |
| **Migration split wizard (web dashboard)** | The most friction-heavy input for a hybrid scenario is the member split assignment. A wizard that lists all members with lease counts and lets the SE toggle each to NIOSX in a browser is dramatically faster than editing a YAML file. | HIGH | MIGR-02: dedicated wizard step in the dashboard. Must list: hostname/FQDN, virtual_oid, lease count, DDI object count. Toggle each member to NIOS vs NIOSX. Produce the same config output as the CLI YAML path. |
| **Configurable default migration group** | Some customers want "all members default to NIOSX except these few that stay on NIOS." Others want "all default to NIOS except these few moving to NIOSX." Supporting both dramatically reduces the number of explicit assignments needed for large grids. | LOW | MIGR-03: `--default-group [nios|niosx]` flag or config key. Changes which direction the toggle goes when members are unassigned. |
| **Confidence levels per metric** | The framework (do_not_commit/CLAUDE.md) specifies: High (directly derived and reconciled), Medium (derived with documented assumptions), Low (unresolved source conflict). Surfacing confidence prevents "provisional numbers becoming final." | MEDIUM | Future v1.2 (NIOS-ADV-02). For v1.1: mark any metric that relies on configurable policy (lease state, reservation estimate) as "Medium" with the policy logged. |
| **Assumption logging** | When a default policy is applied (e.g., lease state = active+static, reservations = 2/subnet), the assumption must be logged explicitly in the report so it can be challenged. Silent defaults are a trust risk. | LOW | OUT-04 footnotes. Log per-metric: policy applied, alternative values, delta if policy changed. |
| **Cross-source reconciliation flag** | Customers often have existing capacity reports or summary exports. The tool should flag when its counts differ significantly from those sources. Even just showing the delta by category helps. | MEDIUM | Future v1.2 (NIOS-ADV-01). For v1.1: include total object counts by type in a format that can be manually compared. |
| **Versioned ruleset / analysis timestamp** | Calculator version drift is a real sales risk (per do_not_commit/CLAUDE.md). Each report must record the tool version and effective date of the counting rules so two reports from different tool versions can be compared. | LOW | Record in report header: tool version string, ruleset effective date. Makes it unambiguous when "we re-ran with the updated formula." |
| **Dashboard NIOS Analysis tab** | The web dashboard is already established for cloud analysis. Adding a NIOS Analysis tab with file upload and migration split wizard makes the tool the single entry point for all UDDI sizing — cloud and on-premises together. | HIGH | INTEG-02. Requires: file upload endpoint, parsing progress SSE, migration split wizard step, results display. Same architectural pattern as cloud scan tabs. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Count all lease states (including expired/released/free)** | "We want to know the maximum ever used." | Expired, released, and free leases are not active IPs. Using them as a licensing metric would massively overestimate (ZF: 605K raw rows vs 168K active IPs — 3.6× overcounting). Infoblox SEs explicitly flag this as the #1 source of conflicting numbers in the field. | Default to active+static. Expose backup as a configurable add-on with explicit warning that it is a conservative worst-case, not a current-usage metric. |
| **Count discovery IPs automatically** | "Network Insight discovers all devices — those should count too." | Discovery IP inclusion depends on whether the customer has Network Insight licensed and deployed, which members it runs on, and whether discovered IPs overlap with lease/fixed-address IPs. Silent inclusion without policy confirmation produces incorrect counts. | Mark discovery IPs as a separate component. Surface the raw count. Require explicit opt-in with a note: "Confirm with customer whether Network Insight is licensed and contributing data." (do_not_commit/CLAUDE.md Section 11 flags this as unresolved.) |
| **Global IP deduplication across network views** | "De-dup all IPs so we don't double-count." | The same RFC1918 address (e.g., 10.0.0.1) can legitimately appear in multiple NIOS network views — each view is an independent IP space. Global dedup would undercount environments that reuse the same address ranges across views. | Deduplicate within each network view, not globally. This mirrors the cloud tool's per-VPC dedup logic (already implemented). |
| **Combine NIOS analysis + cloud analysis in one report** | "Give me one total number across cloud and NIOS." | NIOS objects and cloud objects are licensed differently (different token formulas). Combining them in a single output obscures which formula applied to which count and makes the number unauditable. | Produce separate reports. The SE combines them in the Infoblox sizing spreadsheet, which already has rows for both NIOS Object and Native Object token inputs. |
| **Live NIOS API connection** | "Can it pull data directly from the grid instead of needing a backup?" | The tool is deliberately offline/standalone. A live NIOS connection requires: WAPI credentials, network access to the Grid Manager, and permission from the customer's security team — all of which slow down a pre-sales evaluation. Live data also introduces real-time inconsistency (leases changing mid-scan). | Backup-based analysis is point-in-time, reproducible, and requires no additional credentials. Document the backup export procedure clearly. |
| **Count DTC/LBDN objects in v1.1** | "DTC is complex configuration — it should count toward tokens." | DTC objects (Servers, Pools, LBDNs, Health Monitors, Topology Rules) are present in NIOS backups but their UDDI licensing treatment is unclear in current documentation. Including them without confirmed semantics risks over- or under-counting. They require a separate governance sign-off. | Defer to v1.2 (NIOS-ADV-05). For v1.1: parse and count them in the Object Counters sheet as informational only (not included in DDI total or token calculation). |
| **Count NIOS Views/ACLs/Filter Rules as DDI objects in v1.1** | "All managed objects should be in the count." | ACL Rules, Filter Rules, and similar administrative objects are explicitly out of scope per REQUIREMENTS.md and the existing v1.0 exclusion policy. They do not represent DNS/DHCP/IPAM service delivery and are not counted toward UDDI DDI tokens. | Log their presence in the Object Counters sheet as informational. Do not include in DDI token calculation. |
| **Automatic backup file integrity validation (hash check)** | "Make sure the backup is not corrupted." | NIOS backup files do not include an embedded hash manifest in the standard format. The tar.gz container provides basic integrity via the tar header, but there is no cryptographic guarantee for onedb.xml content. Advertising integrity validation that cannot be delivered is worse than not having it. | Perform structural integrity validation (PARSE-13): check that mandatory object families are present, counts are non-zero, and member references are resolvable. This is semantic integrity, which is more actionable than a hash check. |
| **Incremental / differential backup parsing** | "Can it parse only the changes since the last backup?" | NIOS Grid backups are always full exports — NIOS does not produce incremental onedb.xml backups. Any attempt to "diff" two backups requires parsing both in full and comparing, which doubles the compute cost with limited analytical benefit for a point-in-time sizing tool. | Snapshot date discipline: label every report with its backup date. If two reports from different dates are needed, run the tool twice and compare the output XLS files. |

---

## Feature Dependencies

```
[Backup File Input (.tar.gz)]
    └──required by──> [Streaming XML Parser]
                          └──required by──> [Object Extraction]
                                                ├──required by──> [Member Identity Map]
                                                ├──required by──> [Per-Type Object Counts]
                                                ├──required by──> [Active IP Calculation]
                                                └──required by──> [DDI Object Count (with Host Expansion)]

[Member Identity Map]
    └──required by──> [Member Whitelist/Blacklist Filter]
    └──required by──> [Member Attribution Table]
    └──required by──> [Migration Split Assignment]

[Member Whitelist/Blacklist Filter]
    └──required by──> [All Counts] (filter must be applied before counting)

[Per-Type Object Counts] ──requires──> [Object Extraction]
[DDI Object Count (with Host Expansion)] ──requires──> [Per-Type Object Counts]
[Active IP Calculation] ──requires──> [Per-Type Object Counts]

[Migration Split Assignment] ──requires──> [Member Identity Map]
    └──required by──> [Hybrid UDDI Scenario (SCEN-02)]

[Dual Token Formula]
    ├──requires──> [DDI Object Count]
    ├──requires──> [Active IP Calculation]
    └──requires──> [Migration Split Assignment] (for SCEN-02)

[Three Scenario Views]
    ├──SCEN-01──requires──> [Dual Token Formula (NIOS Object formula only)]
    ├──SCEN-02──requires──> [Migration Split Assignment + Dual Token Formula]
    └──SCEN-03──requires──> [Dual Token Formula (UDDI native formula only)]

[XLS Report]
    ├──requires──> [Three Scenario Views]
    ├──requires──> [Member Attribution Table]
    ├──requires──> [Active IP by Type breakdown]
    └──requires──> [Object Counters per type]

[Web Dashboard NIOS Tab]
    ├──requires──> [Streaming XML Parser]
    ├──requires──> [Three Scenario Views]
    └──enhances──> [Migration Split Wizard]

[Structural Integrity Check]
    └──required by──> [Any output] (must pass before token calculation is surfaced)
```

### Dependency Notes

- **Member Identity Map must be built before filtering:** You cannot apply a hostname glob filter (FILTER-01) if virtual_oid→hostname resolution has not been done. The parser must complete member object extraction before applying any filter.
- **Filter must be applied before counting:** All object counts, Active IP calculations, and token totals must reflect only post-filter objects. Applying filter after counting produces wrong per-scenario totals.
- **Host Object expansion must happen in DDI counting, not in parsing:** The parser extracts Host Object rows. The DDI counter expands each Host Object to its constituent record count (A + PTR + optional CNAME × alias). The expansion logic belongs in the counting layer, not the parse layer.
- **Deduplication is per-network-view, not global:** Active IP deduplication must be scoped to each NIOS Network View (equivalent to UDDI IP Space). The same IP in two different views counts twice.
- **SCEN-02 (Hybrid) is the only scenario that requires migration split input:** SCEN-01 and SCEN-03 can run without any split definition. This means the tool must produce SCEN-01 and SCEN-03 from a backup alone — the migration split is optional.

---

## MVP Definition

### Launch With (v1.1 — Milestone Must-Haves)

Minimum required for v1.1 to be usable in a pre-sales sizing engagement.

- [ ] **Streaming onedb.xml parser** — handles 2 GB+ without memory exhaustion (PARSE-01, PARSE-02)
- [ ] **Member identity map** — virtual_oid → hostname/FQDN (PARSE-04)
- [ ] **DDI object extraction with Host Object expansion** — A + PTR + CNAME per IP per Host Object (PARSE-05 through PARSE-12, COUNT-01)
- [ ] **Active IP calculation** — leases (active+static default) + fixed + host + reservations (COUNT-02, COUNT-03)
- [ ] **Structural integrity check** — mandatory object families present, member references resolvable (PARSE-13)
- [ ] **Dual token formula** — NIOS Object (DDI/50 + IPs/25 + Assets/13) and UDDI native (DDI/25 + IPs/13 + Assets/3) (COUNT-04, COUNT-05)
- [ ] **Three scenario views** — current grid / hybrid UDDI / full migration (SCEN-01, SCEN-02, SCEN-03)
- [ ] **Member attribution table** — per member with virtual_oid, hostname, group, counts, tokens (COUNT-06, OUT-03)
- [ ] **XLS report (5 sheets)** — Object Counters, DDI Objects, Active IP by Type, Scenario Comparison, Member Attribution (OUT-01, OUT-02, OUT-04, OUT-05)
- [ ] **CLI integration** — `python -m cloud_usage.cli --nios <backup.tar.gz>` (INTEG-01)
- [ ] **Member whitelist/blacklist** — hostname glob or virtual_oid list, whitelist-first semantics (FILTER-01, FILTER-02, FILTER-03, FILTER-04)
- [ ] **Migration split via config file** — YAML/JSON `niosx:` member list (MIGR-01, MIGR-03, MIGR-04)

### Add After Validation (v1.1.x — When Core Is Deployed)

Features to add after first customer use validates the core analysis.

- [ ] **Web dashboard NIOS Analysis tab** — file upload, migration split wizard, results display (INTEG-02, MIGR-02). Trigger: SE reports needing a visual interface for customer meetings.
- [ ] **Configurable default group** (nios vs niosx) — reduces explicit member assignments for large grids (MIGR-03 extended). Trigger: customer with 200+ members where bulk default is needed.

### Future Consideration (v1.2+)

- [ ] **Confidence scoring per metric** — High/Medium/Low with explanation (NIOS-ADV-02). Defer: governance sign-off on policy needed first.
- [ ] **Assumption log in report** — explicit notation of every default applied (NIOS-ADV-03). Defer: can be added to report footnotes without changing the core model.
- [ ] **Cross-source reconciliation** — compare backup counts against grid exports, flag unexplained deltas (NIOS-ADV-01). Defer: requires second input file (external grid export), adds UI complexity.
- [ ] **DTC/LBDN objects in DDI count** — DNS Traffic Control objects present in backups (NIOS-ADV-05). Defer: licensing semantics not confirmed; need Infoblox product sign-off.
- [ ] **Snapshot date comparison** — delta report between two backup runs (NIOS-ADV-04). Defer: point-in-time tool; manual comparison of two XLS outputs is sufficient initially.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Streaming XML parser | HIGH | HIGH | P1 |
| Member identity map | HIGH | LOW | P1 |
| DDI object count + Host expansion | HIGH | HIGH | P1 |
| Active IP calculation (4 components) | HIGH | HIGH | P1 |
| Dual token formula | HIGH | MEDIUM | P1 |
| Three scenario views | HIGH | MEDIUM | P1 |
| XLS report (5 sheets) | HIGH | MEDIUM | P1 |
| Structural integrity check | HIGH | LOW | P1 |
| Member attribution table | HIGH | MEDIUM | P1 |
| CLI integration | HIGH | LOW | P1 |
| Member whitelist/blacklist | MEDIUM | MEDIUM | P1 |
| Migration split via config file | MEDIUM | LOW | P1 |
| Configurable lease state | MEDIUM | LOW | P1 |
| Web dashboard NIOS tab | MEDIUM | HIGH | P2 |
| Dashboard migration split wizard | MEDIUM | HIGH | P2 |
| Configurable default group | LOW | LOW | P2 |
| Confidence scoring | MEDIUM | MEDIUM | P3 |
| Assumption log in report | MEDIUM | LOW | P3 |
| Cross-source reconciliation | LOW | HIGH | P3 |
| DTC/LBDN in DDI count | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for v1.1 launch — analysis is incorrect or undeliverable without it
- P2: Should have — significant SE or customer friction without it
- P3: Nice to have — future milestone

---

## Edge Cases at Scale (2.5M Objects, 605K Leases, 49K Networks)

These are not feature requests but failure modes that must be designed against.

| Edge Case | What Goes Wrong | Prevention |
|-----------|----------------|------------|
| **Member resolution failure** | Some lease or network rows reference a virtual_oid that has no corresponding Member object. If unresolved, these objects cannot be attributed to a member and are silently dropped from per-member counts. | Track unresolved virtual_oid references. Surface them as "unattributed" objects in the report. Do not silently drop. |
| **Duplicate lease rows for the same IP** | Lease renewals create new rows in onedb.xml. A single IP may have 5–10 rows from sequential renewals, all in ACTIVE state. Naive counting would count it 5–10×. | Deduplicate leases by IP address within each network view after state filtering. Use the most-recent lease row (by expiry or bind timestamp) if state matters. |
| **Host Objects with multiple IPs** | A Host Object can bind multiple IP addresses (e.g., a server with 4 NICs). Each IP bound to the host generates A + PTR records. Expansion must multiply by the number of IPs, not just count the host object once. | Expand per IP address in the Host Object's address list. Count constituent records per address, not per host object. |
| **Network View overlap** | The same subnet CIDR (e.g., 10.0.0.0/8) can exist in multiple NIOS Network Views, each representing an independent routing domain. They are distinct DDI objects and should be counted separately. | Count networks per (CIDR, network_view) tuple, not by CIDR alone. Dedup Active IPs per network view as separate IP spaces. |
| **Very large member counts (239 members in ZF)** | Grids with hundreds of members generate large member attribution tables. The web dashboard migration split wizard must be paginated or filterable. | Pagination on the member list in the wizard. Sort by lease count descending (high-impact members first). |
| **Missing NIOS version in DATABASE element** | Older backups may lack the version string in the expected location. | Log "NIOS version: unknown" rather than crashing. Warn in the report header. |
| **Empty network views** | Some backups include Network View objects with no associated networks (e.g., a view used only for DNS, not IPAM). These views still count as DDI objects. | Count Network View rows regardless of whether they have child networks. Do not skip empty views. |
| **Exclusion ranges with no parent DHCP range** | Orphaned exclusion range objects (range deleted, exclusion not cleaned up). | Count them as DDI objects regardless. Orphan detection is informational only — do not exclude orphaned ranges from the DDI count. |
| **Backup file with only partial object extraction** | A truncated tar.gz or corrupted XML mid-parse. | Catch `xml.etree.ElementTree.ParseError` and `tarfile.TarError`. Report partial parse result with a WARNING: object counts are incomplete. Do not produce token totals from a partial parse. |

---

## Object Types: UDDI DDI vs Informational-Only

**Count toward DDI objects (include in token calculation):**
DNS Zones, DNS Views, DNS Records (all types including SOA/NS), Host Objects (expanded), Host Aliases, DHCP Ranges, Exclusion Ranges, Networks (subnets), Network Containers, Network Views.

**Count toward Active IPs:**
Active+Static DHCP lease IPs (deduplicated), Fixed Address IPs, Host Object IPs, Reservation IPs (2 × subnet count, derived).

**Count toward Assets:**
Currently none explicitly defined for NIOS in v1.1 — NIOS managed assets are the domain of Network Insight discovery, which is a separate opt-in (see Anti-Features for why discovery IPs are excluded by default).

**Informational only (do not count toward tokens):**
NIOS Members, Physical Nodes, DTC Servers/Pools/LBDNs (v1.1 only — defer to v1.2), ACL Rules, Filter Rules, DDNS Zones.

---

## Sources

- `do_not_commit/CLAUDE.md` — authoritative framework document from the February 27, 2026 customer meeting (ZF Friedrichshafen engagement). Defines Active IP components, canonical NIOS→UDDI mapping, lease state semantics, and verification gates. (Confidence: HIGH — validated with customer data)
- `.planning/REQUIREMENTS.md` — v1.1 requirements definition (37 requirements across PARSE/FILTER/COUNT/MIGR/SCEN/OUT/INTEG)
- `.planning/PROJECT.md` — token ratios, reference backup stats, dual formula definition
- [Infoblox WAPI Lease Object Documentation](https://ipam.illinois.edu/wapidoc/objects/lease.html) — complete binding_state enumeration (ACTIVE, STATIC, BACKUP, EXPIRED, RELEASED, FREE, ABANDONED, DECLINED, OFFERED, RESET) with definitions
- [Host Record A and PTR Entries — Infoblox Community](https://community.infoblox.com/discussion/15621/host-record-a-and-ptr-entries) — confirms A + PTR constituent record generation per host IP
- [Universal DDI Licensing — Infoblox Documentation](https://docs.infoblox.com/space/BloxOneDDI/846954761/Universal+DDI+Licensing) — NIOS Object vs Native Object token categories
- [Universal DDI and NIOS Grid Hybrid Deployment](https://infoblox-docs.atlassian.net/wiki/spaces/BloxOneDDI/pages/290685907/Universal+DDI+and+NIOS+Grid+Hybrid+Deployment) — hybrid deployment token accounting
- [Python iterparse for large XML files](https://www.iditect.com/faq/python/using-python-iterparse-for-large-xml-files.html) — streaming parse + `elem.clear()` pattern for memory efficiency
- ZF Friedrichshafen reference backup: 2,506,601 total objects, 239 members, 49,437 networks, 605,489 raw lease rows, 168,295 unique active-only IPs, 182,873 active+static+backup IPs (validated baseline)

---
*Feature research for: NIOS Grid backup parsing and UDDI hybrid licensing analysis*
*Researched: 2026-02-28*
