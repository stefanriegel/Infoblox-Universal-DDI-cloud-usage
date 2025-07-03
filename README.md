# Infoblox Universal DDI Management Token Calculator

Calculates Management Token requirements for Infoblox Universal DDI licensing by discovering AWS and Azure cloud resources.

## Overview

This tool scans AWS and Azure infrastructure to identify resources that require Management Tokens under Infoblox Universal DDI licensing rules. It discovers VMs, networks, subnets, and load balancers, then calculates the required token count based on official Infoblox licensing methodology.

## Requirements

- Python 3.8+
- AWS credentials (access key/secret, profile, or SSO)
- AWS CLI (installed automatically by setup script)
- Azure credentials (service principal or CLI login)
- Network access to AWS and Azure APIs

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
3. Both AWS and Azure

The setup script will also install the AWS CLI in your virtual environment, enabling AWS SSO and CLI commands.

### Manual Setup

**AWS only:**
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate.bat  # Windows
pip install tqdm pandas scikit-learn matplotlib seaborn boto3
```

**Azure only:**
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate.bat  # Windows
pip install tqdm pandas scikit-learn matplotlib seaborn azure-mgmt-compute azure-mgmt-network azure-mgmt-resource azure-mgmt-monitor azure-identity
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

## Usage

### Main Entry Point (Recommended)

```bash
# AWS discovery
python main.py aws --format json

# Azure discovery  
python main.py azure --format json
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
```

### Module-Specific Commands

**AWS:**
```bash
cd aws_discovery
python discover.py --format txt
```

**Azure:**
```bash
cd azure_discovery
python discover.py --format txt
```

### Performance Features

- **Multi-region scanning**: AWS discovery scans all enabled regions in parallel
- **Resource group scanning**: Azure discovery scans all resource groups in parallel
- **Progress bars**: Real-time progress indicators for all operations
- **Parallel workers**: Configurable number of parallel threads (default: 8)
- **Performance optimization**: 8 workers provide ~50% faster discovery than 5 workers

## Output Files

Generated in `output/` directory:

- `*_discovery_summary_*.json`: Resource counts by type
- `*_native_objects_*.json`: Detailed resource information
- `*_management_token_calculation_*.json`: Token calculation results
- `*_management_token_free_*.json`: Resources that don't require tokens

## Token Calculation

Based on Infoblox Universal DDI licensing rules:

- **DDI Objects**: 1 token per 25 objects
- **Active IPs**: 1 token per 13 IPs  
- **Assets**: 1 token per 3 assets

The highest of these three calculations determines the required Management Token count.

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
├── shared/                 # Shared utilities
│   ├── output_utils.py     # Output formatting
│   └── token_calculator.py # Token calculation logic
├── main.py                 # Main entry point
├── setup_venv.sh          # Linux/macOS setup script
├── setup_venv.bat         # Windows setup script
└── output/                # Generated output files
```

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