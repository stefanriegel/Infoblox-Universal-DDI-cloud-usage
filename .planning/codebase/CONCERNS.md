# Codebase Concerns

**Analysis Date:** 2026-02-18

## Tech Debt

**Bare exception handlers throughout codebase:**
- Issue: 64 instances of `except Exception as e:` without specific exception types, masking real errors and making debugging difficult
- Files: `aws_discovery/aws_discovery.py`, `azure_discovery/azure_discovery.py`, `azure_discovery/discover.py`, `azure_discovery/config.py`, `gcp_discovery/discover.py`, `aws_discovery/discover.py`
- Impact: Silent failures, improper error reporting, difficult troubleshooting in production
- Fix approach: Replace broad Exception catches with specific exception types (ClientError, CredentialUnavailableError, APIError, etc.) per service. Log specific error details.

**Print statements instead of logging:**
- Issue: 209 `print()` statements scattered throughout code - should use logging module for production code
- Files: All `discover.py` files (`aws_discovery/discover.py`, `azure_discovery/discover.py`, `gcp_discovery/discover.py`), `main.py`, config files
- Impact: Cannot control verbosity in production, no timestamp/severity levels, output mixed with actual logging
- Fix approach: Replace print statements with logging calls (logger.info, logger.warning, logger.error). Use appropriate log levels. Maintain backward compatibility for user-facing messaging.

**Inconsistent error exit handling:**
- Issue: Mix of `sys.exit(1)` calls and silent return None/[] on errors - no consistent error handling strategy
- Files: `aws_discovery/discover.py:30,38,41,54,63`, `gcp_discovery/discover.py:31,39,42,66,72,75`, `azure_discovery/discover.py:124`, `aws_discovery/config.py:58,61`
- Impact: Some errors crash hard, others silently fail with empty results, inconsistent user experience
- Fix approach: Implement centralized error handling. Define error hierarchy (FatalError, RecoverableError, etc.). All discovery methods should raise exceptions, not return empty lists.

**Missing None type annotations with mixed return types:**
- Issue: Functions return None, [], or dictionaries inconsistently without proper type hints
- Files: `azure_discovery/discover.py:76,83,87,115`, `shared/resource_counter.py:129,132,136,164,176,182,184,263`, `aws_discovery/aws_discovery.py:594`
- Impact: Type checkers cannot validate code, easy to introduce NoneType errors at runtime
- Fix approach: Add explicit return type hints (Optional[Dict], List[Dict], etc.) to all functions. Use mypy for static type checking.

**Unused pass statements:**
- Issue: Three bare `pass` statements found in except blocks (`azure_discovery/config.py:101`, `shared/resource_counter.py:211`, `gcp_discovery/config.py:50`)
- Impact: Indicates incomplete error handling paths or debugging code left behind
- Fix approach: Remove or replace with proper error handling code. If intentional, add comments explaining why silence is correct.

## Known Bugs

**Azure checkpoint loading overly restrictive:**
- Symptoms: 48-hour checkpoint timeout is hardcoded; legitimate long-running scans get discarded after 2 days
- Files: `azure_discovery/discover.py:81`
- Trigger: Run discovery, wait 48+ hours, resume from checkpoint
- Impact: Users cannot resume from checkpoints after 2 days, even if valid
- Workaround: Delete checkpoint file and start fresh scan
- Fix approach: Make checkpoint TTL configurable via environment variable or CLI arg (default 48h, allow override)

**Resource deduplication issue in licensing calculator:**
- Symptoms: Provider breakdown calculations may double-count resources when called multiple times
- Files: `shared/licensing_calculator.py:224-225`
- Cause: `_get_provider_breakdown()` recalculates active IPs by filtering and recounting, calling `_count_active_ips()` which invokes ResourceCounter.count_active_ip_metrics() again - inefficient and potentially inconsistent with already-counted IPs
- Fix approach: Cache IP counts per provider during initial calculation, reuse in breakdown

## Security Considerations

**Bare certificate file in repository:**
- Risk: `cert.cer` is committed to git without explanation - unclear if this is self-signed, test cert, or production signing cert
- Files: `cert.cer` (802 bytes)
- Current mitigation: Appears to be unused in code (no imports found), likely test cert
- Recommendations: (1) Confirm cert purpose and add comment to .gitignore explaining if legitimate, (2) Move test certs to tests/ directory, (3) Add pre-commit hook to prevent cert/key files being committed

**Environment variable exposure in subprocess calls:**
- Risk: AWS_SECRET_ACCESS_KEY, AZURE_CLIENT_SECRET stored in Python dataclass fields and potentially logged
- Files: `aws_discovery/config.py:21-22`, `azure_discovery/config.py:20-21` (via inheritance from BaseConfig)
- Current mitigation: Code doesn't explicitly log these, but they're loaded into dataclass fields
- Recommendations: (1) Never store secrets in dataclass fields - load only when needed, (2) Mask secrets in debug output, (3) Add comment warning against logging AWSConfig/AzureConfig objects

**GCP credential loading lacks validation:**
- Risk: `GOOGLE_APPLICATION_CREDENTIALS` path could point to invalid location without validation
- Files: `gcp_discovery/config.py:51-60`
- Current mitigation: Error caught at first API call, but late in process
- Recommendations: Validate GOOGLE_APPLICATION_CREDENTIALS path exists at startup in `check_gcp_credentials()`

**Insecure credential fallback chain in Azure:**
- Risk: `ChainedTokenCredential` attempts multiple auth methods including browser popup without user control
- Files: `azure_discovery/config.py:12-19`
- Current mitigation: None
- Recommendations: Document credential chain order, consider making credential strategy configurable, warn users about InteractiveBrowserCredential

## Performance Bottlenecks

**ResourceCounter IP parsing inefficiency:**
- Problem: `_canonicalize_ip()` called for every IP field in every resource, validates with ipaddress.ip_address() (regex-like parsing)
- Files: `shared/resource_counter.py:126-136`
- Cause: No caching of validation results; ipaddress validation is expensive for large-scale IP discovery
- Scaling impact: With 10,000+ resources and 100,000+ IPs, validation time compounds
- Improvement path: (1) Cache validated IP addresses in set, (2) Batch validate IPs using compiled patterns first, (3) Profile canonicalization CPU time in large scans

**Parallel discovery limited by ThreadPoolExecutor sizing:**
- Problem: `--workers` and `--subscription-workers` defaults (8 and 4) may be suboptimal for cloud API throttling
- Files: `main.py:201-210`, various discover.py files
- Cause: Conservative defaults chosen without guidance, no auto-tuning based on API rate limits
- Impact: Underutilizes potential for large subscriptions/projects (100+ regions/subscriptions scan slowly)
- Improvement path: (1) Add heuristic to auto-tune workers based on account/subscription scope, (2) Implement exponential backoff with retry counts as metrics

**Full resource data export writes entire JSON to memory:**
- Problem: `--full` flag saves all resource details; with 100k+ resources, JSON file can be multi-gigabyte
- Files: `shared/output_utils.py`, discovery classes
- Cause: Entire list loaded in memory before writing to disk
- Impact: OOM errors on medium-sized clouds (Azure with 100k+ VMs)
- Improvement path: Use streaming JSON writer (ijson or custom implementation), write resources as they're discovered

## Fragile Areas

**Resource type mapping across three providers:**
- Files: `shared/constants.py`, `shared/licensing_calculator.py:95-126`, `shared/resource_counter.py`
- Why fragile: Resource types are hardcoded in multiple places without centralized source of truth; adding new resource type requires changes in 3+ files
- Safe modification: (1) Create ResourceTypeRegistry class with single source of truth, (2) Centralize all provider type mappings there, (3) Add unit tests for completeness of type coverage
- Test coverage: Only basic help tests exist (tests/test_main.py); no unit tests for counting logic or type classification

**IP address parsing and deduplication logic:**
- Files: `shared/resource_counter.py:180-290`
- Why fragile: Complex nested conditionals for IP space inference (vpc_id vs VpcId, subnet_id vs subnetId) - case-sensitivity issues lurk here
- Safe modification: Add comprehensive unit tests for IP pair extraction. Create normalized key function that handles all case variants. Document IP space inference rules clearly.
- Test coverage: Zero unit tests; only integration tests via main.py --check-auth

**Checkpoint and resume mechanism:**
- Files: `azure_discovery/discover.py:52-97`
- Why fragile: Checkpoint loads args, subscriptions, and objects from JSON but can't validate consistency; if args change mid-scan, results are corrupted
- Safe modification: (1) Add args hash/signature to checkpoint, (2) Detect args mismatch and warn/fail fast, (3) Add comprehensive logging of what's being resumed
- Test coverage: Only manual test in test_checkpoint.py; no pytest integration tests

## Scaling Limits

**Azure subscription discovery sequential bottleneck:**
- Current capacity: Checkpoint saves every 50 subscriptions; with 1000+ subscriptions in large Azure tenant, this creates many checkpoint writes
- Limit: Checkpoint JSON file grows linearly; after processing 500 subscriptions, checkpoint file can be 50MB+
- Scaling path: (1) Implement streaming checkpoint format (JSONL), (2) Make checkpoint interval configurable (default 50 is too frequent for large tenants), (3) Implement checkpoint cleanup to archive old entries

**ThreadPoolExecutor resource leaks on error:**
- Current capacity: 8 workers by default
- Limit: If discovery encounters per-region throttling errors, threads may hang waiting for retries; no connection pooling reuse across regions
- Scaling path: Implement thread pool with connection pooling per region, add per-thread timeout, add health check to kill stuck threads

**Output file sizes for large environments:**
- Current capacity: No limit on resource count before writing files
- Limit: Single JSON file with 100k+ resources = 500MB+; CSV with headers repeated = even larger
- Scaling path: (1) Implement streaming output writers, (2) Split output files by region/subscription/provider, (3) Add compression option

## Dependencies at Risk

**google-cloud-dns pinned to 0.35.1:**
- Risk: Pinned version is likely old (no upper bound constraint)
- Files: `requirements.txt:17`
- Impact: May have security vulnerabilities, doesn't receive updates
- Migration plan: Upgrade to latest google-cloud-dns, test compatibility with discovery patterns

**pandas dependency may be unused:**
- Risk: pandas listed in requirements.txt but not used in analyzed code
- Files: `requirements.txt:22`
- Impact: Adds 100MB+ to venv, slows pip install, increases attack surface
- Migration plan: Search full codebase for pandas usage; if not used, remove from requirements

**boto3 version constraint (>=1.26.0) is loose:**
- Risk: >=1.26.0 allows major version jumps with potential breaking changes
- Files: `requirements.txt:5`
- Impact: Different environments may get incompatible boto3 versions
- Migration plan: Pin to specific minor version (e.g., >=1.26.0,<2.0.0)

## Missing Critical Features

**No request timeout configuration:**
- Problem: Discovery may hang indefinitely on slow/hanging API endpoints with no timeout
- Blocks: Large cloud scans can be interrupted without resuming
- Solution: Add `--api-timeout` parameter (default 30s), pass to boto3/azure/gcp clients
- Files affected: All client initialization in config files and discovery classes

**No API rate limiting awareness:**
- Problem: Discovery fires requests as fast as thread pool allows, no exponential backoff for 429 (rate limit) responses
- Blocks: Large scans fail or are throttled by cloud providers
- Solution: Implement token bucket rate limiter per service, detect 429 responses, auto-backoff
- Files affected: `aws_discovery/aws_discovery.py`, `azure_discovery/azure_discovery.py`, `gcp_discovery/gcp_discovery.py`

**No dry-run or validation mode:**
- Problem: Cannot test credentials/permissions without running full discovery
- Blocks: Users don't know if they have sufficient permissions until discovery completes
- Solution: Add `--dry-run` flag that validates credentials and fetches first page of resources only
- Files affected: `main.py`, all discover.py entry points

## Test Coverage Gaps

**No unit tests for resource counting logic:**
- What's not tested: `_count_ddi_objects()`, `_count_active_ips()`, `_count_managed_assets()` in licensing calculator
- Files: `shared/licensing_calculator.py`, `shared/resource_counter.py`
- Risk: Resource classification bugs go undetected; licensing calculations could be wrong
- Priority: High - licensing accuracy is core to product

**No tests for IP space deduplication:**
- What's not tested: `_get_active_ip_pairs()`, IP space inference by VPC/VNet/network
- Files: `shared/resource_counter.py:160-180`
- Risk: Deduplication logic may fail for edge cases (overlapping VPCs, CIDR notation, IPv6)
- Priority: High - incorrect IP counts affect licensing

**No mocking of cloud API calls:**
- What's not tested: Actual discovery without real cloud credentials
- Files: Tests attempt to run against real cloud APIs
- Risk: Tests cannot run in CI/CD without credentials
- Priority: Medium - add pytest fixtures with mocked responses, test error handling

**No error scenario coverage:**
- What's not tested: What happens when API calls fail, timeouts occur, rate limits triggered, permissions insufficient
- Files: All discovery classes, all config files
- Risk: Error handling code is never validated
- Priority: High - users will hit errors in production

**No integration tests for checkpoint/resume:**
- What's not tested: Full discovery flow with simulated interruption and resume
- Files: `test_checkpoint.py` only tests save/load, not integration with discovery
- Risk: Checkpoint feature could fail silently during actual multi-subscription scans
- Priority: Medium - Azure-specific but critical for large tenants

---

*Concerns audit: 2026-02-18*
