# Requirements: Universal DDI Cloud Usage Estimator

**Defined:** 2026-02-23
**Core Value:** Accurate, auditable UDDI token estimation from cloud discovery — customers must trust the numbers and understand exactly how they were derived.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Authentication & Access

- [x] **AUTH-01**: User can authenticate to AWS via existing SSO profiles (`aws sso login`) without storing credentials
- [ ] **AUTH-02**: User can authenticate to Azure via `az login` (browser-based) without storing credentials
- [ ] **AUTH-03**: User can authenticate to GCP via `gcloud auth application-default login` without storing credentials
- [x] **AUTH-04**: User can run pre-flight auth validation ("auth doctor") that checks credentials are valid before starting scan
- [x] **AUTH-05**: Tool uses read-only cloud access only — never requests write permissions

### Discovery

- [x] **DISC-01**: User can discover cloud resources across all accessible AWS accounts and regions
- [ ] **DISC-02**: User can discover cloud resources across all accessible Azure subscriptions and regions
- [ ] **DISC-03**: User can discover cloud resources across all accessible GCP projects and regions
- [x] **DISC-04**: Discovery runs concurrently across multiple accounts/subscriptions/projects (scales to 100+)
- [x] **DISC-05**: Discovery handles API rate limiting with adaptive retry and exponential backoff with jitter
- [x] **DISC-06**: One failed account/subscription/project does not abort the entire scan — errors are logged and scan continues
- [x] **DISC-07**: User can filter which accounts/subscriptions/projects to include or exclude from discovery
- [x] **DISC-08**: User sees consistent progress indication during scan (`[N/total]` per provider)

### DDI Object Counting

- [x] **DDI-01**: Tool counts DNS zones per cloud provider (Route53 hosted zones, Azure DNS zones, Cloud DNS managed zones)
- [x] **DDI-02**: Tool counts DNS records within discovered zones per cloud provider
- [x] **DDI-03**: Tool counts subnets per cloud provider (VPC subnets, VNet subnets, GCP subnets)
- [x] **DDI-04**: Tool counts DHCP option sets per cloud provider (AWS DHCP option sets, Azure DHCP configs)

### Active IP Counting

- [x] **IP-01**: Tool counts all private IP addresses attached to cloud resources
- [x] **IP-02**: Tool counts all public IP addresses attached to cloud resources
- [x] **IP-03**: Active IPs are de-duplicated per IP space (per VPC/VNet/network — overlapping RFC1918 ranges across VPCs are counted correctly)

### Managed Asset Counting

- [ ] **ASSET-01**: Tool counts resources with at least one associated IP address as managed assets (VMs, load balancers, gateways, firewalls, NICs, etc.)
- [ ] **ASSET-02**: Resources without IP addresses are discovered but not counted toward tokens (security groups, S3 buckets, subnets-as-objects, projects)
- [ ] **ASSET-03**: Token-free resources are explicitly excluded even if they have IPs — AWS: EBS Volumes, S3 Buckets
- [ ] **ASSET-04**: Token-free resources are explicitly excluded — Azure: VM Disks, Management Groups, VM Monitoring Stats, Network Watcher Flow Logs, Network Watchers, Storage Accounts, Storage Containers, Subscription Tenants, Traffic Manager Profiles
- [ ] **ASSET-05**: Token-free resources are explicitly excluded — GCP: Compute Persistent Disks, Instance Groups, URL Maps, Cloud Monitoring Metric Stats, Network Connectivity Locations, Cloud Storage Bucket Policies, Cloud Storage Buckets
- [x] **ASSET-06**: Assets are de-duplicated across sources so the same asset from multiple discovery paths counts once

### Token Calculation

- [x] **TOKEN-01**: Tool calculates tokens needed using native object ratios: DDI objects / 25 + Active IPs / 13 + Managed Assets / 3
- [x] **TOKEN-02**: Each resource is categorized: counted (yes/no), category (DDI/IP/Asset), skip reason if excluded
- [x] **TOKEN-03**: Token calculation shown per account/subscription/project and as provider total

### Output & Reporting

- [ ] **OUT-01**: Tool produces one CSV/XLS file per cloud provider (3 files total)
- [ ] **OUT-02**: Each file contains a detail sheet with one row per discovered resource (resource ID, type, account, region, IPs, counted yes/no, category, skip reason)
- [ ] **OUT-03**: Each file contains a summary sheet with totals per account/subscription/project by resource type
- [ ] **OUT-04**: Tool produces a proof manifest (SHA-256 hashed JSON) documenting scan scope, ratios used, and result integrity
- [ ] **OUT-05**: Output clearly shows what was counted toward licensing and what was skipped, with reasons

### Resilience

- [x] **RESIL-01**: Tool supports checkpoint/resume for interrupted scans across all three providers
- [x] **RESIL-02**: Checkpoint saves progress atomically (no partial/corrupt checkpoints)
- [x] **RESIL-03**: Checkpoint has configurable TTL (default 48h) after which stale checkpoints are discarded

### Platform & UX

- [ ] **PLAT-01**: Tool runs on Windows 11, WSL on Windows 11, and macOS
- [ ] **PLAT-02**: Web dashboard (FastAPI + HTML) shows discovery progress in real-time via SSE
- [ ] **PLAT-03**: Web dashboard displays results with filtering and token calculation summary
- [ ] **PLAT-04**: PowerShell setup scripts are provided and signed (self-signed certificate)
- [x] **PLAT-05**: Codebase is single-language Python for customer auditability — no compiled dependencies, no obfuscation, no telemetry

### Validated Reference

- [ ] **REF-01**: GCP discovery logic validated against production environment with 87 projects — use existing GCP counting rules as reference implementation

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### UX Enhancements

- **UX-01**: Dry-run mode — show scan plan without making API calls
- **UX-02**: Estimator CSV — direct feed into Infoblox sizing spreadsheet yellow-cell format
- **UX-03**: Configurable token-free exclusion lists via external config file (not hardcoded)

### Operational

- **OPS-01**: Historical comparison — diff two scan outputs to show environment growth
- **OPS-02**: Structured JSON logging for CI/CD integration

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| NIOS Grid licensing / objects | Handled separately; Views, ACL Rules, Filter Rules, Exclusion Ranges are NIOS-specific |
| DTC objects (LBDNs, Servers, Pools) | Not discoverable from cloud APIs |
| DDNS Zones | NIOS-specific concept |
| Scheduled / recurring discovery | Point-in-time tool, not operational monitoring; Infoblox has Universal Asset Insights for that |
| Infoblox Portal API integration | Data must not leave customer machine; SEs upload manually |
| Multi-cloud aggregation in single report | Provider-specific output by design; SEs aggregate in sizing spreadsheet |
| SaaS / hosted deployment | Local execution only; enterprise data residency requirements |
| Database backend | Flat files sufficient for point-in-time estimation |
| Credential storage | Security liability; leverage existing cloud CLI auth |
| Plugin / extension system | Resource types defined by Infoblox licensing, not customers |
| Mobile support | Desktop/laptop only use case |
| Write access to any cloud | Read-only by design and constraint |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 2 | Complete |
| AUTH-02 | Phase 3 | Pending |
| AUTH-03 | Phase 4 | Pending |
| AUTH-04 | Phase 1 | Complete |
| AUTH-05 | Phase 1 | Complete |
| DISC-01 | Phase 2 | Complete |
| DISC-02 | Phase 3 | Pending |
| DISC-03 | Phase 4 | Pending |
| DISC-04 | Phase 1 | Complete |
| DISC-05 | Phase 1 | Complete |
| DISC-06 | Phase 1 | Complete |
| DISC-07 | Phase 2 | Complete |
| DISC-08 | Phase 1 | Complete |
| DDI-01 | Phase 2 | Complete |
| DDI-02 | Phase 2 | Complete |
| DDI-03 | Phase 2 | Complete |
| DDI-04 | Phase 2 | Complete |
| IP-01 | Phase 2 | Complete |
| IP-02 | Phase 2 | Complete |
| IP-03 | Phase 2 | Complete |
| ASSET-01 | Phase 2 | Pending |
| ASSET-02 | Phase 2 | Pending |
| ASSET-03 | Phase 2 | Pending |
| ASSET-04 | Phase 3 | Pending |
| ASSET-05 | Phase 4 | Pending |
| ASSET-06 | Phase 2 | Complete |
| TOKEN-01 | Phase 2 | Complete |
| TOKEN-02 | Phase 2 | Complete |
| TOKEN-03 | Phase 2 | Complete |
| OUT-01 | Phase 2 | Pending |
| OUT-02 | Phase 2 | Pending |
| OUT-03 | Phase 2 | Pending |
| OUT-04 | Phase 2 | Pending |
| OUT-05 | Phase 2 | Pending |
| RESIL-01 | Phase 1 | Complete |
| RESIL-02 | Phase 1 | Complete |
| RESIL-03 | Phase 1 | Complete |
| PLAT-01 | Phase 6 | Pending |
| PLAT-02 | Phase 5 | Pending |
| PLAT-03 | Phase 5 | Pending |
| PLAT-04 | Phase 6 | Pending |
| PLAT-05 | Phase 1 | Complete |
| REF-01 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 43 total
- Mapped to phases: 43
- Unmapped: 0

---
*Requirements defined: 2026-02-23*
*Last updated: 2026-02-23 after roadmap creation*
