"""Token-free resource collectors for AWS.

Discovers EBS volumes and S3 buckets. These resources are discovered for
the audit trail but never counted toward tokens. They appear in the
detail sheet with counted=False and a skip_reason.
"""

from __future__ import annotations

import logging
from typing import Any

from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


@retry_with_backoff(max_retries=3)
def collect_ebs_volumes(
    ec2_client: Any,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover EBS volumes (token-free, no IPs).

    EBS volumes have no IP addresses and are categorized as token-free
    (counted=False, skip_reason="token-free: EBS Volume"). Discovered
    for the audit trail and detail report.

    Args:
        ec2_client: boto3 EC2 client.
        account_id: AWS account ID.
        region: AWS region name.

    Returns:
        List of CloudResource for each EBS volume.
    """
    resources: list[CloudResource] = []
    paginator = ec2_client.get_paginator("describe_volumes")

    for page in paginator.paginate():
        for vol in page.get("Volumes", []):
            attached_instance_ids = [
                att.get("InstanceId", "")
                for att in vol.get("Attachments", [])
                if att.get("InstanceId")
            ]

            tags = vol.get("Tags", [])

            resources.append(
                CloudResource(
                    resource_id=vol["VolumeId"],
                    resource_type="ebs-volume",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=_get_name_tag(tags),
                    ip_addresses=[],
                    tags=_tags_to_dict(tags),
                    details={
                        "volume_type": vol.get("VolumeType", ""),
                        "size_gb": vol.get("Size", 0),
                        "state": vol.get("State", ""),
                        "encrypted": vol.get("Encrypted", False),
                        "attached_instance_ids": attached_instance_ids,
                    },
                )
            )

    logger.debug(
        "Discovered %d EBS volumes in %s/%s",
        len(resources),
        account_id,
        region,
    )
    return resources


@retry_with_backoff(max_retries=3)
def collect_s3_buckets(
    s3_client: Any,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover S3 buckets (token-free, no IPs).

    S3 is a global service; call this once per account (not per-region).
    Bucket region is determined via get_bucket_location. Buckets with
    LocationConstraint=None are in us-east-1.

    Args:
        s3_client: boto3 S3 client.
        account_id: AWS account ID.
        region: Region name (used as default; actual region per bucket).

    Returns:
        List of CloudResource for each S3 bucket.
    """
    resources: list[CloudResource] = []

    try:
        response = s3_client.list_buckets()
    except Exception:
        logger.warning(
            "Failed to list S3 buckets for %s",
            account_id,
            exc_info=True,
        )
        return resources

    for bucket in response.get("Buckets", []):
        bucket_name = bucket.get("Name", "")
        creation_date = bucket.get("CreationDate")

        # Determine bucket region
        bucket_region = region
        try:
            loc = s3_client.get_bucket_location(Bucket=bucket_name)
            constraint = loc.get("LocationConstraint")
            if constraint is None:
                bucket_region = "us-east-1"
            else:
                bucket_region = constraint
        except Exception:
            logger.debug(
                "Could not determine region for bucket %s, using %s",
                bucket_name,
                region,
            )

        resources.append(
            CloudResource(
                resource_id=bucket_name,
                resource_type="s3-bucket",
                provider="aws",
                account_id=account_id,
                region=bucket_region,
                name=bucket_name,
                ip_addresses=[],
                details={
                    "creation_date": (
                        creation_date.isoformat() if creation_date else ""
                    ),
                },
            )
        )

    logger.debug(
        "Discovered %d S3 buckets for account %s",
        len(resources),
        account_id,
    )
    return resources


def _get_name_tag(tags: list[dict[str, str]] | None) -> str:
    """Extract the Name tag value from an AWS tags list."""
    for tag in tags or []:
        if tag.get("Key") == "Name":
            return tag.get("Value", "")
    return ""


def _tags_to_dict(tags: list[dict[str, str]] | None) -> dict[str, str]:
    """Convert AWS tags list to a key-value dict."""
    return {tag["Key"]: tag["Value"] for tag in tags or [] if "Key" in tag}
