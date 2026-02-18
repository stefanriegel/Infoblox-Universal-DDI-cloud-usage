# Architecture

**Analysis Date:** 2026-02-18

## Pattern Overview

**Overall:** Multi-cloud discovery orchestrator with provider-specific implementations and shared infrastructure abstraction

**Key Characteristics:**
- Template Method pattern for cloud-agnostic discovery (`BaseDiscovery` in `shared/base_discovery.py`)
- Provider-specific implementations (AWS, Azure, GCP) extend the base class with cloud-native API calls
- Factory pattern for credential handling (cloud-specific auth in each provider's config module)
- Pipeline architecture: Discovery → Resource Counting → Token Calculation → Output Generation

## Layers

**Entry Point Layer:**
- Purpose: User command invocation and credential validation
- Location: `main.py`, `aws_discovery/discover.py`, `azure_discovery/discover.py`, `gcp_discovery/discover.py`
- Contains: CLI argument parsing, pre-flight auth checks, orchestration of discovery flow
- Depends on: Cloud-specific discovery modules, shared utilities
- Used by: Command-line invocation

**Discovery Layer:**
- Purpose: Cloud-native resource discovery across regions/subscriptions
- Location: `aws_discovery/aws_discovery.py`, `azure_discovery/azure_discovery.py`, `gcp_discovery/gcp_discovery.py`
- Contains: Resource enumeration methods, pagination handling, parallel discovery with ThreadPoolExecutor
- Depends on: Cloud SDK clients (boto3, Azure SDK, Google Cloud), base class, shared output utilities
- Used by: Discover entry points

**Configuration Layer:**
- Purpose: Cloud provider credentials and region/resource scope management
- Location: `shared/config.py`, `aws_discovery/config.py`, `azure_discovery/config.py`, `gcp_discovery/config.py`
- Contains: Dataclasses for config (BaseConfig, DiscoveryConfig, provider-specific configs), credential retrieval, region enumeration
- Depends on: Cloud CLI tools (aws, az, gcloud), environment variables
- Used by: Discovery implementations, entry points

**Analysis Layer:**
- Purpose: Transform raw discovered resources into licensing requirements
- Location: `shared/resource_counter.py`, `shared/licensing_calculator.py`
- Contains: DDI object identification, active IP deduplication, token calculation per Infoblox licensing model
- Depends on: Constants, discovered resource objects
- Used by: Discovery implementations, output formatting

**Output Layer:**
- Purpose: Persist and format discovery results for various consumers
- Location: `shared/output_utils.py`
- Contains: CSV/JSON/TXT serialization, discovery summary printing, proof manifests
- Depends on: Resource counter results, file I/O
- Used by: Discover entry points

**Shared Infrastructure:**
- Purpose: Reusable utilities and constants across all providers
- Location: `shared/constants.py`, `shared/__init__.py`
- Contains: Resource type mappings, token calculation constants, DDI object definitions
- Depends on: None (foundational)
- Used by: All layers

## Data Flow

**Credential Flow:**
1. Main entry point validates provider credentials (aws-cli, gcloud, az-cli)
2. Provider-specific config module calls credential getter (AWS: boto3.Session, Azure: azure-identity, GCP: google.auth.default)
3. Discovery implementation receives credential-authenticated clients
4. API calls made with authenticated clients

**Discovery Flow:**

1. **Initialization Phase**
   - CLI parses arguments (provider, format, worker count, output directory)
   - Entry point (discover.py) validates cloud CLI version and credentials
   - Fetches all available regions/subscriptions/projects from cloud provider
   - Creates discovery instance with populated config

2. **Resource Enumeration Phase**
   - `discover_native_objects(max_workers=N)` spawns ThreadPoolExecutor
   - Regional discovery methods called in parallel: `_discover_region()` (AWS), `_discover_subscription()` (Azure), `_discover_zone()` (GCP)
   - Each regional task discovers specific resource types (VMs, networks, load balancers, DNS)
   - Results cached in `_discovered_resources` to prevent re-discovery

3. **Resource Classification Phase**
   - `count_resources()` analyzes discovered objects
   - `ResourceCounter.count_resources()` classifies each resource
   - DDI objects: Resources in `DDI_RESOURCE_TYPES` (subnets, VPCs, DNS zones, records)
   - Active IPs: Extracted from resource details (private_ip, public_ip, ipv6_ips fields)
   - IP space deduplication: IPs grouped by inferred subnet/space to avoid overcounting

4. **Licensing Calculation Phase**
   - `UniversalDDILicensingCalculator.calculate_from_discovery_results()` computes tokens
   - Token calculation: DDI objects ÷ 25, Active IPs ÷ 13, Assets ÷ 3
   - Breakdown by resource type and IP source for transparency
   - Proof manifest generated (resource hash, scope, regions scanned) for audit trail

5. **Output Persistence Phase**
   - Summary printed to console (discovered counts, DDI breakdown, IP sources)
   - If `--full` flag: `save_discovery_results()` exports detailed resource lists (CSV/JSON/TXT)
   - Licensing CSV exported for Sales Engineers
   - Text summary exported for human review
   - Proof manifest (JSON) exported for licensing audit

**State Management:**
- Discovered resources cached in `_discovered_resources` instance variable (BaseDiscovery)
- Results are immutable after discovery phase completes
- Each provider session is independent (no cross-cloud state)
- Checkpoint support for Azure (resume capability via `--resume` flag for long discovery runs)

## Key Abstractions

**BaseDiscovery:**
- Purpose: Template for cloud discovery implementations
- Examples: `aws_discovery/aws_discovery.py:AWSDiscovery`, `azure_discovery/azure_discovery.py:AzureDiscovery`, `gcp_discovery/gcp_discovery.py:GCPDiscovery`
- Pattern: Abstract method `discover_native_objects()` overridden per provider; shared `count_resources()` and `save_discovery_results()` implementations
- Key methods: `_format_resource()` (standardizes resource schema), `_extract_ips_from_details()`, `_get_resource_tags()` (provider-agnostic helpers)

**ResourceCounter:**
- Purpose: Categorize discovered resources and count DDI objects, active IPs, assets
- Examples: `shared/resource_counter.py` (single class, instantiated per provider)
- Pattern: Analyzes resource_type and IP fields to classify; tracks breakdown by region, IP source
- Key methods: `_get_ddi_objects()`, `_get_active_ip_pairs()`, `_calculate_active_ip_breakdown_by_space()`

**UniversalDDILicensingCalculator:**
- Purpose: Convert resource counts into Management Token requirements per Infoblox SKU
- Examples: `shared/licensing_calculator.py` (implements calculation rules for AWS, Azure, GCP)
- Pattern: Resource counts → Token packs (1000-token bundles) with breakdown visibility
- Key methods: `calculate_from_discovery_results()`, `export_csv()`, `export_proof_manifest()`

**DiscoveryConfig:**
- Purpose: Immutable configuration for a discovery run
- Examples: Dataclass with regions, output_directory, output_format, provider fields
- Pattern: Created by entry point, passed to discovery implementations, ensures consistent scope

## Entry Points

**`main.py`:**
- Location: `/Users/sr/Documents/coding/Infoblox-Universal-DDI-cloud-usage/main.py`
- Triggers: User runs `python main.py <provider> [--format] [--workers] [--check-auth]`
- Responsibilities: Provider selection, argument parsing, delegate to provider-specific discover.py, auth check mode
- Routes to: `aws_discovery/discover.py:main()`, `azure_discovery/discover.py:main()`, `gcp_discovery/discover.py:main()`

**`aws_discovery/discover.py:main()`:**
- Location: `/Users/sr/Documents/coding/Infoblox-Universal-DDI-cloud-usage/aws_discovery/discover.py`
- Triggers: `python main.py aws` or direct invocation
- Responsibilities: AWS CLI validation, credential checks, region enumeration, discovery orchestration, licensing export
- Returns: Exit code 0 (success) or 1 (failure)

**`azure_discovery/discover.py:main()`:**
- Location: `/Users/sr/Documents/coding/Infoblox-Universal-DDI-cloud-usage/azure_discovery/discover.py`
- Triggers: `python main.py azure` with optional checkpoint flags
- Responsibilities: Azure credential validation, subscription enumeration, parallelized subscription discovery, checkpoint/resume for fault tolerance
- Special: Supports `--resume` flag to continue interrupted runs

**`gcp_discovery/discover.py:main()`:**
- Location: `/Users/sr/Documents/coding/Infoblox-Universal-DDI-cloud-usage/gcp_discovery/discover.py`
- Triggers: `python main.py gcp`
- Responsibilities: gcloud CLI validation, credential checks, zone enumeration, discovery orchestration, licensing export

## Error Handling

**Strategy:** Fail-fast on credentials, graceful degradation per-resource/per-region

**Patterns:**

1. **Pre-flight Validation (Discovery Entry Points)**
   - CLI version checks (aws-cli v2+, gcloud v300+, az-cli)
   - Credential validation with test API call (AWS STS, Azure Token endpoint, GCP auth)
   - Exit with clear error message and remediation steps if credentials missing

2. **Regional Discovery Resilience (Discovery Implementations)**
   ```python
   try:
       region_resources = self._discover_region(region)
   except Exception as e:
       self.logger.error(f"Error discovering region {region}: {e}")
       # Continue to next region, don't fail entire discovery
   ```
   - Each region's failure logged but doesn't halt discovery
   - Partial results still processed

3. **Azure API Retry (AzureDiscovery)**
   - `_retry_api_call()` wraps Azure SDK calls with exponential backoff (1s, 2s, 4s...)
   - Configurable retry attempts (default 3), used for transient failures
   - Permanent errors logged and re-raised

4. **Resource-Level Error Tolerance**
   - Unknown resource types logged as "unknown" for debugging
   - Invalid IP fields skipped silently
   - Missing tags default to empty dict

## Cross-Cutting Concerns

**Logging:**
- Framework: Python logging module
- Level: WARNING (suppress INFO from cloud SDKs)
- Suppressed modules: boto3, botocore, urllib3, azure, google.auth
- Usage: Warning-level logs for discovery errors, debug logs for region completion
- File: Each discovery class sets level=WARNING in __init__

**Validation:**
- Credentials: Pre-discovery CLI checks + API test calls
- Output format: ArgumentParser choices constraint (json, csv, txt)
- Regions: Cloud provider validation (aws ec2 describe-regions, az account list-locations, gcloud compute regions list)
- Resource schema: _format_resource() ensures consistent field structure

**Authentication:**
- AWS: boto3 Session (respects AWS_PROFILE, AWS_ACCESS_KEY_ID env vars, ~/.aws/credentials)
- Azure: azure-identity ChainedTokenCredential (tries EnvironmentCredential, SharedTokenCacheCredential, AzureCliCredential)
- GCP: google.auth.default (respects GOOGLE_APPLICATION_CREDENTIALS, gcloud default credentials)

**Parallelization:**
- Framework: ThreadPoolExecutor from concurrent.futures
- Workers: Configurable per-provider (default 8), capped at available region/subscription count
- Progress: tqdm progress bars for user feedback
- Thread safety: Immutable resource objects, shared list is thread-safe append-only

---

*Architecture analysis: 2026-02-18*
