"""
Shared output utilities for saving discovery results.
"""

import json
import os
import csv
import pandas as pd
from typing import Dict, List, Any
from datetime import datetime


def print_discovery_summary(native_objects: List[Dict], count_results: Dict, provider: str, extra_info: dict = {}):
    """
    Print discovery summary to console.
    
    Args:
        native_objects: List of discovered resources
        count_results: Resource count results
        provider: Cloud provider name (aws, azure, gcp)
        extra_info: Dict with keys like 'accounts', 'subscriptions', 'projects'
    """
    from datetime import datetime
    print(f"\n===== {provider.upper()} Resource Count =====")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Print scanned account/subscription/project info
    if extra_info:
        if provider == "aws" and extra_info.get("accounts"):
            print(f"Scanned AWS Account(s): {', '.join(extra_info['accounts'])}")
        elif provider == "azure" and extra_info.get("subscriptions"):
            print(f"Scanned Azure Subscription(s): {', '.join(extra_info['subscriptions'])}")
        elif provider == "gcp" and extra_info.get("projects"):
            print(f"Scanned GCP Project(s): {', '.join(extra_info['projects'])}")
    
    # DDI Breakdown
    ddi_breakdown = count_results.get("ddi_breakdown", {})
    ddi_total = sum(ddi_breakdown.values())
    print("\n--- DDI Objects Breakdown ---")
    if not ddi_breakdown:
        print("  (none)")
    else:
        for t, count in ddi_breakdown.items():
            print(f"  {t}: {count}")
    print()

    # Active IPs Breakdown
    ip_sources = count_results.get("ip_sources", {})
    print("--- Active IPs Breakdown ---")
    if not ip_sources:
        print("  (none)")
    else:
        for t, count in ip_sources.items():
            print(f"  {t}: {count}")
    print()

    # Ressourcen-Übersicht
    print(f"Discovered {len(native_objects)} resources:")
    type_to_objs = {}
    for obj in native_objects:
        type_to_objs.setdefault(obj["resource_type"], []).append(obj)
    for t, objs in type_to_objs.items():
        examples = ", ".join([str(o["name"]) for o in objs[:2]])
        more = f", ..." if len(objs) > 2 else ""
        print(
            f"  - {len(objs)} {t}(s)"
            + (f" (e.g. {examples}{more})" if examples else "")
        )
    print()

    # Am Ende: Sizing-Zahlen prominent
    print("==============================")
    print(f" DDI Objects Count (for Sizing): {ddi_total}")
    print("==============================")
    print("==============================")
    active_ips = count_results.get('active_ips', 0)
    print(f" Active IPs Count (for Sizing): {active_ips}")
    print("==============================\n")


def save_discovery_results(
    data: List[Dict], output_dir: str, output_format: str, timestamp: str, provider: str, extra_info: dict = {}
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
            output = {"resources": data}
            if extra_info:
                output.update(extra_info)
            json.dump(output, f, indent=2, default=str)
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

            # Print scanned account/subscription/project info
            if extra_info:
                if provider == "aws" and extra_info.get("accounts"):
                    f.write(f"Scanned AWS Account(s): {', '.join(extra_info['accounts'])}\n")
                elif provider == "azure" and extra_info.get("subscriptions"):
                    f.write(f"Scanned Azure Subscription(s): {', '.join(extra_info['subscriptions'])}\n")
                elif provider == "gcp" and extra_info.get("projects"):
                    f.write(f"Scanned GCP Project(s): {', '.join(extra_info['projects'])}\n")
                f.write("\n")

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
    extra_info: dict = {},
) -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)

    saved_files = {}

    count_filename = f"{provider}_resource_count_{timestamp}.{output_format}"
    count_filepath = os.path.join(output_dir, count_filename)

    if output_format == "json":
        with open(count_filepath, "w") as f:
            output = dict(count_results)
            if extra_info:
                output.update(extra_info)
            json.dump(output, f, indent=2, default=str)
    elif output_format == "csv":
        flat_data = {
            "ddi_objects": count_results.get("ddi_objects", 0),
            "active_ips": count_results.get("active_ips", 0),
            "timestamp": count_results.get("timestamp", ""),
        }
        df = pd.DataFrame([flat_data])
        df.to_csv(count_filepath, index=False)
    else:
        with open(count_filepath, "w") as f:
            from datetime import datetime as dt
            f.write(f"{provider.upper()} Resource Count Results\n")
            f.write("=" * 50 + "\n")
            f.write(f"Timestamp: {count_results.get('timestamp', dt.now().strftime('%Y-%m-%d %H:%M:%S'))}\n\n")

            # Print scanned account/subscription/project info
            if extra_info:
                if provider == "aws" and extra_info.get("accounts"):
                    f.write(f"Scanned AWS Account(s): {', '.join(extra_info['accounts'])}\n")
                elif provider == "azure" and extra_info.get("subscriptions"):
                    f.write(f"Scanned Azure Subscription(s): {', '.join(extra_info['subscriptions'])}\n")
                elif provider == "gcp" and extra_info.get("projects"):
                    f.write(f"Scanned GCP Project(s): {', '.join(extra_info['projects'])}\n")
                f.write("\n")

            # DDI Breakdown
            ddi_breakdown = count_results.get("ddi_breakdown", {})
            ddi_total = sum(ddi_breakdown.values())
            f.write("--- DDI Objects Breakdown ---\n")
            if not ddi_breakdown:
                f.write("  (none)\n")
            else:
                for resource_type, count in ddi_breakdown.items():
                    f.write(f"  {resource_type}: {count}\n")
            f.write("\n")

            # Active IPs Breakdown
            ip_sources = count_results.get("ip_sources", {})
            f.write("--- Active IPs Breakdown ---\n")
            if not ip_sources:
                f.write("  (none)\n")
            else:
                for resource_type, count in ip_sources.items():
                    f.write(f"  {resource_type}: {count}\n")
            f.write("\n")

            # Ressourcen-Übersicht (optional, falls gewünscht)
            if "native_objects" in count_results:
                native_objects = count_results["native_objects"]
                f.write(f"Discovered {len(native_objects)} resources:\n")
                type_to_objs = {}
                for obj in native_objects:
                    type_to_objs.setdefault(obj["resource_type"], []).append(obj)
                for t, objs in type_to_objs.items():
                    examples = ", ".join([str(o["name"]) for o in objs[:2]])
                    more = f", ..." if len(objs) > 2 else ""
                    f.write(
                        f"  - {len(objs)} {t}(s)"
                        + (f" (e.g. {examples}{more})" if examples else "")
                        + "\n"
                    )
                f.write("\n")

            # Am Ende: Sizing-Zahlen prominent
            f.write("==============================\n")
            f.write(f" DDI Objects Count (for Sizing): {ddi_total}\n")
            f.write("==============================\n")
            f.write("==============================\n")
            active_ips = count_results.get('active_ips', 0)
            f.write(f" Active IPs Count (for Sizing): {active_ips}\n")
            f.write("==============================\n\n")

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
