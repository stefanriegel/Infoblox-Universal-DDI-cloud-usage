"""CLI entry point with interactive provider selection and scan orchestration.

Provides the main command-line interface for the cloud usage estimator.
Features interactive provider selection prompts for guided use, and
CLI flags (--aws, --azure, --gcp) for scripted/CI use. Integrates
auth doctor, checkpoint detection, discovery orchestrator, counting
pipeline, and output generation in the correct sequence.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime

from cloud_usage.auth.doctor import AuthDoctor
from cloud_usage.counting.asset_dedup import (
    deduplicate_assets,
    exclude_managed_service_resources,
    fold_enis_into_parents,
)
from cloud_usage.counting.categorizer import categorize_resources
from cloud_usage.counting.ip_counter import deduplicate_ips_per_vpc
from cloud_usage.counting.token_calculator import (
    calculate_account_tokens,
    calculate_provider_tokens,
)
from cloud_usage.discovery.orchestrator import DiscoveryOrchestrator
from cloud_usage.discovery.progress import ProgressTracker
from cloud_usage.logging.audit import setup_audit_logger
from cloud_usage.output.estimator_csv import write_estimator_csv
from cloud_usage.output.proof_manifest import write_proof_manifest
from cloud_usage.output.xlsx_report import write_xlsx_report
from cloud_usage.resilience.checkpoint import CheckpointEngine
from cloud_usage.resilience.rate_limiter import RateLimiter

# Valid provider names
_VALID_PROVIDERS = ("aws", "azure", "gcp")

# Display mapping for provider names
_PROVIDER_DISPLAY = {"aws": "AWS", "azure": "Azure", "gcp": "GCP"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the cloud usage estimator.

    Args:
        argv: Argument list to parse. Defaults to sys.argv[1:] if None.

    Returns:
        Parsed Namespace with all CLI options.
    """
    parser = argparse.ArgumentParser(
        prog="cloud-usage",
        description=(
            "Infoblox Universal DDI Cloud Usage Estimator. "
            "Discovers cloud resources across AWS, Azure, and GCP to estimate "
            "UDDI token consumption."
        ),
    )

    parser.add_argument(
        "--web",
        action="store_true",
        default=False,
        help="Launch web dashboard instead of CLI scan",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for web dashboard (default: 8080)",
    )
    parser.add_argument(
        "--aws",
        action="store_true",
        default=False,
        help="Include AWS in the scan (bypasses interactive prompt)",
    )
    parser.add_argument(
        "--azure",
        action="store_true",
        default=False,
        help="Include Azure in the scan (bypasses interactive prompt)",
    )
    parser.add_argument(
        "--gcp",
        action="store_true",
        default=False,
        help="Include GCP in the scan (bypasses interactive prompt)",
    )
    parser.add_argument(
        "--skip-auth-check",
        action="store_true",
        default=False,
        help="Skip the pre-flight auth doctor check",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="Output directory for results and logs (default: ./output)",
    )
    parser.add_argument(
        "--checkpoint-ttl",
        type=int,
        default=48,
        help="Checkpoint TTL in hours (default: 48)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        default=False,
        help="Ignore existing checkpoints and start a fresh scan",
    )

    # AWS-specific options
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="AWS profile name for boto3 session",
    )
    parser.add_argument(
        "--role-name",
        type=str,
        default="OrganizationAccountAccessRole",
        help="Cross-account role name for AWS Organizations mode (default: OrganizationAccountAccessRole)",
    )
    parser.add_argument(
        "--include-accounts",
        type=str,
        default=None,
        help="Comma-separated AWS account IDs to include (takes precedence over --exclude-accounts)",
    )
    parser.add_argument(
        "--exclude-accounts",
        type=str,
        default=None,
        help="Comma-separated AWS account IDs to exclude from scan",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show scan plan (accounts, regions, resource types) without making discovery API calls",
    )

    # Azure-specific options
    parser.add_argument(
        "--include-subscriptions",
        type=str,
        default=None,
        help="Comma-separated Azure subscription IDs or display names to include (takes precedence over --exclude-subscriptions)",
    )
    parser.add_argument(
        "--exclude-subscriptions",
        type=str,
        default=None,
        help="Comma-separated Azure subscription IDs or display names to exclude from scan",
    )

    # GCP-specific options
    parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="GCP project ID for single-project mode (bypasses project enumeration)",
    )
    parser.add_argument(
        "--org-id",
        type=str,
        default=None,
        help="GCP organization ID to scope project enumeration",
    )
    parser.add_argument(
        "--include-projects",
        type=str,
        default=None,
        help="Comma-separated glob patterns for GCP project IDs to include (takes precedence over --exclude-projects)",
    )
    parser.add_argument(
        "--exclude-projects",
        type=str,
        default=None,
        help="Comma-separated glob patterns for GCP project IDs to exclude from scan",
    )

    return parser.parse_args(argv)


def select_providers() -> list[str]:
    """Interactively prompt the user to select cloud providers to scan.

    Shows a numbered menu and accepts comma-separated numbers or names.
    Re-prompts on invalid input until a valid selection is made.

    Returns:
        List of selected provider name strings (e.g., ["aws", "gcp"]).
    """
    sys.stderr.write("\nWhich cloud providers would you like to scan?\n")
    sys.stderr.write("  1. AWS\n")
    sys.stderr.write("  2. Azure\n")
    sys.stderr.write("  3. GCP\n")
    sys.stderr.write("\n")

    number_map = {"1": "aws", "2": "azure", "3": "gcp"}

    while True:
        try:
            raw = input("Enter selection (e.g., 1,3 or aws,gcp): ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.stderr.write("\n")
            return []

        if not raw:
            sys.stderr.write("Please enter at least one provider.\n")
            continue

        parts = [p.strip().lower() for p in raw.split(",")]
        selected: list[str] = []
        invalid = False

        for part in parts:
            if part in number_map:
                selected.append(number_map[part])
            elif part in _VALID_PROVIDERS:
                selected.append(part)
            else:
                sys.stderr.write(f"Invalid selection: '{part}'. Use 1-3 or aws/azure/gcp.\n")
                invalid = True
                break

        if invalid:
            continue

        if not selected:
            sys.stderr.write("Please enter at least one provider.\n")
            continue

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for p in selected:
            if p not in seen:
                seen.add(p)
                unique.append(p)

        return unique


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the cloud usage estimator CLI.

    Orchestrates the full scan lifecycle:
    1. Parse arguments and determine selected providers
    2. Set up audit logging
    3. Run auth doctor pre-flight checks (unless skipped)
    4. Check for existing checkpoint and offer resume
    5. Create and run discovery orchestrator
    6. Run counting pipeline (ENI folding -> dedup -> categorization -> IP counting -> tokens)
    7. Generate output files (XLS, CSV, proof manifest)
    8. Print final summary

    Args:
        argv: Argument list. Defaults to sys.argv[1:] if None.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    args = parse_args(argv)

    # Web dashboard mode
    if args.web:
        try:
            import uvicorn

            from cloud_usage.dashboard.app import create_app
        except ImportError:
            sys.stderr.write(
                "Dashboard dependencies not installed. Run:\n"
                "  pip install fastapi uvicorn jinja2 janus python-multipart\n"
            )
            return 1

        sys.stderr.write(
            f"\nStarting UDDI Cloud Usage Estimator dashboard at "
            f"http://localhost:{args.port}\n"
        )
        uvicorn.run(create_app(), host="0.0.0.0", port=args.port)
        return 0

    # Determine selected providers
    if args.aws or args.azure or args.gcp:
        # Scripted mode: use CLI flags
        selected: list[str] = []
        if args.aws:
            selected.append("aws")
        if args.azure:
            selected.append("azure")
        if args.gcp:
            selected.append("gcp")
    else:
        # Interactive mode: prompt user
        selected = select_providers()
        if not selected:
            sys.stderr.write("No providers selected. Exiting.\n")
            return 1

    # Set up audit logger
    scan_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_logger = setup_audit_logger(args.output_dir, scan_id=scan_id)
    audit_logger.info("Scan started with providers: %s", ", ".join(selected))

    # Pre-flight auth check
    if not args.skip_auth_check:
        sys.stderr.write("\nPre-flight auth check:\n")
        validators = _get_auth_validators(selected, args)
        doctor = AuthDoctor(validators=validators)
        results = doctor.check_all(selected)
        all_passed = doctor.report(results)

        passing = doctor.get_passing_providers(results)

        if not passing:
            sys.stderr.write("\nAll auth checks failed. Cannot proceed.\n")
            audit_logger.error("All auth checks failed for providers: %s", ", ".join(selected))
            return 1

        if not all_passed and passing:
            display_passing = ", ".join(_PROVIDER_DISPLAY.get(p, p) for p in passing)
            sys.stderr.write(f"\nContinue with {display_passing} only? [Y/n] ")
            try:
                response = input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                sys.stderr.write("\n")
                return 1

            if response in ("n", "no"):
                sys.stderr.write("Scan cancelled.\n")
                return 1

            selected = passing
            audit_logger.info("Continuing with passing providers only: %s", ", ".join(selected))

    # Check for existing checkpoint
    checkpoint_engine = CheckpointEngine(
        checkpoint_dir=f"{args.output_dir}/.checkpoints",
        ttl_hours=args.checkpoint_ttl,
    )
    resumed_checkpoint = None

    if not args.no_resume:
        existing = checkpoint_engine.load()
        if existing is not None:
            prompt = checkpoint_engine.format_resume_prompt(existing)
            sys.stderr.write(f"\n{prompt} ")
            try:
                response = input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                sys.stderr.write("\n")
                return 1

            if response not in ("n", "no"):
                resumed_checkpoint = existing
                audit_logger.info("Resuming from checkpoint: %s", existing.scan_id)
            else:
                audit_logger.info("User declined checkpoint resume, starting fresh")

    # Create discovery providers for selected cloud platforms
    providers = _get_discovery_providers(selected, args)

    if not providers:
        sys.stderr.write(
            "\nNo discovery providers configured. "
            "Provider implementations will be added in subsequent phases.\n"
        )
        audit_logger.info("No discovery providers available for selected providers: %s", ", ".join(selected))
        sys.stderr.write("Scan complete: 0 resources found across 0 providers\n")
        return 0

    # Dry-run: show scan plan and exit
    if args.dry_run:
        return _print_dry_run(providers, audit_logger)

    # Create and run orchestrator
    scan_start = datetime.now()
    progress_tracker = ProgressTracker()
    rate_limiter = RateLimiter()

    orchestrator = DiscoveryOrchestrator(
        providers=providers,
        checkpoint_engine=checkpoint_engine,
        progress_tracker=progress_tracker,
        rate_limiter=rate_limiter,
    )

    resources, errors = orchestrator.run(resumed_checkpoint=resumed_checkpoint)

    # === Counting Pipeline ===
    # Step 1: ENI folding -- mark attached ENIs before categorization
    fold_enis_into_parents(resources)

    # Step 2: Tag-based exclusion of EKS-managed nodes etc.
    exclude_managed_service_resources(resources)

    # Step 3: Cross-account dedup of RAM-shared resources
    deduplicate_assets(resources)

    # Step 4: Categorize resources as DDI/IP/Asset/excluded
    categorize_resources(resources)

    # Step 5: Per-VPC IP deduplication
    ip_counts = deduplicate_ips_per_vpc(resources)

    # Step 6: Build per-account token summaries
    account_summaries: dict[str, dict] = {}
    resources_by_account: dict[str, list] = defaultdict(list)
    for resource in resources:
        resources_by_account[resource.account_id].append(resource)

    per_account_ips = ip_counts.get("per_account", {})
    for acct_id, acct_resources in resources_by_account.items():
        deduped_ip_count = per_account_ips.get(acct_id, 0)
        account_summaries[acct_id] = calculate_account_tokens(
            acct_resources, deduplicated_ip_count=deduped_ip_count
        )

    # Step 7: Provider-level aggregation
    provider_totals = calculate_provider_tokens(account_summaries)

    scan_end = datetime.now()
    scan_duration = (scan_end - scan_start).total_seconds()

    # === Output Generation ===
    if resources:
        output_dir = args.output_dir
        os.makedirs(output_dir, exist_ok=True)
        timestamp = scan_id

        # Determine provider name for output files
        provider_name = "aws"
        for p in providers:
            provider_name = p.provider_name
            break  # Use first provider's name for output file naming

        xlsx_path = f"{output_dir}/{provider_name}_discovery_{timestamp}.xlsx"
        csv_path = f"{output_dir}/{provider_name}_estimator_{timestamp}.csv"
        manifest_path = f"{output_dir}/{provider_name}_proof_{timestamp}.json"

        # Convert errors to dicts for output modules
        error_dicts = []
        for error in errors:
            error_dicts.append({
                "account": error.account_id,
                "region": "",
                "resource_type": "",
                "error": error.message,
                "suggestion": error.suggestion,
            })

        write_xlsx_report(
            xlsx_path, resources, account_summaries, error_dicts, provider_name
        )
        write_estimator_csv(csv_path, account_summaries, provider_name)
        write_proof_manifest(
            manifest_path,
            resources,
            account_summaries,
            {
                "scan_timestamp": scan_start.isoformat(),
                "scan_duration_seconds": scan_duration,
            },
            provider_name,
        )

        audit_logger.info("Output files written: %s, %s, %s", xlsx_path, csv_path, manifest_path)

    # === Print Summary ===
    sys.stderr.write(f"\n{'=' * 60}\n")
    sys.stderr.write("Scan Summary\n")
    sys.stderr.write(f"{'=' * 60}\n")
    sys.stderr.write(f"Resources discovered: {len(resources)}\n")

    # Category breakdown
    ddi_count = sum(1 for r in resources if r.counted and r.category == "ddi")
    asset_count = sum(1 for r in resources if r.counted and r.category == "asset")
    skipped_count = sum(1 for r in resources if not r.counted)
    sys.stderr.write(f"  DDI objects:    {ddi_count}\n")
    sys.stderr.write(f"  Active IPs:     {ip_counts.get('total_unique_ips', 0)}\n")
    sys.stderr.write(f"  Managed assets: {asset_count}\n")
    sys.stderr.write(f"  Skipped:        {skipped_count}\n")

    # Token totals
    sys.stderr.write(f"\nToken estimate: {provider_totals.get('total_tokens', 0)} tokens\n")

    if errors:
        sys.stderr.write(f"\nErrors encountered: {len(errors)}\n")
        for error in errors:
            sys.stderr.write(f"  {error.provider} {error.account_id}: {error.message}\n")
            if error.suggestion:
                sys.stderr.write(f"    Fix: {error.suggestion}\n")

    if resources:
        sys.stderr.write(f"\nOutput files:\n")
        sys.stderr.write(f"  XLS:      {xlsx_path}\n")
        sys.stderr.write(f"  CSV:      {csv_path}\n")
        sys.stderr.write(f"  Manifest: {manifest_path}\n")

    sys.stderr.write(f"Output directory: {args.output_dir}\n")

    audit_logger.info(
        "Scan complete: %d resources, %d errors, %d tokens",
        len(resources),
        len(errors),
        provider_totals.get("total_tokens", 0),
    )

    return 0


def _parse_account_list(value: str | None) -> list[str] | None:
    """Parse a comma-separated account list into a list of stripped strings.

    Args:
        value: Comma-separated string or None.

    Returns:
        List of account ID strings, or None if input is None.
    """
    if value is None:
        return None
    return [a.strip() for a in value.split(",") if a.strip()]


def _get_auth_validators(
    selected: list[str], args: argparse.Namespace
) -> dict:
    """Build auth validators dict for the selected providers.

    Args:
        selected: List of selected provider names.
        args: Parsed CLI arguments.

    Returns:
        Dict mapping provider name to AuthValidator instance.
    """
    from cloud_usage.providers.aws.auth import AWSAuthValidator
    from cloud_usage.providers.azure.auth import AzureAuthValidator
    from cloud_usage.providers.gcp.auth import GCPAuthValidator

    validators: dict = {}
    if "aws" in selected:
        validators["aws"] = AWSAuthValidator(profile=args.profile)
    if "azure" in selected:
        validators["azure"] = AzureAuthValidator()
    if "gcp" in selected:
        validators["gcp"] = GCPAuthValidator()
    return validators


def _get_discovery_providers(selected: list[str], args: argparse.Namespace) -> list:
    """Get discovery provider instances for selected providers.

    Creates and returns concrete DiscoveryProvider instances for each
    selected cloud platform.

    Args:
        selected: List of selected provider names.
        args: Parsed CLI arguments.

    Returns:
        List of DiscoveryProvider instances.
    """
    import boto3

    from cloud_usage.providers.aws.provider import AWSDiscoveryProvider
    from cloud_usage.providers.azure.provider import AzureDiscoveryProvider
    from cloud_usage.providers.azure.subscriptions import list_subscriptions

    providers: list = []

    if "aws" in selected:
        session = boto3.Session(profile_name=args.profile)
        include = _parse_account_list(args.include_accounts)
        exclude = _parse_account_list(args.exclude_accounts)
        providers.append(
            AWSDiscoveryProvider(
                session=session,
                role_name=args.role_name,
                include_accounts=include,
                exclude_accounts=exclude,
            )
        )

    if "azure" in selected:
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        subscriptions = list_subscriptions(credential)

        # Pre-scan display: show tenant ID and subscription count
        if subscriptions:
            tenant_id = subscriptions[0].get("tenant_id", "unknown")
            sys.stderr.write(
                f"\nAzure: Tenant {tenant_id}, "
                f"{len(subscriptions)} enabled subscription(s)\n"
            )

        include_subs = _parse_account_list(args.include_subscriptions)
        exclude_subs = _parse_account_list(args.exclude_subscriptions)
        providers.append(
            AzureDiscoveryProvider(
                credential=credential,
                subscriptions=subscriptions,
                include_subscriptions=include_subs,
                exclude_subscriptions=exclude_subs,
            )
        )

    if "gcp" in selected:
        from google.auth import default as gcp_default

        from cloud_usage.providers.gcp.client_factory import create_shared_clients
        from cloud_usage.providers.gcp.projects import enumerate_gcp_projects
        from cloud_usage.providers.gcp.provider import GCPDiscoveryProvider

        credentials, adc_project = gcp_default()
        include_proj = _parse_account_list(args.include_projects)
        exclude_proj = _parse_account_list(args.exclude_projects)

        projects = enumerate_gcp_projects(
            credentials,
            adc_project,
            args.project,
            args.org_id,
            include_proj,
            exclude_proj,
        )

        # Pre-scan display: show project count and org-id (if scoped)
        org_display = f", org: {args.org_id}" if args.org_id else ""
        sys.stderr.write(
            f"\nGCP: {len(projects)} project(s){org_display}\n"
        )

        shared_clients = create_shared_clients(credentials)
        providers.append(
            GCPDiscoveryProvider(
                credentials=credentials,
                projects=projects,
                shared_clients=shared_clients,
                include_projects=include_proj,
                exclude_projects=exclude_proj,
            )
        )

    return providers


def _print_dry_run(providers: list, audit_logger) -> int:
    """Print scan plan without making discovery API calls.

    Shows the accounts, regions, and resource types that would be scanned
    for each provider.

    Args:
        providers: List of DiscoveryProvider instances.
        audit_logger: Audit logger for recording the dry-run.

    Returns:
        Exit code 0.
    """
    from cloud_usage.providers.aws.regions import get_enabled_regions

    sys.stderr.write(f"\n{'=' * 60}\n")
    sys.stderr.write("DRY RUN - Scan Plan\n")
    sys.stderr.write(f"{'=' * 60}\n\n")

    resource_types = [
        "vpc", "subnet", "eni", "elastic-ip", "nat-gateway", "vpn-gateway",
        "transit-gateway", "dhcp-option-set", "route53-zone", "route53-record",
        "ec2-instance", "ecs-task", "eks-nodegroup", "lambda-function",
        "alb", "nlb", "classic-elb", "rds-instance", "elasticache-cluster",
        "redshift-cluster", "ebs-volume", "s3-bucket",
    ]

    for provider in providers:
        provider_name = provider.provider_name.upper()
        sys.stderr.write(f"Provider: {provider_name}\n")

        try:
            accounts = provider.list_accounts()
            sys.stderr.write(f"  Accounts ({len(accounts)}):\n")
            for acct in accounts:
                sys.stderr.write(f"    - {acct}\n")

            # Show regions for the first account (regions are typically same)
            if accounts and hasattr(provider, "_session"):
                regions = get_enabled_regions(provider._session)
                sys.stderr.write(f"  Regions ({len(regions)}):\n")
                for region in regions:
                    sys.stderr.write(f"    - {region}\n")

            sys.stderr.write(f"  Resource types ({len(resource_types)}):\n")
            for rt in resource_types:
                sys.stderr.write(f"    - {rt}\n")
        except Exception as exc:
            sys.stderr.write(f"  Error listing accounts: {exc}\n")

        sys.stderr.write("\n")

    audit_logger.info("Dry run completed")
    sys.stderr.write("Dry run complete. No discovery API calls were made.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
