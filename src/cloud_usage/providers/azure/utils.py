"""Shared utility functions for Azure collectors.

Provides common helpers used by all Azure collector modules (networking,
compute, database). Plans 02 and 03 (Wave 2) import from this module
to avoid dependency conflicts.
"""

from __future__ import annotations


def _extract_resource_group(resource_id: str) -> str:
    """Extract the resource group name from an ARM resource ID.

    Parses the ARM resource ID by splitting on "/" segments and finding
    the "resourcegroups" segment (case-insensitive per Azure ARM behavior),
    then returns the next segment as the resource group name.

    Args:
        resource_id: Full ARM resource ID string, e.g.,
            "/subscriptions/.../resourceGroups/myRG/providers/..."

    Returns:
        The resource group name, or "" if the ID is empty, malformed,
        or does not contain a resourceGroups segment.
    """
    if not resource_id:
        return ""

    segments = resource_id.split("/")

    for i, segment in enumerate(segments):
        if segment.lower() == "resourcegroups" and i + 1 < len(segments):
            return segments[i + 1]

    return ""
