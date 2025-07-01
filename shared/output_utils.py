"""
Shared output utilities for saving discovery results.
"""

import json
import os
import csv
import pandas as pd
from typing import Dict, List, Any
from datetime import datetime


def save_output(data: Any, filename: str, output_dir: str, format_type: str = "json") -> str:
    """Save discovery data to file in specified format."""
    os.makedirs(output_dir, exist_ok=True)
    
    if format_type == "json":
        filepath = os.path.join(output_dir, f"{filename}.json")
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    elif format_type == "csv":
        filepath = os.path.join(output_dir, f"{filename}.csv")
        if isinstance(data, list) and data:
            # Convert list of dictionaries to CSV
            df = pd.DataFrame(data)
            df.to_csv(filepath, index=False)
        else:
            # For non-list data, create a simple CSV
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                if isinstance(data, dict):
                    for key, value in data.items():
                        writer.writerow([key, str(value)])
                else:
                    writer.writerow([str(data)])
    
    elif format_type == "txt":
        filepath = os.path.join(output_dir, f"{filename}.txt")
        with open(filepath, 'w') as f:
            if isinstance(data, dict):
                for key, value in data.items():
                    f.write(f"{key}: {value}\n")
            elif isinstance(data, list):
                for item in data:
                    f.write(f"{item}\n")
            else:
                f.write(str(data))
    
    else:
        raise ValueError(f"Unsupported format: {format_type}")
    
    return filepath


def save_discovery_results(data: List[Dict], output_dir: str, output_format: str, 
                          timestamp: str, provider: str) -> Dict[str, str]:
    """
    Save discovery results in the specified format.
    
    Args:
        data: List of resource dictionaries
        output_dir: Output directory
        output_format: Output format (json, csv, txt)
        timestamp: Timestamp for filename
        provider: Cloud provider (aws, azure)
        
    Returns:
        Dictionary mapping file types to file paths
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename
    filename = f"{provider}_native_objects_{timestamp}.{output_format}"
    filepath = os.path.join(output_dir, filename)
    
    # Save based on format
    if output_format == 'json':
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    elif output_format == 'csv':
        if not data:
            # Create empty DataFrame with expected columns
            df = pd.DataFrame(columns=pd.Index([
                'resource_id', 'resource_type', 'region', 'name', 'state',
                'requires_management_token', 'tags', 'details', 'discovered_at'
            ]))
        else:
            df = pd.DataFrame(data)
        df.to_csv(filepath, index=False)
    else:  # txt
        with open(filepath, 'w') as f:
            if not data:
                f.write(f"No {provider.upper()} Native Objects found.\n")
                return {'native_objects': filepath}
            
            f.write(f"{provider.upper()} Native Objects Discovery Results\n")
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
    
    return {'native_objects': filepath}


def save_management_token_results(calculation_results: Dict, output_dir: str, output_format: str, 
                                 timestamp: str, provider: str) -> Dict[str, str]:
    """
    Save Management Token calculation results in the specified format.
    
    Args:
        calculation_results: Token calculation results dictionary
        output_dir: Output directory
        output_format: Output format (json, csv, txt)
        timestamp: Timestamp for filename
        provider: Cloud provider (aws, azure)
        
    Returns:
        Dictionary mapping file types to file paths
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    saved_files = {}
    
    # Save main calculation results
    calc_filename = f"{provider}_management_token_calculation_{timestamp}.{output_format}"
    calc_filepath = os.path.join(output_dir, calc_filename)
    
    if output_format == 'json':
        with open(calc_filepath, 'w') as f:
            json.dump(calculation_results, f, indent=2, default=str)
    elif output_format == 'csv':
        # Flatten the calculation results for CSV
        flat_data = {
            'total_native_objects': calculation_results.get('total_native_objects', 0),
            'management_token_required': calculation_results.get('management_token_required', 0),
            'management_token_free': calculation_results.get('management_token_free', 0),
            'calculation_timestamp': calculation_results.get('calculation_timestamp', '')
        }
        df = pd.DataFrame([flat_data])
        df.to_csv(calc_filepath, index=False)
    else:  # txt
        with open(calc_filepath, 'w') as f:
            f.write(f"{provider.upper()} Management Token Calculation Results\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Total Native Objects: {calculation_results.get('total_native_objects', 0)}\n")
            f.write(f"Management Tokens Required: {calculation_results.get('management_token_required', 0)}\n")
            f.write(f"Management Token-Free: {calculation_results.get('management_token_free', 0)}\n")
            f.write(f"Calculation Timestamp: {calculation_results.get('calculation_timestamp', '')}\n\n")
            
            # Breakdown by type
            breakdown_by_type = calculation_results.get('breakdown_by_type', {})
            if breakdown_by_type:
                f.write("Breakdown by Type:\n")
                for resource_type, count in breakdown_by_type.items():
                    f.write(f"  {resource_type}: {count}\n")
                f.write("\n")
            
            # Breakdown by region
            breakdown_by_region = calculation_results.get('breakdown_by_region', {})
            if breakdown_by_region:
                f.write("Breakdown by Region:\n")
                for region, count in breakdown_by_region.items():
                    f.write(f"  {region}: {count}\n")
    
    saved_files['management_token_calculation'] = calc_filepath
    
    # Save token-free resources if they exist
    token_free_resources = calculation_results.get('management_token_free_resources', [])
    if token_free_resources:
        free_filename = f"{provider}_management_token_free_{timestamp}.{output_format}"
        free_filepath = os.path.join(output_dir, free_filename)
        
        if output_format == 'json':
            with open(free_filepath, 'w') as f:
                json.dump(token_free_resources, f, indent=2, default=str)
        elif output_format == 'csv':
            df = pd.DataFrame(token_free_resources)
            df.to_csv(free_filepath, index=False)
        else:  # txt
            with open(free_filepath, 'w') as f:
                f.write(f"{provider.upper()} Management Token-Free Resources\n")
                f.write("=" * 50 + "\n\n")
                for i, resource in enumerate(token_free_resources, 1):
                    f.write(f"Resource {i}:\n")
                    f.write(f"  ID: {resource.get('resource_id', 'N/A')}\n")
                    f.write(f"  Type: {resource.get('resource_type', 'N/A')}\n")
                    f.write(f"  Region: {resource.get('region', 'N/A')}\n")
                    f.write(f"  Name: {resource.get('name', 'N/A')}\n")
                    f.write("\n")
        
        saved_files['management_token_free'] = free_filepath
    
    return saved_files 