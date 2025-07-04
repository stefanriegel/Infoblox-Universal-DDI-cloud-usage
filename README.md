# Infoblox Universal DDI Management Token Calculator

Calculates Management Token requirements for Infoblox Universal DDI licensing by discovering AWS, Azure, and GCP cloud resources.

## ⚠️ Early Preview Disclaimer

**This token calculation tool is currently in early preview and is provided without any guarantees.**

- **No Warranty**: This tool is provided "as is" without warranty of any kind
- **Accuracy**: Token calculations may not be 100% accurate and should be verified independently
- **Licensing Rules**: Infoblox licensing rules may change, affecting calculation accuracy
- **Production Use**: Not recommended for production licensing decisions without manual verification
- **Support**: Limited support available for this preview version

**Please verify all token calculations with your Infoblox representative before making licensing decisions.**

## Overview

This tool scans AWS, Azure, and Google Cloud Platform (GCP) infrastructure to identify resources that require Management Tokens under Infoblox Universal DDI licensing rules. It discovers VMs, networks, subnets, and load balancers, then calculates the required token count based on official Infoblox licensing methodology.

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
- Individual token calculations per provider
- Separate output files for each cloud
- Detailed resource information (when using --full)

## Output Files

Generated in `output/` directory:

- `*_native_objects_*.{format}`: Detailed resource information (when using --full)
- `*_management_token_calculation_*.{format}`: Token calculation results
- `*_management_token_free_*.{format}`: Resources that don't require tokens (when applicable)

## Token Calculation

**⚠️ IMPORTANT**: Token calculations are in early preview and should be verified independently.

Based on Infoblox Universal DDI licensing rules:

- **DDI Objects**: 1 token per 25 objects
- **Active IPs**: 1 token per 13 IPs  
- **Assets**: 1 token per 3 assets

The **sum** of these three calculations determines the required Management Token count.

**Note**: These calculations are estimates and may not reflect the exact token requirements for your specific environment. Always verify results with your Infoblox representative before making licensing decisions.

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
│   ├── token_calculator.py # Token calculation logic
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