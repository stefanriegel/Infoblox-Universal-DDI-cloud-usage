#!/usr/bin/env python3
"""
GCP Cloud Discovery for Infoblox Universal DDI Resource Counter.
Discovers GCP Native Objects and calculates Management Token requirements.
"""

import sys
import argparse
import json
import pandas as pd
import math
from pathlib import Path
from datetime import datetime
import subprocess
import re

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .gcp_discovery import GCPDiscovery
from .config import GCPConfig, get_all_gcp_regions


def check_gcloud_version():
    """Check if gcloud CLI is installed and has the correct version."""
    try:
        result = subprocess.run(["gcloud", "--version"], capture_output=True, text=True)
        version_match = re.search(
            r"Google Cloud SDK (\d+)\.(\d+)\.(\d+)", result.stdout + result.stderr
        )
        if not version_match:
            print(
                "ERROR: Unable to determine gcloud version. Please ensure Google Cloud SDK is installed."
            )
            sys.exit(1)
        major, minor, patch = map(int, version_match.groups())
        if (major, minor, patch) < (300, 0, 0):
            print(
                f"ERROR: Google Cloud SDK version 300.0.0 or higher is required. Detected version: {major}.{minor}.{patch}. Please upgrade your Google Cloud SDK."
            )
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unable to check gcloud version: {e}")
        sys.exit(1)


def check_gcp_credentials():
    """Check if GCP credentials are available."""
    try:
        result = subprocess.run(
            [
                "gcloud",
                "auth",
                "list",
                "--filter=status:ACTIVE",
                "--format=value(account)",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        if not result.stdout.strip():
            print(
                "ERROR: No active GCP credentials found. Please run 'gcloud auth login' or 'gcloud auth application-default login'. Exiting."
            )
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(
            f"ERROR: GCP credentials are invalid or expired: {e}\nPlease check your credentials or run 'gcloud auth login'. Exiting."
        )
        sys.exit(1)
    except FileNotFoundError:
        print("ERROR: gcloud CLI not found. Please install Google Cloud SDK. Exiting.")
        sys.exit(1)


def main(args=None):
    """Main discovery function."""
    if args is None:
        # If called directly, parse arguments from command line
        parser = argparse.ArgumentParser(
            description="GCP Cloud Discovery for Management Token Calculation"
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

    print("GCP Cloud Discovery for Management Token Calculation")
    print("=" * 55)
    print(f"Output format: {args.format.upper()}")
    print(f"Parallel workers: {args.workers}")
    print()

    # Check gcloud version
    check_gcloud_version()
    # Pre-check GCP credentials before any discovery or region fetching
    check_gcp_credentials()

    # Get all available regions
    print("Fetching available regions...")
    all_regions = get_all_gcp_regions()
    print(f"Found {len(all_regions)} available regions")
    print()

    # Initialize discovery with all regions
    config = GCPConfig(
        regions=all_regions, output_directory="output", output_format=args.format
    )
    discovery = GCPDiscovery(config)

    try:
        # Discover Native Objects
        print("Starting GCP Discovery...")
        native_objects = discovery.discover_native_objects(max_workers=args.workers)
        print(f"Found {len(native_objects)} Native Objects")

        # Count DDI objects and active IPs
        count_results = discovery.count_resources()

        # --- Improved Console Output (Scalable) ---
        # 1. Summary of discovered resources by type (with up to 2 example names)
        print("\n===== GCP Discovery Summary =====")
        type_to_objs = {}
        for obj in native_objects:
            type_to_objs.setdefault(obj["resource_type"], []).append(obj)
        print(f"Discovered {len(native_objects)} resources:")
        for t, objs in type_to_objs.items():
            examples = ", ".join([str(o["name"]) for o in objs[:2]])
            more = f", ..." if len(objs) > 2 else ""
            print(
                f"  - {len(objs)} {t}(s)"
                + (f" (e.g. {examples}{more})" if examples else "")
            )

        # 2. DDI Objects Breakdown
        print(f"\nDDI Objects Breakdown:")
        ddi_breakdown = count_results.get("ddi_breakdown", {})
        if not ddi_breakdown:
            print("  - None")
        else:
            for t, count in ddi_breakdown.items():
                print(f"  - {t}: {count}")

        # 3. Active IPs
        print(f"\nActive IPs: {count_results.get('active_ips', 0)}")
        ip_sources = count_results.get("ip_sources", {})
        if ip_sources:
            print("IP Sources:")
            for t, count in ip_sources.items():
                print(f"  - {t}: {count}")

        print("===============================\n")
        # --- End Improved Output ---

        # Save results
        if args.full:
            print(
                f"Saving full resource/object data in {args.format.upper()} format..."
            )
            saved_files = discovery.save_discovery_results()
            print("Results saved to:")
            for file_type, filepath in saved_files.items():
                print(f"  {file_type}: {filepath}")
        else:
            # Save only the summary (DDI objects and active IPs)
            output_dir = config.output_directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            from shared.output_utils import save_resource_count_results
            summary_files = save_resource_count_results(
                count_results, output_dir, args.format, timestamp, "gcp"
            )
            print(f"Summary saved to: {summary_files['resource_count']}")

        print(f"\nDiscovery completed successfully!")

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
