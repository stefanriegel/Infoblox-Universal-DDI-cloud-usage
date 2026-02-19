# Project Research Summary

**Project:** Infoblox Universal DDI Cloud Usage — GCP Multi-Project Discovery (v1.1)
**Domain:** GCP multi-project credential hardening and concurrent resource enumeration
**Researched:** 2026-02-19
**Confidence:** HIGH

---

## Executive Summary

This milestone applies to an existing tool that already handles Azure multi-subscription discovery successfully. The GCP module currently has a critical broken-credentials bug: `google.auth.default()` returns credentials that may be expired, `check_gcp_credentials()` validates the wrong auth path (gcloud CLI, not ADC tokens), and bare `except Exception` blocks swallow all failures, causing every GCP run to end with "Discovery completed successfully!" while returning 0 resources. The fix is not complex — it mirrors the Azure pattern exactly — but the bug must be resolved before any multi-project work can proceed, because project enumeration, client lifecycle management, retry, and checkpoint all depend on working credentials.

The recommended approach is to replicate the Azure v1 architecture for GCP: a credential singleton warmed on the main thread before workers spawn, project enumeration via `resourcemanager_v3.ProjectsClient.search_projects()`, an outer `ThreadPoolExecutor` over projects, and per-project DNS client lifecycle with shared compute clients (Compute API clients are project-agnostic per-request, unlike the DNS client which bakes project into the constructor). The key architectural difference from Azure is that GCP Compute clients accept `project=` on each API call rather than at construction — meaning shared compute client instances work correctly across all projects — while only `dns.Client` requires per-project instantiation.

The primary risk is the GCP Compute Engine API returning 403 with reason `rateLimitExceeded` (not HTTP 429) for quota exhaustion, which any retry logic designed for Azure's 429-with-Retry-After pattern will silently miss. Secondary risks are `accessNotConfigured` (Compute API disabled in a project) being misclassified as permission denied, org-level enumeration silently returning 0 projects when IAM is insufficient, and socket exhaustion from unclosed gRPC transport connections. All of these have clear, well-documented mitigations.

---

## Key Findings

### Recommended Stack

The existing GCP SDK dependency set requires three changes: bump `google-auth` to `>=2.23.0` (thread-safety improvements for concurrent credential refresh introduced in 2.23), add `google-cloud-resource-manager>=1.16.0` (v3 API for project enumeration via `resourcemanager_v3.ProjectsClient`), and make `google-api-core>=2.15.0` explicit (previously transitively installed; explicit declaration ensures `Retry.on_error` is available). `google-cloud-compute` requires no version change, and `google-cloud-dns` must remain pinned at `==0.35.1` — the legacy `dns.Client` API is incompatible with the `google-cloud-dns >= 1.0.0` GAPIC interface (`dns_v1.ManagedZonesClient`).

The retry pattern differs fundamentally from Azure: GCP has no `RetryPolicy` class to subclass. The correct approach is `google.api_core.retry.Retry` configured with an `on_error` callback for visibility, applied at each API call site rather than at the client constructor (`retry=` is not universally supported at construction time across GCP client types). A `Retry` instance is stateless and safe to share as a module-level singleton.

**Core technologies:**
- `google-auth>=2.23.0`: Credential management — bump required for thread-safe concurrent refresh
- `google-cloud-resource-manager>=1.16.0`: Project enumeration — new addition using v3 API; `search_projects()` is recommended over `list_projects()` with recursive folder traversal for most orgs
- `google-api-core>=2.15.0`: Retry with `on_error` callback — make explicit rather than relying on transitive installation
- `google-cloud-compute>=1.12.0`: Compute resource discovery — no change; compute clients are project-agnostic (pass `project=` per API call, not at construction)
- `google-cloud-dns==0.35.1`: DNS zone/record discovery — keep pinned; legacy `dns.Client` API is incompatible with v1.0.0+ GAPIC interface

### Expected Features

**Must have (table stakes — v1.1 milestone):**
- Credential chain: SA key → ADC, with `credentials.refresh()` validation before workers spawn — this is the root bug fix
- Fail-fast on `invalid_grant` / `DefaultCredentialsError` with actionable exit messages — eliminates silent 0-resource "success"
- Credential singleton with threading lock (double-checked locking, same pattern as Azure's `get_azure_credential()`) — prevents concurrent first-refresh race
- Project enumeration via `resourcemanager_v3.ProjectsClient.search_projects()` with `state:ACTIVE` filter — replaces single-project `GOOGLE_CLOUD_PROJECT` env var path
- Per-project `dns.Client` lifecycle — `dns.Client(project=project_id)` bakes project at construction; must be instantiated inside the per-project worker, not at class init
- Visible retry for GCP 403 `rateLimitExceeded` — `google.api_core.retry.Retry` with predicate covering both `ResourceExhausted` and `Forbidden/rateLimitExceeded`
- Checkpoint/resume per project — JSON file with atomic write, saved after each project completes (not per-region), mirrors Azure pattern exactly
- Scan summary: `[N/total] project-id` progress output plus failed-project log to `output/gcp_failed_projects_{timestamp}.txt`
- Credential path logging: `[Auth] Using service account: ...` or `[Auth] Using Application Default Credentials` at startup
- `accessNotConfigured` error classification — distinguish "Compute API not enabled in this project" (expected, skip gracefully) from `PERMISSION_DENIED` (IAM issue, log warning)

**Should have (v1.x, add after core is working and tested):**
- Org/folder-aware enumeration — recursive `FoldersClient.list_folders()` traversal when `GOOGLE_CLOUD_ORG_ID` is set; `search_projects()` may miss projects the credential lacks direct access to in deep folder hierarchies
- Single-project backward compatibility via `--project` flag or `GOOGLE_CLOUD_PROJECT` env var — bypasses enumeration entirely, preserves existing usage
- Large-org warning when project count > 50 and worker count > 2 — quota exhaustion risk advisory
- Project filter: `--include-projects` / `--exclude-projects` glob matching for SE workflows excluding staging/test projects

**Defer (v2+):**
- GCP Cloud Asset Inventory integration — enumerate resources across all projects in a single API call; high complexity, different data model, coverage gaps for some resource types
- Async rewrite — wholesale SDK change, premature optimization until threading throughput proves insufficient

### Architecture Approach

The v1.1 architecture adds a project enumeration tier between the credential layer and the per-project worker pool. Three tiers: (1) credential singleton warmed on main thread via `get_gcp_credential()`, (2) project list from `get_all_gcp_project_ids()` using `resourcemanager_v3.ProjectsClient`, (3) outer `ThreadPoolExecutor(project_workers=4)` dispatching `discover_project(project_id)`, which runs the existing inner regional executor (`max_workers=8`). GCP Compute clients (`InstancesClient`, `SubnetworksClient`, `NetworksClient`, `AddressesClient`, `ZonesClient`) can be shared as class-level singletons across all projects because the Compute API accepts `project=` per API call — only `dns.Client` requires per-project instantiation. The multi-project resource accumulator lives in `discover.py`, not in `GCPDiscovery`; `self._discovered_resources` is bypassed in multi-project mode to prevent cross-project resource contamination.

**Major components:**
1. `get_gcp_credential()` in `config.py` — singleton with threading lock, `credentials.refresh()` warm-up, fail-fast on `RefreshError` / `DefaultCredentialsError`
2. `get_all_gcp_project_ids()` in `config.py` — `search_projects()` with `state:ACTIVE` filter, explicit 0-project warning, org-level IAM error detection
3. `discover_project(project_id, max_workers)` in `gcp_discovery.py` — creates per-project `dns.Client`, passes `project_id` to all compute API calls, returns resources tagged with `project_id`, does not write to `self._discovered_resources`
4. Project loop with checkpoint in `discover.py` `main()` — outer `ThreadPoolExecutor`, `save_checkpoint()` after each future completes, resume logic, SIGINT signal handler
5. `_GCP_RETRY` module-level `google.api_core.retry.Retry` in `gcp_discovery.py` — stateless singleton with `on_error` logging callback, applied at each API call site

### Critical Pitfalls

1. **`google.auth.default()` returns expired credentials silently** — Call `credentials.refresh(google.auth.transport.requests.Request())` immediately after obtaining credentials on the main thread. Catch `RefreshError` and exit with `SystemExit`. Remove the existing `check_gcp_credentials()` subprocess-based gcloud check entirely — it validates the wrong auth path and provides false assurance.

2. **Per-project gRPC client proliferation causes socket exhaustion** — GCP Compute clients are thread-safe and project-agnostic; reuse them as class-level singletons and pass `project=project_id` per API call. Only `dns.Client` requires per-project instantiation. Call `.transport.close()` on DNS clients (and compute clients if per-project) after each project completes to release gRPC channels.

3. **Project enumeration silently returns 0 results when org-level IAM is insufficient** — `search_projects()` returns an empty result without error when the caller lacks `resourcemanager.projects.get` at org level. Always log an explicit warning when 0 projects are returned. Filter to `state:ACTIVE` to exclude projects in the deletion grace period that return 403 on all resource APIs.

4. **GCP 403 `rateLimitExceeded` is not HTTP 429 — Azure retry logic silently misses it** — Configure `google.api_core.retry.Retry` with a predicate that inspects the error reason field, handling both `ResourceExhausted` (some APIs) and `PermissionDenied` with reason `rateLimitExceeded` (Compute Engine). Do not port Azure's 429/Retry-After logic directly.

5. **`accessNotConfigured` (Compute API disabled) treated as permission denied** — Inspect `e.reason` or `e.errors[0]['reason']` on `PermissionDenied` exceptions. `accessNotConfigured` means the project legitimately does not use Compute Engine — skip gracefully with INFO-level logging, not a WARNING. Track the count of API-not-enabled projects separately in the scan summary.

---

## Implications for Roadmap

Based on combined research, suggested phase structure:

### Phase 1: Credential Chain and Fail-Fast

**Rationale:** The existing credential bug blocks all GCP discovery and must be fixed before any other work can be tested. Every subsequent feature — project enumeration, client lifecycle, retry, checkpoint — depends on working credentials. This phase changes only `config.py` and can be tested immediately against the existing single-project path.

**Delivers:** A working GCP credential flow that fails fast on expired/invalid credentials, logs the credential type at startup, and validates via actual token refresh rather than `gcloud auth list`. The existing single-project discovery path works correctly after this phase.

**Addresses:**
- Credential chain: SA key → ADC, with `credentials.refresh()` validation (P1)
- Fail-fast on `invalid_grant` with actionable `SystemExit` message (P1)
- Credential singleton with `threading.Lock` double-checked locking (P1)
- Credential path logging `[Auth] Using ...` (P1)
- Remove `check_gcp_credentials()` subprocess check (required)
- Update hardcoded region fallback list to 40+ GCP regions (required before multi-project to avoid missing newer regions)

**Avoids:** Pitfall 1 (invalid_grant silent failure), Pitfall 4 (bare `except Exception` swallowing auth errors)

**Research flag:** Standard patterns — direct port of the Azure `get_azure_credential()` singleton. Official google-auth docs confirm `credentials.refresh()` behavior. No additional research needed.

---

### Phase 2: Project Enumeration Foundation

**Rationale:** With working credentials, enumeration can be added as an isolated `config.py` change. Enumeration must precede the project loop, client lifecycle refactor, retry, and checkpoint — all downstream features need a stable project list. Completing this as a separate phase allows enumeration to be tested standalone (log the project list, no other changes to discovery behavior).

**Delivers:** `get_all_gcp_project_ids()` that returns all ACTIVE projects visible to the credential, with explicit 0-project warnings, `accessNotConfigured` error classification, and `--project` single-project backward compatibility path.

**Addresses:**
- Project enumeration via `search_projects()` with `state:ACTIVE` filter (P1)
- 0-project warning with IAM guidance (P1)
- `accessNotConfigured` vs `PERMISSION_DENIED` error classification (P1)
- Single-project backward compat via `GOOGLE_CLOUD_PROJECT` env var or `--project` flag (P2)

**Avoids:** Pitfall 3 (silent 0-project enumeration), Pitfall 5 (`accessNotConfigured` misclassified as permission denied)

**Research flag:** Standard patterns — `search_projects()` with `state:ACTIVE` is documented with official sample code. 0-project IAM warning is straightforward. No additional research needed.

---

### Phase 3: Concurrent Multi-Project Execution

**Rationale:** With enumeration working, the outer project loop and the `gcp_discovery.py` refactor can be added together. This is the largest single change — all `_discover_*` methods must accept `project_id` as a parameter, `dns.Client` must move from class init to per-project instantiation, and the outer `ThreadPoolExecutor` must be added to `discover.py`. These changes are tightly coupled and must ship as a unit.

**Delivers:** Full multi-project discovery — outer project worker pool (`project_workers=4`), per-project `dns.Client` lifecycle, shared compute client reuse with per-request `project=`, `project_id` added to each resource's `details` dict, and `[N/total] project-id` progress output.

**Uses:**
- `google-cloud-resource-manager>=1.16.0` for project enumeration
- `google-auth>=2.23.0` for thread-safe concurrent credential use
- Nested `ThreadPoolExecutor` (outer: `project_workers=4`, inner: `region_workers=8`)

**Implements:** Client tier, `discover_project()` method, outer project loop in `discover.py`

**Avoids:** Pitfall 2 (gRPC client proliferation/socket exhaustion), Anti-Pattern: reusing `dns.Client` across projects, Anti-Pattern: cross-project resource contamination via shared `_discovered_resources`, Anti-Pattern: per-project region enumeration (call `get_all_gcp_regions()` once, pass to all workers)

**Research flag:** Needs validation — the Shared VPC subnet deduplication strategy (Pitfall 6) and the `resource_id` collision risk in `ResourceCounter` when two projects have identically named resources both need concrete decisions during planning. See Gaps section.

---

### Phase 4: Retry and Observability

**Rationale:** Retry and observability are only meaningful once the project loop is running — retry wraps per-project API calls, and per-project progress logging requires a multi-project context. These are lower-risk additive changes.

**Delivers:** `_GCP_RETRY` module-level `google.api_core.retry.Retry` with `on_error` logging callback handling both `ResourceExhausted` and `rateLimitExceeded`; scan summary with failed-project log exported to `output/gcp_failed_projects_{timestamp}.txt`; large-org warning at >50 projects; `--project-workers` and `--warn-project-threshold` CLI flags.

**Uses:** `google-api-core>=2.15.0` (`Retry.on_error` parameter)

**Avoids:** Pitfall 9 (per-project Compute API rate limits hit without retry or visibility)

**Research flag:** One gap to resolve — the exact Python exception field path for `rateLimitExceeded` in `google.api_core.exceptions.PermissionDenied` (is it `e.reason`, `e.errors[0].get('reason')`, or string inspection of `str(e)`?) needs verification against a live API response or exception class source before implementation.

---

### Phase 5: Checkpoint and Resume

**Rationale:** Checkpoint wraps the already-working project loop and is the last addition. It requires a stable project list and stable per-project results to checkpoint against. Adding checkpoint before the project loop is stable would produce checkpoint files with unknown consistency.

**Delivers:** JSON checkpoint file with `completed_project_ids`, `total_project_ids`, and accumulated resources. Atomic write via temp file rename. Per-project granularity (save after full project completes, not per-region — per-region would create inconsistent partial state on crash). `--no-checkpoint`, `--resume`, `--checkpoint-file`, `--checkpoint-ttl-hours` CLI flags. SIGINT handler that saves checkpoint before exit. Resume skips already-completed projects without re-enumerating the full project list.

**Avoids:** Pitfall 10 (per-region checkpoint granularity creating inconsistent state on crash), security concern of checkpoint file in world-readable `./output/` location (write to `~/.cache/` or document the risk)

**Research flag:** Standard patterns — direct port of existing Azure `discover.py` checkpoint implementation. Schema is defined in ARCHITECTURE.md. No additional research needed.

---

### Phase Ordering Rationale

- Phase 1 is strictly prerequisite for everything. The credential bug produces silent failures that mask all other work.
- Phase 2 (enumeration) must precede Phase 3 (project loop) because the loop needs the project list. These cannot be developed in parallel without integration risk — enumeration is a `config.py` change; the project loop spans `discover.py` and `gcp_discovery.py`.
- Phase 3 is the largest change (all `_discover_*` method signatures change). Completing Phases 1–2 first means each phase can be tested independently using the single-project path before the multi-project loop is introduced.
- Phase 4 (retry) wraps per-project API calls — adding it before Phase 3 would have nothing meaningful to wrap.
- Phase 5 (checkpoint) wraps the project loop — adding it before Phase 3 is stable would checkpoint an unstable state.

### Research Flags

Phases needing deeper research or concrete design decisions during planning:

- **Phase 3** (`gcp_discovery.py` refactor): The Shared VPC subnet double-counting problem (Pitfall 6) needs an explicit deduplication strategy — by subnet resource URL at collection time vs. in the `ResourceCounter` layer. The `resource_id` collision risk when two projects have identically named resources in the same region also needs verification: does `ResourceCounter` deduplicate by content hash or by `resource_id` string? If by string, adding `project_id` to the `resource_id` format is required.
- **Phase 4** (retry): The exact Python field path for `rateLimitExceeded` reason in `google.api_core.exceptions.PermissionDenied` needs verification against a live GCP Compute API response or the exception class source before the retry predicate can be written correctly.

Phases with standard, well-documented patterns (no additional research needed):

- **Phase 1**: The `credentials.refresh()` pattern is official google-auth documentation. The singleton/`threading.Lock` pattern is a direct port of the existing Azure implementation.
- **Phase 2**: `search_projects()` with `state:ACTIVE` filter has official sample code. 0-project warning is straightforward.
- **Phase 5**: Direct port of existing Azure `discover.py` checkpoint implementation. Schema is defined. No unknowns.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Official PyPI versions confirmed; google-auth-library-python GitHub issues cited with maintainer confirmation of thread-safety behavior; all version constraints verified against official release notes |
| Features | HIGH | Based on official GCP API documentation plus first-party codebase analysis identifying the specific broken code paths in `config.py`, `discover.py`, and `gcp_discovery.py` |
| Architecture | HIGH | GCP Compute API project-per-request pattern confirmed against official documentation samples; `dns.Client` constructor behavior confirmed against official API reference; nested `ThreadPoolExecutor` pattern is the existing Azure pattern applied to GCP |
| Pitfalls | HIGH | All critical pitfalls verified against official GCP documentation, googleapis GitHub issues, and specific line numbers in the existing codebase; no inferred pitfalls — all are documented failures |

**Overall confidence:** HIGH

### Gaps to Address

- **Shared VPC deduplication strategy** (Pitfall 6): Research confirms subnets appear only in the host project, but the specific deduplication logic for `ResourceCounter` is not specified. During Phase 3 planning: decide whether to deduplicate by subnet resource URL at collection time or in the counter layer. For Infoblox DDI sizing, a subnet should be counted once where it is defined.

- **`resource_id` collision in multi-project mode**: ARCHITECTURE.md notes that `_format_resource()` generates `resource_id` as `"{region}:{resource_type}:{name}"`. Two projects can have identically named resources in the same region. ARCHITECTURE.md suggests dedup may be by content hash in `ResourceCounter`, not by `resource_id` string, but states "verify before shipping." This must be confirmed before Phase 3 completes — if `resource_id` uniqueness is assumed anywhere in the output or counter layer, adding `project_id` to the format is required.

- **`rateLimitExceeded` exception field path**: Which Python exception field contains the `rateLimitExceeded` reason string in `google.api_core.exceptions.PermissionDenied`? STACK.md suggests inspecting `e.reason` or `e.errors[0].get('reason')` but notes no confirmed live API response test. Validate during Phase 4 implementation.

- **`google-cloud-dns` version compatibility**: PITFALLS.md flags that `dns.Client` (legacy API) is incompatible with `google-cloud-dns >= 1.0.0`. The version is currently pinned at `==0.35.1`. Before any dependency update in this repo, verify that no other dependency transitively pulls in a newer version that would break the legacy API. If the pin creates a conflict, migrate to `dns_v1.ManagedZonesClient` at that point.

- **DNS client cleanup method**: ARCHITECTURE.md states `dns.Client` does not expose `close()` and relies on garbage collection for cleanup. STACK.md states `.transport.close()` is the correct approach for gRPC-based clients. Before Phase 3 implementation, verify whether `google.cloud.dns.Client` at version 0.35.1 exposes `.transport.close()` or another explicit cleanup method.

---

## Sources

### Primary (HIGH confidence)

- google-cloud-resource-manager PyPI (v1.16.0 current as of 2026-01-15) — project enumeration package version
- `resourcemanager_v3.ProjectsClient` official Python client docs — `search_projects()` and `list_projects()` signatures confirmed
- Listing all GCP projects and folders — official Google Cloud documentation on hierarchy traversal
- google-auth User Guide — `google.auth.default()` priority chain, service account usage
- `google.oauth2.service_account.Credentials` reference — `from_service_account_file()`, `refresh()`
- `google.api_core.retry` reference — `Retry` class, `on_error` callback, `if_transient_error` predicate
- GCP Compute Engine rate quotas — per-project quota; 403 `rateLimitExceeded` behavior confirmed
- Application Default Credentials — credential resolution order
- `google-auth-library-python` issue #246 — concurrent `RefreshError: Internal Failure` root cause confirmed by maintainer
- GCP Compute instances list-all sample — confirms `project` is in the request object, not the client constructor
- `google.cloud.dns.Client` constructor reference — confirms `project` is baked into the constructor
- Resource Manager IAM roles — `roles/browser` minimum for `resourcemanager.projects.list`
- GCP Shared VPC documentation — subnet ownership by host project only
- `google.api_core.exceptions` reference — `ResourceExhausted` maps to 429; `PermissionDenied` maps to 403
- First-party codebase analysis: `gcp_discovery/config.py`, `gcp_discovery/discover.py`, `gcp_discovery/gcp_discovery.py`

### Secondary (MEDIUM confidence)

- google-api-python-client thread safety docs — covers older discovery-based clients; Cloud client library threading model inferred from the same underlying pattern
- `google-auth-library-python` issue #690 — additional concurrent refresh race confirmation
- jdhao.github.io "Retry for Google Cloud Client" (2024-10-08) — call-level `retry=` pattern verified, matches official API
- cloudquery.io blog on cross-project service accounts — single SA can access multiple projects via org-level IAM grants

### Tertiary (LOW confidence)

- None — all implementation-relevant findings are backed by HIGH or MEDIUM sources

---

*Research completed: 2026-02-19*
*Ready for roadmap: yes*
