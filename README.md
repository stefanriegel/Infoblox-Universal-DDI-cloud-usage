# Infoblox Universal DDI Management Token Calculator

Calculates Management Token requirements for Infoblox Universal DDI licensing by discovering AWS and Azure cloud resources.

## Overview

This tool scans AWS and Azure infrastructure to identify resources that require Management Tokens under Infoblox Universal DDI licensing rules. It discovers VMs, networks, subnets, and load balancers, then calculates the required token count based on official Infoblox licensing methodology.

## Requirements

- Python 3.8+
- AWS credentials (access key/secret or profile)
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

## Configuration

### AWS Setup

Set credentials via environment variables:
```bash
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
```

Or use AWS profile:
```bash
export AWS_PROFILE="your_profile"
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

### Main Entry Point

```bash
# AWS discovery
python main.py aws --format json

# Azure discovery  
python main.py azure --format json

# Both platforms
python main.py aws azure --format json
```

### Module-Specific Commands

**AWS:**
```bash
cd aws
python discover.py --format json
```

**Azure:**
```bash
cd azure
python discover.py --format json
```

### Output Formats

- `--format json`: JSON files (default)
- `--format csv`: CSV files
- `--format txt`: Text files

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
├── aws/                    # AWS discovery module
│   ├── aws_discovery.py    # Core AWS discovery logic
│   ├── discover.py         # AWS CLI entry point
│   ├── config.py           # AWS configuration
│   ├── utils.py            # AWS utilities
│   └── requirements.txt    # AWS dependencies
├── azure/                  # Azure discovery module
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