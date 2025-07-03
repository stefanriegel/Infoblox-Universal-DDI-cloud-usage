"""
Azure Utilities Module for Cloud Discovery
Handles Azure-specific data processing and formatting.
"""

from typing import Dict, List, Any
from shared.output_utils import (
    format_azure_resource,
    save_discovery_results,
    save_management_token_results,
    save_summary_results,
    safe_get_nested
)


def format_azure_vm_resource(vm, region: str, requires_management_token: bool = True) -> Dict[str, Any]:
    """
    Format Azure VM resource data for consistent output.
    
    Args:
        vm: Azure VM object
        region: Azure region
        requires_management_token: Whether this resource requires Management Tokens
        
    Returns:
        Formatted resource dictionary
    """
    # Extract VM-specific fields
    vm_id = safe_get_nested(vm, 'id', '')
    vm_name = safe_get_nested(vm, 'name', '')
    vm_tags = safe_get_nested(vm, 'tags', {})
    vm_state = safe_get_nested(vm, 'instance_view.statuses.1.display_status', 'running')
    
    # Create formatted resource
    formatted = {
        'resource_id': f"{region}:vm:{vm_name}",
        'resource_type': 'vm',
        'region': region,
        'name': vm_name,
        'state': vm_state,
        'requires_management_token': requires_management_token,
        'tags': vm_tags,
        'details': {
            'id': vm_id,
            'size': safe_get_nested(vm, 'hardware_profile.vm_size', 'unknown'),
            'os_type': safe_get_nested(vm, 'storage_profile.os_disk.os_type', 'unknown'),
            'location': safe_get_nested(vm, 'location', region)
        }
    }
    
    return formatted


def format_azure_vnet_resource(vnet, region: str, requires_management_token: bool = True) -> Dict[str, Any]:
    """
    Format Azure VNet resource data for consistent output.
    
    Args:
        vnet: Azure VNet object
        region: Azure region
        requires_management_token: Whether this resource requires Management Tokens
        
    Returns:
        Formatted resource dictionary
    """
    # Extract VNet-specific fields
    vnet_id = safe_get_nested(vnet, 'id', '')
    vnet_name = safe_get_nested(vnet, 'name', '')
    vnet_tags = safe_get_nested(vnet, 'tags', {})
    
    # Create formatted resource
    formatted = {
        'resource_id': f"{region}:vnet:{vnet_name}",
        'resource_type': 'vnet',
        'region': region,
        'name': vnet_name,
        'state': 'active',
        'requires_management_token': requires_management_token,
        'tags': vnet_tags,
        'details': {
            'id': vnet_id,
            'address_space': safe_get_nested(vnet, 'address_space.address_prefixes', []),
            'location': safe_get_nested(vnet, 'location', region)
        }
    }
    
    return formatted


def format_azure_subnet_resource(subnet, vnet_name: str, region: str, requires_management_token: bool = True) -> Dict[str, Any]:
    """
    Format Azure Subnet resource data for consistent output.
    
    Args:
        subnet: Azure Subnet object
        vnet_name: Parent VNet name
        region: Azure region
        requires_management_token: Whether this resource requires Management Tokens
        
    Returns:
        Formatted resource dictionary
    """
    # Extract Subnet-specific fields
    subnet_id = safe_get_nested(subnet, 'id', '')
    subnet_name = safe_get_nested(subnet, 'name', '')
    subnet_tags = safe_get_nested(subnet, 'tags', {})
    
    # Create formatted resource
    formatted = {
        'resource_id': f"{region}:subnet:{subnet_name}",
        'resource_type': 'subnet',
        'region': region,
        'name': f"subnet-{vnet_name}",
        'state': 'active',
        'requires_management_token': requires_management_token,
        'tags': subnet_tags,
        'details': {
            'id': subnet_id,
            'address_prefix': safe_get_nested(subnet, 'address_prefix', ''),
            'vnet_name': vnet_name,
            'location': safe_get_nested(subnet, 'location', region)
        }
    }
    
    return formatted 