# Stack Research

**Domain:** GCP multi-project credential hardening and enumeration for concurrent discovery
**Researched:** 2026-02-19
**Confidence:** HIGH for library versions and retry API; MEDIUM for thread-safety details (library docs incomplete, augmented by GitHub issues)

---

## What This Research Covers

This is an **addendum** to the existing Azure stack research. It covers only what is NEW for the GCP v1.1 milestone. The existing `google-cloud-compute>=1.12.0`, `google-cloud-dns==0.35.1`, and `google-auth>=2.17.0` entries remain — this research determines what to add and what minimum versions to enforce.

---

## The Core Problem, Stated Precisely

`google.auth.default()` calls `credentials.refresh()` lazily — the first API call refreshes the token. In `gcp_discovery.py`, the credential is obtained in `_init_gcp_clients()`, and each worker thread then calls an API. With multiple concurrent threads sharing the same credential object, all threads may simultaneously attempt token refresh, triggering the known `google.auth.exceptions.RefreshError: Internal Failure` (documented in google-auth-library-python issue #246). The library maintainer confirmed: *"We don't go out of our way to ensure thread safety but the worst case scenario is that the credentials get refreshed multiple times within a second."* The fix is to call `credentials.refresh()` on the main thread BEFORE workers spawn — identical to the Azure pattern of calling `get_token()` before `ThreadPoolExecutor`.

`google.auth.default()` also returns expired user credentials when the ADC token from `gcloud auth application-default login` has aged past its 1-hour access token lifetime AND the refresh token is invalid (e.g., session control policy `invalid_grant`). The fix is to call `credentials.refresh()` immediately after `default()`, catch `google.auth.exceptions.RefreshError`, and fail-fast with a human-readable message instead of propagating errors into every worker thread.

---

## New Dependencies

### Required New Additions

| Package | Version | Purpose | Why This Version |
|---------|---------|---------|-----------------|
| `google-cloud-resource-manager` | `>=1.16.0` | Enumerate all projects in a GCP org via `resourcemanager_v3.ProjectsClient` and `FoldersClient` | 1.16.0 released 2026-01-15; current stable. v3 API is the only supported surface — v1/v2 REST endpoints exist but the Python client library exposes only v3. |
| `google-api-core` | `>=2.15.0` | `google.api_core.retry.Retry` for visible retry with on-error callback | Transitively installed by all `google-cloud-*` packages. Making it explicit ensures the `Retry` class with `on_error` parameter is available. |

### Existing Packages — Version Adjustments

| Package | Current Constraint | New Constraint | Reason |
|---------|-------------------|----------------|--------|
| `google-auth` | `>=2.17.0` | `>=2.23.0` | 2.23.0 introduced thread-safety improvements; pre-2.23 had documented `RefreshError` races under concurrent load (google-auth-library-python issues #246, #690). |
| `google-cloud-compute` | `>=1.12.0` | `>=1.12.0` | No change needed. Current 3.x series passes `retry` parameter at call level. |
| `google-cloud-dns` | `==0.35.1` | `==0.35.1` | No change. DNS client is pinned; do not unpin without testing. |

### No New Dependencies For

- **Token cache persistence**: GCP service account credentials (JSON key) and ADC do not require a separate cache library. The `service_account.Credentials` class manages token refresh internally. Unlike Azure's `TokenCachePersistenceOptions`, there is no cross-session token cache for GCP service accounts — each run gets a fresh short-lived access token via JWT assertion. For ADC/user credentials, `~/.config/gcloud/application_default_credentials.json` IS the persistent cache managed by the gcloud SDK.
- **Interactive browser auth**: The tool targets service account JSON keys and ADC. There is no GCP equivalent of `InteractiveBrowserCredential`. Users authenticate via `gcloud auth application-default login` (browser-based) outside the tool, which writes to the ADC file that `google.auth.default()` reads. Do NOT add `google-auth-oauthlib` or `InstalledAppFlow` — that flow is for apps requesting user consent, not for admin tooling.

---

## Credential Architecture

### Recommended Credential Chain

Replace `get_gcp_credential()` in `config.py` with a singleton that follows the Azure pattern:

**Priority order:**

1. **Service Account JSON** (env var `GOOGLE_APPLICATION_CREDENTIALS` or `GCP_SERVICE_ACCOUNT_KEY`) — non-interactive, thread-safe, no expiry race. `google.oauth2.service_account.Credentials` handles token refresh via JWT assertion internally. Best for automated/CI runs.

2. **Application Default Credentials** (ADC from `gcloud auth application-default login`) — for interactive user runs. `google.auth.default()` returns these when no service account is configured. Must be refreshed on main thread before workers spawn.

**Both paths** must:
- Call `credentials.refresh(google.auth.transport.requests.Request())` immediately after obtaining credentials
- Catch `google.auth.exceptions.RefreshError` and exit with an actionable message
- Store the credential in a module-level singleton protected by `threading.Lock()` (double-checked locking, same pattern as Azure `get_azure_credential()`)

### Credential Classes

| Class | Package | When To Use | Thread-Safe |
|-------|---------|-------------|------------|
| `google.oauth2.service_account.Credentials` | `google-auth` | `GOOGLE_APPLICATION_CREDENTIALS` points to a service account JSON key | YES — each token refresh is a self-contained JWT assertion; no shared state issues under concurrent calls AFTER initial warmup |
| `google.auth.default()` (returns various) | `google-auth` | ADC path (user ran `gcloud auth application-default login`) | Conditional — safe after pre-refresh on main thread; not safe for first refresh under concurrent calls |
| `google.auth.transport.requests.Request` | `google-auth[requests]` | Transport object required by `credentials.refresh()` | Instantiate once per refresh call |

**Do NOT use:**
- `google.auth.default()` with lazy refresh from worker threads — causes `RefreshError: Internal Failure` under concurrency
- Per-project credential objects — defeats singleton pattern; each instance makes its own token refresh request

### Pre-Warm Pattern (Direct Analog of Azure `get_token()` Warmup)

```python
import threading
import google.auth
import google.auth.transport.requests
import google.oauth2.service_account
from google.auth.exceptions import RefreshError, DefaultCredentialsError

_credential_cache = None
_credential_lock = threading.Lock()

def get_gcp_credential():
    """
    Returns a singleton credential pre-warmed on the calling thread.
    Safe to share across ThreadPoolExecutor workers.

    Call this from the main thread before spawning workers.
    """
    global _credential_cache

    if _credential_cache is not None:
        return _credential_cache

    with _credential_lock:
        if _credential_cache is not None:
            return _credential_cache

        cred = _build_and_warm_credential()
        _credential_cache = cred
        return _credential_cache


def _build_and_warm_credential():
    """Build credential, refresh it immediately, fail-fast on auth errors."""
    import os

    # Path 1: Service account JSON key
    sa_key = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GCP_SERVICE_ACCOUNT_KEY")
    if sa_key:
        try:
            cred = google.oauth2.service_account.Credentials.from_service_account_file(
                sa_key,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            cred.refresh(google.auth.transport.requests.Request())
            print(f"[Auth] Using service account: {cred.service_account_email}")
            return cred
        except RefreshError as e:
            raise SystemExit(
                f"[Auth] Service account credentials failed: {e}\n"
                "Check that GOOGLE_APPLICATION_CREDENTIALS points to a valid key file."
            ) from e

    # Path 2: Application Default Credentials
    try:
        cred, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    except DefaultCredentialsError as e:
        raise SystemExit(
            f"[Auth] No GCP credentials found: {e}\n"
            "Run: gcloud auth application-default login\n"
            "Or set: GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json"
        ) from e

    try:
        cred.refresh(google.auth.transport.requests.Request())
        print(f"[Auth] Using Application Default Credentials (project: {project})")
        return cred
    except RefreshError as e:
        raise SystemExit(
            f"[Auth] GCP credentials expired or invalid: {e}\n"
            "Run: gcloud auth application-default login\n"
            "If error is 'invalid_grant', your session has expired."
        ) from e
```

---

## Project Enumeration

### Library

`google-cloud-resource-manager>=1.16.0` — installs `resourcemanager_v3` module.

```bash
pip install "google-cloud-resource-manager>=1.16.0"
```

### API

Use `resourcemanager_v3.ProjectsClient` with `search_projects()`. This is simpler than the `list_projects()` + recursive folder traversal approach — `search_projects()` returns all projects the credential has `resourcemanager.projects.get` permission on, across the full hierarchy, in a single paginated call.

**Trade-off:** `search_projects()` is eventually consistent — may miss projects created in the last few seconds. For a discovery tool running against customer environments (not real-time), this is acceptable. The `list_projects()` + recursive folder approach provides strong consistency but requires `roles/resourcemanager.folderViewer` and more code.

```python
from google.cloud import resourcemanager_v3

def get_all_project_ids(credentials) -> list[str]:
    """
    Return all project IDs visible to the credential.

    Uses search_projects() for simplicity — returns all projects
    the credential has resourcemanager.projects.get on.

    For orgs using folder nesting, search_projects covers nested
    projects without recursive traversal. Eventual consistency is
    acceptable for discovery tooling.

    Required IAM: roles/viewer or roles/browser on the org,
    or roles/resourcemanager.projectViewer on each project.
    """
    client = resourcemanager_v3.ProjectsClient(credentials=credentials)
    request = resourcemanager_v3.SearchProjectsRequest()
    # Empty query = all accessible projects
    projects = []
    for project in client.search_projects(request=request):
        if project.state == resourcemanager_v3.Project.State.ACTIVE:
            projects.append(project.project_id)
    return projects
```

**For org-scoped enumeration** (when org ID is known, e.g., from env var `GCP_ORGANIZATION_ID`):

```python
request = resourcemanager_v3.SearchProjectsRequest(
    query=f"parent:organizations/{org_id}"
)
```

### Required IAM Roles

| Scenario | Required IAM |
|----------|-------------|
| List all projects in org | `roles/browser` or `roles/resourcemanager.projectViewer` at org level |
| List projects in a folder | `roles/resourcemanager.folderViewer` |
| Service account key | Grant above roles to the service account's email |

---

## Retry Policy

### Mechanism

GCP Python client libraries use `google.api_core.retry.Retry`, passed as the `retry` parameter to individual method calls. This is different from Azure's approach of subclassing `RetryPolicy` — there is no `RetryPolicy` class to subclass. The closest equivalent to Azure's `VisibleRetryPolicy` is a `Retry` object with an `on_error` callback.

**Note:** The Azure pattern of subclassing `RetryPolicy` and overriding `sleep()` does NOT apply to GCP. The GCP equivalent is composing a `Retry` object with an `on_error` function.

### What GCP Retries by Default

The `if_transient_error` predicate (the default) retries:
- `InternalServerError` (HTTP 500)
- `TooManyRequests` (HTTP 429)
- `ServiceUnavailable` (HTTP 503)
- `ResourceExhausted` (gRPC RESOURCE_EXHAUSTED — quota exceeded)

This means 429 quota errors ARE retried by default. The problem is these retries are silent. To make them visible (matching Azure's `VisibleRetryPolicy` behavior):

```python
from google.api_core import retry as api_retry
from google.api_core import exceptions as api_exceptions
import logging
import time

logger = logging.getLogger(__name__)

def _log_gcp_retry(exc):
    """on_error callback — called before each retry sleep."""
    if isinstance(exc, api_exceptions.ResourceExhausted):
        logger.warning(f"[Retry] GCP quota/rate limit hit: {exc}. Retrying with backoff...")
    elif isinstance(exc, api_exceptions.ServiceUnavailable):
        logger.warning(f"[Retry] GCP service unavailable: {exc}. Retrying...")
    else:
        logger.debug(f"[Retry] GCP transient error: {exc}. Retrying...")

GCP_RETRY = api_retry.Retry(
    predicate=api_retry.if_transient_error,
    initial=1.0,        # 1 second initial delay
    maximum=60.0,       # cap at 60 seconds
    multiplier=2.0,     # exponential backoff
    timeout=300.0,      # total retry budget: 5 minutes
    on_error=_log_gcp_retry,
)
```

**Usage** — pass at the call site, not at the client constructor:

```python
# On each API call that may hit quota
instances = compute_client.list(request=request, retry=GCP_RETRY)
projects = projects_client.search_projects(request=request, retry=GCP_RETRY)
```

**Why call-level, not client-level:** The `retry` parameter is not supported at client construction time for all GCP client types. Call-level is universally supported across compute, DNS, and resource manager clients.

### No Retry-After Header Equivalent

GCP does not return a `Retry-After` header. The exponential backoff in `google.api_core.retry.Retry` is the correct pattern. The Azure `VisibleRetryPolicy` that honors `Retry-After` has no direct GCP equivalent — use `Retry` with exponential backoff instead.

---

## Per-Project Client Lifecycle

Follow the Azure per-subscription lifecycle pattern. Create client instances inside the project worker function, not at module level. Close them after the project completes.

```python
from google.cloud import compute_v1, dns

def discover_project(project_id: str, credentials) -> list[dict]:
    """
    Discover resources in a single GCP project.
    Creates clients for this project, closes them on completion.
    Mirrors Azure's per-subscription with-block pattern.
    """
    compute_client = compute_v1.InstancesClient(credentials=credentials)
    networks_client = compute_v1.NetworksClient(credentials=credentials)
    # ... etc

    try:
        results = []
        # ... discovery logic using project_id
        return results
    finally:
        # GCP clients don't implement __exit__ but do have close()
        # transport layer holds HTTP connections; explicit close bounds sockets
        compute_client.transport.close()
        networks_client.transport.close()
```

**Why:** Each `InstancesClient` holds an HTTP/2 (gRPC) connection pool. Without explicit close, connections persist for the lifetime of the process. With N projects running in parallel workers, this means N connection pools open simultaneously. Explicit `transport.close()` bounds socket usage.

---

## Installation

Update `requirements.txt` and `gcp_discovery/requirements.txt`:

```bash
# New — project enumeration
pip install "google-cloud-resource-manager>=1.16.0"

# Updated minimum — thread-safe token refresh
pip install "google-auth>=2.23.0"

# No change needed — already installed transitively, but make explicit
pip install "google-api-core>=2.15.0"
```

In `requirements.txt`:

```
# GCP Dependencies (updated for v1.1)
google-cloud-compute>=1.12.0
google-cloud-dns==0.35.1
google-cloud-resource-manager>=1.16.0   # NEW — project enumeration
google-auth>=2.23.0                     # UPDATED — was >=2.17.0; thread-safety improvements
google-api-core>=2.15.0                 # NEW explicit — Retry.on_error available
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `search_projects()` for project enumeration | `list_projects()` + recursive `list_folders()` | Use `list_projects()` when strong consistency is required (e.g., projects created within the last minute must appear). Requires `roles/resourcemanager.folderViewer` and significantly more code. |
| `google.oauth2.service_account.Credentials.from_service_account_file()` | `google.auth.default()` with `GOOGLE_APPLICATION_CREDENTIALS` pointing to SA key | Both work identically when `GOOGLE_APPLICATION_CREDENTIALS` is a SA JSON file — `google.auth.default()` calls `from_service_account_file` internally. Explicit `from_service_account_file` is clearer about intent. |
| `google.api_core.retry.Retry` with `on_error` callback | Subclassing `Retry` | Subclassing is unnecessary — `on_error` callback achieves visibility without inheritance. GCP SDK retry mechanism is not plugged into a client-level policy object like Azure's `RetryPolicy`. |
| `google.auth.transport.requests.Request()` for manual refresh | `google.auth.transport.urllib3.Request()` | Both work. `requests` transport is the default and more commonly tested. `urllib3` transport is available but not needed unless you have a specific `urllib3` session to reuse. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `google.auth.default()` with lazy refresh from worker threads | First token refresh under concurrent load causes `RefreshError: Internal Failure` (documented race condition in google-auth-library-python issue #246). The library does not guarantee thread-safe first refresh. | Call `credentials.refresh(Request())` on main thread before `ThreadPoolExecutor` spawns. |
| `gcloud auth list` subprocess check as credential validation | Only checks if a CLI account is marked active — does not test whether the API token is valid or expired. The existing `check_gcp_credentials()` function passes even when `invalid_grant` errors occur on actual API calls. | Call `credentials.refresh()` and catch `RefreshError`. |
| Per-project credential instances | Defeats singleton. Each `service_account.Credentials` instance has its own token, causing N separate JWT assertion requests (one per project) instead of reusing a shared short-lived access token. | Single credential singleton passed to all project workers. |
| `google-auth-oauthlib` / `InstalledAppFlow` for interactive auth | This flow is for apps requesting user consent (Gmail, Sheets, etc). It opens a browser and requests a user-facing OAuth scope — inappropriate for admin/infrastructure tooling. Requires OAuth client ID registration in the GCP project. | Users authenticate via `gcloud auth application-default login` outside the tool. |
| `tenacity` for retry | Adds an external dependency duplicating what `google.api_core.retry.Retry` already provides natively. `google.api_core.retry` is already transitively installed via `google-cloud-compute`. | `google.api_core.retry.Retry` with `on_error` callback. |
| Creating `ResourceManagerClient` from the old v1 API surface | The `google.cloud.resourcemanager` package (non-v3) is unmaintained. v3 is the only supported Python API surface. | `google.cloud.resourcemanager_v3.ProjectsClient`. |

---

## Stack Patterns by Scenario

**If the user has a service account JSON key:**
- Set `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json` (or `GCP_SERVICE_ACCOUNT_KEY`)
- `service_account.Credentials.from_service_account_file()` + immediate `refresh()`
- Fully non-interactive, correct for CI/CD and automated customer runs
- The service account needs `roles/browser` (or `roles/viewer`) on the org, and `roles/compute.viewer` + `roles/dns.reader` on projects

**If the user has run `gcloud auth application-default login`:**
- `google.auth.default()` picks up `~/.config/gcloud/application_default_credentials.json`
- Same credential object, same singleton pattern
- Refresh on main thread to fail-fast on `invalid_grant`
- Correct for interactive Sales Engineer runs on dev machines

**If scanning a single project (backward compatibility):**
- Skip project enumeration; use `GCP_PROJECT_ID` env var or gcloud config
- Same credential singleton pattern applies
- Resource enumeration loop over `[project_id]` instead of discovered list

**If scanning an entire GCP org:**
- Set `GCP_ORGANIZATION_ID` env var
- `search_projects(query=f"parent:organizations/{org_id}")` returns all projects
- ThreadPoolExecutor over project list — same structure as Azure subscription loop

---

## Thread Safety Reference

| Item | Thread-Safe | Notes |
|------|------------|-------|
| `service_account.Credentials` (after pre-refresh) | YES | JWT assertion is stateless per-call; access token shared safely after warmup |
| `google.auth.default()` returned credentials (after pre-refresh) | YES (conditional) | Safe after `refresh()` on main thread; concurrent first-refresh is not safe |
| `google.auth.transport.requests.Request()` | NO — create per-call | Not thread-safe; instantiate in the calling thread only |
| `compute_v1.InstancesClient` | NO — create per project worker | Not documented as thread-safe; shares gRPC channel |
| `resourcemanager_v3.ProjectsClient` | NO — create for enumeration only, then discard | Same pattern |
| `google.api_core.retry.Retry` instance | YES — shareable | Pure configuration object; stateless |

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `google-cloud-resource-manager>=1.16.0` | `google-auth>=2.23.0`, `google-api-core>=2.15.0` | v3 API requires `google-api-core>=1.32.0`; >=2.15 is safe upper bound |
| `google-auth>=2.23.0` | `google-cloud-compute>=1.12.0`, `google-cloud-dns==0.35.1` | All google-cloud-* packages use `google-auth` via `google-api-core`; no conflicts |
| `google-api-core>=2.15.0` | Python 3.7–3.13 | `Retry.on_error` parameter exists since google-api-core 1.x; 2.15 ensures modern `timeout` parameter (not deprecated `deadline`) |
| `google-cloud-compute>=1.12.0` | `google-cloud-resource-manager>=1.16.0` | No direct dependency; both use `google-auth` and `google-api-core` transitively; compatible |

---

## Sources

- [google-cloud-resource-manager on PyPI](https://pypi.org/project/google-cloud-resource-manager/) — version 1.16.0 current as of 2026-01-15 (HIGH confidence)
- [resourcemanager_v3 Python client docs](https://docs.cloud.google.com/python/docs/reference/cloudresourcemanager/latest/google.cloud.resourcemanager_v3.services.projects.ProjectsClient) — `list_projects()` and `search_projects()` signatures (HIGH confidence)
- [Listing all projects and folders](https://docs.cloud.google.com/resource-manager/docs/listing-all-resources) — official Google docs on hierarchy traversal (HIGH confidence)
- [google-auth User Guide](https://googleapis.dev/python/google-auth/latest/user-guide.html) — `google.auth.default()` priority chain, service account usage (HIGH confidence)
- [google.oauth2.service_account docs](https://googleapis.dev/python/google-auth/latest/reference/google.oauth2.service_account.html) — `Credentials.from_service_account_file()`, `refresh()` (HIGH confidence)
- [google.api_core.retry docs](https://googleapis.dev/python/google-api-core/latest/retry.html) — `Retry` class, `on_error` callback, `if_transient_error` predicate (HIGH confidence)
- [google-auth-library-python issue #246](https://github.com/googleapis/google-auth-library-python/issues/246) — concurrent `RefreshError: Internal Failure` root cause and `pre-refresh` workaround confirmed by maintainer (HIGH confidence)
- [google-api-python-client thread safety docs](https://googleapis.github.io/google-api-python-client/docs/thread_safety.html) — HTTP client NOT thread-safe; credential object thread-safety not guaranteed for first refresh (MEDIUM confidence — incomplete documentation)
- [Retry for Google Cloud Client (jdhao, 2024-10-08)](https://jdhao.github.io/2024/10/08/gcloud_client_retry/) — call-level `retry=` pattern verified (MEDIUM confidence — community source, matches official API)

---

*Stack research for: GCP multi-project discovery credential hardening, project enumeration, retry policy*
*Researched: 2026-02-19*
