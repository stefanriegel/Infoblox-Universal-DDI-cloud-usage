# Pitfalls Research

**Domain:** GCP multi-project discovery — Python google-cloud-compute/dns concurrent multi-project discovery
**Researched:** 2026-02-19
**Confidence:** HIGH (verified against official GCP documentation, googleapis GitHub issues, and google-auth library behavior)

---

## Critical Pitfalls

### Pitfall 1: google.auth.default() Returns Credentials That Cannot Refresh — Silent Failure

**What goes wrong:**
`google.auth.default()` returns a credentials object without validating it. If the underlying ADC token is expired or if the OAuth2 consent screen is in "Testing" mode (refresh tokens expire after 7 days), the returned credentials object appears valid but throws `google.auth.exceptions.RefreshError: invalid_grant: Bad Request` the first time any API call is made. The current code catches this in a bare `except Exception` in `_init_gcp_clients()`, raises a generic error, and then the outer discovery loop reports "Discovery completed successfully!" with 0 resources.

The current `check_gcp_credentials()` in `discover.py` only runs `gcloud auth list` via subprocess. This checks whether any `gcloud` CLI accounts exist — not whether the ADC token at `~/.config/gcloud/application_default_credentials.json` is valid. The two auth paths are entirely separate: a user can have an active `gcloud` account but expired ADC credentials. The pre-check passes; every API call fails.

**Why it happens:**
ADC user credentials (created by `gcloud auth application-default login`) store a refresh token. The refresh token itself may be revoked if:
- The OAuth2 project's consent screen publishing status is "Testing" — tokens expire in 7 days
- The user authenticated more than 6 months ago without re-authenticating
- The user exceeded 50 simultaneous refresh tokens for the same OAuth client
- On WSL: the `application_default_credentials.json` is stored in the Linux filesystem at `$HOME/.config/gcloud/` but `gcloud` CLI on WSL may read from a different path than the Python library expects

`google.auth.default()` does not call the token endpoint at construction time. It returns the credential object immediately. The first actual API call triggers `credentials.refresh(request)`, which is where `invalid_grant` is thrown.

**How to avoid:**
After calling `google.auth.default()`, eagerly validate the credentials by making a lightweight real API call before spawning any workers. Use `google.auth.transport.requests.Request` to force a token refresh explicitly:

```python
import google.auth
import google.auth.transport.requests
from google.auth.exceptions import RefreshError, DefaultCredentialsError

def get_gcp_credentials_validated():
    """Get and eagerly validate GCP credentials. Fail fast on invalid tokens."""
    try:
        credentials, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    except DefaultCredentialsError as e:
        raise SystemExit(
            f"[Auth] No GCP credentials found: {e}\n"
            "Run: gcloud auth application-default login"
        )

    # Force a token refresh to detect invalid_grant before workers start.
    try:
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
    except RefreshError as e:
        raise SystemExit(
            f"[Auth] GCP credentials are expired or revoked: {e}\n"
            "Run: gcloud auth application-default login"
        )

    print(f"[Auth] GCP credentials validated. Type: {type(credentials).__name__}")
    return credentials, project
```

Remove `check_gcp_credentials()` (the subprocess-based gcloud check) entirely. It provides no protection and misleads users into thinking their auth is working.

**Warning signs:**
- 70+ lines of error output followed by "Discovery completed successfully!" with 0 resources
- `google.auth.exceptions.RefreshError: invalid_grant: Bad Request` in logs (currently swallowed)
- `check_gcp_credentials()` passes but every API call fails immediately after
- Users on WSL report auth works from `gcloud` CLI but not from the Python tool

**Phase to address:** Phase 1 — Credential chain fix. This is the root bug blocking all GCP discovery.

---

### Pitfall 2: Per-Project gRPC Client Proliferation — Socket Exhaustion

**What goes wrong:**
The current `GCPDiscovery.__init__` creates 7 separate GCP client instances (InstancesClient, ZonesClient, NetworksClient, SubnetworksClient, AddressesClient, GlobalAddressesClient, dns.Client). Each gRPC-based client spawns approximately 4 internal background threads (channel polling, delivery, etc.) and holds an open HTTP/2 connection.

When moving to multi-project discovery, if a new `GCPDiscovery` instance is created per project (the natural extension of the current single-project pattern), a 50-project scan creates 350 client instances and ~1,400 background threads. These are never closed. On Windows/WSL, file descriptor limits are lower than Linux, and exhaustion occurs earlier — similar to the Azure `ComputeManagementClient` socket exhaustion that triggered the v1 rewrite.

Even with a single `GCPDiscovery` instance shared across all projects, the clients built at `__init__` time hold credentials for a single project's context and cannot easily be reused across projects for project-scoped APIs.

**Why it happens:**
The Azure v1 lesson was: create management clients per-subscription, close them immediately after use. The equivalent GCP pattern is: create compute/dns clients per-project inside the worker function, close them (`.transport.close()`) when the project's discovery completes. Not doing this creates the same socket exhaustion path.

GCP Python gRPC clients are thread-safe — a single instance CAN be shared across threads. But for multi-project scans, the project ID is baked into many API calls, so shared clients must accept project as a parameter (they do, via `project=` on each request), not at construction time. This is the correct approach.

**How to avoid:**
Build client instances once at the top level (or as a per-project context manager), passing `project=` per API call rather than at client construction. After each project's discovery completes, call `.transport.close()` on each client to release the gRPC channel:

```python
def discover_project(project_id: str, credentials) -> list:
    from google.cloud import compute_v1, dns

    compute = compute_v1.InstancesClient(credentials=credentials)
    zones = compute_v1.ZonesClient(credentials=credentials)
    # ... other clients
    try:
        return _do_discovery(project_id, compute, zones, ...)
    finally:
        # Release gRPC channels
        compute.transport.close()
        zones.transport.close()
```

Alternatively, share a single set of clients across all projects (thread-safe per official docs) and always pass `project=project_id` per API call, never at construction. This is more efficient but requires confirming none of the clients cache project-scoped state.

**Warning signs:**
- Memory grows ~5 MB per project processed
- `ResourceWarning: unclosed transport` in Python output
- Worker threads count in Activity Monitor grows without bound during a run
- `OSError: [Errno 24] Too many open files` after 30-50 projects on WSL

**Phase to address:** Phase 2 — Concurrent execution hardening, per-project client lifecycle.

---

### Pitfall 3: Project Enumeration Requires Org-Level Permissions — Silent Empty Result

**What goes wrong:**
`resourcemanager_v3.ProjectsClient().search_projects()` or `list_projects()` returns only projects the caller has `resourcemanager.projects.get` on. If the service account or ADC user has only project-level permissions (Viewer on specific projects), the org-level search returns an empty result — no error, no warning, just 0 projects found. The tool then silently discovers nothing.

The v1 filter syntax `parent.type:organization parent.id:ORG_ID` requires the caller to have permissions at the organization level. Without it, the API returns an empty page with no indication that permissions caused the empty result.

Additionally, `projects.list()` and `projects.search()` return projects in `DELETE_REQUESTED` state by default — projects that are 1-30 days into the deletion grace period. Attempting to discover resources in `DELETE_REQUESTED` projects produces a flood of 403 errors and wastes time.

**Why it happens:**
The Resource Manager API has two distinct behaviors:
1. Org-level enumeration (requires `resourcemanager.projects.list` at org level) — returns all projects in org
2. User-scoped enumeration (no special permission required) — returns only projects explicitly granted to the caller

These look identical in code but return wildly different result sets depending on IAM setup. The tool cannot distinguish "user has no projects" from "user lacks org-level permission."

**How to avoid:**
1. Filter out non-ACTIVE projects explicitly in the enumeration query:
```python
from google.cloud import resourcemanager_v3

def list_gcp_projects(credentials, org_id: str | None = None) -> list[str]:
    client = resourcemanager_v3.ProjectsClient(credentials=credentials)
    # Filter to only ACTIVE projects; skip DELETE_REQUESTED and DELETE_IN_PROGRESS
    query = "state:ACTIVE"
    if org_id:
        query = f"parent.type:organization parent.id:{org_id} state:ACTIVE"

    projects = []
    try:
        for project in client.search_projects(query=query):
            projects.append(project.project_id)
    except Exception as e:
        # Check specifically for PERMISSION_DENIED
        if "PERMISSION_DENIED" in str(e) or "403" in str(e):
            raise SystemExit(
                "[Auth] Cannot enumerate projects: missing resourcemanager.projects.list "
                "at org level. Grant 'roles/resourcemanager.folderViewer' or "
                "'roles/viewer' at organization level."
            )
        raise

    if not projects:
        print("[Warning] Project enumeration returned 0 projects. "
              "Check IAM permissions at organization level.")
    return projects
```

2. Warn explicitly when 0 projects are returned — never silently succeed with empty results.

3. Require at minimum `roles/viewer` at organization level. Document this clearly in the tool's help text.

**Warning signs:**
- `search_projects()` returns 0 results with no error
- Tool reports "Discovered 0 projects" then "Discovery completed successfully!"
- If GOOGLE_CLOUD_PROJECT is set, tool scans that single project and appears to work — masking the org enumeration failure
- `gcloud projects list` in terminal returns projects but Python tool finds none

**Phase to address:** Phase 1 — Project enumeration foundation. Must be resolved before multi-project discovery can work at all.

---

### Pitfall 4: Bare `except Exception` Swallows Auth Failures — "Completed Successfully" With 0 Resources

**What goes wrong:**
This is the current root-cause of the "no fail-fast" bug. In `gcp_discovery.py`:

```python
# Current broken code
try:
    credentials, project = get_gcp_credential()
    self.compute_client = compute_v1.InstancesClient(credentials=credentials)
    ...
except Exception as e:
    raise Exception(f"Failed to initialize GCP clients: {e}")
```

And in `discover.py`'s `main()`:
```python
try:
    native_objects = discovery.discover_native_objects(max_workers=args.workers)
    ...
    print("\nDiscovery completed successfully!")
except Exception as e:
    print(f"ERROR: {e}")
    return 1
```

When credentials fail, `GCPDiscovery.__init__` raises an `Exception`. The `main()` catch block should catch it — but `GCPDiscovery` is constructed before the try block in `main()`. If construction succeeds but the first API call fails (e.g., `_build_zones_by_region()` which is called in `__init__`), the error is swallowed in `_build_zones_by_region()` with `self.logger.warning()`, and the object is returned with an empty `_zones_by_region`. Every subsequent `_discover_compute_instances()` call silently skips all zones, and `discover_native_objects()` returns an empty list. `print("\nDiscovery completed successfully!")` runs.

**Why it happens:**
Defensive `except Exception` blocks in discovery loops prevent individual region failures from killing the entire run — correct behavior for network flakiness. But when applied to initialization paths (credential acquisition, zone enumeration), they turn hard failures into silent data loss.

**How to avoid:**
Use typed exception catches in discovery loops. Let initialization failures propagate immediately:

```python
# In config.py — fail hard, fail fast
from google.auth.exceptions import RefreshError, DefaultCredentialsError

def get_gcp_credential_validated():
    try:
        creds, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        # Force refresh to detect invalid_grant immediately
        creds.refresh(google.auth.transport.requests.Request())
        return creds, project
    except (DefaultCredentialsError, RefreshError) as e:
        raise  # Let it propagate to main() — do not swallow

# In gcp_discovery.py — let zone enum failure be a warning, not silent empty
def _build_zones_by_region(self) -> dict:
    try:
        ...
    except google.api_core.exceptions.PermissionDenied:
        self.logger.error("Cannot list zones: missing compute.zones.list permission")
        raise  # Do not swallow — propagate to surface the misconfiguration

# In _discover_region() — swallow only transient errors, not auth errors
except google.api_core.exceptions.PermissionDenied:
    self.logger.warning(f"Permission denied for region {region} — skipping")
    # Do NOT swallow — count these as partial failures
except google.api_core.exceptions.ServiceUnavailable:
    self.logger.warning(f"Transient error in region {region} — skipping")
```

**Warning signs:**
- 70+ lines of errors ending with "Discovery completed successfully!"
- `native_objects` list is empty but no exception was raised
- `_zones_by_region` is an empty dict (added debug logging to check)
- Each `_discover_region()` call immediately returns empty list

**Phase to address:** Phase 1 — Fail-fast and error propagation. Foundational fix that unlocks all other phases.

---

### Pitfall 5: Compute Engine API Not Enabled Per Project — Treated As Auth Failure

**What goes wrong:**
In a multi-project org scan, a significant fraction of projects may have the Compute Engine API disabled (projects used purely for billing, IAM, or non-compute workloads). When `compute_v1.InstancesClient().list(project=project_id)` is called against such a project, GCP returns HTTP 403 with the reason `accessNotConfigured`, not `PERMISSION_DENIED`. The error message reads: `"Compute Engine API has not been used in project {id} before or it is disabled."`.

If the tool catches all 403 errors as auth failures (e.g., logs "permission denied, skipping project"), it will silently skip projects where the API is just disabled rather than distinguishing "I don't have permission" from "this project doesn't use Compute Engine."

Conversely, if the tool treats `accessNotConfigured` as a terminal error, it will abort the entire scan because one project doesn't have Compute Engine enabled.

**Why it happens:**
GCP uses HTTP 403 for two distinct conditions:
- `PERMISSION_DENIED` — caller lacks IAM permission
- `accessNotConfigured` — the API itself is not enabled in the target project

Both look like 403 to generic error handling code. The distinction matters: `PERMISSION_DENIED` means the credential is wrong; `accessNotConfigured` means the project legitimately doesn't use that service and should be skipped gracefully.

**How to avoid:**
Inspect the error reason field, not just the HTTP status code, and handle each case distinctly:

```python
import google.api_core.exceptions

def discover_project_compute(project_id: str, client) -> list:
    try:
        return list(client.list(project=project_id, zone=zone))
    except google.api_core.exceptions.PermissionDenied as e:
        reason = getattr(e, 'reason', '') or str(e)
        if 'accessNotConfigured' in reason or 'SERVICE_DISABLED' in reason:
            logger.info(f"[{project_id}] Compute Engine API not enabled — skipping")
            return []  # Normal: project doesn't use Compute Engine
        else:
            logger.warning(f"[{project_id}] Permission denied for Compute Engine: {e}")
            return []  # Credential issue — log and skip, don't abort
    except google.api_core.exceptions.NotFound:
        logger.warning(f"[{project_id}] Project not found — skipping")
        return []
```

Track `accessNotConfigured` project count separately in the summary output:
`"Skipped (API not enabled): 12 projects"` — this is expected and normal in large orgs.

**Warning signs:**
- All projects in a large org return 0 compute resources even though some have VMs
- Logs show `403` errors but no distinction between permission denied and API not enabled
- `accessNotConfigured` appears in raw error messages but is swallowed by generic except blocks

**Phase to address:** Phase 1 — Error classification. Required alongside the fail-fast fix.

---

## Moderate Pitfalls

### Pitfall 6: Shared VPC Subnet Ownership — Subnets Appear In Host Project Only

**What goes wrong:**
In GCP Shared VPC configurations, subnets are owned by the host project, not the service projects that use them. When scanning all projects in an org, subnets will be discovered in the host project. Service projects that attach to the shared VPC will show compute instances with IPs in those subnets, but the subnets themselves will not appear under the service project's `subnetworks.list()` response.

If the tool counts subnets per-project and expects each project to own the subnets its VMs use, the count will be wrong: host project shows many subnets (including ones "belonging" to service projects), and service projects show zero subnets despite having VMs.

**Why it happens:**
This is intentional GCP Shared VPC architecture. The subnet resource belongs to the host project's VPC. Service projects reference subnets by full URL (`projects/HOST/regions/REGION/subnetworks/NAME`), they do not own them. The Compute Engine API's `subnetworks.list(project=SERVICE_PROJECT)` returns nothing for service projects using shared VPCs.

**How to avoid:**
When enumerating subnets across projects, deduplicate by subnet resource URL, not by project. A subnet counted once in the host project should not be counted again even if service project VMs reference it. Log at debug level which projects are using Shared VPC (detectable: their VMs reference subnet URLs from a different project).

For Infoblox sizing purposes, count the subnet once where it is defined (host project). Do not attempt to count it in each service project that uses it.

**Warning signs:**
- Host project shows disproportionately high subnet count vs. compute instances
- Service projects show 0 subnets but have running VMs
- Subnet URLs in compute instance network interfaces reference a different project than the scanning target

**Phase to address:** Phase 2 — Multi-project concurrent discovery correctness.

---

### Pitfall 7: Region Enumeration Per Project — `compute.regions.list` Requires Compute API Enabled

**What goes wrong:**
The current `get_all_gcp_regions()` function calls `compute_v1.RegionsClient().list(project=project)` using the credential's default project. In multi-project mode, this approach would need to be called per project to get that project's available regions — but `regions.list` requires the Compute Engine API to be enabled (same `accessNotConfigured` issue as Pitfall 5). Projects without Compute Engine enabled return an empty region list, and the code falls back to a hardcoded major-regions list.

The fallback hardcoded list in `config.py` has 34 regions. As of 2026, GCP has 40+ regions. A scan using the fallback list will miss newer regions (e.g., `me-central1`, `me-west1`, `africa-south1`) in any project using them.

Additionally, regions are organization-wide — they do not differ per project (though which region APIs are enabled can vary). Enumerating regions once from any project with Compute API enabled is sufficient.

**How to avoid:**
Enumerate regions once at startup from any project that has Compute API enabled (the first successfully enumerated project). Cache the result and use it for all subsequent projects. Do not enumerate regions per-project. Update the fallback hardcoded list to include all GCP regions as of 2026.

```python
def get_all_gcp_regions(credentials, project_ids: list[str]) -> list[str]:
    """Get GCP regions using first available project with Compute API enabled."""
    from google.cloud import compute_v1

    for project_id in project_ids[:5]:  # Try first 5 projects
        try:
            client = compute_v1.RegionsClient(credentials=credentials)
            regions = [r.name for r in client.list(project=project_id)]
            if regions:
                return regions
        except Exception:
            continue

    # Fall back to current list — note it may be stale
    logger.warning("Could not fetch regions from API; using hardcoded fallback list")
    return _get_major_regions()  # Update this list before shipping
```

**Warning signs:**
- Region count returned is exactly 34 (the hardcoded fallback — indicates API region fetch failed)
- Resources in newer GCP regions are not discovered
- `get_all_gcp_regions()` runs before `GCPDiscovery` is initialized, before any project is validated

**Phase to address:** Phase 1 — Foundation, alongside credential fix. Region list must be correct before discovery begins.

---

### Pitfall 8: Cloud DNS `dns.Client` Uses Legacy Library — Incompatible With google-cloud-dns v4

**What goes wrong:**
The current code uses `from google.cloud import dns` and instantiates `dns.Client(project=..., credentials=...)`. This is the legacy `google-cloud-dns` library API (pre-v1). The newer `google.cloud.dns_v1` (part of `google-cloud-dns >= 1.0.0`) has a different client interface. If `google-cloud-dns` is upgraded (e.g., as a transitive dependency of another package), the `dns.Client` interface may break silently.

Additionally, `dns.Client.list_zones()` and `zone.list_resource_record_sets()` are legacy method names. The v1 API uses `ManagedZonesClient` and `ResourceRecordSetsClient` as separate classes.

**Why it happens:**
The `google-cloud-dns` package underwent a major rewrite from the hand-written legacy client to the auto-generated GAPIC client between versions 0.x and 1.0.0. The legacy API (`dns.Client`) was kept for backward compatibility but may not receive updates.

**How to avoid:**
Pin the `google-cloud-dns` version in `requirements.txt` if using the legacy API, or migrate to the GAPIC API in the multi-project implementation:

```python
# New API (google-cloud-dns >= 1.0.0, GAPIC-based)
from google.cloud import dns_v1

def discover_dns_zones(project_id: str, credentials) -> list:
    client = dns_v1.ManagedZonesClient(credentials=credentials)
    request = dns_v1.ListManagedZonesRequest(project=project_id)
    zones = []
    for zone in client.list_managed_zones(request=request):
        zones.append(zone)
    return zones
```

Check `pip show google-cloud-dns` to identify current version and API generation.

**Warning signs:**
- `AttributeError: 'Client' object has no attribute 'list_zones'` after package update
- DNS discovery silently returns 0 zones without errors on upgrade
- `ImportError: cannot import name 'Client' from 'google.cloud.dns'`

**Phase to address:** Phase 1 — Verify and pin DNS client version before implementing multi-project DNS discovery.

---

### Pitfall 9: GCP Compute API Rate Limits Are Per-Project — Cross-Project Scanning Multiplies Quota Usage

**What goes wrong:**
GCP Compute Engine API rate quotas are enforced per-project. When scanning 50 projects with 8 region workers each, each project's quota is separate — a single project cannot exceed its quota from another project's API calls. This is fundamentally different from Azure, where ARM throttling was subscription-scope but shared across resource group workers.

However, the tool still sends 8 concurrent requests per project × N concurrent projects to the same underlying infrastructure. GCP may enforce org-level or credential-level rate limits that are not documented publicly. The most reliable documented limit is per-project quota (read requests at ~1200/min default for most Compute endpoints — verify in console).

The actual risk: if 8 workers hammer a single project with zone-level requests simultaneously (one request per zone per region = up to 25 zones), the 600-requests-per-minute-per-project limit for zonal reads can be exceeded within seconds on a large project.

**Why it happens:**
The current `discover_native_objects()` uses `max_workers=8` for region-level parallelism, and each region iterates over all zones serially within the worker. When moving to multi-project, if outer workers (per project) each start inner region workers, the total request rate against any single project remains bounded. The more dangerous path is the zone-level loop inside `_discover_compute_instances()` — it's serial per region but fires many sequential requests per zone.

**How to avoid:**
1. Keep per-project worker count at 4 or lower (not 8) for discovery tasks
2. Catch `google.api_core.exceptions.ResourceExhausted` (429) and implement exponential backoff with jitter:

```python
import time
import random
import google.api_core.exceptions

def _api_call_with_retry(func, *args, max_retries=5, **kwargs):
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except google.api_core.exceptions.ResourceExhausted as e:
            if attempt == max_retries - 1:
                raise
            wait = (2 ** attempt) + random.uniform(0, 1)
            logger.warning(f"Rate limited (429). Waiting {wait:.1f}s before retry {attempt+1}/{max_retries}")
            time.sleep(wait)
        except google.api_core.exceptions.ServiceUnavailable:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
```

Note: Compute API returns 403 with `rateLimitExceeded` reason (not HTTP 429) for quota exceeded. Check `e.reason` or `e.errors[0].get('reason')` for `"rateLimitExceeded"` in addition to catching `ResourceExhausted`.

**Warning signs:**
- `google.api_core.exceptions.PermissionDenied: 403 ... rateLimitExceeded` in logs
- Discovery slows progressively as the scan runs (quota refill is per-minute)
- Zone-level requests for dense projects (many zones, many instances) fail consistently

**Phase to address:** Phase 2 — Concurrent execution hardening, visible retry policy.

---

### Pitfall 10: Checkpoint Resume Must Filter on Project ID — Not Region

**What goes wrong:**
The current single-project implementation has no checkpoint. When implementing checkpoint/resume for multi-project, the natural unit is the project (analogous to subscription in Azure v1). However, if the checkpoint is stored with region-level granularity (to enable resuming mid-project), the key space becomes `(project_id, region)`, which is more complex and prone to partial-save bugs.

A simpler per-project checkpoint (mark a project complete only when all its resources have been collected and written) risks losing up to 1 project of work on crash — acceptable. A per-region checkpoint within a project risks inconsistent state if some regions completed and others didn't for a single project.

**Why it happens:**
The Azure v1 pattern saves checkpoint after each subscription completes. The GCP equivalent should save after each project completes, not after each region. Saving after each region requires transactional writes across regions within a project, which is complex to implement correctly.

**How to avoid:**
Follow the Azure v1 pattern exactly: per-project checkpoint saves only after the entire project discovery (all regions + DNS) completes successfully. The checkpoint file records `{completed_projects: [...], pending_projects: [...]}`. On resume, skip `completed_projects`.

```python
# Checkpoint schema for multi-project
{
  "version": 2,
  "timestamp": "2026-02-19T10:00:00Z",
  "completed_project_ids": ["proj-1", "proj-2"],
  "total_project_ids": ["proj-1", "proj-2", "proj-3", "proj-4"],
  "resources_collected": 1247
}
```

**Warning signs:**
- Checkpoint saves after each region — crash mid-project leaves partial data with no indication of which regions completed
- Resume scan produces duplicate resources from partially-completed projects
- Checkpoint file size grows proportionally to regions × projects (sign of over-granular checkpointing)

**Phase to address:** Phase 3 — Checkpoint/resume implementation.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `subprocess` calls to `gcloud` for credential validation | Easy to implement | Subprocess storm; gcloud not installed everywhere; WSL path issues; validates wrong auth path | Never — remove entirely |
| `except Exception` in discovery loops | Prevents scan abort on transient errors | Swallows auth failures, quota errors, and permission errors identically | Only for truly transient network errors; use typed catches for everything else |
| Hardcoded fallback region list in `_get_major_regions()` | Works when API is unavailable | List is already stale (GCP has 40+ regions); newer regions silently excluded | Acceptable as fallback only if list is updated before each release |
| Building all 7 GCP clients in `__init__` unconditionally | Simple to understand | Fails at construction time even for DNS-only scans; prevents graceful degradation per-service | Never — construct per-service, per-request, with explicit cleanup |
| Single project from `GOOGLE_CLOUD_PROJECT` env var | Works for single-project test | Masks multi-project enumeration failures; org scan silently falls back to single project | Acceptable only as explicit `--project` override flag |
| Global credential check via `gcloud auth list` before discovery | Gives user confidence before long scan | Validates CLI auth, not ADC; false assurance; real failures occur minutes later | Never — validates the wrong thing |

---

## Integration Gotchas

Common mistakes when connecting to GCP services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| google.auth.default() | Treating returned credentials as validated | Always call `credentials.refresh(Request())` immediately after; catch `RefreshError` before workers start |
| google-cloud-compute clients | Creating one client instance per project in a loop | Create once, reuse with `project=project_id` per API call; GCP clients are thread-safe across threads |
| google-cloud-dns legacy API | Calling `dns.Client(project=...).list_zones()` and assuming it works across all library versions | Pin version OR migrate to `dns_v1.ManagedZonesClient`; test after any dependency update |
| ResourceManager `search_projects()` | Treating 0 results as "no projects exist" | 0 results can mean org-level permission is missing; always log a warning and check IAM |
| GCP project state filtering | Scanning all returned projects from `list_projects()` | Filter to `state:ACTIVE` only; `DELETE_REQUESTED` projects return 403 on resource APIs |
| Compute API 403 errors | Treating all 403s as permission denied | Check `error.errors[0]['reason']`: `accessNotConfigured` means API not enabled (expected); `PERMISSION_DENIED` means IAM issue |
| gRPC clients in multiprocessing | Creating clients before `os.fork()` | GCP Python docs: create all clients AFTER fork in child processes; with ThreadPoolExecutor (not multiprocessing), clients can be safely shared |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Creating 7 GCP clients per project instead of sharing | Memory grows 5+ MB per project; 350 clients for 50 projects | Share clients across projects; pass `project=` per API call | ~30-50 projects on WSL (OS file descriptor limits lower than native Linux) |
| `_build_zones_by_region()` called once per `GCPDiscovery` instance | If one instance per project: 50 full zone-list API calls at startup | Call once, cache globally; zones are org-wide | N/A functionally but wastes quota at scale |
| 8 concurrent region workers per project with inner zone loops | rateLimitExceeded 403 errors on projects with many zones | Reduce to 4 workers; implement retry; or use per-project rate limiting | Projects with 10+ zones per region (dense orgs) |
| Checking `if region == self.config.regions[0]` to discover global resources once | In multi-project mode with shared config, first region guard fires independently per project | Track global resource discovery per-project with a project-scoped flag | First multi-project implementation attempt |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Service account JSON key file path in `GOOGLE_APPLICATION_CREDENTIALS` logged at INFO level | Key file path exposed in log files; reveals credential storage location | Log only `type(credentials).__name__` and masked project, not the file path |
| Falling back to ADC silently when service account key fails | User intends SA auth; ADC user credentials used instead with different permission scope | Fail loudly if `GOOGLE_APPLICATION_CREDENTIALS` is set but key is invalid; never silently fall through |
| Storing checkpoint file with project IDs in world-readable location | Project IDs reveal org structure | Write checkpoint to `~/.cache/gcp-discovery/` (user-private) not `./output/` |
| Re-running `gcloud auth application-default login` prompt in tool output | Users may run this in CI logs, exposing that default credentials are being used | Provide specific error message with exact command; log at ERROR not print to stdout |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Credential validation:** `get_gcp_credential()` returns credentials — verify `credentials.refresh(Request())` is called and `RefreshError` is caught before workers start, not just `DefaultCredentialsError` at construction time
- [ ] **Project enumeration:** `search_projects()` returns a list — verify list is non-empty and contains only `state:ACTIVE` projects; log a warning if 0 projects returned
- [ ] **API-not-enabled handling:** Discovery skips a project — verify the log message distinguishes `accessNotConfigured` (normal: API disabled) from `PERMISSION_DENIED` (abnormal: IAM missing)
- [ ] **gRPC client cleanup:** Discovery completes for a project — verify `.transport.close()` is called for each client after each project; check no `ResourceWarning` in verbose mode
- [ ] **Checkpoint resume:** Resume run skips completed projects — verify checkpoint file contains `completed_project_ids` and that enumeration does not re-fetch the full project list (which would re-add completed projects to the queue)
- [ ] **Region list currency:** `get_all_gcp_regions()` returns regions — verify count > 34 (hardcoded fallback has 34; real GCP has 40+); check for `me-central1`, `me-west1`, `africa-south1`
- [ ] **DNS client compatibility:** `_discover_cloud_dns_zones_and_records()` returns zones — verify `google-cloud-dns` version in `pip show google-cloud-dns` and that `dns.Client` (legacy) vs `dns_v1.ManagedZonesClient` (GAPIC) is explicitly chosen and pinned

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| `invalid_grant` credentials on WSL | LOW | Run `gcloud auth application-default login` in WSL (not Windows); verify `$HOME/.config/gcloud/application_default_credentials.json` exists in WSL home |
| 0 projects returned from `search_projects()` | LOW | Grant `roles/viewer` at org level to the credential's identity; verify `gcloud projects list` returns projects in terminal |
| Socket exhaustion from unclosed gRPC clients | MEDIUM | Restart tool with `--no-checkpoint`; reduce `--workers` to 2; fix client lifecycle before next run |
| `rateLimitExceeded` 403 errors on large projects | LOW | Reduce `--workers`; wait 60 seconds (quota refills per minute); resume from checkpoint |
| `accessNotConfigured` blocking entire scan | LOW | This is expected; ensure error is classified correctly and project is skipped with a log entry, not treated as fatal |
| Checkpoint inconsistency (partial project data) | MEDIUM | Delete checkpoint file; re-run from scratch with `--no-checkpoint` |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| `invalid_grant` not caught before workers start | Phase 1: Credential chain fix | Run with expired ADC token; verify clean error message and non-zero exit code, not "Completed successfully!" |
| `check_gcp_credentials()` subprocess validates wrong auth path | Phase 1: Credential chain fix | Remove subprocess check; verify no `gcloud` subprocess calls remain in credential path |
| 0 projects from `search_projects()` without error | Phase 1: Project enumeration | Run without org-level IAM; verify warning message; run with org-level IAM; verify project count > 0 |
| Bare `except Exception` swallowing auth failures | Phase 1: Error propagation | Run with deliberately invalid credentials; verify non-zero exit code on first API call |
| `accessNotConfigured` treated as auth error | Phase 1: Error classification | Test against a project with Compute API disabled; verify "API not enabled" log entry, not permission error |
| Per-project client proliferation (socket exhaustion) | Phase 2: Client lifecycle | Run 50-project scan; verify no `ResourceWarning`; check memory is stable after 25 projects |
| Compute API rate limits hit during multi-project scan | Phase 2: Visible retry policy | Verify `ResourceExhausted` and `rateLimitExceeded` both trigger retry with backoff |
| Shared VPC subnet double-counting | Phase 2: Multi-project correctness | Run against an org with Shared VPC; verify subnets counted once at host project level |
| Per-region checkpoint instead of per-project | Phase 3: Checkpoint/resume | Crash mid-project; verify resume starts project from scratch, not from mid-region |
| Hardcoded region list missing new GCP regions | Phase 1: Foundation | Verify `get_all_gcp_regions()` returns > 34 regions for a project with Compute API enabled |

---

## Sources

- [How Application Default Credentials works — official GCP documentation](https://docs.cloud.google.com/docs/authentication/application-default-credentials) — HIGH confidence
- [Troubleshoot your ADC setup — official GCP documentation](https://cloud.google.com/docs/authentication/troubleshoot-adc) — HIGH confidence
- [google.auth.exceptions.RefreshError invalid_grant — googleapis/python-storage issue #341](https://github.com/googleapis/python-storage/issues/341) — HIGH confidence (confirmed root cause is expired/revoked refresh token in ADC file)
- [Is the Python client library thread safe when using gRPC? — googleapis/google-cloud-python issue #3272](https://github.com/googleapis/google-cloud-python/issues/3272) — HIGH confidence (Google contributor confirmed: gRPC clients are thread-safe; 4 threads per client instance)
- [Python client libraries — multiprocessing restrictions — official GCP documentation](https://docs.cloud.google.com/python/docs/reference/automl/latest/multiprocessing) — HIGH confidence (create clients after fork, not before)
- [Listing all projects and folders in your hierarchy — Resource Manager documentation](https://docs.cloud.google.com/resource-manager/docs/listing-all-resources) — HIGH confidence (org-level permissions required; recursive traversal needed for folders)
- [Resource Manager roles and permissions — IAM documentation](https://docs.cloud.google.com/iam/docs/roles-permissions/resourcemanager) — HIGH confidence
- [Creating and managing projects — lifecycleState field](https://cloud.google.com/resource-manager/docs/creating-managing-projects) — HIGH confidence (DELETE_REQUESTED projects remain visible in list_projects for 30 days)
- [Compute Engine rate quotas — official documentation](https://docs.cloud.google.com/compute/api-quota) — HIGH confidence (per-project quota; 403 with rateLimitExceeded reason)
- [Shared VPC — official documentation](https://cloud.google.com/vpc/docs/shared-vpc) — HIGH confidence (subnets owned by host project only)
- [Create a zone with cross-project binding — Cloud DNS documentation](https://docs.cloud.google.com/dns/docs/zones/cross-project-binding) — HIGH confidence (DNS peering is unidirectional; cross-project binding requires dns.peer role)
- [gRPC Python documentation — channel lifecycle](https://grpc.github.io/grpc/python/grpc.html) — MEDIUM confidence (no guarantee memory is the only resource consumed; file descriptors may leak without explicit close)
- [google.api_core.exceptions — exceptions reference](https://googleapis.dev/python/google-api-core/latest/exceptions.html) — HIGH confidence (ResourceExhausted maps to 429; PermissionDenied maps to 403)

---
*Pitfalls research for: GCP multi-project discovery — credential hardening, concurrent execution, project enumeration*
*Researched: 2026-02-19*
