# Stack Research

**Domain:** Multi-cloud discovery CLI + local web dashboard (Python)
**Researched:** 2026-02-23
**Confidence:** HIGH

---

## Recommended Stack

### Python Runtime

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Python | >=3.12,<3.15 | Runtime | 3.12 is the floor: improved error messages, faster startup, `match` statements mature. 3.13 is ideal target (bugfix support through Oct 2027). 3.11 is EOL Oct 2027 but lacks key perf improvements. Avoid 3.14-only features for now (still new). Enterprise customers on Windows 11 / macOS will have 3.12+ available via python.org installers or Homebrew. | HIGH |

### Package Management

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| uv | >=0.6 | Package manager, virtualenv, lockfile | 10-100x faster than pip. Single tool replaces pip + pip-tools + virtualenv + pyenv. Cross-platform lockfile (`uv.lock`) works on Windows, macOS, Linux without separate lockfiles. Standard `pyproject.toml` based. Actively maintained by Astral (same team as Ruff). The 2025/2026 default for new Python projects. | HIGH |
| pyproject.toml | (standard) | Project metadata & dependencies | PEP 621 standard. Single source of truth for deps, metadata, tool config. Replaces setup.py + setup.cfg + requirements.txt. uv, pip, and all modern tools support it natively. | HIGH |

### Web Framework

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| FastAPI | >=0.115 | HTTP API + HTML serving | Async-native (ASGI) handles concurrent SSE connections for progress streaming while cloud discovery runs. Built-in Pydantic validation. Auto-generated OpenAPI docs useful for debugging. 38% Python developer adoption in 2025 (up from 29%). Type hints everywhere = auditable code. PROJECT.md says "Flask/FastAPI" — FastAPI wins because SSE progress streaming requires async, and the discovery workload is I/O-bound (cloud API calls). | HIGH |
| Uvicorn | >=0.34 | ASGI server | The standard production ASGI server for FastAPI. Install with `uvicorn[standard]` for uvloop + httptools performance boost on macOS/Linux. Falls back to asyncio on Windows (still works, slightly slower). | HIGH |
| Jinja2 | >=3.1.6 | HTML templates | FastAPI's built-in template engine via `Starlette.templating`. Mature, fast, secure auto-escaping. Server-side rendering keeps the "single language" audit story — templates are just HTML with variables. | HIGH |

### Frontend (No Build Step)

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| HTMX | 2.0.x (CDN) | Dynamic HTML updates | Replaces JavaScript frameworks for our use case. Server sends HTML fragments, HTMX swaps them into the page. SSE extension (`hx-ext="sse"`) handles real-time progress updates natively. Zero JS to write for the dashboard. Served from vendored file (no CDN dependency for air-gapped enterprise networks). | HIGH |
| Pico CSS | 2.x (CDN) | Styling | Classless CSS framework — write semantic HTML, get professional styling with zero CSS classes. 12KB gzipped vs Tailwind's build toolchain. Perfect for internal/enterprise tools where custom design is unnecessary. Vendor the CSS file for offline use. | MEDIUM |

**Why not Tailwind CSS?** Tailwind requires a Node.js build step (PostCSS), which violates the "single language / no npm" constraint. It also requires extensive class markup that clutters HTML templates and adds review burden for customers auditing the code.

**Why not a JavaScript framework (React, Vue, Svelte)?** PROJECT.md explicitly requires "Python-native web (Flask/FastAPI + HTML)" and "single language for auditability." Adding a JS framework means Node.js tooling, a build pipeline, and a second language for customers to audit. HTMX + server-rendered HTML achieves the same result without any of that.

### Real-Time Progress

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| sse-starlette | >=3.2.0 | Server-Sent Events | Production-ready SSE for FastAPI/Starlette. W3C spec compliant. Auto client disconnect detection, heartbeats to prevent proxy timeouts. Discovery progress events stream to the dashboard without WebSocket complexity. One-directional (server-to-client) is exactly what progress reporting needs. | HIGH |

**Why not WebSockets?** SSE is simpler (standard HTTP, no upgrade handshake), works through all proxies/firewalls, and is one-directional — which is all we need for "discovery is X% complete." WebSockets add bidirectional complexity we do not use.

### Cloud Provider SDKs

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| boto3 | >=1.35.0 | AWS discovery | Official AWS SDK. Synchronous but well-tested. Handles SSO/profile auth via credential chain. Pin minimum to 1.35+ for latest service support and Python 3.12+ compatibility. | HIGH |
| azure-identity | >=1.20.0 | Azure authentication | `DefaultAzureCredential` chain supports CLI auth (`az login`), managed identity, environment variables. This is the standard auth pattern for Azure SDK. | HIGH |
| azure-mgmt-compute | >=37.0.0 | Azure VM discovery | Latest stable (37.2.0 as of Feb 2026). Includes async support via `.aio` namespace. | HIGH |
| azure-mgmt-network | >=28.0.0 | Azure network discovery | VNets, subnets, IPs, load balancers. Latest stable 30.2.0. | HIGH |
| azure-mgmt-dns | >=9.0.0 | Azure DNS zones/records | Latest stable targets newest API version only. | HIGH |
| azure-mgmt-privatedns | >=1.2.0 | Azure Private DNS | Private DNS zone discovery. Latest stable 1.2.0. | HIGH |
| azure-mgmt-resource | >=24.0.0 | Azure resource/subscription enumeration | Subscription listing, resource group enumeration. Latest stable 24.0.0. | HIGH |
| google-cloud-compute | >=1.20.0 | GCP compute discovery | VMs, networks, subnets, firewalls. Latest stable 1.40.0. | HIGH |
| google-cloud-dns | >=0.36.0 | GCP DNS zones/records | Moved to google-cloud-python monorepo. Latest 0.36.0. | HIGH |
| google-auth | >=2.20.0 | GCP authentication | Application Default Credentials (ADC). Supports `gcloud auth` flow. | HIGH |
| google-cloud-resource-manager | >=1.14.0 | GCP project enumeration | List/filter projects. Latest 1.16.0. | HIGH |
| google-cloud-service-usage | >=1.10.0 | GCP API enablement check | Check which APIs are enabled per project before querying them. | HIGH |

### Async Strategy for Cloud SDKs

**Decision: Use `asyncio.to_thread()` + synchronous SDKs, NOT async SDK wrappers.**

| Approach | Verdict | Rationale |
|----------|---------|-----------|
| `asyncio.to_thread()` + sync boto3/azure/gcp | **USE THIS** | Run synchronous SDK calls in thread pool. FastAPI's async event loop stays responsive for SSE. No new dependencies. All official SDK documentation and examples work as-is. `concurrent.futures.ThreadPoolExecutor` with configurable worker count handles parallelism across accounts/subscriptions/projects. |
| aioboto3 / aiobotocore | **DO NOT USE** | Third-party wrapper around botocore. Adds dependency complexity. API surface differs from boto3 docs. Version pinning conflicts with boto3. Not worth the complexity for a tool that runs discovery once per invocation (not a long-running server). |
| Azure `.aio` async clients | **CONSIDER LATER** | Official async support exists in azure-mgmt-*.aio modules, but adds complexity. The sync clients + `to_thread()` approach is simpler and sufficient. Can migrate specific hot paths to native async later if thread pool becomes a bottleneck. |

**Implementation pattern:**
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=8)

async def discover_aws_account(account_id: str):
    """Run synchronous boto3 discovery in thread pool."""
    return await asyncio.to_thread(sync_discover_aws, account_id)

async def discover_all_accounts(account_ids: list[str]):
    """Discover all accounts concurrently."""
    tasks = [discover_aws_account(aid) for aid in account_ids]
    return await asyncio.gather(*tasks)
```

### Data & Configuration

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Pydantic | >=2.10.0 | Data models, validation | Core data models for discovered resources, token calculations, API responses. v2 is 5-50x faster than v1 with Rust core. FastAPI requires it. Used for both internal data models AND request/response schemas. | HIGH |
| pydantic-settings | >=2.7.0 | Configuration management | Type-safe settings from env vars, .env files, CLI args. Replaces hand-rolled config parsing. Supports `env_prefix` for namespacing (e.g., `UDDI_WORKERS=8`). | HIGH |

### Output / Export

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| openpyxl | >=3.1.5 | Excel (.xlsx) export | Read/write Excel files with multiple sheets (detail + summary per provider). Supports cell formatting, column widths, header styling for professional output. No binary dependencies. Cross-platform. | HIGH |
| stdlib csv | (built-in) | CSV export | Python's built-in `csv` module. Zero dependencies. Handles quoting, escaping, encoding. Sufficient for flat tabular export. | HIGH |

**Why NOT pandas for export?** Pandas is a 150MB+ dependency that pulls in NumPy. For writing CSV/XLSX files with known schemas, `csv` + `openpyxl` do the job with 1/50th the install size. The existing codebase uses pandas only as a CSV/XLSX writer — that is massive overkill. Removing pandas dramatically reduces install time and avoids NumPy binary compatibility issues on customer machines.

### Rate Limiting & Resilience

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| tenacity | >=9.0.0 | Retry with backoff | The standard Python retry library. Configurable exponential backoff, jitter, retry conditions. Handles cloud API throttling (HTTP 429, 503). Used by cloud SDKs themselves internally. | HIGH |
| asyncio.Semaphore | (stdlib) | Concurrency limiting | Limit concurrent API calls per provider to avoid rate limiting. No external dependency. Pattern: `semaphore = asyncio.Semaphore(10)` before each cloud API call batch. | HIGH |

### Testing

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| pytest | >=9.0.0 | Test framework | The standard. Latest stable 9.0.2 (Feb 2026). Fixtures, parametrize, clear assertion output. | HIGH |
| pytest-asyncio | >=0.25.0 | Async test support | Required for testing FastAPI endpoints and async discovery functions. `@pytest.mark.asyncio` decorator for async test functions. | HIGH |
| httpx | >=0.28.0 | HTTP test client | FastAPI's recommended test client (`from httpx import AsyncClient`). Replaces `requests` for testing. Also used by `TestClient` internally. | HIGH |
| respx | >=0.22.0 | HTTP request mocking | Mock httpx requests in tests. Cleaner than `unittest.mock` for HTTP. | MEDIUM |
| moto | >=5.0.0 | AWS API mocking | Mock boto3 calls without hitting real AWS. Covers EC2, Route53, VPC, etc. | HIGH |

### Development Tools

| Tool | Version | Purpose | Notes | Confidence |
|------|---------|---------|-------|------------|
| Ruff | >=0.9.0 | Linter + formatter | Replaces flake8 + black + isort + pyupgrade + bandit. Single tool, 10-100x faster (Rust). Same team as uv (Astral). Latest 0.15.2 but pin conservatively. Configured in `pyproject.toml`. | HIGH |
| mypy | >=1.14.0 | Type checking | Static type checking catches bugs before runtime. Pydantic plugin for model validation. Optional but strongly recommended for a tool customers audit. | MEDIUM |
| pre-commit | >=4.0.0 | Git hooks | Run ruff + mypy on commit. Catches issues before they reach the repo. | MEDIUM |

### Cross-Platform Setup

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| PowerShell setup script (.ps1) | N/A | Windows setup | PROJECT.md requires signed PS1 scripts. Script creates venv, installs deps via uv (or pip fallback), validates Python version. Self-signed certificate acceptable. | HIGH |
| Bash setup script (.sh) | N/A | macOS / WSL setup | Standard shell script. Detects Python version, creates venv, installs deps. | HIGH |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| Web framework | FastAPI | Flask | Flask is WSGI (synchronous). SSE progress streaming requires hacks (gevent/eventlet) or background threads. FastAPI's native async makes SSE trivial. Flask would work but adds complexity for the real-time dashboard requirement. |
| Web framework | FastAPI | Django | Massive framework for a single-purpose tool. 100+ dependencies. Overkill ORM, admin panel, auth we do not need. Violates "auditable" constraint — too much framework code to review. |
| Package manager | uv | pip + venv | pip is 10-100x slower. No lockfile (requirements.txt is not a lockfile). No cross-platform resolution. Still works as fallback for customers who cannot install uv, so setup scripts should support both. |
| Package manager | uv | Poetry | Poetry is slower than uv, uses non-standard pyproject.toml extensions, and has had resolver reliability issues. uv is the clear successor for 2025/2026. |
| Export | openpyxl + csv | pandas | pandas adds ~150MB install (numpy, etc.) for a feature achievable with stdlib csv + openpyxl. Massive overkill. Binary compatibility issues on customer machines. |
| Export | openpyxl | XlsxWriter | XlsxWriter is write-only (cannot read/modify). openpyxl can do both, which is useful if we ever need template-based output. Similar performance for our scale. |
| CSS | Pico CSS | Tailwind CSS | Tailwind requires Node.js + PostCSS build step. Violates single-language constraint. Pico CSS is classless — write semantic HTML, get styling for free. |
| CSS | Pico CSS | Bootstrap | Bootstrap is 150KB+ and class-heavy. Pico is 12KB and classless. For an internal tool dashboard, Pico is far simpler. |
| Real-time | SSE (sse-starlette) | WebSockets | WebSockets are bidirectional — we only need server-to-client. SSE works through all proxies, is simpler to implement, and auto-reconnects. |
| Real-time | SSE (sse-starlette) | Polling | Polling wastes bandwidth and adds latency. SSE is push-based with near-zero overhead. |
| Async AWS | asyncio.to_thread + boto3 | aioboto3 | aioboto3 is a third-party wrapper with its own API quirks, version pinning conflicts with boto3, and maintenance risk. `to_thread()` is stdlib, zero-dependency, and uses official boto3 directly. |
| Retry | tenacity | Custom retry | tenacity is battle-tested, configurable, and handles all retry patterns. Custom retry logic inevitably misses edge cases (jitter, max delay, retry conditions). |
| Linter/formatter | Ruff | flake8 + black + isort | Ruff replaces all three in a single tool, runs 10-100x faster, and is configured in one place (pyproject.toml). No reason to use three tools when one does the job better. |
| Config | pydantic-settings | python-dotenv + argparse | pydantic-settings provides type-safe settings with validation, env var loading, .env support, and CLI arg integration. python-dotenv is just env loading with no validation. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **pandas** (for export) | 150MB+ install, NumPy binary deps, overkill for CSV/XLSX writing | `csv` (stdlib) + `openpyxl` |
| **Flask** (for new project) | Synchronous WSGI. SSE progress streaming requires gevent/eventlet hacks. | FastAPI (native async + SSE) |
| **aioboto3 / aiobotocore** | Third-party async wrapper. API differences from boto3 docs. Version pinning conflicts. Maintenance risk. | `asyncio.to_thread()` + standard boto3 |
| **Requests** (HTTP client) | Synchronous only. FastAPI's test client uses httpx. | httpx (async + sync, modern API) |
| **setup.py / setup.cfg** | Legacy packaging. No lockfile support. | pyproject.toml + uv |
| **tqdm** (for web dashboard) | Terminal-only progress bars. Does not integrate with web SSE. | SSE events + HTMX for web; `logging` for CLI output |
| **flake8 + black + isort** | Three separate tools, three configs, slow. | Ruff (single tool, faster, same results) |
| **Node.js / npm** (anything) | Violates single-language constraint. Adds build complexity. Customer audit burden. | Python-only tooling throughout |
| **SQLite / any database** | This is a point-in-time estimation tool, not a persistent app. No need for a database. | In-memory data structures during discovery; direct export to CSV/XLSX |
| **Docker** | Customers run this locally on their machines. Docker adds a dependency barrier. | Direct Python + venv install via setup scripts |
| **Celery / task queues** | Overkill for a single-run tool. Background tasks in FastAPI with `asyncio.create_task()` are sufficient. | `asyncio` tasks for background discovery |

---

## Stack Patterns by Variant

**If running from CLI only (no web dashboard):**
- FastAPI is still the backend, but skip launching the browser
- Discovery runs directly, output goes to files
- Progress reported via `logging` to stderr
- All the same libraries, just no browser auto-open

**If customer cannot install uv:**
- Fallback to `pip install -r requirements.txt`
- Generate `requirements.txt` from `uv export --format requirements-txt`
- Setup scripts detect uv first, fall back to pip + venv

**If customer is on Python 3.11:**
- Should work (3.11 has `asyncio.TaskGroup` since 3.11, `to_thread()` since 3.9)
- Minimum 3.12 is recommended; 3.11 is best-effort
- Test matrix includes 3.12 and 3.13

**If Windows without WSL:**
- Uvicorn runs on native Windows (uses asyncio event loop, not uvloop)
- PowerShell setup script handles venv + deps
- All cloud CLIs (aws, az, gcloud) work natively on Windows
- Path handling must use `pathlib.Path` throughout (no hardcoded `/`)

---

## Version Compatibility

| Package | Min Version | Tested Against | Notes |
|---------|-------------|----------------|-------|
| Python | 3.12 | 3.12, 3.13 | 3.12 floor for perf; 3.13 for latest features |
| FastAPI | 0.115 | 0.129.0 | Stable API; minor versions add features, rarely break |
| Pydantic | 2.10 | 2.13.1 | v2 only; v1 is incompatible with modern FastAPI |
| uvicorn | 0.34 | 0.41.0 | 0.40+ dropped Python 3.9 |
| boto3 | 1.35 | 1.42.x | Releases daily; pin minimum, not maximum |
| azure-identity | 1.20 | 1.25.2 | DefaultAzureCredential is stable API |
| azure-mgmt-compute | 37.0 | 37.2.0 | Major versions can have breaking API changes |
| azure-mgmt-network | 28.0 | 30.2.0 | Same pattern — pin minimum conservatively |
| azure-mgmt-dns | 9.0 | 9.0.0 | Targets latest Azure API version only |
| google-cloud-compute | 1.20 | 1.40.0 | Auto-generated; frequent releases |
| google-cloud-dns | 0.36 | 0.36.0 | Monorepo package; less frequently updated |
| openpyxl | 3.1.5 | 3.1.5 | Stable; infrequent releases |
| Ruff | 0.9 | 0.15.2 | Fast-moving; pin minimum not max |

---

## Installation

```bash
# Recommended: using uv (fast, cross-platform lockfile)
uv sync

# Fallback: using pip
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows
pip install -e ".[dev]"
```

### pyproject.toml dependency groups

```toml
[project]
requires-python = ">=3.12"
dependencies = [
    # Web
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "sse-starlette>=3.2.0",
    "jinja2>=3.1.6",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    # AWS
    "boto3>=1.35",
    # Azure
    "azure-identity>=1.20",
    "azure-mgmt-compute>=37.0",
    "azure-mgmt-network>=28.0",
    "azure-mgmt-dns>=9.0",
    "azure-mgmt-privatedns>=1.2",
    "azure-mgmt-resource>=24.0",
    # GCP
    "google-cloud-compute>=1.20",
    "google-cloud-dns>=0.36",
    "google-auth>=2.20",
    "google-cloud-resource-manager>=1.14",
    "google-cloud-service-usage>=1.10",
    # Export
    "openpyxl>=3.1.5",
    # Resilience
    "tenacity>=9.0",
    # HTTP client (for tests and potential webhook notifications)
    "httpx>=0.28",
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0",
    "pytest-asyncio>=0.25",
    "respx>=0.22",
    "moto[ec2,route53,elbv2]>=5.0",
    "ruff>=0.9",
    "mypy>=1.14",
    "pre-commit>=4.0",
]
```

---

## Sources

- [FastAPI PyPI](https://pypi.org/project/fastapi/) -- version 0.129.0 verified, HIGH confidence
- [Uvicorn PyPI](https://pypi.org/project/uvicorn/) -- version 0.41.0 verified, HIGH confidence
- [Pydantic PyPI](https://pypi.org/project/pydantic/) -- version 2.13.1 verified, HIGH confidence
- [pydantic-settings PyPI](https://pypi.org/project/pydantic-settings/) -- version 2.13.1 verified, HIGH confidence
- [sse-starlette PyPI](https://pypi.org/project/sse-starlette/) -- version 3.2.0 verified, HIGH confidence
- [boto3 PyPI](https://pypi.org/project/boto3/) -- version 1.42.x verified, HIGH confidence
- [azure-identity PyPI](https://pypi.org/project/azure-identity/) -- version 1.25.2 verified, HIGH confidence
- [azure-mgmt-compute PyPI](https://pypi.org/project/azure-mgmt-compute/) -- version 37.2.0 verified, HIGH confidence
- [azure-mgmt-network PyPI](https://pypi.org/project/azure-mgmt-network/) -- version 30.2.0 verified, HIGH confidence
- [azure-mgmt-dns PyPI](https://pypi.org/project/azure-mgmt-dns/) -- version 9.0.0 verified, HIGH confidence
- [azure-mgmt-privatedns PyPI](https://pypi.org/project/azure-mgmt-privatedns/) -- version 1.2.0 verified, HIGH confidence
- [azure-mgmt-resource PyPI](https://pypi.org/project/azure-mgmt-resource/) -- version 24.0.0 verified, HIGH confidence
- [google-cloud-compute PyPI](https://pypi.org/project/google-cloud-compute/) -- version 1.40.0 verified, HIGH confidence
- [google-cloud-dns PyPI](https://pypi.org/project/google-cloud-dns/) -- version 0.36.0 verified, HIGH confidence
- [google-cloud-resource-manager PyPI](https://pypi.org/project/google-cloud-resource-manager/) -- version 1.16.0 verified, HIGH confidence
- [google-cloud-service-usage PyPI](https://pypi.org/project/google-cloud-service-usage/) -- version 1.15.0 verified, HIGH confidence
- [openpyxl PyPI](https://pypi.org/project/openpyxl/) -- version 3.1.5 verified, HIGH confidence
- [Ruff PyPI](https://pypi.org/project/ruff/) -- version 0.15.2 verified, HIGH confidence
- [pytest PyPI](https://pypi.org/project/pytest/) -- version 9.0.2 verified, HIGH confidence
- [uv PyPI](https://pypi.org/project/uv/) -- cross-platform lockfile support verified, HIGH confidence
- [Jinja2 PyPI](https://pypi.org/project/Jinja2/) -- version 3.1.6 verified, HIGH confidence
- [HTMX GitHub releases](https://github.com/bigskysoftware/htmx/releases) -- version 2.0.8 verified, HIGH confidence
- [Strapi Blog: FastAPI vs Flask 2025](https://strapi.io/blog/fastapi-vs-flask-python-framework-comparison) -- adoption data, MEDIUM confidence
- [JetBrains PyCharm Blog: Django vs Flask vs FastAPI](https://blog.jetbrains.com/pycharm/2025/02/django-flask-fastapi/) -- comparison, MEDIUM confidence
- [Python devguide: Version status](https://devguide.python.org/versions/) -- Python version EOL dates, HIGH confidence
- [Azure SDK for Python (Mgmt)](https://azure.github.io/azure-sdk/releases/latest/mgmt/python.html) -- async .aio namespace confirmed, HIGH confidence

---
*Stack research for: Universal DDI Cloud Usage Estimator*
*Researched: 2026-02-23*
