"""Azure subscription enumeration and display formatting.

Lists accessible subscriptions via SubscriptionClient and provides
human-readable display formatting per CONTEXT.md:
"Display Name (subscription-guid)" format.
"""

from __future__ import annotations


def list_subscriptions(credential) -> list[dict]:
    """List all Enabled subscriptions accessible with the given credential.

    Uses SubscriptionClient.subscriptions.list() to enumerate subscriptions
    and filters to only Enabled ones.

    Args:
        credential: Azure credential object (DefaultAzureCredential or similar).

    Returns:
        List of dicts with keys: id (subscription_id), display_name,
        tenant_id, state. Only includes Enabled subscriptions.
    """
    from azure.mgmt.resource import SubscriptionClient

    sub_client = SubscriptionClient(credential)
    subscriptions = []

    for sub in sub_client.subscriptions.list():
        if sub.state and sub.state.value == "Enabled":
            subscriptions.append({
                "id": sub.subscription_id,
                "display_name": sub.display_name or "",
                "tenant_id": sub.tenant_id or "",
                "state": sub.state.value,
            })

    return subscriptions


def get_subscription_display(sub_id: str, display_name: str) -> str:
    """Format a subscription for display in output columns.

    Returns "Display Name (subscription-guid)" format per CONTEXT.md
    account column specification.

    Args:
        sub_id: Azure subscription GUID.
        display_name: Human-readable subscription display name.

    Returns:
        Formatted display string.
    """
    if display_name:
        return f"{display_name} ({sub_id})"
    return sub_id
