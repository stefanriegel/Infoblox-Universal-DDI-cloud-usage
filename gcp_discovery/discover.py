#!/usr/bin/env python3
"""
GCP Cloud Discovery for Infoblox Universal DDI Resource Counter.
Discovers GCP Native Objects and calculates Management Token requirements.
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .config import GCPConfig, get_all_gcp_regions
from .gcp_discovery import GCPDiscovery

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def check_gcloud_version():
    """Check if gcloud CLI is installed and has the correct version."""
    try:
        result = subprocess.run(["gcloud", "--version"], capture_output=True, text=True)
        version_match = re.search(
            r"Google Cloud SDK (\d+)\.(\d+)\.(\d+)",
            result.stdout + result.stderr,
        )
        if not version_match:
            print(
                "ERROR: Unable to determine gcloud version. Please ensure Google Cloud SDK is installed."
            )
            sys.exit(1)
        major, minor, patch = map(int, version_match.groups())
        if (major, minor, patch) < (300, 0, 0):
            print(
                f"ERROR: Google Cloud SDK version 300.0.0 or higher is required. "
                f"Detected version: {major}.{minor}.{patch}. "
                "Please upgrade your Google Cloud SDK."
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
                "ERROR: No active GCP credentials found. Please run 'gcloud auth login' "
                "or 'gcloud auth application-default login'. Exiting."
            )
            sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(
            f"ERROR: GCP credentials are invalid or expired: {e}\n"
            "Please check your credentials or run 'gcloud auth login'. Exiting."
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
        parser.add_argument(
            "--licensing",
            action="store_true",
            help="Generate Infoblox Universal DDI licensing calculations for Sales Engineers",
        )
        parser.add_argument(
            "--include-counts",
            action="store_true",
            help="Also write legacy resource_count files alongside licensing outputs",
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
        regions=all_regions,
        output_directory="output",
        output_format=args.format,
    )
    discovery = GCPDiscovery(config)
    scanned_projects = discovery.get_scanned_project_ids()

    try:
        # Discover Native Objects
        print("Starting GCP Discovery...")
        native_objects = discovery.discover_native_objects(max_workers=args.workers)
        print(f"Found {len(native_objects)} Native Objects")

        # Count DDI objects and active IPs
        count_results = discovery.count_resources()

        # Persist unknown resources for debugging (JSON)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        from shared.output_utils import save_unknown_resources

        unk = save_unknown_resources(
            native_objects, config.output_directory, timestamp, "gcp"
        )
        if unk:
            print(f"Unknown resources saved to: {unk['unknown_resources']}")

        # Print discovery summary
        from shared.output_utils import print_discovery_summary

        print_discovery_summary(
            native_objects,
            count_results,
            "gcp",
            {"projects": scanned_projects},
        )

        # Always generate Universal DDI licensing calculations
        from shared.licensing_calculator import UniversalDDILicensingCalculator

        print("\n" + "=" * 60)
        print("GENERATING INFOBLOX UNIVERSAL DDI LICENSING CALCULATIONS")
        print("=" * 60)

        calculator = UniversalDDILicensingCalculator()
        calculator.calculate_from_discovery_results(
            native_objects, provider="gcp"
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Export CSV for Sales Engineers
        csv_file = f"output/gcp_universal_ddi_licensing_{timestamp}.csv"
        calculator.export_csv(csv_file, provider="gcp")
        print(f"Licensing CSV exported: {csv_file}")

        # Export text summary
        txt_file = f"output/gcp_universal_ddi_licensing_{timestamp}.txt"
        calculator.export_text_summary(txt_file, provider="gcp")
        print(f"Licensing summary exported: {txt_file}")

        # Export estimator-only CSV
        estimator_csv = f"output/gcp_universal_ddi_estimator_{timestamp}.csv"
        calculator.export_estimator_csv(estimator_csv)
        print(f"Estimator CSV exported: {estimator_csv}")

        # Export auditable proof manifest (scope + hashes)
        proof_file = f"output/gcp_universal_ddi_proof_{timestamp}.json"
        calculator.export_proof_manifest(
            proof_file,
            provider="gcp",
            scope={"projects": scanned_projects},
            regions=all_regions,
            native_objects=native_objects,
        )
        print(f"Proof manifest exported: {proof_file}")

        # Save results
        if args.full:
            print(
                f"Saving full resource/object data in {args.format.upper()} format..."
            )
            saved_files = discovery.save_discovery_results(
                extra_info={"projects": scanned_projects}
            )
            print("Results saved to:")
            for file_type, filepath in saved_files.items():
                print(f"  {file_type}: {filepath}")
        else:
            # Save only legacy count file if requested
            if args.include_counts:
                output_dir = config.output_directory
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                from shared.output_utils import save_resource_count_results

                summary_files = save_resource_count_results(
                    count_results,
                    output_dir,
                    args.format,
                    timestamp,
                    "gcp",
                    extra_info={"projects": scanned_projects},
                )
                print(f"Summary saved to: {summary_files['resource_count']}")
            else:
                print(
                    "Skipping legacy resource_count output (use --include-counts to enable)"
                )

        print("\nDiscovery completed successfully!")

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
