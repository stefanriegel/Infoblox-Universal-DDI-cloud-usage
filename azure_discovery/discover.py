#!/usr/bin/env python3
"""
Azure Cloud Discovery for Infoblox Universal DDI Resource Counter.
Discovers Azure Native Objects and calculates Management Token requirements.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .azure_discovery import AzureDiscovery
from .config import (
    AzureConfig,
    get_all_azure_regions,
    get_all_subscription_ids,
)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def validate_azure_credentials():
    """Validate that Azure credentials are configured and working."""
    from azure.identity import CredentialUnavailableError
    from .config import get_azure_credential

    try:
        credential = get_azure_credential()
        # Try to get a token to verify credentials work
        credential.get_token("https://management.azure.com/.default")
        return True
    except CredentialUnavailableError as e:
        print(f"ERROR: Azure credentials not available: {e}")
        print("Please configure one of:")
        print(
            "  - Service principal: Set AZURE_CLIENT_ID,"
            " AZURE_CLIENT_SECRET, AZURE_TENANT_ID"
        )
        print("  - Azure CLI: Run 'az login'")
        print(
            "  - Managed identity: Ensure running in Azure with "
            "managed identity enabled"
        )
        return False
    except Exception as e:
        print(f"ERROR: Failed to authenticate with Azure: {e}")
        return False


def main(args=None):
    """Main discovery function."""
    if args is None:
        # If called directly, parse arguments from command line
        parser = argparse.ArgumentParser(
            description="Azure Cloud Discovery for Management Token Calc"
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
            help=(
                "Save/export full resource/object data "
                "(default: only summary and token calculation)"
            ),
        )
        parser.add_argument(
            "--licensing",
            action="store_true",
            help=(
                "Generate Infoblox Universal DDI licensing calculations "
                "for Sales Engineers"
            ),
        )
        parser.add_argument(
            "--include-counts",
            action="store_true",
            help=(
                "Also write legacy resource_count files alongside "
                "licensing outputs"
            ),
        )
        args = parser.parse_args()

    print("Azure Cloud Discovery for Management Token Calculation")
    print("=" * 55)
    print(f"Output format: {args.format.upper()}")
    print(f"Parallel workers: {args.workers}")
    print()

    # Validate credentials before attempting discovery
    if not validate_azure_credentials():
        return 1

    # Get all available regions
    print("Fetching available regions...")
    all_regions = get_all_azure_regions()
    print(f"Found {len(all_regions)} available regions")
    print()

    # Get all subscriptions
    all_subs = get_all_subscription_ids()
    if not all_subs:
        print(
            "No subscriptions found. Check your Azure credentials and permissions."
        )
        return 1
    print(f"Found {len(all_subs)} enabled subscriptions")
    print()

    # Discover across all subscriptions
    all_native_objects = []
    scanned_subs = []
    for sub_id in all_subs:
        print(f"Scanning subscription: {sub_id}")
        config = AzureConfig(
            regions=all_regions,
            output_directory="output",
            output_format=args.format,
            subscription_id=sub_id
        )
        discovery = AzureDiscovery(config)
        native_objects = discovery.discover_native_objects(
            max_workers=args.workers
        )
        all_native_objects.extend(native_objects)
        scanned_subs.append(sub_id)
        print(
            f"Found {len(native_objects)} Native Objects in this subscription"
        )

    print(
        f"\nTotal Native Objects found across all subscriptions: "
        f"{len(all_native_objects)}"
    )

    # Create a dummy discovery for counting and saving
    config = AzureConfig(
        regions=all_regions,
        output_directory="output",
        output_format=args.format,
        subscription_id=all_subs[0] if all_subs else ""
    )
    discovery = AzureDiscovery(config)
    discovery._discovered_resources = all_native_objects  # Set resources

    try:

        # Count DDI objects and active IPs
        count_results = discovery.count_resources()

        # Persist unknown resources for debugging (JSON)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        from shared.output_utils import save_unknown_resources

        unk = save_unknown_resources(
            all_native_objects, config.output_directory, timestamp, "azure"
        )
        if unk:
            print(f"Unknown resources saved to: {unk['unknown_resources']}")

        # Print discovery summary
        from shared.output_utils import print_discovery_summary

        print_discovery_summary(
            all_native_objects,
            count_results,
            "azure",
            {"subscriptions": scanned_subs},
        )

        # Always generate Universal DDI licensing calculations
        from shared.licensing_calculator import UniversalDDILicensingCalculator

        print("\n" + "=" * 60)
        print("GENERATING INFOBLOX UNIVERSAL DDI LICENSING CALCULATIONS")
        print("=" * 60)

        calculator = UniversalDDILicensingCalculator()
        calculator.calculate_from_discovery_results(
            all_native_objects, provider="azure"
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Export CSV for Sales Engineers
        csv_file = f"output/azure_universal_ddi_licensing_{timestamp}.csv"
        calculator.export_csv(csv_file, provider="azure")
        print(f"Licensing CSV exported: {csv_file}")

        # Export text summary
        txt_file = f"output/azure_universal_ddi_licensing_{timestamp}.txt"
        calculator.export_text_summary(txt_file, provider="azure")
        print(f"Licensing summary exported: {txt_file}")

        # Export estimator-only CSV
        estimator_csv = f"output/azure_universal_ddi_estimator_{timestamp}.csv"
        calculator.export_estimator_csv(estimator_csv)
        print(f"Estimator CSV exported: {estimator_csv}")

        # Export auditable proof manifest (scope + hashes)
        proof_file = f"output/azure_universal_ddi_proof_{timestamp}.json"
        calculator.export_proof_manifest(
            proof_file,
            provider="azure",
            scope={"subscriptions": scanned_subs},
            regions=all_regions,
            native_objects=all_native_objects,
        )
        print(f"Proof manifest exported: {proof_file}")

        # Save results
        if args.full:
            print(
                f"Saving full resource/object data in "
                f"{args.format.upper()} format..."
            )
            saved_files = discovery.save_discovery_results(
                extra_info={"subscriptions": scanned_subs}
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
                    "azure",
                    extra_info={"subscriptions": scanned_subs},
                )
                print(f"Summary saved to: {summary_files['resource_count']}")
            else:
                print(
                    "Skipping legacy resource_count output (use --include-counts)"
                )

        print("\nDiscovery completed successfully!")

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
