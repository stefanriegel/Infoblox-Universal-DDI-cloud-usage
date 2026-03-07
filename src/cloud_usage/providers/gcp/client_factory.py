"""GCP SDK client creation and lifecycle management.

Creates all shared GCP SDK clients once and wraps them in a GCPClients
dataclass. Clients are project-agnostic (project passed per-call).
Uses _try_create wrapper for graceful handling of missing SDK packages.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GCPClients:
    """All shared GCP SDK clients for resource discovery.

    Each field holds the SDK client instance for that service,
    or None if the SDK package is not installed (optional dependency).
    Clients are project-agnostic -- project ID is passed per-call.

    DNS client is NOT included here because google.cloud.dns.Client
    requires project= at construction time. DNS clients are created
    per-project inside discover_account().

    Args:
        instances: compute_v1.InstancesClient for VM instances.
        networks: compute_v1.NetworksClient for VPC networks.
        subnetworks: compute_v1.SubnetworksClient for subnets.
        addresses: compute_v1.AddressesClient for reserved IPs.
        global_addresses: compute_v1.GlobalAddressesClient for global IPs.
        forwarding_rules: compute_v1.ForwardingRulesClient for LBs.
        disks: compute_v1.DisksClient for persistent disks.
        instance_groups: compute_v1.InstanceGroupsClient for instance groups.
        url_maps: compute_v1.UrlMapsClient for URL maps.
        container: container_v1.ClusterManagerClient for GKE.
        sqladmin: googleapiclient discovery service for Cloud SQL.
    """

    instances: Any | None = None
    networks: Any | None = None
    subnetworks: Any | None = None
    addresses: Any | None = None
    global_addresses: Any | None = None
    forwarding_rules: Any | None = None
    disks: Any | None = None
    instance_groups: Any | None = None
    url_maps: Any | None = None
    container: Any | None = None
    sqladmin: Any | None = None
    routers: Any | None = None
    target_vpn_gateways: Any | None = None


def _try_create(name: str, factory_fn) -> Any | None:
    """Attempt to create a client, returning None on ImportError.

    Args:
        name: Human-readable client name for logging.
        factory_fn: Callable that creates and returns the client.

    Returns:
        The client instance, or None if import fails.
    """
    try:
        return factory_fn()
    except ImportError:
        logger.debug("Optional GCP SDK package not installed for %s", name)
        return None
    except Exception:
        logger.debug("Failed to create %s client", name, exc_info=True)
        return None


def create_shared_clients(credentials) -> GCPClients:
    """Create all shared GCP SDK clients once.

    Clients are project-agnostic (project is passed per API call).
    Each client is created independently with try/except. If an SDK
    package is not installed, that client field is set to None.

    Args:
        credentials: Validated GCP credential object.

    Returns:
        GCPClients dataclass with all available SDK clients.
    """
    clients = GCPClients()

    clients.instances = _try_create(
        "instances",
        lambda: _create_instances_client(credentials),
    )
    clients.networks = _try_create(
        "networks",
        lambda: _create_networks_client(credentials),
    )
    clients.subnetworks = _try_create(
        "subnetworks",
        lambda: _create_subnetworks_client(credentials),
    )
    clients.addresses = _try_create(
        "addresses",
        lambda: _create_addresses_client(credentials),
    )
    clients.global_addresses = _try_create(
        "global_addresses",
        lambda: _create_global_addresses_client(credentials),
    )
    clients.forwarding_rules = _try_create(
        "forwarding_rules",
        lambda: _create_forwarding_rules_client(credentials),
    )
    clients.disks = _try_create(
        "disks",
        lambda: _create_disks_client(credentials),
    )
    clients.instance_groups = _try_create(
        "instance_groups",
        lambda: _create_instance_groups_client(credentials),
    )
    clients.url_maps = _try_create(
        "url_maps",
        lambda: _create_url_maps_client(credentials),
    )
    clients.container = _try_create(
        "container",
        lambda: _create_container_client(credentials),
    )
    clients.sqladmin = _try_create(
        "sqladmin",
        lambda: _create_sqladmin_client(credentials),
    )
    clients.routers = _try_create(
        "routers",
        lambda: _create_routers_client(credentials),
    )
    clients.target_vpn_gateways = _try_create(
        "target_vpn_gateways",
        lambda: _create_target_vpn_gateways_client(credentials),
    )

    return clients


# --- Individual client factory functions ---


def _create_instances_client(credentials):
    from google.cloud import compute_v1
    return compute_v1.InstancesClient(credentials=credentials)


def _create_networks_client(credentials):
    from google.cloud import compute_v1
    return compute_v1.NetworksClient(credentials=credentials)


def _create_subnetworks_client(credentials):
    from google.cloud import compute_v1
    return compute_v1.SubnetworksClient(credentials=credentials)


def _create_addresses_client(credentials):
    from google.cloud import compute_v1
    return compute_v1.AddressesClient(credentials=credentials)


def _create_global_addresses_client(credentials):
    from google.cloud import compute_v1
    return compute_v1.GlobalAddressesClient(credentials=credentials)


def _create_forwarding_rules_client(credentials):
    from google.cloud import compute_v1
    return compute_v1.ForwardingRulesClient(credentials=credentials)


def _create_disks_client(credentials):
    from google.cloud import compute_v1
    return compute_v1.DisksClient(credentials=credentials)


def _create_instance_groups_client(credentials):
    from google.cloud import compute_v1
    return compute_v1.InstanceGroupsClient(credentials=credentials)


def _create_url_maps_client(credentials):
    from google.cloud import compute_v1
    return compute_v1.UrlMapsClient(credentials=credentials)


def _create_container_client(credentials):
    from google.cloud import container_v1
    return container_v1.ClusterManagerClient(credentials=credentials)


def _create_sqladmin_client(credentials):
    from googleapiclient.discovery import build
    return build("sqladmin", "v1", credentials=credentials, cache_discovery=False)


def _create_routers_client(credentials):
    from google.cloud import compute_v1
    return compute_v1.RoutersClient(credentials=credentials)


def _create_target_vpn_gateways_client(credentials):
    from google.cloud import compute_v1
    return compute_v1.TargetVpnGatewaysClient(credentials=credentials)
