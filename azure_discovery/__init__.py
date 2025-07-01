"""
Azure Cloud Discovery Module for Infoblox Universal DDI Management Token Calculator.
"""

from .azure_discovery import AzureDiscovery
from .config import AzureConfig, get_all_azure_regions, get_azure_credential
from .historical_analysis import AzureActivityAnalyzer

__version__ = "1.0.0"
__author__ = "Stefan Riegel"
__all__ = [
    "AzureDiscovery",
    "AzureConfig", 
    "get_all_azure_regions",
    "get_azure_credential",
    "AzureActivityAnalyzer"
] 