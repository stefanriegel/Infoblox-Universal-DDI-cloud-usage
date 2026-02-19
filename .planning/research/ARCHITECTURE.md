# Architecture Research

**Domain:** GCP multi-project discovery — credential singleton, project enumeration, per-project client lifecycle
**Researched:** 2026-02-19
**Confidence:** HIGH (GCP SDK API surface confirmed against official docs), MEDIUM (retry configuration — pattern documented but not all details verified in GCP compute client specifically)

---

## System Overview

The v1.1 milestone adds a project enumeration layer and wraps the existing per-region discovery loop inside a per-project loop. The architecture mirrors Azure's proven pattern: one credential singleton, one project-enumeration call, then N parallel workers each running the existing regional discovery for their assigned project.

```
┌──────────────────────────────────────────────────────────────────┐
│                      CREDENTIAL TIER                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  get_gcp_credential() — singleton, double-checked lock     │  │
│  │  Service Account JSON | ADC (gcloud) | Interactive         │  │
│  │  credentials.refresh() called on main thread before workers│  │
│  └──────────────────────────────────┬─────────────────────────┘  │
└─────────────────────────────────────┼────────────────────────────┘
                                      │ shared credentials object
                                      │ (passed by reference)
┌─────────────────────────────────────▼────────────────────────────┐
│                   PROJECT ENUMERATION TIER (NEW)                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  get_all_gcp_project_ids()  — config.py                    │  │
│  │  GCP_PROJECT env var?  → [single project]                  │  │
│  │  Otherwise: ProjectsClient.list_projects(org_id)           │  │
│  │             recursive over folders                         │  │
│  │  Result: ["proj-a", "proj-b", "proj-c", ...]               │  │
│  └──────────────────────────────────┬─────────────────────────┘  │
└─────────────────────────────────────┼────────────────────────────┘
                                      │ list of project IDs
┌─────────────────────────────────────▼────────────────────────────┐
│                   CLIENT TIER (per-project workers)               │
│  ThreadPoolExecutor (project_workers=4)                           │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐        │
│  │  Worker: proj-a│ │  Worker: proj-b│ │  Worker: proj-c│ ...    │
│  │  Compute clients│ │  Compute clients│ │  Compute clients│       │
│  │  (shared cred) │ │  (shared cred) │ │  (shared cred) │        │
│  │  dns.Client    │ │  dns.Client    │ │  dns.Client    │        │
│  │  (per-project) │ │  (per-project) │ │  (per-project) │        │
│  └───────┬────────┘ └───────┬────────┘ └───────┬────────┘        │
│          │                  │                  │                  │
│          ▼                  ▼                  ▼                  │
│  discover_project(proj_id) — existing _discover_region() per zone │
│  (inner ThreadPoolExecutor for regions, max_workers=8)            │
└──────────────────────────────────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼────────────────────────────┐
│               CHECKPOINT TIER (NEW)                               │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  save_checkpoint() / load_checkpoint() — discover.py       │  │
│  │  JSON file: output/gcp_discovery_checkpoint.json           │  │
│  │  Saved after each project completes                        │  │
│  │  TTL configurable via --checkpoint-ttl-hours               │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

## New vs Modified Files

| File | Status | Changes |
|------|--------|---------|
| `gcp_discovery/config.py` | Modified | Add `get_all_gcp_project_ids()`, harden `get_gcp_credential()` singleton with threading lock, add credential warm-up |
| `gcp_discovery/discover.py` | Modified | Add project loop with ThreadPoolExecutor, checkpoint save/load, new CLI args (`--project-workers`, `--checkpoint-file`, `--checkpoint-ttl-hours`, `--retry-attempts`, `--warn-project-threshold`) |
| `gcp_discovery/gcp_discovery.py` | Modified | Refactor `_init_gcp_clients()` to accept project_id, accept shared clients; make project_id a method parameter in discover methods; add per-project dns.Client; add retry decorator to GCP API calls |
| `gcp_discovery/gcp_discovery.py` | Modified | Add `discover_project(project_id, max_workers)` method that wraps existing `discover_native_objects()` for a single project |

No new top-level directories or modules are required. All changes stay inside `gcp_discovery/`.

---

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `get_gcp_credential()` | Returns singleton credentials; refreshed on main thread before workers spawn; fail-fast on `invalid_grant` or `DefaultCredentialsError` | `config.py` |
| `get_all_gcp_project_ids()` | Returns list of project IDs to scan; respects `GOOGLE_CLOUD_PROJECT` env var for single-project override; falls back to `gcloud projects list` if org ID unavailable | `config.py` |
| `discover_project(project_id)` | Runs existing per-region discovery loop for one project; returns list of resources tagged with `project_id`; closes dns.Client after completion | `gcp_discovery.py` |
| `save_checkpoint()` / `load_checkpoint()` | JSON checkpoint file with completed project list and accumulated resources; atomic write via temp file rename | `discover.py` |
| `main()` project loop | ThreadPoolExecutor outer loop over projects; saves checkpoint after each future completes; respects `--project-workers` | `discover.py` |

---

## Architectural Patterns

### Pattern 1: GCP Compute Clients Are Project-Agnostic (Pass project per request)

**What:** GCP compute_v1 clients (InstancesClient, SubnetworksClient, NetworksClient, AddressesClient, ZonesClient, GlobalAddressesClient) do NOT embed project_id at construction time. The project is passed in each `request` object at call time.

**Confirmed:** Official GCP documentation for `AggregatedListInstancesRequest` and `ListSubnetworksRequest` both show `project` as a field on the request object, not the client constructor. One `InstancesClient` can query `proj-a`, then `proj-b`, in successive calls by changing `request.project`.

**Implication:** The existing `self.compute_client`, `self.zones_client`, `self.subnetworks_client`, `self.addresses_client`, and `self.global_addresses_client` can remain as class-level singletons. No per-project re-instantiation needed for compute clients.

**What changes:** Every method that currently hard-codes `self.project_id` in the request dict must accept `project_id` as a parameter.

```python
# Before (single-project)
def _discover_compute_instances(self, region: str) -> List[Dict]:
    request = {"project": self.project_id, "zone": zone}

# After (multi-project)
def _discover_compute_instances(self, region: str, project_id: str) -> List[Dict]:
    request = {"project": project_id, "zone": zone}
```

### Pattern 2: DNS Client Requires Per-Project Instantiation

**What:** `google.cloud.dns.Client` takes `project` in its constructor, not per-call. The existing `self.dns_client = dns.Client(project=self.project_id, credentials=credentials)` bakes in the project at construction time. There is no per-call project override.

**Implication:** A fresh `dns.Client(project=project_id, credentials=credentials)` must be created inside each `discover_project()` call and closed (or garbage collected) after the project completes.

**Pattern:** The dns.Client is a local variable inside `discover_project()`, not a class attribute. This mirrors how Azure's `discover.py` creates per-subscription management clients inside `discover_subscription()`.

```python
def discover_project(self, project_id: str, max_workers: int = 8) -> List[Dict]:
    # Per-project DNS client — project baked into constructor
    dns_client = dns.Client(project=project_id, credentials=self.credentials)
    try:
        resources = self._discover_all_regions(project_id, dns_client, max_workers)
        return resources
    finally:
        # dns.Client does not expose close(); let GC collect it
        pass
```

### Pattern 3: Credential Singleton with Warm-Up Before Workers

**What:** `google.auth.default()` returns credentials that may be expired (`invalid_grant`). Calling `credentials.refresh(google.auth.transport.requests.Request())` on the main thread before spawning workers validates the credentials and pre-populates the token.

**Confirmed:** Official google-auth docs confirm `credentials.refresh(request)` raises `RefreshError` on failure (including `invalid_grant`), making it the correct fail-fast validation point. The threading search results indicate google-auth has internal refresh worker coordination to minimize concurrent refresh calls, but explicit warm-up on the main thread remains the safest pattern (same reasoning as Azure's `get_token()` warm-up before `InteractiveBrowserCredential` workers).

```python
# config.py
_gcp_credential_cache = None
_gcp_credential_lock = threading.Lock()

def get_gcp_credential():
    global _gcp_credential_cache
    if _gcp_credential_cache is not None:
        return _gcp_credential_cache
    with _gcp_credential_lock:
        if _gcp_credential_cache is not None:
            return _gcp_credential_cache
        try:
            credentials, project = google.auth.default()
        except DefaultCredentialsError as e:
            raise SystemExit(
                f"GCP credentials not found: {e}\n"
                "Run 'gcloud auth application-default login' or set GOOGLE_APPLICATION_CREDENTIALS."
            )
        # Warm up: validates token, fails fast on invalid_grant
        try:
            from google.auth.transport.requests import Request
            credentials.refresh(Request())
            print("[Auth] GCP credentials validated")
        except google.auth.exceptions.RefreshError as e:
            raise SystemExit(f"GCP credential refresh failed: {e}")
        _gcp_credential_cache = (credentials, project)
        return _gcp_credential_cache
```

### Pattern 4: Project Enumeration with Org-Level and Single-Project Fallback

**What:** `resourcemanager_v3.ProjectsClient.list_projects(parent="organizations/{org_id}")` lists all projects accessible to the credential. The org ID is discovered via `resourcemanager_v3.OrganizationsClient.search_organizations()` or `gcloud organizations list`. If no org is found (standalone projects, sandbox accounts), fall back to the single project from `GOOGLE_CLOUD_PROJECT` or `gcloud config get-value project`.

**Confirmed:** Official Resource Manager v3 Python client docs confirm `list_projects` takes a `parent` string in `organizations/{id}` or `folders/{id}` format. The paginator handles continuation tokens automatically.

**Important:** Folders can contain nested folders with projects. A breadth-first traversal is needed for complete enumeration (use `FoldersClient.list_folders` to discover nested parents, then `list_projects` on each).

```python
# config.py
def get_all_gcp_project_ids(credentials) -> List[str]:
    # Explicit override: single project
    single = os.getenv("GOOGLE_CLOUD_PROJECT")
    if single:
        return [single]

    from google.cloud import resourcemanager_v3

    projects_client = resourcemanager_v3.ProjectsClient(credentials=credentials)
    folders_client = resourcemanager_v3.FoldersClient(credentials=credentials)
    orgs_client = resourcemanager_v3.OrganizationsClient(credentials=credentials)

    # Discover org IDs
    org_ids = []
    try:
        for org in orgs_client.search_organizations():
            org_ids.append(org.name)  # "organizations/12345"
    except Exception as e:
        logger.warning(f"Could not enumerate organizations: {e}")

    if not org_ids:
        # Fall back to projects the credential has direct access to
        # (handles sandbox accounts with no org)
        return _get_projects_via_gcloud_fallback()

    # BFS over org → folders → projects
    project_ids = []
    parents_queue = list(org_ids)
    while parents_queue:
        parent = parents_queue.pop(0)
        try:
            for project in projects_client.list_projects(parent=parent):
                if project.state == resourcemanager_v3.Project.State.ACTIVE:
                    project_ids.append(project.project_id)
        except Exception as e:
            logger.warning(f"Cannot list projects under {parent}: {e}")
        try:
            for folder in folders_client.list_folders(parent=parent):
                parents_queue.append(folder.name)  # "folders/67890"
        except Exception:
            pass

    return project_ids if project_ids else _get_projects_via_gcloud_fallback()
```

### Pattern 5: Retry via google-api-core Retry (Per-Call, Not Per-Client)

**What:** `google.api_core.retry.Retry` is a callable wrapper applied per API call, not a client-level configuration. It uses a predicate function to classify retryable exceptions (429 `TooManyRequests`, 500 `InternalServerError`, 502 `BadGateway`, 503 `ServiceUnavailable`).

**Confirmed:** Official google-api-core docs show `Retry` wraps callables. The predicate `if_transient_error` already includes HTTP 429 as a transient error. For GCP compute and DNS, the client SDK does not expose a `retry_policy=` constructor kwarg like Azure — retry is applied at the call site.

**Pattern:** Wrap each GCP API call with a `Retry` instance. A module-level singleton is sufficient (the Retry object is stateless, its state lives per-call invocation).

```python
from google.api_core import exceptions as gcp_exceptions
from google.api_core.retry import Retry

_RETRYABLE_EXCEPTIONS = (
    gcp_exceptions.TooManyRequests,   # 429
    gcp_exceptions.InternalServerError,  # 500
    gcp_exceptions.BadGateway,        # 502
    gcp_exceptions.ServiceUnavailable, # 503
)

_GCP_RETRY = Retry(
    predicate=lambda e: isinstance(e, _RETRYABLE_EXCEPTIONS),
    initial=2.0,       # 2s initial backoff
    maximum=60.0,      # cap at 60s
    multiplier=2.0,    # double each retry
    deadline=300.0,    # give up after 5 min total
)

# Usage inside GCPDiscovery:
def _list_with_retry(self, client_method, request):
    return _GCP_RETRY(client_method)(request=request)
```

**Note:** GCP Quota exceeded errors (429) may include a `Retry-After` equivalent in headers, but the google-api-core `Retry` class uses exponential backoff by default. For visible retry messaging (like Azure's `VisibleRetryPolicy`), override the retry callback.

### Pattern 6: Checkpoint File with Per-Project Granularity

**What:** JSON checkpoint file modeled directly on Azure's existing `save_checkpoint()` / `load_checkpoint()` in `discover.py`. Save after each project future completes inside the `as_completed()` loop. Atomic write via temp file + `os.rename()` (same as Azure implementation).

**Schema:**
```json
{
  "timestamp": "2026-02-19T14:30:00",
  "args": { "format": "txt", "workers": 8, "project_workers": 4 },
  "total_projects": 47,
  "completed_projects": ["proj-a", "proj-b"],
  "all_native_objects": [ ... ],
  "errors": [{"project_id": "proj-c", "error": "..."}]
}
```

**Implementation note:** `all_native_objects` grows with each checkpoint write. For large orgs (500+ projects, millions of resources), this can make the checkpoint file very large. Consider storing only `completed_projects` + a separate partial results file, then re-merging on resume. This is a V2 optimization; V1 should match the Azure pattern exactly.

---

## Data Flow

### Project Discovery Flow

```
main() called
    |
    v
validate_gcp_credentials()
    - get_gcp_credential() [singleton, warm-up on main thread]
    - fail fast on RefreshError or DefaultCredentialsError
    |
    v
get_all_gcp_project_ids(credentials)
    - GOOGLE_CLOUD_PROJECT set? → [single project], skip org enumeration
    - Otherwise: OrganizationsClient.search_organizations()
    - BFS: FoldersClient.list_folders() + ProjectsClient.list_projects()
    - Fallback: gcloud projects list (subprocess)
    |
    v
load_checkpoint() [if not --no-checkpoint]
    - Filter out already-completed projects from project list
    |
    v
ThreadPoolExecutor(project_workers) over remaining projects
    |
    v
[per worker] discover_project(project_id)
    - Pass project_id to all compute client requests (project per-request)
    - Create dns.Client(project=project_id, credentials=credentials)
    - Run existing _discover_region() inner loop with inner ThreadPoolExecutor
    - Return List[Dict] resources tagged with project_id
    |
    v
[after each future] accumulate resources, save_checkpoint()
    |
    v
All projects done: count, license-calc, export, remove checkpoint
```

### Per-Project Client Lifecycle

```
discover_project(project_id) called
    |
    v
credentials = get_gcp_credential()  [returns cached singleton]
    |
    v
dns_client = dns.Client(project=project_id, credentials=credentials)  [per-project]
    |
    v
self.compute_client.list(request={"project": project_id, "zone": z})   [per-request]
self.subnetworks_client.list(request={"project": project_id, "region": r})
self.networks_client.list(request={"project": project_id})
self.addresses_client.list(request={"project": project_id, "region": r})
    |
    v
dns_client.list_zones()   [scoped to project_id via constructor]
    |
    v
discover_project() returns — dns_client garbage collected (no explicit close needed)
```

---

## Changes Required Per File

### `gcp_discovery/config.py` (Modified)

**Current state:** `get_gcp_credential()` calls `google.auth.default()` without error handling or token validation. No project enumeration. Single project from env or gcloud CLI.

**Required changes:**
1. Add `threading.Lock` and module-level `_gcp_credential_cache` (same pattern as Azure's `_credential_cache`)
2. In `get_gcp_credential()`: add `credentials.refresh(Request())` warm-up, catch `RefreshError` with `SystemExit`, catch `DefaultCredentialsError` with `SystemExit`
3. Add `get_all_gcp_project_ids(credentials)` function: env var check → org enumeration via ResourceManager API → gcloud fallback
4. Keep existing `_get_major_regions()` and `get_all_gcp_regions()` unchanged (these are still used per-project)

**New imports:** `threading`, `google.cloud.resourcemanager_v3`, `google.auth.transport.requests.Request`
**New dependency already in ecosystem:** `google-cloud-resource-manager` (same google-cloud family; likely already satisfiable from existing `requirements.txt`)

### `gcp_discovery/discover.py` (Modified)

**Current state:** Creates one `GCPConfig`, one `GCPDiscovery`, calls `discovery.discover_native_objects()` for the single project.

**Required changes:**
1. Add `save_checkpoint()` and `load_checkpoint()` functions (copy-adapt from `azure_discovery/discover.py`)
2. In `main()`:
   - Call `validate_gcp_credentials()` (already exists but broken — fix to use singleton pattern)
   - Call `get_all_gcp_project_ids(credentials)` to get project list
   - Add checkpoint load/resume block (mirrors Azure pattern)
   - Replace single `discovery.discover_native_objects()` call with `ThreadPoolExecutor` over projects
   - Inside each worker: call `discover_project(project_id)`
   - After each future: accumulate, checkpoint save
3. Add new CLI args: `--project-workers` (default 4), `--checkpoint-file`, `--checkpoint-ttl-hours` (default 48), `--warn-project-threshold` (default 50)
4. Pass credential to `discover_project` (credential retrieved once before loop, passed down)

**Signal handler:** Add `signal.signal(SIGINT, ...)` same as Azure for graceful shutdown with checkpoint save.

### `gcp_discovery/gcp_discovery.py` (Modified)

**Current state:** `GCPDiscovery.__init__()` calls `_init_gcp_clients()` which bakes `self.project_id` into the DNS client. All discovery methods hard-code `self.project_id` in request dicts.

**Required changes:**
1. Extract shared compute clients out of `__init__` into module-level or class-level singletons initialized once with credentials (NOT per-project). These can be reused across projects.
2. Add `discover_project(project_id, max_workers)` method:
   - Creates `dns.Client(project=project_id, credentials=self.credentials)` locally
   - Builds `zones_by_region` cache for this specific project (current `_build_zones_by_region()` uses `self.project_id` — must accept project_id param)
   - Calls inner region loop with `project_id` threaded through
   - Returns `List[Dict]` (does NOT set `self._discovered_resources` — that caching is per-project, not global)
3. Refactor all discovery methods to accept `project_id: str` parameter instead of using `self.project_id`:
   - `_discover_region(self, region, project_id)`
   - `_discover_compute_instances(self, region, project_id)`
   - `_discover_vpc_networks(self, region, project_id)`
   - `_discover_subnets(self, region, project_id)`
   - `_discover_reserved_ip_addresses(self, region, project_id)`
   - `_discover_cloud_dns_zones_and_records(self, dns_client)` — accepts dns_client, not project_id
4. Add `project_id` to each resource's `details` dict so resources can be attributed per project in output
5. Add retry wrapper (`_GCP_RETRY` from `google.api_core.retry`) around each SDK list call
6. Keep `discover_native_objects()` working for backward compatibility (single-project path); it calls `discover_project(self.project_id)`

**Backward compatibility note:** `GCPDiscovery(config)` with a single `config.project_id` still works — `discover_native_objects()` calls `discover_project(self.project_id)`. The `main()` function in `discover.py` is what switches to the multi-project path.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Per-Project Credential Objects

**What:** Creating `google.auth.default()` inside `discover_project()` or inside each worker thread.

**Why wrong:** `google.auth.default()` re-reads the credential chain from scratch on every call. If the credential requires interactive auth (browser), this is catastrophic in a thread pool. For ADC or service account credentials, it adds unnecessary overhead and prevents coordinated token refresh.

**Do instead:** Call `get_gcp_credential()` once on the main thread, pass the returned `(credentials, project)` tuple to workers by closure.

### Anti-Pattern 2: Reusing dns.Client Across Projects

**What:** Creating `self.dns_client = dns.Client(project=project_a)` at class init, then calling `dns_client.list_zones()` when actually scanning project_b.

**Why wrong:** `google.cloud.dns.Client` binds the project at construction time. All DNS calls go to that project's DNS API, regardless of what you intend. This is the current bug — the existing code uses `self.project_id` set at init time, so in a multi-project loop it would only return DNS records for the first project.

**Do instead:** Instantiate a new `dns.Client(project=project_id, credentials=credentials)` inside `discover_project()`.

### Anti-Pattern 3: Storing _discovered_resources as Class State in Multi-Project Mode

**What:** The current `discover_native_objects()` sets `self._discovered_resources` and returns it from cache on subsequent calls. In a multi-project loop, if `GCPDiscovery` is reused across projects, the cache from project A is returned for project B.

**Why wrong:** Cross-project resource contamination; incorrect totals; silent correctness bug.

**Do instead:** `discover_project(project_id)` does NOT use or set `self._discovered_resources`. It returns resources directly. The multi-project accumulator lives in `discover.py`, not in `GCPDiscovery`.

### Anti-Pattern 4: Enumerate Regions Per Project (Expensive)

**What:** Calling `get_all_gcp_regions()` inside each `discover_project()` worker — which calls `compute_v1.RegionsClient.list()` per project.

**Why wrong:** Most GCP organizations have the same available regions across projects (unless per-project quota restrictions apply). Fetching regions 50+ times adds 50+ API calls at startup.

**Do instead:** Call `get_all_gcp_regions()` once before the project loop. Pass `all_regions` to each worker. The existing implementation already does this for the single-project case; preserve that structure.

### Anti-Pattern 5: Single ThreadPoolExecutor with project_workers × region_workers as Flat Pool

**What:** Flattening the outer (project) and inner (region) loops into one giant flat `ThreadPoolExecutor` of `project_workers * region_workers` tasks.

**Why wrong:** Loses per-project checkpointing granularity. A project is only complete when ALL its regions are done; with a flat pool you cannot checkpoint on project completion boundaries.

**Do instead:** Nested executors: outer pool (project_workers=4) dispatches `discover_project()` futures; inside each future, `discover_project()` uses its own inner ThreadPoolExecutor for regions (max_workers=8, same as current `discover_native_objects()`).

---

## Build Order

The components have clear dependencies. Build in this order to avoid integration regressions:

**Phase 1: Credential Chain Fix (config.py)**

1. Add `threading.Lock` singleton pattern to `get_gcp_credential()`
2. Add `credentials.refresh()` warm-up with `SystemExit` on `RefreshError`
3. Detect credential type and print `[Auth] Using ...` message
4. Verify: `gcloud auth application-default login` → tool starts with `[Auth]` line, no credential errors

No downstream code changes yet. Existing single-project flow still works.

**Phase 2: Multi-Project Enumeration (config.py + discover.py)**

5. Add `get_all_gcp_project_ids()` to `config.py`
6. Add project loop with `ThreadPoolExecutor` to `discover.py` `main()`
7. Add checkpoint `save_checkpoint()` / `load_checkpoint()` to `discover.py`
8. Add new CLI args to `discover.py` parser
9. Add signal handler for SIGINT/SIGTERM

At this point: multi-project enumeration works but all projects share the same `GCPDiscovery` instance (incorrect — project_id is wrong for all but the first project). This is a known intermediate state; complete Phase 3 before testing.

**Phase 3: Per-Project Client Lifecycle (gcp_discovery.py)**

10. Add `discover_project(project_id, max_workers)` to `GCPDiscovery`
11. Refactor all `_discover_*` methods to accept `project_id` parameter
12. Create `dns.Client(project=project_id, ...)` inside `discover_project()`
13. Make `_build_zones_by_region()` accept `project_id` parameter
14. Update `discover_native_objects()` to delegate to `discover_project(self.project_id)` for backward compat
15. Add `project_id` field to each resource's `details` dict

At this point: full multi-project discovery is working end-to-end.

**Phase 4: Retry and Observability (gcp_discovery.py + discover.py)**

16. Add `_GCP_RETRY` module-level retry instance
17. Wrap each SDK list call with `_GCP_RETRY`
18. Add large-org warning (`warn_project_threshold` check)
19. Add verbose resume logging (list of skipped project IDs on resume)
20. Add `--warn-project-threshold` CLI arg

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| GCP Cloud Resource Manager API | `resourcemanager_v3.ProjectsClient.list_projects(parent="organizations/{id}")` | Requires `resourcemanager.projects.list` permission on org. New dependency: `google-cloud-resource-manager`. |
| GCP Compute Engine API | `compute_v1.*Client.list(request={"project": project_id, ...})` | Project is per-request, not per-client. One client set serves all projects. |
| Google Cloud DNS API | `dns.Client(project=project_id, credentials=credentials)` | Project baked into constructor. Must be per-project instance. |
| Google OAuth2 token endpoint | `credentials.refresh(Request())` for warm-up | Called once on main thread before any workers spawn. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `config.py` → `discover.py` | `get_gcp_credential()` returns singleton `(credentials, project)` tuple; `get_all_gcp_project_ids(credentials)` returns `List[str]` | Credentials must be warmed before project enumeration; credentials passed into `get_all_gcp_project_ids()` to avoid redundant calls |
| `discover.py` → `gcp_discovery.py` | `GCPDiscovery(config)` constructed once; `discovery.discover_project(project_id)` called per worker | `GCPDiscovery` holds shared compute clients; `discover_project` creates per-project DNS client |
| `gcp_discovery.py` → `shared/base_discovery.py` | `_format_resource()` inherited; `_discovered_resources` cache NOT used in multi-project mode | Multi-project accumulation happens in `discover.py`, not in `GCPDiscovery` |
| Checkpoint file → `discover.py` | JSON file with `completed_projects`, `all_native_objects`, `errors` | Same schema as Azure checkpoint; atomic write via temp rename |

### Dependency on Existing Shared Infrastructure

No changes needed to:
- `shared/base_discovery.py` — `_format_resource()` already provider-agnostic
- `shared/resource_counter.py` — provider-agnostic counting works on the merged `all_native_objects` list
- `shared/output_utils.py` — works on any list of formatted resources
- `shared/licensing_calculator.py` — provider-agnostic calculation

The only shared-layer concern: `_format_resource()` generates `resource_id` as `"{region}:{resource_type}:{name}"`. In multi-project mode, two projects could have identically named resources in the same region. The `resource_id` must include `project_id` to avoid deduplication collisions in `ResourceCounter`. Add `project_id` to the resource dict's `details` field; the resource_id can remain unchanged (dedup is by content hash in `ResourceCounter`, not `resource_id` string — verify before shipping).

---

## Sources

- [GCP Compute instances list-all sample — project in request, not client constructor](https://cloud.google.com/compute/docs/samples/compute-instances-list-all) — HIGH confidence (official GCP documentation sample code)
- [ResourceManager v3 ProjectsClient.list_projects() reference](https://docs.cloud.google.com/python/docs/reference/cloudresourcemanager/latest/google.cloud.resourcemanager_v3.services.projects.ProjectsClient) — HIGH confidence (official API reference)
- [Listing all resources in GCP hierarchy](https://docs.cloud.google.com/resource-manager/docs/listing-all-resources) — HIGH confidence (official GCP documentation)
- [google.cloud.dns.Client constructor — project parameter](https://cloud.google.com/python/docs/reference/dns/latest/client) — HIGH confidence (official API reference)
- [google-api-core Retry class reference](https://googleapis.dev/python/google-api-core/latest/retry.html) — HIGH confidence (official documentation)
- [google-auth credentials.refresh() reference](https://googleapis.dev/python/google-auth/latest/reference/google.auth.credentials.html) — HIGH confidence (official API reference)
- [google-api-python-client thread safety](https://googleapis.github.io/google-api-python-client/docs/thread_safety.html) — MEDIUM confidence (covers older discovery-based clients; Cloud client libraries use different transport but same underlying credential threading model)

---

*Architecture research for: GCP multi-project discovery — credential singleton, project enumeration, per-project DNS client*
*Researched: 2026-02-19*
