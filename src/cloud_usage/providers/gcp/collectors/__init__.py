"""GCP resource collectors for cloud discovery.

Contains per-category collector modules (compute, networking, dns,
database, token_free) that return lists of CloudResource instances.
Each collector uses aggregatedList where available for efficiency.
"""
