# Coding Conventions

**Analysis Date:** 2026-02-18

## Naming Patterns

**Files:**
- Lowercase with underscores: `discover.py`, `aws_discovery.py`, `output_utils.py`
- Module files group related functionality: `config.py`, `constants.py`, `resource_counter.py`
- Main entry point: `main.py` at project root
- Test files follow pytest convention: `test_*.py`
- Internal helper modules prefixed with scope: `aws_discovery.py` (provider-specific)

**Functions:**
- snake_case for all function names: `_check_aws_auth()`, `discover_native_objects()`, `save_checkpoint()`
- Private functions prefixed with single underscore: `_init_aws_clients()`, `_format_resource()`, `_is_managed_service()`
- Descriptive action-oriented names: `check_awscli_version()`, `validate_azure_credentials()`, `count_resources()`
- Main entry functions named `main()` with optional `args` parameter

**Variables:**
- snake_case for all variables: `native_objects`, `max_workers`, `output_directory`
- Boolean prefixed with `is_` or verb forms: `requires_management_token`, `is_managed_service()`
- Acronyms lowercase in variables: `aws_profile`, `gcp_config`, `azure_credential`
- Collection names plural: `all_regions`, `native_objects`, `discovered_resources`

**Types & Classes:**
- PascalCase for all class names: `AWSDiscovery`, `AzureConfig`, `BaseDiscovery`, `ResourceCounter`
- Dataclasses for configuration: `@dataclass class AWSConfig`, `@dataclass class DiscoveryConfig`
- Base classes follow naming: `BaseDiscovery`, `BaseConfig`
- Union types use modern syntax: `dict | None`, `str | None` instead of `Optional[]`

## Code Style

**Formatting:**
- Tool: `black` (version 25.0.0+) per `requirements.txt`
- Line length: Not explicitly configured, follows black default (88 characters implied)
- No configuration file found - uses black defaults

**Linting:**
- Tool: `flake8` (version 7.0.0+) per `requirements.txt`
- No `.flake8` configuration file found - uses flake8 defaults
- Primary enforcement: style via black formatting

**File Headers:**
- Shebang on executable scripts: `#!/usr/bin/env python3`
- Module docstring immediately after shebang: `"""Module description."""`
- UTF-8 encoding pragma set for subprocess compatibility: `os.environ['PYTHONIOENCODING'] = 'utf-8'`

**Imports:**
- Standard library imports first
- Third-party imports second (boto3, azure-*, google-cloud-*, tqdm, pandas)
- Local relative imports last
- Example from `aws_discovery.py`:
  ```python
  import logging
  import sys
  from concurrent.futures import ThreadPoolExecutor, as_completed
  from pathlib import Path
  from typing import Dict, List

  from tqdm import tqdm

  from shared.base_discovery import BaseDiscovery, DiscoveryConfig
  ```

## Import Organization

**Order:**
1. Standard library (`sys`, `os`, `json`, `logging`, `subprocess`, `time`, `threading`, etc.)
2. Type hints and dataclasses (`from dataclasses import dataclass`, `from typing import Dict, List, Optional`)
3. Third-party packages (`boto3`, `azure-*`, `google-cloud-*`, `tqdm`, `pandas`)
4. Local imports from parent modules (`from shared.config import BaseConfig`)
5. Relative imports within package (`from .config import AWSConfig`)

**Path Aliases:**
- No path aliases configured
- Explicit relative imports used: `from shared.base_discovery import BaseDiscovery`
- Parent directory added to path for cross-module access: `sys.path.insert(0, str(Path(__file__).parent.parent))`

## Error Handling

**Patterns:**
- Try-except blocks with specific exception types (avoid bare `except`)
- Example from `main.py`:
  ```python
  except NoCredentialsError as e:
      print(f"ERROR: AWS credentials are invalid or expired: {e}\n"...)
      sys.exit(1)
  except Exception as e:
      print(f"Error importing {args.provider} module: {e}")
      return 1
  ```
- Exit codes used: `return 0` for success, `return 1` for failure
- `sys.exit(1)` for credential validation failures in config modules
- Error messages prefixed with "ERROR:" for user-facing output
- Warning messages prefixed with "WARNING:" for deprecation notices

**Exception Types:**
- `NoCredentialsError` caught for AWS authentication
- `CredentialUnavailableError` caught for Azure authentication
- `ClientError` caught for AWS API errors
- `FileNotFoundError` caught for CLI tools
- Generic `Exception` as fallback with descriptive messages

## Logging

**Framework:** `logging` standard library

**Configuration:**
- Basic logging setup in discovery classes: `logging.basicConfig(level=logging.WARNING)`
- Module-level logger: `logger = logging.getLogger(__name__)` or `self.logger = logging.getLogger(self.__class__.__name__)`
- Suppression of verbose third-party loggers:
  ```python
  logging.getLogger("boto3").setLevel(logging.WARNING)
  logging.getLogger("botocore").setLevel(logging.WARNING)
  logging.getLogger("urllib3").setLevel(logging.WARNING)
  logging.getLogger("azure").setLevel(logging.ERROR)
  ```

**Patterns:**
- Info level for progress milestones: `self.logger.info("Starting AWS discovery across all regions...")`
- Debug level for detailed discovery info: `self.logger.debug(f"Discovered {len(region_resources)} resources in {region}")`
- Error level for failures: `self.logger.error(f"Error discovering region {region}: {e}")`
- Print statements for user-facing output (not logger)

## Comments

**When to Comment:**
- Module-level docstrings required: `"""Module description."""` at top of each file
- Class docstrings required: `"""Class description."""` after class definition
- Complex logic explanations: `# Use us-east-1 as default region to get list of all regions`
- Non-obvious decisions: `# Force a real call so we know tokens are valid.`
- Commented-out code replaced with inline explanations instead

**Docstring Format:**
- Google-style docstrings for public methods
- Example from `base_discovery.py`:
  ```python
  def discover_native_objects(self, max_workers: int = 8) -> List[Dict]:
      """
      Discover native objects in the cloud provider.

      Args:
          max_workers: Maximum number of parallel workers

      Returns:
          List of discovered resources
      """
  ```
- One-liner docstrings for simple functions: `"""Get all enabled regions for the AWS account."""`

## Function Design

**Size:**
- Functions range from 5-50 lines typically
- Large discovery functions (100+ lines) broken into discrete regions/subscriptions via parallelization
- Helper methods prefixed with underscore for complex internal logic

**Parameters:**
- Type hints required for all function parameters: `def main(args=None):`
- Default arguments used for optional parameters: `max_workers: int = 8`, `state: str = "active"`
- Complex objects passed as dataclass instances: `config: AWSConfig`
- Optional parameters marked in type hints: `extra_info: Dict[str, Any] = None`

**Return Values:**
- Type hints required: `-> List[Dict]`, `-> Dict[str, str]`, `-> int`
- Dictionary returns well-structured with consistent keys
- None implicitly returned if no return statement (functions that print/save only)
- Exit codes returned as integers (0 success, 1 failure)

## Module Design

**Exports:**
- Classes exported directly (no `__all__` list used)
- Public functions/classes used as-is
- Private utilities marked with underscore prefix

**Dataclass Usage:**
- Configuration classes use `@dataclass` with field defaults
- Post-init validation in `__post_init__()` method
- Example from `aws_discovery/config.py`:
  ```python
  @dataclass
  class AWSConfig(BaseConfig):
      aws_access_key_id: Optional[str] = None
      aws_secret_access_key: Optional[str] = None

      def __post_init__(self):
          super().__post_init__()
          if not self.aws_access_key_id:
              self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
  ```

**Inheritance:**
- Provider-specific classes inherit from `BaseDiscovery`: `class AWSDiscovery(BaseDiscovery)`
- Configuration classes inherit from `BaseConfig`: `class AWSConfig(BaseConfig)`
- Abstract methods decorated with `@abstractmethod`

---

*Convention analysis: 2026-02-18*
