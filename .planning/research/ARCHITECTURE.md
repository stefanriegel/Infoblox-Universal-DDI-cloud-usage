# Architecture Research

**Domain:** Multi-cloud resource discovery & UDDI licensing estimation tool
**Researched:** 2026-02-23
**Confidence:** HIGH

## Existing Architecture Problems

The current codebase has structural issues that motivate a rewrite. Understanding these is essential context for the target architecture.

**Problem 1: Nested ThreadPoolExecutor deadlock risk.** Azure's `discover.py` spawns a `ThreadPoolExecutor(subscription_workers)` where each worker calls `AzureDiscovery.discover_native_objects(max_workers)`, which creates *another* `ThreadPoolExecutor` internally. Under load with 100+ subscriptions, the outer pool's threads block waiting for inner pool threads, all competing for the same OS thread pool. This creates thread starvation and, on large tenants, can cause silent hangs.

**Problem 2: No cross-account rate coordination.** Each subscription/project worker independently hits cloud APIs with no awareness of other workers. Azure ARM has *tenant-level* rate limits (not just per-subscription), so 4 concurrent subscription workers each doing `NetworkManagementClient.list_all()` can collectively exceed the tenant-wide 25 reads/sec limit and trigger cascading 429s. The current retry policy is per-client, not coordinated.

**Problem 3: Monolithic discover.py files.** Each provider's `discover.py` is a ~450-line `main()` function that handles CLI parsing, auth, enumeration, concurrent execution, progress display, error collection, checkpointing, licensing calculation, and file export. This makes testing and modification difficult.

**Problem 4: Duplicated logic across providers.** The post-discovery flow (count resources, calculate licensing, export CSV/TXT/JSON) is copy-pasted across all three provider `discover.py` files. Changes to output format require editing three files.

**Problem 5: In-memory accumulation.** All discovered resources are held in `all_native_objects: List[Dict]` in memory. For 100+ accounts with thousands of resources each, this can exhaust memory on customer laptops.

## Recommended Architecture

### System Overview

```
                         +-----------------------+
                         |      CLI / Web UI     |
                         |  (argparse + FastAPI)  |
                         +----------+------------+
                                    |
                         +----------v------------+
                         |    Orchestrator        |
                         |  (provider selection,  |
                         |   account enumeration, |
                         |   progress tracking)   |
                         +----------+------------+
                                    |
              +---------------------+---------------------+
              |                     |                     |
    +---------v--------+  +--------v---------+  +--------v---------+
    |  AWS Provider    |  |  Azure Provider  |  |  GCP Provider    |
    |  (account-level  |  |  (subscription-  |  |  (project-level  |
    |   discovery)     |  |   level disc.)   |  |   discovery)     |
    +--------+---------+  +--------+---------+  +--------+---------+
             |                     |                     |
    +--------v---------+  +--------v---------+  +--------v---------+
    |  Rate Limiter    |  |  Rate Limiter    |  |  Rate Limiter    |
    |  (per-provider   |  |  (per-tenant +   |  |  (per-project    |
    |   semaphore)     |  |   per-sub)       |  |   semaphore)     |
    +--------+---------+  +--------+---------+  +--------+---------+
             |                     |                     |
             +---------------------+---------------------+
                                   |
                         +---------v----------+
                         |   Result Collector  |
                         |  (streaming append  |
                         |   to disk, not RAM) |
                         +---------+----------+
                                   |
                    +--------------+--------------+
                    |              |              |
           +--------v---+  +------v------+  +----v---------+
           | Resource   |  | Licensing   |  | Report       |
           | Counter    |  | Calculator  |  | Generator    |
           | (DDI/IP/   |  | (token math)|  | (CSV/XLS per |
           | Asset)     |  |             |  |  provider)   |
           +------------+  +-------------+  +--------------+
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| **CLI Entry** | Parse arguments, select provider, invoke orchestrator | Orchestrator |
| **Web UI** | FastAPI server with HTML dashboard, SSE progress stream | Orchestrator (via shared state) |
| **Orchestrator** | Enumerate accounts/subs/projects, manage concurrency pool, track progress, handle checkpointing | Provider modules, Result Collector, CLI/Web UI |
| **Provider Module** (x3) | Authenticate, discover resources for one account/sub/project, format resources to common schema | Rate Limiter, Result Collector |
| **Rate Limiter** | Per-provider semaphore + token bucket enforcing cloud API rate limits across all concurrent workers | Provider Modules |
| **Result Collector** | Receive discovered resources, stream-write to temp storage (JSONL on disk), provide iterator for post-processing | Orchestrator, Resource Counter |
| **Resource Counter** | Classify resources into DDI objects, Active IPs (with IP-space dedup), Managed Assets | Result Collector, Licensing Calculator |
| **Licensing Calculator** | Apply token ratios (25/13/3), compute totals | Resource Counter, Report Generator |
| **Report Generator** | Produce per-provider CSV/XLS with detail + summary sheets | Licensing Calculator, filesystem |

## Recommended Project Structure

```
src/
  uddi_estimator/
    __init__.py
    cli.py                    # argparse entry point
    web/
      app.py                  # FastAPI app
      templates/              # Jinja2 HTML templates
      static/                 # CSS/JS
    core/
      orchestrator.py         # Discovery orchestration
      rate_limiter.py         # Provider-aware rate limiting
      result_collector.py     # Streaming result accumulation
      checkpoint.py           # Checkpoint save/resume
      progress.py             # Progress tracking (CLI + SSE)
    providers/
      base.py                 # Abstract provider interface
      aws/
        __init__.py
        auth.py               # AWS auth (SSO/profile detection)
        discovery.py          # AWS resource discovery
        config.py             # AWS-specific config
      azure/
        __init__.py
        auth.py               # Azure auth (az login / credential chain)
        discovery.py          # Azure resource discovery
        config.py             # Azure-specific config
      gcp/
        __init__.py
        auth.py               # GCP auth (gcloud ADC)
        discovery.py          # GCP resource discovery
        config.py             # GCP-specific config
    counting/
      resource_counter.py     # DDI/IP/Asset classification
      ip_dedup.py             # IP-space aware deduplication
    licensing/
      calculator.py           # Token math
      mapping.yml             # Resource type -> category mapping
    reporting/
      generator.py            # CSV/XLS report generation
      templates/              # Report templates/schemas
    shared/
      constants.py            # Token ratios, resource type lists
      types.py                # Dataclass/TypedDict definitions
      logging.py              # Structured logging config
```

### Structure Rationale

- **`providers/`**: One package per cloud, each with the same interface (auth, discovery, config). Isolates SDK-specific code. Adding a fourth cloud means adding one package.
- **`core/`**: Shared orchestration logic that does not depend on any specific cloud SDK. The orchestrator does not import boto3, azure-mgmt, or google-cloud.
- **`counting/` and `licensing/`**: Separated from discovery. These only operate on the common resource schema (list of dicts). This makes them independently testable.
- **`web/`**: Fully optional. The CLI works without FastAPI installed. The web module imports the same orchestrator.

## Architectural Patterns

### Pattern 1: Single-Level Concurrency with Provider-Scoped Semaphores

**What:** Replace nested `ThreadPoolExecutor` with a single `ThreadPoolExecutor` whose workers are governed by per-provider `threading.Semaphore` instances. Each account/subscription/project is one work unit submitted to the pool. Within each work unit, API calls are made sequentially (regions iterated in a loop, not a nested pool).

**When to use:** Always. This is the core concurrency model for the rewrite.

**Trade-offs:**
- Pro: eliminates thread starvation from nested pools, makes rate limiting straightforward (acquire semaphore before each API call batch), predictable thread count
- Pro: ThreadPoolExecutor is the right choice over asyncio because all three cloud SDKs (boto3, azure-mgmt, google-cloud) are synchronous libraries; wrapping them in `asyncio.to_thread()` adds complexity with no throughput benefit
- Con: sequential region iteration within a worker is slower per-account than parallel regions, but total throughput across 100+ accounts is higher because threads are not wasted waiting for inner pools

**Example:**
```python
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

class RateLimiter:
    """Per-provider rate limiter using semaphore + delay."""
    def __init__(self, max_concurrent: int = 4, min_delay_sec: float = 0.1):
        self._sem = threading.Semaphore(max_concurrent)
        self._delay = min_delay_sec
        self._lock = threading.Lock()
        self._last_call = 0.0

    def acquire(self):
        self._sem.acquire()

    def release(self):
        import time
        with self._lock:
            now = time.monotonic()
            wait = max(0, self._delay - (now - self._last_call))
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
        self._sem.release()

# Orchestrator uses a SINGLE thread pool
rate_limiter = RateLimiter(max_concurrent=4)

with ThreadPoolExecutor(max_workers=8) as pool:
    futures = {
        pool.submit(discover_account, acct, rate_limiter): acct
        for acct in accounts
    }
    for future in as_completed(futures):
        results = future.result()
        result_collector.append(results)  # stream to disk
```

### Pattern 2: Streaming Result Collection (JSONL on Disk)

**What:** Instead of accumulating all resources in a Python list (`all_native_objects`), write each account's results immediately to a JSONL (newline-delimited JSON) temp file. Post-processing reads the file line by line.

**When to use:** When total discovered resources across all accounts may exceed available RAM (realistic for 100+ accounts with 10,000+ resources each).

**Trade-offs:**
- Pro: constant memory usage regardless of scale, crash-safe (partial results survive), enables checkpoint-resume at account granularity
- Pro: JSONL is trivially appendable (no JSON array bookkeeping)
- Con: post-processing requires a file read pass, slightly slower than in-memory for small datasets
- Con: adds file I/O dependency (but these are local SSDs, latency is negligible)

### Pattern 3: Common Resource Schema with Provider Annotation

**What:** Every provider emits resources as a flat dict with a fixed set of top-level keys. Provider-specific details live in `details`. The counting and licensing modules never need to know which cloud a resource came from.

**When to use:** Always. This is already partially implemented in the current codebase.

**Trade-offs:**
- Pro: counting/licensing code is provider-agnostic, single code path
- Pro: makes adding resource types a data change (update mapping.yml) not a code change
- Con: some provider nuances get flattened (but this is the right trade for a licensing estimation tool)

```python
# Common resource schema (enforced by providers/base.py)
resource = {
    "provider": "aws",                    # NEW: explicit provider tag
    "account_id": "123456789012",          # NEW: account/sub/project
    "resource_id": "vpc-0abc123",
    "resource_type": "vpc",
    "region": "us-east-1",
    "name": "production-vpc",
    "state": "available",
    "requires_management_token": True,
    "category": "ddi",                     # NEW: pre-classified
    "tags": {"Environment": "prod"},
    "details": {                           # provider-specific
        "cidr_block": "10.0.0.0/16",
        "vpc_id": "vpc-0abc123",
    },
    "discovered_at": "2026-02-23T10:30:00",
}
```

## Data Flow

### Discovery Flow (Primary)

```
CLI args / Web UI request
    |
    v
Orchestrator.run(provider, config)
    |
    +--> Auth module validates credentials (fail-fast)
    |
    +--> Enumerate accounts/subscriptions/projects
    |
    +--> Check for checkpoint, resume if valid
    |
    +--> Create ThreadPoolExecutor(max_workers=N)
    |       |
    |       +--> Worker 1: discover_account(acct_A)
    |       |       |
    |       |       +--> rate_limiter.acquire()
    |       |       +--> discover_regions_sequentially()
    |       |       +--> rate_limiter.release()
    |       |       +--> result_collector.write(resources)
    |       |       +--> progress.update(acct_A, done)
    |       |
    |       +--> Worker 2: discover_account(acct_B) ...
    |       +--> Worker N: ...
    |
    +--> result_collector.finalize()
    |
    +--> ResourceCounter.count(result_collector.iter())
    |
    +--> LicensingCalculator.calculate(counts)
    |
    +--> ReportGenerator.generate(licensing_results)
    |
    v
Output: per-provider CSV/XLS + proof manifest
```

### Progress Reporting Flow

```
Worker completes account
    |
    +--> progress.update(account_id, resource_counts, elapsed)
            |
            +--> CLI: print("[3/150] acct-xyz -- 42 vpcs, 128 subnets ...")
            |
            +--> Web UI: SSE push to /api/progress endpoint
                    |
                    +--> Browser JS updates progress bar + table
```

### Checkpoint Flow

```
Worker completes account
    |
    +--> Orchestrator saves checkpoint:
    |       { completed_accounts: [...], timestamp, config_hash }
    |
On restart:
    |
    +--> Load checkpoint, verify config_hash matches
    |
    +--> Filter account list to exclude completed ones
    |
    +--> Resume from where it left off
    |
On successful completion:
    |
    +--> Delete checkpoint file
```

### Key Data Flows

1. **Discovery -> Collection:** Each worker writes its account's resources as JSONL lines to a shared temp file (protected by `threading.Lock` on the file handle). No cross-worker data sharing needed.
2. **Collection -> Counting:** After all workers complete, `ResourceCounter` iterates the JSONL file line-by-line, classifying each resource and building counts in memory (counts are O(resource_types), not O(resources)).
3. **Counting -> Licensing:** Pure math pass. Takes DDI count, IP count, Asset count and applies token ratios.
4. **Licensing -> Reports:** Writes CSV/XLS files. Detail sheet reads JSONL again for per-resource rows. Summary sheet uses aggregated counts.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-10 accounts | Default config works. Single-threaded is fine. No rate limiter needed. |
| 10-50 accounts | ThreadPoolExecutor with 4-8 workers. Rate limiter with semaphore(4). |
| 50-200 accounts | ThreadPoolExecutor with 4-6 workers (not more). Rate limiter with semaphore(3). Azure: limit to 2 subscription workers due to tenant-level ARM throttling. JSONL streaming essential. |
| 200+ accounts | Consider provider-specific adaptive concurrency (start at 4 workers, reduce on 429). Checkpoint-resume mandatory. May need to split into batches. |

### Scaling Priorities

1. **First bottleneck: Azure tenant-level rate limits.** ARM throttles at 25 reads/sec across ALL subscriptions for a single service principal. With 4 subscription workers each doing 5 API calls concurrently, you hit this immediately. Fix: shared tenant-level semaphore limiting total concurrent ARM calls to ~10, with Retry-After header respect.

2. **Second bottleneck: Memory with large resource sets.** 200 accounts * 5,000 resources/account * 2KB/resource = ~2GB in memory. Fix: JSONL streaming to disk, line-by-line post-processing.

3. **Third bottleneck: AWS region fan-out.** AWS has 30+ regions, and describe calls per region add up quickly with many accounts. Fix: sequential region iteration per account (not parallel), rely on account-level concurrency for throughput.

## Anti-Patterns

### Anti-Pattern 1: Nested Thread Pools

**What people do:** Create a `ThreadPoolExecutor` for accounts, where each worker creates *another* `ThreadPoolExecutor` for regions within that account.
**Why it's wrong:** With 100 accounts * 8 region workers = 800 threads competing for OS resources. Thread creation overhead dominates. Inner threads block outer threads when the OS scheduler deprioritizes them. Python's GIL means these threads cannot run truly concurrently for CPU work anyway.
**Do this instead:** Single `ThreadPoolExecutor` with a moderate worker count (4-8). Each worker iterates regions sequentially. Total throughput is governed by the number of accounts, not regions-per-account.

### Anti-Pattern 2: In-Memory Resource Accumulation

**What people do:** `all_native_objects.extend(worker_results)` in a shared list, protected by a lock.
**Why it's wrong:** Memory grows linearly with total resources. For 100+ accounts, this can reach gigabytes. A crash loses everything. Checkpointing requires serializing the entire list.
**Do this instead:** Stream results to JSONL on disk. Each account's results are appended atomically. Checkpoint is just the list of completed account IDs.

### Anti-Pattern 3: Provider-Unaware Rate Limiting

**What people do:** Set `max_workers=8` and hope for the best. Add retry logic per-client but no coordination across clients.
**Why it's wrong:** Cloud rate limits are scoped differently per provider. Azure limits per-tenant (across all subscriptions). AWS limits per-account per-region. GCP limits per-project. A single `max_workers` setting cannot respect all three simultaneously.
**Do this instead:** Provider-specific rate limiter configuration. Azure gets a tenant-level semaphore(2-3). AWS gets per-region delay. GCP gets per-project semaphore(4).

### Anti-Pattern 4: Copy-Paste Post-Processing

**What people do:** Duplicate the "count resources -> calculate tokens -> export files" pipeline in each provider's `discover.py`.
**Why it's wrong:** Bug fixes and output format changes require editing three files. Easy to introduce inconsistencies.
**Do this instead:** Single post-processing pipeline in the orchestrator. Provider modules only handle discovery. Counting, licensing, and reporting are provider-agnostic modules operating on the common resource schema.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| AWS APIs (EC2, Route53, ELB, STS) | boto3 clients, one per region per account | Use `adaptive` retry mode. Session-per-account. Respect `RequestLimitExceeded`. |
| Azure ARM APIs | azure-mgmt-* clients, one per subscription | Share credential across subs. Respect `Retry-After` header from 429s. Tenant-level rate limit coordination required. |
| GCP APIs (Compute, DNS) | google-cloud-* clients, shared across projects (except DNS per-project) | 403 `rateLimitExceeded` = wait 60s. Per-project quota. Compute clients are project-agnostic. |
| Local filesystem | JSONL temp files + CSV/XLS output | All data stays local. No network egress. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| CLI/Web <-> Orchestrator | Function call (CLI) or shared state + SSE (Web) | Web UI is optional; CLI must work standalone |
| Orchestrator <-> Provider Modules | Provider implements `discover(account_id, config, rate_limiter) -> Iterator[Resource]` | Provider never imports orchestrator |
| Provider Modules <-> Rate Limiter | `rate_limiter.acquire()` / `rate_limiter.release()` context manager | Rate limiter is injected by orchestrator |
| Result Collector <-> Counting | `collector.iter_resources() -> Iterator[dict]` | Read-only iteration, no mutation |
| Counting <-> Licensing | `LicensingCalculator.calculate(ddi_count, ip_count, asset_count) -> TokenResult` | Pure function, no side effects |

## Build Order Implications

Components should be built in this order due to data and interface dependencies:

1. **Phase 1: Common schema + provider base class + resource counter.** Everything depends on the resource schema. Define the `Resource` TypedDict/dataclass and the abstract provider interface first. Port the existing `ResourceCounter` and `LicensingCalculator` to work with the new schema. These are independently testable.

2. **Phase 2: Rate limiter + result collector.** These are infrastructure components needed by the orchestrator. Build and test independently with mock data.

3. **Phase 3: One provider (start with AWS -- simplest rate limiting model).** Implement the AWS provider module against the base class. Wire it through the orchestrator. End-to-end test: CLI invocation -> AWS discovery -> JSONL -> counts -> licensing CSV.

4. **Phase 4: Azure provider.** Most complex rate limiting (tenant-level). Add Azure-specific rate limiter configuration. Add checkpoint/resume (Azure has the longest scan times due to many subscriptions).

5. **Phase 5: GCP provider.** Multi-project with shared compute clients (pattern already prototyped in existing codebase).

6. **Phase 6: Web dashboard.** FastAPI + SSE progress stream + HTML results viewer. Depends on orchestrator progress tracking being in place.

7. **Phase 7: Report generation (CSV/XLS with detail + summary sheets).** Can be refined after all providers work. Uses the same JSONL data.

**Critical dependency:** Phases 3-5 all depend on Phase 1 (schema) and Phase 2 (rate limiter). Phase 6 depends on Phase 3-5 having a working progress API. Phase 7 can be built in parallel with Phase 6.

## Sources

- Existing codebase analysis (primary source, HIGH confidence)
- [Azure ARM throttling documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling) (HIGH confidence)
- [GCP Compute Engine rate quotas](https://cloud.google.com/compute/api-quota) (HIGH confidence)
- [AWS managing API throttling](https://aws.amazon.com/blogs/mt/managing-monitoring-api-throttling-in-workloads/) (HIGH confidence)
- [Boto3 retry configuration](https://boto3.amazonaws.com/v1/documentation/api/1.17.108/guide/retries.html) (HIGH confidence)
- [Python ThreadPoolExecutor vs AsyncIO](https://superfastpython.com/threadpoolexecutor-vs-asyncio/) (MEDIUM confidence)
- [Asyncio semaphore concurrency limiting](https://rednafi.com/python/limit-concurrency-with-semaphore/) (MEDIUM confidence)

---
*Architecture research for: Multi-cloud resource discovery & UDDI licensing estimation*
*Researched: 2026-02-23*
