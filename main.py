#!/usr/bin/env python3
"""
Main entry point for Infoblox Universal DDI Resource Counter.
"""

import argparse
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Infoblox Universal DDI Resource Counter"
    )
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
        "--workers", type=int, default=8, help="Number of parallel workers (default: 8)"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Save/export full resource/object data (default: only summary and resource count)",
    )
    # Remove extra_args, use parse_known_args instead
    args, unknown = parser.parse_known_args()
    try:
        if args.provider == "aws":
            from aws_discovery.discover import main as aws_main

            aws_args = argparse.Namespace()
            aws_args.format = args.format
            aws_args.workers = args.workers
            aws_args.full = args.full

            aws_main(aws_args)
        elif args.provider == "azure":
            from azure_discovery.discover import main as azure_main

            azure_args = argparse.Namespace()
            azure_args.format = args.format
            azure_args.workers = args.workers
            azure_args.full = args.full
            azure_main(azure_args)
        elif args.provider == "gcp":
            from gcp_discovery.discover import main as gcp_main

            gcp_args = argparse.Namespace()
            gcp_args.format = args.format
            gcp_args.workers = args.workers
            gcp_args.full = args.full
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
