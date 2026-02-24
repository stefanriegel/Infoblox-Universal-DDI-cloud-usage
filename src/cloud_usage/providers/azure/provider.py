"""Azure discovery provider implementing the DiscoveryProvider ABC.

Connects to the Phase 1 orchestrator by implementing list_accounts()
and discover_account(). Supports subscription filtering by GUID and
display name, checkpoint-based resume for completed subscriptions,
and Azure-specific error detection for MissingSubscriptionRegistration
and AuthorizationFailed errors.
"""

from __future__ import annotations

import logging
import sys

from cloud_usage.discovery.provider import DiscoveryProvider
from cloud_usage.providers.azure.client_factory import create_subscription_clients
from cloud_usage.providers.azure.subscriptions import get_subscription_display
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


class AzureDiscoveryProvider(DiscoveryProvider):
    """Azure implementation of the discovery provider interface.

    Lists subscriptions with include/exclude filtering, discovers
    resources within each subscription using Azure management SDK
    clients, and integrates with checkpoint engine for resume support.

    Args:
        credential: Azure credential object (DefaultAzureCredential or similar).
        subscriptions: List of subscription dicts from list_subscriptions().
        include_subscriptions: If provided, only scan these subscription IDs or
            display names (case-insensitive).
        exclude_subscriptions: If provided, exclude these subscription IDs or
            display names from scan.
        checkpoint_engine: Optional checkpoint engine for resume support.
    """

    def __init__(
        self,
        credential,
        subscriptions: list[dict],
        include_subscriptions: list[str] | None = None,
        exclude_subscriptions: list[str] | None = None,
        checkpoint_engine=None,
    ) -> None:
        self._credential = credential
        self._subscriptions = subscriptions
        self._include = include_subscriptions
        self._exclude = exclude_subscriptions
        self._checkpoint_engine = checkpoint_engine

        # Build id -> display_name mapping for output formatting
        self._display_names: dict[str, str] = {
            sub["id"]: sub.get("display_name", "")
            for sub in subscriptions
        }

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "azure"

    def list_accounts(self) -> list[str]:
        """List filtered subscription IDs to scan.

        If include_subscriptions is provided, matches by subscription_id
        (exact GUID match) OR display_name (case-insensitive). If
        exclude_subscriptions is provided (and no include), excludes by
        the same matching. Include takes precedence over exclude per
        CONTEXT.md.

        Logs the pre-scan subscription summary with display names.

        Returns:
            Filtered list of Azure subscription ID strings.
        """
        sub_ids = [sub["id"] for sub in self._subscriptions]

        # Apply filtering: include takes precedence over exclude
        if self._include is not None:
            include_lower = {s.lower() for s in self._include}
            sub_ids = [
                s for s in sub_ids
                if s.lower() in include_lower
                or self._display_names.get(s, "").lower() in include_lower
            ]
        elif self._exclude is not None:
            exclude_lower = {s.lower() for s in self._exclude}
            sub_ids = [
                s for s in sub_ids
                if s.lower() not in exclude_lower
                and self._display_names.get(s, "").lower() not in exclude_lower
            ]

        # Log pre-scan summary with display names
        for sub_id in sub_ids:
            display = get_subscription_display(
                sub_id, self._display_names.get(sub_id, "")
            )
            logger.info("Subscription to scan: %s", display)

        return sub_ids

    def discover_account(self, account_id: str) -> list[CloudResource]:
        """Discover all resources in a single Azure subscription.

        Creates management clients via create_subscription_clients and
        runs all collectors. Currently a skeleton returning an empty list;
        collector wiring will be added in Plan 04.

        Checkpoint integration: checks if subscription is already completed
        (key: "azure:{sub_id}:completed") and skips if so. Writes
        checkpoint key on successful completion.

        Args:
            account_id: Azure subscription GUID to scan.

        Returns:
            List of discovered CloudResource instances (empty for now).
        """
        # Check if this subscription was already completed (checkpoint)
        checkpoint_key = f"azure:{account_id}:completed"

        if self._checkpoint_engine is not None:
            existing = self._checkpoint_engine.load()
            if existing is not None:
                azure_progress = existing.providers.get("azure")
                if azure_progress and account_id in azure_progress.completed_accounts:
                    display = get_subscription_display(
                        account_id, self._display_names.get(account_id, "")
                    )
                    logger.info(
                        "Skipping already-completed subscription: %s (checkpoint key: %s)",
                        display,
                        checkpoint_key,
                    )
                    return []

        # Create all management clients for this subscription
        clients = create_subscription_clients(self._credential, account_id)

        all_resources: list[CloudResource] = []

        # SKELETON: Collector wiring will be added in Plan 04.
        # Each collector will follow the _safe_collect pattern below.

        display = get_subscription_display(
            account_id, self._display_names.get(account_id, "")
        )
        logger.info(
            "Discovered %d resources in subscription %s",
            len(all_resources),
            display,
        )
        return all_resources

    @staticmethod
    def _safe_collect(
        resource_type: str,
        subscription_id: str,
        collector_fn,
        *args,
    ) -> list[CloudResource]:
        """Call a collector function with Azure-specific error isolation.

        If the collector raises an exception, logs a warning and returns
        an empty list. Specifically detects MissingSubscriptionRegistration
        (HttpResponseError with that error code) and AuthorizationFailed
        errors for targeted skip-with-warning behavior.

        Per CONTEXT.md: unregistered providers skip with warning,
        AuthorizationFailed per-resource-type not per-subscription.

        Args:
            resource_type: Human-readable resource type name for logging.
            subscription_id: Azure subscription GUID being scanned.
            collector_fn: The collector function to call.
            *args: Arguments to pass to the collector function.

        Returns:
            List of discovered CloudResource instances, or empty on failure.
        """
        try:
            return collector_fn(*args)
        except Exception as exc:
            exc_msg = str(exc)
            exc_name = type(exc).__name__

            # Detect MissingSubscriptionRegistration
            if "MissingSubscriptionRegistration" in exc_msg:
                logger.warning(
                    "Resource provider not registered for %s in subscription %s. Skipping.",
                    resource_type,
                    subscription_id,
                )
                sys.stderr.write(
                    f"WARNING: Resource provider not registered for {resource_type} "
                    f"in subscription {subscription_id}. Skipping.\n"
                )
                return []

            # Detect AuthorizationFailed
            if "AuthorizationFailed" in exc_msg or exc_name == "HttpResponseError" and "authorization" in exc_msg.lower():
                logger.warning(
                    "Authorization failed for %s in subscription %s. Skipping resource type.",
                    resource_type,
                    subscription_id,
                )
                sys.stderr.write(
                    f"WARNING: Authorization failed for {resource_type} "
                    f"in subscription {subscription_id}. Skipping.\n"
                )
                return []

            # Generic failure
            logger.warning(
                "Failed to collect %s in subscription %s",
                resource_type,
                subscription_id,
                exc_info=True,
            )
            sys.stderr.write(
                f"WARNING: Failed to collect {resource_type} "
                f"in subscription {subscription_id}. Continuing.\n"
            )
            return []
