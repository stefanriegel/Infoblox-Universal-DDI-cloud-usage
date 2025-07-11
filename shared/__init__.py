"""
Shared utilities for cloud discovery modules.
"""

from .output_utils import (
    save_discovery_results,
    format_azure_resource,
    get_resource_tags,
    safe_get_nested,
)

__all__ = [
    "save_discovery_results",
    "format_azure_resource",
    "get_resource_tags",
    "safe_get_nested",
]

__version__ = "1.0.0"
__author__ = "Stefan Riegel"
