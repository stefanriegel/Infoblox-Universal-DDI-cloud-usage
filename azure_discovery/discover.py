#!/usr/bin/env python3
"""
Azure Cloud Discovery for Infoblox Universal DDI Management Token Calculator.
Discovers Azure Native Objects and calculates Management Token requirements.
"""

import sys
import argparse
import json
import pandas as pd
import math
from pathlib import Path
from datetime import datetime
import subprocess

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .azure_discovery import AzureDiscovery
from .config import AzureConfig, get_all_azure_regions
from .historical_analysis import AzureActivityAnalyzer


def check_azure_cli_login():
    try:
        subprocess.run([
            "az", "account", "show"
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        print("ERROR: Azure CLI is not authenticated. Please run 'az login' or configure your credentials. Exiting.")
        sys.exit(1)


def main(args=None):
    """Main discovery function."""
    if args is None:
        # If called directly, parse arguments from command line
        parser = argparse.ArgumentParser(description="Azure Cloud Discovery for Management Token Calculation")
        parser.add_argument("--format", choices=["json", "csv", "txt"], default="txt",
                           help="Output format (default: txt)")
        parser.add_argument("--workers", type=int, default=8,
                           help="Number of parallel workers (default: 8)")
        parser.add_argument("--full", action="store_true",
                           help="Save/export full resource/object data (default: only summary and token calculation)")
        args = parser.parse_args()
    
    print("Azure Cloud Discovery for Management Token Calculation")
    print("=" * 55)
    print(f"Output format: {args.format.upper()}")
    print(f"Parallel workers: {args.workers}")
    print()
    
    # Pre-check Azure CLI login before any discovery or region fetching
    check_azure_cli_login()
    
    # Get all available regions
    print("Fetching available regions...")
    all_regions = get_all_azure_regions()
    print(f"Found {len(all_regions)} available regions")
    print()
    
    # Initialize discovery with all regions
    config = AzureConfig(
        regions=all_regions, 
        output_directory="output",
        output_format=args.format
    )
    discovery = AzureDiscovery(config)
    
    try:
        # Discover Native Objects
        print("Starting Azure Discovery...")
        native_objects = discovery.discover_native_objects(max_workers=args.workers)
        print(f"Found {len(native_objects)} Native Objects")
        
        # Calculate Management Token requirements
        calculation = discovery.calculate_management_token_requirements()
        
        # --- Improved Console Output (Scalable) ---
        # 1. Summary of discovered resources by type (with up to 2 example names)
        print("\n===== Azure Discovery Summary =====")
        type_to_objs = {}
        for obj in native_objects:
            type_to_objs.setdefault(obj['resource_type'], []).append(obj)
        print(f"Discovered {len(native_objects)} resources:")
        for t, objs in type_to_objs.items():
            examples = ', '.join([str(o['name']) for o in objs[:2]])
            more = f", ..." if len(objs) > 2 else ""
            print(f"  - {len(objs)} {t}(s)" + (f" (e.g. {examples}{more})" if examples else ""))
        
        # 2. Token-Free (Non-Counted) Resources: count per type, up to 2 example names
        token_free = calculation.get('management_token_free_resources', [])
        type_to_free = {}
        for obj in token_free:
            type_to_free.setdefault(obj['resource_type'], []).append(obj)
        print(f"\nToken-Free (Non-Counted) Resources:")
        if not token_free:
            print("  - None")
        else:
            for t, objs in type_to_free.items():
                examples = ', '.join([str(o['name']) for o in objs[:2]])
                more = f", ..." if len(objs) > 2 else ""
                print(f"  - {len(objs)} {t}(s)" + (f" (e.g. {examples}{more})" if examples else ""))
        
        # 3. Counted (Token-Licensed) Resources: count per type, up to 2 example names
        counted = [obj for obj in native_objects if obj not in token_free]
        type_to_counted = {}
        for obj in counted:
            type_to_counted.setdefault(obj['resource_type'], []).append(obj)
        print(f"\nCounted (Token-Licensed) Resources:")
        if not counted:
            print("  - None")
        else:
            for t, objs in type_to_counted.items():
                examples = ', '.join([str(o['name']) for o in objs[:2]])
                more = f", ..." if len(objs) > 2 else ""
                print(f"  - {len(objs)} {t}(s)" + (f" (e.g. {examples}{more})" if examples else ""))
        
        # 4. Token Calculation Breakdown
        print("\nToken Calculation:")
        ddi_objects = calculation['breakdown_by_type'].get('ddi_objects', 0)
        active_ips = calculation['breakdown_by_type'].get('active_ips', 0)
        assets = calculation['breakdown_by_type'].get('assets', 0)
        print(f"  - DDI Objects: {ddi_objects} → {math.ceil(ddi_objects / 25)} token(s)")
        print(f"  - Active IPs: {active_ips} → {math.ceil(active_ips / 13)} token(s)")
        print(f"  - Assets: {assets} → {math.ceil(assets / 3)} token(s)")
        print(f"  - **Total Management Tokens Required: {calculation['management_token_required']}**")
        print(f"  - **Token Packs (1000 tokens each): {calculation['management_token_packs']}**")
        print(f"  - **Total Tokens in Packs: {calculation['management_tokens_packs_total']}**")
        print("===============================\n")
        # --- End Improved Output ---
        
        # Save results
        if args.full:
            print(f"Saving full resource/object data in {args.format.upper()} format...")
            saved_files = discovery.save_discovery_results()
            print("Results saved to:")
            for file_type, filepath in saved_files.items():
                print(f"  {file_type}: {filepath}")
        else:
            # Save only the summary and token calculation
            output_dir = config.output_directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_file = f"{output_dir}/azure_management_token_calculation_{timestamp}.{args.format}"
            # Save calculation summary only
            if args.format == 'csv':
                df = pd.DataFrame([calculation])
                df.to_csv(summary_file, index=False)
            elif args.format == 'json':
                with open(summary_file, 'w') as f:
                    json.dump(calculation, f, indent=2, default=str)
            else:  # txt
                with open(summary_file, 'w') as f:
                    for k, v in calculation.items():
                        f.write(f"{k}: {v}\n")
            print(f"Summary and token calculation saved to: {summary_file}")
        
        print(f"\nDiscovery completed successfully!")
        
        return 0
        
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    exit(main()) 