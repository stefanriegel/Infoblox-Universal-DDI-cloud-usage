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
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

from tqdm import tqdm

from .azure_discovery import AzureDiscovery
from .config import (
    AzureConfig,
    get_all_azure_regions,
    get_all_subscription_ids,
)


def validate_azure_credentials():
    """Validate that Azure credentials are configured and working.

    On failure, prints actionable diagnostics based on the Azure SDK
    troubleshooting guide:
    https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/identity/azure-identity/TROUBLESHOOTING.md
    """
    from azure.identity import CredentialUnavailableError
    from .config import get_azure_credential
    import logging as _logging

    try:
        credential = get_azure_credential()
        # Try to get a token to verify credentials work
        credential.get_token("https://management.azure.com/.default")
        return True
    except CredentialUnavailableError as e:
        print(f"ERROR: Azure credentials not available: {e}")
        print("Please configure one of:")
        print("  - Service principal: Set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID")
        print("  - Azure CLI: Run 'az login'")
        print("  - Managed identity: Ensure running in Azure with managed identity enabled")
        print("")
        print("Multi-tenant hint: If you used 'az login --tenant <id>',")
        print("  also set AZURE_TENANT_ID=<id> so credentials target the correct tenant.")
        print("")
        print("For detailed diagnostics, set env AZURE_IDENTITY_DEBUG=1 before running.")
        return False
    except Exception as e:
        print(f"ERROR: Failed to authenticate with Azure: {e}")
        print("")
        print("Troubleshooting tips:")
        print("  - Run: python main.py azure --check-auth")
        print("  - Set AZURE_IDENTITY_DEBUG=1 for verbose credential chain logging")
        print("  - See: https://github.com/Azure/azure-sdk-for-python/blob/main/")
        print("    sdk/identity/azure-identity/TROUBLESHOOTING.md")
        return False


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
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        # Use os.replace for cross-platform atomic replace (destination may already exist on Windows)
        os.replace(temp_file, checkpoint_file)
        print(f"Checkpoint saved: {len(scanned_subs)}/{len(all_subs)} subscriptions completed.")
    except Exception as e:
        print(f"Warning: Failed to save checkpoint: {e}")


def load_checkpoint(checkpoint_file):
    """Load checkpoint data if valid and recent."""
    if not os.path.exists(checkpoint_file):
        return None
    try:
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        timestamp = datetime.fromisoformat(data["timestamp"])
        if datetime.now() - timestamp > timedelta(hours=48):
            print("Checkpoint is older than 48 hours, starting fresh.")
            return None
        return data
    except Exception as e:
        print(f"Warning: Failed to load checkpoint: {e}")
        return None


def prompt_resume(checkpoint_data):
    """Prompt user to resume from checkpoint."""
    completed = len(checkpoint_data["completed_subs"])
    total = checkpoint_data["total_subs"]
    timestamp = checkpoint_data["timestamp"]
    print(f"Found checkpoint from {timestamp}: {completed}/{total} subscriptions completed.")
    response = input("Resume from checkpoint? [y/N]: ").strip().lower()
    return response in ("y", "yes")


# Module-level state for signal handler to access
_checkpoint_state = {
    "enabled": False,
    "file": None,
    "args": None,
    "all_subs": [],
    "scanned_subs": [],
    "all_native_objects": [],
    "errors": [],
}


def signal_handler(signum, frame):
    """Handle signals for graceful shutdown — saves checkpoint before exit."""
    print("\nReceived signal, saving checkpoint and exiting...")
    st = _checkpoint_state
    if st["enabled"] and st["file"] and st["args"]:
        try:
            save_checkpoint(
                st["file"], st["args"], st["all_subs"],
                st["scanned_subs"], st["all_native_objects"], st["errors"],
            )
        except Exception as e:
            print(f"Warning: Failed to save checkpoint on signal: {e}")
    sys.exit(1)


def main(args=None):
    """Main discovery function."""
    signal.signal(signal.SIGINT, signal_handler)
    try:
        # SIGTERM is not supported on Windows; ignore if unavailable
        sigterm = getattr(signal, "SIGTERM")
        signal.signal(sigterm, signal_handler)
    except (AttributeError, ValueError):
        pass

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
            "--checkpoint-interval",
            type=int,
            default=50,
            help="Save checkpoint every N subscriptions (default: 50)",
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

        args = parser.parse_args()

    print("Azure Cloud Discovery for Management Token Calculation")
    print("=" * 55)
    print(f"Output format: {args.format.upper()}")
    print(f"Parallel workers: {args.workers}")
    print(f"Subscription workers: {args.subscription_workers}")
    if not args.no_checkpoint:
        print(f"Checkpointing enabled: {args.checkpoint_file} (every {args.checkpoint_interval} subs or 15 mins)")
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

    # Check for checkpoint and resume
    checkpoint_data = None
    if not args.no_checkpoint:
        checkpoint_data = load_checkpoint(args.checkpoint_file)
        if checkpoint_data:
            if args.resume or prompt_resume(checkpoint_data):
                print("Resuming from checkpoint...")
                # Restore state
                scanned_subs = checkpoint_data["completed_subs"]
                all_native_objects = checkpoint_data["all_native_objects"]
                # Filter all_subs to exclude completed ones
                all_subs = [sub for sub in all_subs if sub not in scanned_subs]
                print(f"Skipped {len(scanned_subs)} completed subscriptions.")
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

    # Keep a stable copy of all_subs for checkpoint (avoid re-querying API)
    all_subs_snapshot = list(all_subs)  # includes already-completed from checkpoint

    lock = threading.Lock()
    last_checkpoint_time = time.time()
    errors = checkpoint_data.get("errors", []) if checkpoint_data else []

    # Populate module-level state so signal handler can save a checkpoint
    if not args.no_checkpoint:
        _checkpoint_state.update({
            "enabled": True,
            "file": args.checkpoint_file,
            "args": args,
            "all_subs": all_subs_snapshot,
            "scanned_subs": scanned_subs,
            "all_native_objects": all_native_objects,
            "errors": errors,
        })

    max_retries = getattr(args, "retry_attempts", 3)

    def discover_subscription(sub_id):
        """Discover a single subscription with retry + exponential backoff."""
        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                config = AzureConfig(
                    regions=all_regions, output_directory="output",
                    output_format=args.format, subscription_id=sub_id,
                )
                discovery = AzureDiscovery(config, retry_attempts=max_retries)
                native_objects = discovery.discover_native_objects(max_workers=args.workers)
                return sub_id, native_objects
            except Exception as e:
                last_exc = e
                if attempt < max_retries:
                    wait = 2 ** (attempt - 1)  # 1s, 2s, 4s …
                    print(f"Retry {attempt}/{max_retries} for subscription {sub_id}: {e} (waiting {wait}s)")
                    time.sleep(wait)
        raise last_exc  # type: ignore[misc]

    def should_save_checkpoint():
        return (len(scanned_subs) % args.checkpoint_interval == 0) or (time.time() - last_checkpoint_time > 900)  # 15 mins

    with ThreadPoolExecutor(max_workers=args.subscription_workers) as executor:
        future_to_sub = {executor.submit(discover_subscription, sub_id): sub_id for sub_id in all_subs}

        with tqdm(total=len(all_subs), desc="Subscriptions") as pbar:
            for future in as_completed(future_to_sub):
                sub_id = future_to_sub[future]

                try:
                    result_sub_id, native_objects = future.result()
                    with lock:
                        all_native_objects.extend(native_objects)
                        scanned_subs.append(result_sub_id)
                        if not args.no_checkpoint and should_save_checkpoint():
                            save_checkpoint(args.checkpoint_file, args, all_subs_snapshot, scanned_subs, all_native_objects, errors)
                            last_checkpoint_time = time.time()
                except Exception as e:
                    print(f"Error discovering subscription {sub_id}: {type(e).__name__}: {e}")
                    with lock:
                        errors.append(f"{sub_id}: {type(e).__name__}: {str(e)}")
                finally:
                    pbar.update(1)

    print(f"\nTotal Native Objects found across all subscriptions: {len(all_native_objects)}")
    print(f"Successfully scanned: {len(scanned_subs)}/{len(scanned_subs) + len(errors)} subscriptions")
    if errors:
        print(f"Failed subscriptions: {len(errors)}")

    # Log failed subscriptions to a separate file
    if errors:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        error_file = f"output/azure_failed_subscriptions_{timestamp}.txt"
        try:
            os.makedirs("output", exist_ok=True)
            with open(error_file, 'w') as f:
                for error in errors:
                    f.write(error + '\n')
            print(f"Failed subscriptions logged to: {error_file}")
        except Exception as e:
            print(f"Warning: Failed to write error log: {e}")

    # Create a dummy discovery for counting and saving
    config = AzureConfig(
        regions=all_regions,
        output_directory="output",
        output_format=args.format,
        subscription_id=all_subs[0] if all_subs else "",
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

        # Generate Universal DDI licensing calculations
        from shared.output_utils import run_licensing_export

        run_licensing_export(
            all_native_objects,
            provider="azure",
            scope={"subscriptions": scanned_subs},
            regions=all_regions,
        )

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
