#!/usr/bin/env python3
"""
GCP Cloud Discovery for Infoblox Universal DDI Resource Counter.

Discovers GCP Native Objects and calculates Management Token requirements.
"""

import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

from tqdm import tqdm

from shared.base_discovery import BaseDiscovery, DiscoveryConfig

from .config import GCPConfig, get_gcp_credential

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Suppress google cloud logging
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger("google.auth").setLevel(logging.WARNING)
logging.getLogger("google.cloud").setLevel(logging.WARNING)


class GCPDiscovery(BaseDiscovery):
    """GCP Cloud Discovery implementation."""

    _managed_key_prefixes = ("goog-managed-by", "gke-managed", "cloud-run", "cloud-functions")
    _managed_key_exact = frozenset({"managed-by", "managed_by", "google-managed"})
    _managed_value_exact = frozenset({"google-managed", "gke", "cloud-run", "cloud-functions"})

    def __init__(self, config: GCPConfig, shared_compute_clients: Optional[dict] = None):
        """
        Initialize GCP discovery.

        Args:
            config: GCP configuration
            shared_compute_clients: Optional dict of pre-built, project-agnostic compute
                clients to share across GCPDiscovery instances. When provided, the caller
                supplies compute clients and a fresh dns.Client is created per
                instance (EXEC-01 / EXEC-02). When None, the existing _init_gcp_clients()
                path runs unchanged (backward compatible).

                Expected keys: "instances", "zones", "networks", "subnetworks",
                "addresses", "global_addresses", "routers".
        """
        # Convert GCPConfig to DiscoveryConfig
        discovery_config = DiscoveryConfig(
            regions=config.regions or [],
            output_directory=config.output_directory,
            output_format=config.output_format,
            provider="gcp",
        )
        super().__init__(discovery_config)

        # Store original GCP config for GCP-specific functionality
        self.gcp_config = config

        if shared_compute_clients is not None:
            # EXEC-02: reuse caller-provided compute clients (project-agnostic, thread-safe)
            # EXEC-01: create fresh dns.Client per instance (dns.Client stores project= at init)
            credentials, project = get_gcp_credential()
            self.credentials = credentials
            # config.project_id is always set by caller in multi-project mode.
            # In single-project mode, fall back to ADC project for consistency.
            self.project_id = config.project_id or project

            self.compute_client = shared_compute_clients["instances"]
            self.zones_client = shared_compute_clients["zones"]
            self.networks_client = shared_compute_clients["networks"]
            self.subnetworks_client = shared_compute_clients["subnetworks"]
            self.addresses_client = shared_compute_clients["addresses"]
            self.global_addresses_client = shared_compute_clients["global_addresses"]
            self.routers_client = shared_compute_clients.get("routers")

            # dns.Client requires per-project instantiation (stores project= at construction).
            # At v0.35.1 it has no close() method and uses HTTP REST transport — GC handles cleanup.
            from google.cloud import dns

            self.dns_client = dns.Client(project=self.project_id, credentials=credentials)

            # GKE client is project-agnostic (project passed via parent string per call)
            self.container_client = shared_compute_clients.get("container")
            if self.container_client is None:
                try:
                    from google.cloud import container_v1

                    self.container_client = container_v1.ClusterManagerClient(credentials=credentials)
                except ImportError:
                    self.container_client = None

            # Build the zones-by-region cache using the shared zones_client
            self._zones_by_region = self._build_zones_by_region()
        else:
            # Backward-compatible path: create all clients internally
            self._init_gcp_clients()

    def _init_gcp_clients(self):
        """Initialize GCP clients for different services."""
        # Auth exceptions (DefaultCredentialsError, RefreshError) propagate from
        # get_gcp_credential() — the singleton exits on failure, so they never
        # reach here in practice. No bare except wrapping the credential call (CRED-05).
        credentials, project = get_gcp_credential()

        from google.cloud import compute_v1, dns

        self.credentials = credentials
        self.project_id = project or self.gcp_config.project_id

        try:
            # Initialize compute clients (project-agnostic, shared)
            self.compute_client = compute_v1.InstancesClient(credentials=credentials)
            self.zones_client = compute_v1.ZonesClient(credentials=credentials)
            self.networks_client = compute_v1.NetworksClient(credentials=credentials)
            self.subnetworks_client = compute_v1.SubnetworksClient(credentials=credentials)
            self.addresses_client = compute_v1.AddressesClient(credentials=credentials)
            self.global_addresses_client = compute_v1.GlobalAddressesClient(credentials=credentials)
            self.routers_client = compute_v1.RoutersClient(credentials=credentials)

            # DNS client requires per-project instantiation
            self.dns_client = dns.Client(project=self.project_id, credentials=credentials)

            # GKE client (project-agnostic — project passed via parent string per call)
            try:
                from google.cloud import container_v1

                self.container_client = container_v1.ClusterManagerClient(credentials=credentials)
            except ImportError:
                self.container_client = None

            # Cache zone names so we don't guess region-a/b/c.
            self._zones_by_region = self._build_zones_by_region()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize GCP clients: {e}") from e

    def _build_zones_by_region(self) -> Dict[str, List[str]]:
        """Build a {region: [zones]} map once.

        This avoids missing zones by guessing region-a/b/c.
        """
        zones_by_region: Dict[str, List[str]] = {}
        try:
            for zone in self.zones_client.list(project=self.project_id):
                name = getattr(zone, "name", None)
                if not name:
                    continue
                region = name.rsplit("-", 1)[0] if "-" in name else "unknown"
                zones_by_region.setdefault(region, []).append(name)
        except Exception as e:
            self.logger.warning(f"Could not list GCP zones: {e}")

        for region, zones in zones_by_region.items():
            zones.sort()

        return zones_by_region

    def discover_native_objects(self, max_workers: int = 8) -> List[Dict]:
        """
        Discover all Native Objects across all GCP regions.

        Args:
            max_workers: Maximum number of parallel workers

        Returns:
            List of discovered resources
        """
        if self._discovered_resources is not None:
            return self._discovered_resources

        self.logger.info("Starting GCP discovery across all regions...")

        all_resources = []

        # Use all regions and handle errors gracefully during discovery
        valid_regions = self.config.regions
        self.logger.info(f"Using {len(valid_regions)} regions for discovery")

        # Discover regional resources in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_region = {executor.submit(self._discover_region, region): region for region in valid_regions}

            # Use tqdm for progress tracking
            with tqdm(total=len(valid_regions), desc="Completed") as pbar:
                for future in as_completed(future_to_region):
                    region = future_to_region[future]
                    try:
                        region_resources = future.result()
                        all_resources.extend(region_resources)
                        self.logger.debug(f"Discovered {len(region_resources)} resources in {region}")
                    except Exception as e:
                        self.logger.error(f"Error discovering region {region}: {e}")
                    finally:
                        pbar.update(1)

        # Discover global resources (Cloud DNS)
        dns_resources = self._discover_cloud_dns_zones_and_records()
        all_resources.extend(dns_resources)

        self.logger.info(f"Discovery complete. Found {len(all_resources)} Native Objects")

        # Cache the results
        self._discovered_resources = all_resources
        return all_resources

    def _discover_region(self, region: str) -> List[Dict]:
        """
        Discover all Native Objects in a specific GCP region.

        Args:
            region: GCP region name

        Returns:
            List of discovered resources in the region
        """
        region_resources = []

        try:
            # Discover Compute Engine instances
            instances = self._discover_compute_instances(region)
            region_resources.extend(instances)

            # Discover VPC networks
            networks = self._discover_vpc_networks(region)
            region_resources.extend(networks)

            # Discover subnets
            subnets = self._discover_subnets(region)
            region_resources.extend(subnets)

            # Discover reserved/static addresses (allocated even if unattached)
            reserved_ips = self._discover_reserved_ip_addresses(region)
            region_resources.extend(reserved_ips)

            # Discover Cloud NAT IPs from routers
            nat_resources = self._discover_cloud_nat(region)
            region_resources.extend(nat_resources)

            # Discover GKE clusters and their CIDR ranges
            gke_resources = self._discover_gke_clusters(region)
            region_resources.extend(gke_resources)

        except Exception as e:
            self.logger.error(f"Error discovering region {region}: {e}")

        return region_resources

    def _discover_compute_instances(self, region: str) -> List[Dict]:
        """Discover Compute Engine instances in a region.

        Uses a cached zone list instead of guessing region-a/b/c.
        """
        resources: List[Dict] = []
        zones = (getattr(self, "_zones_by_region", {}) or {}).get(region, [])
        if not zones:
            return resources

        for zone in zones:
            try:
                request = {
                    "project": self.project_id,
                    "zone": zone,
                }

                for instance in self.compute_client.list(request=request):
                    instance_name = instance.name
                    instance_id = instance.id
                    machine_type = instance.machine_type.split("/")[-1]
                    status = instance.status

                    private_ips: List[str] = []
                    public_ips: List[str] = []
                    ipv6_ips: List[str] = []
                    network_name = None

                    for interface in getattr(instance, "network_interfaces", []) or []:
                        if getattr(interface, "network_i_p", None):
                            private_ips.append(interface.network_i_p)

                        iface_network = getattr(interface, "network", None)
                        if isinstance(iface_network, str) and iface_network and not network_name:
                            network_name = iface_network.split("/")[-1]

                        for access_config in getattr(interface, "access_configs", []) or []:
                            if getattr(access_config, "nat_i_p", None):
                                public_ips.append(access_config.nat_i_p)

                        # Best-effort IPv6 extraction (field names vary by API versions).
                        for ipv6_cfg in getattr(interface, "ipv6_access_configs", []) or []:
                            for attr in ("external_ipv6", "external_ipv6_address"):
                                val = getattr(ipv6_cfg, attr, None)
                                if val:
                                    ipv6_ips.append(val)

                    # Get labels (tags)
                    try:
                        labels = dict(instance.labels) if instance.labels else {}
                    except AttributeError:
                        labels = {}

                    is_managed = self._is_managed_service(labels)
                    requires_token = bool(private_ips or public_ips or ipv6_ips) and not is_managed

                    details = {
                        "instance_id": instance_id,
                        "instance_name": instance_name,
                        "machine_type": machine_type,
                        "status": status,
                        "private_ip": (private_ips[0] if private_ips else None),
                        "public_ip": (public_ips[0] if public_ips else None),
                        "private_ips": private_ips,
                        "public_ips": public_ips,
                        "ipv6_ips": ipv6_ips,
                        "network": network_name,
                        "zone": zone,
                        "creation_timestamp": getattr(instance, "creation_timestamp", None),
                        "cpu_platform": getattr(instance, "cpu_platform", None),
                    }

                    resources.append(
                        self._format_resource(
                            details,
                            "compute-instance",
                            region,
                            instance_name,
                            requires_token,
                            "active",
                            labels,
                        )
                    )

            except Exception as e:
                self.logger.debug(f"Zone {zone} not available or no instances: {e}")
                continue

        return resources

    def _discover_vpc_networks(self, region: str) -> List[Dict]:
        """Discover VPC networks (global resource, but we check per region)."""
        resources = []
        try:
            # VPC networks are global, but we'll discover them once
            if region == self.config.regions[0]:  # Only discover once
                request = {"project": self.project_id}

                page_result = self.networks_client.list(request=request)
                for network in page_result:
                    network_name = network.name
                    network_id = network.id

                    # Get labels (handle missing field gracefully)
                    try:
                        labels = dict(network.labels) if network.labels else {}
                    except AttributeError:
                        labels = {}

                    # VPC networks always require tokens
                    requires_token = True

                    # Create resource details
                    details = {
                        "network_id": network_id,
                        "network_name": network_name,
                        "auto_create_subnetworks": getattr(network, "auto_create_subnetworks", None),
                        "routing_mode": getattr(network, "routing_mode", None),
                        "mtu": getattr(network, "mtu", None),
                        "creation_timestamp": getattr(network, "creation_timestamp", None),
                    }

                    # Format resource
                    formatted_resource = self._format_resource(
                        details,
                        "vpc-network",
                        "global",
                        network_name,
                        requires_token,
                        "active",
                        labels,
                    )

                    resources.append(formatted_resource)

        except Exception as e:
            self.logger.error(f"Error discovering VPC networks: {e}")

        return resources

    def _discover_subnets(self, region: str) -> List[Dict]:
        """Discover subnets in a region."""
        resources = []
        try:
            request = {"project": self.project_id, "region": region}

            page_result = self.subnetworks_client.list(request=request)
            for subnet in page_result:
                subnet_name = subnet.name
                subnet_id = subnet.id
                network = subnet.network.split("/")[-1]  # Extract network name from full path

                # Get labels (handle missing field gracefully)
                try:
                    labels = dict(subnet.labels) if subnet.labels else {}
                except AttributeError:
                    labels = {}

                # Subnets always require tokens
                requires_token = True

                # Create resource details
                details = {
                    "subnet_id": subnet_id,
                    "subnet_name": subnet_name,
                    "network": network,
                    "ip_cidr_range": getattr(subnet, "ip_cidr_range", None),
                    "gateway_address": getattr(subnet, "gateway_address", None),
                    "ipv6_cidr_range": getattr(subnet, "ipv6_cidr_range", None),
                    "stack_type": str(getattr(subnet, "stack_type", "")) or None,
                    "creation_timestamp": getattr(subnet, "creation_timestamp", None),
                }

                # Format resource
                formatted_resource = self._format_resource(
                    details,
                    "subnet",
                    region,
                    subnet_name,
                    requires_token,
                    "active",
                    labels,
                )

                resources.append(formatted_resource)

        except Exception as e:
            error_msg = str(e)
            if "Unknown region" in error_msg or "Invalid value for field 'region'" in error_msg:
                # Skip invalid regions silently
                self.logger.debug(f"Region {region} not available for subnets: {error_msg}")
            else:
                # Log other errors
                self.logger.error(f"Error discovering subnets in region {region}: {e}")

        return resources

    def _discover_reserved_ip_addresses(self, region: str) -> List[Dict]:
        """Discover reserved/static IP addresses (allocated even if unattached)."""
        resources: List[Dict] = []

        # Regional reserved addresses
        try:
            request = {"project": self.project_id, "region": region}
            for addr in self.addresses_client.list(request=request):
                ip_address = getattr(addr, "address", None)
                name = getattr(addr, "name", None) or ip_address
                if not ip_address or not name:
                    continue

                # Normalize network context for IP-space de-duplication
                network = getattr(addr, "network", None)
                subnetwork = getattr(addr, "subnetwork", None)

                # Get labels (tags)
                try:
                    labels = dict(addr.labels) if getattr(addr, "labels", None) else {}
                except Exception:
                    labels = {}

                details = {
                    "ip_address": ip_address,
                    "address_type": str(getattr(addr, "address_type", "")) or None,
                    "status": str(getattr(addr, "status", "")) or None,
                    "purpose": str(getattr(addr, "purpose", "")) or None,
                    "region": region,
                    "network": (network.split("/")[-1] if isinstance(network, str) and network else None),
                    "subnetwork": (subnetwork.split("/")[-1] if isinstance(subnetwork, str) and subnetwork else None),
                }

                resources.append(
                    self._format_resource(
                        details,
                        "reserved-ip",
                        region,
                        name,
                        True,
                        (details.get("status") or "reserved").lower(),
                        labels,
                    )
                )

        except Exception as e:
            self.logger.warning(f"Error discovering reserved IP addresses in {region}: {e}")

        # Global reserved addresses (discover once)
        if self.config.regions and region == self.config.regions[0]:
            resources.extend(self._discover_global_reserved_ip_addresses())

        return resources

    def _discover_global_reserved_ip_addresses(self) -> List[Dict]:
        resources: List[Dict] = []
        try:
            request = {"project": self.project_id}
            for addr in self.global_addresses_client.list(request=request):
                ip_address = getattr(addr, "address", None)
                name = getattr(addr, "name", None) or ip_address
                if not ip_address or not name:
                    continue

                network = getattr(addr, "network", None)
                try:
                    labels = dict(addr.labels) if getattr(addr, "labels", None) else {}
                except Exception:
                    labels = {}

                details = {
                    "ip_address": ip_address,
                    "address_type": str(getattr(addr, "address_type", "")) or None,
                    "status": str(getattr(addr, "status", "")) or None,
                    "purpose": str(getattr(addr, "purpose", "")) or None,
                    "network": (network.split("/")[-1] if isinstance(network, str) and network else None),
                }

                resources.append(
                    self._format_resource(
                        details,
                        "reserved-ip",
                        "global",
                        name,
                        True,
                        (details.get("status") or "reserved").lower(),
                        labels,
                    )
                )

        except Exception as e:
            self.logger.warning(f"Error discovering global reserved IP addresses: {e}")

        return resources

    def _resolve_nat_ip_address(self, nat_ip_url: str, region: str) -> Optional[str]:
        """Resolve a NAT IP resource URL to its actual IP address.

        Args:
            nat_ip_url: Full resource URL (projects/P/regions/R/addresses/NAME)
            region: Fallback region if URL parsing fails
        """
        if not isinstance(nat_ip_url, str):
            return None
        parts = nat_ip_url.split("/")
        addr_name = parts[-1] if parts else None
        # Extract region from URL: .../regions/<region>/addresses/<name>
        try:
            addr_region = parts[parts.index("regions") + 1]
        except (ValueError, IndexError):
            addr_region = region
        if not addr_name:
            return None
        try:
            addr = self.addresses_client.get(
                project=self.project_id,
                region=addr_region,
                address=addr_name,
            )
            return getattr(addr, "address", None)
        except Exception as e:
            self.logger.debug(f"Could not resolve NAT IP {addr_name}: {e}")
            return None

    def _get_auto_allocated_nat_ips(self, router_name: str, region: str) -> List[str]:
        """Fetch auto-allocated NAT IPs from router status."""
        ips: List[str] = []
        try:
            status_response = self.routers_client.get_router_status(
                project=self.project_id,
                region=region,
                router=router_name,
            )
            result = getattr(status_response, "result", None) or status_response
            for nat_status in getattr(result, "nat_status", []) or []:
                for auto_ip_url in getattr(nat_status, "auto_allocated_nat_ips", []) or []:
                    if isinstance(auto_ip_url, str):
                        resolved = self._resolve_nat_ip_address(auto_ip_url, region)
                        if resolved:
                            ips.append(resolved)
        except Exception as e:
            self.logger.debug(f"Could not get auto-allocated NAT IPs for {router_name}: {e}")
        return ips

    def _discover_cloud_nat(self, region: str) -> List[Dict]:
        """Discover Cloud NAT IPs from routers in a region."""
        resources: List[Dict] = []
        if not getattr(self, "routers_client", None):
            return resources

        try:
            request = {"project": self.project_id, "region": region}
            for router in self.routers_client.list(request=request):
                router_name = getattr(router, "name", None)
                if not router_name:
                    continue

                nats = getattr(router, "nats", None) or []
                for nat_config in nats:
                    nat_name = getattr(nat_config, "name", None) or f"{router_name}-nat"

                    # Get network context from router
                    network = getattr(router, "network", None)
                    network_name = network.split("/")[-1] if isinstance(network, str) and network else None

                    alloc_option = str(getattr(nat_config, "nat_ip_allocate_option", "")) or None
                    source_range = str(getattr(nat_config, "source_subnetwork_ip_ranges_to_nat", "")) or None

                    # Resolve manual NAT IP URLs to actual IP addresses
                    resolved_ips: List[str] = []
                    nat_ip_names: List[str] = []
                    for nat_ip_url in getattr(nat_config, "nat_ips", []) or []:
                        if isinstance(nat_ip_url, str):
                            nat_ip_names.append(nat_ip_url.split("/")[-1])
                            ip = self._resolve_nat_ip_address(nat_ip_url, region)
                            if ip:
                                resolved_ips.append(ip)

                    # Fetch auto-allocated NAT IPs from router status
                    if alloc_option and "AUTO" in str(alloc_option):
                        resolved_ips.extend(self._get_auto_allocated_nat_ips(router_name, region))

                    details = {
                        "router_name": router_name,
                        "nat_name": nat_name,
                        "nat_ip_allocate_option": alloc_option,
                        "source_subnetwork_ip_ranges_to_nat": source_range,
                        "nat_ip_names": nat_ip_names,
                        "network": network_name,
                        "public_ips": resolved_ips,
                    }

                    resources.append(
                        self._format_resource(
                            details,
                            "cloud-nat",
                            region,
                            nat_name,
                            True,
                            "active",
                            {},
                        )
                    )

        except Exception as e:
            self.logger.warning(f"Error discovering Cloud NAT in {region}: {e}")

        return resources

    def _discover_gke_clusters(self, region: str) -> List[Dict]:
        """Discover GKE clusters and their pod/service CIDR ranges."""
        resources: List[Dict] = []
        if not getattr(self, "container_client", None):
            return resources

        try:
            parent = f"projects/{self.project_id}/locations/{region}"
            response = self.container_client.list_clusters(parent=parent)

            for cluster in response.clusters:
                cluster_name = getattr(cluster, "name", None)
                if not cluster_name:
                    continue

                pod_cidr = getattr(cluster, "cluster_ipv4_cidr", None)
                services_cidr = getattr(cluster, "services_ipv4_cidr", None)
                network = getattr(cluster, "network", None)
                subnetwork = getattr(cluster, "subnetwork", None)
                status = str(getattr(cluster, "status", "")).lower() or "unknown"

                try:
                    labels = dict(cluster.resource_labels) if getattr(cluster, "resource_labels", None) else {}
                except (AttributeError, TypeError):
                    labels = {}

                details = {
                    "cluster_name": cluster_name,
                    "cluster_ipv4_cidr": pod_cidr,
                    "services_ipv4_cidr": services_cidr,
                    "network": network,
                    "subnetwork": subnetwork,
                    "location": getattr(cluster, "location", region),
                    "current_node_count": getattr(cluster, "current_node_count", None),
                    "initial_cluster_version": getattr(cluster, "initial_cluster_version", None),
                }

                resources.append(
                    self._format_resource(
                        details,
                        "gke-cluster",
                        region,
                        cluster_name,
                        True,
                        status,
                        labels,
                    )
                )

        except Exception as e:
            error_msg = str(e)
            # Silently skip regions where Container API is not enabled or unavailable
            if "PERMISSION_DENIED" in error_msg or "not enabled" in error_msg or "404" in error_msg:
                self.logger.debug(f"GKE API not available in {region}: {error_msg}")
            else:
                self.logger.warning(f"Error discovering GKE clusters in {region}: {e}")

        return resources

    def _discover_cloud_dns_zones_and_records(self) -> List[Dict]:
        """Discover Cloud DNS zones and records."""
        resources = []
        try:
            # Discover DNS zones
            for zone in self.dns_client.list_zones():
                zone_name = zone.name
                dns_name = zone.dns_name

                # DNS zones always require tokens
                requires_token = True

                # Create resource details
                details = {
                    "zone_id": zone_name,
                    "dns_name": dns_name,
                    "description": getattr(zone, "description", None),
                    "visibility": getattr(zone, "visibility", "unknown"),
                    "creation_timestamp": getattr(zone, "created", None),
                }

                # Format resource
                formatted_resource = self._format_resource(
                    details,
                    "dns-zone",
                    "global",
                    dns_name,
                    requires_token,
                    "active",
                    {},
                )

                resources.append(formatted_resource)

                # Discover DNS records for this zone
                record_resources = self._discover_dns_records(zone)
                resources.extend(record_resources)

        except Exception as e:
            self.logger.error(f"Error discovering Cloud DNS zones: {e}")

        return resources

    def _discover_dns_records(self, zone) -> List[Dict]:
        """Discover DNS records for a specific zone."""
        resources = []
        try:
            for record in zone.list_resource_record_sets():
                record_name = record.name
                record_type = record.record_type

                # DNS records always require tokens
                requires_token = True

                # Create resource details
                details = {
                    "record_name": record_name,
                    "record_type": record_type,
                    "ttl": getattr(record, "ttl", None),
                    "rrdatas": list(getattr(record, "rrdatas", [])),
                    "zone_name": zone.dns_name,
                }

                # Format resource
                formatted_resource = self._format_resource(
                    details,
                    "dns-record",
                    "global",
                    record_name,
                    requires_token,
                    "active",
                    {},
                )

                resources.append(formatted_resource)

        except Exception as e:
            self.logger.error(f"Error discovering DNS records for zone {zone.name}: {e}")

        return resources

    def get_scanned_project_ids(self) -> list:
        """Return the GCP Project ID(s) scanned."""
        return [self.project_id] if self.project_id else []
