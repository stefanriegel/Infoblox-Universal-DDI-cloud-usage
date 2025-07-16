"""
Validation utilities for Infoblox Universal DDI Resource Counter.
"""

from typing import Any, Dict

from .constants import (
    ERROR_MESSAGES,
    SUPPORTED_OUTPUT_FORMATS,
    SUPPORTED_PROVIDERS,
)


def validate_provider(provider: str) -> str:
    """
    Validate cloud provider name.

    Args:
        provider: Provider name to validate

    Returns:
        Normalized provider name (lowercase)

    Raises:
        ValueError: If provider is not supported
    """
    if not provider:
        raise ValueError("Provider cannot be empty")

    normalized_provider = provider.lower()
    if normalized_provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            ERROR_MESSAGES["unsupported_provider"].format(
                provider=provider, supported=SUPPORTED_PROVIDERS
            )
        )

    return normalized_provider


def validate_output_format(output_format: str) -> str:
    """
    Validate output format.

    Args:
        output_format: Output format to validate

    Returns:
        Normalized output format (lowercase)

    Raises:
        ValueError: If output format is not supported
    """
    if not output_format:
        raise ValueError("Output format cannot be empty")

    normalized_format = output_format.lower()
    if normalized_format not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(
            ERROR_MESSAGES["invalid_output_format"].format(
                format=output_format, supported=SUPPORTED_OUTPUT_FORMATS
            )
        )

    return normalized_format


def validate_workers(workers: int) -> int:
    """
    Validate number of workers.

    Args:
        workers: Number of workers to validate

    Returns:
        Validated number of workers

    Raises:
        ValueError: If workers is invalid
    """
    if not isinstance(workers, int):
        raise ValueError("Workers must be an integer")

    if workers < 1:
        raise ValueError("Workers must be at least 1")

    if workers > 100:
        raise ValueError("Workers cannot exceed 100")

    return workers


def validate_output_directory(output_directory: str) -> str:
    """
    Validate output directory.

    Args:
        output_directory: Output directory to validate

    Returns:
        Validated output directory

    Raises:
        ValueError: If output directory is invalid
    """
    if not output_directory:
        raise ValueError(ERROR_MESSAGES["missing_output_directory"])

    if not isinstance(output_directory, str):
        raise ValueError("Output directory must be a string")

    return output_directory


def validate_discovery_config(
    provider: str,
    output_format: str,
    workers: int,
    output_directory: str,
) -> Dict[str, Any]:
    """
    Validate complete discovery configuration.

    Args:
        provider: Cloud provider
        output_format: Output format
        workers: Number of workers
        output_directory: Output directory

    Returns:
        Validated configuration dictionary

    Raises:
        ValueError: If any configuration is invalid
    """
    return {
        "provider": validate_provider(provider),
        "output_format": validate_output_format(output_format),
        "workers": validate_workers(workers),
        "output_directory": validate_output_directory(output_directory),
    }


def validate_resource_data(resource: Dict[str, Any]) -> bool:
    """
    Validate resource data structure.

    Args:
        resource: Resource data to validate

    Returns:
        True if resource is valid

    Raises:
        ValueError: If resource is invalid
    """
    required_fields = ["resource_id", "resource_type", "region", "name"]

    for field in required_fields:
        if field not in resource:
            raise ValueError(f"Resource missing required field: {field}")

        if not resource[field]:
            raise ValueError(f"Resource field cannot be empty: {field}")

    return True


def validate_token_calculation_result(result: Dict[str, Any]) -> bool:
    """
    Validate token calculation result.

    Args:
        result: Token calculation result to validate

    Returns:
        True if result is valid

    Raises:
        ValueError: If result is invalid
    """
    required_fields = [
        "total_native_objects",
        "management_token_required",
        "management_token_free",
        "breakdown_by_type",
        "breakdown_by_region",
        "calculation_timestamp",
    ]

    for field in required_fields:
        if field not in result:
            raise ValueError(f"Token calculation result missing required field: {field}")

    # Validate numeric fields
    numeric_fields = [
        "total_native_objects",
        "management_token_required",
        "management_token_free",
    ]

    for field in numeric_fields:
        if not isinstance(result[field], int):
            raise ValueError(f"Token calculation field must be integer: {field}")

        if result[field] < 0:
            raise ValueError(f"Token calculation field cannot be negative: {field}")

    return True


def validate_credentials(provider: str, credentials: Dict[str, Any]) -> bool:
    """
    Validate cloud provider credentials.

    Args:
        provider: Cloud provider
        credentials: Credentials to validate

    Returns:
        True if credentials are valid

    Raises:
        ValueError: If credentials are invalid
    """
    if not credentials:
        raise ValueError(ERROR_MESSAGES["credentials_not_found"])

    # Provider-specific validation
    if provider == "aws":
        required_fields = ["access_key_id", "secret_access_key"]
    elif provider == "azure":
        required_fields = [
            "client_id",
            "client_secret",
            "tenant_id",
            "subscription_id",
        ]
    elif provider == "gcp":
        required_fields = ["project_id", "service_account_key"]
    else:
        raise ValueError(f"Unknown provider for credential validation: {provider}")

    for field in required_fields:
        if field not in credentials or not credentials[field]:
            raise ValueError(f"Missing required credential field: {field}")

    return True
