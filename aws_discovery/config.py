"""
Configuration module for AWS Cloud Discovery.
"""

import os
import boto3
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class AWSConfig:
    """AWS configuration settings."""
    
    # AWS credentials
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_profile: Optional[str] = None
    
    # AWS regions to scan
    regions: Optional[List[str]] = None
    
    # Output settings
    output_directory: str = "output"
    output_format: str = "csv"  # json, csv, txt
    
    def __post_init__(self):
        """Initialize default values."""
        if self.regions is None:
            self.regions = ["us-east-1", "us-west-2", "eu-west-1"]
        
        # Load from environment variables if not provided
        if not self.aws_access_key_id:
            self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        if not self.aws_secret_access_key:
            self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        if not self.aws_profile:
            self.aws_profile = os.getenv("AWS_PROFILE")


def get_all_enabled_regions() -> List[str]:
    """Get all enabled regions for the AWS account."""
    try:
        # Use us-east-1 as the default region to get the list of all regions
        ec2_client = boto3.client('ec2', region_name='us-east-1')
        response = ec2_client.describe_regions()
        
        # Extract region names and filter for enabled regions
        enabled_regions = [
            region['RegionName'] 
            for region in response['Regions'] 
            if region['OptInStatus'] in ['opt-in-not-required', 'opted-in']
        ]
        
        return sorted(enabled_regions)
    except Exception as e:
        print(f"Warning: Could not fetch enabled regions: {e}")
        # Fallback to common regions
        return ["us-east-1", "us-west-2", "eu-west-1", "eu-central-1", "ap-southeast-1"]


def load_config() -> AWSConfig:
    """Load AWS configuration from environment."""
    return AWSConfig() 