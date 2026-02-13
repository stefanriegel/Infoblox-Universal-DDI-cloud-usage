"""
GCP Cloud Discovery Module for Infoblox Universal DDI Resource Counter.
"""

from .config import GCPConfig, get_all_gcp_regions, get_gcp_credential
from .gcp_discovery import GCPDiscovery

__all__ = [
    "GCPDiscovery",
    "GCPConfig",
    "get_all_gcp_regions",
    "get_gcp_credential",
]

__version__ = "1.0.0"
__author__ = "Stefan Riegel"
