#!/usr/bin/env python3
"""
GCP Cloud Discovery for Infoblox Universal DDI Resource Counter.

Discovers GCP Native Objects and calculates Management Token requirements.
"""

import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from tqdm import tqdm

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.base_discovery import BaseDiscovery, DiscoveryConfig
from shared.output_utils import (
    save_discovery_results,
    save_resource_count_results,
)

from .config import GCPConfig, get_gcp_credential

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Suppress google cloud logging
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger("google.auth").setLevel(logging.WARNING)
logging.getLogger("google.cloud").setLevel(logging.WARNING)


class GCPDiscovery(BaseDiscovery):
    """GCP Cloud Discovery implementation."""

    def __init__(self, config: GCPConfig):
        """
        Initialize GCP discovery.

        Args:
            config: GCP configuration
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

        # Initialize GCP clients
        self._init_gcp_clients()

    def _init_gcp_clients(self):
        """Initialize GCP clients for different services."""
        try:
            credentials, project = get_gcp_credential()

            # Import GCP clients
            from google.cloud import compute_v1, dns

            self.credentials = credentials
            self.project_id = project or self.gcp_config.project_id

            # Initialize clients
            self.compute_client = compute_v1.InstancesClient(credentials=credentials)
            self.networks_client = compute_v1.NetworksClient(credentials=credentials)
            self.subnetworks_client = compute_v1.SubnetworksClient(
                credentials=credentials
            )
            self.dns_client = dns.Client(
                project=self.project_id, credentials=credentials
            )

        except Exception as e:
            raise Exception(f"Failed to initialize GCP clients: {e}")

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
            future_to_region = {
                executor.submit(self._discover_region, region): region
                for region in valid_regions
            }

            # Use tqdm for progress tracking
            with tqdm(total=len(valid_regions), desc="Completed") as pbar:
                for future in as_completed(future_to_region):
                    region = future_to_region[future]
                    try:
                        region_resources = future.result()
                        all_resources.extend(region_resources)
                        self.logger.debug(
                            f"Discovered {len(region_resources)} resources in {region}"
                        )
                    except Exception as e:
                        self.logger.error(f"Error discovering region {region}: {e}")
                    finally:
                        pbar.update(1)

        # Discover global resources (Cloud DNS)
        dns_resources = self._discover_cloud_dns_zones_and_records()
        all_resources.extend(dns_resources)

        self.logger.info(
            f"Discovery complete. Found {len(all_resources)} Native Objects"
        )

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

        except Exception as e:
            self.logger.error(f"Error discovering region {region}: {e}")

        return region_resources

    def _discover_compute_instances(self, region: str) -> List[Dict]:
        """Discover Compute Engine instances in a region."""
        resources = []
        try:
            # List instances in the region
            request = {
                "project": self.project_id,
                "zone": f"{region}-a",  # GCP zones are region + letter (a, b, c)
            }

            # Try multiple zones in the region
            for zone_letter in ["a", "b", "c"]:
                try:
                    zone = f"{region}-{zone_letter}"
                    request["zone"] = zone

                    page_result = self.compute_client.list(request=request)
                    for instance in page_result:
                        # Extract instance details
                        instance_name = instance.name
                        instance_id = instance.id
                        machine_type = instance.machine_type.split("/")[-1]
                        status = instance.status

                        # Extract IP addresses
                        private_ip = None
                        public_ip = None

                        for interface in instance.network_interfaces:
                            if interface.network_i_p:
                                private_ip = interface.network_i_p
                            for access_config in interface.access_configs:
                                if access_config.nat_i_p:
                                    public_ip = access_config.nat_i_p

                        # Get labels (tags)
                        try:
                            labels = dict(instance.labels) if instance.labels else {}
                        except AttributeError:
                            labels = {}

                        # Determine if Management Token is required
                        is_managed = self._is_managed_service(labels)
                        requires_token = (
                            bool(private_ip or public_ip) and not is_managed
                        )

                        # Create resource details
                        details = {
                            "instance_id": instance_id,
                            "instance_name": instance_name,
                            "machine_type": machine_type,
                            "status": status,
                            "private_ip": private_ip,
                            "public_ip": public_ip,
                            "zone": zone,
                            "creation_timestamp": getattr(
                                instance, "creation_timestamp", None
                            ),
                            "cpu_platform": getattr(instance, "cpu_platform", None),
                        }

                        # Format resource
                        formatted_resource = self._format_resource(
                            details,
                            "compute-instance",
                            region,
                            instance_name,
                            requires_token,
                            "active",
                            labels,
                        )

                        resources.append(formatted_resource)

                except Exception as e:
                    self.logger.debug(f"Zone {zone} not available or no instances: {e}")
                    continue

        except Exception as e:
            error_msg = str(e)
            if (
                "Unknown region" in error_msg
                or "Invalid value for field 'region'" in error_msg
            ):
                # Skip invalid regions silently
                self.logger.debug(
                    f"Region {region} not available for compute instances: {error_msg}"
                )
            else:
                # Log other errors
                self.logger.error(
                    f"Error discovering instances in region {region}: {e}"
                )

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
                        "auto_create_subnetworks": getattr(
                            network, "auto_create_subnetworks", None
                        ),
                        "routing_mode": getattr(network, "routing_mode", None),
                        "mtu": getattr(network, "mtu", None),
                        "creation_timestamp": getattr(
                            network, "creation_timestamp", None
                        ),
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
                network = subnet.network.split("/")[
                    -1
                ]  # Extract network name from full path

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
            if (
                "Unknown region" in error_msg
                or "Invalid value for field 'region'" in error_msg
            ):
                # Skip invalid regions silently
                self.logger.debug(
                    f"Region {region} not available for subnets: {error_msg}"
                )
            else:
                # Log other errors
                self.logger.error(f"Error discovering subnets in region {region}: {e}")

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

                # Skip SOA and NS records (they're part of the zone)
                if record_type in ["SOA", "NS"]:
                    continue

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
            self.logger.error(
                f"Error discovering DNS records for zone {zone.name}: {e}"
            )

        return resources

    def _is_managed_service(self, labels: Dict[str, str]) -> bool:
        """Check if a resource is a managed service (doesn't require tokens)."""
        # Check for common managed service indicators in labels
        managed_indicators = [
            "goog-managed-by",
            "managed-by",
            "google-managed",
            "gke-managed",
            "cloud-run",
            "cloud-functions",
        ]

        for key, value in labels.items():
            if any(
                indicator in key.lower() or indicator in value.lower()
                for indicator in managed_indicators
            ):
                return True

        return False

    def get_scanned_project_ids(self) -> list:
        """Return the GCP Project ID(s) scanned."""
        return [self.project_id] if self.project_id else []
