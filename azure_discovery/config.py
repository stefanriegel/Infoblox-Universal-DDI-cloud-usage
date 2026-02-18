"""
Azure Configuration Module for Cloud Discovery
Handles Azure-specific configuration and region management.
"""

import logging
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import List, Optional

from azure.identity import (
    ClientSecretCredential,
    DeviceCodeCredential,
    InteractiveBrowserCredential,
    TokenCachePersistenceOptions,
    CredentialUnavailableError,
)
from azure.core.exceptions import ClientAuthenticationError

from shared.config import BaseConfig

# Global cached credential (thread-safe singleton)
_credential_cache = None
_credential_lock = threading.Lock()

logger = logging.getLogger(__name__)


def _find_az_command():
    """Find the Azure CLI command, checking common installation paths on Windows."""
    # Try standard PATH first
    if _check_az_available():
        return ["az"]

    # Common Windows installation paths
    import platform
    if platform.system() == "Windows":
        common_paths = [
            r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
            r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
            r"C:\Users\{}\AppData\Local\Microsoft\WindowsApps\az.cmd".format(os.getenv("USERNAME", "")),
        ]
        for path in common_paths:
            if os.path.exists(path):
                return [path]

    return ["az"]


def _check_az_available():
    """Check if az command is available in PATH."""
    try:
        subprocess.run(
            ["az", "--version"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _has_display() -> bool:
    """Check if an interactive browser can be launched."""
    if sys.platform == "win32":
        return True
    if sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _build_credential():
    """
    Build and return a warmed credential. Raises CredentialUnavailableError on failure.

    Tries in order:
    1. ClientSecretCredential (service principal) if all three env vars are set
    2. InteractiveBrowserCredential if a display is available
    3. DeviceCodeCredential for headless environments
    """
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    tenant_id = os.getenv("AZURE_TENANT_ID")

    attempts = []

    # Path 1: Service principal (all three vars required)
    if client_id and client_secret and tenant_id:
        try:
            cred = ClientSecretCredential(tenant_id, client_id, client_secret)
            cred.get_token("https://management.azure.com/.default")
            print("[Auth] Using ClientSecretCredential (service principal)")
            return cred
        except (CredentialUnavailableError, ClientAuthenticationError) as e:
            attempts.append(f"ClientSecretCredential: {e}")
            # Fall through to interactive
    elif client_id and not (client_secret and tenant_id):
        # Partial env vars — warn and fall through to interactive auth
        missing = []
        if not client_secret:
            missing.append("AZURE_CLIENT_SECRET")
        if not tenant_id:
            missing.append("AZURE_TENANT_ID")
        warning = (
            f"ClientSecretCredential skipped: AZURE_CLIENT_ID set but "
            f"{', '.join(missing)} missing. "
            "Set env vars or remove AZURE_CLIENT_ID to use interactive auth."
        )
        print(f"[Auth] Warning: {warning}")
        attempts.append(warning)

    # Path 2: Interactive (browser or device code depending on environment)
    # Build TokenCachePersistenceOptions with Linux fallback for environments without libsecret
    try:
        cache_opts = TokenCachePersistenceOptions(name="infoblox-ddi-scanner")
    except Exception:
        cache_opts = TokenCachePersistenceOptions(
            name="infoblox-ddi-scanner",
            allow_unencrypted_storage=True,
        )

    if _has_display():
        print("[Auth] Using InteractiveBrowserCredential")
        print("Opening browser for authentication... waiting")
        try:
            cred = InteractiveBrowserCredential(
                cache_persistence_options=cache_opts,
                timeout=120,
            )
            cred.get_token("https://management.azure.com/.default")
            print("[Auth] Browser authentication successful")
            return cred
        except ClientAuthenticationError as e:
            # At startup, any ClientAuthenticationError from the browser credential
            # is treated as a timeout/auth failure — show actionable message
            raise SystemExit("Authentication timed out. Run again to retry.") from e
        except CredentialUnavailableError as e:
            attempts.append(f"InteractiveBrowserCredential: {e}")
            # Fall through to device code
    # Headless path (or if browser credential failed with CredentialUnavailableError)
    def _device_code_callback(verification_uri, user_code, expires_on):
        print(f"Go to {verification_uri} and enter code {user_code}")

    try:
        # Rebuild cache_opts with unencrypted fallback for headless Linux environments
        try:
            cache_opts_headless = TokenCachePersistenceOptions(name="infoblox-ddi-scanner")
        except Exception:
            cache_opts_headless = TokenCachePersistenceOptions(
                name="infoblox-ddi-scanner",
                allow_unencrypted_storage=True,
            )
        print("[Auth] Using DeviceCodeCredential")
        cred = DeviceCodeCredential(
            cache_persistence_options=cache_opts_headless,
            timeout=120,
            prompt_callback=_device_code_callback,
        )
        cred.get_token("https://management.azure.com/.default")
        print("[Auth] Device code authentication successful")
        return cred
    except (CredentialUnavailableError, ClientAuthenticationError) as e:
        attempts.append(f"DeviceCodeCredential: {e}")

    # All paths exhausted — build summary and raise
    summary = "\n".join(f"  - {a}" for a in attempts)
    raise CredentialUnavailableError(
        message=f"All authentication methods failed:\n{summary}"
    )


def get_azure_credential():
    """
    Get Azure credential for authentication.
    Returns a cached singleton credential for thread-safety.
    Tries ClientSecretCredential first, then InteractiveBrowserCredential or DeviceCodeCredential.
    """
    global _credential_cache

    # Return cached credential if available (thread-safe)
    if _credential_cache is not None:
        return _credential_cache

    with _credential_lock:
        # Double-check after acquiring lock
        if _credential_cache is not None:
            return _credential_cache

        _credential_cache = _build_credential()
        return _credential_cache


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
                        _find_az_command() + [
                            "account",
                            "show",
                            "--query",
                            "id",
                            "-o",
                            "tsv",
                        ],
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        check=True,
                    )
                    sub_id = result.stdout.strip()
                    if sub_id:
                        self.subscription_id = sub_id
                except (subprocess.CalledProcessError, FileNotFoundError, UnicodeDecodeError) as e:
                    logger.warning(f"Azure CLI not available or failed: {e}")
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
                    _find_az_command() + [
                        "account",
                        "show",
                        "--query",
                        "id",
                        "-o",
                        "tsv",
                    ],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    check=True,
                )
                subscription_id = result.stdout.strip()
            except (subprocess.CalledProcessError, FileNotFoundError, UnicodeDecodeError) as e:
                logger.warning(f"Azure CLI not available for region detection: {e}")
                return get_major_azure_regions()

        from azure.mgmt.subscription import SubscriptionClient

        subscription_client = SubscriptionClient(credential)
        locations = subscription_client.subscriptions.list_locations(subscription_id)
        regions = [loc.name for loc in locations if loc.name]
        return regions if regions else get_major_azure_regions()

    except Exception as e:
        logger.warning(f"Error getting Azure regions: {e}")
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
        return [sub.subscription_id for sub in subscriptions if sub.state == "Enabled"]
    except Exception as e:
        logger.warning(f"Error getting subscriptions via API: {e}")

        # Fallback: try to get from az CLI
        try:
            result = subprocess.run(
                _find_az_command() + ["account", "list", "--query", "[?state=='Enabled'].id", "-o", "tsv"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                check=True,
            )
            subs = result.stdout.strip().split('\n')
            return [sub for sub in subs if sub.strip()]
        except Exception as e2:
            logger.warning(f"Error getting subscriptions via CLI: {e2}")
            return []


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
        print("Set AZURE_SUBSCRIPTION_ID env var or configure in config")
        return False

    if not config.regions:
        print("Error: No Azure regions specified")
        return False

    if config.output_format not in ["json", "csv", "txt"]:
        print(f"Error: Invalid output format '{config.output_format}'")
        print("Supported formats: json, csv, txt")
        return False

    return True
