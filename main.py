#!/usr/bin/env python3
"""
Main entry point for Infoblox Universal DDI Resource Counter.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def _print_kv(key: str, value: str) -> None:
    print(f"  {key}: {value}")


def _check_aws_auth() -> int:
    print("AWS Authentication Check")
    print("=" * 28)

    # Optional: AWS CLI helps with SSO login for non-experienced users.
    try:
        proc = subprocess.run(["aws", "--version"], capture_output=True, text=True)
        output = (proc.stdout or "") + (proc.stderr or "")
        m = re.search(r"aws-cli/(\d+)\.(\d+)\.(\d+)", output)
        if m:
            major, minor, patch = map(int, m.groups())
            _print_kv("aws CLI", f"{major}.{minor}.{patch}")
            if (major, minor, patch) < (2, 0, 0):
                print("  WARNING: AWS CLI v2 is recommended for SSO (aws sso login).")
        else:
            _print_kv("aws CLI", "installed (version unknown)")
    except FileNotFoundError:
        _print_kv("aws CLI", "not found (optional, but recommended for SSO)")

    profile = os.getenv("AWS_PROFILE")
    if profile:
        _print_kv("AWS_PROFILE", profile)
    if os.getenv("AWS_ACCESS_KEY_ID"):
        _print_kv("AWS_ACCESS_KEY_ID", "set")

    try:
        import boto3

        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        # Force a real call so we know tokens are valid.
        sts = session.client("sts", region_name=os.getenv("AWS_REGION") or "us-east-1")
        ident = sts.get_caller_identity()
        _print_kv("Account", str(ident.get("Account")))
        _print_kv("Arn", str(ident.get("Arn")))
        print("OK: AWS credentials are working.")
        return 0

    except Exception as e:
        print(f"ERROR: AWS auth check failed: {e}")
        print("Next steps (SSO-friendly):")
        if profile:
            print(f"  1) Run: aws sso login --profile {profile}")
        else:
            print("  1) Run: aws configure sso")
            print("  2) Run: aws sso login --profile <your-profile>")
            print("  3) Set AWS_PROFILE=<your-profile> in your environment")
        print("Alternative (access keys):")
        print("  - Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        return 1


def _check_azure_auth() -> int:
    print("Azure Authentication Check")
    print("=" * 30)

    # Optional: Azure CLI is the simplest login path (az login).
    try:
        proc = subprocess.run(["az", "version"], capture_output=True, text=True)
        if proc.returncode == 0:
            _print_kv("az CLI", "installed")
        else:
            _print_kv("az CLI", "installed (version check failed)")
    except FileNotFoundError:
        _print_kv("az CLI", "not found (optional, but recommended for az login)")

    if os.getenv("AZURE_SUBSCRIPTION_ID"):
        _print_kv("AZURE_SUBSCRIPTION_ID", "set")

    try:
        from azure_discovery.config import get_azure_credential

        credential = get_azure_credential()
        token = credential.get_token("https://management.azure.com/.default")
        _print_kv("Token expires", str(getattr(token, "expires_on", "unknown")))
        print("OK: Azure credentials are working.")
        return 0

    except Exception as e:
        print(f"ERROR: Azure auth check failed: {e}")
        print("Next steps (simple login):")
        print("  1) Run: az login")
        print("  2) (Optional) Get subscription id: az account show --query id -o tsv")
        print("     Then set AZURE_SUBSCRIPTION_ID in your environment")
        print("Alternative (service principal):")
        print("  - Set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID")
        return 1


def _check_gcp_auth() -> int:
    print("GCP Authentication Check")
    print("=" * 28)

    # Optional: gcloud makes application-default login easy.
    try:
        proc = subprocess.run(["gcloud", "--version"], capture_output=True, text=True)
        if proc.returncode == 0:
            _print_kv("gcloud", "installed")
        else:
            _print_kv("gcloud", "installed (version check failed)")
    except FileNotFoundError:
        _print_kv("gcloud", "not found (optional, but recommended)")

    if os.getenv("GOOGLE_CLOUD_PROJECT"):
        _print_kv("GOOGLE_CLOUD_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT") or "")
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        _print_kv("GOOGLE_APPLICATION_CREDENTIALS", "set")

    try:
        from google.auth import default
        from google.auth.transport.requests import Request

        credentials, project = default()
        if project:
            _print_kv("Project", project)

        # Force refresh to validate the credential can obtain an access token.
        refresh = getattr(credentials, "refresh", None)
        if callable(refresh):
            refresh(Request())
        print("OK: GCP credentials are working.")
        if not project and not os.getenv("GOOGLE_CLOUD_PROJECT"):
            print("NOTE: No project detected. Set GOOGLE_CLOUD_PROJECT or run:")
            print("  gcloud config set project <your-project-id>")
        return 0

    except Exception as e:
        print(f"ERROR: GCP auth check failed: {e}")
        print("Next steps (simple login):")
        print("  1) Run: gcloud auth application-default login")
        print("  2) Run: gcloud config set project <your-project-id>")
        print("Alternative (service account):")
        print("  - Set GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
        return 1


def _run_auth_doctor(provider: str) -> int:
    provider = (provider or "").lower()
    if provider == "aws":
        return _check_aws_auth()
    if provider == "azure":
        return _check_azure_auth()
    if provider == "gcp":
        return _check_gcp_auth()
    print(f"Unsupported provider for auth check: {provider}")
    return 1


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Infoblox Universal DDI Resource Counter")
    parser.add_argument(
        "provider",
        choices=["aws", "azure", "gcp"],
        help="Cloud provider to discover (aws, azure, or gcp)",
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
        help="Save/export full resource/object data (default: only summary and token calculation)",
    )
    parser.add_argument(
        "--include-counts",
        action="store_true",
        help="Also write legacy resource_count files alongside licensing outputs",
    )
    parser.add_argument(
        "--check-auth",
        action="store_true",
        help="Validate cloud credentials and print setup guidance, then exit",
    )

    # Remove extra_args, use parse_known_args instead
    args, unknown = parser.parse_known_args()

    if args.check_auth:
        return _run_auth_doctor(args.provider)

    try:
        if args.provider == "aws":
            from aws_discovery.discover import main as aws_main

            aws_args = argparse.Namespace()
            aws_args.format = args.format
            aws_args.workers = args.workers
            aws_args.full = args.full
            aws_args.include_counts = args.include_counts

            aws_main(aws_args)
        elif args.provider == "azure":
            from azure_discovery.discover import main as azure_main

            azure_args = argparse.Namespace()
            azure_args.format = args.format
            azure_args.workers = args.workers
            azure_args.subscription_workers = args.subscription_workers
            azure_args.full = args.full
            azure_args.include_counts = args.include_counts
            azure_args.no_checkpoint = args.no_checkpoint
            azure_args.resume = args.resume
            azure_args.checkpoint_file = args.checkpoint_file
            azure_args.checkpoint_interval = args.checkpoint_interval
            azure_args.retry_attempts = args.retry_attempts
            azure_main(azure_args)
        elif args.provider == "gcp":
            from gcp_discovery.discover import main as gcp_main

            gcp_args = argparse.Namespace()
            gcp_args.format = args.format
            gcp_args.workers = args.workers
            gcp_args.full = args.full
            gcp_args.include_counts = args.include_counts
            gcp_main(gcp_args)
        else:
            print(f"Unsupported provider: {args.provider}")
            return 1
    except ImportError as e:
        print(f"Error importing {args.provider} module: {e}")
        print("Please ensure you have installed the required dependencies:")
        print(f"  pip install -r {args.provider}/requirements.txt")
        return 1
    except Exception as e:
        print(f"Error running {args.provider} discovery: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
