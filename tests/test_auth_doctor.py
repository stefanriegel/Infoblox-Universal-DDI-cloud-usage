"""
Tests for auth doctor pre-flight validation.

Tests cover AuthValidator interface, AuthDoctor orchestration,
report output to stderr, partial-provider continuation, and AUTH-05
read_only enforcement.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cloud_usage.auth.doctor import AuthDoctor
from cloud_usage.auth.validators import AuthResult, AuthValidator


# -- Mock validators for testing --


class MockPassingValidator(AuthValidator):
    """Mock validator that always passes."""

    def __init__(self, provider: str, identity: str, account_count: int) -> None:
        self._provider = provider
        self._identity = identity
        self._account_count = account_count

    def validate(self) -> AuthResult:
        return AuthResult(
            provider=self._provider,
            success=True,
            identity=self._identity,
            account_count=self._account_count,
        )

    @property
    def provider_name(self) -> str:
        return self._provider


class MockFailingValidator(AuthValidator):
    """Mock validator that always fails with an error and suggestion."""

    def __init__(self, provider: str, error: str, suggestion: str | None = None) -> None:
        self._provider = provider
        self._error = error
        self._suggestion = suggestion

    def validate(self) -> AuthResult:
        return AuthResult(
            provider=self._provider,
            success=False,
            identity="",
            account_count=0,
            error_message=self._error,
            suggestion=self._suggestion,
        )

    @property
    def provider_name(self) -> str:
        return self._provider


# -- Tests for AuthDoctor.check_all --


class TestCheckAll:
    """Tests for AuthDoctor.check_all() validation orchestration."""

    def test_all_providers_passing(self) -> None:
        """check_all returns success results for all passing providers."""
        validators = {
            "aws": MockPassingValidator("aws", "SSO profile: prod", 12),
            "azure": MockPassingValidator("azure", "Service Principal: app-123", 5),
            "gcp": MockPassingValidator("gcp", "Service Account: sa@proj.iam", 3),
        }
        doctor = AuthDoctor(validators)
        results = doctor.check_all(["aws", "azure", "gcp"])

        assert len(results) == 3
        assert all(r.success for r in results)
        assert results[0].provider == "aws"
        assert results[0].identity == "SSO profile: prod"
        assert results[0].account_count == 12
        assert results[1].provider == "azure"
        assert results[1].account_count == 5
        assert results[2].provider == "gcp"
        assert results[2].account_count == 3

    def test_one_provider_failing_others_passing(self) -> None:
        """check_all returns mixed results when one provider fails."""
        validators = {
            "aws": MockPassingValidator("aws", "SSO profile: prod", 12),
            "azure": MockFailingValidator(
                "azure",
                "Service principal expired",
                "run: az login --service-principal",
            ),
            "gcp": MockPassingValidator("gcp", "Service Account: sa@proj.iam", 3),
        }
        doctor = AuthDoctor(validators)
        results = doctor.check_all(["aws", "azure", "gcp"])

        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[1].error_message == "Service principal expired"
        assert results[1].suggestion == "run: az login --service-principal"
        assert results[2].success is True

    def test_unregistered_provider_returns_failed_result(self) -> None:
        """check_all creates a failed AuthResult for unregistered providers."""
        validators = {
            "aws": MockPassingValidator("aws", "SSO profile: prod", 12),
        }
        doctor = AuthDoctor(validators)
        results = doctor.check_all(["aws", "azure"])

        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        assert results[1].provider == "azure"
        assert results[1].error_message == "No validator registered for azure"
        assert results[1].identity == ""
        assert results[1].account_count == 0

    def test_empty_selected_providers(self) -> None:
        """check_all returns empty list when no providers selected."""
        validators = {
            "aws": MockPassingValidator("aws", "SSO profile: prod", 12),
        }
        doctor = AuthDoctor(validators)
        results = doctor.check_all([])

        assert results == []

    def test_only_selected_providers_are_validated(self) -> None:
        """check_all only validates providers in the selected list."""
        validators = {
            "aws": MockPassingValidator("aws", "SSO profile: prod", 12),
            "azure": MockPassingValidator("azure", "Service Principal: app-123", 5),
            "gcp": MockPassingValidator("gcp", "Service Account: sa@proj.iam", 3),
        }
        doctor = AuthDoctor(validators)
        results = doctor.check_all(["aws"])

        assert len(results) == 1
        assert results[0].provider == "aws"


# -- Tests for AuthDoctor.report --


class TestReport:
    """Tests for AuthDoctor.report() stderr output."""

    def test_report_returns_true_when_all_pass(self) -> None:
        """report() returns True when all results are successful."""
        results = [
            AuthResult(provider="aws", success=True, identity="SSO profile: prod", account_count=12),
            AuthResult(provider="azure", success=True, identity="SP: app-123", account_count=5),
        ]
        doctor = AuthDoctor({})
        assert doctor.report(results) is True

    def test_report_returns_false_when_any_fail(self) -> None:
        """report() returns False when any result has failed."""
        results = [
            AuthResult(provider="aws", success=True, identity="SSO profile: prod", account_count=12),
            AuthResult(
                provider="azure",
                success=False,
                identity="",
                account_count=0,
                error_message="Expired credentials",
            ),
        ]
        doctor = AuthDoctor({})
        assert doctor.report(results) is False

    def test_report_writes_success_to_stderr(self, capsys: object) -> None:
        """report() writes OK line with identity and account count to stderr."""
        results = [
            AuthResult(provider="aws", success=True, identity="SSO profile: prod", account_count=12),
        ]
        doctor = AuthDoctor({})
        doctor.report(results)

        captured = sys.stdout  # capsys doesn't capture sys.stderr.write directly
        # Use capsys readouterr for captured output
        import io
        from unittest.mock import patch

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            doctor.report(results)

        output = stderr_capture.getvalue()
        assert "aws: OK" in output
        assert "SSO profile: prod" in output
        assert "12 accounts accessible" in output

    def test_report_writes_failure_to_stderr(self) -> None:
        """report() writes FAILED line with error message to stderr."""
        import io
        from unittest.mock import patch

        results = [
            AuthResult(
                provider="azure",
                success=False,
                identity="",
                account_count=0,
                error_message="Service principal expired",
                suggestion="run: az login --service-principal",
            ),
        ]
        doctor = AuthDoctor({})

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            doctor.report(results)

        output = stderr_capture.getvalue()
        assert "azure: FAILED" in output
        assert "Service principal expired" in output
        assert "Fix: run: az login --service-principal" in output

    def test_report_writes_failure_without_suggestion(self) -> None:
        """report() writes FAILED line without Fix line when no suggestion."""
        import io
        from unittest.mock import patch

        results = [
            AuthResult(
                provider="gcp",
                success=False,
                identity="",
                account_count=0,
                error_message="No credentials found",
                suggestion=None,
            ),
        ]
        doctor = AuthDoctor({})

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            doctor.report(results)

        output = stderr_capture.getvalue()
        assert "gcp: FAILED" in output
        assert "No credentials found" in output
        assert "Fix:" not in output

    def test_report_mixed_results_format(self) -> None:
        """report() outputs both OK and FAILED lines for mixed results."""
        import io
        from unittest.mock import patch

        results = [
            AuthResult(provider="aws", success=True, identity="SSO profile: prod", account_count=12),
            AuthResult(
                provider="azure",
                success=False,
                identity="",
                account_count=0,
                error_message="Expired",
                suggestion="run: az login",
            ),
            AuthResult(provider="gcp", success=True, identity="SA: sa@proj.iam", account_count=3),
        ]
        doctor = AuthDoctor({})

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            doctor.report(results)

        output = stderr_capture.getvalue()
        assert "aws: OK" in output
        assert "azure: FAILED" in output
        assert "gcp: OK" in output


# -- Tests for AuthDoctor.get_passing_providers --


class TestGetPassingProviders:
    """Tests for AuthDoctor.get_passing_providers() partial continuation."""

    def test_returns_only_passing_providers(self) -> None:
        """get_passing_providers returns names of providers that passed."""
        results = [
            AuthResult(provider="aws", success=True, identity="SSO: prod", account_count=12),
            AuthResult(
                provider="azure",
                success=False,
                identity="",
                account_count=0,
                error_message="Expired",
            ),
            AuthResult(provider="gcp", success=True, identity="SA: sa@proj.iam", account_count=3),
        ]
        doctor = AuthDoctor({})
        passing = doctor.get_passing_providers(results)

        assert passing == ["aws", "gcp"]

    def test_returns_empty_when_all_fail(self) -> None:
        """get_passing_providers returns empty list when all fail."""
        results = [
            AuthResult(
                provider="aws", success=False, identity="", account_count=0, error_message="Err"
            ),
            AuthResult(
                provider="azure", success=False, identity="", account_count=0, error_message="Err"
            ),
        ]
        doctor = AuthDoctor({})
        passing = doctor.get_passing_providers(results)

        assert passing == []

    def test_returns_all_when_all_pass(self) -> None:
        """get_passing_providers returns all names when all pass."""
        results = [
            AuthResult(provider="aws", success=True, identity="SSO: prod", account_count=12),
            AuthResult(provider="azure", success=True, identity="SP: app-123", account_count=5),
        ]
        doctor = AuthDoctor({})
        passing = doctor.get_passing_providers(results)

        assert passing == ["aws", "azure"]


# -- Tests for AUTH-05 enforcement --


class TestAuthResultReadOnly:
    """Tests that AuthResult enforces AUTH-05 (read-only access only)."""

    def test_auth_result_default_read_only_true(self) -> None:
        """AuthResult defaults to read_only=True."""
        result = AuthResult(provider="aws", success=True, identity="test", account_count=1)
        assert result.read_only is True

    def test_auth_result_read_only_on_failure(self) -> None:
        """AuthResult has read_only=True even on failed validation."""
        result = AuthResult(
            provider="aws",
            success=False,
            identity="",
            account_count=0,
            error_message="Failed",
        )
        assert result.read_only is True

    def test_mock_passing_validator_produces_read_only_result(self) -> None:
        """Passing mock validator produces AuthResult with read_only=True."""
        validator = MockPassingValidator("aws", "SSO: prod", 12)
        result = validator.validate()
        assert result.read_only is True

    def test_mock_failing_validator_produces_read_only_result(self) -> None:
        """Failing mock validator produces AuthResult with read_only=True."""
        validator = MockFailingValidator("aws", "Expired")
        result = validator.validate()
        assert result.read_only is True
