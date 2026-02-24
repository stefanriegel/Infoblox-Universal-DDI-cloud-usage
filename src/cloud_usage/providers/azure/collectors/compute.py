"""Azure compute resource collectors.

Discovers VMs and VMSS instances. VMs are discovered with NIC ID references
(no inline NIC resolution -- IPs attributed via NIC collector). VMSS instances
are individually enumerated for accurate IP counting per CONTEXT.md.
"""

from __future__ import annotations

import logging
from typing import Any

from cloud_usage.providers.azure.utils import _extract_resource_group
from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


@retry_with_backoff(max_retries=3)
def collect_azure_vms(
    compute_client: Any,
    network_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all VMs in a subscription.

    Uses compute_client.virtual_machines.list_all() for subscription-level
    enumeration. Per RESEARCH.md Pitfall 4, NICs are collected separately
    as standalone assets -- VMs store NIC IDs for cross-reference but do
    NOT make extra API calls per NIC.

    Args:
        compute_client: Azure ComputeManagementClient.
        network_client: Azure NetworkManagementClient (unused, kept for
            consistent collector signature).
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-vm".
    """
    resources: list[CloudResource] = []

    for vm in compute_client.virtual_machines.list_all():
        rg = _extract_resource_group(vm.id)

        # Extract NIC IDs from network profile (no inline resolution)
        nic_ids: list[str] = []
        if vm.network_profile and vm.network_profile.network_interfaces:
            for nic_ref in vm.network_profile.network_interfaces:
                if nic_ref.id:
                    nic_ids.append(nic_ref.id)

        # VM size from hardware profile
        vm_size = ""
        if vm.hardware_profile:
            vm_size = vm.hardware_profile.vm_size or ""

        resources.append(
            CloudResource(
                resource_id=vm.id,
                resource_type="azure-vm",
                provider="azure",
                account_id=subscription_id,
                region=vm.location,
                name=vm.name,
                ip_addresses=[],
                tags=dict(vm.tags) if vm.tags else {},
                details={
                    "resource_group": rg,
                    "vm_size": vm_size,
                    "provisioning_state": vm.provisioning_state or "",
                    "nic_ids": nic_ids,
                },
            )
        )

    logger.debug(
        "Discovered %d VMs in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_azure_vmss_instances(
    compute_client: Any,
    network_client: Any,
    subscription_id: str,
) -> list[CloudResource]:
    """Discover all VMSS instances in a subscription.

    Per CONTEXT.md and RESEARCH.md Pitfall 6: enumerate individual VM
    instances within each VMSS for accurate IP counting (not just the
    scale set itself). For each VMSS instance, retrieves network interfaces
    to extract private IPs.

    Args:
        compute_client: Azure ComputeManagementClient.
        network_client: Azure NetworkManagementClient.
        subscription_id: Azure subscription ID.

    Returns:
        List of CloudResource with resource_type="azure-vmss-instance".
    """
    resources: list[CloudResource] = []

    for vmss in compute_client.virtual_machine_scale_sets.list_all():
        rg = _extract_resource_group(vmss.id)
        vmss_name = vmss.name

        if not rg or not vmss_name:
            continue

        # Enumerate individual instances within the VMSS
        for instance in compute_client.virtual_machine_scale_set_vms.list(
            rg, vmss_name
        ):
            instance_id = instance.instance_id

            # Get network interfaces for this VMSS instance
            ip_addresses: list[str] = []
            try:
                for nic in network_client.network_interfaces.list_virtual_machine_scale_set_vm_network_interfaces(
                    rg, vmss_name, instance_id
                ):
                    for ip_config in (nic.ip_configurations or []):
                        if ip_config.private_ip_address:
                            ip_addresses.append(ip_config.private_ip_address)
            except Exception:
                logger.warning(
                    "Failed to get NICs for VMSS instance %s/%s/%s",
                    vmss_name,
                    instance_id,
                    subscription_id,
                    exc_info=True,
                )

            resources.append(
                CloudResource(
                    resource_id=instance.id or f"{vmss.id}/virtualMachines/{instance_id}",
                    resource_type="azure-vmss-instance",
                    provider="azure",
                    account_id=subscription_id,
                    region=vmss.location,
                    name=instance.name or f"{vmss_name}_{instance_id}",
                    ip_addresses=ip_addresses,
                    tags=dict(vmss.tags) if vmss.tags else {},
                    details={
                        "resource_group": rg,
                        "vmss_name": vmss_name,
                        "vmss_id": vmss.id,
                        "instance_id": instance_id,
                    },
                )
            )

    logger.debug(
        "Discovered %d VMSS instances in subscription %s",
        len(resources),
        subscription_id,
    )
    return resources
