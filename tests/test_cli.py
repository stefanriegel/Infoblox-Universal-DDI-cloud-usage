"""Tests for the CLI entry point with argument parsing and provider selection.

Verifies argument parsing, interactive provider selection, and the main
scan lifecycle integration (auth doctor, checkpoint, orchestrator).
"""

from __future__ import annotations

import sys
from unittest import mock

sys.path.insert(0, "src")

from cloud_usage.cli import main, parse_args, select_providers


class TestParseArgs:
    """Tests for parse_args argument handling."""

    def test_aws_flag_sets_aws_true(self):
        """--aws flag sets aws=True."""
        args = parse_args(["--aws"])
        assert args.aws is True
        assert args.azure is False
        assert args.gcp is False

    def test_azure_flag_sets_azure_true(self):
        """--azure flag sets azure=True."""
        args = parse_args(["--azure"])
        assert args.azure is True
        assert args.aws is False
        assert args.gcp is False

    def test_gcp_flag_sets_gcp_true(self):
        """--gcp flag sets gcp=True."""
        args = parse_args(["--gcp"])
        assert args.gcp is True
        assert args.aws is False
        assert args.azure is False

    def test_aws_and_gcp_sets_both(self):
        """--aws --gcp sets both flags."""
        args = parse_args(["--aws", "--gcp"])
        assert args.aws is True
        assert args.gcp is True
        assert args.azure is False

    def test_all_providers_set(self):
        """All three provider flags can be set simultaneously."""
        args = parse_args(["--aws", "--azure", "--gcp"])
        assert args.aws is True
        assert args.azure is True
        assert args.gcp is True

    def test_skip_auth_check_flag(self):
        """--skip-auth-check sets skip_auth_check=True."""
        args = parse_args(["--skip-auth-check"])
        assert args.skip_auth_check is True

    def test_output_dir_custom_path(self):
        """--output-dir sets custom output directory."""
        args = parse_args(["--output-dir", "/tmp/custom_output"])
        assert args.output_dir == "/tmp/custom_output"

    def test_output_dir_default(self):
        """Default output-dir is ./output."""
        args = parse_args([])
        assert args.output_dir == "./output"

    def test_checkpoint_ttl_custom_value(self):
        """--checkpoint-ttl sets custom TTL value."""
        args = parse_args(["--checkpoint-ttl", "72"])
        assert args.checkpoint_ttl == 72

    def test_checkpoint_ttl_default(self):
        """Default checkpoint-ttl is 48."""
        args = parse_args([])
        assert args.checkpoint_ttl == 48

    def test_no_resume_flag(self):
        """--no-resume sets no_resume=True."""
        args = parse_args(["--no-resume"])
        assert args.no_resume is True

    def test_no_flags_all_false(self):
        """No flags results in all providers False (interactive mode)."""
        args = parse_args([])
        assert args.aws is False
        assert args.azure is False
        assert args.gcp is False
        assert args.skip_auth_check is False
        assert args.no_resume is False


class TestSelectProviders:
    """Tests for interactive provider selection."""

    def test_select_by_numbers(self):
        """Selecting providers by numbers (1,3) returns aws and gcp."""
        with mock.patch("builtins.input", return_value="1,3"):
            result = select_providers()
        assert result == ["aws", "gcp"]

    def test_select_by_names(self):
        """Selecting providers by names (aws,gcp) returns those providers."""
        with mock.patch("builtins.input", return_value="aws,gcp"):
            result = select_providers()
        assert result == ["aws", "gcp"]

    def test_select_single_provider(self):
        """Selecting a single provider works."""
        with mock.patch("builtins.input", return_value="2"):
            result = select_providers()
        assert result == ["azure"]

    def test_select_all_providers(self):
        """Selecting all three providers returns all."""
        with mock.patch("builtins.input", return_value="1,2,3"):
            result = select_providers()
        assert result == ["aws", "azure", "gcp"]

    def test_mixed_numbers_and_names(self):
        """Mixed number and name input works."""
        with mock.patch("builtins.input", return_value="1,azure"):
            result = select_providers()
        assert result == ["aws", "azure"]

    def test_invalid_input_reprompts(self):
        """Invalid input causes re-prompt until valid input received."""
        call_count = 0

        def mock_input(prompt: str = "") -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "invalid"
            return "1"

        with mock.patch("builtins.input", side_effect=mock_input):
            result = select_providers()
        assert result == ["aws"]
        assert call_count == 2

    def test_empty_input_reprompts(self):
        """Empty input causes re-prompt."""
        call_count = 0

        def mock_input(prompt: str = "") -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ""
            return "2"

        with mock.patch("builtins.input", side_effect=mock_input):
            result = select_providers()
        assert result == ["azure"]
        assert call_count == 2

    def test_eof_returns_empty(self):
        """EOFError on input returns empty list."""
        with mock.patch("builtins.input", side_effect=EOFError):
            result = select_providers()
        assert result == []

    def test_deduplicates_selections(self):
        """Duplicate selections are deduplicated."""
        with mock.patch("builtins.input", return_value="1,1,aws"):
            result = select_providers()
        assert result == ["aws"]

    def test_case_insensitive(self):
        """Provider names are case-insensitive."""
        with mock.patch("builtins.input", return_value="AWS,Azure"):
            result = select_providers()
        assert result == ["aws", "azure"]


class TestMainFunction:
    """Tests for the main() CLI entry point."""

    @mock.patch("cloud_usage.cli._get_discovery_providers", return_value=[])
    @mock.patch("cloud_usage.cli.setup_audit_logger")
    def test_main_returns_0_on_success_with_no_providers(self, mock_logger, mock_get_providers):
        """main() returns 0 when scan completes (even with no providers in Phase 1)."""
        mock_logger.return_value = mock.MagicMock()
        result = main(["--aws", "--skip-auth-check"])
        assert result == 0

    @mock.patch("cloud_usage.cli._get_discovery_providers", return_value=[])
    @mock.patch("cloud_usage.cli.setup_audit_logger")
    @mock.patch("cloud_usage.cli.AuthDoctor")
    def test_main_returns_1_when_all_auth_checks_fail(self, mock_doctor_cls, mock_logger, mock_get_providers):
        """main() returns 1 when all auth checks fail."""
        from cloud_usage.auth.validators import AuthResult

        mock_logger.return_value = mock.MagicMock()
        mock_doctor = mock.MagicMock()
        mock_doctor_cls.return_value = mock_doctor

        failed_result = AuthResult(
            provider="aws",
            success=False,
            identity="",
            account_count=0,
            error_message="No validator registered for aws",
        )
        mock_doctor.check_all.return_value = [failed_result]
        mock_doctor.report.return_value = False
        mock_doctor.get_passing_providers.return_value = []

        result = main(["--aws"])
        assert result == 1

    @mock.patch("cloud_usage.cli._get_discovery_providers", return_value=[])
    @mock.patch("cloud_usage.cli.setup_audit_logger")
    def test_main_scripted_mode_uses_flags(self, mock_logger, mock_get_providers):
        """main() with --aws --gcp uses those providers (no interactive prompt)."""
        mock_logger.return_value = mock.MagicMock()
        # Should NOT call select_providers (no input() call)
        with mock.patch("builtins.input", side_effect=AssertionError("Should not prompt")):
            result = main(["--aws", "--gcp", "--skip-auth-check"])
        assert result == 0

    @mock.patch("cloud_usage.cli._get_discovery_providers", return_value=[])
    @mock.patch("cloud_usage.cli.setup_audit_logger")
    @mock.patch("cloud_usage.cli.select_providers", return_value=[])
    def test_main_returns_1_when_no_providers_selected(self, mock_select, mock_logger, mock_get_providers):
        """main() returns 1 when user selects no providers in interactive mode."""
        mock_logger.return_value = mock.MagicMock()
        result = main([])
        assert result == 1

    @mock.patch("cloud_usage.cli._get_discovery_providers", return_value=[])
    @mock.patch("cloud_usage.cli.setup_audit_logger")
    @mock.patch("cloud_usage.cli.select_providers", return_value=["aws"])
    def test_main_interactive_mode_calls_select_providers(self, mock_select, mock_logger, mock_get_providers):
        """main() calls select_providers() when no CLI flags are set."""
        mock_logger.return_value = mock.MagicMock()
        result = main(["--skip-auth-check"])
        mock_select.assert_called_once()
        assert result == 0

    @mock.patch("cloud_usage.cli._get_discovery_providers", return_value=[])
    @mock.patch("cloud_usage.cli.setup_audit_logger")
    @mock.patch("cloud_usage.cli.AuthDoctor")
    def test_main_partial_auth_continue_with_passing(self, mock_doctor_cls, mock_logger, mock_get_providers):
        """main() offers continuation with passing providers when some auth fails."""
        from cloud_usage.auth.validators import AuthResult

        mock_logger.return_value = mock.MagicMock()
        mock_doctor = mock.MagicMock()
        mock_doctor_cls.return_value = mock_doctor

        results = [
            AuthResult(provider="aws", success=True, identity="SSO prod", account_count=5),
            AuthResult(provider="azure", success=False, identity="", account_count=0, error_message="No creds"),
        ]
        mock_doctor.check_all.return_value = results
        mock_doctor.report.return_value = False
        mock_doctor.get_passing_providers.return_value = ["aws"]

        # User says yes to continue with passing providers
        with mock.patch("builtins.input", return_value="y"):
            result = main(["--aws", "--azure"])

        assert result == 0

    @mock.patch("cloud_usage.cli._get_discovery_providers", return_value=[])
    @mock.patch("cloud_usage.cli.setup_audit_logger")
    @mock.patch("cloud_usage.cli.AuthDoctor")
    def test_main_partial_auth_user_cancels(self, mock_doctor_cls, mock_logger, mock_get_providers):
        """main() returns 1 when user declines to continue with partial providers."""
        from cloud_usage.auth.validators import AuthResult

        mock_logger.return_value = mock.MagicMock()
        mock_doctor = mock.MagicMock()
        mock_doctor_cls.return_value = mock_doctor

        results = [
            AuthResult(provider="aws", success=True, identity="SSO prod", account_count=5),
            AuthResult(provider="azure", success=False, identity="", account_count=0, error_message="No creds"),
        ]
        mock_doctor.check_all.return_value = results
        mock_doctor.report.return_value = False
        mock_doctor.get_passing_providers.return_value = ["aws"]

        with mock.patch("builtins.input", return_value="n"):
            result = main(["--aws", "--azure"])

        assert result == 1

    @mock.patch("cloud_usage.cli._get_discovery_providers", return_value=[])
    @mock.patch("cloud_usage.cli.setup_audit_logger")
    @mock.patch("cloud_usage.cli.CheckpointEngine")
    def test_main_no_resume_skips_checkpoint(self, mock_cp_cls, mock_logger, mock_get_providers):
        """main() with --no-resume does not attempt to load checkpoint."""
        mock_logger.return_value = mock.MagicMock()
        mock_cp = mock.MagicMock()
        mock_cp_cls.return_value = mock_cp
        mock_cp.load.return_value = None

        result = main(["--aws", "--skip-auth-check", "--no-resume"])

        # Should not call load() when --no-resume is set
        mock_cp.load.assert_not_called()
        assert result == 0
