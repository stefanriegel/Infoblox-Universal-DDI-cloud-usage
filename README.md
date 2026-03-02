# Infoblox Universal DDI Resource Counter

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-v1.2%20Production%20Preview-blue.svg)](https://github.com/stefanriegel/Infoblox-Universal-DDI-cloud-usage)

> **Note**: This tool is a production preview provided for pre-sales estimation purposes. Resource counts should be verified independently before making licensing decisions.

A Python tool that estimates Infoblox Universal DDI management tokens from two sources: (1) cloud discovery across AWS, Azure, and GCP, and (2) NIOS Grid backup analysis for customers migrating from NIOS to UDDI. Produces XLS reports with full traceability. Runs entirely locally — no data leaves the machine.

## Quick Start

**Prerequisites:** Python 3.9+, network access to cloud provider APIs (cloud mode) or a NIOS Grid backup file (NIOS mode)

**Installation:**
```bash
git clone https://github.com/stefanriegel/Infoblox-Universal-DDI-cloud-usage.git
cd Infoblox-Universal-DDI-cloud-usage

# macOS/Linux
./setup_venv.sh

# Windows (PowerShell)
.\setup_venv.ps1

# Windows (batch fallback)
setup_venv.bat

# Activate virtual environment
source venv/bin/activate          # macOS/Linux
& venv\Scripts\Activate.ps1      # Windows PowerShell
```

**Run a cloud scan (interactive mode):**
```bash
cloud-usage
```

Or use flags to bypass the interactive prompt:
```bash
cloud-usage --aws
cloud-usage --azure
cloud-usage --gcp
```

**Launch the web dashboard:**
```bash
cloud-usage --web
# Open http://localhost:8080
```

**Analyze a NIOS Grid backup:**
```bash
cloud-usage --nios /path/to/backup.tar.gz
```

## Installation

### Automated Setup (Recommended)

The setup scripts create a virtual environment and install all dependencies automatically.

**macOS/Linux:**
```bash
./setup_venv.sh
```

**Windows (PowerShell):**
```powershell
.\setup_venv.ps1
```

**Windows (batch fallback — use if PowerShell execution is restricted):**
```batch
setup_venv.bat
```

> The PowerShell script is signed but may be blocked on systems with strict execution policies that do not trust self-signed certificates. Use the batch file in such cases.

### Manual Setup

Use manual setup when automated scripts cannot execute due to system restrictions.

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

**Windows:**
```batch
python -m venv venv
venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

> On Windows, you may need to install the [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) if Azure dependencies fail to install due to cryptography compilation errors.

## Cloud Provider Authentication

### AWS Setup

**AWS CLI / SSO:**
```bash
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"

# Or using profiles / SSO:
export AWS_PROFILE="your_profile"
aws sso login --profile your_profile
```

**Required Permissions:** EC2ReadOnlyAccess, Route53ReadOnlyAccess

### Azure Setup

**Azure CLI:**
```bash
az login --tenant "your-tenant-id"
az account show  # Verify login
```

**Service Principal:**
```bash
export AZURE_CLIENT_ID="your_client_id"
export AZURE_CLIENT_SECRET="your_client_secret"
export AZURE_TENANT_ID="your_tenant_id"
export AZURE_SUBSCRIPTION_ID="your_subscription_id"
```

**Required Permissions:**
- **Reader** — built-in role for subscription-level read access
- **Network Reader** — for network resource discovery across resource groups
- **Management Group Reader** — for multi-subscription discovery via Management Groups

### GCP Setup

**gcloud CLI:**
```bash
gcloud auth login
gcloud auth application-default login
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

**Service Account:**
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

**Required Permissions:** Compute Instance Viewer, Network Viewer, DNS Reader

## How To Use

### Cloud Scan (CLI)

Without flags, `cloud-usage` presents an interactive provider selection menu:

```
Which cloud providers would you like to scan?
  1. AWS
  2. Azure
  3. GCP

Enter selection (e.g., 1,3 or aws,gcp):
```

For scripted or CI use, pass provider flags directly:

```bash
cloud-usage --aws
cloud-usage --azure
cloud-usage --gcp
cloud-usage --aws --azure    # scan multiple providers
```

**Key options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir PATH` | `./output` | Directory for output files and logs |
| `--checkpoint-ttl N` | `48` | Checkpoint TTL in hours |
| `--no-resume` | off | Ignore existing checkpoint and start fresh |
| `--skip-auth-check` | off | Skip the pre-flight auth doctor check |
| `--dry-run` | off | Show scan plan without making API calls |
| `--profile NAME` | — | AWS profile name (boto3 session) |
| `--role-name NAME` | `OrganizationAccountAccessRole` | Cross-account role for AWS Organizations |
| `--include-accounts IDS` | — | Comma-separated AWS account IDs to include |
| `--exclude-accounts IDS` | — | Comma-separated AWS account IDs to exclude |
| `--include-subscriptions IDS` | — | Azure subscription IDs or names to include |
| `--exclude-subscriptions IDS` | — | Azure subscription IDs or names to exclude |
| `--project ID` | — | Single GCP project (skips project enumeration) |
| `--org-id ID` | — | GCP organization ID for project scoping |
| `--include-projects PATTERNS` | — | Comma-separated glob patterns for GCP projects to include |
| `--exclude-projects PATTERNS` | — | Comma-separated glob patterns for GCP projects to exclude |

**Examples:**

```bash
# Interactive mode
cloud-usage

# Scripted mode — single provider
cloud-usage --aws
cloud-usage --azure
cloud-usage --gcp

# Resume from checkpoint (prompted automatically if checkpoint exists)
cloud-usage --aws

# Force fresh scan, ignoring any checkpoint
cloud-usage --aws --no-resume

# Dry run — show scan plan without calling APIs
cloud-usage --aws --dry-run

# Custom output directory
cloud-usage --azure --output-dir /tmp/ddi-results

# Filter to specific Azure subscriptions
cloud-usage --azure --include-subscriptions "sub-id-1,sub-id-2"

# Single GCP project scan
cloud-usage --gcp --project my-gcp-project-id
```

### Web Dashboard

```bash
cloud-usage --web
cloud-usage --web --port 9090    # custom port
```

Open http://localhost:8080 (or your custom port). The dashboard provides:

- **Cloud Scan tab:** interactive provider selection with real-time progress (SSE), results browsing, and output file download
- **NIOS Analysis tab:** upload a backup file, configure migration split via step wizard, download the XLS report

### NIOS Grid Analysis (CLI)

```bash
cloud-usage --nios /path/to/backup.tar.gz
cloud-usage --nios /path/to/backup.tar.gz --nios-config nios-config.yaml
```

Analyzes a NIOS Grid backup XML archive. Produces `nios_analysis_<timestamp>.xlsx` in the output directory with 5 sheets:

1. **Object Counters** — DDI object counts per member, per family (26 families including 5 DTC families)
2. **Active IPs** — deduplicated Active IP counts per member (4-source deduplication)
3. **Scenario Comparison** — token estimates across three scenarios (current grid, hybrid UDDI split, full migration)
4. **Member Attribution** — per-member token breakdown for each scenario
5. **Inspect** — raw object counts for audit and traceability

**NIOS config YAML (optional):**

Use `nios-config.yaml` to configure member filtering and hybrid migration split:

```yaml
# nios-config.yaml
filter:
  whitelist: []          # glob patterns — if non-empty, only matching members are counted
  blacklist: []          # glob patterns — matching members are excluded
  lease_states: [active] # DHCP lease states counted as Active IPs (default: active only)

migration_split:         # optional — enables the Hybrid UDDI scenario
  niosx_members:         # members migrated to NIOSX-native licensing
    - "member1.example.com"
    - "member2.example.com"
  default_group: nios    # nios | niosx — which formula applies to unspecified members
```

Without `migration_split`, only the Current Grid and Full Migration scenarios are computed.

## Output Files

### Cloud Scan Output

Generated in `./output/` (or `--output-dir`):

- `{provider}_discovery_{timestamp}.xlsx` — full XLS report with resource breakdowns, token estimates per account
- `{provider}_estimator_{timestamp}.csv` — minimal columns for sizing sheets
- `{provider}_proof_{timestamp}.json` — audit manifest (scope, regions, resource hashes)

### NIOS Analysis Output

Generated in `./output/` (or `--output-dir`):

- `nios_analysis_{timestamp}.xlsx` — 5-sheet XLS report (Object Counters, Active IPs, Scenario Comparison, Member Attribution, Inspect)

## Token Formula Reference

| Formula | Applies to | DDI divisor | IP divisor | Asset divisor |
|---------|-----------|-------------|------------|---------------|
| UDDI native | NIOSX-native objects, cloud resources | 25 | 13 | 3 |
| NIOS Object | NIOS-managed objects in hybrid UDDI | 50 | 25 | 13 |

Cloud resources always use the UDDI native formula. For NIOS Grid analysis, all objects use the NIOS Object formula in the current grid and hybrid scenarios; the full migration scenario applies UDDI native to all objects.

## Project Structure

```
src/
└── cloud_usage/
    ├── providers/          # Cloud resource collectors
    │   ├── aws/            # AWS discovery (EC2, VPC, Route53, etc.)
    │   ├── azure/          # Azure discovery (VNet, DNS, compute, etc.)
    │   └── gcp/            # GCP discovery (VPC, Cloud DNS, compute, etc.)
    ├── nios/               # NIOS Grid backup analysis
    │   ├── parser/         # Streaming lxml iterparse, 26 object families
    │   ├── counter.py      # Per-member DDI/IP/Asset counting
    │   ├── scenarios.py    # Three licensing scenarios
    │   └── output.py       # 5-sheet XLS report
    ├── dashboard/          # FastAPI + HTMX web UI
    │   ├── routes/
    │   ├── services/
    │   ├── static/
    │   └── templates/
    ├── counting/           # Token calculation, IP deduplication
    ├── resilience/         # Checkpoint engine, rate limiter, retry
    ├── output/             # Cloud XLS/CSV/proof output
    └── cli.py              # Main CLI entry point
tests/                      # pytest test suite (195+ tests)
setup_venv.sh               # macOS/Linux setup
setup_venv.ps1              # Windows PowerShell setup
setup_venv.bat              # Windows batch fallback
requirements.txt            # All dependencies
```

## License

MIT License — see [LICENSE](LICENSE) for details.
