#!/usr/bin/env python3
"""
Azure Cloud Discovery for Infoblox Universal DDI Resource Counter.
Discovers Azure Native Objects and calculates Management Token requirements.
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .azure_discovery import AzureDiscovery
from .config import AzureConfig, get_all_azure_regions


def check_azure_cli_login():
    try:
        subprocess.run(
            ["az", "account", "show"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        print(
            "ERROR: Azure CLI is not authenticated. Please run 'az login' or configure your credentials. Exiting."
        )
        sys.exit(1)


def main(args=None):
    """Main discovery function."""
    if args is None:
        # If called directly, parse arguments from command line
        parser = argparse.ArgumentParser(
            description="Azure Cloud Discovery for Management Token Calculation"
        )
        parser.add_argument(
            "--format",
            choices=["json", "csv", "txt"],
            default="txt",
            help="Output format (default: txt)",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=8,
            help="Number of parallel workers (default: 8)",
        )
        parser.add_argument(
            "--full",
            action="store_true",
            help="Save/export full resource/object data (default: only summary and token calculation)",
        )
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
        output_format=args.format,
    )
    discovery = AzureDiscovery(config)
    scanned_subscriptions = discovery.get_scanned_subscription_ids()

    try:
        # Discover Native Objects
        print("Starting Azure Discovery...")
        native_objects = discovery.discover_native_objects(max_workers=args.workers)
        print(f"Found {len(native_objects)} Native Objects")

        # Count DDI objects and active IPs
        count_results = discovery.count_resources()

        # Print discovery summary
        from shared.output_utils import print_discovery_summary

        print_discovery_summary(
            native_objects,
            count_results,
            "azure",
            {"subscriptions": scanned_subscriptions},
        )

        # Save results
        if args.full:
            print(f"Saving full resource/object data in {args.format.upper()} format...")
            saved_files = discovery.save_discovery_results(
                extra_info={"subscriptions": scanned_subscriptions}
            )
            print("Results saved to:")
            for file_type, filepath in saved_files.items():
                print(f"  {file_type}: {filepath}")
        else:
            # Save only the summary (DDI objects and active IPs)
            output_dir = config.output_directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            from shared.output_utils import save_resource_count_results

            summary_files = save_resource_count_results(
                count_results,
                output_dir,
                args.format,
                timestamp,
                "azure",
                extra_info={"subscriptions": scanned_subscriptions},
            )
            print(f"Summary saved to: {summary_files['resource_count']}")

        print(f"\nDiscovery completed successfully!")

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
