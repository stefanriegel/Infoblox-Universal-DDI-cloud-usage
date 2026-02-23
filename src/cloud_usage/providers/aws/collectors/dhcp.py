"""DHCP option set collector.

Discovers DHCP option sets and cross-references them with VPCs to identify
orphaned sets. The caller (discover_account in provider.py) should first
collect VPCs, extract their DhcpOptionsId values into a set, then pass
that set as vpc_dhcp_ids to this collector.
"""

from __future__ import annotations

from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource


@retry_with_backoff(max_retries=3)
def collect_dhcp_option_sets(
    ec2_client,
    account_id: str,
    region: str,
    vpc_dhcp_ids: set[str],
) -> list[CloudResource]:
    """Discover all DHCP option sets in a region.

    Cross-references each DHCP option set with vpc_dhcp_ids to determine
    if it is orphaned. Orphaned sets (not associated with any VPC) are
    still discovered but marked with details["orphaned"]=True so the
    categorizer (Plan 02) can set counted=False.

    Args:
        ec2_client: boto3 EC2 client for the target account/region.
        account_id: AWS account ID owning these resources.
        region: AWS region being scanned.
        vpc_dhcp_ids: Set of DHCP option set IDs that are associated
            with at least one VPC. Built by caller from VPC discovery
            results: {vpc.details["dhcp_options_id"] for vpc in vpcs}.

    Returns:
        List of CloudResource with resource_type="dhcp-option-set".
    """
    resources: list[CloudResource] = []
    paginator = ec2_client.get_paginator("describe_dhcp_options")

    for page in paginator.paginate():
        for dhcp_opts in page.get("DhcpOptions", []):
            dhcp_id = dhcp_opts["DhcpOptionsId"]
            is_orphaned = dhcp_id not in vpc_dhcp_ids

            # Extract configuration key-value pairs
            configurations: list[dict[str, str | list[str]]] = []
            for config in dhcp_opts.get("DhcpConfigurations", []):
                key = config.get("Key", "")
                values = [v.get("Value", "") for v in config.get("Values", [])]
                configurations.append({"key": key, "values": values})

            tags = dhcp_opts.get("Tags", [])
            tag_dict = {}
            if tags:
                tag_dict = {t["Key"]: t["Value"] for t in tags if "Key" in t}

            name = ""
            for t in (tags or []):
                if t.get("Key") == "Name":
                    name = t.get("Value", "")
                    break

            resources.append(
                CloudResource(
                    resource_id=dhcp_id,
                    resource_type="dhcp-option-set",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=name,
                    ip_addresses=[],
                    tags=tag_dict,
                    details={
                        "orphaned": is_orphaned,
                        "configurations": configurations,
                    },
                )
            )

    return resources
