# External Integrations

**Analysis Date:** 2026-02-18

## APIs & External Services

**AWS:**
- EC2 API - Instance, VPC, subnet, and load balancer enumeration
  - SDK/Client: boto3 (via `aws_discovery/utils.py` `get_aws_client()`)
  - Auth: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, or AWS_PROFILE (SSO)
  - Operations: DescribeInstances, DescribeVpcs, DescribeSubnets, DescribeSecurityGroups

- Route53 API - DNS zone and record discovery
  - SDK/Client: boto3 (via `aws_discovery/aws_discovery.py`)
  - Auth: Same as EC2 API
  - Operations: ListHostedZones, ListResourceRecordSets

- ELBv2 API - Application and Network Load Balancer discovery
  - SDK/Client: boto3
  - Auth: Same as EC2 API
  - Operations: DescribeLoadBalancers, DescribeTargetGroups

- ELB API - Classic Load Balancer discovery
  - SDK/Client: boto3
  - Auth: Same as EC2 API
  - Operations: DescribeLoadBalancers, DescribeInstanceHealth

- STS API - Credential validation and account identity
  - SDK/Client: boto3 (via `main.py` and `aws_discovery/discover.py`)
  - Auth: Same credential chain
  - Operations: GetCallerIdentity (for auth check)

**Azure:**
- Azure Resource Manager API - Network and DNS resource enumeration
  - SDK/Client: azure-mgmt-network, azure-mgmt-compute, azure-mgmt-dns
  - Auth: AZURE_CLIENT_ID + AZURE_CLIENT_SECRET + AZURE_TENANT_ID or az login or interactive browser
  - Resources: VirtualNetworks, Subnets, NetworkInterfaces, LoadBalancers, PublicIPAddresses

- Azure Compute API - Virtual machine discovery
  - SDK/Client: azure-mgmt-compute
  - Auth: Same credential chain
  - Operations: List VMs, get disk/NIC details, instance state

- Azure DNS API - Public DNS zone and record enumeration
  - SDK/Client: azure-mgmt-dns
  - Auth: Same credential chain
  - Operations: List DNS zones, list records within zones

- Azure Private DNS API - Private DNS zone discovery
  - SDK/Client: azure-mgmt-privatedns
  - Auth: Same credential chain
  - Operations: List private DNS zones, list records

- Azure Subscription API - Multi-subscription enumeration
  - SDK/Client: azure-mgmt-subscription
  - Auth: Same credential chain
  - Operations: List all subscriptions, list regions per subscription, get locations

- Azure CLI (az command) - Credential cache lookup and project context
  - Invocation: `azure_discovery/config.py` (subprocess calls)
  - Purpose: Fallback credential discovery, subscription enumeration
  - Detected paths: Windows Program Files, standard PATH, AppData

**GCP:**
- Compute Engine API - Virtual machine and network discovery
  - SDK/Client: google-cloud-compute (ComputeV1 client)
  - Auth: GOOGLE_APPLICATION_CREDENTIALS or gcloud application-default-login
  - Operations: List instances, list networks, list subnetworks, list regions

- Cloud DNS API - DNS zone and record discovery
  - SDK/Client: google-cloud-dns (v0.35.1)
  - Auth: Same credential chain
  - Operations: List managed zones, list resource record sets

- Google Auth Library - Credential chain management
  - SDK/Client: google-auth
  - Purpose: Default credential detection from environment/metadata
  - Supports: Service accounts, ADC (Application Default Credentials), metadata service

- gcloud CLI - Project defaults and credential validation
  - Invocation: `gcp_discovery/config.py` (subprocess calls)
  - Purpose: Project ID detection, credential validation
  - Operations: config get-value project, auth list

## Data Storage

**Databases:**
- None - This is a stateless discovery tool

**File Storage:**
- Local filesystem only
  - Output directory: `output/` (configurable via --checkpoint-file)
  - Files: JSON, CSV, or TXT discovery results
  - Format: `{provider}_native_objects_{timestamp}.{format}` (defined in `shared/constants.py`)

**Caching:**
- In-memory: Credential objects cached in module globals (`azure_discovery/config.py` line 23-24)
- File-based checkpoint (Azure only):
  - Location: `output/azure_discovery_checkpoint.json` (default)
  - Purpose: Resume interrupted multi-subscription scans
  - Content: Timestamp, args, completed subscriptions, discovered objects, errors
  - Interval: Configurable (default: every 50 subscriptions)

## Authentication & Identity

**Auth Provider:**
- Multi-strategy native cloud auth (no third-party auth service)

**AWS Authentication:**
- Strategy: Credential chain (profile → environment keys → assume role)
  - AWS SSO profiles via `aws sso login --profile {name}`
  - Environment: AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY
  - AWS_PROFILE env var for named profile
  - Fallback: IAM role (if running in EC2)
  - Implementation: `aws_discovery/config.py` (AWSConfig class)

**Azure Authentication:**
- Strategy: Chained credential providers (in priority order)
  - Service Principal: AZURE_CLIENT_ID + AZURE_CLIENT_SECRET + AZURE_TENANT_ID
  - SharedTokenCache: Tokens from `az login` SSO session (preferred)
  - InteractiveBrowserCredential: Launches browser for SSO (fallback)
  - Windows: Skips AzureCliCredential subprocess (avoids encoding issues)
  - Implementation: `azure_discovery/config.py` (get_azure_credential function, lines 223-275)

**GCP Authentication:**
- Strategy: Default credential chain
  - Service account JSON: GOOGLE_APPLICATION_CREDENTIALS env var
  - Application Default Credentials (ADC): gcloud login cache
  - Metadata service: Running in GCP (Compute Engine, Cloud Run)
  - Implementation: `gcp_discovery/config.py` (get_gcp_credential function)

**Credential Validation:**
- AWS: `main.py` _check_aws_auth() - STS GetCallerIdentity call
- Azure: `main.py` _check_azure_auth() - Token generation test
- GCP: `main.py` _check_gcp_auth() - Credential refresh test
- Entry point: `--check-auth` flag on any provider command

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking integration

**Logs:**
- Approach: Python logging module
  - Level: WARNING (configured in `aws_discovery/aws_discovery.py`)
  - Suppressed modules: boto3, botocore, urllib3 (verbose by default)
  - Output: stdout/stderr via argparse
  - Checkpoint saves: File-based JSON logs in output directory

**Discovery Progress:**
- tqdm progress bars (visible in stdout during discovery)
- Resource counts logged at completion
- Error accumulation in Azure checkpoint (stores errors alongside progress)

## CI/CD & Deployment

**Hosting:**
- GitHub repository: `stefanriegel/Infoblox-Universal-DDI-cloud-usage`
- Execution: Local CLI tool or GitHub Actions

**CI Pipeline:**
- GitHub Actions (.github/workflows/ci.yml)
  - Setup validation: Runs setup_venv.sh/ps1 on Windows, macOS, Linux
  - Lint check: flake8 + black on Ubuntu
  - Unit tests: pytest on all platforms (Windows, macOS, Linux)
  - Integration tests: AWS/Azure/GCP on Ubuntu with real credentials (dev branch only)
  - Triggers: Push to dev branch, PRs to dev branch

**Code Signing:**
- PowerShell script signing (.github/workflows/sign-ps1.yml)
- Self-signed certificate: `cert.cer` (for setup_venv.ps1)

## Environment Configuration

**Required env vars (provider-specific):**

AWS:
- `AWS_PROFILE` OR (`AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`)
- `AWS_REGION` (optional, defaults to us-east-1)

Azure:
- `AZURE_SUBSCRIPTION_ID` (auto-discovered via az CLI if not set)
- Optional service principal: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`

GCP:
- `GOOGLE_CLOUD_PROJECT` (auto-discovered from gcloud if not set)
- `GOOGLE_APPLICATION_CREDENTIALS` (optional, path to service account key)

**Secrets location:**
- AWS: ~/.aws/credentials (profile-based) or environment variables
- Azure: System token cache (via az login) or environment service principal
- GCP: ~/.config/gcloud/ (ADC cache) or GOOGLE_APPLICATION_CREDENTIALS file

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Cloud CLI Tool Integration

**AWS CLI:**
- Version check: >= 2.0.0 enforced (v1 lacks SSO support)
- Check: `aws_discovery/discover.py` check_awscli_version()
- Usage: Prerequisite for SSO login workflow (`aws sso login --profile {name}`)

**Azure CLI:**
- Optional but recommended for SSO (`az login`)
- Platform-specific detection: Searches Program Files on Windows
- Fallback path: /usr/bin/az (macOS/Linux)
- Used for: Subscription enumeration, region discovery, auth validation

**Google Cloud SDK:**
- Version check: >= 300.0.0 required
- Check: `gcp_discovery/discover.py` check_gcloud_version()
- Usage: Project ID detection, credential validation, project configuration

## Data Flow Summary

1. **User invokes:** `python main.py {aws|azure|gcp} [options]`
2. **Credential validation:** Checks auth via cloud provider STS/Token APIs
3. **Region/Subscription enumeration:** Uses SDK clients to list available scopes
4. **Parallel discovery:** ThreadPoolExecutor spawns workers per region/subscription
5. **API calls:** Each worker calls cloud provider APIs (EC2, DNS, Network, etc.)
6. **Resource extraction:** Raw API responses parsed into standardized objects
7. **Token calculation:** Licensing calculator computes token requirements
8. **Output generation:** Results formatted as JSON/CSV/TXT to `output/` directory
9. **Checkpoint (Azure only):** Progress saved after each subscription batch

---

*Integration audit: 2026-02-18*
