"""AWS auth validator for pre-flight credential checks.

Implements AuthValidator ABC using STS get_caller_identity to verify
credentials and Organizations list_accounts to count accessible accounts.
Handles SSO token expiry and missing credentials with actionable suggestions.
"""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from cloud_usage.auth.validators import AuthResult, AuthValidator


class AWSAuthValidator(AuthValidator):
    """Validate AWS credentials and count accessible accounts.

    Creates a boto3 Session with the given profile, calls STS to verify
    identity, then attempts Organizations to count active accounts. Falls
    back to single-account mode on AccessDeniedException.

    Args:
        profile: AWS profile name for the boto3 session, or None for default.
    """

    def __init__(self, profile: str | None = None) -> None:
        self._profile = profile

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "aws"

    def validate(self) -> AuthResult:
        """Check AWS credential validity and count accessible accounts.

        Calls STS get_caller_identity to verify credentials, then tries
        Organizations list_accounts to count active accounts. On Organizations
        failure, falls back to account_count=1 (single-account mode).

        Returns:
            AuthResult with pass/fail status, ARN identity, and account count.
        """
        try:
            session = boto3.Session(profile_name=self._profile)
            sts = session.client("sts")
            identity = sts.get_caller_identity()

            # Try Organizations for account count
            account_count = 1
            try:
                org = session.client("organizations")
                paginator = org.get_paginator("list_accounts")
                accounts = []
                for page in paginator.paginate():
                    accounts.extend(page["Accounts"])
                active = [a for a in accounts if a["Status"] == "ACTIVE"]
                if active:
                    account_count = len(active)
                # If Organizations returns 0 active accounts, keep fallback of 1
            except ClientError:
                # Organizations not available -- single-account mode
                pass

            arn = identity["Arn"]
            return AuthResult(
                provider="aws",
                success=True,
                identity=arn,
                account_count=account_count,
            )

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code == "ExpiredTokenException":
                profile_hint = self._profile or "<your-profile>"
                return AuthResult(
                    provider="aws",
                    success=False,
                    identity="",
                    account_count=0,
                    error_message="AWS SSO token expired or not found",
                    suggestion=f"Run: aws sso login --profile {profile_hint}",
                )
            return AuthResult(
                provider="aws",
                success=False,
                identity="",
                account_count=0,
                error_message=f"AWS authentication failed: {exc}",
                suggestion="Check AWS credentials configuration",
            )

        except NoCredentialsError:
            return AuthResult(
                provider="aws",
                success=False,
                identity="",
                account_count=0,
                error_message="No AWS credentials found",
                suggestion="Configure AWS credentials, set AWS_PROFILE, or run 'aws sso login'",
            )

        except Exception as exc:
            # Handle SSOTokenLoadError and other botocore exceptions.
            # SSOTokenLoadError is not always importable directly, so
            # we check the exception class name.
            exc_name = type(exc).__name__
            if "SSOTokenLoadError" in exc_name or "SSO" in exc_name:
                profile_hint = self._profile or "<your-profile>"
                return AuthResult(
                    provider="aws",
                    success=False,
                    identity="",
                    account_count=0,
                    error_message="AWS SSO token expired or not found",
                    suggestion=f"Run: aws sso login --profile {profile_hint}",
                )

            return AuthResult(
                provider="aws",
                success=False,
                identity="",
                account_count=0,
                error_message=f"AWS authentication failed: {exc}",
                suggestion="Check AWS credentials configuration",
            )
