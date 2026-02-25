"""Tests for the platform preflight detection module.

Verifies that check_platform() returns the expected structure and types,
and that print_preflight_warnings() handles edge cases correctly.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from cloud_usage.preflight import check_platform, print_preflight_warnings


class TestCheckPlatform:
    """Tests for check_platform() return structure and types."""

    def test_check_platform_returns_required_keys(self):
        """check_platform() returns all expected keys."""
        result = check_platform()
        expected_keys = {
            "python_ok",
            "python_version",
            "system",
            "is_wsl",
            "long_path_enabled",
            "execution_policy",
            "ansi_capable",
            "cli_aws",
            "cli_az",
            "cli_gcloud",
        }
        assert expected_keys.issubset(result.keys()), (
            f"Missing keys: {expected_keys - set(result.keys())}"
        )

    def test_python_ok_reflects_current_version(self):
        """python_ok correctly reflects whether the current Python is >= 3.10."""
        result = check_platform()
        expected = sys.version_info >= (3, 10)
        assert result["python_ok"] is expected

    def test_system_is_valid(self):
        """system is one of the expected OS name strings."""
        result = check_platform()
        assert result["system"] in ("Windows", "Darwin", "Linux"), (
            f"Unexpected system value: {result['system']!r}"
        )

    def test_cli_detection_returns_bool(self):
        """cli_aws, cli_az, cli_gcloud are all booleans."""
        result = check_platform()
        assert isinstance(result["cli_aws"], bool)
        assert isinstance(result["cli_az"], bool)
        assert isinstance(result["cli_gcloud"], bool)

    def test_python_version_string_format(self):
        """python_version is a non-empty string with version info."""
        result = check_platform()
        assert isinstance(result["python_version"], str)
        assert len(result["python_version"]) > 0
        # Should contain at least one dot (e.g., "3.11.4")
        assert "." in result["python_version"]

    def test_is_wsl_returns_bool(self):
        """is_wsl is a boolean."""
        result = check_platform()
        assert isinstance(result["is_wsl"], bool)

    def test_long_path_enabled_returns_bool(self):
        """long_path_enabled is a boolean (True on non-Windows)."""
        result = check_platform()
        assert isinstance(result["long_path_enabled"], bool)
        # On non-Windows, should always be True
        if result["system"] != "Windows":
            assert result["long_path_enabled"] is True

    def test_execution_policy_none_on_non_windows(self):
        """execution_policy is None on non-Windows platforms."""
        result = check_platform()
        if result["system"] != "Windows":
            assert result["execution_policy"] is None


class TestPrintPreflightWarnings:
    """Tests for print_preflight_warnings() output behavior."""

    def test_print_preflight_warnings_no_error(self, capsys):
        """No exception raised when python_ok=True."""
        mock_results = {
            "python_ok": True,
            "python_version": "3.11.4",
            "system": "Linux",
            "is_wsl": False,
            "long_path_enabled": True,
            "execution_policy": None,
            "ansi_capable": True,
            "cli_aws": True,
            "cli_az": False,
            "cli_gcloud": False,
        }
        # Should not raise any exception
        print_preflight_warnings(mock_results)
        captured = capsys.readouterr()
        # Summary line should be printed
        assert "Platform:" in captured.err
        assert "Python 3.11.4" in captured.err

    def test_print_preflight_warnings_python_too_old(self, capsys):
        """Stderr contains '3.10+' message when python_ok=False."""
        mock_results = {
            "python_ok": False,
            "python_version": "3.8.0",
            "system": "Linux",
            "is_wsl": False,
            "long_path_enabled": True,
            "execution_policy": None,
            "ansi_capable": True,
            "cli_aws": False,
            "cli_az": False,
            "cli_gcloud": False,
        }
        print_preflight_warnings(mock_results)
        captured = capsys.readouterr()
        assert "3.10+" in captured.err
        assert "3.8.0" in captured.err

    def test_print_preflight_warnings_python_too_old_no_summary(self, capsys):
        """When python_ok=False, summary line is NOT printed (early return)."""
        mock_results = {
            "python_ok": False,
            "python_version": "3.9.0",
            "system": "Darwin",
            "is_wsl": False,
            "long_path_enabled": True,
            "execution_policy": None,
            "ansi_capable": True,
            "cli_aws": False,
            "cli_az": False,
            "cli_gcloud": False,
        }
        print_preflight_warnings(mock_results)
        captured = capsys.readouterr()
        # No summary line when python_ok=False
        assert "Platform:" not in captured.err

    def test_print_preflight_warnings_wsl_tag(self, capsys):
        """WSL platforms show '(WSL)' tag in summary line."""
        mock_results = {
            "python_ok": True,
            "python_version": "3.11.4",
            "system": "Linux",
            "is_wsl": True,
            "long_path_enabled": True,
            "execution_policy": None,
            "ansi_capable": True,
            "cli_aws": False,
            "cli_az": False,
            "cli_gcloud": False,
        }
        print_preflight_warnings(mock_results)
        captured = capsys.readouterr()
        assert "(WSL)" in captured.err

    def test_print_preflight_warnings_cli_summary(self, capsys):
        """CLI availability is shown in the summary line."""
        mock_results = {
            "python_ok": True,
            "python_version": "3.11.4",
            "system": "Darwin",
            "is_wsl": False,
            "long_path_enabled": True,
            "execution_policy": None,
            "ansi_capable": True,
            "cli_aws": True,
            "cli_az": False,
            "cli_gcloud": True,
        }
        print_preflight_warnings(mock_results)
        captured = capsys.readouterr()
        assert "aws=yes" in captured.err
        assert "az=no" in captured.err
        assert "gcloud=yes" in captured.err
