"""Azure resource collectors for cloud discovery.

Each collector module discovers a category of Azure resources (networking,
DNS, compute, etc.) and returns list[CloudResource] instances. All
collectors use @retry_with_backoff for transient error handling and
accept injected Azure SDK management clients for testability.
"""
