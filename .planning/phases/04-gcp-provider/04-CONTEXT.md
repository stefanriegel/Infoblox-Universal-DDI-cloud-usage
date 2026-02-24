# Phase 4: GCP Provider - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

GCP project discovery plugged into the proven pipeline with per-project rate limiting. Users can run a complete GCP scan across all projects, using aggregatedList endpoints for efficiency, validated against a known 87-project reference environment. The counting, token calculation, and report pipeline from Phase 2 are reused -- Phase 4 adds GCP-specific authentication, resource collectors, project enumeration, and rate limiting coordination.

</domain>

<decisions>
## Implementation Decisions

### GCP resource coverage
- **Core resources from legacy + expansion**: Legacy covers compute instances, VPC networks, subnets, reserved IPs, Cloud DNS (zones + records). Expand with Cloud SQL, GKE clusters, and forwarding rules (load balancers)
- **Cloud SQL instances**: Discover as managed assets with private/public IPs. Most common GCP database service
- **GKE clusters**: Discover for audit trail but mark as **token-free** (metadata only). Nodes are compute instances already discovered separately. No double-counting
- **Forwarding rules (load balancers)**: Discover as managed assets. Each forwarding rule has an IP address. Direct equivalent of AWS ELB/NLB and Azure LB
- **VPC networks as DDI**: VPC networks count as DDI objects (network containers, like AWS VPCs and Azure VNets)
- **Subnets as DDI**: Subnets count as DDI objects (address ranges)
- **Skip DHCP for GCP**: GCP manages DHCP internally with no user-visible DHCP objects. Report DDI DHCP count as 0 for GCP
- **Full DNS record enumeration**: Enumerate all DNS record types including SOA and NS (no filtering). Consistent with Azure approach
- **Drop managed-service label exclusion**: Do NOT use the legacy label-based exclusion (goog-managed-by, gke-managed, etc.). Use the explicit token-free type list (ASSET-05) instead. If a resource has IPs and isn't on the token-free list, count it
- **Include all IP-bearing resources**: If a discovered GCP resource has IP addresses, it counts as a managed asset unless explicitly on the token-free list

### Token-free resources (ASSET-05)
- **Exactly the ASSET-05 list**: Compute Persistent Disks, Instance Groups, URL Maps, Cloud Monitoring Metric Stats, Network Connectivity Locations, Cloud Storage Bucket Policies, Cloud Storage Buckets
- **GKE clusters added as token-free**: Discovered for audit trail, marked counted=False
- **No additional audit-only types**: Keep scope tight to ASSET-05 + GKE clusters. Resources without IPs that aren't on the list naturally get counted=False

### Reference validation (REF-01)
- **Legacy output as baseline**: Existing output from legacy gcp_discovery/ tool run against the 87-project environment serves as the reference
- **Superset match**: New counts must be >= legacy counts for shared resource types (VMs, VPCs, subnets, DNS zones, DNS records, reserved IPs). New resource types (Cloud SQL, forwarding rules, GKE) are additive
- **No special comparison tooling**: Standard XLS output with detail + summary sheets is sufficient. Manual comparison of legacy vs. new outputs
- **Delete legacy gcp_discovery/ after validation**: Delete once new code is validated against the 87-project environment. Consistent with Azure approach

### Authentication & project enumeration
- **Auth methods**: Support ADC (gcloud auth application-default login) AND service account key files via google.auth.default() which auto-detects credential type. Also supports compute engine metadata credentials
- **Full project enumeration**: Replicate all legacy enumeration capabilities:
  - search_projects() for multi-project discovery across org
  - `--project` flag for single-project mode (bypasses enumeration)
  - `--org-id` for scoping enumeration to a specific organization
  - `--include-projects` / `--exclude-projects` glob filters
- **Per-project API pre-checks**: Pre-check Compute and DNS API enablement per project using ServiceUsage API before scanning. Skip disabled projects with [Skip] log line
- **Auth doctor integration**: Validate credentials work + count accessible projects. Auto-detect GCP credentials (no explicit --provider flag needed)
- **Contextual error suggestions**: Suggest `gcloud auth application-default login` or `export GOOGLE_APPLICATION_CREDENTIALS=...` depending on error type

### GCP rate limiting strategy
- **Per-project tracking**: Use Phase 1 RateLimiter with per-project tracking. When one project hits 429, only that project backs off. Other projects continue unaffected
- **Dual-layer retry**: GCP SDK built-in retry handles per-request errors + our RateLimiter adds cross-project coordination within the same project scope
- **Reactive 429 handling**: Match AWS/Azure UX -- react to 429s with retry+backoff, consistent experience across all three providers
- **Skip project on persistent failure**: If throttle persists beyond max retries, skip the project and continue with remaining (error isolation)

### API pattern
- **aggregatedList where available**: Use aggregatedList endpoints for resources that support it (instances, disks, addresses, subnetworks, forwarding rules). Fall back to per-region/project listing for resources without aggregatedList support
- **Reduces API call volume**: aggregatedList returns all regions in one call vs. N calls for N regions. Critical for 87-project environment efficiency

### Legacy code strategy
- **Fresh rewrite**: Rewrite all collectors from scratch following the AWS/Azure collector pattern (CloudResource schema, @retry_with_backoff decorator, Phase 1 progress tracker)
- **Port enumeration logic, not code**: Replicate the project enumeration behavior (search_projects, org-scoping, API pre-checks, filters) but write new code in the new architecture style
- **Same GCP SDK dependencies**: Use google-cloud-compute, google-cloud-dns, google-cloud-resource-manager, google-cloud-service-usage. Add new packages for Cloud SQL (google-cloud-sql-admin?), GKE (google-cloud-container), etc.

### CLI integration
- **Provider flag**: `--provider gcp` to select GCP scanning. One provider at a time
- **Provider-specific filter flags**: `--include-projects` / `--exclude-projects` (matches legacy naming)
- **Output naming**: `gcp_discovery_YYYY-MM-DD.xlsx` (matches AWS/Azure pattern)
- **Pre-scan summary**: Display project count and org-id (if scoped) before scan starts

### Checkpoint/resume
- **Same checkpoint file**: Provider-scoped keys in shared checkpoint file (e.g., `gcp:project-id:completed`)
- **Auto-skip completed**: Completed projects skipped on resume, failed/pending re-scanned. Same 48h TTL applies
- **Signal handling**: Ctrl+C saves GCP checkpoint state atomically (same behavior as AWS/Azure)

### Report output
- **Full GCP resource paths**: Use GCP resource self-link or project/resource format in detail sheet resource_id column
- **Account column**: Show project ID in the account column
- **Summary by project**: One summary row per project with resource type totals
- **Proof manifest**: Same structure as AWS/Azure with GCP-specific fields (projects, org_id if scoped)
- **Short friendly type names**: Use 'gcp-vm', 'gcp-vpc', 'gcp-subnet', 'gcp-cloud-sql' style (not full GCP API resource paths)

### Claude's Discretion
- Validation testing approach (unit tests with mocks, integration test patterns)
- Exact aggregatedList vs per-region decision per resource type
- SDK client lifecycle management (shared clients, per-project dns client)
- Internal collector module organization
- Concurrency limit for parallel project scanning
- Error handling details per API failure type
- google-cloud-* package version constraints

</decisions>

<specifics>
## Specific Ideas

- "GCP, AWS and Azure should have the same UX experience" -- consistency across all three providers is a core principle. Rate limiting, progress display, error handling, output format should feel the same
- Rewrite collectors from scratch (don't port legacy code). Follow the AWS/Azure collector pattern with CloudResource schema and @retry_with_backoff decorator
- Delete legacy `gcp_discovery/` directory after Phase 4 is validated against 87-project environment
- Use existing Phase 1 progress tracker (not tqdm from legacy code)
- Legacy output from 87-project environment is the validation baseline. New counts must be >= legacy for shared resource types
- aggregatedList endpoints are key efficiency gain over legacy per-region listing

</specifics>

<deferred>
## Deferred Ideas

- `--provider all` multi-provider scan in one run -- deferred until all providers ready
- Cloud Run, Cloud Functions, Memorystore, Spanner, Bigtable discovery -- could be added in a future enhancement phase
- Cloud VPN, Cloud Interconnect, Cloud NAT discovery -- hybrid networking expansion
- Firewall rules discovery for audit trail -- token-free, low priority
- Comparison tooling (--compare flag) for legacy vs. new output -- manual comparison sufficient

</deferred>

---

*Phase: 04-gcp-provider*
*Context gathered: 2026-02-24*
