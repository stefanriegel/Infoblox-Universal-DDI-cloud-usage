# Infoblox Universal DDI Resource Counter

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Early%20Preview-orange.svg)](https://github.com/your-username/Infoblox-Universal-DDI-cloud-usage)

> **⚠️ Early Preview**: This tool is currently in early preview and provided without guarantees. Resource counts should be verified independently before making licensing decisions.

A Python tool that discovers and counts DDI Objects and Active IPs across AWS, Azure, and Google Cloud Platform (GCP) for Infoblox Universal DDI licensing assessment.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Output](#output)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Multi-Cloud Support**: Discover resources across AWS, Azure, and GCP
- **DDI Object Counting**: Count VPCs, subnets, DNS zones, and other network infrastructure
- **Active IP Tracking**: Identify IP addresses assigned to running instances and services
- **Flexible Output**: Support for JSON, CSV, and TXT output formats
- **Parallel Processing**: Configurable worker threads for improved performance
- **Modular Design**: Clean separation between cloud providers and shared utilities

## Quick Start

### Prerequisites

- Python 3.8 or higher
- AWS CLI (for AWS discovery)
- Google Cloud SDK (for GCP discovery)
- Network access to cloud provider APIs

### Installation

**macOS/Linux:**
```bash
git clone https://github.com/your-username/Infoblox-Universal-DDI-cloud-usage.git
cd Infoblox-Universal-DDI-cloud-usage
./setup_venv.sh
```

**Windows:**
```cmd
git clone https://github.com/your-username/Infoblox-Universal-DDI-cloud-usage.git
cd Infoblox-Universal-DDI-cloud-usage
setup_venv.bat
```

### Basic Usage

```bash
# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate.bat  # Windows

# Run discovery
python main.py aws --format json
python main.py azure --format json
python main.py gcp --format json
```

## Installation

### Automated Setup (Recommended)

The setup scripts handle everything automatically:

**macOS/Linux:**
```bash
./setup_venv.sh
```

**Windows:**
```cmd
setup_venv.bat
```

### Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate.bat  # Windows

# Install dependencies
pip install -r requirements.txt
```

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

**Required Permissions (Read-Only):**
- **EC2ReadOnlyAccess** - For EC2, VPC, and Load Balancer discovery across all regions
- **Route53ReadOnlyAccess** - For DNS zone and record discovery (global)
- **IAMReadOnlyAccess** - For account information and cross-account discovery
- **OrganizationsReadOnlyAccess** - For multi-account discovery (if using AWS Organizations)

### Azure Setup

**Azure CLI:**
```bash
az login
```

**Service Principal:**
```bash
export AZURE_CLIENT_ID="your_client_id"
export AZURE_CLIENT_SECRET="your_client_secret"
export AZURE_TENANT_ID="your_tenant_id"
export AZURE_SUBSCRIPTION_ID="your_subscription_id"
```

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

**Required Permissions (Read-Only):**
- **Compute Instance Viewer** - For Compute Engine instance discovery across all zones
- **Network Viewer** - For VPC and subnet discovery across all regions
- **DNS Reader** - For Cloud DNS zone and record discovery (global)
- **Project IAM Viewer** - For multi-project discovery and project listing (read-only)

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
- `--full` - Save detailed resource data (default: summary only)

### Examples

```bash
# Basic discovery with default settings
python main.py aws

# High-performance discovery with JSON output
python main.py aws --format json --workers 12

# Full discovery with detailed output
python main.py azure --format json --full

# GCP discovery with CSV output
python main.py gcp --format csv --full
```



## Output

### Output Files

Generated in the `output/` directory:

- `*_native_objects_*.{format}` - Detailed resource information (with `--full`)
- `*_resource_count_*.{format}` - DDI Objects and Active IPs count results

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

The tool counts two main categories:

#### DDI Object Count
The tool identifies and counts various DDI (DNS, DHCP, IPAM) objects across your cloud infrastructure:

**Network Infrastructure:**
- VPCs/Networks
- Subnets
- Route Tables
- Network Interfaces

**DNS Resources:**
- DNS Zones (Hosted Zones)
- DNS Records (A, AAAA, CNAME, MX, etc.)
- DNS Policies

**Load Balancing:**
- Load Balancers (Application, Network, Classic)
- Target Groups
- Health Checks

**Other DDI Objects:**
- NAT Gateways
- Internet Gateways
- VPN Connections
- Direct Connect (AWS)

#### Active IP Count
Tracks IP addresses currently assigned to running resources:

**Compute Resources:**
- EC2 Instances (AWS)
- Virtual Machines (Azure)
- Compute Instances (GCP)

**Network Services:**
- Load Balancers
- NAT Gateways
- VPN Endpoints
- Database Instances

**Other IP Sources:**
- Container Services
- Serverless Functions
- Network-attached Storage




## Project Structure

```
Infoblox-Universal-DDI-cloud-usage/
├── aws_discovery/          # AWS discovery module
│   ├── aws_discovery.py    # Core AWS discovery logic
│   ├── discover.py         # AWS CLI entry point
│   ├── config.py           # AWS configuration
│   └── utils.py            # AWS utilities
├── azure_discovery/        # Azure discovery module
│   ├── azure_discovery.py  # Core Azure discovery logic
│   ├── discover.py         # Azure CLI entry point
│   ├── config.py           # Azure configuration
│   └── utils.py            # Azure utilities
├── gcp_discovery/          # GCP discovery module
│   ├── gcp_discovery.py    # Core GCP discovery logic
│   ├── discover.py         # GCP CLI entry point
│   ├── config.py           # GCP configuration
│   └── utils.py            # GCP utilities
├── shared/                 # Shared utilities
│   ├── base_discovery.py   # Base discovery class
│   ├── output_utils.py     # Output formatting
│   ├── resource_counter.py # Resource counting logic
│   ├── constants.py        # Shared constants
│   ├── logging_utils.py    # Logging utilities
│   ├── validation.py       # Input validation
│   └── config.py           # Base configuration
├── main.py                 # Main entry point
├── requirements.txt        # Project dependencies
├── setup_venv.sh          # Linux/macOS setup script
├── setup_venv.bat         # Windows setup script
└── output/                # Generated output files
```



## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.