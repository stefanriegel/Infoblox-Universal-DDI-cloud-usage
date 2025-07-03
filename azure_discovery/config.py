"""
Azure Configuration Module for Cloud Discovery
Handles Azure-specific configuration and region management.
"""

import os
from typing import List, Optional
from dataclasses import dataclass
from azure.mgmt.resource import ResourceManagementClient
from azure.identity import DefaultAzureCredential
import subprocess
import json
from shared.config import BaseConfig


@dataclass
class AzureConfig(BaseConfig):
    """Configuration for Azure cloud discovery."""
    subscription_id: Optional[str] = None
    # regions, output_directory, output_format inherited from BaseConfig

    def __post_init__(self):
        super().__post_init__()
        if not self.regions:
            self.regions = get_major_azure_regions()
        if not self.subscription_id:
            self.subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
            if not self.subscription_id:
                try:
                    print("AZURE_SUBSCRIPTION_ID not set. Attempting to auto-detect from Azure CLI...")
                    result = subprocess.run([
                        'az', 'account', 'show', '--query', 'id', '-o', 'tsv'
                    ], capture_output=True, text=True, check=True)
                    sub_id = result.stdout.strip()
                    if sub_id:
                        print(f"Auto-detected Azure subscription ID: {sub_id}")
                        self.subscription_id = sub_id
                    else:
                        print("Could not auto-detect subscription ID from Azure CLI. Using major regions only.")
                except Exception as e:
                    print(f"Failed to auto-detect subscription ID: {e}")
                    print("Using major regions only.")


def get_major_azure_regions() -> List[str]:
    """
    Get list of major Azure regions for discovery.
    
    Returns:
        List of Azure region names
    """
    return [
        'eastus',           # East US
        'eastus2',          # East US 2
        'southcentralus',   # South Central US
        'westus2',          # West US 2
        'westus3',          # West US 3
        'canadacentral',    # Canada Central
        'northeurope',      # North Europe
        'westeurope',       # West Europe
        'uksouth',          # UK South
        'ukwest',           # UK West
        'francecentral',    # France Central
        'germanywestcentral', # Germany West Central
        'switzerlandnorth', # Switzerland North
        'eastasia',         # East Asia
        'southeastasia',    # Southeast Asia
        'japaneast',        # Japan East
        'japanwest',        # Japan West
        'australiaeast',    # Australia East
        'australiasoutheast', # Australia Southeast
        'brazilsouth',      # Brazil South
        'southafricanorth', # South Africa North
        'centralindia',     # Central India
        'westindia',        # West India
        'southindia',       # South India
    ]


def get_all_azure_regions() -> List[str]:
    """
    Get all available Azure regions for the current subscription.
    
    Returns:
        List of all available Azure region names
    """
    try:
        # Use default Azure credential
        credential = DefaultAzureCredential()
        subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        
        if not subscription_id:
            print("Warning: AZURE_SUBSCRIPTION_ID not set. Using major regions only.")
            return get_major_azure_regions()
        
        # For now, return major regions to avoid dependency issues
        # TODO: Implement full region discovery when azure-mgmt-subscription is available
        print("Using major Azure regions (full region discovery requires azure-mgmt-subscription)")
        return get_major_azure_regions()
        
    except Exception as e:
        print(f"Error fetching Azure regions: {e}")
        print("Falling back to major regions...")
        return get_major_azure_regions()


def get_azure_credential():
    """
    Get Azure credential for authentication.
    
    Returns:
        Azure credential object
    """
    return DefaultAzureCredential()


def validate_azure_config(config: AzureConfig) -> bool:
    """
    Validate Azure configuration.
    
    Args:
        config: Azure configuration object
        
    Returns:
        True if configuration is valid, False otherwise
    """
    if not config.subscription_id:
        print("Error: Azure subscription ID is required")
        print("Set AZURE_SUBSCRIPTION_ID environment variable or configure in config")
        return False
    
    if not config.regions:
        print("Error: No Azure regions specified")
        return False
    
    if config.output_format not in ['json', 'csv', 'txt']:
        print(f"Error: Invalid output format '{config.output_format}'")
        print("Supported formats: json, csv, txt")
        return False
    
    return True 