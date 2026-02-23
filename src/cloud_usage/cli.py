"""CLI entry point with interactive provider selection and scan orchestration.

Provides the main command-line interface for the cloud usage estimator.
Features interactive provider selection prompts for guided use, and
CLI flags (--aws, --azure, --gcp) for scripted/CI use. Integrates
auth doctor, checkpoint detection, and discovery orchestrator in the
correct sequence.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from cloud_usage.auth.doctor import AuthDoctor
from cloud_usage.discovery.orchestrator import DiscoveryOrchestrator
from cloud_usage.discovery.progress import ProgressTracker
from cloud_usage.logging.audit import setup_audit_logger
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
    6. Print final summary

    Args:
        argv: Argument list. Defaults to sys.argv[1:] if None.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    args = parse_args(argv)

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
    progress_tracker = ProgressTracker()
    rate_limiter = RateLimiter()

    orchestrator = DiscoveryOrchestrator(
        providers=providers,
        checkpoint_engine=checkpoint_engine,
        progress_tracker=progress_tracker,
        rate_limiter=rate_limiter,
    )

    resources, errors = orchestrator.run(resumed_checkpoint=resumed_checkpoint)

    # Print final summary
    sys.stderr.write(f"\n{'=' * 60}\n")
    sys.stderr.write("Scan Summary\n")
    sys.stderr.write(f"{'=' * 60}\n")
    sys.stderr.write(f"Resources discovered: {len(resources)}\n")
    sys.stderr.write(f"Errors encountered: {len(errors)}\n")
    sys.stderr.write(f"Output directory: {args.output_dir}\n")

    if errors:
        sys.stderr.write(f"\nFailed accounts:\n")
        for error in errors:
            sys.stderr.write(f"  {error.provider} {error.account_id}: {error.message}\n")
            if error.suggestion:
                sys.stderr.write(f"    Fix: {error.suggestion}\n")

    audit_logger.info(
        "Scan complete: %d resources, %d errors",
        len(resources),
        len(errors),
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

    validators: dict = {}
    if "aws" in selected:
        validators["aws"] = AWSAuthValidator(profile=args.profile)
    # Azure and GCP validators will be added in Phases 3-4
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

    # Azure and GCP providers will be added in Phases 3-4

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

            sys.stderr.write("  Resource types: (collectors not yet wired)\n")
        except Exception as exc:
            sys.stderr.write(f"  Error listing accounts: {exc}\n")

        sys.stderr.write("\n")

    audit_logger.info("Dry run completed")
    sys.stderr.write("Dry run complete. No discovery API calls were made.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
