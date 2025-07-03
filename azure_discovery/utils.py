"""
Azure Utilities Module for Cloud Discovery
Handles output formatting and data processing for Azure resources.
"""

import json
import pandas as pd
from typing import Dict, List, Any
from datetime import datetime
import os


def save_to_json(data: List[Dict], filepath: str) -> str:
    """
    Save data to JSON file.
    
    Args:
        data: List of dictionaries to save
        filepath: Path to save the file
        
    Returns:
        Path to saved file
    """
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    return filepath


def save_to_csv(data: List[Dict], filepath: str) -> str:
    """
    Save data to CSV file.
    
    Args:
        data: List of dictionaries to save
        filepath: Path to save the file
        
    Returns:
        Path to saved file
    """
    if not data:
        # Create empty DataFrame with expected columns
        df = pd.DataFrame(columns=pd.Index([
            'resource_id', 'resource_type', 'region', 'name', 'state',
            'requires_management_token', 'tags', 'details', 'discovered_at'
        ]))
    else:
        df = pd.DataFrame(data)
    
    df.to_csv(filepath, index=False)
    return filepath


def save_to_txt(data: List[Dict], filepath: str) -> str:
    """
    Save data to human-readable text file.
    
    Args:
        data: List of dictionaries to save
        filepath: Path to save the file
        
    Returns:
        Path to saved file
    """
    with open(filepath, 'w') as f:
        if not data:
            f.write("No Azure Native Objects found.\n")
            return filepath
        
        f.write("Azure Native Objects Discovery Results\n")
        f.write("=" * 50 + "\n\n")
        
        for i, resource in enumerate(data, 1):
            f.write(f"Resource {i}:\n")
            f.write(f"  ID: {resource.get('resource_id', 'N/A')}\n")
            f.write(f"  Type: {resource.get('resource_type', 'N/A')}\n")
            f.write(f"  Region: {resource.get('region', 'N/A')}\n")
            f.write(f"  Name: {resource.get('name', 'N/A')}\n")
            f.write(f"  State: {resource.get('state', 'N/A')}\n")
            f.write(f"  Requires Management Token: {resource.get('requires_management_token', 'N/A')}\n")
            
            # Format tags
            tags = resource.get('tags', {})
            if tags:
                f.write(f"  Tags: {tags}\n")
            
            # Format details
            details = resource.get('details', {})
            if details:
                f.write(f"  Details: {details}\n")
            
            f.write(f"  Discovered: {resource.get('discovered_at', 'N/A')}\n")
            f.write("\n")
    
    return filepath


def save_discovery_results(data: List[Dict], output_dir: str, output_format: str, 
                          timestamp: str) -> Dict[str, str]:
    """
    Save discovery results in the specified format.
    
    Args:
        data: List of resource dictionaries
        output_dir: Output directory
        output_format: Output format (json, csv, txt)
        timestamp: Timestamp for filename
        
    Returns:
        Dictionary mapping file types to file paths
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename
    filename = f"azure_native_objects_{timestamp}.{output_format}"
    filepath = os.path.join(output_dir, filename)
    
    # Save based on format
    if output_format == 'json':
        save_to_json(data, filepath)
    elif output_format == 'csv':
        save_to_csv(data, filepath)
    elif output_format == 'txt':
        save_to_txt(data, filepath)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")
    
    return {'native_objects': filepath}


def save_management_token_results(calculation_results: Dict, output_dir: str, 
                                 output_format: str, timestamp: str) -> Dict[str, str]:
    """
    Save Management Token calculation results.
    
    Args:
        calculation_results: Dictionary with calculation results
        output_dir: Output directory
        output_format: Output format
        timestamp: Timestamp for filename
        
    Returns:
        Dictionary mapping file types to file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    
    saved_files = {}
    
    # Save Management Token calculation
    calc_filename = f"azure_management_token_calculation_{timestamp}.{output_format}"
    calc_filepath = os.path.join(output_dir, calc_filename)
    
    if output_format == 'json':
        with open(calc_filepath, 'w') as f:
            json.dump(calculation_results, f, indent=2, default=str)
    elif output_format == 'csv':
        # Flatten the calculation results for CSV
        flat_data = []
        for resource_type, count in calculation_results.get('breakdown_by_type', {}).items():
            flat_data.append({
                'resource_type': resource_type,
                'count': count,
                'requires_management_token': True
            })
        df = pd.DataFrame(flat_data)
        df.to_csv(calc_filepath, index=False)
    else:  # txt
        with open(calc_filepath, 'w') as f:
            f.write("Azure Management Token Calculation\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Total Native Objects: {calculation_results.get('total_native_objects', 0)}\n")
            f.write(f"Management Tokens Required: {calculation_results.get('management_token_required', 0)}\n")
            f.write(f"Management Token-Free: {calculation_results.get('management_token_free', 0)}\n\n")
            f.write("Breakdown by Type:\n")
            for resource_type, count in calculation_results.get('breakdown_by_type', {}).items():
                f.write(f"  {resource_type}: {count}\n")
            f.write("\nBreakdown by Region:\n")
            for region, count in calculation_results.get('breakdown_by_region', {}).items():
                f.write(f"  {region}: {count}\n")
    
    saved_files['management_token_calculation'] = calc_filepath
    
    # Save Management Token-free resources
    free_resources = calculation_results.get('management_token_free_resources', [])
    free_filename = f"azure_management_token_free_{timestamp}.{output_format}"
    free_filepath = os.path.join(output_dir, free_filename)
    
    if output_format == 'json':
        save_to_json(free_resources, free_filepath)
    elif output_format == 'csv':
        save_to_csv(free_resources, free_filepath)
    else:  # txt
        save_to_txt(free_resources, free_filepath)
    
    saved_files['management_token_free'] = free_filepath
    
    # Save summary
    summary_data = {
        'total_native_objects': calculation_results.get('total_native_objects', 0),
        'management_token_required': calculation_results.get('management_token_required', 0),
        'management_token_free': calculation_results.get('management_token_free', 0),
        'calculation_timestamp': timestamp
    }
    
    summary_filename = f"azure_discovery_summary_{timestamp}.{output_format}"
    summary_filepath = os.path.join(output_dir, summary_filename)
    
    if output_format == 'json':
        with open(summary_filepath, 'w') as f:
            json.dump(summary_data, f, indent=2, default=str)
    elif output_format == 'csv':
        df = pd.DataFrame([summary_data])
        df.to_csv(summary_filepath, index=False)
    else:  # txt
        with open(summary_filepath, 'w') as f:
            f.write("Azure Discovery Summary\n")
            f.write("=" * 25 + "\n\n")
            f.write(f"Total Native Objects: {summary_data['total_native_objects']}\n")
            f.write(f"Management Tokens Required: {summary_data['management_token_required']}\n")
            f.write(f"Management Token-Free: {summary_data['management_token_free']}\n")
            f.write(f"Calculation Timestamp: {summary_data['calculation_timestamp']}\n")
    
    saved_files['summary'] = summary_filepath
    
    return saved_files


def format_azure_resource(resource: Dict, resource_type: str, region: str, requires_management_token: bool = True) -> Dict[str, Any]:
    """
    Format Azure resource data for consistent output.
    
    Args:
        resource: Raw Azure resource data (from vars() on Azure SDK model)
        resource_type: Type of resource (vm, vnet, subnet, etc.)
        region: Azure region
        requires_management_token: Whether this resource requires Management Tokens
        
    Returns:
        Formatted resource dictionary
    """
    # Extract common fields - use getattr for Azure SDK model compatibility
    resource_id = getattr(resource, 'id', '') if hasattr(resource, 'id') else resource.get('id', '')
    name = getattr(resource, 'name', '') if hasattr(resource, 'name') else resource.get('name', '')
    tags = getattr(resource, 'tags', {}) if hasattr(resource, 'tags') else resource.get('tags', {})
    
    # Create formatted resource
    formatted = {
        'resource_id': f"{region}:{resource_type}:{name}",
        'resource_type': resource_type,
        'region': region,
        'name': name,
        'state': getattr(resource, 'provisioning_state', 'unknown') if hasattr(resource, 'provisioning_state') else resource.get('provisioning_state', 'unknown'),
        'requires_management_token': requires_management_token,
        'tags': tags,
        'details': {},
        'discovered_at': datetime.now().isoformat()
    }
    
    # Helper function to safely get nested attributes
    def safe_get_nested(obj, attr_path, default: Any = 'unknown'):
        """Safely get nested attributes from Azure SDK model objects."""
        current = obj
        for attr in attr_path.split('.'):
            if hasattr(current, attr):
                current = getattr(current, attr)
            elif isinstance(current, dict) and attr in current:
                current = current[attr]
            else:
                return default
        return current
    
    # Add resource-specific details
    if resource_type == 'vm':
        formatted['details'] = {
            'vm_size': safe_get_nested(resource, 'hardware_profile.vm_size'),
            'os_type': safe_get_nested(resource, 'storage_profile.os_disk.os_type'),
            'network_interfaces': len(safe_get_nested(resource, 'network_profile.network_interfaces', [])),
            'location': safe_get_nested(resource, 'location', region)
        }
    elif resource_type == 'vnet':
        formatted['details'] = {
            'address_space': safe_get_nested(resource, 'address_space.address_prefixes', []),
            'subnets': len(safe_get_nested(resource, 'subnets', [])),
            'location': safe_get_nested(resource, 'location', region)
        }
    elif resource_type == 'subnet':
        formatted['details'] = {
            'address_prefix': safe_get_nested(resource, 'address_prefix'),
            'vnet_id': safe_get_nested(resource, 'virtual_network.id'),
            'location': safe_get_nested(resource, 'location', region)
        }
    elif resource_type == 'load_balancer':
        formatted['details'] = {
            'sku': safe_get_nested(resource, 'sku.name'),
            'frontend_ip_configurations': len(safe_get_nested(resource, 'frontend_ip_configurations', [])),
            'backend_address_pools': len(safe_get_nested(resource, 'backend_address_pools', [])),
            'location': safe_get_nested(resource, 'location', region)
        }
    
    return formatted 