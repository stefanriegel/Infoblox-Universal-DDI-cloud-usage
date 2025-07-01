#!/usr/bin/env python3
"""
Main entry point for Infoblox Universal DDI Management Token Calculator.
"""

import argparse
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Infoblox Universal DDI Management Token Calculator"
    )
    parser.add_argument(
        "provider",
        choices=["aws", "azure"],
        help="Cloud provider to discover (aws or azure)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "txt"],
        default="csv",
        help="Output format (default: csv)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=5,
        help="Number of parallel workers (default: 5)"
    )
    parser.add_argument(
        "--analyze-growth",
        action="store_true",
        help="Analyze historical growth and predict future requirements"
    )
    
    args = parser.parse_args()
    try:
        if args.provider == "aws":
            from aws_discovery.discover import main as aws_main
            aws_main(args)
        elif args.provider == "azure":
            from azure_discovery.discover import main as azure_main
            azure_main(args)
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