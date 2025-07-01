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