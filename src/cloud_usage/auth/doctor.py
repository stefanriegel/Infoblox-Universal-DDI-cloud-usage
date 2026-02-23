"""
Auth doctor: pre-flight credential validation orchestrator.

Runs auth validators for each selected cloud provider before scan execution
starts, reports pass/fail results to stderr with actionable suggestions,
and enables partial-provider continuation when some providers fail.
"""

from __future__ import annotations

import sys

from cloud_usage.auth.validators import AuthResult, AuthValidator


class AuthDoctor:
    """Pre-flight auth validation orchestrator.

    Validates credentials for selected cloud providers before discovery
    begins, preventing wasted scan time on invalid credentials.

    Args:
        validators: Mapping of provider name to AuthValidator instance.
    """

    def __init__(self, validators: dict[str, AuthValidator]) -> None:
        self._validators = validators

    def check_all(self, selected_providers: list[str]) -> list[AuthResult]:
        """Run validation for each selected provider.

        For each provider in selected_providers, looks up the registered
        validator and calls validate(). If no validator is registered for
        a provider, creates a failed AuthResult.

        Args:
            selected_providers: List of provider names to validate
                (e.g., ["aws", "azure"]).

        Returns:
            List of AuthResult, one per selected provider.
        """
        results: list[AuthResult] = []
        for provider in selected_providers:
            validator = self._validators.get(provider)
            if validator is not None:
                results.append(validator.validate())
            else:
                results.append(
                    AuthResult(
                        provider=provider,
                        success=False,
                        identity="",
                        account_count=0,
                        error_message=f"No validator registered for {provider}",
                        suggestion=None,
                    )
                )
        return results

    def report(self, results: list[AuthResult]) -> bool:
        """Print pre-flight checklist to stderr.

        Writes a pass/fail line per provider with context (identity,
        account count) for successes and actionable fix suggestions
        for failures.

        Args:
            results: List of AuthResult from check_all().

        Returns:
            True if ALL results passed, False otherwise.
        """
        for result in results:
            if result.success:
                sys.stderr.write(
                    f"  {result.provider}: OK"
                    f" ({result.identity}, {result.account_count} accounts accessible)\n"
                )
            else:
                sys.stderr.write(f"  {result.provider}: FAILED -- {result.error_message}\n")
                if result.suggestion:
                    sys.stderr.write(f"    Fix: {result.suggestion}\n")

        return all(r.success for r in results)

    def get_passing_providers(self, results: list[AuthResult]) -> list[str]:
        """Return provider names that passed validation.

        Used by the caller to offer partial-provider continuation when
        some providers fail (e.g., "Continue with AWS and GCP only?").

        Args:
            results: List of AuthResult from check_all().

        Returns:
            List of provider name strings that passed validation.
        """
        return [r.provider for r in results if r.success]
