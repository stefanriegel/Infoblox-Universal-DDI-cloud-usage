# Requirements: Universal DDI Cloud Usage Estimator

**Defined:** 2026-03-03
**Core Value:** Accurate, auditable UDDI token estimation from any source — cloud or NIOS Grid — customers must trust the numbers and understand exactly how they were derived.

## v1.7 Requirements

Requirements for the Reference Parity milestone. Each maps to roadmap phases.

### Microsoft AD

- [ ] **AD-01**: User can scan Microsoft AD via WinRM/PowerShell with `--ad-servers` flag
- [ ] **AD-02**: Tool collects DNS zones and resource records from AD (DDI + IP counts via `Get-DnsServerZone`/`Get-DnsServerResourceRecord`)
- [ ] **AD-03**: Tool collects DHCP scopes, leases, and reservations from AD (DDI + IP counts via `Get-DhcpServerv4Scope/Lease/Reservation`)
- [ ] **AD-04**: Tool collects AD Users as Asset count (`Get-ADUser -Filter *`)
- [ ] **AD-05**: User can specify AD services to scan (dns, dhcp, user) via `--ad-services` flag
- [ ] **AD-06**: User can choose auth mode: Kerberos (default) or NTLM (user+pass) via `--ad-auth-mode`
- [ ] **AD-07**: User can autodiscover all domain controllers from a seed DC via `--ad-autodiscover`/`--ad-discovery-server`
- [ ] **AD-08**: AD results appear in XLS report with same token formula as cloud providers

### IP Methodology

- [x] **METH-01**: AWS IP count uses NIC/network interface objects (not unique IP address dedup)
- [x] **METH-02**: Azure IP count uses NIC objects (not unique IP address dedup)
- [x] **METH-03**: GCP IP count uses network interface config objects (not unique IP address dedup)
- [x] **METH-04**: Standalone ENIs, EIPs, NAT GW IPs excluded from AWS IP count (matching reference)

### AWS DDI Gaps

- [x] **AWSG-01**: Route53 Resolver endpoints counted as DDI objects
- [x] **AWSG-02**: Route53 Resolver rules and rule associations counted as DDI objects
- [x] **AWSG-03**: AWS IPAM pools, scopes, and allocations counted as DDI objects
- [x] **AWSG-04**: Internet Gateways and Customer Gateways counted as DDI objects
- [x] **AWSG-05**: Route Tables counted as DDI objects
- [x] **AWSG-06**: Direct Connect Gateways counted as DDI objects
- [x] **AWSG-07**: Route53 Health Checks and Traffic Policies counted as DDI objects

### Azure DDI Gaps

- [x] **AZUG-01**: Virtual Network Gateways (VPN and ExpressRoute) counted as DDI objects
- [x] **AZUG-02**: Private Link Services counted as DDI objects
- [x] **AZUG-03**: Virtual WANs counted as DDI objects
- [x] **AZUG-04**: Route Tables counted as DDI objects
- [x] **AZUG-05**: Azure Tenants counted as DDI objects

### GCP DDI Gaps

- [ ] **GCPG-01**: Compute Addresses (reserved static IPs) counted as DDI objects
- [ ] **GCPG-02**: GKE CIDR Ranges (control plane/pod/service) counted as DDI objects
- [ ] **GCPG-03**: Router NAT Mapping Infos counted as DDI objects
- [ ] **GCPG-04**: Target VPN Gateways (legacy) counted as DDI objects

## Future Requirements

### Microsoft AD (deferred)

- **AD-09**: Dashboard tab for AD with connection wizard and results display
- **AD-10**: AD autodiscovery progress and results surfaced in web dashboard

### Cloud DDI (deferred)

- **CLOUD-EXT-01**: Per-account breakdown for new DDI types in attribution table

## Out of Scope

| Feature | Reason |
|---------|--------|
| AD live directory browsing | Tool is a token estimator, not a directory explorer |
| AD write operations | Read-only; no modification of AD objects |
| AD Group Policy Objects | Not a DDI object type in UDDI spec |
| AD Certificate Services | Not a DDI object type in UDDI spec |
| Real-time IP dedup for AD | Point-in-time estimation; AD DNS/DHCP objects represent network objects |
| Dashboard AD wizard (v1.7) | CLI-first for AD; dashboard tab deferred to future milestone |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AD-01 | Phase 29 | Pending |
| AD-02 | Phase 29 | Pending |
| AD-03 | Phase 29 | Pending |
| AD-04 | Phase 29 | Pending |
| AD-05 | Phase 29 | Pending |
| AD-06 | Phase 29 | Pending |
| AD-07 | Phase 29 | Pending |
| AD-08 | Phase 29 | Pending |
| METH-01 | Phase 25 | Complete |
| METH-02 | Phase 25 | Complete |
| METH-03 | Phase 25 | Complete |
| METH-04 | Phase 25 | Complete |
| AWSG-01 | Phase 26 | Complete |
| AWSG-02 | Phase 26 | Complete |
| AWSG-03 | Phase 26 | Complete |
| AWSG-04 | Phase 26 | Complete |
| AWSG-05 | Phase 26 | Complete |
| AWSG-06 | Phase 26 | Complete |
| AWSG-07 | Phase 26 | Complete |
| AZUG-01 | Phase 27 | Complete |
| AZUG-02 | Phase 27 | Complete |
| AZUG-03 | Phase 27 | Complete |
| AZUG-04 | Phase 27 | Complete |
| AZUG-05 | Phase 27 | Complete |
| GCPG-01 | Phase 28 | Pending |
| GCPG-02 | Phase 28 | Pending |
| GCPG-03 | Phase 28 | Pending |
| GCPG-04 | Phase 28 | Pending |

**Coverage:**
- v1.7 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0

---
*Requirements defined: 2026-03-03*
*Last updated: 2026-03-03 after roadmap creation (v1.7)*
