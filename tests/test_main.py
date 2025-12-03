import subprocess
import sys


def test_main_help():
    """Test that main.py shows help correctly."""
    result = subprocess.run(
        [sys.executable, "main.py", "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
    assert "aws" in result.stdout.lower()
    assert "azure" in result.stdout.lower()
    assert "gcp" in result.stdout.lower()


def test_main_no_args():
    """Test that main.py fails gracefully with no arguments."""
    result = subprocess.run(
        [sys.executable, "main.py"], capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "error:" in result.stderr.lower() or "usage:" in result.stderr.lower()


def test_main_invalid_provider():
    """Test that main.py fails with invalid provider."""
    result = subprocess.run(
        [sys.executable, "main.py", "invalid"], capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "invalid" in result.stderr.lower() or "error" in result.stderr.lower()


def test_main_aws_help():
    """Test that main.py aws shows help."""
    result = subprocess.run(
        [sys.executable, "main.py", "aws", "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()


def test_main_azure_help():
    """Test that main.py azure shows help."""
    result = subprocess.run(
        [sys.executable, "main.py", "azure", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()


def test_main_gcp_help():
    """Test that main.py gcp shows help."""
    result = subprocess.run(
        [sys.executable, "main.py", "gcp", "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()