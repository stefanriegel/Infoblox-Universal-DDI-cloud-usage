"""
Shared output utilities for saving discovery results.
"""

import json
import os
import csv
import pandas as pd
from typing import Dict, List, Any
from datetime import datetime


def save_discovery_results(
    data: List[Dict], output_dir: str, output_format: str, timestamp: str, provider: str
) -> Dict[str, str]:
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
    if output_format == "json":
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
    elif output_format == "csv":
        if not data:
            # Create empty DataFrame with expected columns
            df = pd.DataFrame(
                columns=pd.Index(
                    [
                        "resource_id",
                        "resource_type",
                        "region",
                        "name",
                        "state",
                        "requires_management_token",
                        "tags",
                        "details",
                        "discovered_at",
                    ]
                )
            )
        else:
            df = pd.DataFrame(data)
        df.to_csv(filepath, index=False)
    else:  # txt
        with open(filepath, "w") as f:
            if not data:
                f.write(f"No {provider.upper()} Native Objects found.\n")
                return {"native_objects": filepath}

            f.write(f"{provider.upper()} Native Objects Discovery Results\n")
            f.write("=" * 50 + "\n\n")

            for i, resource in enumerate(data, 1):
                f.write(f"Resource {i}:\n")
                f.write(f"  ID: {resource.get('resource_id', 'N/A')}\n")
                f.write(f"  Type: {resource.get('resource_type', 'N/A')}\n")
                f.write(f"  Region: {resource.get('region', 'N/A')}\n")
                f.write(f"  Name: {resource.get('name', 'N/A')}\n")
                f.write(f"  State: {resource.get('state', 'N/A')}\n")
                f.write(
                    f"  Requires Management Token: {resource.get('requires_management_token', 'N/A')}\n"
                )

                # Format tags
                tags = resource.get("tags", {})
                if tags:
                    f.write(f"  Tags: {tags}\n")

                # Format details
                details = resource.get("details", {})
                if details:
                    f.write(f"  Details: {details}\n")

                f.write(f"  Discovered: {resource.get('discovered_at', 'N/A')}\n")
                f.write("\n")

    return {"native_objects": filepath}





def save_resource_count_results(
    count_results: Dict,
    output_dir: str,
    output_format: str,
    timestamp: str,
    provider: str,
) -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)

    saved_files = {}

    count_filename = f"{provider}_resource_count_{timestamp}.{output_format}"
    count_filepath = os.path.join(output_dir, count_filename)

    if output_format == "json":
        with open(count_filepath, "w") as f:
            json.dump(count_results, f, indent=2, default=str)
    elif output_format == "csv":
        flat_data = {
            "total_objects": count_results.get("total_objects", 0),
            "ddi_objects": count_results.get("ddi_objects", 0),
            "active_ips": count_results.get("active_ips", 0),
            "timestamp": count_results.get("timestamp", ""),
        }
        df = pd.DataFrame([flat_data])
        df.to_csv(count_filepath, index=False)
    else:
        with open(count_filepath, "w") as f:
            f.write(f"{provider.upper()} Resource Count Results\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Timestamp: {count_results.get('timestamp', '')}\n\n")
            f.write(f"Total Objects: {count_results.get('total_objects', 0)}\n")
            f.write(f"DDI Objects: {count_results.get('ddi_objects', 0)}\n")
            f.write(f"Active IPs: {count_results.get('active_ips', 0)}\n\n")

            ddi_breakdown = count_results.get("ddi_breakdown", {})
            if ddi_breakdown:
                f.write("DDI Objects Breakdown:\n")
                for resource_type, count in ddi_breakdown.items():
                    f.write(f"  {resource_type}: {count}\n")
                f.write("\n")

            ip_sources = count_results.get("ip_sources", {})
            if ip_sources:
                f.write("IP Sources:\n")
                for resource_type, count in ip_sources.items():
                    f.write(f"  {resource_type}: {count}\n")
                f.write("\n")

            breakdown_by_region = count_results.get("breakdown_by_region", {})
            if breakdown_by_region:
                f.write("Breakdown by Region:\n")
                for region, count in breakdown_by_region.items():
                    f.write(f"  {region}: {count}\n")

    saved_files["resource_count"] = count_filepath

    return saved_files


def format_azure_resource(
    resource: Dict,
    resource_type: str,
    region: str,
    requires_management_token: bool = True,
) -> Dict[str, Any]:
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
    resource_id = (
        getattr(resource, "id", "")
        if hasattr(resource, "id")
        else resource.get("id", "")
    )
    name = (
        getattr(resource, "name", "")
        if hasattr(resource, "name")
        else resource.get("name", "")
    )
    tags = (
        getattr(resource, "tags", {})
        if hasattr(resource, "tags")
        else resource.get("tags", {})
    )

    # Create formatted resource
    formatted = {
        "resource_id": f"{region}:{resource_type}:{name}",
        "resource_type": resource_type,
        "region": region,
        "name": name,
        "state": "active",  # Azure resources are typically active if we can discover them
        "requires_management_token": requires_management_token,
        "tags": tags,
        "details": resource,
        "discovered_at": datetime.now().isoformat(),
    }

    return formatted


def get_resource_tags(tags: List[Dict[str, str]]) -> Dict[str, str]:
    """Convert AWS tags list to dictionary."""
    return {tag["Key"]: tag["Value"] for tag in tags} if tags else {}


def safe_get_nested(obj, attr_path, default: Any = "unknown"):
    """
    Safely get nested attribute or key from an object.

    Args:
        obj: Object to extract from
        attr_path: Dot-separated path to the attribute/key
        default: Default value if not found

    Returns:
        Value at the path or default
    """
    try:
        for attr in attr_path.split("."):
            if hasattr(obj, attr):
                obj = getattr(obj, attr)
            elif isinstance(obj, dict) and attr in obj:
                obj = obj[attr]
            else:
                return default
        return obj
    except (AttributeError, KeyError, TypeError):
        return default
