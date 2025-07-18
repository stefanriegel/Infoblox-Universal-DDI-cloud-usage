"""
Azure Cloud Discovery Module for Infoblox Universal DDI Resource Counter.
"""

from .azure_discovery import AzureDiscovery
from .config import AzureConfig, get_all_azure_regions, get_azure_credential

__version__ = "1.0.0"
__author__ = "Stefan Riegel"
__all__ = [
    "AzureDiscovery",
    "AzureConfig",
    "get_all_azure_regions",
    "get_azure_credential",
]
