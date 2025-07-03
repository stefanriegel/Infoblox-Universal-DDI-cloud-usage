"""
Shared token calculation logic for Infoblox Universal DDI Management Tokens.
"""

import math
from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TokenCalculation:
    """Results of Management Token calculation."""
    total_native_objects: int
    management_token_required: int
    management_token_free: int
    breakdown_by_type: Dict[str, int]
    breakdown_by_region: Dict[str, int]
    management_token_free_resources: List[Dict]
    calculation_timestamp: str
    management_token_packs: int
    management_tokens_packs_total: int
    tokens_ddi: int
    tokens_ips: int
    tokens_assets: int


class UnifiedTokenCalculator:
    """Unified token calculator for both AWS and Azure resources."""
    
    # Resource type mappings for different providers
    DDI_RESOURCE_TYPES = {
        'aws': ['subnet', 'vpc', 'route53-zone', 'route53-record'],
        'azure': ['dns-zone', 'dns-record', 'subnet', 'vnet', 'dhcp-range', 'ipam-block', 'ipam-space', 'host-record', 'ddns-record', 'address-block', 'view', 'zone', 'dtc-lbdn', 'dtc-server', 'dtc-pool', 'dtc-topology-rule', 'dtc-health-check', 'dhcp-exclusion-range', 'dhcp-filter-rule', 'dhcp-option', 'ddns-zone']
    }
    
    ASSET_RESOURCE_TYPES = {
        'aws': ['ec2-instance', 'application-load-balancer', 'network-load-balancer', 'classic-load-balancer'],
        'azure': ['vm', 'gateway', 'endpoint', 'firewall', 'switch', 'router', 'server', 'load_balancer']
    }
    
    IP_DETAIL_KEYS = ['ip', 'private_ip', 'public_ip', 'private_ips', 'public_ips']
    
    def __init__(self, provider: str):
        """
        Initialize the token calculator for a specific provider.
        
        Args:
            provider: Cloud provider ('aws' or 'azure')
        """
        self.provider = provider.lower()
        if self.provider not in ['aws', 'azure']:
            raise ValueError(f"Unsupported provider: {provider}. Must be 'aws' or 'azure'")
    
    def calculate_management_tokens(self, native_objects: List[Dict]) -> TokenCalculation:
        """
        Calculate Management Token requirements based on Infoblox Universal DDI rules.
        
        Args:
            native_objects: List of discovered native objects
            
        Returns:
            TokenCalculation object with results
        """
        if not native_objects:
            return self._create_empty_calculation()
        
        # Separate token-free and licensed resources
        token_free_resources = []
        licensed_resources = []
        
        for resource in native_objects:
            if resource.get('requires_management_token', True):
                licensed_resources.append(resource)
            else:
                token_free_resources.append(resource)
        
        # Calculate breakdowns
        breakdown_by_type = self._calculate_breakdown_by_type(licensed_resources)
        breakdown_by_region = self._calculate_breakdown_by_region(licensed_resources)
        
        # Calculate token requirements
        ddi_objects = self._get_ddi_objects(licensed_resources)
        active_ips = self._get_active_ips(licensed_resources)
        assets = self._get_assets(licensed_resources)
        
        # Token calculations
        tokens_ddi = math.ceil(len(ddi_objects) / 25)
        tokens_ips = math.ceil(len(active_ips) / 13)
        tokens_assets = math.ceil(len(assets) / 3)
        
        # Total tokens required (SUM, not max)
        total_tokens = tokens_ddi + tokens_ips + tokens_assets
        
        # Packs to sell (round up to next 1000)
        packs = math.ceil(total_tokens / 1000)
        tokens_packs_total = packs * 1000
        
        return TokenCalculation(
            total_native_objects=len(native_objects),
            management_token_required=total_tokens,
            management_token_free=len(token_free_resources),
            breakdown_by_type={
                'ddi_objects': len(ddi_objects),
                'active_ips': len(active_ips),
                'assets': len(assets)
            },
            breakdown_by_region=breakdown_by_region,
            management_token_free_resources=token_free_resources,
            calculation_timestamp=datetime.now().isoformat(),
            management_token_packs=packs,
            management_tokens_packs_total=tokens_packs_total,
            tokens_ddi=tokens_ddi,
            tokens_ips=tokens_ips,
            tokens_assets=tokens_assets
        )
    
    def _create_empty_calculation(self) -> TokenCalculation:
        """Create an empty calculation result."""
        return TokenCalculation(
            total_native_objects=0,
            management_token_required=0,
            management_token_free=0,
            breakdown_by_type={},
            breakdown_by_region={},
            management_token_free_resources=[],
            calculation_timestamp=datetime.now().isoformat(),
            management_token_packs=0,
            management_tokens_packs_total=0,
            tokens_ddi=0,
            tokens_ips=0,
            tokens_assets=0
        )
    
    def _calculate_breakdown_by_type(self, resources: List[Dict]) -> Dict[str, int]:
        """Calculate breakdown by resource type."""
        breakdown = {}
        for resource in resources:
            resource_type = resource.get('resource_type', 'unknown')
            breakdown[resource_type] = breakdown.get(resource_type, 0) + 1
        return breakdown
    
    def _calculate_breakdown_by_region(self, resources: List[Dict]) -> Dict[str, int]:
        """Calculate breakdown by region."""
        breakdown = {}
        for resource in resources:
            region = resource.get('region', 'unknown')
            breakdown[region] = breakdown.get(region, 0) + 1
        return breakdown
    
    def _get_ddi_objects(self, resources: List[Dict]) -> List[Dict]:
        """Get DDI objects from resources."""
        ddi_types = self.DDI_RESOURCE_TYPES.get(self.provider, [])
        return [r for r in resources if r.get('resource_type') in ddi_types]
    
    def _get_active_ips(self, resources: List[Dict]) -> List[str]:
        """Get unique active IP addresses from resources."""
        ip_set = set()
        for resource in resources:
            details = resource.get('details', {})
            
            # Check for single IP addresses
            for key in self.IP_DETAIL_KEYS:
                ip = details.get(key)
                if ip and isinstance(ip, str):
                    ip_set.add(ip)
            
            # Check for IP lists
            for key in ['private_ips', 'public_ips']:
                ips = details.get(key)
                if ips and isinstance(ips, list):
                    for ip in ips:
                        if ip:
                            ip_set.add(ip)
            
            # For subnets, check discovered IPs if available
            if resource.get('resource_type') == 'subnet' and 'discovered_ips' in details:
                for ip in details['discovered_ips']:
                    if ip:
                        ip_set.add(ip)
        
        return list(ip_set)
    
    def _get_assets(self, resources: List[Dict]) -> List[Dict]:
        """Get assets (resources with IP addresses) from resources."""
        asset_types = self.ASSET_RESOURCE_TYPES.get(self.provider, [])
        assets = []
        
        for resource in resources:
            if resource.get('resource_type') in asset_types:
                details = resource.get('details', {})
                
                # Check if resource has any IP addresses
                has_ip = False
                for key in self.IP_DETAIL_KEYS:
                    ip = details.get(key)
                    if ip:
                        has_ip = True
                        break
                
                if has_ip:
                    assets.append(resource)
        
        # De-duplicate assets by resource_id
        asset_ids = set()
        unique_assets = []
        for asset in assets:
            if asset['resource_id'] not in asset_ids:
                asset_ids.add(asset['resource_id'])
                unique_assets.append(asset)
        
        return unique_assets


def calculate_management_tokens(native_objects: List[Dict], provider: str) -> TokenCalculation:
    """
    Legacy function for backward compatibility.
    
    Args:
        native_objects: List of discovered native objects
        provider: Cloud provider (aws, azure)
        
    Returns:
        TokenCalculation object with results
    """
    calculator = UnifiedTokenCalculator(provider)
    return calculator.calculate_management_tokens(native_objects)


def is_managed_service(tags: Dict[str, str], provider: str) -> bool:
    """
    Check if a resource is a managed service (Management Token-free).
    
    Args:
        tags: Resource tags
        provider: Cloud provider ('aws' or 'azure')
        
    Returns:
        True if the resource is a managed service
    """
    if not tags:
        return False
    
    # Provider-specific managed service indicators
    indicators = {
        'aws': ['managed', 'service', 'aws', 'eks', 'fargate', 'lambda'],
        'azure': ['managed', 'service', 'azure', 'aks', 'appservice', 'functions']
    }
    
    provider_indicators = indicators.get(provider.lower(), [])
    
    for key, value in tags.items():
        key_lower = key.lower()
        value_lower = value.lower()
        
        # Check if any indicator is in the key or value
        if any(indicator in key_lower for indicator in provider_indicators):
            return True
        if any(indicator in value_lower for indicator in provider_indicators):
            return True
    
    return False 