# Feature Research

**Domain:** GCP multi-project discovery — credential hardening, project enumeration, and reliability at scale
**Researched:** 2026-02-19
**Confidence:** HIGH (official GCP docs + codebase analysis + Azure blueprint comparison)

---

## Context

This is a hardening milestone applied to an existing single-project GCP discovery module. The Azure
v1 milestone delivered proven patterns (credential singleton, per-subscription lifecycle,
checkpoint/resume, visible retry, observability). This research defines what those patterns mean for
GCP — which features map directly, which differ due to GCP's distinct quota model, and which are
anti-features that would break the Azure blueprint.

**Root causes already confirmed (from codebase analysis):**

1. `get_gcp_credential()` calls `google.auth.default()` which returns expired/invalid tokens
   (`invalid_grant: Bad Request`). No fail-fast.
2. `check_gcp_credentials()` runs `gcloud auth list` — validates CLI auth, not actual API tokens.
3. No fail-fast: 70+ error lines per run, then reports "Discovery completed successfully!" with 0
   resources.
4. Single project only (from `GOOGLE_CLOUD_PROJECT` env or `gcloud config get-value project`).
   No enumeration of all projects in an org.
5. No checkpoint/resume, no visible retry, no observability.

**Key GCP vs Azure differences that affect feature design:**

| Concern | Azure | GCP |
|---------|-------|-----|
| Scope unit | Subscription | Project |
| Org enumeration | ARM subscription list API | Resource Manager v3 `list_projects()` / `search_projects()` |
| Credential model | MSAL-caching credential objects | Single `google.auth.Credentials` object, refreshed in place |
| Quotas | ARM: per-subscription, per-principal token bucket (250 req/bucket) | Compute: per-project rate quota, 403 `rateLimitExceeded` not 429 |
| Rate limit error | HTTP 429 with `Retry-After` header | HTTP 403 with reason `rateLimitExceeded` (no standard Retry-After) |
| SDK retry | `RetryPolicy` kwarg on management clients | `google.api_core.retry.Retry` per-call or per-method |
| Folder hierarchy | Flat subscription list | Org → Folders (recursive) → Projects (must traverse) |

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist for a multi-project scanning tool. Missing these = tool is incomplete
or unreliable.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Credential chain: SA key → ADC → browser** | Without working credentials there is nothing. Current `google.auth.default()` returns expired tokens silently. | LOW | Replace `get_gcp_credential()` with explicit chain: check `GOOGLE_APPLICATION_CREDENTIALS` (SA JSON key) first, then ADC from `gcloud auth application-default login`, then interactive browser. Validate each path by requesting an actual token, not by running `gcloud auth list`. |
| **Fail-fast on invalid_grant** | Current tool runs for minutes generating 70+ error lines before declaring success with 0 resources. Users lose trust. | LOW | Catch `google.auth.exceptions.RefreshError` with message containing `invalid_grant` and exit immediately with a clear message. This is the primary fix for the broken credential bug. |
| **Credential validation before any API calls** | Mirrors Azure: warm the credential on the main thread, fail early, don't spawn workers with an untested credential. | LOW | Call `credentials.refresh(Request())` and check `credentials.valid` before entering `ThreadPoolExecutor`. Log the credential type (SA key path, ADC, or interactive). |
| **Project enumeration: list all accessible projects** | A single-project tool requires users to re-run per project. Multi-project is the stated milestone goal. | MEDIUM | Use `google.cloud.resourcemanager_v3.ProjectsClient.search_projects()` with empty query to list all projects accessible to the credential — works without knowing the org ID. For org-scoped credentials, use `list_projects(parent="organizations/{org_id}")` with recursive folder traversal. Filter to `state == ACTIVE` only (exclude `DELETE_REQUESTED`, `DELETE_IN_PROGRESS`). |
| **Checkpoint/resume per project** | Crash recovery. Without this, an org with 200 projects restarts from zero after any failure. Users are SEs in customer environments — interruptions happen. | MEDIUM | Mirror Azure pattern: JSON checkpoint file updated after each project completes. On restart, prompt user to resume or start fresh. `--no-checkpoint`, `--resume`, `--checkpoint-file`, `--checkpoint-ttl-hours` flags. Atomic write (write to `.tmp`, rename). |
| **Per-project client lifecycle (socket bounding)** | Without closing GCP SDK clients after each project, concurrent workers accumulate open connections. 50+ projects × multiple clients = socket exhaustion. | MEDIUM | Instantiate `compute_v1.InstancesClient`, `SubnetworksClient`, `AddressesClient`, `ZonesClient`, `NetworksClient`, and `dns.Client` inside the per-project worker function, not globally. Close them when the function exits (use context managers or explicit `.transport.close()` calls). |
| **Visible retry for GCP 403 rateLimitExceeded** | GCP Compute API returns 403 with reason `rateLimitExceeded` (not 429). Silently swallowed exceptions make retries invisible. Users need to see "retrying project X after quota error." | MEDIUM | Configure `google.api_core.retry.Retry` with predicate catching `google.api_core.exceptions.ResourceExhausted` and `google.api_core.exceptions.ServiceUnavailable`. Log each retry attempt with the project ID. Default: 3 attempts, exponential backoff (0.5s → 2s → 8s). |
| **Scan summary: projects scanned / failed** | Azure shows `[3/10] project-id` as each project completes. GCP must mirror this. Users need to know which projects failed and why. | LOW | Print `[N/total] project-id` per completed project. Collect failures in an errors list. Print failed projects after scan with their error messages. Export to `output/gcp_failed_projects_{timestamp}.txt`. |

### Differentiators (Improvements Beyond the Minimum)

Features that make the tool meaningfully better, but are not required to fix the core reliability
problems.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Org/folder-aware enumeration** | `search_projects()` works without org ID but may miss projects nested deep in folder hierarchies if the credential lacks org-level IAM. `list_projects()` with recursive folder traversal guarantees completeness for org-scoped credentials. | MEDIUM | If `GOOGLE_CLOUD_ORG_ID` env var is set, traverse org → folders (recursive via `FoldersClient.list_folders()`) → projects. If not set, fall back to `search_projects()`. Warn user if org ID is absent: "Scanning accessible projects only. Set GOOGLE_CLOUD_ORG_ID for complete org coverage." |
| **Single-project compatibility (`--project`)** | Backward compatibility: users who currently set `GOOGLE_CLOUD_PROJECT` must not be broken by multi-project changes. | LOW | If `GOOGLE_CLOUD_PROJECT` env var is set OR `--project` flag passed, skip enumeration and scan only that project. Mirrors Azure's `AZURE_SUBSCRIPTION_ID` single-subscription path. |
| **Large-org warning** | Azure warns at 200+ subscriptions with high worker counts. GCP should warn for similar risk of quota exhaustion. | LOW | If project count > 50 and `--project-workers` > 2, print warning: "N projects detected with --project-workers M. This may trigger Compute API rate limiting (403 rateLimitExceeded). Consider reducing to --project-workers 2." |
| **Project filter: include/exclude patterns** | SEs often want to exclude staging/dev projects or include only specific prefixes. | LOW | `--include-projects "prod-*,infra-*"` and `--exclude-projects "test-*,sandbox-*"` flags. Simple glob matching against project ID. Default: include all active projects. |
| **Credential path logging** | Azure logs which credential type was selected at startup (`[Auth] Using ClientSecretCredential`). GCP should mirror this: users need to diagnose auth issues without enabling DEBUG logging. | LOW | Print `[Auth] Using service account: path/to/key.json` or `[Auth] Using ADC (gcloud application-default)` or `[Auth] Using interactive browser`. |
| **Configurable checkpoint TTL** | Mirrors Azure's `--checkpoint-ttl-hours`. Large orgs may take hours to scan; 48h default may expire mid-scan if restarted the next day. | LOW | `--checkpoint-ttl-hours` flag, default 48. `0` = never expire. Already present in Azure implementation — carry through to GCP. |

### Anti-Features (Do Not Build These)

Features that seem like improvements but are wrong for this milestone or would break the design.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Per-project credential objects** | Creating separate credentials per project "for isolation" defeats the singleton pattern. GCP credentials are refreshed in-place — one `Credentials` object can access any project the SA has IAM for. Multiple credential objects multiply token refresh calls. | Share one `google.auth.Credentials` singleton across all project workers. |
| **`gcloud auth list` as credential validation** | Current broken behavior. CLI auth and API token auth are distinct. A user can have an active `gcloud` account but an expired ADC token — `gcloud auth list` passes, API calls fail with `invalid_grant`. | Call `credentials.refresh(Request())` and check `credentials.valid` / `credentials.token` directly. |
| **Bare `except Exception` in credential chain** | Current `config.py` wraps `_init_gcp_clients()` in `except Exception as e: raise Exception(...)`. This swallows SDK bugs, credential type information, and prevents proper `invalid_grant` detection. | Catch specific exception types: `google.auth.exceptions.DefaultCredentialsError`, `google.auth.exceptions.RefreshError`, `google.auth.exceptions.TransportError`. Let unknown exceptions propagate. |
| **Global client objects (current pattern)** | Current `GCPDiscovery.__init__` creates clients in `_init_gcp_clients()` and stores them as `self.compute_client`, `self.zones_client`, etc. In multi-project mode, these become per-project but still live for the object lifetime. Across 50+ concurrent projects, this exhausts sockets. | Create and close clients inside the per-project worker function, not at class construction time. |
| **Attempting to use `gcloud` CLI for project enumeration** | `subprocess.run(["gcloud", "projects", "list"])` has the same problems as `gcloud auth list` — only CLI-authenticated projects, slow, subprocess overhead, fails in WSL without gcloud installed. | Use `google.cloud.resourcemanager_v3.ProjectsClient` with the already-validated API credentials. |
| **Treating GCP 403 rateLimitExceeded as Azure 429** | GCP Compute API does not send an HTTP 429. It sends 403 with JSON body `{reason: "rateLimitExceeded"}`. Retry logic that only handles 429 will let quota errors pass through silently. | Configure `google.api_core.retry.Retry` with a predicate that handles both `google.api_core.exceptions.ResourceExhausted` (429 from some APIs) and `google.api_core.exceptions.Forbidden` with `reason=rateLimitExceeded`. |
| **Async rewrite** | Same anti-pattern as Azure. Would require replacing all sync Google Cloud clients with async equivalents, rewriting `ThreadPoolExecutor` patterns. Out of scope. | Use `threading.Lock` + per-project client lifecycle with existing sync SDK. Threading is the correct model here. |
| **New GCP resource types** | Out of scope per PROJECT.md. Existing set (VMs, VPCs, subnets, reserved IPs, Cloud DNS zones/records) is sufficient for DDI licensing. | Separate milestone. |

---

## Feature Dependencies

```
[Credential chain: SA key → ADC → browser]
    └──required-by──> [Fail-fast on invalid_grant]
    └──required-by──> [Credential validation before API calls]
    └──required-by──> [Project enumeration]
    └──required-by──> [Per-project client lifecycle]
    └──required-by──> [Credential path logging]

[Credential validation before API calls]
    └──required-by──> [Project enumeration]
                          └──required-by──> [Checkpoint/resume per project]
                          └──required-by──> [Scan summary: projects scanned / failed]
                          └──required-by──> [Large-org warning]
                          └──enhanced-by──> [Org/folder-aware enumeration]
                          └──enhanced-by──> [Project filter: include/exclude patterns]

[Per-project client lifecycle]
    └──required-by──> [Visible retry for GCP 403 rateLimitExceeded]
    (retry must wrap per-project client construction + API calls, not global clients)

[Single-project compatibility (--project)]
    └──conflicts──> [Project enumeration]
    (if --project set, skip enumeration entirely)
```

### Dependency Notes

- **Credential fix is the prerequisite for everything else**: Project enumeration, per-project
  lifecycle, retry, and checkpoint all require working credentials. Fix credentials first.
- **Project enumeration enables checkpoint**: Checkpoint needs a stable list of project IDs to
  track. Enumeration must run before checkpoint logic.
- **Per-project client lifecycle enables visible retry**: Retry wraps the per-project scan
  function. If clients are global (current pattern), there is no clean scope to retry at the
  project level.
- **Single-project mode conflicts with enumeration**: These are mutually exclusive paths — not
  combined features. The `--project` flag (or `GOOGLE_CLOUD_PROJECT` env var) bypasses
  enumeration entirely, preserving backward compatibility.
- **Org/folder traversal requires org ID**: `search_projects()` works without org ID;
  `list_projects()` with folder traversal requires `GOOGLE_CLOUD_ORG_ID`. Org enumeration
  is an enhancement on top of basic `search_projects()`, not a replacement.

---

## MVP Definition

This is a hardening milestone. MVP = minimum changes to make GCP discovery work reliably
across multiple projects, mirroring what Azure v1 delivered.

### Fix With (Milestone v1.1)

All items below build on or replace existing code in `gcp_discovery/config.py`,
`gcp_discovery/discover.py`, and `gcp_discovery/gcp_discovery.py`.

- [ ] **Credential chain: SA key → ADC → browser, with fail-fast**
  REPLACES `get_gcp_credential()` in `config.py`. Catches `RefreshError` with `invalid_grant`
  and exits with actionable message. Validates by calling `credentials.refresh()`, not
  `gcloud auth list`.

- [ ] **Credential singleton, warmed on main thread before workers**
  EXTENDS `config.py`. Thread-safe singleton pattern (global + `threading.Lock`) matching
  Azure's `get_azure_credential()`. Logs credential type at startup.

- [ ] **Project enumeration: `get_all_gcp_project_ids()`**
  NEW function in `config.py`. Calls `resourcemanager_v3.ProjectsClient.search_projects()`
  for accessible projects. Filters to `ACTIVE` state only. If `GOOGLE_CLOUD_ORG_ID` set,
  uses `list_projects()` + recursive folder traversal for complete org coverage. If
  `GOOGLE_CLOUD_PROJECT` set, returns single project (backward compat).

- [ ] **Per-project client lifecycle in `discover_project()`**
  REPLACES global client init in `GCPDiscovery.__init__`. Creates all GCP SDK clients inside
  the per-project worker function. Explicitly closes them (`.transport.close()`) on exit.
  Bounds socket count at `project_workers * (num_client_types)`.

- [ ] **Visible retry for 403 rateLimitExceeded**
  NEW retry configuration using `google.api_core.retry.Retry`. Predicate handles
  `ResourceExhausted` and `Forbidden/rateLimitExceeded`. Logs each retry with project ID
  and attempt number. Default: 3 attempts, exponential backoff.

- [ ] **Checkpoint/resume per project**
  NEW in `discover.py`. JSON checkpoint file (atomic write). `--no-checkpoint`, `--resume`,
  `--checkpoint-file`, `--checkpoint-ttl-hours` flags. Prompt to resume on restart.
  Saves after each project completes. Deletes on successful completion.

- [ ] **Scan summary and failed-project log**
  EXTENDS `discover.py`. `[N/total] project-id` progress output. Collect and display failed
  projects after scan. Export `output/gcp_failed_projects_{timestamp}.txt`.

### Add After Validation (v1.x)

- [ ] **Org/folder-aware enumeration** — Add recursive folder traversal when
  `GOOGLE_CLOUD_ORG_ID` is set. Low-risk extension of the enumeration feature.
  Trigger: first user report of missing projects in deep folder hierarchies.

- [ ] **Project filter: --include-projects / --exclude-projects** — Add glob filtering.
  Trigger: SE feedback that they need to exclude staging/test projects during customer scans.

### Future Consideration (v2+)

- [ ] **GCP Asset Inventory integration** — Cloud Asset API can enumerate resources across
  all projects in a single call, similar to Azure Resource Graph. Eliminates per-project
  Compute API calls. High complexity — requires `google-cloud-asset` dependency, different
  data model, coverage gaps for some resource types.

- [ ] **Async discovery mode** — Full asyncio rewrite. Only justified if sync threading at
  current worker counts proves to be a throughput bottleneck after v1.1 ships.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Credential chain + fail-fast | HIGH — fixes broken tool | LOW — replaces ~20 lines in config.py | P1 |
| Credential singleton, warmed on main thread | HIGH — prevents auth race in workers | LOW — ~30 lines in config.py | P1 |
| Project enumeration (`get_all_gcp_project_ids`) | HIGH — enables multi-project | MEDIUM — new function, resourcemanager_v3 client | P1 |
| Per-project client lifecycle | HIGH — prevents socket exhaustion | MEDIUM — refactor GCPDiscovery init | P1 |
| Visible retry for 403 rateLimitExceeded | HIGH — prevents silent failures | LOW — configure google.api_core.retry | P1 |
| Checkpoint/resume per project | HIGH — crash recovery | MEDIUM — mirrors Azure pattern | P1 |
| Scan summary + failed-project log | MEDIUM — UX/diagnostics | LOW — extend existing output | P1 |
| Credential path logging | MEDIUM — diagnostics | LOW — one print statement after auth | P1 |
| Large-org warning | LOW — UX | LOW — conditional print | P2 |
| Single-project backward compat (`--project`) | MEDIUM — existing users | LOW — env var + flag check | P2 |
| Org/folder-aware enumeration | MEDIUM — complete coverage | MEDIUM — recursive FoldersClient traversal | P2 |
| Project filter (include/exclude) | LOW — power user | LOW — glob matching | P2 |
| Cloud Asset Inventory | HIGH — major perf gain | HIGH — new dep, new data model | P3 |
| Async rewrite | LOW — premature optimization | HIGH — wholesale SDK change | P3 |

**Priority key:**
- P1: Must have for v1.1 milestone
- P2: Add when core is working and tested
- P3: Future milestone

---

## Relationship to Existing Code

Each feature's relationship to the existing `gcp_discovery/` module:

| Feature | Existing Code | Action |
|---------|--------------|--------|
| Credential chain + fail-fast | `get_gcp_credential()` in `config.py` — uses `google.auth.default()`, no validation | REPLACE |
| Credential singleton | Partially present: global `_credential_cache` pattern missing; credential created fresh each `GCPDiscovery.__init__` | ADD |
| Project enumeration | `_get_default_project_id()` reads single project from env/CLI only | ADD new function |
| Per-project client lifecycle | Clients initialized in `_init_gcp_clients()` as instance vars, live for object lifetime | REPLACE |
| Visible retry | No retry logic exists for GCP API calls | ADD |
| Checkpoint/resume | Not present in GCP module | ADD (mirror Azure `discover.py`) |
| Scan summary | Partial: `discover.py` prints final count, no per-project progress or error log | EXTEND |
| Credential path logging | Not present | ADD |
| `check_gcloud_version()` | Validates gcloud CLI version via subprocess | REMOVE (irrelevant for API-based auth) |
| `check_gcp_credentials()` | Validates via `gcloud auth list` subprocess | REPLACE with `credentials.refresh()` check |

---

## Sources

**Official GCP documentation (HIGH confidence):**
- Cloud Resource Manager quotas (v3 list: 10 req/s): https://docs.cloud.google.com/resource-manager/docs/limits
- Resource Manager Python client — `ProjectsClient.search_projects()` and `list_projects()`: https://docs.cloud.google.com/python/docs/reference/cloudresourcemanager/latest/google.cloud.resourcemanager_v3.services.projects.ProjectsClient
- Listing all projects in hierarchy (recursive folder traversal pattern): https://docs.cloud.google.com/resource-manager/docs/listing-all-resources
- Project lifecycle states (ACTIVE, DELETE_REQUESTED, DELETE_IN_PROGRESS): https://docs.cloud.google.com/resource-manager/reference/rest/v3/projects/delete
- Access control for projects — minimum `roles/browser` for `resourcemanager.projects.list`: https://docs.cloud.google.com/resource-manager/docs/access-control-proj
- Compute Engine rate quotas — per-project, 403 rateLimitExceeded: https://docs.cloud.google.com/compute/api-quota
- Application Default Credentials — credential resolution order: https://docs.cloud.google.com/docs/authentication/application-default-credentials
- google.api_core retry with exponential backoff (built-in, configurable): https://blog.salrashid.dev/articles/2021/exponential_backoff_retry/

**Cross-project credential access (MEDIUM confidence — multiple sources agree):**
- Single service account can access multiple projects via org-level IAM grants: https://www.cloudquery.io/blog/creating-cross-project-service-accounts-in-gcp
- Per-project quota tracking: quotas don't accumulate across projects (confirmed from official GCP quota docs)

**Codebase analysis (HIGH confidence — first-party):**
- Broken credential: `gcp_discovery/config.py:56-65` — `get_gcp_credential()` uses `google.auth.default()` with no validation
- Broken credential check: `gcp_discovery/discover.py:45-76` — `check_gcp_credentials()` uses `gcloud auth list` subprocess
- Global client init: `gcp_discovery/gcp_discovery.py:58-82` — `_init_gcp_clients()` creates clients as instance vars at construction
- Single project: `gcp_discovery/config.py:25-53` — `_get_default_project_id()` returns one project
- No retry: `gcp_discovery/gcp_discovery.py` — no `google.api_core.retry` usage anywhere

---

*Feature research for: GCP multi-project discovery hardening (v1.1 milestone)*
*Researched: 2026-02-19*
