"""GCP discovery provider implementing the DiscoveryProvider ABC.

Connects to the Phase 1 orchestrator by implementing list_accounts()
and discover_account(). Supports project filtering by glob patterns,
checkpoint-based resume for completed projects, and GCP-specific error
detection for PermissionDenied, TooManyRequests, and API disabled errors.
"""

from __future__ import annotations

import fnmatch
import logging
import sys

from cloud_usage.discovery.provider import DiscoveryProvider
from cloud_usage.providers.gcp.client_factory import GCPClients
from cloud_usage.providers.gcp.projects import ProjectInfo
from cloud_usage.schema.resource import CloudResource

logger = logging.getLogger(__name__)


class GCPDiscoveryProvider(DiscoveryProvider):
    """GCP implementation of the discovery provider interface.

    Lists projects with include/exclude glob filtering, discovers
    resources within each project using GCP SDK clients, and
    integrates with checkpoint engine for resume support.

    Args:
        credentials: GCP credential object from google.auth.default().
        projects: List of ProjectInfo from enumerate_gcp_projects().
        shared_clients: GCPClients with shared SDK clients.
        include_projects: Glob patterns to include (takes precedence).
        exclude_projects: Glob patterns to exclude.
        checkpoint_engine: Optional checkpoint engine for resume support.
    """

    def __init__(
        self,
        credentials,
        projects: list[ProjectInfo],
        shared_clients: GCPClients,
        include_projects: list[str] | None = None,
        exclude_projects: list[str] | None = None,
        checkpoint_engine=None,
    ) -> None:
        self._credentials = credentials
        self._projects = projects
        self._shared_clients = shared_clients
        self._include = include_projects
        self._exclude = exclude_projects
        self._checkpoint_engine = checkpoint_engine

        # Build id -> ProjectInfo mapping for quick lookup
        self._project_info: dict[str, ProjectInfo] = {
            p.project_id: p for p in projects
        }

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "gcp"

    def list_accounts(self) -> list[str]:
        """List filtered project IDs to scan.

        If include_projects is provided, matches by glob pattern.
        If exclude_projects is provided (and no include), excludes
        by glob pattern. Include takes precedence over exclude.

        Logs the pre-scan project summary.

        Returns:
            Filtered list of GCP project ID strings.
        """
        project_ids = [p.project_id for p in self._projects]

        # Apply filtering: include takes precedence over exclude
        if self._include is not None:
            project_ids = [
                pid for pid in project_ids
                if any(fnmatch.fnmatch(pid, pat) for pat in self._include)
            ]
        elif self._exclude is not None:
            project_ids = [
                pid for pid in project_ids
                if not any(fnmatch.fnmatch(pid, pat) for pat in self._exclude)
            ]

        # Log pre-scan summary
        for pid in project_ids:
            logger.info("Project to scan: %s", pid)

        return project_ids

    def discover_account(self, account_id: str) -> list[CloudResource]:
        """Discover all resources in a single GCP project.

        Skeleton implementation that returns an empty list. Plans 02-04
        will wire resource collectors into this method.

        Checkpoint integration: checks if project is already completed
        (key: "gcp:{project_id}:completed") and skips if so.

        Per Pitfall 1 from RESEARCH.md: creates a per-project DNS client
        inside this method rather than sharing one across projects.

        Args:
            account_id: GCP project ID to scan.

        Returns:
            List of discovered CloudResource instances.
        """
        # Suppress Google SDK logging
        logging.getLogger("google").setLevel(logging.ERROR)

        # Check if this project was already completed (checkpoint)
        checkpoint_key = f"gcp:{account_id}:completed"

        if self._checkpoint_engine is not None:
            existing = self._checkpoint_engine.load()
            if existing is not None:
                gcp_progress = existing.providers.get("gcp")
                if gcp_progress and account_id in gcp_progress.completed_accounts:
                    logger.info(
                        "Skipping already-completed project: %s (checkpoint key: %s)",
                        account_id,
                        checkpoint_key,
                    )
                    return []

        # Create per-project DNS client (Pitfall 1: dns.Client requires project= at init)
        _dns_client = self._create_dns_client(account_id)

        # Plans 02-04 will add collector calls here
        all_resources: list[CloudResource] = []

        logger.info(
            "Discovered %d resources in project %s",
            len(all_resources),
            account_id,
        )
        return all_resources

    def _create_dns_client(self, project_id: str):
        """Create a per-project DNS client.

        DNS client requires project= at construction time (Pitfall 1
        from RESEARCH.md), so it cannot be shared across projects.

        Args:
            project_id: GCP project ID to bind the DNS client to.

        Returns:
            google.cloud.dns.Client or None if SDK not installed.
        """
        try:
            from google.cloud import dns
            return dns.Client(project=project_id, credentials=self._credentials)
        except ImportError:
            logger.debug("google-cloud-dns not installed, DNS collection will be skipped")
            return None
        except Exception:
            logger.debug("Failed to create DNS client for %s", project_id, exc_info=True)
            return None

    @staticmethod
    def _safe_collect(
        resource_type: str,
        project_id: str,
        collector_fn,
        *args,
    ) -> list[CloudResource]:
        """Call a collector function with GCP-specific error isolation.

        Detects GCP-specific errors and logs appropriate messages:
        - PermissionDenied / Forbidden: skip with warning
        - 429 / TooManyRequests: log visible WARNING to stderr
        - API disabled ("has not been used" or "is not enabled"): log [Skip]
        - Generic: log warning with exc_info=True

        Args:
            resource_type: Human-readable resource type name for logging.
            project_id: GCP project ID being scanned.
            collector_fn: The collector function to call.
            *args: Arguments to pass to the collector function.

        Returns:
            List of discovered CloudResource instances, or empty on failure.
        """
        try:
            return collector_fn(*args)
        except Exception as exc:
            exc_msg = str(exc)
            exc_name = type(exc).__name__

            # Detect PermissionDenied or Forbidden
            if exc_name in ("PermissionDenied", "Forbidden"):
                logger.warning(
                    "Permission denied for %s in project %s. Skipping.",
                    resource_type,
                    project_id,
                )
                sys.stderr.write(
                    f"WARNING: Permission denied for {resource_type} "
                    f"in project {project_id}. Skipping.\n"
                )
                return []

            # Detect 429 / TooManyRequests
            status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if exc_name == "TooManyRequests" or status_code == 429:
                retry_after = getattr(exc, "retry_after", None)
                delay = float(retry_after) if retry_after else 30.0
                logger.warning(
                    "Project %s: throttled on %s, retrying in %.0fs",
                    project_id,
                    resource_type,
                    delay,
                )
                sys.stderr.write(
                    f"WARNING: Project {project_id}: throttled on {resource_type}, "
                    f"retrying in {delay:.0f}s\n"
                )
                return []

            # Detect API disabled
            if "has not been used" in exc_msg or "is not enabled" in exc_msg:
                logger.info(
                    "[Skip] %s: %s API not enabled in project %s",
                    project_id,
                    resource_type,
                    project_id,
                )
                sys.stderr.write(
                    f"[Skip] {project_id}: {resource_type} API not enabled\n"
                )
                return []

            # Generic failure
            logger.warning(
                "Failed to collect %s in project %s",
                resource_type,
                project_id,
                exc_info=True,
            )
            sys.stderr.write(
                f"WARNING: Failed to collect {resource_type} "
                f"in project {project_id}. Continuing.\n"
            )
            return []
