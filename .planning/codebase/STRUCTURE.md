# Codebase Structure

**Analysis Date:** 2026-02-18

## Directory Layout

```
/Users/sr/Documents/coding/Infoblox-Universal-DDI-cloud-usage/
├── main.py                          # Primary CLI entry point
├── test_checkpoint.py               # Manual checkpoint testing utility
├── requirements.txt                 # Python dependencies (consolidated)
├── setup_venv.sh                    # Unix/Linux venv setup script
├── setup_venv.ps1                   # Windows PowerShell venv setup script
├── setup_venv.bat                   # Windows CMD venv setup script
├── cert.cer                         # SSL certificate for signing
├── LICENSE                          # Project license
├── README.md                         # User documentation
├── .gitignore                       # Git exclusion patterns
├── .pre-commit-config.yaml          # Pre-commit hook configuration
├── .github/                         # GitHub workflows (CI/CD)
├── .planning/                       # GSD planning documents
│
├── aws_discovery/                   # AWS cloud discovery module
│   ├── __init__.py
│   ├── aws_discovery.py             # AWSDiscovery class (resource enumeration)
│   ├── discover.py                  # AWS CLI entry point
│   ├── config.py                    # AWS config + credential helper
│   └── utils.py                     # AWS boto3 client factory
│
├── azure_discovery/                 # Azure cloud discovery module
│   ├── __init__.py
│   ├── azure_discovery.py           # AzureDiscovery class (resource enumeration)
│   ├── discover.py                  # Azure CLI entry point
│   └── config.py                    # Azure config + credential helper
│
├── gcp_discovery/                   # GCP cloud discovery module
│   ├── __init__.py
│   ├── gcp_discovery.py             # GCPDiscovery class (resource enumeration)
│   ├── discover.py                  # GCP CLI entry point
│   └── config.py                    # GCP config + credential helper
│
├── shared/                          # Shared infrastructure & utilities
│   ├── __init__.py
│   ├── base_discovery.py            # BaseDiscovery abstract class (template)
│   ├── config.py                    # Shared dataclasses (BaseConfig, DiscoveryConfig)
│   ├── constants.py                 # DDI resource types, token constants, error messages
│   ├── resource_counter.py          # ResourceCounter class (counts DDI objects, active IPs)
│   ├── output_utils.py              # Serialization to CSV/JSON/TXT
│   └── licensing_calculator.py      # UniversalDDILicensingCalculator (token calculation)
│
├── licensing/                       # (Stub) Licensing module placeholder
│
└── tests/                           # Test suite
    ├── __init__.py
    └── test_main.py                 # CLI smoke tests
```

## Directory Purposes

**Root Directory:**
- Purpose: Project configuration, setup scripts, documentation
- Contains: Entry point (main.py), environment setup, Git/GitHub config
- Key files: `main.py` (CLI router), `requirements.txt` (dependencies), setup scripts (Windows/Unix)

**`aws_discovery/`:**
- Purpose: AWS-specific cloud discovery implementation
- Contains: Boto3 integration, EC2/VPC/Route53 enumeration, region handling
- Key files: `aws_discovery.py` (resource discovery), `config.py` (boto3 clients, region enumeration), `discover.py` (CLI entry)
- Generator: Discovers EC2 instances, VPCs, subnets, load balancers, Elastic IPs, Route53 zones/records

**`azure_discovery/`:**
- Purpose: Azure-specific cloud discovery implementation
- Contains: Azure SDK integration, VM/VNET/DNS enumeration, subscription handling
- Key files: `azure_discovery.py` (resource discovery), `config.py` (Azure clients, subscription enumeration), `discover.py` (CLI entry)
- Generator: Discovers VMs, VNETs, subnets, load balancers, DNS zones, Private DNS zones
- Special: Supports checkpoint/resume for fault tolerance on long-running subscriptions

**`gcp_discovery/`:**
- Purpose: GCP-specific cloud discovery implementation
- Contains: Google Cloud integration, Compute/DNS enumeration, zone handling
- Key files: `gcp_discovery.py` (resource discovery), `config.py` (GCP clients, zone enumeration), `discover.py` (CLI entry)
- Generator: Discovers Compute instances, networks, subnetworks, addresses, DNS zones

**`shared/`:**
- Purpose: Cloud-agnostic reusable infrastructure
- Contains: Template base class, configuration dataclasses, resource counting logic, token calculation, output serialization
- Key files: `base_discovery.py` (BaseDiscovery template), `resource_counter.py` (DDI classification), `licensing_calculator.py` (token math), `output_utils.py` (CSV/JSON export)
- Critical: Houses `DDI_RESOURCE_TYPES` dict defining DDI-relevant resources per cloud provider

**`tests/`:**
- Purpose: Automated test suite
- Contains: CLI smoke tests (argument parsing, help text, error conditions)
- Key files: `test_main.py` (pytest tests invoked via subprocess)

**`licensing/`:**
- Purpose: (Stub directory) Potential licensing utilities
- Contains: Currently empty/placeholder
- Generated: Not in use

## Key File Locations

**Entry Points:**
- `main.py`: Primary CLI, routes to provider-specific discover modules
- `aws_discovery/discover.py`: AWS discovery entry point, implements AWS-specific workflow
- `azure_discovery/discover.py`: Azure discovery entry point, checkpoint/resume orchestration
- `gcp_discovery/discover.py`: GCP discovery entry point

**Configuration:**
- `shared/config.py`: Dataclass definitions (BaseConfig, DiscoveryConfig)
- `aws_discovery/config.py`: AWSConfig, boto3 client factory, region enumeration
- `azure_discovery/config.py`: AzureConfig, Azure SDK clients, subscription enumeration
- `gcp_discovery/config.py`: GCPConfig, Google Cloud clients, zone enumeration

**Core Logic:**
- `shared/base_discovery.py`: Abstract template BaseDiscovery with shared methods
- `aws_discovery/aws_discovery.py`: AWSDiscovery implementation (EC2, VPC, Route53 discovery)
- `azure_discovery/azure_discovery.py`: AzureDiscovery implementation (VM, VNET, DNS discovery)
- `gcp_discovery/gcp_discovery.py`: GCPDiscovery implementation (Compute, DNS discovery)
- `shared/resource_counter.py`: ResourceCounter class for DDI object and IP counting
- `shared/licensing_calculator.py`: UniversalDDILicensingCalculator for token computation

**Testing:**
- `tests/test_main.py`: Pytest test cases for CLI behavior
- `test_checkpoint.py`: Manual testing utility for Azure checkpoint/resume feature

**Constants:**
- `shared/constants.py`: DDI_RESOURCE_TYPES, ASSET_RESOURCE_TYPES, token calculation constants, error messages

## Naming Conventions

**Files:**
- Module files: snake_case (e.g., `aws_discovery.py`, `resource_counter.py`)
- Entry points: `discover.py` per provider, `main.py` for orchestrator
- Config files: `config.py` per module
- Tests: `test_*.py` or `*_test.py` (test_main.py, test_checkpoint.py)

**Directories:**
- Provider modules: lowercase with underscore (aws_discovery, azure_discovery, gcp_discovery)
- Shared utilities: `shared/`
- Tests: `tests/`

**Classes:**
- Discovery implementations: PascalCase + Discovery suffix (AWSDiscovery, AzureDiscovery, GCPDiscovery)
- Configuration classes: PascalCase + Config suffix (AWSConfig, AzureConfig, GCPConfig, DiscoveryConfig)
- Utility classes: PascalCase (ResourceCounter, UniversalDDILicensingCalculator)

**Functions:**
- Private methods: leading underscore (e.g., `_discover_region()`, `_format_resource()`)
- Public methods: camelCase or snake_case (e.g., `discover_native_objects()`, `count_resources()`)
- Entry points: `main()` function per module
- Credential helpers: `get_*_credential()`, `get_all_*_regions()` (e.g., `get_azure_credential()`, `get_all_enabled_regions()`)

**Constants:**
- ALL_CAPS with underscores (e.g., DDI_RESOURCE_TYPES, DEFAULT_WORKERS, ACTIVE_IPS_PER_TOKEN)

## Where to Add New Code

**New Cloud Provider:**
- Create directory: `/Users/sr/Documents/coding/Infoblox-Universal-DDI-cloud-usage/{provider}_discovery/`
- Add files:
  - `{provider}_discovery.py`: Class extending `BaseDiscovery`, implement `discover_native_objects()`
  - `config.py`: {Provider}Config dataclass, credential getter, region/project enumeration
  - `discover.py`: CLI entry point with credential validation, discovery orchestration
- Register in `main.py`: Add provider choice to ArgumentParser, import and route in main()
- Update `shared/constants.py`: Add DDI_RESOURCE_TYPES and ASSET_RESOURCE_TYPES for new provider

**New Resource Type Discovery:**
- If type is DDI-relevant:
  - Add resource_type string to `shared/constants.py:DDI_RESOURCE_TYPES[provider]`
  - Implement discovery method in `{provider}_discovery.py` (e.g., `_discover_new_resources()`)
  - Call from `_discover_region()` or `discover_native_objects()`
  - Call `_format_resource()` for consistent schema
- If type has IPs:
  - Ensure `_format_resource()` call includes correct IP fields in resource_data details
  - ResourceCounter will automatically extract via `_extract_ips_from_details()`

**New Output Format:**
- Add format choice to ArgumentParser in entry points (currently json, csv, txt)
- Implement serializer in `shared/output_utils.py` (e.g., `save_discovery_results_parquet()`)
- Call from discover.py after `save_discovery_results()` completes

**Utilities & Helpers:**
- General utilities: Add to `shared/{module}.py` (e.g., new helper in output_utils.py)
- Provider-specific utils: Add to `{provider}_discovery/utils.py` (e.g., AWS has utils.py for boto3 client factory)
- Import at module level: `from .utils import function_name` in discovery class file

## Special Directories

**`.planning/`:**
- Purpose: GSD phase planning documents and analysis
- Generated: Yes (by `/gsd:map-codebase` command)
- Committed: Yes
- Contents: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, STACK.md, INTEGRATIONS.md, CONCERNS.md

**`.github/`:**
- Purpose: GitHub Actions CI/CD workflows
- Generated: No (manually configured)
- Committed: Yes
- Contents: GitHub Actions YAML workflow files

**`output/`:**
- Purpose: Generated discovery results directory
- Generated: Yes (created at runtime if not exists)
- Committed: No (in .gitignore)
- Contents: CSV/JSON/TXT discovery results, licensing calculations, proof manifests, checkpoint files

**`tests/`:**
- Purpose: Test suite
- Generated: No (manually maintained)
- Committed: Yes
- Contents: test_main.py with pytest test cases

---

*Structure analysis: 2026-02-18*
