# Feature Research

**Domain:** Cloud resource discovery and UDDI licensing estimation (pre-sales, enterprise, on-premises CLI tool)
**Researched:** 2026-02-23
**Confidence:** HIGH (domain well-understood from existing codebase, PROJECT.md, and industry research)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = tool is unusable for enterprise pre-sales.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Multi-cloud discovery (AWS/Azure/GCP)** | Customers use multiple clouds; a tool missing one provider is dead on arrival for that segment | HIGH | Existing codebase covers all three. Each provider has unique APIs, resource types, and auth flows. Cannot ship with only one provider. |
| **CLI auth via existing cloud credentials** | Enterprise customers use SSO (`aws sso login`, `az login`, `gcloud auth`). Asking for service account keys or stored credentials is a security non-starter for most enterprises. | MEDIUM | Current codebase already does this. Must support AWS profiles, Azure DefaultAzureCredential chain, GCP application-default credentials. No credential storage. |
| **Read-only cloud access** | Security teams will reject any tool requesting write permissions during a pre-sales evaluation. Customers audit IAM policies before running third-party tools. | LOW | Design constraint, not implementation effort. Document required IAM policies per provider. |
| **Accurate token calculation (DDI/25 + IPs/13 + Assets/3)** | The entire purpose of the tool. Wrong numbers destroy trust and kill deals. Must match Infoblox's official sizing methodology exactly. | MEDIUM | Core business logic. Existing calculator covers this but needs validation against edge cases (overlapping IPs across VPCs, subnet reservations, IPv6). |
| **Per-provider CSV/XLS output with detail + summary sheets** | Sales Engineers need files they can hand to customers and attach to deals. Detail sheet for audit, summary sheet for the sizing conversation. | MEDIUM | Current codebase outputs CSV/TXT/JSON but lacks XLS with multi-sheet support. Need `openpyxl` for proper Excel output. Detail sheet: one row per resource with counted/skipped/category columns. Summary sheet: totals per account by resource type. |
| **Transparent resource categorization** | Customers must see exactly why each resource was counted or skipped. "Trust the numbers" is the core value prop. Every resource needs: counted yes/no, which category (DDI/IP/Asset), skip reason if excluded. | MEDIUM | Partially exists in current `_format_resource()` with `requires_management_token` field. Needs explicit category assignment and skip-reason fields. |
| **Scale to 100+ accounts/subscriptions/projects** | Enterprise environments routinely have 100-500+ AWS accounts (via Organizations), Azure subscriptions, or GCP projects. Tool must not fall over or take days. | HIGH | Current codebase has concurrent discovery (ThreadPoolExecutor) for Azure and GCP. AWS discovery is single-account only -- needs multi-account support. Memory management for large result sets is unaddressed. |
| **Adaptive rate limiting with retry and backoff** | Cloud APIs throttle aggressively at scale (AWS EC2 API: ~100 req/s per region; Azure ARM: 12,000 reads/hr per subscription; GCP: varies by API). Hitting 429s and crashing mid-scan was a primary reason for the rewrite. | HIGH | Azure has `make_retry_policy()`. AWS/GCP have no explicit rate limiting in current code. Need exponential backoff with jitter, respect for Retry-After headers, and configurable concurrency limits. |
| **Graceful error handling per account** | One failed account must not abort the entire scan. Errors must be logged, reported, and the scan must continue. | MEDIUM | Azure discover.py already does this with per-subscription error collection. AWS and GCP need the same pattern. |
| **Auth validation before scan ("auth doctor")** | Users waste 20+ minutes discovering auth failures mid-scan. Pre-flight auth check saves time and reduces support tickets. | LOW | Existing `--check-auth` in main.py. Clean implementation, just needs to be consistent across providers. |
| **Cross-platform support (Windows 11, WSL, macOS)** | Enterprise SEs and customers run Windows primarily. macOS for some SEs. WSL is common for Python tooling on Windows. | MEDIUM | Python is inherently cross-platform. Pain points: path separators, encoding (UTF-8 on Windows), subprocess calls, PowerShell scripts. Current code has `os.environ['PYTHONIOENCODING'] = 'utf-8'` fix. |
| **Checkpoint/resume for long scans** | Scans of 100+ accounts take 30-60+ minutes. Network blips, laptop sleep, or token expiry can interrupt. Losing all progress is unacceptable. | HIGH | Azure has checkpoint implementation. AWS and GCP lack it. Checkpoint design must handle: TTL expiry, atomic writes, corruption recovery, and cross-provider consistency. |
| **Token-free resource exclusions** | Resources that do not consume UDDI tokens must be explicitly excluded (EBS Volumes, S3 Buckets, Azure VM Disks, GCP Persistent Disks, etc.). Missing an exclusion = overestimation = customer distrust. | MEDIUM | Defined in PROJECT.md. Must be configurable (not hardcoded) so exclusion list can be updated without code changes. |
| **Progress indication during scan** | A CLI tool scanning 100+ accounts for 30+ minutes with no output looks hung. Users will kill it. | LOW | Azure/GCP show `[N/total]` progress. AWS shows nothing during region scanning. Need consistent progress output across all providers. |

### Differentiators (Competitive Advantage)

Features that set the product apart from generic cloud discovery tools. Not required, but valuable for the pre-sales use case.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Web dashboard (Flask/FastAPI + HTML)** | Visual progress monitoring and results browsing without CLI expertise. SEs can demo results to customers in a browser. Transforms a CLI-only tool into something presentable in a meeting. | HIGH | No HTML exists in current codebase. Needs: progress SSE/WebSocket feed, results viewer with filtering, token calculation summary. Keep it Python-native (Flask/FastAPI + vanilla HTML/JS) for auditability -- no React/Node build step. |
| **Auditable proof manifest (SHA-256 hashes)** | Customers and their security teams can verify that output files have not been tampered with. Manifest includes scope, ratios, breakdowns, and resource-set hash. Unique to this tool. | LOW | Already implemented in `export_proof_manifest()`. Needs cleanup and documentation but the concept is sound and differentiating. |
| **Code auditability (single-language, clear structure)** | Enterprise security teams review the source code before allowing it to run in their environment. Python-only with no compiled dependencies, no obfuscation, no data exfiltration. This is a trust signal that closed-source competitors cannot match. | MEDIUM | Architecture decision, not a feature to build. Enforced by: single language (Python), no network calls except cloud APIs, no telemetry, no phone-home. Document this explicitly. |
| **Account/subscription/project filtering** | Let users scope discovery to specific accounts or exclude sandbox/dev environments. Reduces scan time and focuses results on production infrastructure that matters for licensing. | LOW | GCP has `--include-projects` / `--exclude-projects` with glob patterns. AWS and Azure lack filtering. Easy to add. |
| **PowerShell setup scripts (signed)** | Windows-first enterprises often require signed scripts. Self-signed is acceptable for internal tools. Lowers the barrier for non-Python-savvy SEs on Windows. | LOW | Mentioned in PROJECT.md constraints. Simple wrapper scripts for venv creation, dependency install, and tool execution. |
| **Estimator CSV (yellow-cell format)** | Direct feed into Infoblox's sizing Excel spreadsheet. SEs copy-paste one row of numbers. Eliminates transcription errors between the tool output and the official sizing workbook. | LOW | Already implemented in `export_estimator_csv()`. Just needs to match the latest Excel template format. |
| **Concurrent multi-account discovery** | Scan multiple accounts/subscriptions/projects in parallel. At 100+ accounts, sequential scanning is too slow. Configurable worker count lets users tune for their API rate limits. | MEDIUM | Azure and GCP have this. AWS needs it. Key design decision: shared credential singleton (avoid interactive auth in worker threads), per-account error isolation, thread-safe result aggregation. |
| **IP-space-aware deduplication** | The same RFC1918 IP (e.g., 10.0.0.1) can exist in multiple VPCs. Naive global dedup undercounts. IP-space-aware dedup (per-VPC/VNet/network) gives accurate numbers. | MEDIUM | Already implemented in `ResourceCounter._infer_ip_space()`. Differentiating because most discovery tools do not handle this correctly. |
| **Dry-run / what-if mode** | Show what would be scanned (accounts, regions, resource types) without making API calls. Useful for validating scope and getting security team approval before running the actual scan. | LOW | Not in current codebase. Easy to implement: enumerate accounts/regions, print the plan, exit. |

### Anti-Features (Commonly Requested, Often Problematic)

Features to explicitly NOT build. These seem good but create problems for this specific tool's use case.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Real-time / scheduled / recurring discovery** | "Can it run on a schedule and track changes over time?" | This is a point-in-time estimation tool for pre-sales, not an operational monitoring system. Adding scheduling creates: state management complexity, stale credential handling, daemon process management, and scope creep toward a full CMDB. Infoblox already has Universal Asset Insights for continuous discovery. | Run the tool manually when needed. Each run produces timestamped output. Compare outputs manually if trend analysis is needed. |
| **Infoblox Portal API integration** | "Can it push results directly to the Infoblox portal?" | Adds network dependency, auth complexity (portal API tokens), and data exfiltration risk. Customers specifically chose a local tool because data must not leave their machine. | Export CSV/XLS files. SEs upload manually to portal. Clean separation of concerns. |
| **Multi-cloud aggregation in single report** | "Can I get one file with AWS + Azure + GCP combined?" | Provider-specific resource types, naming conventions, and token calculations differ. Combining them creates confusing output. Customers often only care about one cloud. SEs handle aggregation in their sizing spreadsheet. | One output file per provider. Estimator CSV has a consistent format across providers for easy spreadsheet aggregation. |
| **SaaS / hosted deployment** | "Can we host this as a service?" | The tool runs locally specifically because enterprise customers will not send cloud inventory data to a third party. Any hosted version would face: SOC2 compliance requirements, data residency concerns, multi-tenancy complexity, and would undermine the trust story. | Local execution only. No cloud hosting. No data leaves the customer's machine. |
| **Database backend (SQLite/PostgreSQL)** | "Store results in a database for querying." | Adds deployment complexity (database setup), migration management, and is overkill for a point-in-time estimation tool that produces flat files. Enterprise customers want files they can email/share, not a database they need to query. | CSV/XLS files with detail + summary sheets. JSON proof manifest for programmatic access. |
| **Credential storage / management** | "Store credentials so users do not have to re-auth." | Massive security liability. Enterprise security teams will reject a pre-sales tool that stores cloud credentials. Any credential leak would damage Infoblox's reputation. | Leverage existing cloud CLI auth (`aws sso login`, `az login`, `gcloud auth`). The tool never sees or stores credentials directly. |
| **Plugin / extension system** | "Let customers add their own resource types." | Adds complexity without value. The resource types and token calculations are defined by Infoblox licensing, not by customers. A plugin system creates: untested code paths, version compatibility issues, and support burden. | Update the tool's resource type definitions in new releases. Keep the exclusion list configurable (config file, not code). |
| **Mobile support** | "Can the dashboard work on phones?" | Desktop/laptop only use case. SEs use the tool in meetings on their laptops. No one runs cloud discovery from a phone. Responsive design effort is wasted. | Desktop/laptop browsers only. Minimum viewport: 1024px. |
| **NIOS Grid integration** | "Can it also count NIOS objects?" | NIOS licensing is handled separately by different tools. Mixing NIOS and cloud native objects in the same estimation would confuse both the calculation and the customer conversation. NIOS objects (Views, ACL Rules, Filter Rules, Exclusion Ranges) are not discoverable from cloud APIs. | Explicitly out of scope. Document this clearly in the tool's help output and README. |

## Feature Dependencies

```
[CLI Auth Validation] ──requires──> [Cloud Provider SDK Auth]

[Multi-Cloud Discovery]
    ├──requires──> [CLI Auth Validation]
    ├──requires──> [Rate Limiting / Retry]
    └──requires──> [Resource Type Registry]

[Token Calculation]
    ├──requires──> [Multi-Cloud Discovery]
    ├──requires──> [Resource Categorization (DDI/IP/Asset)]
    ├──requires──> [IP-Space-Aware Deduplication]
    └──requires──> [Token-Free Exclusions]

[CSV/XLS Output]
    ├──requires──> [Token Calculation]
    └──requires──> [Resource Categorization]

[Proof Manifest]
    └──requires──> [Token Calculation]

[Checkpoint/Resume]
    └──requires──> [Multi-Cloud Discovery]

[Concurrent Multi-Account]
    ├──requires──> [CLI Auth Validation]
    ├──requires──> [Rate Limiting / Retry]
    └──enhances──> [Multi-Cloud Discovery]

[Web Dashboard]
    ├──requires──> [Multi-Cloud Discovery]
    ├──requires──> [Token Calculation]
    └──enhances──> [Progress Indication]

[Account Filtering]
    └──enhances──> [Multi-Cloud Discovery]

[Dry-Run Mode]
    ├──requires──> [CLI Auth Validation]
    └──enhances──> [Account Filtering]
```

### Dependency Notes

- **Token Calculation requires IP-Space-Aware Deduplication:** Without per-VPC/VNet dedup, Active IP counts will be wrong for environments with overlapping RFC1918 ranges. This must be in place before token calculation can be trusted.
- **Concurrent Multi-Account requires Rate Limiting:** Parallel API calls without rate limiting will trigger 429 throttling, especially on Azure ARM (12,000 reads/hr per sub) and AWS EC2 APIs. Rate limiting must be built before concurrency is enabled.
- **Web Dashboard requires Multi-Cloud Discovery + Token Calculation:** The dashboard displays progress and results. Both must be stable before adding a UI layer.
- **Checkpoint/Resume enhances but does not block Multi-Cloud Discovery:** Discovery works without checkpointing; checkpointing just makes it resilient to interruption. Can be added after basic discovery works.
- **Account Filtering is independent:** Can be added at any time without affecting other features. Low risk.

## MVP Definition

### Launch With (v1)

Minimum viable product -- what is needed for SEs to run the tool and produce a sizing estimate.

- [ ] **AWS/Azure/GCP discovery** -- all three providers with concurrent multi-account support
- [ ] **CLI auth validation** -- pre-flight check before scan starts
- [ ] **Adaptive rate limiting with retry/backoff** -- handle 429s gracefully at scale
- [ ] **Token calculation** -- DDI/25 + IPs/13 + Assets/3 with IP-space dedup
- [ ] **Resource categorization** -- every resource labeled: counted (yes/no), category (DDI/IP/Asset), skip reason
- [ ] **CSV/XLS output** -- per-provider files with detail + summary sheets
- [ ] **Proof manifest** -- SHA-256 hashed JSON for auditability
- [ ] **Checkpoint/resume** -- for all three providers
- [ ] **Progress indication** -- consistent `[N/total]` output across providers
- [ ] **Graceful per-account error handling** -- one failure does not abort the scan
- [ ] **Cross-platform** -- Windows 11, WSL, macOS

### Add After Validation (v1.x)

Features to add once the core is deployed and validated with real customer environments.

- [ ] **Web dashboard** -- Flask/FastAPI + HTML for progress monitoring and results browsing. Trigger: SEs request a visual interface for customer-facing demos.
- [ ] **Account/subscription/project filtering** -- `--include` / `--exclude` with glob patterns for all three providers. Trigger: customers with 200+ accounts need to scope scans.
- [ ] **Dry-run mode** -- show scan plan without API calls. Trigger: security teams want to review scope before approving the scan.
- [ ] **PowerShell setup scripts (signed)** -- Windows onboarding. Trigger: SEs report friction with manual Python/pip setup on Windows.
- [ ] **Estimator CSV refinement** -- match the latest Infoblox sizing Excel yellow-cell format exactly. Trigger: updated sizing spreadsheet from product team.

### Future Consideration (v2+)

Features to defer until the tool is stable and widely deployed.

- [ ] **Configurable exclusion lists** -- external config file for token-free resource types. Defer: hardcoded list is sufficient until licensing model changes.
- [ ] **Historical comparison** -- diff two scan outputs to show environment growth. Defer: manual comparison is sufficient initially.
- [ ] **Structured logging (JSON)** -- machine-readable logs for CI/CD integration. Defer: human-readable console output is sufficient for the pre-sales use case.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Multi-cloud discovery (AWS/Azure/GCP) | HIGH | HIGH | P1 |
| Token calculation (DDI/IP/Asset) | HIGH | MEDIUM | P1 |
| Rate limiting / retry / backoff | HIGH | HIGH | P1 |
| CSV/XLS output (detail + summary) | HIGH | MEDIUM | P1 |
| CLI auth validation | HIGH | LOW | P1 |
| Resource categorization (counted/skipped/reason) | HIGH | MEDIUM | P1 |
| Checkpoint/resume (all providers) | HIGH | HIGH | P1 |
| Concurrent multi-account discovery | HIGH | MEDIUM | P1 |
| Graceful per-account error handling | HIGH | LOW | P1 |
| Progress indication | MEDIUM | LOW | P1 |
| Cross-platform (Win/WSL/macOS) | HIGH | MEDIUM | P1 |
| IP-space-aware deduplication | HIGH | MEDIUM | P1 |
| Token-free exclusions | HIGH | LOW | P1 |
| Proof manifest (SHA-256) | MEDIUM | LOW | P1 |
| Web dashboard | MEDIUM | HIGH | P2 |
| Account filtering (include/exclude) | MEDIUM | LOW | P2 |
| Dry-run mode | LOW | LOW | P2 |
| PowerShell setup scripts | MEDIUM | LOW | P2 |
| Estimator CSV (yellow-cell format) | MEDIUM | LOW | P2 |
| Configurable exclusion lists | LOW | MEDIUM | P3 |
| Historical comparison | LOW | MEDIUM | P3 |
| Structured logging | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for launch -- tool is broken or unusable without it
- P2: Should have, add when core is stable
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | ServiceNow CLE | Flexera Cloud | This Tool (UDDI Estimator) |
|---------|----------------|---------------|---------------------------|
| Multi-cloud support | AWS + Azure (no GCP in CLE) | AWS, Azure, GCP, OCI | AWS, Azure, GCP |
| Deployment model | SaaS (ServiceNow instance) | SaaS | Local CLI (no data leaves customer machine) |
| Auth method | Service account credentials | Service account / API keys | CLI-based SSO (no stored credentials) |
| Licensing model support | ServiceNow ITOM/CCM licensing | Multi-vendor (Microsoft, Oracle, SAP) | Infoblox UDDI-specific (25/13/3 ratios) |
| Output format | PDF report | Dashboard + exports | CSV/XLS + JSON proof manifest |
| Auditability | Closed source, SaaS | Closed source, SaaS | Open source Python, customer-auditable |
| Cost | ServiceNow license required | Flexera license required | Free (pre-sales tool) |
| Scale | Enterprise (via ServiceNow infra) | Enterprise (via SaaS infra) | 100+ accounts (local machine resources) |
| Setup complexity | Mid-server + service accounts | Agent + credentials | `pip install` + existing cloud CLI auth |
| Resource-level transparency | Summary counts only | Aggregated dashboards | Per-resource detail with counted/skipped/reason |

**Key differentiators vs. competitors:**
1. **Local execution** -- data never leaves the customer's machine. Competitors are SaaS.
2. **Code auditability** -- single-language Python, no obfuscation. Competitors are closed source.
3. **Zero cost** -- pre-sales tool, not a licensed product. Competitors require platform licenses.
4. **Resource-level transparency** -- every resource shows counted/skipped/reason. Competitors show summary counts.
5. **No credential storage** -- leverages existing CLI auth. Competitors require service account setup.

## Sources

- Existing codebase analysis: `main.py`, `shared/licensing_calculator.py`, `shared/resource_counter.py`, `aws_discovery/discover.py`, `azure_discovery/discover.py`, `gcp_discovery/discover.py`
- [ServiceNow ITOM Cloud License Estimator](https://store.servicenow.com/store/app/c44eef2a1b646a50a85b16db234bcb38) -- closest competitor in the "license estimation" space
- [Flexera Cloud License Management](https://www.flexera.com/products/flexera-one/cloud-license-management) -- enterprise multi-vendor license management
- [AWS API throttling best practices](https://docs.aws.amazon.com/ec2/latest/devguide/ec2-api-throttling.html) -- rate limiting patterns
- [Azure ARM throttling guidance](https://learn.microsoft.com/en-us/graph/throttling) -- per-subscription rate limits
- [Infoblox Universal DDI Licensing](https://docs.infoblox.com/space/BloxOneDDI/846954761/Universal+DDI+Licensing) -- official token ratios
- PROJECT.md constraints and requirements (authoritative for this specific tool)

---
*Feature research for: Cloud resource discovery and UDDI licensing estimation*
*Researched: 2026-02-23*
