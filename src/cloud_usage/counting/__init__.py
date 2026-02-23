"""
Counting, categorization, and token calculation pipeline.

Modules:
    categorizer: Resource categorization (DDI / IP / Asset / excluded)
    ip_counter: IP extraction and per-VPC de-duplication
    asset_dedup: ENI folding, tag-based exclusion, cross-account dedup
    token_calculator: Token calculation with ceiling division
"""
