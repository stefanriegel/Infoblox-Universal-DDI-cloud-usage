#!/usr/bin/env python3
"""
AWS Cloud Discovery for Infoblox Universal DDI Management Token Calculator.
Discovers AWS Native Objects and calculates Management Token requirements.
"""

import sys
import argparse
import json
import pandas as pd
import math
from pathlib import Path
from datetime import datetime
from botocore.exceptions import NoCredentialsError, ClientError
import boto3

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .aws_discovery import AWSDiscovery
from .config import AWSConfig, get_all_enabled_regions
from .historical_analysis import CloudTrailAnalyzer


def check_aws_credentials():
    session = boto3.Session()
    credentials = session.get_credentials()
    if not credentials:
        print("ERROR: AWS credentials not found. Please configure credentials, set AWS_PROFILE, or run 'aws sso login'. Exiting.")
        sys.exit(1)
    try:
        sts = session.client('sts')
        sts.get_caller_identity()
    except (NoCredentialsError, ClientError) as e:
        print(f"ERROR: AWS credentials are invalid or expired: {e}\nPlease check your credentials or run 'aws sso login'. Exiting.")
        sys.exit(1)


def main(args=None):
    """Main discovery function."""
    if args is None:
        # If called directly, parse arguments from command line
        parser = argparse.ArgumentParser(description="AWS Cloud Discovery for Management Token Calculation")
        parser.add_argument("--format", choices=["json", "csv", "txt"], default="csv",
                           help="Output format (default: csv)")
        parser.add_argument("--workers", type=int, default=5,
                           help="Number of parallel workers (default: 5)")
        parser.add_argument("--analyze-growth", action="store_true",
                           help="Analyze historical growth and predict future requirements")
        args = parser.parse_args()
    
    print("AWS Cloud Discovery for Management Token Calculation")
    print("=" * 55)
    print(f"Output format: {args.format.upper()}")
    print(f"Parallel workers: {args.workers}")
    if args.analyze_growth:
        print("Growth analysis: ENABLED")
    print()
    
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
        output_format=args.format
    )
    discovery = AWSDiscovery(config)
    
    try:
        # Discover Native Objects
        print("Starting AWS Discovery...")
        native_objects = discovery.discover_native_objects(max_workers=args.workers)
        print(f"Found {len(native_objects)} Native Objects")
        
        # Calculate Management Token requirements
        calculation = discovery.calculate_management_token_requirements()
        
        # --- Improved Console Output (Scalable) ---
        # 1. Summary of discovered resources by type (with up to 2 example names)
        print("\n===== AWS Discovery Summary =====")
        type_to_objs = {}
        for obj in native_objects:
            type_to_objs.setdefault(obj['resource_type'], []).append(obj)
        print(f"Discovered {len(native_objects)} resources:")
        for t, objs in type_to_objs.items():
            examples = ', '.join([str(o['name']) for o in objs[:2]])
            more = f", ..." if len(objs) > 2 else ""
            print(f"  - {len(objs)} {t}(s)" + (f" (e.g. {examples}{more})" if examples else ""))
        
        # 2. Token-Free (Non-Counted) Resources: count per type, up to 2 example names
        token_free = discovery.get_management_token_free_assets()
        type_to_free = {}
        for obj in token_free:
            type_to_free.setdefault(obj['resource_type'], []).append(obj)
        print(f"\nToken-Free (Non-Counted) Resources:")
        if not token_free:
            print("  - None")
        else:
            for t, objs in type_to_free.items():
                examples = ', '.join([str(o['name']) for o in objs[:2]])
                more = f", ..." if len(objs) > 2 else ""
                print(f"  - {len(objs)} {t}(s)" + (f" (e.g. {examples}{more})" if examples else ""))
        
        # 3. Counted (Token-Licensed) Resources: count per type, up to 2 example names
        counted = [obj for obj in native_objects if obj['requires_management_token']]
        type_to_counted = {}
        for obj in counted:
            type_to_counted.setdefault(obj['resource_type'], []).append(obj)
        print(f"\nCounted (Token-Licensed) Resources:")
        if not counted:
            print("  - None")
        else:
            for t, objs in type_to_counted.items():
                examples = ', '.join([str(o['name']) for o in objs[:2]])
                more = f", ..." if len(objs) > 2 else ""
                print(f"  - {len(objs)} {t}(s)" + (f" (e.g. {examples}{more})" if examples else ""))
        
        # 4. Token Calculation Breakdown
        print("\nToken Calculation:")
        ddi_objects = calculation['breakdown_by_type'].get('ddi_objects', 0)
        active_ips = calculation['breakdown_by_type'].get('active_ips', 0)
        assets = calculation['breakdown_by_type'].get('assets', 0)
        print(f"  - DDI Objects: {ddi_objects} → {math.ceil(ddi_objects / 25)} token(s)")
        print(f"  - Active IPs: {active_ips} → {math.ceil(active_ips / 13)} token(s)")
        print(f"  - Assets: {assets} → {math.ceil(assets / 3)} token(s)")
        print(f"  - **Total Management Tokens Required: {calculation['management_token_required']}**")
        print(f"  - **Token Packs (1000 tokens each): {calculation['management_token_packs']}**")
        print(f"  - **Total Tokens in Packs: {calculation['management_tokens_packs_total']}**")
        print("===============================\n")
        # --- End Improved Output ---
        
        # Save results
        print(f"Saving results in {args.format.upper()} format...")
        saved_files = discovery.save_discovery_results()
        
        print("Results saved to:")
        for file_type, filepath in saved_files.items():
            print(f"  {file_type}: {filepath}")
        
        # Historical analysis and growth prediction
        if args.analyze_growth:
            print("\n" + "="*50)
            print("HISTORICAL ANALYSIS & GROWTH PREDICTION")
            print("="*50)
            
            analyzer = CloudTrailAnalyzer(all_regions)
            
            # Run complete CloudTrail analysis
            print("Running CloudTrail-based historical analysis...")
            try:
                report, predictions, historical_data = analyzer.run_complete_analysis(
                    days_back=90,  # Last 90 days
                    months_ahead=36,  # 3 years ahead
                    output_format=args.format
                )
                
                print(f"Current Management Tokens: {report['current_state']['management_tokens']}")
                print(f"Current Native Objects: {report['current_state']['native_objects']}")
                print(f"Model Accuracy: {report['growth_analysis']['model_accuracy_tokens']:.2%}")
                
                print("\nGROWTH PREDICTIONS:")
                print(f"  1 Year: {report['predictions']['year_1']['management_tokens']} tokens")
                print(f"  2 Years: {report['predictions']['year_2']['management_tokens']} tokens")
                print(f"  3 Years: {report['predictions']['year_3']['management_tokens']} tokens")
                
                # Save growth reports
                print("Saving growth analysis reports...")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Save predictions
                predictions_file = f"output/aws_growth_predictions_{timestamp}.{args.format}"
                if args.format == 'csv':
                    predictions.to_csv(predictions_file, index=False)
                elif args.format == 'json':
                    predictions.to_json(predictions_file, orient='records', indent=2)
                else:  # txt
                    with open(predictions_file, 'w') as f:
                        f.write("AWS Growth Predictions\n")
                        f.write("=" * 30 + "\n\n")
                        for _, row in predictions.iterrows():
                            f.write(f"Month: {row['month']}\n")
                            f.write(f"  Predicted Tokens: {row['predicted_tokens']}\n")
                            f.write(f"  Predicted Objects: {row['predicted_objects']}\n\n")
                
                # Save summary report
                summary_file = f"output/aws_growth_summary_{timestamp}.{args.format}"
                if args.format == 'csv':
                    summary_df = pd.DataFrame([report])
                    summary_df.to_csv(summary_file, index=False)
                elif args.format == 'json':
                    with open(summary_file, 'w') as f:
                        json.dump(report, f, indent=2, default=str)
                else:  # txt
                    with open(summary_file, 'w') as f:
                        f.write("AWS Growth Analysis Summary\n")
                        f.write("=" * 30 + "\n\n")
                        f.write(f"Analysis Date: {report['analysis_timestamp']}\n")
                        f.write(f"Current Tokens: {report['current_state']['management_tokens']}\n")
                        f.write(f"Current Objects: {report['current_state']['native_objects']}\n")
                        f.write(f"Model Accuracy: {report['growth_analysis']['model_accuracy_tokens']:.2%}\n\n")
                        f.write("Predictions:\n")
                        for year, data in report['predictions'].items():
                            f.write(f"  {year}: {data['management_tokens']} tokens\n")
                        f.write("\nRecommendations:\n")
                        for period, rec in report['recommendations'].items():
                            f.write(f"  {period}: {rec}\n")
                
                print("Growth analysis files saved to:")
                print(f"  Predictions: {predictions_file}")
                print(f"  Summary: {summary_file}")
                
                # Create visualization
                print("Creating growth visualization...")
                plot_path = f"output/aws_growth_prediction_{timestamp}.png"
                analyzer.create_growth_visualization(historical_data, predictions, plot_path)
                print(f"  Growth chart: {plot_path}")
                
            except Exception as e:
                print(f"CloudTrail analysis failed: {e}")
                print("This might be due to:")
                print("  - CloudTrail not enabled in your AWS account")
                print("  - Insufficient CloudTrail permissions")
                print("  - No CloudTrail events in the last 90 days")
                print("Continuing without historical analysis...")
        
        print(f"\nDiscovery completed successfully!")
        
        return 0
        
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    exit(main()) 