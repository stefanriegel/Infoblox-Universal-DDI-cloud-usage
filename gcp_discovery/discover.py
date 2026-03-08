#!/usr/bin/env python3
"""
GCP Cloud Discovery for Infoblox Universal DDI Resource Counter.
Discovers GCP Native Objects and calculates Management Token requirements.
"""

import argparse
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from .config import GCPConfig, get_all_gcp_regions, get_gcp_credential, enumerate_gcp_projects
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
            default=4,
            help="Number of parallel project workers (default: 4)",
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
            help="Scan a single GCP project (bypasses enumeration). " "Overrides GOOGLE_CLOUD_PROJECT env var.",
        )
        parser.add_argument(
            "--org-id",
            default=None,
            help="Scope enumeration to this GCP organization ID. " "Overrides GOOGLE_CLOUD_ORG_ID env var.",
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

    total = len(projects)
    effective_workers = min(args.workers, total)

    print("GCP Cloud Discovery for Management Token Calculation")
    print("=" * 55)
    print(f"Output format: {args.format.upper()}")
    print(f"Project workers: {effective_workers}")
    print()

    # Get all available regions once (shared across all project workers)
    print("Fetching available regions...")
    all_regions = get_all_gcp_regions()
    print(f"Found {len(all_regions)} available regions")
    print()

    # Build shared compute clients ONCE before the worker pool.
    # GCP compute clients are project-agnostic; project is passed per API call.
    from google.cloud import compute_v1

    shared_compute_clients = {
        "instances": compute_v1.InstancesClient(credentials=credentials),
        "zones": compute_v1.ZonesClient(credentials=credentials),
        "networks": compute_v1.NetworksClient(credentials=credentials),
        "subnetworks": compute_v1.SubnetworksClient(credentials=credentials),
        "addresses": compute_v1.AddressesClient(credentials=credentials),
        "global_addresses": compute_v1.GlobalAddressesClient(credentials=credentials),
        "routers": compute_v1.RoutersClient(credentials=credentials),
    }

    # Initialize worker state
    lock = threading.Lock()
    errors = []
    all_native_objects = []
    scanned_projects = []
    completed_count = 0
    scan_start = time.monotonic()

    # --- Worker closure ---
    def discover_project(project_info):
        """Scan one GCP project. Returns (project_id, resources, type_counts)."""
        project_id = project_info.project_id
        config = GCPConfig(
            project_id=project_id,
            regions=all_regions,
            output_directory="output",
            output_format=args.format,
        )
        discovery = GCPDiscovery(config, shared_compute_clients=shared_compute_clients)
        native_objects = discovery.discover_native_objects(max_workers=args.workers)

        # EXEC-04: annotate every resource with project_id
        # EXEC-05: prefix resource_id with project_id for uniqueness
        for r in native_objects:
            r["project_id"] = project_id
            r["resource_id"] = f"{project_id}:{r['resource_id']}"

        # Count resources by type for progress output
        type_counts = {}
        for r in native_objects:
            t = r.get("resource_type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        return project_id, native_objects, type_counts

    # --- Concurrent executor loop ---
    with ThreadPoolExecutor(max_workers=effective_workers) as executor:
        future_to_project = {executor.submit(discover_project, pi): pi for pi in projects}
        for future in as_completed(future_to_project):
            pi = future_to_project[future]
            project_id = pi.project_id
            try:
                result_pid, native_objects, type_counts = future.result()
                with lock:
                    completed_count += 1
                    all_native_objects.extend(native_objects)
                    scanned_projects.append(result_pid)
                    # EXEC-03: [N/total] project-id — resource breakdown
                    breakdown_parts = []
                    # Ordered resource types for consistent output
                    for rtype in (
                        "compute-instance",
                        "vpc-network",
                        "subnet",
                        "reserved-ip",
                        "cloud-nat",
                        "gke-cluster",
                        "dns-zone",
                        "dns-record",
                    ):
                        if rtype in type_counts:
                            breakdown_parts.append(f"{type_counts[rtype]} {rtype}")
                    # Append any remaining types not in the ordered list
                    for rtype, count in sorted(type_counts.items()):
                        if rtype not in (
                            "compute-instance",
                            "vpc-network",
                            "subnet",
                            "reserved-ip",
                            "cloud-nat",
                            "gke-cluster",
                            "dns-zone",
                            "dns-record",
                        ):
                            breakdown_parts.append(f"{count} {rtype}")
                    suffix = " -- " + ", ".join(breakdown_parts) if breakdown_parts else ""
                    print(f"[{completed_count}/{total}] {result_pid}{suffix}")
            except Exception as e:
                with lock:
                    completed_count += 1
                    errors.append({"project_id": project_id, "error": str(e)})
                    print(f"[{completed_count}/{total}] {project_id}: FAILED -- {e}")

    elapsed = time.monotonic() - scan_start

    # Aggregated summary
    print(f"\nTotal resources found across all projects: {len(all_native_objects)}")

    # Failed project summary
    if errors:
        print(f"\nFailed projects ({len(errors)}):")
        for err in errors:
            print(f"  {err['project_id']}: {err['error']}")

    print(f"\nScan complete: {len(scanned_projects)}/{total} projects succeeded ({elapsed:.1f}s total)")

    # --- Post-scan processing ---
    try:
        # Count DDI objects and active IPs using aggregated resource list
        from dataclasses import asdict

        from shared.resource_counter import ResourceCounter

        resource_counter = ResourceCounter("gcp")
        count_results = asdict(resource_counter.count_resources(all_native_objects))

        # Persist unknown resources for debugging (JSON)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        from shared.output_utils import save_unknown_resources

        unk = save_unknown_resources(all_native_objects, "output", timestamp, "gcp")
        if unk:
            print(f"Unknown resources saved to: {unk['unknown_resources']}")

        # Print discovery summary
        from shared.output_utils import print_discovery_summary

        print_discovery_summary(
            all_native_objects,
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
        calculator.calculate_from_discovery_results(all_native_objects, provider="gcp")

        # Export CSV for Sales Engineers
        csv_file = os.path.join("output", f"gcp_universal_ddi_licensing_{timestamp}.csv")
        calculator.export_csv(csv_file, provider="gcp")
        print(f"Licensing CSV exported: {csv_file}")

        # Export text summary
        txt_file = os.path.join("output", f"gcp_universal_ddi_licensing_{timestamp}.txt")
        calculator.export_text_summary(txt_file, provider="gcp")
        print(f"Licensing summary exported: {txt_file}")

        # Export estimator-only CSV
        estimator_csv = os.path.join("output", f"gcp_universal_ddi_estimator_{timestamp}.csv")
        calculator.export_estimator_csv(estimator_csv)
        print(f"Estimator CSV exported: {estimator_csv}")

        # Export auditable proof manifest (scope + hashes)
        proof_file = os.path.join("output", f"gcp_universal_ddi_proof_{timestamp}.json")
        calculator.export_proof_manifest(
            proof_file,
            provider="gcp",
            scope={"projects": scanned_projects},
            regions=all_regions,
            native_objects=all_native_objects,
        )
        print(f"Proof manifest exported: {proof_file}")

        # Save results
        if args.full:
            from shared.output_utils import save_discovery_results

            print(f"Saving full resource/object data in {args.format.upper()} format...")
            saved_files = save_discovery_results(
                all_native_objects,
                "output",
                args.format,
                timestamp,
                "gcp",
                extra_info={"projects": scanned_projects},
            )
            print("Results saved to:")
            for file_type, filepath in saved_files.items():
                print(f"  {file_type}: {filepath}")

        print("\nDiscovery completed successfully!")

        return 1 if errors else 0

    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
