"""
Utility functions for AWS Cloud Discovery.
"""

import json
import os
import csv
from typing import Dict, List, Any
import boto3
from botocore.exceptions import NoCredentialsError
import pandas as pd


def get_aws_client(service_name: str, region: str, config) -> Any:
    """Get AWS client for specified service and region."""
    try:
        if config.aws_profile:
            session = boto3.Session(profile_name=config.aws_profile)
            return session.client(service_name, region_name=region)
        else:
            return boto3.client(
                service_name,
                region_name=region,
                aws_access_key_id=config.aws_access_key_id,
                aws_secret_access_key=config.aws_secret_access_key
            )
    except NoCredentialsError:
        raise NoCredentialsError("AWS credentials not found. Please configure AWS credentials.")


def save_output(data: Any, filename: str, output_dir: str, format_type: str = "json") -> str:
    """Save discovery data to file in specified format."""
    os.makedirs(output_dir, exist_ok=True)
    
    if format_type == "json":
        filepath = os.path.join(output_dir, f"{filename}.json")
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    elif format_type == "csv":
        filepath = os.path.join(output_dir, f"{filename}.csv")
        if isinstance(data, list) and data:
            # Convert list of dictionaries to CSV
            df = pd.DataFrame(data)
            df.to_csv(filepath, index=False)
        else:
            # For non-list data, create a simple CSV
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                if isinstance(data, dict):
                    for key, value in data.items():
                        writer.writerow([key, str(value)])
                else:
                    writer.writerow([str(data)])
    
    elif format_type == "txt":
        filepath = os.path.join(output_dir, f"{filename}.txt")
        with open(filepath, 'w') as f:
            if isinstance(data, dict):
                for key, value in data.items():
                    f.write(f"{key}: {value}\n")
            elif isinstance(data, list):
                for item in data:
                    f.write(f"{item}\n")
            else:
                f.write(str(data))
    
    else:
        raise ValueError(f"Unsupported format: {format_type}")
    
    return filepath


def get_resource_tags(tags: List[Dict[str, str]]) -> Dict[str, str]:
    """Convert AWS tags list to dictionary."""
    return {tag['Key']: tag['Value'] for tag in tags} if tags else {} 