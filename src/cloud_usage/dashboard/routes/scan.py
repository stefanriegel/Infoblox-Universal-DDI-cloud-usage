"""Scan wizard and lifecycle routes for the dashboard.

Implements the 4-step scan wizard (auth check, provider selection,
account selection, review & start) and scan lifecycle management
(start, cancel). All blocking cloud SDK calls run in background
threads via asyncio.to_thread() to avoid blocking the async event loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from cloud_usage.dashboard.services.scan_manager import (
    DashboardProgressTracker,
    ScanConfig,
    ScanState,
)

if TYPE_CHECKING:
    from cloud_usage.dashboard.services.scan_manager import ScanManager

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_wizard_step_context(current_step: int) -> dict:
    """Build wizard step indicator context.

    Args:
        current_step: Current step number (1-4).

    Returns:
        Dict with step info for the step indicator template fragment.
    """
    steps = [
        {"number": 1, "label": "Auth Check"},
        {"number": 2, "label": "Providers"},
        {"number": 3, "label": "Accounts"},
        {"number": 4, "label": "Review"},
    ]
    for s in steps:
        if s["number"] < current_step:
            s["state"] = "completed"
        elif s["number"] == current_step:
            s["state"] = "active"
        else:
            s["state"] = ""
    return {"steps": steps, "current_step": current_step}


def _get_auth_validators(providers: list[str]) -> dict:
    """Build auth validators dict for given provider names.

    Args:
        providers: Provider name list (e.g., ["aws", "azure", "gcp"]).

    Returns:
        Dict mapping provider name to AuthValidator instance.
        Skips providers whose SDK is not installed.
    """
    validators: dict = {}

    if "aws" in providers:
        try:
            from cloud_usage.providers.aws.auth import AWSAuthValidator
            validators["aws"] = AWSAuthValidator()
        except ImportError:
            pass

    if "azure" in providers:
        try:
            from cloud_usage.providers.azure.auth import AzureAuthValidator
            validators["azure"] = AzureAuthValidator()
        except ImportError:
            pass

    if "gcp" in providers:
        try:
            from cloud_usage.providers.gcp.auth import GCPAuthValidator
            validators["gcp"] = GCPAuthValidator()
        except ImportError:
            pass

    return validators


def _run_auth_check() -> list[dict]:
    """Run auth check for all providers. Blocking -- call via to_thread.

    Returns:
        List of dicts with provider, success, identity, account_count,
        error_message, suggestion fields.
    """
    from cloud_usage.auth.doctor import AuthDoctor

    all_providers = ["aws", "azure", "gcp"]
    validators = _get_auth_validators(all_providers)
    doctor = AuthDoctor(validators=validators)
    results = doctor.check_all(all_providers)

    return [
        {
            "provider": r.provider,
            "success": r.success,
            "identity": r.identity,
            "account_count": r.account_count,
            "error_message": r.error_message,
            "suggestion": r.suggestion,
        }
        for r in results
    ]


def _enumerate_accounts(providers: list[str]) -> dict[str, dict]:
    """Enumerate accounts/subscriptions/projects per provider. Blocking.

    Args:
        providers: List of provider names to enumerate.

    Returns:
        Dict mapping provider -> {"accounts": list[{id, display_name}], "error": str | None}.
        On success, "accounts" contains the list and "error" is None.
        On failure, "accounts" is empty and "error" contains the exception message.
    """
    accounts: dict[str, dict] = {}

    if "aws" in providers:
        try:
            import boto3
            from cloud_usage.providers.aws.provider import AWSDiscoveryProvider

            session = boto3.Session()
            provider = AWSDiscoveryProvider(session=session)
            acct_ids = provider.list_accounts()
            accounts["aws"] = {
                "accounts": [
                    {"id": a, "display_name": f"Account {a}"}
                    for a in acct_ids
                ],
                "error": None,
            }
        except Exception as exc:
            logger.warning("Failed to enumerate AWS accounts: %s", exc)
            accounts["aws"] = {"accounts": [], "error": str(exc)}

    if "azure" in providers:
        try:
            from azure.identity import DefaultAzureCredential
            from cloud_usage.providers.azure.subscriptions import list_subscriptions

            credential = DefaultAzureCredential()
            subs = list_subscriptions(credential)
            accounts["azure"] = {
                "accounts": [
                    {
                        "id": s.get("id", ""),
                        "display_name": s.get("display_name") or s.get("id", ""),
                    }
                    for s in subs
                ],
                "error": None,
            }
        except Exception as exc:
            logger.warning("Failed to enumerate Azure subscriptions: %s", exc)
            accounts["azure"] = {"accounts": [], "error": str(exc)}

    if "gcp" in providers:
        try:
            from google.auth import default as gcp_default
            from cloud_usage.providers.gcp.projects import enumerate_gcp_projects

            credentials, adc_project = gcp_default()
            projects = enumerate_gcp_projects(credentials, adc_project, None, None, None, None)
            accounts["gcp"] = {
                "accounts": [
                    {"id": p.project_id, "display_name": f"Project {p.project_id}"}
                    for p in projects
                ],
                "error": None,
            }
        except Exception as exc:
            logger.warning("Failed to enumerate GCP projects: %s", exc)
            accounts["gcp"] = {"accounts": [], "error": str(exc)}

    return accounts


def _run_scan_pipeline(
    scan_manager: ScanManager,
    config: ScanConfig,
    event_bridge: object,
) -> None:
    """Run the full scan pipeline in a background thread.

    This function blocks and should be called via run_in_executor or
    asyncio.to_thread. Sets scan_manager state to RUNNING on entry,
    COMPLETE on success, or ERROR on exception.

    Args:
        scan_manager: The ScanManager instance for state/result storage.
        config: Scan configuration with providers and account filters.
        event_bridge: The EventBridge for SSE progress events.
    """
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

    try:
        scan_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = "./output"
        os.makedirs(output_dir, exist_ok=True)

        checkpoint_engine = CheckpointEngine(
            checkpoint_dir=f"{output_dir}/.checkpoints",
            ttl_hours=48,
        )

        # Build discovery providers (checkpoint_engine threaded in for resume support)
        providers = _build_discovery_providers(config, checkpoint_engine)
        if not providers:
            scan_manager.set_state(ScanState.COMPLETE)
            return

        audit_logger = setup_audit_logger(output_dir, scan_id=scan_id)
        audit_logger.info(
            "Dashboard scan started with providers: %s",
            ", ".join(config.providers),
        )

        # Create progress tracker bridged to SSE
        progress_tracker = DashboardProgressTracker(event_bridge)

        # Store progress_data reference on scan_manager for tab rendering
        scan_manager._progress_data = {}

        # Wrap complete_account to also update scan_manager progress data
        _orig_complete = progress_tracker.complete_account

        def _tracked_complete(provider: str, resources_found: int) -> None:
            _orig_complete(provider, resources_found)
            summary = progress_tracker.get_summary()
            state = summary.get(provider)
            if state:
                scan_manager._progress_data[provider.lower()] = {
                    "provider": provider,
                    "completed": state.completed,
                    "total": state.total,
                    "resources": state.resources,
                    "unit_label": state.unit_label,
                    "status": "running",
                    "has_errors": False,
                }

        progress_tracker.complete_account = _tracked_complete

        rate_limiter = RateLimiter()

        orchestrator = DiscoveryOrchestrator(
            providers=providers,
            checkpoint_engine=checkpoint_engine,
            progress_tracker=progress_tracker,
            rate_limiter=rate_limiter,
        )

        # Check for cancellation before starting
        if scan_manager.state != ScanState.RUNNING:
            return

        resources, errors = orchestrator.run()

        # Check for cancellation after discovery
        if scan_manager.state == ScanState.CANCELLED:
            scan_manager.set_resources(resources)
            scan_manager.set_errors(errors)
            return

        # === Counting Pipeline ===
        fold_enis_into_parents(resources)
        exclude_managed_service_resources(resources)
        deduplicate_assets(resources)
        categorize_resources(resources)
        ip_counts = deduplicate_ips_per_vpc(resources)

        # Per-account token calculation
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

        provider_totals = calculate_provider_tokens(account_summaries)

        # Store results in scan_manager
        scan_manager.set_resources(resources)
        scan_manager.set_errors(errors)

        # Generate output files
        output_paths: dict[str, str] = {}
        if resources:
            timestamp = scan_id
            for p in providers:
                provider_name = p.provider_name
                xlsx_path = f"{output_dir}/{provider_name}_discovery_{timestamp}.xlsx"
                csv_path = f"{output_dir}/{provider_name}_estimator_{timestamp}.csv"
                manifest_path = f"{output_dir}/{provider_name}_proof_{timestamp}.json"

                error_dicts = [
                    {
                        "account": e.account_id,
                        "region": "",
                        "resource_type": "",
                        "error": e.message,
                        "suggestion": e.suggestion,
                    }
                    for e in errors
                    if e.provider == provider_name
                ]

                write_xlsx_report(
                    xlsx_path, resources, account_summaries, error_dicts, provider_name
                )
                write_estimator_csv(csv_path, account_summaries, provider_name)
                write_proof_manifest(
                    manifest_path,
                    resources,
                    account_summaries,
                    {
                        "scan_timestamp": datetime.now().isoformat(),
                        "scan_duration_seconds": 0,
                    },
                    provider_name,
                )

                output_paths[f"{provider_name}_xlsx"] = xlsx_path
                output_paths[f"{provider_name}_csv"] = csv_path
                output_paths[f"{provider_name}_manifest"] = manifest_path

        scan_manager.set_output_paths(output_paths)

        # Mark progress rows as complete
        for key in scan_manager._progress_data:
            scan_manager._progress_data[key]["status"] = "complete"

        scan_manager.set_state(ScanState.COMPLETE)

        audit_logger.info(
            "Dashboard scan complete: %d resources, %d errors, %d tokens",
            len(resources),
            len(errors),
            provider_totals.get("total_tokens", 0),
        )

    except Exception as exc:
        logger.exception("Scan pipeline failed: %s", exc)
        scan_manager.set_state(ScanState.ERROR)

    finally:
        # Always signal SSE completion
        try:
            event_bridge.emit_done()
        except Exception:
            pass


def _build_discovery_providers(config: ScanConfig, checkpoint_engine=None) -> list:
    """Build discovery provider instances from scan config.

    The checkpoint_engine is threaded into Azure and GCP provider constructors
    so that per-subscription and per-project resume is functional.

    Args:
        config: Scan configuration with providers and filters.
        checkpoint_engine: CheckpointEngine for per-account resume, or None.

    Returns:
        List of DiscoveryProvider instances.
    """
    providers: list = []

    if "aws" in config.providers:
        try:
            import boto3
            from cloud_usage.providers.aws.provider import AWSDiscoveryProvider

            session = boto3.Session()
            include = config.include_accounts.get("aws")
            exclude = config.exclude_accounts.get("aws")
            providers.append(
                AWSDiscoveryProvider(
                    session=session,
                    include_accounts=include,
                    exclude_accounts=exclude,
                    checkpoint_engine=checkpoint_engine,
                )
            )
        except ImportError:
            logger.warning("AWS SDK not available, skipping AWS provider")

    if "azure" in config.providers:
        try:
            from azure.identity import DefaultAzureCredential
            from cloud_usage.providers.azure.provider import AzureDiscoveryProvider
            from cloud_usage.providers.azure.subscriptions import list_subscriptions

            credential = DefaultAzureCredential()
            subscriptions = list_subscriptions(credential)
            include = config.include_accounts.get("azure")
            exclude = config.exclude_accounts.get("azure")
            providers.append(
                AzureDiscoveryProvider(
                    credential=credential,
                    subscriptions=subscriptions,
                    include_subscriptions=include,
                    exclude_subscriptions=exclude,
                    checkpoint_engine=checkpoint_engine,
                )
            )
        except ImportError:
            logger.warning("Azure SDK not available, skipping Azure provider")

    if "gcp" in config.providers:
        try:
            from google.auth import default as gcp_default
            from cloud_usage.providers.gcp.client_factory import create_shared_clients
            from cloud_usage.providers.gcp.projects import enumerate_gcp_projects
            from cloud_usage.providers.gcp.provider import GCPDiscoveryProvider

            credentials, adc_project = gcp_default()
            include = config.include_accounts.get("gcp")
            exclude = config.exclude_accounts.get("gcp")
            projects = enumerate_gcp_projects(
                credentials, adc_project, None, None, include, exclude,
            )
            shared_clients = create_shared_clients(credentials)
            providers.append(
                GCPDiscoveryProvider(
                    credentials=credentials,
                    projects=projects,
                    shared_clients=shared_clients,
                    include_projects=include,
                    exclude_projects=exclude,
                    checkpoint_engine=checkpoint_engine,
                )
            )
        except ImportError:
            logger.warning("GCP SDK not available, skipping GCP provider")

    return providers


# -- Wizard Routes --


@router.get("/wizard", response_class=HTMLResponse)
async def wizard(request: Request) -> HTMLResponse:
    """Render the wizard container with step 1 auth check auto-triggered.

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered wizard container HTML.
    """
    templates = request.app.state.templates
    scan_manager = request.app.state.scan_manager

    # Load saved config for defaults
    saved_config = scan_manager.load_scan_config()

    step_ctx = _get_wizard_step_context(1)
    return templates.TemplateResponse(
        request,
        "partials/wizard/step1_auth.html",
        {
            "request": request,
            **step_ctx,
            "auth_results": None,
            "checking": True,
            "saved_config": saved_config,
        },
    )


@router.post("/wizard/auth-check", response_class=HTMLResponse)
async def wizard_auth_check(request: Request) -> HTMLResponse:
    """Run auth check for all providers and return step 1 results.

    Runs AuthDoctor.check_all() in a thread to avoid blocking async loop.

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered step1_auth.html with per-provider pass/fail results.
    """
    auth_results = await asyncio.to_thread(_run_auth_check)

    templates = request.app.state.templates
    step_ctx = _get_wizard_step_context(1)
    has_passing = any(r["success"] for r in auth_results)

    return templates.TemplateResponse(
        request,
        "partials/wizard/step1_auth.html",
        {
            "request": request,
            **step_ctx,
            "auth_results": auth_results,
            "checking": False,
            "has_passing": has_passing,
        },
    )


def _list_aws_profiles() -> list[str]:
    """Return named profiles found in ~/.aws/config (excluding [default]).

    Reads the AWS config file using configparser.  Only returns profile names
    that appear as ``[profile <name>]`` sections -- not ``[default]``.

    Returns:
        Sorted list of profile name strings.  Empty list if the file does not
        exist or cannot be read.
    """
    import configparser
    import pathlib

    config_path = pathlib.Path.home() / ".aws" / "config"
    if not config_path.exists():
        return []

    parser = configparser.ConfigParser()
    try:
        parser.read(config_path)
    except Exception:
        return []

    profiles: list[str] = []
    for section in parser.sections():
        # AWS config file sections look like "profile my-profile" for named profiles
        if section.startswith("profile "):
            name = section[len("profile "):]
            if name:
                profiles.append(name)

    return sorted(profiles)


@router.get("/wizard/setup-credentials", response_class=HTMLResponse)
async def wizard_setup_credentials_get(request: Request) -> HTMLResponse:
    """Show the credential setup assistant (step 1 sub-page).

    Displayed when no cloud providers are authenticated and the user clicks
    "Connect a cloud provider" or a per-provider "Connect" button in step 1.
    Renders a form with per-provider credential fields and all auth methods
    supported by the codebase (no CLI knowledge required).

    Query params:
        cloud: Optional provider to pre-select (``aws``, ``azure``, ``gcp``).
               When provided, the wizard opens scoped to that cloud with its
               section expanded and only that provider's checkbox pre-ticked.

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered step1_setup.html with cloud context and available auth methods.
    """
    cloud = request.query_params.get("cloud", "")
    # Validate to prevent injection; accept only known provider names
    if cloud not in ("aws", "azure", "gcp", ""):
        cloud = ""

    # Pre-select the scoped cloud (or all three if no cloud specified)
    if cloud:
        selected_clouds = [cloud]
    else:
        selected_clouds = []

    # Enumerate available AWS profiles for the profile-selector method
    aws_profiles = await asyncio.to_thread(_list_aws_profiles)

    templates = request.app.state.templates
    step_ctx = _get_wizard_step_context(1)
    return templates.TemplateResponse(
        request,
        "partials/wizard/step1_setup.html",
        {
            "request": request,
            **step_ctx,
            "selected_cloud": cloud,
            "selected_clouds": selected_clouds,
            "aws_profiles": aws_profiles,
            "error": None,
            "saved": [],
        },
    )


def _save_credentials(form_data: dict) -> tuple[list[str], str | None]:
    """Write provider credentials to standard local config locations.

    Writes only for providers included in ``form_data["clouds"]``.  Each
    provider's section is written independently so a partial failure leaves
    the successfully-written providers usable.

    Credential storage locations:
    - AWS: ``~/.aws/credentials`` ([default] section, access key + secret)
    - Azure: ``~/.cloud-usage-azure.env`` (shell-sourced env file) +
             sets ``AZURE_CLIENT_ID`` / ``AZURE_CLIENT_SECRET`` /
             ``AZURE_TENANT_ID`` in the running process environment so
             the subsequent auth-check call picks them up immediately.
    - GCP: ``~/.config/gcloud/application_default_credentials.json``
           (Application Default Credentials) + sets
           ``GOOGLE_APPLICATION_CREDENTIALS`` in the running process.

    Args:
        form_data: Dict derived from the POST form.  Must include a
            ``"clouds"`` key whose value is a list of selected provider
            names (``"aws"``, ``"azure"``, ``"gcp"``).

    Returns:
        Tuple of ``(saved, error_message)``.
        ``saved`` is the list of provider names whose credentials were
        written successfully.  ``error_message`` is a human-readable
        description of the first failure encountered, or ``None`` if all
        selected providers were saved without errors.
    """
    import configparser
    import json
    import pathlib

    clouds: list[str] = form_data.get("clouds", [])
    if isinstance(clouds, str):
        clouds = [clouds]

    saved: list[str] = []
    error: str | None = None

    # -- AWS --
    if "aws" in clouds:
        auth_method = (form_data.get("aws_auth_method") or "access_key").strip()

        if auth_method == "profile":
            # Profile-based auth: write AWS_PROFILE env var so the running process
            # and subsequent boto3 calls pick up the named profile immediately.
            profile_name = (form_data.get("aws_profile_name") or "").strip()
            if profile_name:
                try:
                    os.environ["AWS_PROFILE"] = profile_name
                    # Persist the choice to a small marker file so it survives
                    # process restarts (read by preflight on next startup).
                    profile_marker = pathlib.Path.home() / ".cloud-usage-aws-profile"
                    profile_marker.write_text(profile_name, encoding="utf-8")
                    saved.append("aws")
                except Exception as exc:
                    error = f"AWS: {exc}"
            # If no profile name provided, skip silently

        else:
            # Access key auth (default)
            access_key = (form_data.get("aws_access_key_id") or "").strip()
            secret_key = (form_data.get("aws_secret_access_key") or "").strip()
            region = (form_data.get("aws_region") or "").strip()
            if access_key and secret_key:
                try:
                    creds_path = pathlib.Path.home() / ".aws" / "credentials"
                    creds_path.parent.mkdir(parents=True, exist_ok=True)
                    parser = configparser.ConfigParser()
                    if creds_path.exists():
                        parser.read(creds_path)
                    if not parser.has_section("default"):
                        parser.add_section("default")
                    parser.set("default", "aws_access_key_id", access_key)
                    parser.set("default", "aws_secret_access_key", secret_key)
                    if region:
                        parser.set("default", "region", region)
                    with creds_path.open("w") as fh:
                        parser.write(fh)
                    saved.append("aws")
                except Exception as exc:
                    error = f"AWS: {exc}"
            # If fields are empty, skip silently (user left AWS unchecked or blank)

    # -- Azure --
    if "azure" in clouds:
        client_id = (form_data.get("azure_client_id") or "").strip()
        client_secret = (form_data.get("azure_client_secret") or "").strip()
        tenant_id = (form_data.get("azure_tenant_id") or "").strip()
        if client_id and client_secret and tenant_id:
            try:
                env_path = pathlib.Path.home() / ".cloud-usage-azure.env"
                env_path.write_text(
                    f"AZURE_CLIENT_ID={client_id}\n"
                    f"AZURE_TENANT_ID={tenant_id}\n"
                    f"AZURE_CLIENT_SECRET={client_secret}\n",
                    encoding="utf-8",
                )
                # Apply to running process so next auth-check call works immediately
                os.environ["AZURE_CLIENT_ID"] = client_id
                os.environ["AZURE_TENANT_ID"] = tenant_id
                os.environ["AZURE_CLIENT_SECRET"] = client_secret
                saved.append("azure")
            except Exception as exc:
                if error is None:
                    error = f"Azure: {exc}"

    # -- GCP --
    if "gcp" in clouds:
        json_text = (form_data.get("gcp_service_account_json") or "").strip()
        if json_text:
            try:
                # Validate JSON before writing
                json.loads(json_text)
                adc_path = (
                    pathlib.Path.home()
                    / ".config"
                    / "gcloud"
                    / "application_default_credentials.json"
                )
                adc_path.parent.mkdir(parents=True, exist_ok=True)
                adc_path.write_text(json_text, encoding="utf-8")
                # Also point GOOGLE_APPLICATION_CREDENTIALS so the validator
                # finds the file without relying on gcloud SDK paths
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(adc_path)
                saved.append("gcp")
            except json.JSONDecodeError as exc:
                if error is None:
                    error = f"GCP: Invalid JSON — {exc}"
            except Exception as exc:
                if error is None:
                    error = f"GCP: {exc}"

    return saved, error


@router.post("/wizard/setup-credentials", response_class=HTMLResponse)
async def wizard_setup_credentials_post(request: Request) -> HTMLResponse:
    """Accept and save cloud credentials entered via the setup assistant.

    Writes credentials to standard local config locations so the subsequent
    auth-check call can pick them up without any CLI commands.

    On success, renders the setup page with a success banner directing the
    user to click "Back to Auth Check".  On failure, renders the page again
    with an error message and the previously-selected cloud checkboxes
    pre-ticked.

    Args:
        request: The incoming HTTP request with form data.

    Returns:
        Rendered step1_setup.html with save outcome feedback.
    """
    form = await request.form()
    form_data: dict = dict(form)
    # Multi-value "clouds" field
    form_data["clouds"] = form.getlist("clouds")

    # Preserve the scoped cloud context so the template re-renders correctly
    selected_cloud = (form_data.get("selected_cloud") or "").strip()
    if selected_cloud not in ("aws", "azure", "gcp", ""):
        selected_cloud = ""

    saved, error = await asyncio.to_thread(_save_credentials, form_data)

    # Re-enumerate AWS profiles in case the user just set up a profile
    aws_profiles = await asyncio.to_thread(_list_aws_profiles)

    templates = request.app.state.templates
    step_ctx = _get_wizard_step_context(1)
    return templates.TemplateResponse(
        request,
        "partials/wizard/step1_setup.html",
        {
            "request": request,
            **step_ctx,
            "selected_cloud": selected_cloud,
            "selected_clouds": form_data["clouds"],
            "aws_profiles": aws_profiles,
            "error": error,
            "saved": saved,
        },
    )


@router.post("/wizard/providers", response_class=HTMLResponse)
async def wizard_providers(request: Request) -> HTMLResponse:
    """Accept auth results and show provider selection (step 2).

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered step2_providers.html with authenticated providers.
    """
    form = await request.form()

    # Collect authenticated providers passed from step 1
    authenticated_providers = []
    for p in ["aws", "azure", "gcp"]:
        if form.get(f"auth_{p}") == "true":
            authenticated_providers.append(p)

    # Load saved config for defaults
    scan_manager = request.app.state.scan_manager
    saved_config = scan_manager.load_scan_config()
    saved_providers = saved_config.providers if saved_config else []

    templates = request.app.state.templates
    step_ctx = _get_wizard_step_context(2)

    return templates.TemplateResponse(
        request,
        "partials/wizard/step2_providers.html",
        {
            "request": request,
            **step_ctx,
            "authenticated_providers": authenticated_providers,
            "saved_providers": saved_providers,
        },
    )


@router.post("/wizard/accounts", response_class=HTMLResponse)
async def wizard_accounts(request: Request) -> HTMLResponse:
    """Accept selected providers and show account selection (step 3).

    Enumerates accounts per provider in a background thread.

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered step3_accounts.html with per-provider account lists.
    """
    form = await request.form()

    selected_providers = form.getlist("providers")
    if not selected_providers:
        # Fallback: check individual fields
        for p in ["aws", "azure", "gcp"]:
            if form.get(f"provider_{p}"):
                selected_providers.append(p)

    # Enumerate accounts in background thread
    accounts = await asyncio.to_thread(_enumerate_accounts, selected_providers)

    # Load saved config for pre-selection
    scan_manager = request.app.state.scan_manager
    saved_config = scan_manager.load_scan_config()
    saved_includes = saved_config.include_accounts if saved_config else {}

    templates = request.app.state.templates
    step_ctx = _get_wizard_step_context(3)

    return templates.TemplateResponse(
        request,
        "partials/wizard/step3_accounts.html",
        {
            "request": request,
            **step_ctx,
            "selected_providers": selected_providers,
            "accounts": accounts,
            "saved_includes": saved_includes,
        },
    )


@router.get("/wizard/filter-accounts", response_class=HTMLResponse)
async def wizard_filter_accounts(request: Request) -> HTMLResponse:
    """Filter account list by search query for HTMX swap.

    Query params:
        provider: Provider name (aws, azure, gcp).
        q: Search query string.

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered account checkbox list fragment filtered by query.
    """
    provider = request.query_params.get("provider", "")
    query = request.query_params.get("q", "").lower()

    # Re-enumerate would be slow; use cached accounts from scan_manager
    # For simplicity, enumerate fresh (the list is small)
    if provider:
        accounts = await asyncio.to_thread(_enumerate_accounts, [provider])
        provider_accounts = accounts.get(provider, {}).get("accounts", [])
    else:
        provider_accounts = []

    if query:
        provider_accounts = [
            a for a in provider_accounts
            if query in a["id"].lower() or query in a["display_name"].lower()
        ]

    # Return just the checkbox list HTML
    html_parts = []
    for acct in provider_accounts:
        checked = "checked"
        html_parts.append(
            f'<label><input type="checkbox" name="accounts_{provider}" '
            f'value="{acct["id"]}" {checked}> '
            f'{acct["display_name"]} ({acct["id"]})</label>'
        )

    html = "\n".join(html_parts) if html_parts else "<p>No accounts found.</p>"
    return HTMLResponse(html)


@router.post("/wizard/review", response_class=HTMLResponse)
async def wizard_review(request: Request) -> HTMLResponse:
    """Accept selected accounts and show review step (step 4).

    Args:
        request: The incoming HTTP request.

    Returns:
        Rendered step4_review.html with scan configuration summary.
    """
    form = await request.form()

    selected_providers = form.getlist("selected_providers")
    if not selected_providers:
        for p in ["aws", "azure", "gcp"]:
            if form.getlist(f"accounts_{p}"):
                selected_providers.append(p)

    # Collect selected accounts per provider
    selected_accounts: dict[str, list[str]] = {}
    for p in selected_providers:
        accts = form.getlist(f"accounts_{p}")
        if accts:
            selected_accounts[p] = list(accts)

    templates = request.app.state.templates
    step_ctx = _get_wizard_step_context(4)

    provider_display = {"aws": "AWS", "azure": "Azure", "gcp": "GCP"}

    return templates.TemplateResponse(
        request,
        "partials/wizard/step4_review.html",
        {
            "request": request,
            **step_ctx,
            "selected_providers": selected_providers,
            "selected_accounts": selected_accounts,
            "provider_display": provider_display,
        },
    )


# -- Scan Lifecycle Routes --


@router.post("/api/scan/start")
async def scan_start(request: Request) -> JSONResponse:
    """Start a scan with the given configuration.

    Validates scan_manager.can_start() and returns 409 if already running.
    Kicks off scan pipeline in a background thread.

    Args:
        request: The incoming HTTP request.

    Returns:
        JSON response with status and redirect hint.
    """
    scan_manager = request.app.state.scan_manager
    event_bridge = request.app.state.event_bridge

    if not scan_manager.can_start():
        return JSONResponse(
            {"error": "Scan already running"},
            status_code=409,
        )

    form = await request.form()

    # Parse providers and accounts from form
    providers = form.getlist("providers")
    if not providers:
        for p in ["aws", "azure", "gcp"]:
            if form.get(f"provider_{p}"):
                providers.append(p)

    include_accounts: dict[str, list[str] | None] = {}
    for p in providers:
        accts = form.getlist(f"accounts_{p}")
        if accts:
            include_accounts[p] = list(accts)
        else:
            include_accounts[p] = None

    config = ScanConfig(
        providers=providers,
        include_accounts=include_accounts,
        exclude_accounts={},
    )

    # Save config for next time
    scan_manager.save_scan_config(config)

    # Start the scan
    scan_manager.start(config)

    # Run scan pipeline in background thread
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _run_scan_pipeline, scan_manager, config, event_bridge)

    return JSONResponse({"status": "started", "redirect": "/tab/progress"})


@router.post("/api/scan/cancel")
async def scan_cancel(request: Request) -> JSONResponse:
    """Cancel a running scan.

    Sets scan_manager state to CANCELLED and signals scan_complete
    via event_bridge for SSE stream termination.

    Args:
        request: The incoming HTTP request.

    Returns:
        JSON response confirming cancellation.
    """
    scan_manager = request.app.state.scan_manager
    event_bridge = request.app.state.event_bridge

    if scan_manager.state != ScanState.RUNNING:
        return JSONResponse(
            {"status": "not_running"},
            status_code=200,
        )

    scan_manager.cancel()

    return JSONResponse({"status": "cancelled"})
