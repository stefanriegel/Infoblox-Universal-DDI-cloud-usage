"""Azure auth validator for pre-flight credential checks.

Implements AuthValidator ABC using DefaultAzureCredential to verify
credentials and SubscriptionClient to count accessible subscriptions.
Handles credential unavailable, expired tokens, and generic auth failures
with contextual error suggestions.
"""

from __future__ import annotations

import logging

from cloud_usage.auth.validators import AuthResult, AuthValidator

# Suppress verbose Azure SDK logging
logging.getLogger("azure").setLevel(logging.ERROR)


class AzureAuthValidator(AuthValidator):
    """Validate Azure credentials and count accessible subscriptions.

    Uses DefaultAzureCredential to obtain a token for the Azure Resource
    Manager endpoint, then enumerates Enabled subscriptions via
    SubscriptionClient. No auto-launch of browser login -- fails with
    helpful error message if credentials are missing.
    """

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "azure"

    def validate(self) -> AuthResult:
        """Check Azure credential validity and count accessible subscriptions.

        Warms the credential by requesting a token for
        https://management.azure.com/.default, then lists subscriptions
        to count Enabled ones and extract tenant_id.

        Returns:
            AuthResult with pass/fail status, tenant identity, and
            subscription count.
        """
        try:
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()

            # Warm credential -- request a token to validate
            credential.get_token("https://management.azure.com/.default")

            # List subscriptions to count enabled ones and get tenant
            from azure.mgmt.resource import SubscriptionClient

            sub_client = SubscriptionClient(credential)
            enabled_subs = []
            tenant_id = ""

            for sub in sub_client.subscriptions.list():
                if sub.state and sub.state.value == "Enabled":
                    enabled_subs.append(sub)
                    if not tenant_id and sub.tenant_id:
                        tenant_id = sub.tenant_id

            return AuthResult(
                provider="azure",
                success=True,
                identity=f"Tenant: {tenant_id}",
                account_count=len(enabled_subs),
            )

        except ImportError:
            return AuthResult(
                provider="azure",
                success=False,
                identity="",
                account_count=0,
                error_message="Azure SDK not installed",
                suggestion="Run: pip install azure-identity azure-mgmt-resource",
            )

        except Exception as exc:
            return self._handle_auth_error(exc)

    def _handle_auth_error(self, exc: Exception) -> AuthResult:
        """Convert Azure auth exceptions to structured AuthResult.

        Handles CredentialUnavailableError, ClientAuthenticationError
        (with token expiry detection), and generic exceptions.

        Args:
            exc: The exception raised during authentication.

        Returns:
            AuthResult with failure status and actionable suggestion.
        """
        exc_name = type(exc).__name__
        exc_msg = str(exc).lower()

        # CredentialUnavailableError: no credentials found at all
        if exc_name == "CredentialUnavailableError":
            return AuthResult(
                provider="azure",
                success=False,
                identity="",
                account_count=0,
                error_message="No Azure credentials found",
                suggestion=(
                    "Run: az login  |  "
                    "Or set AZURE_CLIENT_ID + AZURE_TENANT_ID + AZURE_CLIENT_SECRET"
                ),
            )

        # ClientAuthenticationError: credentials found but invalid/expired
        if exc_name == "ClientAuthenticationError":
            if "expired" in exc_msg or "refresh" in exc_msg:
                return AuthResult(
                    provider="azure",
                    success=False,
                    identity="",
                    account_count=0,
                    error_message="Azure token expired",
                    suggestion="Run: az login",
                )
            return AuthResult(
                provider="azure",
                success=False,
                identity="",
                account_count=0,
                error_message=f"Azure authentication failed: {exc}",
                suggestion="Check credentials. Run: az account list",
            )

        # Fallback: unexpected error
        return AuthResult(
            provider="azure",
            success=False,
            identity="",
            account_count=0,
            error_message=f"Unexpected error: {exc}",
            suggestion="Check Azure credentials and network connectivity",
        )
