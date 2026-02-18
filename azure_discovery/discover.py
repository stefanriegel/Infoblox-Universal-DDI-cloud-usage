#!/usr/bin/env python3
"""
Azure Cloud Discovery for Infoblox Universal DDI Resource Counter.
Discovers Azure Native Objects and calculates Management Token requirements.
"""

import argparse
import json
import os
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.dns import DnsManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.privatedns import PrivateDnsManagementClient
from azure.mgmt.resource import ResourceManagementClient

from .azure_discovery import AzureDiscovery, make_retry_policy
from .config import (
    AzureConfig,
    get_all_azure_regions,
    get_all_subscription_ids,
    get_azure_credential,
)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def validate_azure_credentials():
    """Validate that Azure credentials are configured and working.
    Uses ClientSecretCredential or InteractiveBrowserCredential/DeviceCodeCredential."""
    from azure.identity import CredentialUnavailableError
    from azure.core.exceptions import ClientAuthenticationError
    from .config import get_azure_credential

    try:
        credential = get_azure_credential()
        # Try to get a token to verify credentials work (defense-in-depth;
        # get_azure_credential already warms the credential internally)
        credential.get_token("https://management.azure.com/.default")
        return True
    except CredentialUnavailableError as e:
        print(f"ERROR: Azure credentials not available: {e}")
        return False
    except ClientAuthenticationError as e:
        print(f"ERROR: Azure authentication failed: {e}")
        print("Check your credentials and try again.")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error during credential validation: {e}")
        raise


def save_checkpoint(checkpoint_file, args, all_subs, scanned_subs, all_native_objects, errors=None):
    """Save current progress to checkpoint file."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "args": vars(args),
        "total_subs": len(all_subs),
        "completed_subs": scanned_subs,
        "all_native_objects": all_native_objects,
        "errors": errors or [],
    }
    try:
        os.makedirs(os.path.dirname(checkpoint_file), exist_ok=True)
        temp_file = checkpoint_file + ".tmp"
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2)
        os.rename(temp_file, checkpoint_file)
        print(f"Checkpoint saved: {len(scanned_subs)}/{len(all_subs)} subscriptions completed.")
    except Exception as e:
        print(f"Warning: Failed to save checkpoint: {e}")


def load_checkpoint(checkpoint_file, ttl_hours=48):
    """Load checkpoint data if valid and recent."""
    if not os.path.exists(checkpoint_file):
        return None
    try:
        with open(checkpoint_file, "r") as f:
            data = json.load(f)
        timestamp = datetime.fromisoformat(data["timestamp"])
        if ttl_hours > 0 and datetime.now() - timestamp > timedelta(hours=ttl_hours):
            print(f"Checkpoint expired ({ttl_hours}h TTL). Starting fresh scan.")
            return None
        return data
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"Warning: Checkpoint file is corrupted or incompatible ({e}). Starting fresh scan.")
        return None
    except Exception as e:
        print(f"Warning: Failed to load checkpoint ({e}). Starting fresh scan.")
        return None


def prompt_resume(checkpoint_data):
    """Prompt user to resume from checkpoint."""
    completed = len(checkpoint_data["completed_subs"])
    total = checkpoint_data["total_subs"]
    timestamp = checkpoint_data["timestamp"]
    print(f"Found checkpoint from {timestamp}: {completed}/{total} subscriptions completed.")
    response = input("Resume from checkpoint? [y/N]: ").strip().lower()
    return response in ("y", "yes")


def signal_handler(signum, frame):
    """Handle signals for graceful shutdown."""
    print("\nReceived signal, saving checkpoint and exiting...")
    # Note: This is a simple handler; in real usage, we'd pass args and state, but for now, just exit
    sys.exit(1)

def main(args=None):
    """Main discovery function."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args is None:
        # If called directly, parse arguments from command line
        parser = argparse.ArgumentParser(description="Azure Cloud Discovery for Management Token Calc")
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
            "--subscription-workers",
            type=int,
            default=4,
            help="Number of parallel subscription workers (default: 4)",
        )
        parser.add_argument(
            "--no-checkpoint",
            action="store_true",
            help="Disable checkpointing and resume (default: enabled)",
        )
        parser.add_argument(
            "--resume",
            action="store_true",
            help="Automatically resume from checkpoint without prompting",
        )
        parser.add_argument(
            "--checkpoint-file",
            default="output/azure_discovery_checkpoint.json",
            help="Path to checkpoint file (default: output/azure_discovery_checkpoint.json)",
        )
        parser.add_argument(
            "--retry-attempts",
            type=int,
            default=3,
            help="Number of retry attempts for failed API calls (default: 3)",
        )
        parser.add_argument(
            "--full",
            action="store_true",
            help=("Save/export full resource/object data " "(default: only summary and token calculation)"),
        )
        parser.add_argument(
            "--licensing",
            action="store_true",
            help=("Generate Infoblox Universal DDI licensing calculations " "for Sales Engineers"),
        )
        parser.add_argument(
            "--checkpoint-ttl-hours",
            type=int,
            default=48,
            help="Checkpoint expiry in hours (default: 48). Use 0 to never expire.",
        )
        parser.add_argument(
            "--warn-sub-threshold",
            type=int,
            default=200,
            help="Print a warning when subscription count exceeds this value and --subscription-workers >2 (default: 200).",
        )

        args = parser.parse_args()

    print("Azure Cloud Discovery for Management Token Calculation")
    print("=" * 55)
    print(f"Output format: {args.format.upper()}")
    print(f"Parallel workers: {args.workers}")
    print(f"Subscription workers: {args.subscription_workers}")
    if not args.no_checkpoint:
        print(f"Checkpointing enabled: {args.checkpoint_file} (after each subscription)")
    print()

    # Validate credentials before attempting discovery
    if not validate_azure_credentials():
        return 1

    # Get all subscriptions
    all_subs = get_all_subscription_ids()
    if not all_subs:
        print("No subscriptions found. Check your Azure credentials and permissions.")
        return 1
    print(f"Found {len(all_subs)} enabled subscriptions")
    all_subs_total = list(all_subs)  # Capture full list before checkpoint filtering

    # Warn for large-tenant + high-worker combination (OBSV-02)
    if len(all_subs_total) > args.warn_sub_threshold and args.subscription_workers > 2:
        print(
            f"[Warning] {len(all_subs_total)} subscriptions detected with "
            f"--subscription-workers {args.subscription_workers}. "
            f"This combination may trigger ARM rate limiting (429 throttling). "
            f"Consider reducing to --subscription-workers 2 for large tenants."
        )

    # Check for checkpoint and resume
    checkpoint_data = None
    if not args.no_checkpoint:
        checkpoint_data = load_checkpoint(args.checkpoint_file, args.checkpoint_ttl_hours)
        if checkpoint_data:
            if args.resume or prompt_resume(checkpoint_data):
                print("Resuming from checkpoint...")
                # Restore state
                scanned_subs = checkpoint_data["completed_subs"]
                all_native_objects = checkpoint_data["all_native_objects"]
                # Verbose resume: print count and list of skipped subscription IDs
                print(f"Skipping {len(scanned_subs)} previously completed subscriptions, scanning {len(all_subs) - len(scanned_subs)} remaining:")
                for sub_id in scanned_subs:
                    print(f"  - {sub_id}")
                # Filter all_subs to exclude completed ones
                all_subs = [sub for sub in all_subs if sub not in scanned_subs]
            else:
                print("Starting fresh...")
                checkpoint_data = None
                scanned_subs = []
                all_native_objects = []
        else:
            scanned_subs = []
            all_native_objects = []
    else:
        scanned_subs = []
        all_native_objects = []

    print()

    # Get all available regions
    print("Fetching available regions...")
    all_regions = get_all_azure_regions()
    print(f"Found {len(all_regions)} available regions")

    print()

    # Discover across all subscriptions in parallel

    lock = threading.Lock()
    errors = checkpoint_data.get("errors", []) if checkpoint_data else []

    # Get the credential singleton once before spawning workers.
    # InteractiveBrowserCredential must not be called from worker threads.
    credential = get_azure_credential()
    print_lock = lock  # reuse existing threading.Lock for thread-safe output

    def discover_subscription(sub_id):
        retry_policy = make_retry_policy(sub_id, print_lock)

        with ComputeManagementClient(credential, sub_id, retry_policy=retry_policy) as compute_client, \
             NetworkManagementClient(credential, sub_id, retry_policy=retry_policy) as network_client, \
             ResourceManagementClient(credential, sub_id, retry_policy=retry_policy) as resource_client, \
             DnsManagementClient(credential, sub_id, retry_policy=retry_policy) as dns_client, \
             PrivateDnsManagementClient(credential, sub_id, retry_policy=retry_policy) as privatedns_client:

            config = AzureConfig(
                regions=all_regions,
                output_directory="output",
                output_format=args.format,
                subscription_id=sub_id,
            )
            discovery = AzureDiscovery(
                config,
                compute_client=compute_client,
                network_client=network_client,
                resource_client=resource_client,
                dns_client=dns_client,
                privatedns_client=privatedns_client,
            )
            native_objects = discovery.discover_native_objects(max_workers=args.workers)
            return sub_id, native_objects
        # All five clients are closed here -- sockets released

    completed_count = len(scanned_subs)  # account for resumed subs
    total = len(all_subs_total)

    with ThreadPoolExecutor(max_workers=args.subscription_workers) as executor:
        future_to_sub = {executor.submit(discover_subscription, sub_id): sub_id for sub_id in all_subs}
        for future in as_completed(future_to_sub):
            sub_id = future_to_sub[future]
            try:
                result_sub_id, native_objects = future.result()
                with lock:
                    completed_count += 1
                    all_native_objects.extend(native_objects)
                    scanned_subs.append(result_sub_id)
                    print(f"[{completed_count}/{total}] {result_sub_id}")
                    if not args.no_checkpoint:
                        save_checkpoint(args.checkpoint_file, args, all_subs_total, scanned_subs, all_native_objects, errors)
            except Exception as e:
                with lock:
                    completed_count += 1
                    errors.append({"sub_id": sub_id, "error": str(e)})
                    print(f"[{completed_count}/{total}] {sub_id}: FAILED -- {e}")

    succeeded = len(scanned_subs)
    failed = len(errors)
    print(f"\nScan complete: {succeeded}/{total} subscriptions succeeded")

    if errors:
        print(f"\nFAILED ({len(errors)}):")
        for err in errors:
            if isinstance(err, dict):
                print(f"  - {err['sub_id']}: {err['error']}")
            else:
                print(f"  - {err}")  # backward compat with checkpoint string format

    print(f"\nTotal Native Objects found across all subscriptions: " f"{len(all_native_objects)}")

    # Log failed subscriptions to a separate file
    if errors:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        error_file = f"output/azure_failed_subscriptions_{timestamp}.txt"
        try:
            os.makedirs("output", exist_ok=True)
            with open(error_file, 'w') as f:
                for err in errors:
                    if isinstance(err, dict):
                        f.write(f"{err['sub_id']}: {err['error']}\n")
                    else:
                        f.write(err + '\n')  # backward compat with checkpoint string format
            print(f"Failed subscriptions logged to: {error_file}")
        except Exception as e:
            print(f"Warning: Failed to write error log: {e}")

    # Create a dummy discovery for counting and saving.
    # AzureDiscovery is constructed without pre-built clients here; it internally creates
    # management clients but never calls any Azure API (count_resources() and save_discovery_results()
    # only process _discovered_resources which is set directly below). These internal clients
    # will be garbage-collected normally after this function returns.
    config = AzureConfig(
        regions=all_regions,
        output_directory="output",
        output_format=args.format,
        subscription_id=all_subs_total[0] if all_subs_total else "",
    )
    discovery = AzureDiscovery(config)
    discovery._discovered_resources = all_native_objects  # Set resources

    try:

        # Count DDI objects and active IPs
        count_results = discovery.count_resources()

        # Persist unknown resources for debugging (JSON)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        from shared.output_utils import save_unknown_resources

        unk = save_unknown_resources(all_native_objects, config.output_directory, timestamp, "azure")
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
        calculator.calculate_from_discovery_results(all_native_objects, provider="azure")

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
            print(f"Saving full resource/object data in " f"{args.format.upper()} format...")
            saved_files = discovery.save_discovery_results(extra_info={"subscriptions": scanned_subs})
            print("Results saved to:")
            for file_type, filepath in saved_files.items():
                print(f"  {file_type}: {filepath}")


        print("\nDiscovery completed successfully!")

        # Remove checkpoint on success
        if not args.no_checkpoint and os.path.exists(args.checkpoint_file):
            try:
                os.remove(args.checkpoint_file)
                print(f"Checkpoint file removed: {args.checkpoint_file}")
            except Exception as e:
                print(f"Warning: Failed to remove checkpoint: {e}")

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
