"""AWS region discovery via EC2 describe_regions.

Discovers all enabled regions for the current account using the EC2
describe_regions API, filtering to opt-in-not-required and opted-in
regions. Never hardcodes a region list.
"""

from __future__ import annotations

import boto3


def get_enabled_regions(session: boto3.Session) -> list[str]:
    """Get all enabled regions for the current AWS account.

    Creates an EC2 client in us-east-1 and calls describe_regions with
    a filter for opt-in-not-required and opted-in regions. Returns a
    sorted list of region name strings.

    Args:
        session: Authenticated boto3 session.

    Returns:
        Sorted list of enabled region name strings
        (e.g., ["ap-northeast-1", "eu-west-1", "us-east-1"]).
    """
    ec2 = session.client("ec2", region_name="us-east-1")
    response = ec2.describe_regions(
        Filters=[
            {
                "Name": "opt-in-status",
                "Values": ["opt-in-not-required", "opted-in"],
            }
        ]
    )
    return sorted(r["RegionName"] for r in response["Regions"])
