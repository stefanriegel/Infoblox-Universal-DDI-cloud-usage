"""Tests for the setup script content correctness.

Verifies that all three setup scripts use the consolidated requirements.txt
path (no legacy per-provider paths) and include cloud CLI detection logic.
No subprocess execution of setup scripts — content assertions only.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, "src")

# Resolve setup script paths relative to the project root
_PROJECT_ROOT = Path(__file__).parent.parent


def _read_setup_script(filename: str) -> str:
    """Read a setup script from the project root."""
    return (_PROJECT_ROOT / filename).read_text(encoding="utf-8")


class TestSetupShContent:
    """Tests for setup_venv.sh content."""

    def test_setup_sh_no_legacy_aws_path(self):
        """setup_venv.sh does not reference legacy aws_discovery/requirements.txt."""
        content = _read_setup_script("setup_venv.sh")
        assert "aws_discovery/requirements.txt" not in content

    def test_setup_sh_no_legacy_azure_path(self):
        """setup_venv.sh does not reference legacy azure_discovery/requirements.txt."""
        content = _read_setup_script("setup_venv.sh")
        assert "azure_discovery/requirements.txt" not in content

    def test_setup_sh_no_legacy_gcp_path(self):
        """setup_venv.sh does not reference legacy gcp_discovery/requirements.txt."""
        content = _read_setup_script("setup_venv.sh")
        assert "gcp_discovery/requirements.txt" not in content

    def test_setup_sh_uses_consolidated_requirements(self):
        """setup_venv.sh installs from top-level requirements.txt."""
        content = _read_setup_script("setup_venv.sh")
        assert "requirements.txt" in content

    def test_setup_sh_has_cli_detection(self):
        """setup_venv.sh includes detection for all three cloud CLIs."""
        content = _read_setup_script("setup_venv.sh")
        assert "aws" in content
        assert "az" in content
        assert "gcloud" in content

    def test_setup_sh_has_check_cli_function(self):
        """setup_venv.sh defines a check_cli helper function."""
        content = _read_setup_script("setup_venv.sh")
        assert "check_cli" in content

    def test_setup_sh_has_port_check(self):
        """setup_venv.sh checks if port 8080 is in use."""
        content = _read_setup_script("setup_venv.sh")
        assert "8080" in content


class TestSetupPs1Content:
    """Tests for setup_venv.ps1 content."""

    def test_setup_ps1_no_legacy_aws_path(self):
        """setup_venv.ps1 does not reference legacy aws_discovery/requirements.txt."""
        content = _read_setup_script("setup_venv.ps1")
        assert "aws_discovery/requirements.txt" not in content

    def test_setup_ps1_no_legacy_azure_path(self):
        """setup_venv.ps1 does not reference legacy azure_discovery/requirements.txt."""
        content = _read_setup_script("setup_venv.ps1")
        assert "azure_discovery/requirements.txt" not in content

    def test_setup_ps1_no_legacy_gcp_path(self):
        """setup_venv.ps1 does not reference legacy gcp_discovery/requirements.txt."""
        content = _read_setup_script("setup_venv.ps1")
        assert "gcp_discovery/requirements.txt" not in content

    def test_setup_ps1_uses_consolidated_requirements(self):
        """setup_venv.ps1 installs from top-level requirements.txt."""
        content = _read_setup_script("setup_venv.ps1")
        assert "requirements.txt" in content

    def test_setup_ps1_has_cli_detection(self):
        """setup_venv.ps1 includes detection for all three cloud CLIs."""
        content = _read_setup_script("setup_venv.ps1")
        assert "aws" in content.lower()
        assert "az" in content.lower()
        assert "gcloud" in content.lower()

    def test_setup_ps1_has_test_cli_function(self):
        """setup_venv.ps1 defines a Test-CLI helper function."""
        content = _read_setup_script("setup_venv.ps1")
        assert "Test-CLI" in content

    def test_setup_ps1_has_long_path_check(self):
        """setup_venv.ps1 checks Windows long path support."""
        content = _read_setup_script("setup_venv.ps1")
        assert "LongPathsEnabled" in content

    def test_setup_ps1_has_port_check(self):
        """setup_venv.ps1 checks if port 8080 is in use."""
        content = _read_setup_script("setup_venv.ps1")
        assert "8080" in content

    def test_setup_ps1_has_execution_policy_check(self):
        """setup_venv.ps1 checks PowerShell ExecutionPolicy."""
        content = _read_setup_script("setup_venv.ps1")
        assert "ExecutionPolicy" in content


class TestSetupBatContent:
    """Tests for setup_venv.bat content."""

    def test_setup_bat_no_legacy_aws_path(self):
        """setup_venv.bat does not reference legacy aws_discovery/requirements.txt."""
        content = _read_setup_script("setup_venv.bat")
        assert "aws_discovery/requirements.txt" not in content

    def test_setup_bat_no_legacy_azure_path(self):
        """setup_venv.bat does not reference legacy azure_discovery/requirements.txt."""
        content = _read_setup_script("setup_venv.bat")
        assert "azure_discovery/requirements.txt" not in content

    def test_setup_bat_no_legacy_gcp_path(self):
        """setup_venv.bat does not reference legacy gcp_discovery/requirements.txt."""
        content = _read_setup_script("setup_venv.bat")
        assert "gcp_discovery/requirements.txt" not in content

    def test_setup_bat_uses_consolidated_requirements(self):
        """setup_venv.bat installs from top-level requirements.txt."""
        content = _read_setup_script("setup_venv.bat")
        assert "requirements.txt" in content

    def test_setup_bat_has_cli_detection(self):
        """setup_venv.bat includes detection for all three cloud CLIs."""
        content = _read_setup_script("setup_venv.bat")
        assert "aws" in content.lower()
        assert "az" in content.lower()
        assert "gcloud" in content.lower()
