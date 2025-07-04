"""
Configuration module for AWS Cloud Discovery.
"""

import os
import boto3
from typing import List, Optional
from dataclasses import dataclass
import sys
from botocore.exceptions import NoCredentialsError
from shared.config import BaseConfig


@dataclass
class AWSConfig(BaseConfig):
    """AWS configuration settings."""
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_profile: Optional[str] = None
    # regions, output_directory, output_format inherited from BaseConfig

    def __post_init__(self):
        super().__post_init__()
        if not self.regions:
            self.regions = get_all_enabled_regions()
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
    except NoCredentialsError:
        print("""ERROR: AWS credentials not found.\nPlease configure credentials, set AWS_PROFILE, or run 'aws sso login' for SSO profiles.\nExiting.""")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Could not fetch enabled regions: {e}")
        sys.exit(1)


def load_config() -> AWSConfig:
    """Load AWS configuration from environment."""
    return AWSConfig() 