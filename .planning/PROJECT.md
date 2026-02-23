# Universal DDI Cloud Usage Estimator

## What This Is

A pre-sales licensing estimation tool that discovers cloud resources across AWS, Azure, and GCP to calculate how many Infoblox Universal DDI management tokens a customer will need. Produces per-provider CSV/XLS reports with detail and summary views showing what was counted, what was skipped, and the resulting token estimate. Built for enterprise environments with 100+ cloud accounts and SSO authentication.

## Core Value

Accurate, auditable UDDI token estimation from cloud discovery — customers must trust the numbers and understand exactly how they were derived.

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

- NIOS Grid licensing / objects — customers handle this separately
- DTC objects (LBDNs, Servers, Pools, Topology Rules, Health Checks) — not discoverable from cloud APIs
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
| Native objects only (not NIOS) | NIOS licensing is handled separately; mixing would confuse the estimation | — Pending |
| CLI auth only (no service accounts) | Enterprise customers use SSO/CLI auth; storing credentials adds security risk | — Pending |

---
*Last updated: 2026-02-23 after initialization*
