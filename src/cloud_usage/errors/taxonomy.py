"""
Error taxonomy for cloud API exceptions.

Classifies exceptions into categories with defined handling strategies
(retry, skip, backoff). Provides ErrorRecord for structured error capture
with actionable user-facing messages and fix suggestions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ErrorCategory(Enum):
    """Categorization of cloud API exceptions.

    Each category has a defined handling strategy that determines whether
    the operation should be retried, skipped, or escalated.
    """

    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    API = "api"
    UNKNOWN = "unknown"


CATEGORY_STRATEGIES: dict[str, dict[str, Any]] = {
    ErrorCategory.AUTH: {
        "retryable": False,
        "max_retries": 0,
        "description": "Authentication/authorization failure",
    },
    ErrorCategory.RATE_LIMIT: {
        "retryable": True,
        "max_retries": 5,
        "description": "API rate limit exceeded",
    },
    ErrorCategory.NETWORK: {
        "retryable": True,
        "max_retries": 3,
        "description": "Network connectivity issue",
    },
    ErrorCategory.API: {
        "retryable": False,
        "max_retries": 0,
        "description": "API error (unsupported operation/region)",
    },
    ErrorCategory.UNKNOWN: {
        "retryable": False,
        "max_retries": 0,
        "description": "Unexpected error",
    },
}


# Keywords used for exception classification, organized by category.
# Checked against lowercased exception type name and message.
_AUTH_TYPE_KEYWORDS = ("credential", "auth", "access", "forbidden", "permission")
_AUTH_MSG_KEYWORDS = ("accessdenied", "unauthorized", "forbidden", "403")
_RATE_LIMIT_KEYWORDS = ("429", "throttl", "rate", "too many requests", "retry-after")
_NETWORK_KEYWORDS = ("timeout", "connection", "socket", "dns", "resolve")
_API_KEYWORDS = ("notsupported", "not found", "404", "invalid")


@dataclass
class ErrorRecord:
    """Structured record of a classified cloud API error.

    Captures the provider, account, category, an actionable user-facing
    message, the raw exception text, retry eligibility, and a fix suggestion.

    Args:
        provider: Cloud provider ("aws", "azure", "gcp").
        account_id: AWS account ID, Azure subscription ID, or GCP project ID.
        category: Classified error category.
        message: Actionable user-facing error message.
        raw_exception: String representation of the original exception.
        retryable: Whether the operation can be retried.
        suggestion: Fix hint for the user (e.g., "run: aws sso login").
        timestamp: ISO timestamp of when the error was recorded.
    """

    provider: str
    account_id: str
    category: ErrorCategory
    message: str
    raw_exception: str
    retryable: bool
    suggestion: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


def classify_error(provider: str, exc: Exception) -> ErrorCategory:
    """Classify a cloud API exception into an ErrorCategory.

    Uses exception type name and message content to determine the category.
    Checks are performed in priority order: AUTH > RATE_LIMIT > NETWORK > API > UNKNOWN.

    Args:
        provider: Cloud provider where the error occurred ("aws", "azure", "gcp").
        exc: The raw Python exception to classify.

    Returns:
        The ErrorCategory that best matches the exception.
    """
    exc_type_name = type(exc).__name__.lower()
    exc_message = str(exc).lower()

    # Check for auth errors by type name
    for keyword in _AUTH_TYPE_KEYWORDS:
        if keyword in exc_type_name:
            return ErrorCategory.AUTH

    # Check for auth errors by message content
    for keyword in _AUTH_MSG_KEYWORDS:
        if keyword in exc_message:
            return ErrorCategory.AUTH

    # Check for rate limit errors
    for keyword in _RATE_LIMIT_KEYWORDS:
        if keyword in exc_type_name or keyword in exc_message:
            return ErrorCategory.RATE_LIMIT

    # Check for network errors
    for keyword in _NETWORK_KEYWORDS:
        if keyword in exc_type_name or keyword in exc_message:
            return ErrorCategory.NETWORK

    # Check for API errors
    for keyword in _API_KEYWORDS:
        if keyword in exc_type_name or keyword in exc_message:
            return ErrorCategory.API

    return ErrorCategory.UNKNOWN


# Mapping from ErrorCategory to actionable fix suggestion for users.
_CATEGORY_SUGGESTIONS: dict[str, str] = {
    ErrorCategory.AUTH: "Check that credentials are configured and not expired",
    ErrorCategory.RATE_LIMIT: "Scan will retry automatically",
    ErrorCategory.NETWORK: "Check network connectivity",
    ErrorCategory.API: "This operation may not be supported in the target region",
    ErrorCategory.UNKNOWN: "Check the log file for full details",
}


def create_error_record(provider: str, account_id: str, exc: Exception) -> ErrorRecord:
    """Create an ErrorRecord from a raw exception.

    Classifies the exception, determines retry eligibility from the category
    strategy, and builds an ErrorRecord with an actionable suggestion.

    Args:
        provider: Cloud provider where the error occurred.
        account_id: Account/subscription/project where the error occurred.
        exc: The raw Python exception.

    Returns:
        A fully populated ErrorRecord with classification and suggestion.
    """
    category = classify_error(provider, exc)
    strategy = CATEGORY_STRATEGIES[category]
    suggestion = _CATEGORY_SUGGESTIONS[category]

    return ErrorRecord(
        provider=provider,
        account_id=account_id,
        category=category,
        message=f"{strategy['description']}: {exc}",
        raw_exception=repr(exc),
        retryable=strategy["retryable"],
        suggestion=suggestion,
    )
