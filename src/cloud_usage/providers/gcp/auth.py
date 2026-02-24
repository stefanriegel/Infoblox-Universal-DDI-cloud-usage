"""GCP auth validator for pre-flight credential checks.

Implements AuthValidator ABC using google.auth.default() to verify
Application Default Credentials and count accessible projects.
Handles DefaultCredentialsError, RefreshError, and generic auth
failures with contextual error suggestions.
"""

from __future__ import annotations

import logging

from cloud_usage.auth.validators import AuthResult, AuthValidator

# Suppress verbose Google SDK logging
logging.getLogger("google").setLevel(logging.ERROR)


class GCPAuthValidator(AuthValidator):
    """Validate GCP credentials and count accessible projects.

    Uses google.auth.default() to obtain Application Default Credentials,
    then validates them with credentials.refresh(Request()). Counts
    accessible ACTIVE projects via resourcemanager_v3.ProjectsClient.

    No browser launch -- fails with helpful error if credentials are missing.
    """

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "gcp"

    def validate(self) -> AuthResult:
        """Check GCP credential validity and count accessible projects.

        Calls google.auth.default() to discover credentials, validates
        them with a token refresh, then counts ACTIVE projects.

        Returns:
            AuthResult with pass/fail status, project identity, and
            project count.
        """
        try:
            from google.auth import default
            from google.auth.transport.requests import Request

            credentials, project = default()

            # Validate credentials by forcing a token refresh
            credentials.refresh(Request())

            # Count accessible projects
            project_count = self._count_projects(credentials)

            identity = f"Project: {project}" if project else "ADC (no default project)"

            return AuthResult(
                provider="gcp",
                success=True,
                identity=identity,
                account_count=max(project_count, 1),
            )

        except ImportError:
            return AuthResult(
                provider="gcp",
                success=False,
                identity="",
                account_count=0,
                error_message="GCP SDK not installed",
                suggestion="Run: pip install google-auth google-cloud-resource-manager",
            )

        except Exception as exc:
            return self._handle_auth_error(exc)

    def _count_projects(self, credentials) -> int:
        """Count accessible ACTIVE projects using Resource Manager.

        Args:
            credentials: Validated GCP credentials.

        Returns:
            Number of accessible ACTIVE projects.
        """
        try:
            from google.cloud import resourcemanager_v3

            client = resourcemanager_v3.ProjectsClient(credentials=credentials)
            request = resourcemanager_v3.SearchProjectsRequest(query="state:ACTIVE")
            count = 0
            for _project in client.search_projects(request=request):
                count += 1
            return count
        except Exception:
            # If project listing fails, return 0 -- auth was already validated
            return 0

    def _handle_auth_error(self, exc: Exception) -> AuthResult:
        """Convert GCP auth exceptions to structured AuthResult.

        Handles DefaultCredentialsError, RefreshError, and generic
        exceptions with contextual suggestions.

        Args:
            exc: The exception raised during authentication.

        Returns:
            AuthResult with failure status and actionable suggestion.
        """
        exc_name = type(exc).__name__

        # DefaultCredentialsError: no credentials found at all
        if exc_name == "DefaultCredentialsError":
            return AuthResult(
                provider="gcp",
                success=False,
                identity="",
                account_count=0,
                error_message="No GCP credentials found",
                suggestion=(
                    "Run: gcloud auth application-default login  |  "
                    "Or set GOOGLE_APPLICATION_CREDENTIALS=..."
                ),
            )

        # RefreshError: credentials found but expired/invalid
        if exc_name == "RefreshError":
            return AuthResult(
                provider="gcp",
                success=False,
                identity="",
                account_count=0,
                error_message="GCP credentials expired",
                suggestion="Run: gcloud auth application-default login",
            )

        # Fallback: unexpected error
        return AuthResult(
            provider="gcp",
            success=False,
            identity="",
            account_count=0,
            error_message=f"Unexpected error: {exc}",
            suggestion="Check GCP credentials and network connectivity",
        )
