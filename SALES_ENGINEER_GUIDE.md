# Infoblox Universal DDI Licensing Calculator - Sales Engineer Guide

## Overview

This tool helps Infoblox Sales Engineers calculate Universal DDI licensing requirements for customer cloud environments. It discovers cloud resources across AWS, Azure, and GCP, then applies official Infoblox licensing ratios to determine the number of Management Tokens needed.

## Quick Start

### Prerequisites
1. Ensure customer has configured cloud credentials (AWS CLI, Azure CLI, or GCP SDK)
2. Run the setup script: `./setup_venv.sh` (macOS/Linux) or `setup_venv.bat` (Windows)
3. Activate virtual environment: `source venv/bin/activate`

### Basic Usage

**Generate licensing calculations for AWS:**
```bash
python main.py aws --licensing
```

**Generate licensing calculations for all providers:**
```bash
python main.py aws --licensing
python main.py azure --licensing  
python main.py gcp --licensing
```

**Include full discovery data:**
```bash
python main.py aws --licensing --full
```

## Output Files

The tool generates two files for Sales Engineers:

1. **CSV File** (`aws_universal_ddi_licensing_YYYYMMDD_HHMMSS.csv`)
   - Ready for import into Excel/Sheets
   - Contains licensing summary and provider breakdown
   - Suitable for customer presentations

2. **Text Summary** (`aws_universal_ddi_licensing_YYYYMMDD_HHMMSS.txt`)
   - Human-readable summary
   - Quick reference for calls/meetings

## Universal DDI Licensing Model

Based on official Infoblox Universal DDI licensing documentation:

| Metric | Objects per Management Token (Native) |
|--------|---------------------------------------|
| **DDI Objects** | 25 |
| **Active IP Addresses** | 13 |
| **Managed Assets** | 3 |

### What Counts as Each Metric:

**DDI Objects (25 per token):**
- VPCs/VNets and Subnets
- DNS Zones and Records (Route53, Azure DNS, Cloud DNS)
- DHCP ranges and IPAM blocks (where applicable)

**Active IP Addresses (13 per token):**
- IP addresses assigned to running instances
- Load balancer IP addresses
- NAT gateway IP addresses
- De-duplicated across IP spaces

**Managed Assets (3 per token):**
- EC2 instances, VMs, Compute instances (with IP addresses)
- Load balancers
- Network gateways and appliances (with IP addresses)

## Sample Output

```
UNIVERSAL DDI LICENSING SUMMARY:
DDI Objects: 127 (6 tokens)
Active IPs: 89 (7 tokens)
Managed Assets: 23 (8 tokens)
TOTAL MANAGEMENT TOKENS REQUIRED: 21
```

## Customer Conversation Points

1. **Sizing Accuracy**: Counts are based on live discovery of actual cloud resources
2. **Official Ratios**: Uses Infoblox's published Universal DDI licensing ratios
3. **Multi-Cloud**: Supports AWS, Azure, and GCP in single or combined deployments
4. **Licensing Compliance**: Aligns with Infoblox Universal DDI Native Objects model

## Troubleshooting

**Common Issues:**

- **No credentials found**: Customer needs to configure cloud CLI tools
- **Permission denied**: Requires read-only permissions across cloud accounts
- **Zero counts**: May indicate no resources or permission issues

**For large environments:**
- Use `--workers 12` for faster discovery
- Run during off-peak hours to avoid API throttling
- Consider running per-region or per-account for very large deployments

## Support

- Review `README.md` for detailed setup instructions
- Check `licensing/Universal DDI Licensing - Universal DDI - Infoblox Documentation Portal.pdf` for official licensing documentation
- Contact Infoblox Support for licensing questions

---

**Important**: This tool provides estimates based on discovered resources. Always verify counts and consult with Infoblox licensing team for final sizing decisions.