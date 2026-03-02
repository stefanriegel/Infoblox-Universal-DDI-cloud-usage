# Universal DDI Cloud Usage Estimator

## What This Is

A pre-sales licensing estimation tool that calculates Infoblox Universal DDI management tokens from two sources: (1) cloud discovery across AWS, Azure, and GCP, and (2) NIOS Grid backup analysis for customers migrating from NIOS to UDDI. Produces per-provider and per-scenario XLS reports with full traceability — what was counted, what was skipped, and exactly how every token total was derived. Built for enterprise environments: 100+ cloud accounts, multi-thousand-member NIOS Grids, and hybrid UDDI deployments where NIOS objects are licensed alongside NIOSX-native objects.

## Core Value

Accurate, auditable UDDI token estimation from any source — cloud or NIOS Grid — customers must trust the numbers and understand exactly how they were derived.

## Current Milestone: v1.1 NIOS Grid Analysis

**Goal:** Add NIOS Grid backup analysis so customers can calculate UDDI tokens from their existing NIOS Grid data, model hybrid migration scenarios (which members stay on NIOS, which move to NIOSX), and understand the licensing impact of connecting a NIOS Grid to the UDDI platform.

**Target features:**
- Parse NIOS Grid backup (.tar.gz / onedb.xml) — streaming, handles 2GB+ files
- Extract and count all DDI objects, Active IPs, and Assets from NIOS backup data
- Whitelist/blacklist NIOS members for scoped analysis
- Member migration split: define which members move to NIOSX vs stay on NIOS
- Three scenario views: current grid | hybrid UDDI (NIOS + NIOSX split) | full migration
- Dual token formulas: NIOS Object rates (DDI/50 + IPs/25 + Assets/13) for NIOS-remaining members; native UDDI rates (DDI/25 + IPs/13 + Assets/3) for NIOSX-migrated members
- XLS report with per-scenario totals, member attribution table, and full traceability

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Discover cloud resources across AWS, Azure, and GCP
- [ ] Count DDI objects: DNS zones, DNS records, subnets, DHCP option sets per cloud provider
- [ ] Count Active IPs: all private + public IPs attached to resources, de-duplicated
- [ ] Count Managed Assets: resources with IPs, excluding token-free assets
- [ ] Token calculation: DDI/25 + IPs/13 + Assets/3 = tokens needed (native objects only)
- [ ] Token-free exclusions — AWS: EBS Volumes, S3 Buckets; Azure: VM Disks, Management Groups, VM Monitoring Stats, Network Watcher Flow Logs, Network Watchers, Storage Accounts, Storage Containers, Subscription Tenants, Traffic Manager Profiles; GCP: Compute Persistent Disks, Instance Groups, URL Maps, Cloud Monitoring Metric Stats, Network Connectivity Locations, Cloud Storage Bucket Policies, Cloud Storage Buckets
- [ ] Output 3 CSV/XLS files (one per cloud provider) with detail sheet (one row per resource) and summary sheet (totals per account/subscription/project by resource type)
- [ ] Detail sheet shows per-resource: counted toward license (yes/no), which category (DDI/IP/Asset), reason if skipped
- [ ] Scale to 100+ accounts/subscriptions/projects without API rate limiting failures
- [ ] Adaptive rate limiting and retry with backoff for cloud API throttling
- [ ] Authentication via existing cloud CLI: AWS SSO/profiles, Azure `az login`, GCP `gcloud auth`
- [ ] Read-only cloud access (no write permissions needed)
- [ ] Web dashboard (Python-native: Flask/FastAPI + HTML) showing discovery progress and results
- [ ] Cross-platform: Windows 11, WSL, macOS
- [ ] PowerShell setup scripts signed (self-signed OK)
- [ ] Code auditable by customers — single language (Python), clear structure, no obfuscation
- [ ] NIOS/NIOS Grid objects explicitly out of scope — no Views, ACL Rules, Filter Rules, Exclusion Ranges

### Out of Scope

- DTC/LBDN objects (Servers, Pools, Topology Rules, Health Checks) from cloud APIs — not discoverable
- DDNS Zones — NIOS-specific concept
- Real-time / scheduled / recurring discovery — this is a point-in-time estimation tool
- Infoblox Portal API integration — tool is standalone
- Multi-cloud aggregation in single report — one file per provider by design
- Mobile support — desktop/laptop browsers only

## Context

- Existing Python codebase exists but is being rewritten from scratch due to widespread customer errors (auth failures, API throttling, mid-scan crashes, checkpoint bugs)
- Customers are enterprise organizations evaluating UDDI licensing before purchase
- Environments range from a handful of accounts to 100+ across providers
- Authentication is always via enterprise SSO / CLI-based auth (no service account keys)
- Output must be transparent: customers and their security teams audit the code and the results
- The tool runs locally on customer machines — no cloud hosting, no data leaves the machine
- Native UDDI token ratios: 25 DDI objects/token, 13 Active IPs/token, 3 Assets/token
- NIOS Object token ratios (hybrid UDDI, NIOS-managed objects): 50 DDI objects/token, 25 Active IPs/token, 13 Assets/token
- NIOS Grid backup format: tar.gz archive containing onedb.xml (flat `<OBJECT><PROPERTY>` XML, 2GB+ for large grids)
- Member identity: NIOS members identified by virtual_oid (integer) mapped to hostname/FQDN
- Validated reference backup: ZF Friedrichshafen — 2.5M objects, 49K subnets, 605K leases, 168K active lease IPs

### Validated Reference Data (from existing codebase)

**GCP:** Validated with 87 projects — discovery logic and resource counting confirmed correct.

**Azure:** Validated with customer environment (2026-02-23):
- 13,363 resources discovered across 14 types
- Resource types: 731 VNets, 1614 subnets, 1535 NSGs, 901 routes, 991 VMs, 310 public IPs, 1904 endpoints, 95 load balancers, 85 gateways, 471 DNS zones, 4161 DNS records, 510 VMSS instances, 49 AKS clusters, 6 firewalls
- DDI Objects: 7,026 | Active IPs: 33,214
- Output files: licensing CSV, licensing summary TXT, estimator CSV, proof manifest JSON
- Customer feedback: "Worked well and was surprisingly fast"

**AWS:** Not yet validated at scale — priority for testing during Phase 2.

## Constraints

- **Tech stack**: Python-only (Flask/FastAPI + HTML for web UI) — single language for auditability
- **Platform**: Must work on Windows 11, WSL on Windows 11, and macOS
- **Auth**: Leverage existing cloud CLI auth only (aws sso, az login, gcloud auth) — no credential storage
- **Access**: Read-only cloud permissions — tool must never request write access
- **Scale**: Must handle 100+ accounts without hitting API rate limits or running out of memory
- **Security**: PS1 scripts must be signed (self-signed acceptable); no secrets in code or output
- **Deployment**: Local execution only — no SaaS, no data exfiltration, runs entirely on customer machine

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Clean rewrite over incremental fix | Current codebase has deep structural issues (error handling, checkpoint bugs, rate limiting) that make patching harder than rebuilding | — Pending |
| Python-native web (Flask/FastAPI + HTML) | Single language keeps audit story clean, no Node/npm complexity for customers to review | — Pending |
| One CSV/XLS per cloud provider | Keeps output simple and provider-specific; customers often only care about one cloud | — Pending |
| Native objects only (not NIOS) — v1.0 decision reversed in v1.1 | NIOS licensing is now in scope: customers migrating from NIOS need UDDI token estimates from their grid backup data | ⚠️ Revisit |
| Dual token formula (NIOS Object vs UDDI native) | Hybrid UDDI deployment licenses NIOS-managed objects at DDI/50 + IPs/25 + Assets/13; NIOSX-native at DDI/25 + IPs/13 + Assets/3 | — Pending |
| Migration split via config file + dashboard wizard | CLI users need a config file; dashboard users need a wizard step — both inputs produce identical analysis | — Pending |
| CLI auth only (no service accounts) | Enterprise customers use SSO/CLI auth; storing credentials adds security risk | — Pending |

---
*Last updated: 2026-02-28 after v1.1 milestone start*
