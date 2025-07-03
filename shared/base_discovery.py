"""
Base discovery class for cloud providers.
Contains common functionality shared between AWS and Azure discovery modules.
"""

import logging
import math
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .token_calculator import UnifiedTokenCalculator, TokenCalculation
from .output_utils import save_discovery_results, save_management_token_results


@dataclass
class DiscoveryConfig:
    """Base configuration for cloud discovery."""
    regions: List[str]
    output_directory: str
    output_format: str
    provider: str


class BaseDiscovery(ABC):
    """Base class for cloud discovery implementations."""
    
    def __init__(self, config: DiscoveryConfig):
        """
        Initialize the base discovery class.
        
        Args:
            config: Discovery configuration
        """
        self.config = config
        self._discovered_resources: Optional[List[Dict]] = None
        self.token_calculator = UnifiedTokenCalculator(config.provider)
        
        # Configure logging
        logging.basicConfig(level=logging.WARNING)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def discover_native_objects(self, max_workers: int = 8) -> List[Dict]:
        """
        Discover native objects in the cloud provider.
        
        Args:
            max_workers: Maximum number of parallel workers
            
        Returns:
            List of discovered resources
        """
        pass
    
    def get_management_token_free_assets(self) -> List[Dict]:
        """
        Get list of Management Token-free assets.
        
        Returns:
            List of resources that don't require Management Tokens
        """
        resources = self.discover_native_objects()
        return [obj for obj in resources if not obj['requires_management_token']]
    
    def calculate_management_token_requirements(self) -> Dict[str, Any]:
        """
        Calculate Management Token requirements using the unified calculator.
        
        Returns:
            Dictionary with calculation results
        """
        resources = self.discover_native_objects()
        calculation = self.token_calculator.calculate_management_tokens(resources)
        
        # Convert to dictionary format for backward compatibility
        return {
            'total_native_objects': calculation.total_native_objects,
            'management_token_required': calculation.management_token_required,
            'management_token_free': calculation.management_token_free,
            'breakdown_by_type': calculation.breakdown_by_type,
            'breakdown_by_region': calculation.breakdown_by_region,
            'management_token_free_resources': calculation.management_token_free_resources,
            'calculation_timestamp': calculation.calculation_timestamp,
            'management_token_packs': calculation.management_token_packs,
            'management_tokens_packs_total': calculation.management_tokens_packs_total,
            'tokens_ddi': calculation.tokens_ddi,
            'tokens_ips': calculation.tokens_ips,
            'tokens_assets': calculation.tokens_assets
        }
    
    def save_discovery_results(self, output_dir: Optional[str] = None) -> Dict[str, str]:
        """
        Save discovery results to files.
        
        Args:
            output_dir: Output directory (uses config default if None)
            
        Returns:
            Dictionary mapping file types to file paths
        """
        # Get discovered resources (will use cached results if available)
        resources = self.discover_native_objects()
        
        # Use provided output directory or config default
        output_directory = output_dir or self.config.output_directory
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save native objects
        native_objects_files = save_discovery_results(
            resources, 
            output_directory, 
            self.config.output_format, 
            timestamp,
            self.config.provider
        )
        
        # Calculate and save Management Token results (will use cached resources)
        calculation_results = self.calculate_management_token_requirements()
        token_files = save_management_token_results(
            calculation_results,
            output_directory,
            self.config.output_format,
            timestamp,
            self.config.provider
        )
        
        # Combine all saved files
        saved_files = {**native_objects_files, **token_files}
        
        return saved_files
    
    def _format_resource(self, resource_data: Dict, resource_type: str, region: str, 
                        name: str, requires_management_token: bool = True, 
                        state: str = 'active', tags: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Format a resource for consistent output.
        
        Args:
            resource_data: Raw resource data
            resource_type: Type of resource
            region: Cloud region
            name: Resource name
            requires_management_token: Whether this resource requires Management Tokens
            state: Resource state
            tags: Resource tags
            
        Returns:
            Formatted resource dictionary
        """
        return {
            'resource_id': f"{region}:{resource_type}:{name}",
            'resource_type': resource_type,
            'region': region,
            'name': name,
            'state': state,
            'requires_management_token': requires_management_token,
            'tags': tags or {},
            'details': resource_data,
            'discovered_at': datetime.now().isoformat()
        }
    
    def _is_managed_service(self, tags: Dict[str, str]) -> bool:
        """
        Check if a resource is a managed service (Management Token-free).
        
        Args:
            tags: Resource tags
            
        Returns:
            True if the resource is a managed service
        """
        from .token_calculator import is_managed_service
        return is_managed_service(tags, self.config.provider)
    
    def _extract_ips_from_details(self, details: Dict[str, Any]) -> List[str]:
        """
        Extract IP addresses from resource details.
        
        Args:
            details: Resource details dictionary
            
        Returns:
            List of IP addresses
        """
        ips = []
        
        # Check for single IP addresses
        for key in ['ip', 'private_ip', 'public_ip']:
            ip = details.get(key)
            if ip and isinstance(ip, str):
                ips.append(ip)
        
        # Check for IP lists
        for key in ['private_ips', 'public_ips']:
            ip_list = details.get(key)
            if ip_list and isinstance(ip_list, list):
                ips.extend([ip for ip in ip_list if ip])
        
        return ips
    
    def _get_resource_name(self, resource: Any, default: str = 'unknown') -> str:
        """
        Extract resource name from various resource formats.
        
        Args:
            resource: Resource object or dictionary
            default: Default name if not found
            
        Returns:
            Resource name
        """
        if hasattr(resource, 'name'):
            return getattr(resource, 'name', default)
        elif isinstance(resource, dict):
            return resource.get('name', default)
        else:
            return default
    
    def _get_resource_tags(self, resource: Any) -> Dict[str, str]:
        """
        Extract tags from various resource formats.
        
        Args:
            resource: Resource object or dictionary
            
        Returns:
            Resource tags dictionary
        """
        if hasattr(resource, 'tags'):
            tags = getattr(resource, 'tags', {})
            return tags if tags else {}
        elif isinstance(resource, dict):
            return resource.get('tags', {})
        else:
            return {}
    
    def _get_resource_id(self, resource: Any, region: str, resource_type: str, name: str) -> str:
        """
        Generate a consistent resource ID.
        
        Args:
            resource: Resource object or dictionary
            region: Cloud region
            resource_type: Type of resource
            name: Resource name
            
        Returns:
            Resource ID
        """
        # Try to get native resource ID first
        if hasattr(resource, 'id'):
            return getattr(resource, 'id', f"{region}:{resource_type}:{name}")
        elif isinstance(resource, dict):
            return resource.get('id', f"{region}:{resource_type}:{name}")
        else:
            return f"{region}:{resource_type}:{name}" 