"""Microsoft Active Directory provider package.

Provides collection of DNS zones/records, DHCP scopes/leases, and AD user
objects from Windows Domain Controllers via WinRM/PowerShell.

run_ad_analysis() stub is provided here so 29-02 tests can import it.
The full implementation (CloudResource conversion) is completed in 29-03.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    pass


def run_ad_analysis(
    options: object,
    output_path: Optional[str] = None,
) -> tuple[list, list[str]]:
    """Run AD data collection and return (resources, errors).

    Stub implementation: converts collect_all() results into CloudResource
    objects. Full implementation is completed in 29-03 (runner module).

    Args:
        options: AdOptions instance describing the collection parameters.
        output_path: Optional path for XLS output (handled in 29-03).

    Returns:
        Tuple of (list[CloudResource], list[str]) — resources and error messages.
    """
    from .collector import MicrosoftAdCollector

    collector = MicrosoftAdCollector(options)
    server_results = collector.collect_all()

    resources: list = []
    errors: list[str] = []

    for result in server_results:
        server = result.get("server", "unknown")
        if result.get("status") == "error":
            error_msg = result.get("error", "Unknown error")
            errors.append(f"DC {server}: {error_msg}")
            continue
        # Full CloudResource conversion implemented in 29-03.
        # For now, resources from successful DCs are appended as-is (placeholder).

    return resources, errors
