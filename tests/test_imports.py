import pytest


def test_import_main():
    """Test that main module can be imported."""
    import main

    assert main is not None


def test_import_aws_discovery():
    """Test that AWS discovery modules can be imported."""
    from aws_discovery import aws_discovery, discover, config

    assert aws_discovery is not None
    assert discover is not None
    assert config is not None


def test_import_azure_discovery():
    """Test that Azure discovery modules can be imported."""
    from azure_discovery import azure_discovery, discover, config

    assert azure_discovery is not None
    assert discover is not None
    assert config is not None


def test_import_gcp_discovery():
    """Test that GCP discovery modules can be imported."""
    from gcp_discovery import gcp_discovery, discover, config

    assert gcp_discovery is not None
    assert discover is not None
    assert config is not None


def test_import_shared_modules():
    """Test that shared modules can be imported."""
    from shared import (
        base_discovery,
        output_utils,
        resource_counter,
        constants,
        licensing_calculator,
    )

    assert base_discovery is not None
    assert output_utils is not None
    assert resource_counter is not None
    assert constants is not None
    assert licensing_calculator is not None


def test_main_without_credentials():
    """Test that main.py fails gracefully without credentials."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "main.py", "aws"], capture_output=True, text=True
    )
    assert result.returncode != 0  # Should fail
    assert (
        "credentials" in result.stderr.lower()
        or "auth" in result.stderr.lower()
        or "error" in result.stderr.lower()
    )
