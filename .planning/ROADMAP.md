# Roadmap: Universal DDI Cloud Usage Estimator

## Milestones

- ✅ **v1.0 Cloud Discovery MVP** — Phases 1–9 (shipped 2026-02-26)
- ✅ **v1.1 NIOS Grid Analysis** — Phases 10–15 (shipped 2026-03-02)
- ✅ **v1.2 DTC/LBDN DDI Support** — Phases 16–17 (shipped 2026-03-02)
- ✅ **v1.3 Enhanced WebUI Experience** — Phases 18–20 (shipped 2026-03-03)
- ✅ **v1.4 Audit Depth** — Phases 21–22 (shipped 2026-03-03)
- ✅ **v1.5 Results Navigation** — Phase 23 (shipped 2026-03-03)
- ✅ **v1.6 Wizard Navigation Fix** — Phase 24 (shipped 2026-03-03)
- 🚧 **v1.7 Reference Parity** — Phases 25–29 (in progress)

## Phases

<details>
<summary>✅ v1.0 Cloud Discovery MVP (Phases 1–9) — SHIPPED 2026-02-26</summary>

- [x] Phase 1: Core Infrastructure (4/4 plans) — completed 2026-02-23
- [x] Phase 2: AWS Provider and End-to-End Pipeline (6/6 plans) — completed 2026-02-23
- [x] Phase 2.1: Wire RateLimiter into Discovery Pipeline — INSERTED (2/2 plans) — completed 2026-02-24
- [x] Phase 3: Azure Provider (4/4 plans) — completed 2026-02-24
- [x] Phase 4: GCP Provider (4/4 plans) — completed 2026-02-24
- [x] Phase 5: Web Dashboard (4/4 plans) — completed 2026-02-24
- [x] Phase 6: Platform Hardening (2/2 plans) — completed 2026-02-25
- [x] Phase 7: Integration Gap Closure (2/2 plans) — completed 2026-02-25
- [x] Phase 8: Dashboard GCP Scan Fix (2/2 plans) — completed 2026-02-25
- [x] Phase 9: Integration Tech Debt Cleanup (1/1 plan) — completed 2026-02-26

Archive: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 NIOS Grid Analysis (Phases 10–15) — SHIPPED 2026-03-02</summary>

- [x] Phase 10: NIOS Parser and Schema (3/3 plans) — completed 2026-02-28
- [x] Phase 11: Filter and Counter (3/3 plans) — completed 2026-03-02
- [x] Phase 12: Scenario Engine (2/2 plans) — completed 2026-03-02
- [x] Phase 13: Output and Runner (2/2 plans) — completed 2026-03-02
- [x] Phase 14: CLI Integration (2/2 plans) — completed 2026-03-02
- [x] Phase 15: Dashboard Integration (2/2 plans) — completed 2026-03-02

Archive: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 DTC/LBDN DDI Support (Phases 16–17) — SHIPPED 2026-03-02</summary>

- [x] Phase 16: DTC Parser and Counter (2/2 plans) — completed 2026-03-02
- [x] Phase 17: DTC Integration Verification (2/2 plans) — completed 2026-03-02

Archive: `.planning/milestones/v1.2-ROADMAP.md`

</details>

<details>
<summary>✅ v1.3 Enhanced WebUI Experience (Phases 18–20) — SHIPPED 2026-03-03</summary>

- [x] Phase 18: NIOS Pipeline Progress Events (2/2 plans) — completed 2026-03-02
- [x] Phase 19: Token Breakdown WebUI (2/2 plans) — completed 2026-03-03
- [x] Phase 20: Migration Wizard UX (2/2 plans) — completed 2026-03-03

Archive: `.planning/milestones/v1.3-ROADMAP.md`

</details>

<details>
<summary>✅ v1.4 Audit Depth (Phases 21–22) — SHIPPED 2026-03-03</summary>

- [x] Phase 21: Cloud Per-Account Attribution Table (2/2 plans) — completed 2026-03-03
- [x] Phase 22: NIOS Object Family Breakdown (2/2 plans) — completed 2026-03-03

Archive: `.planning/milestones/v1.4-ROADMAP.md`

</details>

<details>
<summary>✅ v1.5 Results Navigation (Phase 23) — SHIPPED 2026-03-03</summary>

- [x] Phase 23: Results Navigation (2/2 plans) — completed 2026-03-03

Archive: `.planning/milestones/v1.5-ROADMAP.md`

</details>

<details>
<summary>✅ v1.6 Wizard Navigation Fix (Phase 24) — SHIPPED 2026-03-03</summary>

- [x] Phase 24: Wizard Navigation Fix (1/1 plan) — completed 2026-03-03

</details>

### 🚧 v1.7 Reference Parity (In Progress)

**Milestone Goal:** Match the reference CLI implementation — align cloud IP counting methodology with NIC/config object counting (not unique IP dedup), add missing DDI resource types across AWS/Azure/GCP, and add Microsoft AD as a full provider via WinRM/PowerShell.

- [x] **Phase 25: IP Methodology Fix** — Align AWS, Azure, GCP IP counting with reference (NIC objects, not unique IP dedup; exclude standalone ENIs/EIPs/NAT GW IPs from AWS) (completed 2026-03-03)
- [ ] **Phase 26: AWS DDI Gaps** — Add Route53 Resolver, IPAM, gateways, route tables, Direct Connect, and Route53 health/traffic types to AWS collector
- [ ] **Phase 27: Azure DDI Gaps** — Add Virtual Network Gateways, Private Link Services, Virtual WANs, Route Tables, and Tenants to Azure collector
- [ ] **Phase 28: GCP DDI Gaps** — Add Compute Addresses, GKE CIDR Ranges, Router NAT Mapping Infos, and Target VPN Gateways to GCP collector
- [ ] **Phase 29: Microsoft AD Core** — Full WinRM/PowerShell provider: DNS, DHCP, Users, Kerberos/NTLM auth, DC autodiscovery, XLS output

## Phase Details

### Phase 25: IP Methodology Fix
**Goal**: Cloud IP counting matches the reference implementation — all three providers count NIC/network interface config objects instead of deduplicating unique IP address strings, and AWS excludes standalone ENIs, EIPs, and NAT Gateway IPs
**Depends on**: Phase 24
**Requirements**: METH-01, METH-02, METH-03, METH-04
**Success Criteria** (what must be TRUE):
  1. AWS IP count in the XLS report reflects the number of EC2 network interface objects attached to instances, not the count of unique IP address strings extracted from those interfaces
  2. Azure IP count in the XLS report reflects the number of NIC (network interface card) objects, not unique IP addresses extracted from NIC configurations
  3. GCP IP count in the XLS report reflects the number of network interface config objects on compute instances, not unique IP address strings
  4. Running an AWS scan against an account with standalone ENIs, Elastic IPs, or NAT Gateway IPs produces an IP count that excludes those resources — only EC2 instance NICs are counted
**Plans**: 4 plans

Plans:
- [ ] 25-01-PLAN.md — Test scaffolding: rewrite test_ip_counter.py, update test_categorizer.py/test_asset_dedup.py, add collector assertions
- [ ] 25-02-PLAN.md — Categorizer DDI reclassification (eni/elastic-ip/nat-gateway/azure-nic/azure-public-ip) + remove fold_enis_into_parents
- [ ] 25-03-PLAN.md — Collector changes: EC2 stores nic_ip_count, GCP VM stores network_interface_count
- [ ] 25-04-PLAN.md — Implement count_nics_per_account(), wire into 3 call sites, update "Address Records" labels

### Phase 26: AWS DDI Gaps
**Goal**: The AWS collector counts all DDI object types from the reference implementation — Route53 Resolver endpoints/rules/associations, IPAM pools/scopes/allocations, Internet and Customer Gateways, Route Tables, Direct Connect Gateways, and Route53 Health Checks and Traffic Policies
**Depends on**: Phase 25
**Requirements**: AWSG-01, AWSG-02, AWSG-03, AWSG-04, AWSG-05, AWSG-06, AWSG-07
**Success Criteria** (what must be TRUE):
  1. Running an AWS scan against an account with Route53 Resolver endpoints and rules produces DDI counts that include those endpoints, rules, and rule associations as separate DDI objects
  2. Running an AWS scan against an account with IPAM configured produces DDI counts that include IPAM pools, scopes, and allocations
  3. Running an AWS scan against an account with networking resources produces DDI counts that include Internet Gateways, Customer Gateways, Route Tables, and Direct Connect Gateways
  4. Running an AWS scan against an account with Route53 health checks or traffic policies produces DDI counts that include those resources
  5. The AWS XLS report resource-type breakdown shows each new DDI type as a distinct row with its object count
**Plans**: 5 plans

Plans:
- [ ] 26-01-PLAN.md — Wave 0 test scaffolding: add failing tests for all 7 AWSG requirements to test_collectors_ddi.py + test_categorizer.py
- [ ] 26-02-PLAN.md — Extend ec2.py: collect_internet_gateways, collect_customer_gateways, collect_route_tables (AWSG-04, AWSG-05)
- [ ] 26-03-PLAN.md — Extend route53.py: Resolver collectors (AWSG-01, AWSG-02) + Health Check / Traffic Policy collectors (AWSG-07)
- [ ] 26-04-PLAN.md — Create ipam.py (5 IPAM types, AWSG-03) + direct_connect.py (AWSG-06)
- [ ] 26-05-PLAN.md — Wire all collectors into provider.py + update categorizer.py DDI_TYPES with 15 new types

### Phase 27: Azure DDI Gaps
**Goal**: The Azure collector counts all DDI object types from the reference implementation — Virtual Network Gateways (VPN and ExpressRoute), Private Link Services, Virtual WANs, Route Tables, and Azure Tenants
**Depends on**: Phase 25
**Requirements**: AZUG-01, AZUG-02, AZUG-03, AZUG-04, AZUG-05
**Success Criteria** (what must be TRUE):
  1. Running an Azure scan against a subscription with Virtual Network Gateways produces DDI counts that include both VPN Gateway and ExpressRoute Gateway objects
  2. Running an Azure scan against a subscription with Private Link Services produces DDI counts that include those services as DDI objects
  3. Running an Azure scan against a subscription with Virtual WANs, Route Tables, or Tenant-level resources produces DDI counts that include those objects
  4. The Azure XLS report resource-type breakdown shows each new DDI type as a distinct row with its object count
**Plans**: TBD

### Phase 28: GCP DDI Gaps
**Goal**: The GCP collector counts all DDI object types from the reference implementation — Compute Addresses (reserved static IPs), GKE CIDR Ranges (control plane, pod, service), Router NAT Mapping Infos, and Target VPN Gateways (legacy)
**Depends on**: Phase 25
**Requirements**: GCPG-01, GCPG-02, GCPG-03, GCPG-04
**Success Criteria** (what must be TRUE):
  1. Running a GCP scan against a project with reserved static Compute Addresses produces DDI counts that include those addresses as DDI objects
  2. Running a GCP scan against a project with GKE clusters produces DDI counts that include control plane, pod, and service CIDR ranges as separate DDI objects
  3. Running a GCP scan against a project with Cloud Routers configured for NAT or Target VPN Gateways produces DDI counts that include Router NAT Mapping Infos and Target VPN Gateway objects
  4. The GCP XLS report resource-type breakdown shows each new DDI type as a distinct row with its object count
**Plans**: TBD

### Phase 29: Microsoft AD Core
**Goal**: Users can scan a Microsoft Active Directory environment via WinRM/PowerShell and receive a complete UDDI token estimate for DNS objects, DHCP objects, and AD Users — with Kerberos or NTLM auth, optional DC autodiscovery, and an XLS report using the same token formula as cloud providers
**Depends on**: Phase 25
**Requirements**: AD-01, AD-02, AD-03, AD-04, AD-05, AD-06, AD-07, AD-08
**Success Criteria** (what must be TRUE):
  1. Running `--ad-servers dc1.corp.example.com` initiates a WinRM/PowerShell connection and produces a UDDI token estimate from that domain controller
  2. The AD scan collects DNS zones and resource records via `Get-DnsServerZone`/`Get-DnsServerResourceRecord` and produces DDI counts (zones + records) and IP counts (A/AAAA records extracted)
  3. The AD scan collects DHCP scopes, leases, and reservations via `Get-DhcpServerv4Scope/Lease/Reservation` and produces DDI counts (scopes) and IP counts (leases + reservations)
  4. The AD scan collects AD Users via `Get-ADUser -Filter *` and produces Asset counts using SID as the primary key
  5. Running `--ad-autodiscover --ad-discovery-server dc1.corp.example.com` discovers all domain controllers in the forest via `Get-ADForest`/`Get-ADDomainController` and scans each one
  6. An XLS report is produced for the AD scan with the same UDDI native token formula (DDI÷25, IPs÷13, Assets÷3) and the same report structure as cloud provider reports
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Core Infrastructure | v1.0 | 4/4 | Complete | 2026-02-23 |
| 2. AWS Provider | v1.0 | 6/6 | Complete | 2026-02-23 |
| 2.1. Wire RateLimiter | v1.0 | 2/2 | Complete | 2026-02-24 |
| 3. Azure Provider | v1.0 | 4/4 | Complete | 2026-02-24 |
| 4. GCP Provider | v1.0 | 4/4 | Complete | 2026-02-24 |
| 5. Web Dashboard | v1.0 | 4/4 | Complete | 2026-02-24 |
| 6. Platform Hardening | v1.0 | 2/2 | Complete | 2026-02-25 |
| 7. Integration Gap Closure | v1.0 | 2/2 | Complete | 2026-02-25 |
| 8. Dashboard GCP Scan Fix | v1.0 | 2/2 | Complete | 2026-02-25 |
| 9. Integration Tech Debt Cleanup | v1.0 | 1/1 | Complete | 2026-02-26 |
| 10. NIOS Parser and Schema | v1.1 | 3/3 | Complete | 2026-02-28 |
| 11. Filter and Counter | v1.1 | 3/3 | Complete | 2026-03-02 |
| 12. Scenario Engine | v1.1 | 2/2 | Complete | 2026-03-02 |
| 13. Output and Runner | v1.1 | 2/2 | Complete | 2026-03-02 |
| 14. CLI Integration | v1.1 | 2/2 | Complete | 2026-03-02 |
| 15. Dashboard Integration | v1.1 | 2/2 | Complete | 2026-03-02 |
| 16. DTC Parser and Counter | v1.2 | 2/2 | Complete | 2026-03-02 |
| 17. DTC Integration Verification | v1.2 | 2/2 | Complete | 2026-03-02 |
| 18. NIOS Pipeline Progress Events | v1.3 | 2/2 | Complete | 2026-03-02 |
| 19. Token Breakdown WebUI | v1.3 | 2/2 | Complete | 2026-03-03 |
| 20. Migration Wizard UX | v1.3 | 2/2 | Complete | 2026-03-03 |
| 21. Cloud Per-Account Attribution Table | v1.4 | 2/2 | Complete | 2026-03-03 |
| 22. NIOS Object Family Breakdown | v1.4 | 2/2 | Complete | 2026-03-03 |
| 23. Results Navigation | v1.5 | 2/2 | Complete | 2026-03-03 |
| 24. Wizard Navigation Fix | v1.6 | 1/1 | Complete | 2026-03-03 |
| 25. IP Methodology Fix | v1.7 | 4/4 | Complete | 2026-03-03 |
| 26. AWS DDI Gaps | v1.7 | 0/5 | Not started | - |
| 27. Azure DDI Gaps | v1.7 | 0/TBD | Not started | - |
| 28. GCP DDI Gaps | v1.7 | 0/TBD | Not started | - |
| 29. Microsoft AD Core | v1.7 | 0/TBD | Not started | - |
