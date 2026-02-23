"""AWS resource collectors for cloud discovery.

Each module contains collector functions that take a boto3 client,
account_id, and region, returning lists of CloudResource instances.
All collectors use boto3 paginators and the retry_with_backoff decorator.
"""
