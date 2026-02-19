#!/usr/bin/env python3
"""
AWS Cloud Discovery for Infoblox Universal DDI Resource Counter.
Discovers AWS Native Objects and calculates Management Token requirements.
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from aws_discovery.aws_discovery import AWSDiscovery
from aws_discovery.config import AWSConfig, get_all_enabled_regions
from shared.output_utils import print_discovery_summary

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def check_awscli_version():
    import re
    import subprocess
    import sys

    try:
        result = subprocess.run(["aws", "--version"], capture_output=True, text=True, encoding="utf-8")
        version_match = re.search(r"aws-cli/(\d+)\.(\d+)\.(\d+)", result.stdout + result.stderr)
        if not version_match:
            print("ERROR: Unable to determine AWS CLI version. Please ensure AWS CLI v2 is installed.")
            sys.exit(1)
        major, minor, patch = map(int, version_match.groups())
        if (major, minor, patch) < (2, 0, 0):
            print(
                f"ERROR: AWS CLI version 2.0.0 or higher is required. "
                f"Detected version: {major}.{minor}.{patch}. "
                "Please upgrade your AWS CLI."
            )
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unable to check AWS CLI version: {e}")
        sys.exit(1)


def check_aws_credentials():
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError

    session = boto3.Session()
    credentials = session.get_credentials()
    if not credentials:
        print(
            "ERROR: AWS credentials not found. Please configure credentials, set AWS_PROFILE, or run 'aws sso login'. Exiting."
        )
        sys.exit(1)
    try:
        sts = session.client("sts")
        sts.get_caller_identity()
    except (NoCredentialsError, ClientError) as e:
        print(
            f"ERROR: AWS credentials are invalid or expired: {e}\n"
            "Please check your credentials or run 'aws sso login'. Exiting."
        )
        sys.exit(1)


def main(args=None):
    """Main discovery function."""
    if args is None:
        # If called directly, parse arguments from command line
        parser = argparse.ArgumentParser(description="AWS Cloud Discovery for Management Token Calculation")
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

    print("AWS Cloud Discovery for Management Token Calculation")
    print("=" * 55)
    print(f"Output format: {args.format.upper()}")
    print(f"Parallel workers: {args.workers}")
    print()

    # Check AWS CLI version
    check_awscli_version()
    # Pre-check AWS credentials before any discovery or region fetching
    check_aws_credentials()

    # Get all enabled regions
    print("Fetching enabled regions...")
    all_regions = get_all_enabled_regions()
    print(f"Found {len(all_regions)} enabled regions")
    print()

    # Initialize discovery with all regions
    config = AWSConfig(
        regions=all_regions,
        output_directory="output",
        output_format=args.format,
    )
    discovery = AWSDiscovery(config)
    scanned_accounts = discovery.get_scanned_account_ids()

    try:
        # Discover Native Objects
        print("Starting AWS Discovery...")
        native_objects = discovery.discover_native_objects(max_workers=args.workers)

        # Annotate every resource with account_id and prefix resource_id for uniqueness
        account_id = scanned_accounts[0] if scanned_accounts else "unknown"
        for r in native_objects:
            r["account_id"] = account_id
            r["resource_id"] = f"{account_id}:{r['resource_id']}"

        print(f"Found {len(native_objects)} Native Objects")

        # Count DDI objects and active IPs
        count_results = discovery.count_resources()

        # Persist unknown resources for debugging (JSON)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        from shared.output_utils import save_unknown_resources

        unk = save_unknown_resources(native_objects, config.output_directory, timestamp, "aws")
        if unk:
            print(f"Unknown resources saved to: {unk['unknown_resources']}")

        # Print discovery summary
        print_discovery_summary(
            native_objects,
            count_results,
            "aws",
            {"accounts": scanned_accounts},
        )

        # Always generate Universal DDI licensing calculations
        from shared.licensing_calculator import UniversalDDILicensingCalculator

        print("\n" + "=" * 60)
        print("GENERATING INFOBLOX UNIVERSAL DDI LICENSING CALCULATIONS")
        print("=" * 60)

        calculator = UniversalDDILicensingCalculator()
        licensing_results = calculator.calculate_from_discovery_results(native_objects, provider="aws")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Export CSV for Sales Engineers
        csv_file = os.path.join("output", f"aws_universal_ddi_licensing_{timestamp}.csv")
        calculator.export_csv(csv_file, provider="aws")
        print(f"Licensing CSV exported: {csv_file}")

        # Export text summary
        txt_file = os.path.join("output", f"aws_universal_ddi_licensing_{timestamp}.txt")
        calculator.export_text_summary(txt_file, provider="aws")
        print(f"Licensing summary exported: {txt_file}")

        # Export estimator-only CSV
        estimator_csv = os.path.join("output", f"aws_universal_ddi_estimator_{timestamp}.csv")
        calculator.export_estimator_csv(estimator_csv)
        print(f"Estimator CSV exported: {estimator_csv}")

        # Export auditable proof manifest (scope + hashes)
        proof_file = os.path.join("output", f"aws_universal_ddi_proof_{timestamp}.json")
        calculator.export_proof_manifest(
            proof_file,
            provider="aws",
            scope={"accounts": scanned_accounts},
            regions=all_regions,
            native_objects=native_objects,
        )
        print(f"Proof manifest exported: {proof_file}")

        # Print summary to console
        print("\nUNIVERSAL DDI LICENSING SUMMARY:")
        print(
            f"DDI Objects: {licensing_results['counts']['ddi_objects']:,} "
            f"({licensing_results['token_requirements']['ddi_objects_tokens']} tokens)"
        )
        print(
            f"Active IPs: {licensing_results['counts']['active_ip_addresses']:,} "
            f"({licensing_results['token_requirements']['active_ips_tokens']} tokens)"
        )
        print(
            f"Managed Assets: {licensing_results['counts']['managed_assets']:,} "
            f"({licensing_results['token_requirements']['managed_assets_tokens']} tokens)"
        )
        print(f"TOTAL MANAGEMENT TOKENS REQUIRED: {licensing_results['token_requirements']['total_management_tokens']}")

        # Save results
        if args.full:
            print(f"Saving full resource/object data in {args.format.upper()} format...")
            saved_files = discovery.save_discovery_results(extra_info={"accounts": scanned_accounts})
            print("Results saved to:")
            for file_type, filepath in saved_files.items():
                print(f"  {file_type}: {filepath}")

        print("\nDiscovery completed successfully!")

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
