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


@dataclass
class AzureConfig:
    """Configuration for Azure cloud discovery."""
    
    # Azure regions to scan (default to major regions)
    regions: Optional[List[str]] = None
    
    # Output configuration
    output_directory: str = "output"
    output_format: str = "txt"  # json, csv, txt
    
    # Azure-specific settings
    subscription_id: Optional[str] = None
    
    def __post_init__(self):
        """Initialize default values after dataclass creation."""
        if self.regions is None:
            self.regions = get_major_azure_regions()
        
        if self.subscription_id is None:
            self.subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
            if not self.subscription_id:
                # Try to auto-detect from Azure CLI
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
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_directory, exist_ok=True)


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
        
        # Create resource management client
        resource_client = ResourceManagementClient(credential, subscription_id)
        
        # Get all locations
        locations = resource_client.subscriptions.list_locations(subscription_id)
        regions = [location.name for location in locations]
        
        print(f"Found {len(regions)} available Azure regions")
        return regions
        
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