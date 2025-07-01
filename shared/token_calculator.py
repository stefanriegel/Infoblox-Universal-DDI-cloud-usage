"""
Shared token calculation logic for Infoblox Universal DDI Management Tokens.
"""

import math
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class TokenCalculation:
    """Results of Management Token calculation."""
    total_native_objects: int
    management_token_required: int
    management_token_free: int
    breakdown_by_type: Dict[str, int]
    breakdown_by_region: Dict[str, int]
    management_token_free_resources: List[Dict]


def calculate_management_tokens(native_objects: List[Dict], provider: str) -> TokenCalculation:
    """
    Calculate Management Token requirements based on Infoblox Universal DDI rules.
    
    Args:
        native_objects: List of discovered native objects
        provider: Cloud provider (aws, azure)
        
    Returns:
        TokenCalculation object with results
    """
    if not native_objects:
        return TokenCalculation(
            total_native_objects=0,
            management_token_required=0,
            management_token_free=0,
            breakdown_by_type={},
            breakdown_by_region={},
            management_token_free_resources=[]
        )
    
    # Separate token-free and licensed resources
    token_free_resources = []
    licensed_resources = []
    
    for resource in native_objects:
        if resource.get('requires_management_token', True):
            licensed_resources.append(resource)
        else:
            token_free_resources.append(resource)
    
    # Count by type
    breakdown_by_type = {}
    for resource in licensed_resources:
        resource_type = resource.get('resource_type', 'unknown')
        breakdown_by_type[resource_type] = breakdown_by_type.get(resource_type, 0) + 1
    
    # Count by region
    breakdown_by_region = {}
    for resource in licensed_resources:
        region = resource.get('region', 'unknown')
        breakdown_by_region[region] = breakdown_by_region.get(region, 0) + 1
    
    # Calculate tokens based on Infoblox rules:
    # 1 token per 25 DDI objects (DNS, DHCP, IPAM objects)
    # 1 token per 13 active IP addresses  
    # 1 token per 3 assets (VMs, gateways, endpoints with at least one IP)
    
    total_licensed = len(licensed_resources)
    
    # Count assets (VMs, gateways, etc. with IPs)
    assets_with_ips = sum(1 for r in licensed_resources 
                         if r.get('resource_type') in ['vm', 'instance', 'gateway', 'endpoint'])
    
    # Count IP addresses (simplified - each asset typically has at least one IP)
    active_ips = assets_with_ips  # Simplified assumption
    
    # Calculate tokens
    ddi_tokens = math.ceil(total_licensed / 25)
    ip_tokens = math.ceil(active_ips / 13)
    asset_tokens = math.ceil(assets_with_ips / 3)
    
    # Total tokens required (take the maximum of the three calculations)
    management_token_required = max(ddi_tokens, ip_tokens, asset_tokens)
    
    return TokenCalculation(
        total_native_objects=len(native_objects),
        management_token_required=management_token_required,
        management_token_free=len(token_free_resources),
        breakdown_by_type=breakdown_by_type,
        breakdown_by_region=breakdown_by_region,
        management_token_free_resources=token_free_resources
    ) 