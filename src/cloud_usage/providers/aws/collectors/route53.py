"""Route53 resource collectors.

Discovers Route53 hosted zones and DNS records. Route53 is a global service
(not per-region), so these collectors set region="global" on all resources.
The route53_client should be created with region_name="us-east-1".
"""

from __future__ import annotations

from cloud_usage.resilience.retry import retry_with_backoff
from cloud_usage.schema.resource import CloudResource


@retry_with_backoff(max_retries=3)
def collect_route53_zones(
    route53_client,
    account_id: str,
) -> list[CloudResource]:
    """Discover all Route53 hosted zones in an account.

    Route53 is account-global (not per-region, per Pitfall 1). Each zone
    is classified as public or private based on Config.PrivateZone.

    Args:
        route53_client: boto3 Route53 client (created with us-east-1).
        account_id: AWS account ID owning these zones.

    Returns:
        List of CloudResource with resource_type="route53-zone".
    """
    resources: list[CloudResource] = []
    paginator = route53_client.get_paginator("list_hosted_zones")

    for page in paginator.paginate():
        for zone in page.get("HostedZones", []):
            # Zone ID comes as "/hostedzone/Z1234..." -- strip prefix
            raw_id = zone.get("Id", "")
            zone_id = raw_id.split("/")[-1] if "/" in raw_id else raw_id

            # Zone name has trailing dot -- strip it
            zone_name = zone.get("Name", "").rstrip(".")

            is_private = zone.get("Config", {}).get("PrivateZone", False)

            resources.append(
                CloudResource(
                    resource_id=zone_id,
                    resource_type="route53-zone",
                    provider="aws",
                    account_id=account_id,
                    region="global",
                    name=zone_name,
                    ip_addresses=[],
                    tags={},
                    details={
                        "zone_type": "private" if is_private else "public",
                        "record_count": zone.get("ResourceRecordSetCount", 0),
                    },
                )
            )

    return resources


@retry_with_backoff(max_retries=3)
def collect_route53_records(
    route53_client,
    account_id: str,
    zone_id: str,
    zone_name: str,
) -> list[CloudResource]:
    """Discover all DNS records in a Route53 hosted zone.

    All record types are included (A, AAAA, CNAME, MX, NS, SOA, TXT, SRV,
    etc.) per CONTEXT decision. A records have IPv4 IPs extracted; AAAA
    records have IPv6 IPs extracted. Other types have empty ip_addresses.

    Args:
        route53_client: boto3 Route53 client (created with us-east-1).
        account_id: AWS account ID owning these records.
        zone_id: Route53 hosted zone ID (without /hostedzone/ prefix).
        zone_name: Human-readable zone name (without trailing dot).

    Returns:
        List of CloudResource with resource_type="route53-record".
    """
    resources: list[CloudResource] = []
    paginator = route53_client.get_paginator("list_resource_record_sets")

    for page in paginator.paginate(HostedZoneId=zone_id):
        for record_set in page.get("ResourceRecordSets", []):
            record_name = record_set.get("Name", "").rstrip(".")
            record_type = record_set.get("Type", "")

            # Build unique resource ID from zone, name, and type
            resource_id = f"{zone_id}/{record_name}/{record_type}"

            # Extract IPs for A and AAAA records
            ip_addresses: list[str] = []
            if record_type in ("A", "AAAA"):
                for rr in record_set.get("ResourceRecords", []):
                    value = rr.get("Value", "")
                    if value:
                        ip_addresses.append(value)

            # Check for alias
            has_alias = "AliasTarget" in record_set

            resources.append(
                CloudResource(
                    resource_id=resource_id,
                    resource_type="route53-record",
                    provider="aws",
                    account_id=account_id,
                    region="global",
                    name=record_name,
                    ip_addresses=ip_addresses,
                    tags={},
                    details={
                        "zone_id": zone_id,
                        "zone_name": zone_name,
                        "record_type": record_type,
                        "ttl": record_set.get("TTL"),
                        "alias": has_alias,
                    },
                )
            )

    return resources


@retry_with_backoff(max_retries=3)
def collect_resolver_endpoints(
    resolver_client,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover Route53 Resolver Endpoints in a region (AWSG-01).

    Uses the route53resolver client (distinct from route53 — see Pitfall 1).
    Resolver is per-region; this function is called inside the per-region loop
    in discover_account() with a region-specific route53resolver client.

    Args:
        resolver_client: boto3 route53resolver client for the target region.
        account_id: AWS account ID owning these resources.
        region: AWS region being scanned.

    Returns:
        List of CloudResource with resource_type="aws-resolver-endpoint".
    """
    resources: list[CloudResource] = []
    paginator = resolver_client.get_paginator("list_resolver_endpoints")

    for page in paginator.paginate():
        for ep in page.get("ResolverEndpoints", []):
            resources.append(
                CloudResource(
                    resource_id=ep["Id"],
                    resource_type="aws-resolver-endpoint",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=ep.get("Name", ""),
                    ip_addresses=[],
                    tags={},
                    details={
                        "direction": ep.get("Direction", ""),
                        "status": ep.get("Status", ""),
                        "ip_address_count": ep.get("IpAddressCount", 0),
                        "vpc_id": ep.get("HostVpcId", ""),
                    },
                )
            )
    return resources


@retry_with_backoff(max_retries=3)
def collect_resolver_rules(
    resolver_client,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover Route53 Resolver Rules in a region (AWSG-02).

    No filtering — count all rules including system-managed rules, matching
    reference implementation behavior.

    Args:
        resolver_client: boto3 route53resolver client for the target region.
        account_id: AWS account ID owning these resources.
        region: AWS region being scanned.

    Returns:
        List of CloudResource with resource_type="aws-resolver-rule".
    """
    resources: list[CloudResource] = []
    paginator = resolver_client.get_paginator("list_resolver_rules")

    for page in paginator.paginate():
        for rule in page.get("ResolverRules", []):
            resources.append(
                CloudResource(
                    resource_id=rule["Id"],
                    resource_type="aws-resolver-rule",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=rule.get("Name", ""),
                    ip_addresses=[],
                    tags={},
                    details={
                        "rule_type": rule.get("RuleType", ""),
                        "domain_name": rule.get("DomainName", "").rstrip("."),
                        "status": rule.get("Status", ""),
                    },
                )
            )
    return resources


@retry_with_backoff(max_retries=3)
def collect_resolver_rule_associations(
    resolver_client,
    account_id: str,
    region: str,
) -> list[CloudResource]:
    """Discover Route53 Resolver Rule Associations in a region (AWSG-02).

    Each association links a resolver rule to a VPC. Counted as a separate
    DDI object per the reference implementation.

    Args:
        resolver_client: boto3 route53resolver client for the target region.
        account_id: AWS account ID owning these resources.
        region: AWS region being scanned.

    Returns:
        List of CloudResource with resource_type="aws-resolver-rule-association".
    """
    resources: list[CloudResource] = []
    paginator = resolver_client.get_paginator("list_resolver_rule_associations")

    for page in paginator.paginate():
        for assoc in page.get("ResolverRuleAssociations", []):
            resources.append(
                CloudResource(
                    resource_id=assoc["Id"],
                    resource_type="aws-resolver-rule-association",
                    provider="aws",
                    account_id=account_id,
                    region=region,
                    name=assoc.get("Name", ""),
                    ip_addresses=[],
                    tags={},
                    details={
                        "resolver_rule_id": assoc.get("ResolverRuleId", ""),
                        "vpc_id": assoc.get("VPCId", ""),
                        "status": assoc.get("Status", ""),
                    },
                )
            )
    return resources


@retry_with_backoff(max_retries=3)
def collect_health_checks(
    route53_client,
    account_id: str,
) -> list[CloudResource]:
    """Discover Route53 Health Checks in an account (AWSG-07).

    Global resource — uses the same route53 client as collect_route53_zones.
    Called once per account in the global section of discover_account().

    Args:
        route53_client: boto3 Route53 client (global, us-east-1).
        account_id: AWS account ID owning these resources.

    Returns:
        List of CloudResource with resource_type="aws-route53-health-check".
    """
    resources: list[CloudResource] = []
    paginator = route53_client.get_paginator("list_health_checks")

    for page in paginator.paginate():
        for hc in page.get("HealthChecks", []):
            hc_config = hc.get("HealthCheckConfig", {})
            resources.append(
                CloudResource(
                    resource_id=hc["Id"],
                    resource_type="aws-route53-health-check",
                    provider="aws",
                    account_id=account_id,
                    region="global",
                    name=hc.get("Id", ""),
                    ip_addresses=[],
                    tags={},
                    details={
                        "type": hc_config.get("Type", ""),
                        "fqdn": hc_config.get("FullyQualifiedDomainName", ""),
                        "ip_address": hc_config.get("IPAddress", ""),
                    },
                )
            )
    return resources


@retry_with_backoff(max_retries=3)
def collect_traffic_policies(
    route53_client,
    account_id: str,
) -> list[CloudResource]:
    """Discover Route53 Traffic Policies in an account (AWSG-07).

    IMPORTANT: list_traffic_policies returns "TrafficPolicySummaries" (not
    "TrafficPolicies") — this is a known API quirk (see Pitfall 6 in RESEARCH.md).

    Args:
        route53_client: boto3 Route53 client (global, us-east-1).
        account_id: AWS account ID owning these resources.

    Returns:
        List of CloudResource with resource_type="aws-route53-traffic-policy".
    """
    resources: list[CloudResource] = []
    paginator = route53_client.get_paginator("list_traffic_policies")

    for page in paginator.paginate():
        for policy in page.get("TrafficPolicySummaries", []):
            resources.append(
                CloudResource(
                    resource_id=policy["Id"],
                    resource_type="aws-route53-traffic-policy",
                    provider="aws",
                    account_id=account_id,
                    region="global",
                    name=policy.get("Name", ""),
                    ip_addresses=[],
                    tags={},
                    details={
                        "type": policy.get("Type", ""),
                        "latest_version": policy.get("LatestVersion", 0),
                        "traffic_policy_count": policy.get("TrafficPolicyCount", 0),
                    },
                )
            )
    return resources


@retry_with_backoff(max_retries=3)
def collect_traffic_policy_instances(
    route53_client,
    account_id: str,
) -> list[CloudResource]:
    """Discover Route53 Traffic Policy Instances in an account (AWSG-07).

    Traffic policy instances are separate DDI objects from traffic policies
    themselves — each instance is a DNS name with a traffic policy applied.

    Args:
        route53_client: boto3 Route53 client (global, us-east-1).
        account_id: AWS account ID owning these resources.

    Returns:
        List of CloudResource with resource_type="aws-route53-traffic-policy-instance".
    """
    resources: list[CloudResource] = []
    paginator = route53_client.get_paginator("list_traffic_policy_instances")

    for page in paginator.paginate():
        for instance in page.get("TrafficPolicyInstances", []):
            resources.append(
                CloudResource(
                    resource_id=instance["Id"],
                    resource_type="aws-route53-traffic-policy-instance",
                    provider="aws",
                    account_id=account_id,
                    region="global",
                    name=instance.get("Name", "").rstrip("."),
                    ip_addresses=[],
                    tags={},
                    details={
                        "traffic_policy_id": instance.get("TrafficPolicyId", ""),
                        "traffic_policy_version": instance.get("TrafficPolicyVersion", 0),
                        "hosted_zone_id": instance.get("HostedZoneId", ""),
                    },
                )
            )
    return resources
