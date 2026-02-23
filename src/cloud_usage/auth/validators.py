"""
Abstract auth validator protocol and result types.

Defines the AuthValidator ABC that concrete cloud provider validators
implement (Phases 2-4), and the AuthResult dataclass for structured
validation outcomes with actionable suggestions.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class AuthResult:
    """Result of a pre-flight auth validation check.

    Captures pass/fail status, identity context, accessible account count,
    and an actionable fix suggestion when validation fails.

    Args:
        provider: Cloud provider identifier ("aws", "azure", "gcp").
        success: True if the auth check passed.
        identity: Human-readable identity description
            (e.g., "SSO profile: prod" or "Service Principal: app-123").
        account_count: Number of accessible accounts/subscriptions/projects.
        error_message: Error description if validation failed, None otherwise.
        suggestion: Actionable fix hint when validation fails
            (e.g., "run: aws sso login --profile prod").
        read_only: Always True -- enforces AUTH-05 (read-only access only).
    """

    provider: str
    success: bool
    identity: str
    account_count: int
    error_message: str | None = None
    suggestion: str | None = None
    read_only: bool = True


class AuthValidator(abc.ABC):
    """Abstract base class for cloud provider auth validators.

    Concrete implementations are created per provider in Phases 2-4.
    Each validator checks credential validity and makes a lightweight
    API call to verify basic read access. No write API calls are ever made.
    """

    @abc.abstractmethod
    def validate(self) -> AuthResult:
        """Check credential validity and verify basic read access.

        Returns:
            AuthResult with pass/fail status, identity, and account count.
        """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier.

        Returns:
            Provider name string: "aws", "azure", or "gcp".
        """
