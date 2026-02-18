# Technology Stack

**Analysis Date:** 2026-02-18

## Languages

**Primary:**
- Python 3.11+ - Core application language for all cloud discovery modules

**Secondary:**
- YAML - Configuration files for licensing mappings and CI/CD workflows
- Bash/PowerShell - Setup scripts for cross-platform environment initialization

## Runtime

**Environment:**
- Python 3.11+ (enforced across all CI/CD workflows)

**Package Manager:**
- pip (Python package installer)
- Lockfile: `requirements.txt` present (consolidated for all providers)

## Frameworks

**Core:**
- argparse (Python stdlib) - Command-line argument parsing in `main.py`
- concurrent.futures (Python stdlib) - ThreadPoolExecutor for parallel cloud API calls
- threading (Python stdlib) - Thread-safe credential caching in `azure_discovery/config.py`
- dataclasses (Python stdlib) - Configuration object definitions

**Data Processing:**
- pandas 1.5.0+ - Data aggregation and summary generation
- tqdm 4.64.0+ - Progress bar visualization during discovery

**Cloud SDKs:**
- boto3 1.26.0+ - AWS EC2, Route53, ELBv2, ELB API access
- azure-mgmt-compute 30.0.0+ - Azure VM, managed disk discovery
- azure-mgmt-dns 8.0.0+ - Azure DNS zone and record enumeration
- azure-mgmt-network 28.0.0+ - Azure VNet, subnet, load balancer discovery
- azure-mgmt-privatedns 1.0.0+ - Azure Private DNS zone discovery
- azure-mgmt-resource 23.0.0+ - Azure resource management
- azure-identity 1.12.0+ - Azure authentication (multiple credential strategies)
- google-cloud-compute 1.12.0+ - GCP Compute Engine instance and network enumeration
- google-cloud-dns 0.35.1 - GCP Cloud DNS zone and record discovery
- google-auth 2.17.0+ - GCP authentication and credential chain

**Development/Testing:**
- pytest 8.0.0+ - Unit and integration test execution (referenced in CI)
- black 25.0.0+ - Python code formatting
- flake8 7.0.0+ - Python linting and style enforcement

## Key Dependencies

**Critical:**
- boto3 - AWS API interaction without this, AWS discovery cannot function
- azure-identity - Azure credential chain (supports SSO, CLI, service principal)
- google-auth - GCP credential management required for Compute and DNS APIs
- pandas - Data aggregation for licensing calculation summaries
- tqdm - Progress tracking prevents UI blocking on long API calls

**Infrastructure:**
- botocore (transitive via boto3) - AWS API client foundation
- azure-common (transitive via azure-* packages) - Shared Azure SDK utilities
- google-api-core (transitive via google-cloud-*) - GCP API client foundation

## Configuration

**Environment:**
Cloud provider credentials configured via environment variables:

**AWS:**
- `AWS_PROFILE` - Named profile for credential chain
- `AWS_ACCESS_KEY_ID` - Access key ID (alternative to profiles)
- `AWS_SECRET_ACCESS_KEY` - Secret access key
- `AWS_REGION` - Default region (fallback: us-east-1)

**Azure:**
- `AZURE_SUBSCRIPTION_ID` - Subscription to scan
- `AZURE_CLIENT_ID` - Service principal client ID
- `AZURE_CLIENT_SECRET` - Service principal secret
- `AZURE_TENANT_ID` - Azure tenant ID
- Falls back to: `az login` cache, Interactive Browser SSO

**GCP:**
- `GOOGLE_CLOUD_PROJECT` - GCP project ID
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to service account JSON key
- Falls back to: `gcloud auth application-default login` cache

**Application:**
- Output format: json, csv, txt (default: txt)
- Output directory: configurable via CLI args (default: output/)
- Parallel workers: configurable (AWS/GCP default: 8, Azure: 4 per subscription)
- Checkpoint interval (Azure): every 50 subscriptions by default
- Retry attempts: configurable (default: 3)

**Build:**
- `.pre-commit-config.yaml` - Pre-commit hooks for linting/formatting
  - flake8 7.3.0 with max line length 127
  - black 25.1.0 with line length 127
- GitHub Actions workflows in `.github/workflows/`
  - `ci.yml` - Multi-platform testing (Windows, macOS, Linux)
  - `sign-ps1.yml` - PowerShell script signing

## Platform Requirements

**Development:**
- Python 3.11+ interpreter
- Virtual environment manager (venv, pip)
- Cloud provider CLIs (optional but recommended):
  - AWS CLI v2.0.0+ for SSO login
  - Azure CLI for `az login` and subscription discovery
  - Google Cloud SDK (gcloud) 300.0.0+ for project defaults
- Pre-commit hook framework (optional)

**Production:**
- Python 3.11+ runtime
- Network connectivity to cloud provider APIs:
  - AWS: EC2, Route53, ELBv2, ELB endpoints
  - Azure: management.azure.com, login.microsoftonline.com
  - GCP: compute.googleapis.com, dns.googleapis.com
- Valid cloud provider credentials (service account, SSO, or keys)

**Cross-Platform Support:**
- Linux/macOS: Bash setup script `setup_venv.sh`
- Windows: PowerShell script `setup_venv.ps1` (signed) or batch fallback `setup_venv.bat`
- Windows path handling in Azure CLI detection: checks Program Files, AppData

---

*Stack analysis: 2026-02-18*
