# Testing Patterns

**Analysis Date:** 2026-02-18

## Test Framework

**Runner:**
- `pytest` (version 8.0.0+)
- No `pytest.ini` or `setup.cfg` configuration file found - uses pytest defaults
- Entry point: `tests/` directory at project root

**Assertion Library:**
- Built-in Python assertions used: `assert returncode == 0`, `assert "usage:" in result.stdout.lower()`

**Run Commands:**
```bash
pytest                    # Run all tests in tests/ directory
pytest tests/test_main.py # Run specific test file
pytest -v                 # Verbose output with test names
pytest -s                 # Show print statements and output
```

## Test File Organization

**Location:**
- `tests/` directory at project root (separate from source)
- Test files follow naming convention: `test_*.py`
- Current test file: `tests/test_main.py`

**Naming:**
- Test functions: `test_<description>()` - e.g., `test_main_help()`, `test_main_aws_help()`
- No test classes currently used - pure function-based tests

**Structure:**
```
tests/
├── __init__.py        # Empty module marker
└── test_main.py       # Tests for main entry point
```

## Test Structure

**Suite Organization:**
From `tests/test_main.py`:
```python
import subprocess
import sys

def test_main_help():
    """Test that main.py shows help correctly."""
    result = subprocess.run([sys.executable, "main.py", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
    assert "aws" in result.stdout.lower()
    assert "azure" in result.stdout.lower()
    assert "gcp" in result.stdout.lower()
```

**Patterns:**
- Setup: None used (tests are self-contained)
- Teardown: None used (subprocess tests don't require cleanup)
- Assertion pattern: Direct assertions on `result.returncode`, string content checks
- Docstrings required on all test functions describing what is tested

**Test Types:**

1. **Exit Code Tests:**
   - Verify successful execution: `assert result.returncode == 0`
   - Verify error exit: `assert result.returncode != 0`

2. **Output Tests:**
   - Check stdout for expected content: `assert "usage:" in result.stdout.lower()`
   - Check stderr for error messages: `assert "error:" in result.stderr.lower() or "usage:" in result.stderr.lower()`
   - Case-insensitive checks: `.lower()` applied to output

3. **Argument Validation Tests:**
   - Invalid provider: `test_main_invalid_provider()`
   - No arguments: `test_main_no_args()`
   - Help flags: `test_main_aws_help()`, `test_main_azure_help()`, `test_main_gcp_help()`

## Subprocess Testing Pattern

**Integration Testing Approach:**
- Used for testing CLI entry points (`main.py`)
- Spawns actual Python processes: `subprocess.run([sys.executable, "main.py", ...])`
- Captures stdout/stderr for assertion: `capture_output=True, text=True`
- Uses `encoding='utf-8'` for proper text handling

**Example from `test_main.py`:**
```python
def test_main_no_args():
    """Test that main.py fails gracefully with no arguments."""
    result = subprocess.run([sys.executable, "main.py"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "error:" in result.stderr.lower() or "usage:" in result.stderr.lower()
```

## Error Handling in Tests

**Pattern:**
- Tests check both success and failure paths
- Negative tests verify error handling: `assert result.returncode != 0`
- Output validation for user-facing error messages
- No exception catching - let test failures surface naturally

**Test Coverage by Provider:**
- AWS help validation: `test_main_aws_help()`
- Azure help validation: `test_main_azure_help()`
- GCP help validation: `test_main_gcp_help()`
- Invalid provider detection: `test_main_invalid_provider()`

## Checkpoint Testing

**Location:** `test_checkpoint.py` (separate test utility at project root)

**Purpose:** Manual testing script for Azure checkpoint save/load functionality

**Pattern:**
```python
def test_checkpoint():
    """Test saving and loading checkpoint."""
    checkpoint_file = "test_checkpoint.json"

    # Mock args
    class MockArgs:
        def __init__(self):
            self.format = "txt"
            self.workers = 8

    args = MockArgs()

    # Mock data setup
    all_subs = ["sub1", "sub2", "sub3"]
    scanned_subs = ["sub1"]

    # Execute save
    save_checkpoint(checkpoint_file, args, all_subs, scanned_subs, all_native_objects, errors)

    # Verify load
    data = load_checkpoint(checkpoint_file)
    assert data is not None
    assert len(data['completed_subs']) == 1

    # Cleanup
    os.remove(checkpoint_file)
```

**Mock Usage:**
- Inline `MockArgs` class for configuration testing
- Mock data structures: lists and dictionaries matching expected formats

## What IS Tested

**Currently Tested:**
- Command-line interface (`main.py`) argument parsing
- Help output for all providers (aws, azure, gcp)
- Exit codes for success and failure scenarios
- Error message presence for invalid arguments
- Checkpoint save/load functionality (separate manual test)

## What IS NOT Tested (Gaps)

**Discovery Logic:**
- No unit tests for AWS/Azure/GCP discovery implementations
- No mocking of cloud provider API calls
- Files: `aws_discovery/aws_discovery.py`, `azure_discovery/azure_discovery.py`, `gcp_discovery/gcp_discovery.py`

**Resource Counter:**
- No unit tests for resource counting logic
- File: `shared/resource_counter.py` (381 lines, untested)

**Output Generation:**
- No tests for output formatting (JSON, CSV, TXT)
- File: `shared/output_utils.py` (407 lines, untested)

**Licensing Calculator:**
- No tests for licensing token calculations
- File: `shared/licensing_calculator.py` (635 lines, untested)

**Configuration Validation:**
- Minimal testing of configuration loading and validation
- Files: `aws_discovery/config.py`, `azure_discovery/config.py`, `gcp_discovery/config.py`

## Testing Infrastructure Gaps

**Missing:**
- No test fixtures or factories for mock cloud resources
- No mocking framework (unittest.mock, pytest-mock)
- No test data/fixtures directory
- No integration test setup for actual cloud API calls (with credentials)
- No coverage metrics or coverage reporting configuration
- No parameterized tests (could reduce test duplication)

## Test Coverage Status

**Estimated Coverage:**
- CLI/Entry Points: ~60% (main argument parsing tested, but auth flows not tested)
- Discovery Logic: ~0% (no unit tests)
- Resource Processing: ~0% (no unit tests)
- Output Formatting: ~0% (no unit tests)
- Configuration: ~10% (only CLI validation tested)

---

*Testing analysis: 2026-02-18*
