# Infoblox Universal DDI Resource Counter

Counts DDI Objects and Active IPs for Infoblox Universal DDI licensing by discovering AWS, Azure, and GCP cloud resources.

## ⚠️ Early Preview Disclaimer

**This resource counting tool is currently in early preview and is provided without any guarantees.**

- **No Warranty**: This tool is provided "as is" without warranty of any kind
- **Accuracy**: Resource counts may not be 100% accurate and should be verified independently
- **Licensing Rules**: Infoblox licensing rules may change, affecting count accuracy
- **Production Use**: Not recommended for production licensing decisions without manual verification
- **Support**: Limited support available for this preview version

**Please verify all resource counts with your Infoblox representative before making licensing decisions.**

## Overview

This tool scans AWS, Azure, and Google Cloud Platform (GCP) infrastructure to identify and count DDI Objects and Active IPs under Infoblox Universal DDI licensing rules. It discovers VMs, networks, subnets, load balancers, and DNS resources, then provides detailed counts and breakdowns for licensing assessment.

## Requirements

- Python 3.8+
- AWS credentials (access key/secret, profile, or SSO)
- AWS CLI (installed automatically by setup script)
- Azure credentials (service principal or CLI login)
- GCP credentials (service account or gcloud CLI)
- Google Cloud SDK (for GCP discovery)
- Network access to AWS, Azure, and GCP APIs

## Installation

### Automated Setup

**macOS/Linux:**
```bash
./setup_venv.sh
```

**Windows:**
```cmd
setup_venv.bat
```

Choose which modules to install:
1. AWS only
2. Azure only  
3. GCP only
4. All three (AWS, Azure, GCP)

The setup script will also install the AWS CLI in your virtual environment, enabling AWS SSO and CLI commands.

### Manual Setup

**AWS only:**
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate.bat  # Windows
pip install -r aws_discovery/requirements.txt
```

**Azure only:**
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate.bat  # Windows
pip install -r azure_discovery/requirements.txt
```

**GCP only:**
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate.bat  # Windows
pip install -r gcp_discovery/requirements.txt
```

**All three (AWS, Azure, GCP):**
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate.bat  # Windows
pip install -r aws_discovery/requirements.txt
pip install -r azure_discovery/requirements.txt
pip install -r gcp_discovery/requirements.txt
```

### Activating the Virtual Environment

**IMPORTANT**: You must activate the virtual environment before running the tool!

**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```cmd
venv\Scripts\activate.bat
```

**To deactivate:**
```bash
deactivate
```

**Note**: The virtual environment must be activated in each new terminal session.

## Configuration

### AWS Setup

Set credentials via environment variables:
```bash
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
```

Or use AWS profile or SSO profile:
```bash
export AWS_PROFILE="your_profile"  # or your SSO profile
```

Required permissions:
- EC2:DescribeInstances, DescribeVpcs, DescribeSubnets, DescribeLoadBalancers
- Route53:ListHostedZones, ListResourceRecordSets
- IAM:GetUser

### Azure Setup

Login with Azure CLI:
```bash
az login
```

Or set service principal credentials:
```bash
export AZURE_CLIENT_ID="your_client_id"
export AZURE_CLIENT_SECRET="your_client_secret"
export AZURE_TENANT_ID="your_tenant_id"
export AZURE_SUBSCRIPTION_ID="your_subscription_id"
```

Required permissions:
- Reader role on subscription or resource groups
- Network Reader role

### GCP Setup

Login with gcloud CLI:
```bash
gcloud auth login
gcloud auth application-default login
```

Or set service account credentials:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
export GOOGLE_CLOUD_PROJECT="your-project-id"
```

Required permissions:
- Compute Engine: Compute Instance Viewer, Network Viewer
- Cloud DNS: DNS Reader
- Resource Manager: Project IAM Admin (for project discovery)

## Usage

### Main Entry Point (Recommended)

```bash
# AWS discovery
python main.py aws --format json

# Azure discovery  
python main.py azure --format json

# GCP discovery
python main.py gcp --format json
```

### Command Line Options

**Format Options:**
- `--format txt`: Text files (default)
- `--format json`: JSON files
- `--format csv`: CSV files

**Performance Options:**
- `--workers <number>`: Number of parallel workers (default: 8)
- `--full`: Save detailed resource/object data (default: summary only)

**Examples:**
```bash
# Basic discovery with default settings (TXT format)
python main.py aws

# High-performance discovery with 12 workers
python main.py aws --format json --workers 12

# Full discovery with detailed output
python main.py azure --format json --full

# GCP discovery with CSV output
python main.py gcp --format csv --full
```

### Individual Provider Discovery

Each cloud provider should be discovered separately for security and control:

```bash
# AWS discovery
python main.py aws --format json --full

# Azure discovery  
python main.py azure --format json --full

# GCP discovery
python main.py gcp --format json --full
```

**Output Includes:**
- Provider-specific resource discovery
- DDI Objects breakdown by type
- Active IPs count and sources
- Separate output files for each cloud
- Detailed resource information (when using --full)

## Output Files

Generated in `output/` directory:

- `*_native_objects_*.{format}`: Detailed resource information (when using --full)
- `*_resource_count_*.{format}`: DDI Objects and Active IPs count results

## Resource Counting

**⚠️ IMPORTANT**: Resource counts are in early preview and should be verified independently.

The tool counts two main categories:

- **DDI Objects**: VPCs, subnets, DNS zones, DNS records, and other network infrastructure
- **Active IPs**: IP addresses assigned to running instances and services

**DDI Objects Breakdown:**
- VPCs/Networks
- Subnets
- DNS Zones
- DNS Records
- Load Balancers

**Active IPs Sources:**
- EC2 Instances (AWS)
- Virtual Machines (Azure)
- Compute Instances (GCP)
- Load Balancers
- Other network-attached resources

**Note**: These counts are estimates and may not reflect the exact requirements for your specific environment. Always verify results with your Infoblox representative before making licensing decisions.

## Project Structure

```
├── aws_discovery/          # AWS discovery module
│   ├── aws_discovery.py    # Core AWS discovery logic
│   ├── discover.py         # AWS CLI entry point
│   ├── config.py           # AWS configuration
│   ├── utils.py            # AWS utilities
│   └── requirements.txt    # AWS dependencies
├── azure_discovery/        # Azure discovery module
│   ├── azure_discovery.py  # Core Azure discovery logic
│   ├── discover.py         # Azure CLI entry point
│   ├── config.py           # Azure configuration
│   ├── utils.py            # Azure utilities
│   └── requirements.txt    # Azure dependencies
├── gcp_discovery/          # GCP discovery module
│   ├── gcp_discovery.py    # Core GCP discovery logic
│   ├── discover.py         # GCP CLI entry point
│   ├── config.py           # GCP configuration
│   ├── utils.py            # GCP utilities
│   └── requirements.txt    # GCP dependencies
├── shared/                 # Shared utilities
│   ├── base_discovery.py   # Base discovery class
│   ├── output_utils.py     # Output formatting
│   ├── resource_counter.py # Resource counting logic
│   └── config.py           # Base configuration
├── main.py                 # Main entry point
├── setup_venv.sh          # Linux/macOS setup script
├── setup_venv.bat         # Windows setup script
└── output/                # Generated output files
```

### Architecture Overview

The project follows a clean separation of concerns:

- **`main.py`**: Main entry point that orchestrates discovery
- **`discover.py`**: Command-line interface and user experience layer
- **`*_discovery.py`**: Core business logic and cloud provider integration
- **`shared/`**: Reusable utilities and base classes

### AWS SSO (Single Sign-On) Usage

If your organization uses AWS SSO, you can authenticate using the AWS CLI:

```bash
aws sso login --profile <your-sso-profile>
```

Then run the tool with your SSO profile:

```bash
export AWS_PROFILE=<your-sso-profile>
python main.py aws --format txt
```

Or set the profile in your environment or config as needed. The tool will automatically use SSO credentials if available.

#### Example: Running with AWS SSO

After logging in with your SSO profile:

```bash
aws sso login --profile aws_test_pm_dev_sso
```

Run the tool using your SSO profile:

```bash
AWS_PROFILE=aws_test_pm_dev_sso python main.py aws --format txt
```

This ensures the tool uses your SSO credentials for AWS discovery.

### GCP Authentication

For GCP, you can authenticate using the gcloud CLI:

```bash
gcloud auth login
gcloud auth application-default login
```

Then run the tool:

```bash
export GOOGLE_CLOUD_PROJECT="your-project-id"
python main.py gcp --format txt
```