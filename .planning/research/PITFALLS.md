# Pitfalls Research

**Domain:** Multi-cloud resource discovery & UDDI licensing estimation (AWS, Azure, GCP)
**Researched:** 2026-02-23
**Confidence:** HIGH (based on existing codebase analysis + cloud SDK documentation + community issue trackers)

## Critical Pitfalls

### Pitfall 1: Auth Token Expiry Mid-Scan Silently Breaks Discovery

**What goes wrong:**
SSO tokens and OAuth access tokens expire during long-running scans (30-120 minutes for 100+ accounts). AWS SSO tokens expire after ~4 hours with no automatic re-authentication. Azure InteractiveBrowserCredential access tokens expire in ~1 hour; refresh token usage is not guaranteed. GCP ADC user credentials expire and `RefreshError` surfaces mid-enumeration. When a token expires partway through, some accounts/subscriptions complete successfully while others fail with auth errors. The user gets partial results that look complete but are missing data from failed accounts.

**Why it happens:**
The current codebase caches credentials as module-level singletons (`_credential_cache` in `azure_discovery/config.py:26`, `_gcp_credential_cache` in `gcp_discovery/config.py:23`) with no TTL check or refresh mechanism. Credential validation happens once at startup (`validate_azure_credentials()`, `_build_gcp_credential()`), but tokens can expire before all accounts are scanned. AWS SSO cannot refresh silently because it may require interactive browser authorization. The credential singleton pattern means stale tokens are reused across all worker threads without re-validation.

**How to avoid:**
- Add a credential wrapper that checks token expiry time before each API call batch (per-account/subscription boundary, not per-request).
- For AWS SSO: read the `expiresAt` field from the SSO token cache file (`~/.aws/sso/cache/`) and warn users before scan start if the remaining token lifetime is less than estimated scan duration.
- For Azure: enable `TokenCachePersistenceOptions` (already partially done) and set up `AuthenticationRecord` serialization so refresh tokens can be used without re-prompting.
- For GCP: call `credentials.refresh(Request())` at the start of each project's discovery, not just once globally.
- Add a pre-scan estimate: "Estimated scan time: ~45 min. Your token expires in 20 min. Run `aws sso login` / `az login` first."

**Warning signs:**
- Scans that succeed for the first N accounts/subscriptions but fail for later ones with auth errors.
- Error messages containing "Token has expired and refresh failed" (AWS), "ClientAuthenticationError" (Azure), or "RefreshError" (GCP).
- The `errors` list in checkpoint data growing with auth-related failures in later subscriptions.

**Phase to address:**
Phase 1 (Core auth/config). This must be solved before any multi-account discovery code runs. The credential layer is the foundation everything else depends on.

---

### Pitfall 2: Azure ARM Tenant-Level Rate Limiting Causes Cascading 429 Failures

**What goes wrong:**
Azure Resource Manager enforces tenant-level rate limits of 25 reads/second (burst up to 250). With 4 concurrent subscription workers, each making ~50 API calls per subscription (VMs, VNets, DNS, subnets, load balancers, NICs, etc.), the tool easily exceeds 200 requests per subscription scan cycle. Once 429 responses begin, the fixed retry intervals (currently 2s, 4s, 8s in `VisibleRetryPolicy`) cause a thundering herd: all workers retry simultaneously at the same offsets, triggering more 429s. In large tenants (200+ subscriptions), this can stall the entire scan for minutes or cause cascading timeouts.

**Why it happens:**
ARM throttling is per-tenant, not per-subscription. The current code (`azure_discovery/discover.py:296-308`) spawns concurrent subscription workers that all share the same tenant-level quota pool. The retry policy uses fixed backoff without jitter (`azure_discovery/azure_discovery.py:35-76`). The `--subscription-workers 4` default was chosen for throughput without modeling the tenant-level ceiling. The code does not read `Retry-After` headers or `x-ms-ratelimit-remaining-tenant-reads` response headers to adapt pace.

**How to avoid:**
- Default `--subscription-workers` to 2 for tenants with 100+ subscriptions; auto-reduce to 1 for 500+.
- Implement exponential backoff with full jitter (not just jitter on fixed intervals). Formula: `sleep = random(0, min(cap, base * 2^attempt))`.
- Read `Retry-After` and `x-ms-ratelimit-remaining-tenant-reads` headers from every response. When remaining reads drops below 20%, voluntarily pause all workers for the specified retry-after duration.
- Implement a shared tenant-level semaphore across all subscription workers: a single `threading.Semaphore` that limits total concurrent ARM requests to ~15/second (leaving headroom).
- Within each subscription, parallelize resource type discovery (VMs, VNets, DNS zones in parallel threads) but gate total request volume through the shared semaphore.

**Warning signs:**
- `429 Too Many Requests` in logs or error output.
- Scans that take 10x longer than expected for large tenants.
- Multiple subscriptions failing simultaneously with the same error.
- The `[Warning]` at line 211-217 of `azure_discovery/discover.py` triggering (200+ subscriptions with workers > 2).

**Phase to address:**
Phase 2 (Provider discovery implementation). Must be baked into the Azure discovery module before any enterprise testing. Impossible to retrofit cleanly after the discovery loop is built.

---

### Pitfall 3: GCP API Quota Exhaustion Across Multi-Project Scanning

**What goes wrong:**
GCP Compute Engine rate quotas are per-project but the tool scans many projects with shared credentials. The `compute.instances.list` and `compute.zones.list` calls have daily quotas (default: 20,000 reads/day for compute API). With 100+ projects, each with ~40 regions, scanning all resource types generates ~100 API calls per project. At 200 projects, that is 20,000 API calls -- right at the daily quota limit. Organizations with 500+ projects will exceed quota within the first scan, and the tool will start receiving `403 rateLimitExceeded` errors mid-scan.

**Why it happens:**
The current code (`gcp_discovery/discover.py:158-189`) uses a ThreadPoolExecutor with up to 4 project workers. Each worker creates API calls for instances, networks, subnetworks, addresses, and DNS zones across all regions. GCP rate quotas apply to the *quota project* (the project associated with the credential), not the target project. So all API calls from all project workers consume quota from a single quota project. The shared compute clients (`gcp_discovery/discover.py:113-120`) amplify this: requests from all workers go through the same client with the same quota project billing.

**How to avoid:**
- Track API calls per quota-project. Before each batch, check `X-Goog-User-Project` or quota headers.
- Implement a per-API-endpoint rate limiter (e.g., `aiolimiter` or a simple token bucket) set to ~80% of the known quota limit.
- Support `--quota-project` flag to let users specify a dedicated quota project with elevated limits.
- For very large orgs (500+ projects): implement batched scanning with configurable concurrency, scan in waves of 50 projects at a time, wait for quota reset if needed.
- Pre-check quota with `gcloud compute project-info describe --project=QUOTA_PROJECT` and warn if remaining daily quota is insufficient.
- Consider using `aggregatedList` API calls (single call returns resources across all zones/regions) instead of per-region listing, which cuts API calls by 40x per resource type.

**Warning signs:**
- `403 rateLimitExceeded` or `429` errors appearing after scanning the first ~50-100 projects.
- Scans that succeed for small organizations but fail for large ones.
- GCP discovery taking orders of magnitude longer than AWS or Azure for similar-sized environments.
- `FAILED` entries in project scan output concentrated in the second half of the project list.

**Phase to address:**
Phase 2 (Provider discovery implementation). Must be designed into the GCP discovery architecture before the multi-project scanning loop is built.

---

### Pitfall 4: Signal Handler State Loss and Checkpoint Data Corruption

**What goes wrong:**
When a user presses Ctrl+C during a long-running scan, the signal handler (`azure_discovery/discover.py:111-115`) prints "saving checkpoint and exiting" but does not actually save the checkpoint because it has no access to the accumulated state (`all_native_objects`, `scanned_subs`, etc.). All progress from partially-completed scans is lost. Worse: if the signal arrives while `save_checkpoint()` is mid-write (between `open()` and `os.rename()` at lines 72-75), the temp file may exist but the final checkpoint file is either stale or missing, corrupting the resume path.

**Why it happens:**
The signal handler is defined as a module-level function that cannot access the local variables in `main()`. Python signal handlers run in the main thread and can interrupt any operation, including file I/O. The checkpoint write is not atomic relative to signals: `json.dump()` to a temp file followed by `os.rename()` is safe against crashes but not against mid-write signal interrupts where the temp file is partially written. The checkpoint format is not versioned (`azure_discovery/discover.py:60-78`), so schema changes between tool versions will silently corrupt checkpoint loading.

**How to avoid:**
- Use a closure or class-based signal handler that captures mutable state (e.g., `signal.signal(signal.SIGINT, lambda s, f: save_and_exit(state))` where `state` is a dict reference).
- Use `try/finally` blocks around the main discovery loop to guarantee checkpoint save on any exit path (normal, exception, signal).
- Add checkpoint format versioning: include `"schema_version": 1` in the JSON. On load, validate version and apply migration logic for older formats.
- Use `threading.Event` for graceful shutdown instead of `sys.exit()` in the signal handler. Set the event, let workers drain, then save state.
- Write checkpoints atomically: write to temp file, `fsync()`, then `os.rename()`. This prevents partial writes from being visible.

**Warning signs:**
- Users report "checkpoint saved" message but resume finds no checkpoint or stale data.
- Checkpoint file exists but `load_checkpoint()` returns `None` with "corrupted or incompatible" message.
- After tool upgrade, old checkpoints cause `KeyError` on load.
- Users lose 30+ minutes of scan progress after Ctrl+C.

**Phase to address:**
Phase 2 (Provider discovery -- Azure module). But the pattern should be established in Phase 1 as a shared checkpoint/state management abstraction used by all providers.

---

### Pitfall 5: Memory Exhaustion from In-Memory Resource Aggregation at Scale

**What goes wrong:**
All discovered resources are accumulated in a single Python list (`all_native_objects`) in memory before being written to disk. Each resource dict contains `resource_id`, `resource_type`, `region`, `name`, `state`, `tags`, `details` (raw API response), and `discovered_at`. For a large enterprise with 100+ accounts and millions of cloud resources, this list grows to 1GB+ of RAM. On machines with 4-8GB RAM (common customer laptops running other workloads), this causes the Python process to be OOM-killed or swap-thrash to the point of unusability.

**Why it happens:**
The current architecture (`gcp_discovery/discover.py:125,169`, `azure_discovery/discover.py:228,304`) extends a shared list from each worker thread. The `details` field in each resource contains the full API response (including nested objects, metadata, tags), which bloats memory significantly. The licensing calculator (`shared/licensing_calculator.py`) then iterates over the entire list again, doubling peak memory. Checkpoint saving serializes the entire list to JSON, adding a third copy in memory during `json.dump()`.

**How to avoid:**
- Implement streaming output: write resources to a temporary SQLite database or append-only CSV as each account/subscription completes, rather than accumulating in memory.
- Strip raw API response from the `details` field after extracting the needed fields (IPs, tags, name, state). Keep only licensing-relevant fields in memory.
- Use generators/iterators where possible instead of list accumulation.
- For checkpoint serialization, use `json.dump()` with a file handle (stream to disk) rather than `json.dumps()` (string in memory).
- Add a memory usage monitor: `psutil.Process().memory_info().rss` checked after each account completes. Warn if exceeding 70% of available RAM.
- Set a hard memory limit with `resource.setrlimit()` on Linux/macOS to fail gracefully rather than OOM-killing.

**Warning signs:**
- Python process memory growing linearly with number of accounts/projects scanned.
- System becoming unresponsive during large scans (swap thrashing).
- `MemoryError` exceptions or process killed by OS (exit code 137 on Linux).
- Checkpoint save taking >30 seconds (sign the data is very large).

**Phase to address:**
Phase 2 (Provider discovery implementation). The output/storage architecture must be designed for streaming from the start. Retrofitting streaming into a list-accumulation architecture requires rewriting the entire data pipeline.

---

### Pitfall 6: Broad Exception Handling Masks Actionable Errors

**What goes wrong:**
Catching `except Exception as e` everywhere (60+ instances in the current codebase per `CONCERNS.md`) makes it impossible for users or support to distinguish between: (a) transient network errors (retry will fix), (b) permission errors (wrong IAM role, will never succeed), (c) API throttling (back off and retry), (d) missing API enablement (enable the API first), and (e) genuine bugs in the tool. Users see "FAILED -- <opaque error string>" and cannot determine the correct remediation. They retry the entire scan when they should have fixed a permission issue first. Or they give up when a transient error would have resolved itself.

**Why it happens:**
Developers use `except Exception` as a safety net to prevent crashes during demo/pre-sales situations. The original codebase was written for single-account use where errors were rare. At 100+ accounts, every edge case in every API eventually manifests. Exception types from cloud SDKs are spread across multiple packages (`botocore.exceptions`, `azure.core.exceptions`, `google.api_core.exceptions`), making it tedious to catch them all specifically.

**How to avoid:**
- Define a provider-agnostic error taxonomy: `ThrottlingError`, `AuthExpiredError`, `PermissionDeniedError`, `ApiDisabledError`, `TransientNetworkError`, `UnexpectedError`.
- Map each cloud SDK's exception types to this taxonomy in a single module per provider (e.g., `aws_discovery/exceptions.py` maps `ClientError` with code `Throttling` to `ThrottlingError`).
- At the discovery loop level, catch by taxonomy class: retry `ThrottlingError` and `TransientNetworkError`, skip+report `PermissionDeniedError` and `ApiDisabledError`, fail+abort on `AuthExpiredError`.
- Log the original exception at DEBUG level for support diagnostics, but present user-facing messages keyed to the taxonomy class (e.g., "Subscription X: permission denied for VMs. Grant the Reader role to continue.").
- Reserve `except Exception` only for the outermost scope (per-account/subscription), never inside per-resource-type enumeration.

**Warning signs:**
- Users reporting "it failed" with no actionable error message.
- Support requests where the only information is a generic traceback.
- Silent data omissions: resources missing from output because an exception was caught and swallowed with `pass`.
- The `errors` list containing the same error string pattern across many accounts (indicates a systemic issue that should have been caught earlier and reported differently).

**Phase to address:**
Phase 1 (Core framework). The error taxonomy and exception mapping must exist before any provider discovery code is written. This is the most impactful structural decision for user experience.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `except Exception: pass` for tag/label extraction | Prevents crashes on missing attributes | Silent data loss; impossible to debug missing tags in output | Never -- use `getattr(obj, 'labels', {})` with default instead |
| Module-level credential singletons without TTL | Simple caching, avoids re-auth prompts | Stale tokens cause mid-scan failures in long runs | Only if TTL validation wrapper added around cache reads |
| Accumulating all resources in a Python list | Simple aggregation, easy JSON serialization | OOM at scale (100K+ resources), checkpoint serialization doubles memory | Only for environments with < 10 accounts and < 50K resources |
| Fixed retry intervals (2s, 4s, 8s) | Predictable retry behavior | Thundering herd when multiple workers retry at same offsets | Never at scale -- always use jitter |
| `sys.path.insert(0, ...)` for imports | Quick fix for package resolution | Fragile, breaks with different working directories or packaging | Never in production tool -- use proper package structure with `pyproject.toml` |
| Hardcoded output directory `"output"` | No configuration needed | Cannot run tool from different directories; path breaks on Windows with spaces | Never -- use `pathlib.Path` and make configurable |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| AWS SSO (`aws sso login`) | Assuming boto3 Session auto-refreshes SSO tokens. It does not -- SSO tokens are cached files with fixed expiry, not refreshable OAuth tokens. | Check `~/.aws/sso/cache/*.json` for `expiresAt` before starting scan. Warn users if remaining lifetime < estimated scan duration. Catch `UnauthorizedSSOTokenError` specifically and advise re-login. |
| Azure `InteractiveBrowserCredential` | Calling it from worker threads. The browser auth flow must happen on the main thread; calling from a `ThreadPoolExecutor` worker causes deadlocks or crashes. | Warm the credential on the main thread before spawning workers (current code does this at `discover.py:263`). Pass the singleton credential object to all workers. |
| Azure `SubscriptionClient.subscriptions.list()` | Not handling paginated results. `list()` returns a lazy iterator that makes additional API calls as you iterate. If the token expires mid-pagination, you get partial results. | Materialize to list immediately: `list(subscription_client.subscriptions.list())`. Check for empty results and fall back to CLI. |
| GCP `google.auth.default()` | Assuming `project` is always returned. ADC returns `(credentials, project)` but `project` is `None` when using service account keys without a default project. | Always fall back to `GOOGLE_CLOUD_PROJECT` env var. In multi-project mode, `project` is only needed for quota billing, not for enumeration. |
| GCP `compute_v1` shared clients | Assuming per-project scoping. GCP compute clients are project-agnostic; the `project` parameter is passed per-API-call. But quota consumption is billed to the credential's quota project, not the target project. | Document this clearly. Support `--quota-project` flag. Monitor quota headers. |
| Azure `ResourceManagementClient` | Creating a new client per subscription in a loop without closing. Each client opens HTTP connection pools. With 200+ subscriptions, this exhausts file descriptors. | Use context managers (`with ... as client:`) as the current code does (`discover.py:269-273`). Verify connections are released on exit. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Per-region API calls when aggregated API exists | Scan takes 40x longer than necessary for GCP. 40 regions x N resource types = hundreds of API calls per project. | Use `aggregatedList` endpoints (GCP) that return resources across all zones in one call. Use `--filter` parameters to reduce response size. | At 50+ projects: each project scans 40 regions individually |
| Sequential resource type enumeration within accounts | Azure scans each resource type (VMs, VNets, DNS, LBs) one after another within a subscription, serializing what could be parallel. | Parallelize per-resource-type API calls within each account/subscription using a nested ThreadPoolExecutor. Gate concurrency with a shared semaphore. | At 20+ subscriptions: sequential enumeration adds minutes per subscription |
| DNS zone listing repeated per GCP project | `_build_zones_by_region()` called once per `GCPDiscovery` instance. With 100 projects, identical zone data is fetched 100 times. | Cache DNS zone-to-region mapping at the module level and share across all `GCPDiscovery` instances (same pattern as `shared_compute_clients`). | At 10+ projects: noticeable overhead and unnecessary API calls |
| Full API response stored in `details` field | Memory grows 5-10x beyond what licensing calculation needs. Raw API responses contain nested objects, metadata, audit logs. | Extract only licensing-relevant fields (IPs, name, state, tags) during discovery. Discard raw response immediately after extraction. | At 50K+ resources: memory exceeds 1GB |
| Checkpoint serialization of entire resource list | `json.dump()` of 100K+ resources takes 30+ seconds and doubles peak memory (Python string in memory + disk write). | Stream checkpoint data: use SQLite or append-only JSONL. Checkpoint per-account state, not the entire resource list. | At 100K+ resources: checkpoint save blocks scan progress |
| macOS default file descriptor limit of 256 | `OSError: [Errno 24] Too many open files` when running concurrent cloud API connections. 4 subscription workers x 5 Azure SDK clients each = 20 persistent connections minimum, plus DNS, plus HTTP keep-alive pools. | Check `ulimit -n` at startup and warn if < 1024. Document `ulimit -n 4096` in setup instructions. On macOS, auto-increase with `resource.setrlimit()` if under hard limit. | At 10+ concurrent subscription/project workers with all resource types enabled |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging full exception text from cloud SDKs | AWS/Azure/GCP SDK exceptions may contain bearer tokens, SAS tokens, or session IDs in their string representation. Writing these to stdout, log files, or error reports leaks credentials. | Sanitize exception messages before logging. Strip known token patterns (`Bearer .*`, `sig=.*`, `X-Amz-Security-Token=.*`). Log only exception type + sanitized message. |
| Writing checkpoint files with resource data to unprotected paths | Checkpoint JSON contains discovered resource details (IPs, hostnames, network configurations). If written to a world-readable directory, this is a data leak. | Write checkpoints to `~/.config/infoblox-ddi/` with `0o600` permissions. Or use the tool's output directory with restricted permissions. Document this in security guide. |
| Not validating cloud CLI tool integrity | The tool shells out to `aws`, `az`, `gcloud` via `subprocess`. On a compromised machine, a malicious binary in `PATH` could intercept these calls. | Use absolute paths to CLI tools where possible. On Windows, validate that `az.cmd` is in the expected Microsoft SDK path. This is low risk since the tool runs locally, but worth documenting for security-conscious customers. |
| Credential singleton persists across test runs | `_credential_cache` global variable survives between test cases in the same process. Stale credentials from one test can leak into another. | Provide `clear_credential_cache()` functions for testing. Use `importlib.reload()` or fixture-based credential injection. |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No progress indication during long scans | User sees no output for 5+ minutes while workers enumerate resources. Assumes the tool is hung. Presses Ctrl+C and loses progress. | Print per-account/subscription progress as workers complete (current code does this: `[N/total] sub_id`). Add a spinner or ETA for in-progress accounts. Show aggregate resource count incrementally. |
| Error messages reference SDK internals, not user actions | "ClientAuthenticationError: DefaultAzureCredential failed to retrieve a token" is not actionable for a pre-sales engineer. | Map every error to a user-facing message with remediation steps. Example: "Azure auth expired. Run `az login` and try again." |
| Output file naming uses timestamps only | `azure_universal_ddi_licensing_20260223_143022.csv` -- user cannot tell which scan parameters produced which file. | Include account count, provider, and a short hash in filename: `azure_42subs_20260223.csv`. |
| No distinction between "zero resources found" and "discovery failed" | If a subscription has no VMs, the output is the same as if the tool failed to authenticate to that subscription: zero resources in the report. | Add explicit "Scanned successfully: 0 resources" vs "FAILED: auth error" per account/subscription in the summary. Include scanned scope metadata in the output file header. |
| Resume prompt blocks unattended execution | `prompt_resume()` calls `input()`, which hangs in CI/CD, cron, or piped execution. | Already partially solved with `--resume` flag. Ensure the tool auto-detects non-interactive terminals (`sys.stdin.isatty()`) and defaults to `--resume` or `--no-checkpoint` behavior. |

## "Looks Done But Isn't" Checklist

- [ ] **Authentication:** Token validated at startup, but not checked for remaining lifetime vs. estimated scan duration -- stale tokens cause mid-scan failures
- [ ] **Rate limiting:** Retry logic exists for HTTP errors, but does not read cloud-specific throttling headers (`Retry-After`, `x-ms-ratelimit-remaining-tenant-reads`, `X-Goog-User-Project`) -- retries are blind
- [ ] **Checkpointing:** Checkpoint save/load works in happy path, but signal handler does not actually save state -- Ctrl+C loses all progress despite "saving checkpoint" message
- [ ] **Cross-platform:** Tool runs on macOS and Linux, but Windows file path handling uses forward slashes, `subprocess` calls assume Unix PATH resolution, and PowerShell script signing is mentioned but not implemented
- [ ] **Resource counting:** DDI objects, IPs, and assets are counted, but IP de-duplication across overlapping cloud accounts (e.g., same VPC peered across accounts) is not verified -- may double-count shared IPs
- [ ] **Output completeness:** CSV/XLS files contain resource data, but do not include scan metadata (which accounts were scanned, which failed, which were skipped) -- auditors cannot verify completeness
- [ ] **Large-scale testing:** Tool works for 5-10 accounts, but has never been tested at 100+ accounts with millions of resources -- memory, file descriptors, and API quotas are untested
- [ ] **Error categorization:** Errors are logged, but not categorized (transient vs. permanent, retriable vs. fatal) -- every error looks the same to the user

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Auth token expired mid-scan | LOW | Re-authenticate (`aws sso login` / `az login` / `gcloud auth login`), resume from checkpoint if available. If checkpoint is broken, re-run entire scan. |
| ARM rate limiting cascade | LOW | Reduce `--subscription-workers` to 1-2, wait 5 minutes for throttle window to reset, resume from checkpoint. |
| GCP quota exhausted | MEDIUM | Wait 24 hours for daily quota reset, or request quota increase via GCP Console. Resume from checkpoint if available. No way to speed this up. |
| Memory exhaustion (OOM) | HIGH | Must redesign data pipeline to stream results. Cannot recover by retrying -- the same data volume will cause the same OOM. Requires code changes, not configuration. |
| Checkpoint corruption | MEDIUM | Delete checkpoint file and re-run from scratch. If the checkpoint was the only record of partial results, those results are lost. Add checkpoint versioning and validation to prevent recurrence. |
| Broad exception masking real bug | HIGH | Must read raw exception type from DEBUG logs (if enabled), identify root cause, then fix code. Users cannot self-service this -- requires developer investigation. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Auth token expiry mid-scan | Phase 1: Core auth/config | Integration test: start scan with token expiring in 5 minutes. Verify tool warns or refreshes. |
| Azure ARM rate limiting | Phase 2: Azure discovery | Load test: scan 50+ subscriptions. Verify zero 429 errors with adaptive throttling. Check logs for throttling header reads. |
| GCP API quota exhaustion | Phase 2: GCP discovery | Load test: scan 100+ projects. Monitor quota consumption via `gcloud` commands. Verify adaptive rate limiting engages. |
| Signal handler state loss | Phase 1: Core framework | Test: send SIGINT during active scan. Verify checkpoint file contains all completed accounts. Verify resume works from saved checkpoint. |
| Memory exhaustion at scale | Phase 2: Provider discovery | Load test with synthetic 100K resources. Monitor RSS memory via `psutil`. Verify memory stays under 500MB. |
| Broad exception handling | Phase 1: Core framework | Code review: verify no `except Exception: pass` patterns remain. Verify error taxonomy covers all cloud SDK exception types. Verify user-facing messages are actionable. |
| Cross-platform file paths | Phase 1: Core framework | CI matrix: run full test suite on Windows, WSL, macOS. Verify output paths use `pathlib.Path` everywhere. Verify subprocess calls use platform-appropriate CLI paths. |
| Checkpoint format versioning | Phase 1: Core framework | Unit test: load a v1 checkpoint in a v2 tool. Verify migration logic applies. Verify unknown versions are rejected with a clear message. |
| File descriptor exhaustion | Phase 2: Provider discovery | Test on macOS with default `ulimit -n 256`. Run with 10+ concurrent workers. Verify tool warns if fd limit is too low and does not crash. |
| Output completeness metadata | Phase 3: Output/reporting | Review output CSV/XLS: verify header includes scan scope, failed accounts, and timestamp. Verify auditor can reconstruct what was and was not scanned. |

## Sources

- Existing codebase analysis: `azure_discovery/discover.py`, `gcp_discovery/discover.py`, `aws_discovery/discover.py`, `shared/base_discovery.py`
- `.planning/codebase/CONCERNS.md` -- documented tech debt, known bugs, performance bottlenecks, security considerations
- [Azure ARM throttling documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling) -- tenant-level rate limits (25 reads/sec), throttling headers, per-subscription vs per-tenant scoping
- [GCP Compute Engine rate quotas](https://docs.cloud.google.com/compute/api-quota) -- per-project rate quotas, quota project scoping
- [GCP Resource Manager quotas](https://docs.google.com/cloud/resource-manager/docs/limits) -- project enumeration limits
- [AWS boto3 SSO token expiry (GitHub #4119)](https://github.com/boto/boto3/issues/4119) -- "Token has expired and refresh failed" during long-running scripts
- [AWS SSO session expiration (GitHub #531)](https://github.com/aws/aws-sdk/issues/531) -- no automatic re-authentication for SSO tokens
- [Azure SDK Python token caching](https://github.com/Azure/azure-sdk-for-python/blob/azure-identity_1.21.0/sdk/identity/azure-identity/TOKEN_CACHING.md) -- persistent cache options, refresh token behavior
- [Azure InteractiveBrowserCredential caching issues (GitHub #23721)](https://github.com/Azure/azure-sdk-for-python/issues/23721) -- credential persistence gaps
- [Python ThreadPoolExecutor memory leaks (CPython #85754)](https://github.com/python/cpython/issues/85754) -- memory not freed when executor shuts down
- [Python signal handler deadlock with ThreadPoolExecutor (CPython #121649)](https://github.com/python/cpython/issues/121649) -- SIGINT handling deadlocks on shutdown lock
- [Cross-platform tool considerations (Semgrep blog)](https://semgrep.dev/blog/2025/five-considerations-when-building-cross-platform-tools-for-windows-and-macos/) -- subprocess, file paths, platform-specific behavior
- [macOS file descriptor limits](https://hiltmon.com/blog/2023/01/01/increasing-file-descriptor-ulimit-on-macos/) -- default 256 fd limit, `ulimit -n` adjustment

---
*Pitfalls research for: Multi-cloud resource discovery & UDDI licensing estimation*
*Researched: 2026-02-23*
