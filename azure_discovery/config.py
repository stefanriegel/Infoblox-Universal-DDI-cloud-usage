"""
Azure Configuration Module for Cloud Discovery
Handles Azure-specific configuration and region management.
"""

import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from azure.identity import DefaultAzureCredential, ClientSecretCredential

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
            self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
            if not self.subscription_id:
                try:
                    result = subprocess.run(
                        [
                            "az",
                            "account",
                            "show",
                            "--query",
                            "id",
                            "-o",
                            "tsv",
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    sub_id = result.stdout.strip()
                    if sub_id:
                        self.subscription_id = sub_id
                except Exception:
                    pass


def get_major_azure_regions() -> List[str]:
    """
    Get list of major Azure regions for discovery.

    Returns:
        List of Azure region names
    """
    return [
        "eastus",  # East US
        "eastus2",  # East US 2
        "southcentralus",  # South Central US
        "westus2",  # West US 2
        "westus3",  # West US 3
        "canadacentral",  # Canada Central
        "northeurope",  # North Europe
        "westeurope",  # West Europe
        "uksouth",  # UK South
        "ukwest",  # UK West
        "francecentral",  # France Central
        "germanywestcentral",  # Germany West Central
        "switzerlandnorth",  # Switzerland North
        "eastasia",  # East Asia
        "southeastasia",  # Southeast Asia
        "japaneast",  # Japan East
        "japanwest",  # Japan West
        "australiaeast",  # Australia East
        "australiasoutheast",  # Australia Southeast
        "brazilsouth",  # Brazil South
        "southafricanorth",  # South Africa North
        "centralindia",  # Central India
        "westindia",  # West India
        "southindia",  # South India
    ]


def get_all_azure_regions() -> List[str]:
    """
    Get all available Azure regions for the current subscription.

    Returns:
        List of all available Azure region names
    """
    try:
        credential = get_azure_credential()
        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")

        if not subscription_id:
            # Try to get from az CLI
            try:
                result = subprocess.run(
                    [
                        "az",
                        "account",
                        "show",
                        "--query",
                        "id",
                        "-o",
                        "tsv",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                subscription_id = result.stdout.strip()
            except Exception:
                return get_major_azure_regions()

        from azure.mgmt.subscription import SubscriptionClient
        subscription_client = SubscriptionClient(credential)
        locations = subscription_client.subscriptions.list_locations(
            subscription_id
        )
        regions = [loc.name for loc in locations if loc.name]
        return regions if regions else get_major_azure_regions()

    except Exception:
        return get_major_azure_regions()


def get_all_subscription_ids() -> List[str]:
    """
    Get all enabled Azure subscription IDs accessible to current credentials.
    If AZURE_SUBSCRIPTION_ID is set, returns only that subscription.

    Returns:
        List of subscription IDs
    """
    # If specific subscription is set, use only that one
    specific_sub = os.getenv("AZURE_SUBSCRIPTION_ID")
    if specific_sub:
        return [specific_sub]

    try:
        credential = get_azure_credential()
        from azure.mgmt.subscription import SubscriptionClient
        subscription_client = SubscriptionClient(credential)
        subscriptions = list(subscription_client.subscriptions.list())
        return [
            sub.subscription_id for sub in subscriptions
            if sub.state == 'Enabled'
        ]
    except Exception as e:
        print(f"Error getting subscriptions: {e}")
        return []


def get_azure_credential():
    """
    Get Azure credential for authentication.

    Tries service principal first, then DefaultAzureCredential.

    Returns:
        Azure credential object
    """
    # Check for service principal credentials in environment
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    tenant_id = os.getenv("AZURE_TENANT_ID")

    if client_id and client_secret and tenant_id:
        # Use service principal credentials if available
        return ClientSecretCredential(
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id
        )
    else:
        # Fall back to DefaultAzureCredential
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
        print(
            "Set AZURE_SUBSCRIPTION_ID env var or configure in config"
        )
        return False

    if not config.regions:
        print("Error: No Azure regions specified")
        return False

    if config.output_format not in ["json", "csv", "txt"]:
        print(f"Error: Invalid output format '{config.output_format}'")
        print("Supported formats: json, csv, txt")
        return False

    return True
