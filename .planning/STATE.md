---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: NIOS Grid Analysis
status: unknown
last_updated: "2026-02-28T20:11:19.761Z"
progress:
  total_phases: 11
  completed_phases: 10
  total_plans: 34
  completed_plans: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-28)

**Core value:** Accurate, auditable UDDI token estimation from any source — cloud or NIOS Grid — customers must trust the numbers and understand exactly how they were derived.
**Current focus:** Milestone v1.1 — NIOS Grid Analysis (roadmap defined, ready for Phase 10 planning)

## Current Position

Phase: Phase 10 — 10-nios-parser-and-schema
Plan: Plan 02 complete — 10-02-PLAN.md (parse_backup streaming parser)
Status: In Progress — Plan 03 (inspect_backup) is next
Last activity: 2026-02-28 — Plan 02 complete: parse_backup() TDD, 10 tests, 4 parser modules

Progress: [==========░░░░░░░░░░░░░░░] Phase 10: 2/3 plans complete

## Performance Metrics

**Velocity (v1.0 baseline):**
- Total plans completed: 26
- Average duration: 8min
- Total execution time: 3.35 hours

**By Phase (v1.0):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-core-infrastructure | 4 | 15min | 4min |
| 02-aws-provider-and-end-to-end-pipeline | 6 | 51min | 9min |
| 02.1-wire-ratelimiter-into-discovery-pipeline | 2 | 17min | 9min |
| 03-azure-provider | 4 | 40min | 10min |
| 04-gcp-provider | 4 | 33min | 8min |
| 05-web-dashboard | 4/4 | 42min | 11min |

**Recent Trend:**
- Last 5 plans: 04-04 (6min), 05-01 (8min), 05-02 (13min), 05-03 (13min), 05-04 (8min)
- Trend: Foundation plans take 8-11min, collector plans 7-9min, integration plans 13min, dashboard plans 8-13min

*Updated after each plan completion*
| Phase 02 P01 | 6min | 2 tasks | 9 files |
| Phase 02 P03 | 7min | 2 tasks | 5 files |
| Phase 02 P04 | 7min | 2 tasks | 4 files |
| Phase 02 P05 | 5min | 2 tasks | 6 files |
| Phase 02 P06 | 22min | 3 tasks | 7 files (+15 deleted) |
| Phase 02.1 P02 | 8min | 1 task | 2 files |
| Phase 02.1 P01 | 9min | 2 tasks | 6 files |
| Phase 03 P01 | 7min | 2 tasks | 10 files |
| Phase 03 P02 | 6min | 2 tasks | 5 files |
| Phase 03 P03 | 14min | 2 tasks | 8 files |
| Phase 03 P04 | 13min | 3 tasks | 14 files (+6 deleted) |
| Phase 04 P01 | 11min | 2 tasks | 10 files |
| Phase 04 P02 | 7min | 2 tasks | 4 files |
| Phase 04 P03 | 9min | 2 tasks | 4 files |
| Phase 04 P04 | 6min | 4 tasks | 8 files (+5 deleted) |
| Phase 05 P01 | 8min | 2 tasks | 14 files |
| Phase 05 P02 | 13min | 2 tasks | 13 files |
| Phase 05 P03 | 13min | 2 tasks | 10 files |
| Phase 05 P04 | 8min | 2 tasks | 12 files |
| Phase 06 P01 | 3min | 2 tasks | 8 files |
| Phase 06 P02 | 2min | 2 tasks | 3 files |
| Phase 07 P01 | 7min | 2 tasks | 4 files |
| Phase 07 P02 | 9min | 2 tasks | 4 files |
| Phase 08 P01 | 2min | 2 tasks | 3 files |
| Phase 08 P02 | 7min | 2 tasks | 3 files |
| Phase 09 P01 | 16min | 2 tasks | 9 files |
| Phase 09 P01 | 16 | 2 tasks | 9 files |
| Phase 10-nios-parser-and-schema P01 | 35 | 2 tasks | 6 files |
| Phase 10-nios-parser-and-schema P02 | 8 | 2 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Phase 2 builds the full end-to-end pipeline (discovery -> counting -> tokens -> reports) with AWS as first provider, so Phases 3-4 only add provider-specific discovery
- [Roadmap]: Phase 1 addresses 4 of 6 critical pitfalls (auth expiry, exception masking, checkpoint corruption, signal handler state loss) before any cloud SDK code
- [01-01]: Used from __future__ import annotations for Python 3.10+ type hint syntax on Python 3.9 runtime
- [01-01]: Error classification uses strict priority ordering (AUTH > RATE_LIMIT > NETWORK > API > UNKNOWN) for deterministic resolution
- [01-01]: Audit logger clears existing handlers per setup call for per-scan file isolation
- [01-02]: Retry decorator delegates to classify_error() for category-based retry eligibility, not exception type matching
- [01-02]: RateLimiter uses exponential backoff (1s*2^n capped at 60s) when no Retry-After header present
- [01-02]: Checkpoint save uses fd-tracking with None sentinel to prevent double-close in error cleanup
- [01-02]: TTL=0 disables expiry check, allowing indefinite checkpoint validity for testing
- [01-03]: AuthResult.read_only defaults to True with no setter -- AUTH-05 enforced by design, not runtime checks
- [01-03]: ProgressTracker uses copy.deepcopy for get_summary() to prevent callers from mutating internal state
- [01-03]: register_provider accepts unit_label parameter so Azure uses 'subscriptions' and GCP uses 'projects'
- [01-04]: Orchestrator uses provider-scoped semaphores (not global) for independent per-provider concurrency control
- [01-04]: GracefulShutdown registers SIGINT/SIGTERM handlers in __init__ and uses threading.Lock for state updates
- [01-04]: CLI returns graceful message when no provider implementations exist (Phase 1 stub)
- [01-04]: select_providers() accepts both numbers (1,3) and names (aws,gcp) for user-friendly input
- [02-02]: Categorizer uses type-to-category mapping dicts (DDI_TYPES, TOKEN_FREE_TYPES) for clarity and easy extension
- [02-02]: IP counter uses ipaddress stdlib module for private/public classification and validation
- [02-02]: Per-VPC dedup key is (vpc_id_or_account_id, ip_address) tuple in a set for O(1) dedup
- [02-02]: Tag-based exclusion exempts DDI and token-free types (only managed assets can be excluded)
- [02-02]: Token ceiling division uses if count > 0 else 0 guard (not max(1, ...))
- [02-02]: calculate_account_tokens accepts optional deduplicated_ip_count for per-VPC dedup integration
- [Phase 02]: AWS Organizations API returns 'Id' not 'AccountId' -- code uses actual API field names
- [Phase 02]: Auth validator keeps account_count=1 fallback when Organizations returns 0 accounts
- [Phase 02]: SSOTokenLoadError handled via exception class name check since import path varies across botocore versions
- [02-03]: Route53 collectors set region="global" and omit region parameter since Route53 is account-global
- [02-03]: All ENIs collected regardless of attachment status -- asset_dedup module handles folding
- [02-03]: DHCP orphan detection uses set membership check against VPC-extracted DhcpOptionsId values
- [02-03]: Record resource_id format is zone_id/name/type for uniqueness across zones
- [02-04]: ECS tests use manual mocks due to moto 5.1.21 awsvpc bug (private_dns_name missing on NetworkInterface)
- [02-04]: RDS instances set ip_addresses=[] -- ENI discovery handles IP attribution
- [02-04]: Lambda VPC test checks non-empty vpc_id (moto returns synthetic vpc-123abc)
- [02-04]: Redshift uses ClusterNamespaceArn as resource_id when available
- [02-05]: xlsxwriter for write-only XLS generation (rich formatting, no read overhead); openpyxl only in tests
- [02-05]: .gitignore output/ exclusion scoped to root /output/ so src/cloud_usage/output/ is trackable
- [02-05]: Proof manifest uses two-phase hashing: resource_hash from sorted resource tuples, then manifest_hash over all fields
- [02-06]: Route53 and S3 collected once per account (global services), all other collectors run per-region
- [02-06]: Categorizer respects prior pipeline exclusions: resources with counted=False and skip_reason are not re-categorized
- [02-06]: Asset dedup and managed service exclusion check counted is False (explicit), not falsy None, to process uncategorized resources
- [02-06]: Legacy code (aws_discovery/, shared/, main.py) deleted after integration tests confirm Phase 2 works
- [02.1-02]: Removed import ipaddress from ip_counter.py -- only needed by deleted count_ips(), not by deduplicate_ips_per_vpc()
- [02.1-02]: Updated ip_counter module docstring to reflect per-VPC deduplication scope only (removed "IP extraction" reference)
- [02.1-01]: Thread-local _retry_context for runtime on_retry injection (zero changes to 20+ collector decorators)
- [02.1-01]: classify_error() called twice per retry (once in decorator, once in callback) -- acceptable for pure string matching
- [02.1-01]: Non-rate-limit transient errors (network, 503) do NOT affect RateLimiter state
- [02.1-01]: Dispatch loop refactored from dict comprehension to sequential for-loop for delay injection
- [03-01]: Auth validator uses exception class name matching for Azure SDK exceptions since SDK may not be installed
- [03-01]: Client factory uses _try_create wrapper so missing optional SDK packages set client to None
- [03-01]: _extract_resource_group uses case-insensitive segment matching per Azure ARM behavior
- [03-01]: Subscription filtering uses case-insensitive matching for display names
- [03-01]: PostgreSQL uses PostgreSQLFlexibleManagementClient (flexible servers API, not legacy single server)
- [03-02]: DHCP configs extracted from VNet details as separate CloudResource (resource_id={vnet_id}/dhcpOptions, no SDK call)
- [03-02]: DNS record type parsed from full ARM type path via split('/')[-1] (e.g., Microsoft.Network/dnszones/A -> A)
- [03-02]: Per-zone error isolation in DNS record collectors (try/except per zone, log warning, continue)
- [03-02]: NIC private IPs extracted from ip_configurations; public IPs collected separately per Pitfall 4
- [03-03]: VMs set ip_addresses=[] with NIC IDs in details -- NICs collected separately as standalone assets
- [03-03]: VMSS instances enumerated individually per scale set with per-instance NIC IP extraction
- [03-03]: All PaaS databases set ip_addresses=[] -- IPs attributed via private endpoints per CONTEXT.md
- [03-03]: Redis includes static_ip in ip_addresses when set, otherwise empty
- [03-03]: App Services/Functions parse comma-separated inbound+outbound IPs with deduplication
- [03-03]: Container Apps uses collect_azure_container_apps_with_client pattern for graceful SDK fallback
- [03-03]: VPN gateways iterated per unique resource group from VNet discovery (no subscription-level API)
- [03-04]: Token-free collectors use @retry_with_backoff(max_retries=3) consistent with all other Azure collectors
- [03-04]: Management groups attributed to the scanning subscription (tenant-level API)
- [03-04]: Storage containers collected per-account with try/except for blob-access-disabled accounts
- [03-04]: discover_account() collects VNets first for dependency ordering (subnets, DHCP, peerings, VPN gateways)
- [03-04]: 429 throttle detection in _safe_collect checks exc.status_code and emits visible WARNING per CONTEXT.md
- [03-04]: Azure XLS detail sheet dynamically adds Resource Group column based on provider parameter
- [03-04]: Legacy azure_discovery/ and root test_checkpoint.py deleted after all 653 tests pass
- [04-01]: Auth validator uses exception class name matching for GCP SDK exceptions since SDK may not be installed
- [04-01]: Client factory uses _try_create wrapper so missing optional SDK packages set client to None
- [04-01]: DNS client NOT shared across projects -- created per-project in discover_account() per Pitfall 1
- [04-01]: Include/exclude glob filtering uses fnmatch.fnmatch -- include takes precedence over exclude
- [04-01]: API pre-checks use batch_get_services for 4 APIs -- PermissionDenied treats all as unavailable, transient errors assume enabled
- [04-01]: GCPClients wraps 11 clients (9 compute, 1 container, 1 sqladmin) -- all project-agnostic
- [04-02]: VPC networks use global list() (no aggregatedList for networks) with self_link as resource_id
- [04-02]: Subnets use aggregatedList with empty scoped list skip per Pitfall 2
- [04-02]: Reserved IPs combine regional aggregatedList + global list in a single collector function
- [04-02]: DNS records enumerate all types (SOA, NS, A, AAAA, CNAME, MX, TXT, etc.) per CONTEXT.md decision
- [04-02]: A/AAAA record IP addresses extracted from rrdatas into ip_addresses field
- [04-02]: Per-zone error isolation wraps each zone's record enumeration in try/except (consistent with Azure DNS pattern)
- [04-03]: Forwarding rule IP uses getattr fallback chain (I_p_address, i_p_address, ip_address) for SDK attribute name resilience
- [04-03]: Cloud SQL collector returns [] when sqladmin_service is None (graceful fallback when google-api-python-client not installed)
- [04-03]: Instance network_i_p (private) and access_config nat_i_p (public) correctly extracted per Pitfall 6
- [04-04]: GKE clusters registered as token-free (metadata only -- nodes already counted as gcp-vm)
- [04-04]: Storage buckets use optional google-cloud-storage import with graceful ImportError fallback (not added to requirements.txt)
- [04-04]: API enablement flags (compute_enabled, dns_enabled, sqladmin_enabled, container_enabled) control collector skip per project
- [04-04]: Legacy gcp_discovery/ deleted after 853 tests confirm zero regressions (consistent with 03-04 azure_discovery/ deletion)
- [05-01]: EventBridge uses per-subscriber fan-out queues (not single shared queue) for multi-client SSE support
- [05-01]: TemplateResponse uses new API with request as first parameter (avoids deprecation warning)
- [05-01]: ScanManager accepts config_path parameter for testable config persistence via tmp_path
- [05-02]: SSE endpoint tests use threaded emit_done() to avoid blocking the streaming response
- [05-02]: DashboardProgressTracker emits progress_{provider_lower} event names for HTMX sse-swap matching
- [05-02]: Tab endpoints return full #tab-container div (tab bar + content) for HTMX HATEOAS pattern
- [05-02]: Base.html uses hx-get=/tab/progress hx-trigger=load for initial tab content load
- [05-03]: Partials router uses /partials prefix for all HTMX fragment endpoints
- [05-03]: Filter options built from ALL resources (not filtered subset) for consistent dropdown population
- [05-03]: Summary calculation reuses counting pipeline (calculate_account_tokens, deduplicate_ips_per_vpc) for CLI-consistent output
- [05-03]: Results/Summary templates follow Plan 02 tab-container HTMX swap pattern (not base.html extensions)
- [05-04]: Auth check runs all 3 providers via asyncio.to_thread to avoid blocking async loop
- [05-04]: Scan pipeline runs in executor thread, reuses full CLI counting pipeline for consistency
- [05-04]: Download endpoint validates basename==filename and extension whitelist for path traversal prevention
- [05-04]: CLI --web flag early-exits before provider selection, handles ImportError gracefully
- [05-04]: Wizard steps use HTMX hx-post/hx-target for server-controlled step progression
- [06-01]: preflight check_platform() returns dict so callers can inspect results without re-running detection
- [06-01]: print_preflight_warnings() hard-exits only on Python < 3.10; all other issues are warn-only on stderr
- [06-01]: SIGTERM registered only on sys.platform != 'win32' -- SIGINT is the primary interrupt on Windows
- [06-01]: Bash setup script does NOT prompt to install CLIs (just prints URL) -- Linux/macOS users use package managers
- [06-01]: PowerShell Test-CLI() prompts to open browser in interactive mode, skips when ProviderChoice is set (CI mode)
- [06-02]: CI matrix uses os x python-version product: 3 platforms x 3 Python versions = 9 jobs per matrix job
- [06-02]: Integration test commands updated from python main.py to python -m cloud_usage.cli (main.py deleted in Phase 2)
- [06-02]: sign-ps1.yml: CN=Infoblox UDDI Estimator, 2-year expiry, -HashAlgorithm sha256 added
- [06-02]: enterprise-resign.md covers both paths: enterprise CA signing and self-signed cert import
- [07-01]: record_success() uses immediate reset (delay=0.0, consecutive_rate_limits=0) -- not gradual decay -- per CONTEXT.md locked decision
- [07-01]: record_success() called at account granularity in orchestrator (once per successful discover_account()), not per individual collector
- [07-01]: CheckpointEngine creation moved before _build_discovery_providers() in dashboard _run_scan_pipeline() to ensure it is in scope
- [07-02]: sys.modules injection used for azure.identity and google.auth stubs since SDKs not installed in test env; avoids requiring cloud SDKs to run unit tests
- [07-02]: Pre-import GCP provider modules before mock.patch to ensure cloud_usage.providers.gcp is in sys.modules (lazy imports require this)
- [08-01]: _enumerate_accounts return type changed from dict[str, list[dict]] to dict[str, dict] with 'accounts' and 'error' keys for error transparency in wizard
- [08-01]: enumerate_gcp_projects called with all 6 positional args (credentials, adc_project, None, None, include, exclude) in both dashboard call sites
- [08-01]: Azure subscriptions use 'id' key directly (no dead 'subscription_id' fallback) matching list_subscriptions() actual return dict structure
- [08-01]: Failed providers show inline error in wizard step 3 but do not block form submission; only all-providers-fail scenario disables Next button
- [08-02]: Azure display_name fallback uses 'or' operator (s.get('display_name') or s.get('id', '')) so empty-string falls back to id -- dict.get() default only triggers on missing key
- [08-02]: Parity tests mock at SDK level (enumerate_gcp_projects) not wrapper level (_enumerate_accounts) to exercise real dashboard code path
- [08-02]: call_args.args tuple length == 6 is the definitive assertion for positional vs keyword arg usage in enumerate_gcp_projects calls
- [Phase 09-01]: [09-01]: AWSDiscoveryProvider checkpoint skip guard symmetric with Azure/GCP; skip triggered when account_id in checkpoint.providers['aws'].completed_accounts
- [Phase 09-01]: [09-01]: asset_dedup.DDI_TYPES replaced with import from categorizer -- removes AWS-only 5-item set, now 16 types covering all 3 providers
- [Phase 09-01]: [09-01]: DashboardProgressTracker.finish() no longer calls emit_done(); finally block in _run_scan_pipeline is sole owner of scan_complete SSE emission
- [v1.1 Roadmap]: NIOS pipeline isolated in src/cloud_usage/nios/ -- no imports from providers/, counting/, discovery/, or schema/resource.py
- [v1.1 Roadmap]: lxml>=5.3.0 is the only new dependency; tarfile r:gz mode (not r|gz) avoids 14x CPython slowdown bug (#121109)
- [v1.1 Roadmap]: Two-pass parser design: members pass first to build virtual_oid->hostname map, then all objects in second pass with member IDs resolvable
- [v1.1 Roadmap]: Active IP dedup uses set per network view (not global) -- prevents undercounting in overlapping RFC1918 environments
- [v1.1 Roadmap]: Phase 15 dashboard upload saves file to disk path before background thread starts -- prevents FastAPI UploadFile closed-before-read bug (#10936)
- [Phase 10-01]: PROPERTY NAME='__type' VALUE pattern confirmed empirically — elem.get('type') returns None; Plans 02/03 must use PROPERTY child iteration for type extraction
- [Phase 10-01]: Only LEASE is MEMBER_SCOPED (vnode_id field); all other DHCP/DNS families are GRID_LEVEL in ZF NIOS backup — RESEARCH.md hypothesis was incorrect
- [Phase 10-01]: Member type is .com.infoblox.one.virtual_node (not 'Member:Grid'); host_name is hostname field; virtual_oid is OID key; DATABASE element has VERSION as XML attribute
- [Phase 10-02]: vnode_id is the attribution field on LEASE objects (not virtual_oid) — lease.vnode_id -> virtual_node.virtual_oid -> host_name
- [Phase 10-02]: Exact basename match for onedb.xml (Path(member.name).name == 'onedb.xml') — endswith check falsely matched 'notonedb.xml'
- [Phase 10-02]: lxml 6.x iterparse: options passed as direct kwargs not via XMLParser object — parser= kwarg not supported in lxml 6.x

### Pending Todos

None.

### Blockers/Concerns

- [Phase 11]: Host Object parent-OID field name in onedb.xml requires validation against ZF reference backup during implementation — FEATURES.md rates MEDIUM confidence on exact XML property name
- [Phase 11]: CNAME condition for Host Object expansion (whether alias is defined) requires validation against ZF backup during implementation

## Session Continuity

Last session: 2026-02-28
Stopped at: v1.1 roadmap created — 6 phases (10-15), 37 requirements mapped 100%
Resume with: `/gsd:plan-phase 10`
