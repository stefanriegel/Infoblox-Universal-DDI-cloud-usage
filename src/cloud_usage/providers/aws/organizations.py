"""AWS Organizations multi-account support.

Provides account listing via Organizations API and cross-account role
assumption via STS for multi-account discovery. Falls back gracefully
when Organizations access is unavailable.
"""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError


def list_organization_accounts(session: boto3.Session) -> list[dict]:
    """List all active accounts in the AWS Organization.

    Uses the Organizations list_accounts paginator to retrieve all accounts,
    filtering to only those with Status=="ACTIVE". On AccessDeniedException,
    returns an empty list so the caller can fall back to single-account mode.

    Args:
        session: Authenticated boto3 session with Organizations access.

    Returns:
        List of dicts with at least 'Id' and 'Status' keys (AWS API format).
        Empty list if Organizations access is denied.
    """
    try:
        org = session.client("organizations")
        paginator = org.get_paginator("list_accounts")
        accounts: list[dict] = []
        for page in paginator.paginate():
            accounts.extend(page["Accounts"])
        return [a for a in accounts if a["Status"] == "ACTIVE"]
    except ClientError:
        return []


def assume_cross_account_role(
    sts_client,
    account_id: str,
    role_name: str = "OrganizationAccountAccessRole",
    session_name: str = "InfobloxUDDI-Discovery",
) -> boto3.Session:
    """Assume a role in a target account and return a session with temporary credentials.

    Uses STS assume_role to get temporary credentials for the target account.
    The session name is set to 'InfobloxUDDI-Discovery' for CloudTrail
    auditability.

    Args:
        sts_client: STS client from the management account session.
        account_id: Target AWS account ID.
        role_name: Name of the cross-account role to assume.
        session_name: Session name for CloudTrail audit trail.

    Returns:
        A new boto3.Session with temporary credentials for the target account.

    Raises:
        ClientError: If the role assumption fails (e.g., role doesn't exist,
            access denied).
    """
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
    response = sts_client.assume_role(
        RoleArn=role_arn,
        RoleSessionName=session_name,
        DurationSeconds=3600,
    )
    creds = response["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )
