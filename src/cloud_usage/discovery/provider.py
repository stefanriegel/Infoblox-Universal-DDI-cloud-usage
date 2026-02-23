"""Abstract DiscoveryProvider interface for cloud resource scanning.

Defines the DiscoveryProvider ABC that concrete cloud providers implement
in Phases 2-4. Each provider discovers resources across multiple
accounts/subscriptions/projects. The discover_account() method is the
unit of concurrent work dispatched by the DiscoveryOrchestrator.
"""

from __future__ import annotations

import abc

from cloud_usage.schema.resource import CloudResource


class DiscoveryProvider(abc.ABC):
    """Abstract base class for cloud provider discovery implementations.

    Concrete implementations (AWSDiscoveryProvider, AzureDiscoveryProvider,
    GCPDiscoveryProvider) are created in Phases 2-4. Each implementation
    wraps provider-specific SDK calls behind this uniform interface.
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier.

        Returns:
            Provider name string: "aws", "azure", or "gcp".
        """

    @abc.abstractmethod
    def list_accounts(self) -> list[str]:
        """List all account/subscription/project IDs available for scanning.

        Returns:
            List of account identifiers to scan.
        """

    @abc.abstractmethod
    def discover_account(self, account_id: str) -> list[CloudResource]:
        """Discover all resources in a single account.

        This is the unit of work dispatched by the DiscoveryOrchestrator.
        Each call scans one account/subscription/project and returns all
        discovered resources.

        Args:
            account_id: The account/subscription/project ID to scan.

        Returns:
            List of discovered CloudResource instances.
        """
