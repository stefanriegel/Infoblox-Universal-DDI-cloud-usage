"""
Utility functions for AWS Cloud Discovery.
"""

import boto3
from botocore.exceptions import NoCredentialsError
from typing import Any
from shared.output_utils import get_resource_tags


def get_aws_client(service_name: str, region: str, config) -> Any:
    """Get AWS client for specified service and region, supporting SSO and default credential chain."""
    try:
        if config.aws_profile:
            session = boto3.Session(profile_name=config.aws_profile)
            return session.client(service_name, region_name=region)
        elif config.aws_access_key_id and config.aws_secret_access_key:
            return boto3.client(
                service_name,
                region_name=region,
                aws_access_key_id=config.aws_access_key_id,
                aws_secret_access_key=config.aws_secret_access_key
            )
        else:
            # Use default credential chain (env, config, SSO, etc.)
            return boto3.client(service_name, region_name=region)
    except NoCredentialsError:
        raise RuntimeError(
            "AWS credentials not found. Please configure AWS credentials, set AWS_PROFILE, or run 'aws sso login' for SSO profiles."
        ) 