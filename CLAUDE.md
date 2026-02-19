# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Multi-cloud discovery tool that counts DDI (DNS, DHCP, IPAM) objects and active IPs across AWS, Azure, and GCP for Infoblox Universal DDI licensing assessment. Python 3.11+.

## Commands

```bash
# Setup
./setup_venv.sh && source venv/bin/activate

# Run discovery
python main.py aws
python main.py azure --subscription-workers 8
python main.py gcp --workers 4

# Tests
pytest                        # all tests
pytest tests/test_main.py     # single file
pytest -v -s                  # verbose with stdout

# Code quality (line length: 127)
black --line-length=127 .
flake8 --max-line-length=127 .
```

## Architecture

**Entry points:** `main.py` routes `python main.py <provider>` to `{provider}_discovery/discover.py:main()`. Each provider also has a standalone `discover.py` that can run independently.

**Discovery pattern (Template Method):**
- `shared/base_discovery.py:BaseDiscovery` — abstract base with `discover_native_objects()`, shared `count_resources()`, `save_discovery_results()`
- `aws_discovery/aws_discovery.py:AWSDiscovery` — EC2, VPC, Route53 via boto3
- `azure_discovery/azure_discovery.py:AzureDiscovery` — VMs, VNets, DNS via Azure SDK, with checkpoint/resume
- `gcp_discovery/gcp_discovery.py:GCPDiscovery` — Compute, VPC, DNS via Google Cloud SDK

**Shared infrastructure (`shared/`):**
- `resource_counter.py` — Categorizes resources into DDI objects vs active IPs, deduplicates by (ip_space, ip) pairs
- `licensing_calculator.py` — Converts counts to management token requirements (ratios: 25 DDI objects/token, 13 active IPs/token, 3 assets/token)
- `output_utils.py` — CSV/JSON/TXT serialization + proof manifest generation
- `config.py` — Shared config dataclass base

**Per-provider configs** (`{provider}/config.py`): credential management, region/project/subscription enumeration. GCP uses a credential singleton with `threading.Lock`.

**Concurrency model:** `ThreadPoolExecutor` throughout. Azure has per-subscription workers. GCP has per-project workers with shared compute clients (project-agnostic) and per-project DNS clients.

## Key Patterns

- **Credential validation before output:** Each provider's `main()` validates credentials as the first action — auth failures never produce misleading "success" output
- **Shared vs per-project clients (GCP):** Compute clients are project-agnostic (pass `project=project_id` per call). Only `dns.Client` requires per-project instantiation
- **Resource ID format:** Includes provider prefix and project/subscription ID to prevent collisions in multi-project/subscription scans
- **`google-cloud-dns` pinned at 0.35.1** — incompatible with >= 1.0.0 GAPIC interface; uses HTTP REST transport

## Output Files

All written to `output/` directory:
- `{provider}_universal_ddi_licensing_{ts}.csv` — DDI objects, active IPs, token calculation
- `{provider}_universal_ddi_proof_{ts}.json` — Audit trail with resource hash, scope, summary
- `{provider}_universal_ddi_licensing_{ts}.txt` — Human-readable summary

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on Ubuntu/macOS/Windows: setup validation, flake8, black, pytest. Integration tests run on `dev` branch with real cloud credentials.
