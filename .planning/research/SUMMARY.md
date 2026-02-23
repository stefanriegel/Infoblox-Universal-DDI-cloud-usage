# Project Research Summary

**Project:** Infoblox Universal DDI Cloud Usage Estimator
**Domain:** Multi-cloud resource discovery CLI + local web dashboard (Python)
**Researched:** 2026-02-23
**Confidence:** HIGH

## Executive Summary

The Universal DDI Cloud Usage Estimator is a point-in-time, local-execution pre-sales tool that discovers cloud resources across AWS, Azure, and GCP and translates them into Infoblox UDDI token estimates. Experts build this class of tool as a CLI-first Python application with optional lightweight web dashboard — single language, no build toolchain, no external services, and no credential storage. The trust story is the product: enterprise security teams audit the source before running it, so clarity and minimalism are non-negotiable constraints that must drive every architectural decision.

The recommended approach is a clean rewrite of the existing codebase using FastAPI (ASGI) + HTMX for the optional dashboard, `asyncio.to_thread()` wrapping synchronous cloud SDKs for concurrency, a single-level ThreadPoolExecutor (no nesting) governed by per-provider semaphores, and JSONL streaming to disk instead of in-memory list accumulation. The existing codebase has partially correct implementations across all three providers, but contains five structural defects — nested thread pools, uncoordinated rate limiting, monolithic discovery functions, duplicated post-processing pipelines, and in-memory resource accumulation — that prevent reliable scale beyond ~10 accounts without a redesign.

The primary risk is scale failure: the existing patterns look correct at small scale and fail silently at 100+ accounts. The antidotes are JSONL streaming, a shared rate-limiting abstraction built before any provider code is written, token expiry detection at scan start, and a provider-agnostic error taxonomy that surfaces actionable user messages instead of opaque SDK exceptions. Phases 1 and 2 of the roadmap carry the highest risk; getting the infrastructure layer right in Phase 1 determines whether the provider implementations in Phase 2 are reliable at enterprise scale.

---

## Key Findings

### Recommended Stack

The stack is entirely Python, with no Node.js build toolchain anywhere. FastAPI (>=0.115) with Uvicorn provides the ASGI server needed for SSE-based progress streaming; Flask is explicitly ruled out because SSE requires async. HTMX 2.x handles all frontend interactivity via HTML fragments, eliminating the need for any JavaScript framework. Pico CSS provides professional styling in 12KB with no PostCSS build step. All cloud SDKs (boto3, azure-mgmt-*, google-cloud-*) are synchronous and should be wrapped with `asyncio.to_thread()` — not replaced with async wrappers like aioboto3, which add dependency complexity with no benefit for a single-run tool. uv replaces pip + pip-tools + virtualenv as the package manager, and Ruff replaces flake8 + black + isort. pandas is explicitly removed from the dependency tree (replaced by stdlib csv + openpyxl), reducing install size by ~150MB.

**Core technologies:**
- **Python 3.12+**: Runtime — 3.12 is the floor for performance improvements and improved error messages; 3.13 is the recommended target
- **FastAPI + Uvicorn**: HTTP API + HTML serving — async-native, built-in Pydantic, trivial SSE support
- **HTMX 2.x + Pico CSS**: Frontend — zero JavaScript to write, zero build toolchain, vendored for air-gapped installs
- **sse-starlette**: Server-Sent Events — W3C spec compliant, handles heartbeats and proxy timeouts automatically
- **boto3 / azure-mgmt-* / google-cloud-***: Cloud SDKs — official, synchronous, wrapped via `asyncio.to_thread()`
- **tenacity + asyncio.Semaphore**: Retry and rate limiting — exponential backoff with jitter, provider-scoped concurrency limits
- **openpyxl + stdlib csv**: Export — replaces pandas for 1/50th the install footprint
- **uv + pyproject.toml**: Package management — cross-platform lockfile, replaces pip + venv + pip-tools
- **Pydantic v2 + pydantic-settings**: Data models + config — Rust-core validation, type-safe settings from env vars
- **pytest + pytest-asyncio + moto**: Testing — async test support, AWS API mocking without live credentials

### Expected Features

**Must have (table stakes, v1):**
- Multi-cloud discovery (AWS/Azure/GCP) with concurrent multi-account support — missing one provider = tool is dead on arrival for that cloud segment
- CLI auth via existing SSO credentials (`aws sso login`, `az login`, `gcloud auth`) — no credential storage, non-negotiable security constraint
- Adaptive rate limiting with exponential backoff + jitter — the primary reason for the rewrite; 429 cascades at scale are fatal
- Accurate token calculation (DDI/25 + IPs/13 + Assets/3) with IP-space-aware deduplication — wrong numbers destroy trust
- Resource categorization: every resource labeled counted/skipped with explicit skip reason — "trust the numbers" is the core value proposition
- CSV/XLS output per provider with detail + summary sheets — sales engineers need files to hand to customers
- Checkpoint/resume for all three providers — 30-60 minute scans on 100+ accounts cannot afford to restart from zero
- Graceful per-account error handling — one failed account must not abort the scan
- Progress indication — a CLI that shows nothing for 30 minutes looks hung; users kill it and lose progress
- Cross-platform (Windows 11, WSL, macOS) — enterprise SEs are primarily on Windows
- Proof manifest (SHA-256 hashed JSON) — auditability differentiator
- Auth validation pre-flight ("auth doctor") — prevent mid-scan auth failures

**Should have (competitive, v1.x):**
- Web dashboard (FastAPI + HTMX) — transforms CLI tool into something presentable in a customer meeting
- Account/subscription/project filtering with glob patterns — production scope management for 200+ account environments
- Dry-run / what-if mode — security team approval before running the actual scan
- PowerShell setup scripts (signed) — Windows onboarding for non-Python-savvy SEs
- Estimator CSV in yellow-cell format — direct feed into Infoblox sizing spreadsheet

**Defer (v2+):**
- Configurable exclusion lists (external config file) — hardcoded list is sufficient until licensing model changes
- Historical comparison between scan outputs — manual file comparison is sufficient initially
- Structured logging (JSON) — human-readable output is sufficient for pre-sales use case

**Anti-features (explicitly do not build):**
- Recurring/scheduled discovery — scope creep toward a CMDB; Infoblox has Universal Asset Insights for that
- Infoblox Portal API push — violates the "data never leaves customer machine" trust constraint
- Multi-cloud aggregated report — provider-specific naming/types make combined output confusing
- Database backend (SQLite/PostgreSQL) — customers want files they can email, not a database to query
- Credential storage — security teams will reject any pre-sales tool that stores cloud credentials

### Architecture Approach

The target architecture separates the tool into eight components with strict one-way dependencies: CLI/Web UI calls the Orchestrator, the Orchestrator dispatches to Provider Modules (one per cloud) via a single-level ThreadPoolExecutor, Provider Modules acquire and release provider-specific Rate Limiters before API call batches, results stream to the Result Collector as JSONL on disk (not a Python list), and post-processing runs sequentially through Resource Counter, Licensing Calculator, and Report Generator using the common resource schema. The Web UI (FastAPI + SSE) is an optional overlay on the same Orchestrator; removing it does not affect CLI operation. The core innovation over the existing architecture is moving concurrency governance up to the Orchestrator level (single thread pool, semaphore per provider) and moving result storage down to disk (JSONL streaming), eliminating both nested-pool deadlock risk and memory exhaustion at scale.

**Major components:**
1. **Orchestrator** (`core/orchestrator.py`) — account enumeration, concurrency management, checkpoint coordination, progress tracking; the single integration point between UI and providers
2. **Provider Modules** (`providers/aws/`, `providers/azure/`, `providers/gcp/`) — one package per cloud with auth, discovery, and config; conforms to abstract base interface; never imports orchestrator
3. **Rate Limiter** (`core/rate_limiter.py`) — per-provider semaphore + token bucket; Azure gets tenant-level coordination; injected by orchestrator, not instantiated by providers
4. **Result Collector** (`core/result_collector.py`) — append-only JSONL temp file; thread-safe writes; provides iterator for post-processing; constant memory regardless of resource count
5. **Resource Counter** (`counting/resource_counter.py`) — classifies resources into DDI/IP/Asset; IP-space-aware deduplication per VPC/VNet; operates on common schema only
6. **Licensing Calculator** (`licensing/calculator.py`) — pure math: token ratios applied to counts; no cloud SDK imports
7. **Report Generator** (`reporting/generator.py`) — CSV + XLS (openpyxl) with detail and summary sheets; reads JSONL collector for detail rows
8. **Web UI** (`web/app.py`) — FastAPI with SSE endpoint for progress; Jinja2 templates; HTMX frontend; optional, not required for CLI operation

### Critical Pitfalls

1. **Auth token expiry mid-scan** — SSO/OAuth tokens expire during long scans (1-4 hours). Module-level credential singletons have no TTL check. Fix: check token expiry at scan start, compare against estimated scan duration, warn users; add per-account credential refresh boundaries. Address in Phase 1 before any provider code runs.

2. **Azure ARM tenant-level rate limiting cascade** — ARM throttles at 25 reads/sec across the entire tenant (not per subscription). With 4 concurrent subscription workers each making 50+ API calls, cascading 429s stall the entire scan. Fix: tenant-level semaphore limiting total concurrent ARM requests to ~10-15/sec; exponential backoff with full jitter (not fixed intervals); respect `Retry-After` and `x-ms-ratelimit-remaining-tenant-reads` headers. Must be designed into Azure provider, not retrofitted.

3. **Memory exhaustion at scale** — all resources accumulated in a Python list; 100+ accounts with large environments can exceed 2GB RAM. Fix: JSONL streaming to disk — each account's results appended atomically; post-processing reads line-by-line. This requires architectural commitment in Phase 2; cannot be retrofitted.

4. **Signal handler state loss and checkpoint corruption** — Ctrl+C calls a signal handler that cannot access local scan state, so "saving checkpoint" prints but no checkpoint is saved. Atomic checkpoint writes (`fsync` + `os.rename`) and `threading.Event`-based graceful shutdown prevent both partial writes and state loss. Checkpoint format must include a schema version field for forward compatibility.

5. **Broad exception handling masks actionable errors** — 60+ `except Exception` instances in the current codebase swallow the distinction between throttling (retry), permission denied (fix IAM), API disabled (enable the API), and genuine bugs. Fix: define a provider-agnostic error taxonomy (`ThrottlingError`, `AuthExpiredError`, `PermissionDeniedError`, `ApiDisabledError`) and map each cloud SDK exception to it in a single module per provider. Must be established in Phase 1 before any provider code is written.

---

## Implications for Roadmap

Based on research, the architecture defines a clear dependency graph that translates directly into phases. Phase 1 is the highest-leverage investment: four of the six critical pitfalls must be addressed there before any cloud API code is written.

### Phase 1: Core Infrastructure and Framework

**Rationale:** Everything downstream depends on the resource schema, error taxonomy, rate limiter interface, result collector, and checkpoint abstraction. Building provider code before these exist forces retrofitting — which is precisely how the current codebase accumulated its structural defects. Phase 1 has no cloud API dependencies, making it fully testable in isolation.

**Delivers:** A working foundation: common resource schema (TypedDict/dataclass), abstract provider base class, provider-agnostic error taxonomy with SDK exception mapping stubs, rate limiter with configurable semaphore, JSONL-based result collector, atomic checkpoint save/load with schema versioning, progress tracking abstraction (CLI print + SSE event generation), and token-expiry-aware credential wrapper interface.

**Addresses features:** CLI auth validation, graceful error handling, checkpoint/resume foundation, progress indication framework, cross-platform path handling (pathlib.Path throughout)

**Avoids pitfalls:** Auth token expiry mid-scan (credential TTL wrapper), broad exception masking (error taxonomy), checkpoint corruption (atomic writes + schema versioning), signal handler state loss (threading.Event shutdown pattern)

**Research flag:** Standard patterns — well-documented Python infrastructure; no phase research needed.

---

### Phase 2: AWS Provider + End-to-End Pipeline

**Rationale:** AWS has the simplest rate limiting model (per-account per-region, not tenant-level) and the most straightforward auth chain (credential file / SSO token cache). Building the first end-to-end pipeline — CLI invocation through AWS discovery through JSONL collection through token calculation through CSV/XLS output — validates the entire architecture before Azure's more complex rate limiting or GCP's quota model is introduced.

**Delivers:** Fully working AWS discovery with multi-account support via Organizations or explicit account list, concurrent account workers using Phase 1 rate limiter, JSONL result streaming, end-to-end token calculation and XLS output, and the first integration test proving the full pipeline.

**Addresses features:** AWS multi-account discovery, AWS token calculation, CSV/XLS output with detail + summary sheets, proof manifest, IP-space-aware deduplication, resource categorization

**Avoids pitfalls:** Memory exhaustion (JSONL streaming committed from the start), nested thread pools (single-level ThreadPoolExecutor), per-region API fan-out (sequential region iteration within account workers)

**Uses:** boto3, tenacity, asyncio.Semaphore, openpyxl, moto for tests

**Research flag:** Standard patterns — AWS SDK and concurrent discovery patterns are well-documented. No phase research needed.

---

### Phase 3: Azure Provider

**Rationale:** Azure is the most complex provider: tenant-level rate limits, the longest scan times (many subscriptions), the highest chance of mid-scan token expiry, and the most nuanced credential chain (InteractiveBrowserCredential must be warmed on the main thread). Tackling it as a discrete phase after the AWS pipeline is proven lets the team focus on Azure's unique challenges without simultaneously solving pipeline bugs.

**Delivers:** Azure subscription enumeration, concurrent subscription workers behind a tenant-level semaphore, resource discovery (VMs, VNets, DNS zones, subnets, NICs, load balancers), per-subscription error isolation, and checkpoint/resume for Azure scans.

**Addresses features:** Azure multi-subscription discovery, Azure rate limiting, Azure checkpoint/resume, Azure token calculation

**Avoids pitfalls:** ARM tenant-level rate limiting cascade (tenant semaphore + full jitter backoff + Retry-After header respect), Azure InteractiveBrowserCredential threading deadlock (main-thread credential warm-up), SubscriptionClient pagination (materialize to list immediately), ResourceManagementClient file descriptor leak (context managers throughout)

**Uses:** azure-identity, azure-mgmt-compute, azure-mgmt-network, azure-mgmt-dns, azure-mgmt-privatedns, azure-mgmt-resource

**Research flag:** Phase research recommended — Azure ARM throttling edge cases and subscription-scale testing are complex enough to warrant pre-implementation research during planning.

---

### Phase 4: GCP Provider

**Rationale:** GCP's multi-project discovery pattern is already partially prototyped in the existing codebase (shared compute clients injection is implemented), providing a starting point. However, GCP's quota model (all API calls billed to a single quota project regardless of target project) requires specific design decisions. Building GCP after Azure means the rate limiter and result collector are already proven at scale.

**Delivers:** GCP project enumeration (Resource Manager), multi-project concurrent discovery using `aggregatedList` endpoints (40x fewer API calls than per-region listing), per-project error isolation, quota-project awareness, and DNS zone caching across GCPDiscovery instances.

**Addresses features:** GCP multi-project discovery, GCP token calculation, GCP checkpoint/resume

**Avoids pitfalls:** GCP API quota exhaustion (`aggregatedList` instead of per-region calls, quota-project monitoring, wave-based scanning for 500+ project orgs), DNS zone listing repeated per project (module-level cache), full API response stored in details field (extract only licensing-relevant fields during discovery)

**Uses:** google-cloud-compute, google-cloud-dns, google-cloud-resource-manager, google-cloud-service-usage, google-auth

**Research flag:** Standard patterns for `aggregatedList` usage — GCP Compute API is well-documented. Quota-project mechanics may need validation during planning.

---

### Phase 5: Web Dashboard

**Rationale:** The dashboard sits entirely on top of the complete discovery pipeline. FastAPI is already the web framework for the CLI server, and the SSE progress infrastructure was designed into Phase 1's progress tracking abstraction. Phase 5 is "wire up the UI layer" — not architectural work. Building it last means the underlying discovery is already reliable and the dashboard can display real results.

**Delivers:** FastAPI app with Jinja2 templates and HTMX frontend, SSE-based real-time progress stream, results viewer with per-provider summary and resource detail, export download links, and browser auto-open on scan start.

**Addresses features:** Web dashboard, progress indication (visual), results browsing without CLI expertise

**Avoids pitfalls:** No build toolchain (HTMX + Pico CSS vendored; no npm/Node.js), no WebSocket complexity (SSE is sufficient for server-to-client progress), mobile support explicitly out of scope (desktop/laptop only)

**Uses:** FastAPI, sse-starlette, Jinja2, HTMX 2.x, Pico CSS 2.x (both vendored)

**Research flag:** Standard patterns — FastAPI + HTMX + SSE is well-documented with multiple worked examples. No phase research needed.

---

### Phase 6: Hardening, Cross-Platform, and Polish

**Rationale:** Once all three providers and the dashboard work functionally, a dedicated hardening phase addresses the "looks done but isn't" checklist: cross-platform path handling, file descriptor limits on macOS, Windows PowerShell setup scripts, output file completeness metadata, dry-run mode, and account filtering. These are individually low-risk but need systematic validation across platforms.

**Delivers:** PowerShell setup scripts (signed), Windows CI matrix, output file scan metadata headers (scanned/failed/skipped accounts), dry-run / what-if mode, account/subscription/project filtering with glob patterns, macOS file descriptor limit detection, security log sanitization (bearer token stripping), and checkpoint file permissions hardening.

**Addresses features:** Cross-platform (Windows 11, WSL, macOS), PowerShell setup scripts, dry-run mode, account filtering, estimator CSV yellow-cell format alignment

**Avoids pitfalls:** Cross-platform file paths (pathlib.Path audit), file descriptor exhaustion (ulimit detection + warning), output completeness gaps (scan metadata in report headers), credential logging leaks (exception message sanitization)

**Research flag:** Windows-specific PowerShell script signing may need targeted research. Otherwise standard patterns.

---

### Phase Ordering Rationale

The dependency chain from ARCHITECTURE.md maps cleanly to this phase sequence:

- **Phase 1 is foundational and non-negotiable as first.** Four of six critical pitfalls from PITFALLS.md must be addressed in the core framework before provider code exists. The error taxonomy, credential TTL wrapper, and checkpoint abstraction are the most impactful structural investments in the entire project.
- **Phase 2 (AWS) before Azure/GCP** because AWS has the simplest rate model, validating the full pipeline before complexity is added. The ARCHITECTURE.md build order recommendation explicitly calls out this sequence.
- **Phase 3 (Azure) before GCP** because Azure's tenant-level rate limiting is the hardest coordination problem in the project. Solving it second, with a working pipeline already proven, reduces debugging surface area.
- **Phase 5 (Dashboard) last among features** because it depends on all three providers having stable progress APIs and results. Building it early would require mocking discovery — adding work, not reducing it.
- **Phase 6 (Hardening) as dedicated final phase** because cross-platform testing and security review require a complete, stable codebase. Interleaving this work with feature development creates a moving target.

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 3 (Azure):** Azure ARM tenant-level throttling behavior at 100-500 subscription scale is well-documented but the interaction between adaptive concurrency, Retry-After headers, and concurrent subscription workers has subtleties that warrant pre-implementation spike work. Specifically: validate the tenant-level semaphore value (2-4 concurrent subscription workers is the research recommendation; confirm with ARM documentation).
- **Phase 6 (Hardening):** PowerShell script signing requirements vary by enterprise policy. Research the self-signed certificate workflow for Windows 11 and validate against `Set-ExecutionPolicy` requirements before writing setup scripts.

**Phases with standard patterns (skip research-phase):**
- **Phase 1:** Pure Python infrastructure — error taxonomy, JSONL file I/O, threading primitives, checkpoint JSON. All standard library or well-documented patterns.
- **Phase 2 (AWS):** boto3 multi-account, ThreadPoolExecutor, moto testing. All well-documented with official examples.
- **Phase 4 (GCP):** `aggregatedList` endpoints and ADC auth are documented in GCP official docs. Shared compute client pattern already prototyped in existing codebase.
- **Phase 5 (Dashboard):** FastAPI + HTMX + SSE has multiple worked examples in official docs. Zero novel patterns.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies verified via PyPI with specific version numbers. Rationale for every exclusion (pandas, Flask, aioboto3, Node.js) is documented and cross-checked against project constraints. |
| Features | HIGH | Derived from existing codebase analysis + PROJECT.md (authoritative) + competitor analysis (ServiceNow CLE, Flexera). Feature dependencies are explicit. MVP definition is clear. |
| Architecture | HIGH | Component design is directly informed by existing codebase defects (nested pools, in-memory accumulation, copy-pasted pipelines). Build order derived from data dependency graph, not opinion. |
| Pitfalls | HIGH | Six critical pitfalls all identified from codebase analysis + official cloud provider rate limit documentation + SDK issue trackers. Each has specific line references in existing code. |

**Overall confidence:** HIGH

### Gaps to Address

- **Azure ARM adaptive concurrency threshold:** The research recommends 2-4 concurrent subscription workers for large tenants, but the exact value that avoids throttling without unnecessarily serializing discovery depends on the customer's tenant size and ARM subscription quota tier. This can only be validated with a real-scale test against a large Azure tenant. Plan a dedicated Azure load test in Phase 3.

- **GCP `aggregatedList` availability per resource type:** The recommendation to use `aggregatedList` instead of per-region listing (40x API call reduction) applies to Compute Engine resources. Verify which specific resource types (instances, networks, subnetworks, addresses) support `aggregatedList` versus requiring per-zone calls before writing GCP discovery code in Phase 4.

- **Windows PowerShell script signing mechanics:** PROJECT.md requires signed `.ps1` scripts. The exact signing workflow (self-signed certificate creation, code signing, execution policy requirements) has not been fully researched. Validate before writing setup scripts in Phase 6.

- **Token calculation edge cases (IPv6, overlapping CIDRs):** The core DDI/IP/Asset token ratios are well-understood, but edge cases — IPv6 subnets, VPC peering with overlapping RFC1918 ranges, Azure Hybrid Benefit implications — are noted as unvalidated. These should be verified against Infoblox's official sizing methodology during Phase 2 implementation.

---

## Sources

### Primary (HIGH confidence)
- **Existing codebase** (`main.py`, `shared/`, `aws_discovery/`, `azure_discovery/`, `gcp_discovery/`) — authoritative source for current behavior, defects, and patterns
- **PROJECT.md** — authoritative constraints document; defines tool scope, platform requirements, and feature set
- [PyPI verified versions](https://pypi.org) — all stack versions confirmed for FastAPI 0.129.0, Pydantic 2.13.1, boto3 1.42.x, azure-identity 1.25.2, azure-mgmt-compute 37.2.0, azure-mgmt-network 30.2.0, google-cloud-compute 1.40.0, uv 0.6+, Ruff 0.15.2, pytest 9.0.2
- [Azure ARM throttling documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling) — tenant-level rate limits, throttling headers
- [GCP Compute Engine rate quotas](https://cloud.google.com/compute/api-quota) — per-project quota, quota project scoping
- [Python devguide: Version status](https://devguide.python.org/versions/) — Python 3.12/3.13 support timelines

### Secondary (MEDIUM confidence)
- [HTMX GitHub releases](https://github.com/bigskysoftware/htmx/releases) — version 2.0.8 confirmed; SSE extension behavior verified
- [ServiceNow ITOM Cloud License Estimator](https://store.servicenow.com/store/app/c44eef2a1b646a50a85b16db234bcb38) — competitor feature comparison
- [Flexera Cloud License Management](https://www.flexera.com/products/flexera-one/cloud-license-management) — competitor feature comparison
- [boto3 SSO token expiry (GitHub #4119)](https://github.com/boto/boto3/issues/4119) — SSO non-refresh behavior confirmed
- [Azure InteractiveBrowserCredential threading issues (GitHub #23721)](https://github.com/Azure/azure-sdk-for-python/issues/23721) — main-thread requirement confirmed
- [Python signal handler + ThreadPoolExecutor deadlock (CPython #121649)](https://github.com/python/cpython/issues/121649) — SIGINT handling behavior
- `.planning/codebase/CONCERNS.md` — documented tech debt and known bugs in existing codebase

### Tertiary (MEDIUM-LOW confidence)
- [Strapi Blog: FastAPI vs Flask 2025](https://strapi.io/blog/fastapi-vs-flask-python-framework-comparison) — adoption data (38% FastAPI adoption cited)
- [JetBrains PyCharm Blog: Django vs Flask vs FastAPI](https://blog.jetbrains.com/pycharm/2025/02/django-flask-fastapi/) — framework comparison
- [Infoblox Universal DDI Licensing](https://docs.infoblox.com/space/BloxOneDDI/846954761/Universal+DDI+Licensing) — token ratios (DDI/25, IPs/13, Assets/3)

---

*Research completed: 2026-02-23*
*Ready for roadmap: yes*
