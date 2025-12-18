# Infoblox Universal DDI Resource Counter

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Early%20Preview-orange.svg)](https://github.com/stefanriegel/Infoblox-Universal-DDI-cloud-usage)

> **⚠️ Early Preview**: This tool is currently in early preview and provided without guarantees. Resource counts should be verified independently before making licensing decisions.

A Python tool that discovers and counts DDI Objects and Active IPs across AWS, Azure, and Google Cloud Platform (GCP) for Infoblox Universal DDI licensing assessment.

## Features

- **Multi-Cloud Support**: Discover resources across AWS, Azure, and GCP
- **DDI Object Counting**: Count VPCs, subnets, DNS zones, and other network infrastructure
- **Active IP Tracking**: Identify IP addresses assigned to running instances and services
- **Flexible Output**: Support for JSON, CSV, and TXT output formats
- **Parallel Processing**: Configurable worker threads for improved performance
- **Checkpointing & Resume**: Save progress and resume interrupted discoveries (Azure)
- **Retry Logic**: Automatic retries for failed API calls to ensure consistency
- **Modular Design**: Clean separation between cloud providers and shared utilities

## Quick Start

**Prerequisites:** Python 3.11+, network access to cloud provider APIs

**Installation:**
```bash
git clone https://github.com/stefanriegel/Infoblox-Universal-DDI-cloud-usage.git
cd Infoblox-Universal-DDI-cloud-usage

# macOS/Linux
./setup_venv.sh

# Windows
.\setup_venv.ps1

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
& venv\Scripts\Activate.ps1  # Windows
```

**Usage:**
```bash
python main.py aws
python main.py azure --subscription-workers 8
python main.py gcp
```

## Installation

### Automated Setup (Recommended)

The setup scripts handle everything automatically:

**macOS/Linux:**
```bash
./setup_venv.sh
```

**Windows:**
```powershell
.\setup_venv.ps1
```

**Windows (Batch file fallback - use if PowerShell execution is restricted):**
```batch
setup_venv.bat
```

**Note:** The PowerShell script is signed but may be blocked on systems with strict execution policies that don't trust self-signed certificates. Use the batch file alternative in such cases.

### Manual Setup

Use manual setup when automated scripts cannot execute due to system restrictions or permissions issues.

**macOS/Linux:**
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Windows (required when PowerShell/Batch scripts cannot execute):**
```batch
# Create virtual environment
python -m venv venv
venv\Scripts\activate.bat

# Upgrade pip
python -m pip install --upgrade pip

# Install common dependencies
pip install tqdm pandas

# Install provider-specific dependencies (choose one):
# For AWS only:
pip install -r aws_discovery/requirements.txt

# For Azure only:
pip install -r azure_discovery/requirements.txt

# For GCP only:
pip install -r gcp_discovery/requirements.txt

# For all providers:
pip install -r aws_discovery/requirements.txt
pip install -r azure_discovery/requirements.txt
pip install -r gcp_discovery/requirements.txt
```

**Note:** On Windows, you may need to install the [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) if Azure dependencies fail to install due to cryptography compilation errors.

## Configuration

### AWS Setup

**Environment Variables:**
```bash
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
```

**AWS Profile/SSO:**
```bash
export AWS_PROFILE="your_profile"
aws sso login --profile your_profile
```

**Required Permissions:** EC2ReadOnlyAccess, Route53ReadOnlyAccess

### Azure Setup

**Azure CLI:**
```bash
az login --tenant "your-tenant-id"  # Use --tenant for specific tenant
az account set --subscription "your-subscription-id"  # Optional
az account show  # Verify login
```

**Service Principal:**
```bash
export AZURE_CLIENT_ID="your_client_id"
export AZURE_CLIENT_SECRET="your_client_secret"
export AZURE_TENANT_ID="your_tenant_id"
export AZURE_SUBSCRIPTION_ID="your_subscription_id"
```

**Required Permissions:** Reader role for subscription-level read access

**Required Permissions (Read-Only):**
- **Reader** - Built-in role for subscription-level read access across all subscriptions
- **Network Reader** - For network resource discovery across all resource groups (read-only)
- **Management Group Reader** - For multi-subscription discovery (if using Management Groups)

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

## Usage

### Command Line Interface

```bash
python main.py {provider} [options]
```

**Providers:**
- `aws` - Amazon Web Services
- `azure` - Microsoft Azure
- `gcp` - Google Cloud Platform

**Options:**
- `--format {json,csv,txt}` - Output format (default: txt)
- `--workers <number>` - Number of parallel workers (default: 8)
- `--subscription-workers <number>` - Parallel subscriptions for Azure (default: 4)
- `--retry-attempts <number>` - Retry attempts for failed API calls (default: 3)
- `--no-checkpoint` - Disable checkpointing and resume
- `--resume` - Auto-resume from checkpoint without prompt
- `--checkpoint-file <path>` - Custom checkpoint file path
- `--checkpoint-interval <number>` - Save checkpoint every N subscriptions (default: 50)
- `--full` - Save detailed resource data (default: summary only)

### Examples

```bash
python main.py aws
python main.py azure --subscription-workers 8
python main.py gcp --format json
python main.py azure --resume
```



## Output

### Output Files

Generated in the `output/` directory:

- `{provider}_universal_ddi_estimator_{timestamp}.csv` - Minimal columns for sizing sheets
- `{provider}_universal_ddi_licensing_{timestamp}.txt` - Human-readable summary
- `{provider}_universal_ddi_proof_{timestamp}.json` - Audit manifest (scope, regions, hashes)
- `{provider}_unknown_resources_{timestamp}.json` - Only when unknown types exist

### Output Structure

The tool generates detailed reports showing breakdowns first, with the key sizing numbers prominently displayed at the end:

**Resource Breakdowns:**
- DDI Objects breakdown (vpc, subnet, route53-zone, etc.)
- Active IPs breakdown (ec2-instance, load-balancer, etc.)

**Key Sizing Numbers (at the end):**
- **DDI Objects Count** - Total DDI objects for licensing
- **Active IPs Count** - Total active IP addresses

### Resource Counting

**⚠️ Important**: Resource counts are estimates and should be verified independently.

**DDI Objects**: VPCs, subnets, DNS zones/records, load balancers, network interfaces, etc.

**Active IPs**: IP addresses assigned to running instances, load balancers, and network services.




## Project Structure

```
├── aws_discovery/          # AWS discovery module
├── azure_discovery/        # Azure discovery module
├── gcp_discovery/          # GCP discovery module
├── licensing/              # Licensing calculation data
├── shared/                 # Shared utilities
├── tests/                  # Unit tests
├── main.py                 # Main CLI entry point
├── setup_venv.sh          # Linux/macOS setup script
├── setup_venv.ps1         # Windows PowerShell setup script
├── setup_venv.bat         # Windows batch file setup script
└── requirements.txt        # Dependencies
```
