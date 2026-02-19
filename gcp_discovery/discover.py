#!/usr/bin/env python3
"""
GCP Cloud Discovery for Infoblox Universal DDI Resource Counter.
Discovers GCP Native Objects and calculates Management Token requirements.
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from .config import GCPConfig, get_all_gcp_regions, get_gcp_credential, enumerate_gcp_projects, ProjectInfo
from .gcp_discovery import GCPDiscovery

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def main(args=None):
    """Main discovery function."""
    if args is None:
        # If called directly, parse arguments from command line
        parser = argparse.ArgumentParser(description="GCP Cloud Discovery for Management Token Calculation")
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
            "--project",
            default=None,
            help="Scan a single GCP project (bypasses enumeration). "
                 "Overrides GOOGLE_CLOUD_PROJECT env var.",
        )
        parser.add_argument(
            "--org-id",
            default=None,
            help="Scope enumeration to this GCP organization ID. "
                 "Overrides GOOGLE_CLOUD_ORG_ID env var.",
        )
        parser.add_argument(
            "--include-projects",
            nargs="+",
            metavar="PATTERN",
            default=None,
            help="Only scan projects matching these glob patterns (e.g. 'prod-*').",
        )
        parser.add_argument(
            "--exclude-projects",
            nargs="+",
            metavar="PATTERN",
            default=None,
            help="Skip projects matching these glob patterns (e.g. 'test-*').",
        )

        args = parser.parse_args()

    # Credential validation first (fail-fast before banner): CRED-02, CRED-03
    # Warms the singleton on the main thread before any workers are spawned.
    credentials, project = get_gcp_credential()

    # Enumerate projects (ENUM-01 through ENUM-06)
    # Resolves org_id from flag or env var
    org_id = getattr(args, "org_id", None) or os.getenv("GOOGLE_CLOUD_ORG_ID")
    projects = enumerate_gcp_projects(
        credentials=credentials,
        adc_project=project,
        project=getattr(args, "project", None),
        org_id=org_id,
        include_patterns=getattr(args, "include_projects", None),
        exclude_patterns=getattr(args, "exclude_projects", None),
    )

    print("GCP Cloud Discovery for Management Token Calculation")
    print("=" * 55)
    print(f"Output format: {args.format.upper()}")
    print(f"Parallel workers: {args.workers}")
    print()

    # Phase 5: use first project for single-project discovery (Phase 6 adds multi-project)
    # The project list is curated with API availability; use first project's ID
    active_project = projects[0].project_id

    # Get all available regions
    print("Fetching available regions...")
    all_regions = get_all_gcp_regions()
    print(f"Found {len(all_regions)} available regions")
    print()

    # Initialize discovery with first project
    config = GCPConfig(
        project_id=active_project,
        regions=all_regions,
        output_directory="output",
        output_format=args.format,
    )
    discovery = GCPDiscovery(config)
    scanned_projects = [p.project_id for p in projects]

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

        unk = save_unknown_resources(native_objects, config.output_directory, timestamp, "gcp")
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
        calculator.calculate_from_discovery_results(native_objects, provider="gcp")

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
            print(f"Saving full resource/object data in {args.format.upper()} format...")
            saved_files = discovery.save_discovery_results(extra_info={"projects": scanned_projects})
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
