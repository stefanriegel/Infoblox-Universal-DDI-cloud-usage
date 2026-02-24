"""Azure discovery provider implementing the DiscoveryProvider ABC.

Connects to the Phase 1 orchestrator by implementing list_accounts()
and discover_account(). Supports subscription filtering by GUID and
display name, checkpoint-based resume for completed subscriptions,
and Azure-specific error detection for MissingSubscriptionRegistration,
AuthorizationFailed, SubscriptionNotFound, and 429 throttling errors.
"""

from __future__ import annotations

import logging
import sys

from cloud_usage.discovery.provider import DiscoveryProvider
from cloud_usage.providers.azure.client_factory import create_subscription_clients
from cloud_usage.providers.azure.collectors.compute import (
    collect_azure_vms,
    collect_azure_vmss_instances,
)
from cloud_usage.providers.azure.collectors.database import (
    collect_azure_cosmosdb_accounts,
    collect_azure_mysql_servers,
    collect_azure_postgresql_servers,
    collect_azure_redis_caches,
    collect_azure_sql_databases,
)
from cloud_usage.providers.azure.collectors.dns import (
    collect_azure_dns_records,
    collect_azure_dns_zones,
    collect_azure_private_dns_records,
    collect_azure_private_dns_zones,
)
from cloud_usage.providers.azure.collectors.hybrid_networking import (
    collect_azure_app_gateways,
    collect_azure_bastion_hosts,
    collect_azure_express_route_circuits,
    collect_azure_firewalls,
    collect_azure_load_balancers,
    collect_azure_nat_gateways,
    collect_azure_private_endpoints,
    collect_azure_virtual_wan_hubs,
    collect_azure_vnet_peerings,
    collect_azure_vpn_gateways,
)
from cloud_usage.providers.azure.collectors.networking import (
    collect_azure_dhcp_configs,
    collect_azure_nics,
    collect_azure_public_ips,
    collect_azure_subnets,
    collect_azure_vnets,
)
from cloud_usage.providers.azure.collectors.paas import (
    collect_azure_aks_clusters,
    collect_azure_api_management,
    collect_azure_app_services,
    collect_azure_container_apps_with_client,
    collect_azure_container_instances,
    collect_azure_functions,
)
from cloud_usage.providers.azure.collectors.token_free import (
    collect_azure_disks,
    collect_azure_management_groups,
    collect_azure_network_watchers,
    collect_azure_nsgs,
    collect_azure_resource_groups,
    collect_azure_storage_accounts,
    collect_azure_storage_containers,
    collect_azure_traffic_manager_profiles,
)
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
        runs all collectors in dependency order. VNets are collected first
        since subnets, DHCP configs, peerings, and VPN gateways depend on
        the VNet list. DNS zones are collected before records.

        Checkpoint integration: checks if subscription is already completed
        (key: "azure:{sub_id}:completed") and skips if so.

        Args:
            account_id: Azure subscription GUID to scan.

        Returns:
            List of discovered CloudResource instances.
        """
        # Suppress Azure SDK logging per CONTEXT.md
        logging.getLogger("azure").setLevel(logging.ERROR)

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

        # ---- DDI: VNets first (subnets/DHCP/peerings/VPN depend on VNet list) ----
        vnets = self._safe_collect(
            "VNets", account_id, collect_azure_vnets,
            clients.network, account_id,
        )
        all_resources.extend(vnets)

        subnets = self._safe_collect(
            "Subnets", account_id, collect_azure_subnets,
            clients.network, account_id, vnets,
        )
        all_resources.extend(subnets)

        # DHCP configs extracted from VNets (no API call)
        dhcp_configs = collect_azure_dhcp_configs(vnets)
        all_resources.extend(dhcp_configs)

        # ---- DNS: Zones before records ----
        dns_zones = self._safe_collect(
            "DNS Zones", account_id, collect_azure_dns_zones,
            clients.dns, account_id,
        )
        all_resources.extend(dns_zones)

        dns_records = self._safe_collect(
            "DNS Records", account_id, collect_azure_dns_records,
            clients.dns, account_id, dns_zones,
        )
        all_resources.extend(dns_records)

        private_dns_zones = self._safe_collect(
            "Private DNS Zones", account_id, collect_azure_private_dns_zones,
            clients.privatedns, account_id,
        )
        all_resources.extend(private_dns_zones)

        private_dns_records = self._safe_collect(
            "Private DNS Records", account_id, collect_azure_private_dns_records,
            clients.privatedns, account_id, private_dns_zones,
        )
        all_resources.extend(private_dns_records)

        # ---- Networking: NICs, Public IPs ----
        all_resources.extend(self._safe_collect(
            "NICs", account_id, collect_azure_nics,
            clients.network, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Public IPs", account_id, collect_azure_public_ips,
            clients.network, account_id,
        ))

        # ---- Compute: VMs, VMSS instances ----
        all_resources.extend(self._safe_collect(
            "VMs", account_id, collect_azure_vms,
            clients.compute, clients.network, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "VMSS Instances", account_id, collect_azure_vmss_instances,
            clients.compute, clients.network, account_id,
        ))

        # ---- Hybrid Networking ----
        all_resources.extend(self._safe_collect(
            "Load Balancers", account_id, collect_azure_load_balancers,
            clients.network, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "App Gateways", account_id, collect_azure_app_gateways,
            clients.network, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Firewalls", account_id, collect_azure_firewalls,
            clients.network, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "NAT Gateways", account_id, collect_azure_nat_gateways,
            clients.network, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Private Endpoints", account_id, collect_azure_private_endpoints,
            clients.network, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "VNet Peerings", account_id, collect_azure_vnet_peerings,
            clients.network, account_id, vnets,
        ))

        all_resources.extend(self._safe_collect(
            "ExpressRoute Circuits", account_id, collect_azure_express_route_circuits,
            clients.network, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "VPN Gateways", account_id, collect_azure_vpn_gateways,
            clients.network, account_id, vnets,
        ))

        all_resources.extend(self._safe_collect(
            "Virtual WAN Hubs", account_id, collect_azure_virtual_wan_hubs,
            clients.network, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Bastion Hosts", account_id, collect_azure_bastion_hosts,
            clients.network, account_id,
        ))

        # ---- Database ----
        all_resources.extend(self._safe_collect(
            "SQL Databases", account_id, collect_azure_sql_databases,
            clients.sql, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Cosmos DB", account_id, collect_azure_cosmosdb_accounts,
            clients.cosmosdb, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "MySQL Servers", account_id, collect_azure_mysql_servers,
            clients.mysql, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "PostgreSQL Servers", account_id, collect_azure_postgresql_servers,
            clients.postgresql, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Redis Caches", account_id, collect_azure_redis_caches,
            clients.redis, account_id,
        ))

        # ---- PaaS ----
        all_resources.extend(self._safe_collect(
            "App Services", account_id, collect_azure_app_services,
            clients.web, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Functions", account_id, collect_azure_functions,
            clients.web, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Container Instances", account_id, collect_azure_container_instances,
            clients.container, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Container Apps", account_id, collect_azure_container_apps_with_client,
            clients.appcontainers, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "AKS Clusters", account_id, collect_azure_aks_clusters,
            clients.containerservice, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "API Management", account_id, collect_azure_api_management,
            clients.apimanagement, account_id,
        ))

        # ---- Token-free ----
        all_resources.extend(self._safe_collect(
            "VM Disks", account_id, collect_azure_disks,
            clients.compute, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Storage Accounts", account_id, collect_azure_storage_accounts,
            clients.storage, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Storage Containers", account_id, collect_azure_storage_containers,
            clients.storage, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Management Groups", account_id, collect_azure_management_groups,
            clients.mgmt_groups, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Traffic Manager Profiles", account_id, collect_azure_traffic_manager_profiles,
            clients.trafficmanager, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Network Watchers", account_id, collect_azure_network_watchers,
            clients.network, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "NSGs", account_id, collect_azure_nsgs,
            clients.network, account_id,
        ))

        all_resources.extend(self._safe_collect(
            "Resource Groups", account_id, collect_azure_resource_groups,
            clients.resource, account_id,
        ))

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
        (HttpResponseError with that error code), AuthorizationFailed,
        SubscriptionNotFound, and 429 throttling errors.

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

            # Detect SubscriptionNotFound -- skip entire subscription
            if "SubscriptionNotFound" in exc_msg:
                logger.warning(
                    "Subscription %s not found. Skipping.",
                    subscription_id,
                )
                sys.stderr.write(
                    f"WARNING: Subscription {subscription_id} not found. Skipping.\n"
                )
                return []

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
            if "AuthorizationFailed" in exc_msg or (
                exc_name == "HttpResponseError" and "authorization" in exc_msg.lower()
            ):
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

            # Detect 429 throttling -- log visible warning per CONTEXT.md
            status_code = getattr(exc, "status_code", None)
            if status_code == 429:
                # Extract retry-after from headers if available
                retry_after = getattr(exc, "retry_after", None)
                delay = float(retry_after) if retry_after else 30.0
                display = get_subscription_display(subscription_id, "")
                logger.warning(
                    "Subscription %s: throttled, retrying in %.0fs",
                    display,
                    delay,
                )
                sys.stderr.write(
                    f"WARNING: Subscription {display}: throttled, retrying in {delay:.0f}s\n"
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
