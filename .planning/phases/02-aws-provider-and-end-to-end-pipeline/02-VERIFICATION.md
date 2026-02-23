---
phase: 02-aws-provider-and-end-to-end-pipeline
verified: 2026-02-23T22:15:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Run python3 -m cloud_usage.cli --aws --profile <real-profile> --dry-run"
    expected: "Prints scan plan with accounts, regions, and resource types without crashing"
    why_human: "Requires live AWS credentials for the SSO auth path (SSOTokenLoadError handling)"
  - test: "Run a real scan against a dev AWS account with EC2 + Route53 + EBS resources"
    expected: "XLS file opens with three sheets, Detail rows show correct counted/skipped, Summary shows correct token totals"
    why_human: "Output formatting, formula correctness against live data, and XLS visual appearance need eyes on the file"
---

# Phase 2: AWS Provider and End-to-End Pipeline Verification Report

**Phase Goal:** Users can run a complete AWS scan that discovers resources across all accounts, counts DDI objects/IPs/assets, calculates token estimates, and produces a CSV/XLS report with detail and summary sheets
**Verified:** 2026-02-23T22:15:00Z
**Status:** PASSED
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths (from Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | User can authenticate via AWS SSO profile and discover resources across multiple AWS accounts and regions concurrently | VERIFIED | `AWSAuthValidator` in `auth.py` calls `sts.get_caller_identity()` with SSO session, handles `SSOTokenLoadError` / `NoCredentialsError` / `ExpiredTokenException` with actionable suggestions. `AWSDiscoveryProvider.list_accounts()` uses Organizations API with single-account fallback. Include/exclude filtering wired in `list_accounts()`. Concurrent multi-account wired through Phase 1 `DiscoveryOrchestrator`. |
| 2 | Tool correctly counts DNS zones, DNS records, subnets, and DHCP option sets from AWS and categorizes each resource as DDI, IP, or Asset with a skip reason if excluded | VERIFIED | `categorizer.py` maps `DDI_TYPES = {"vpc", "subnet", "route53-zone", "route53-record", "dhcp-option-set"}` and `TOKEN_FREE_TYPES = {"ebs-volume", "s3-bucket"}`. Orphaned DHCP option sets get `counted=False, skip_reason="orphaned DHCP option set..."`. All DDI collectors (`ec2.py`, `route53.py`, `dhcp.py`) produce correctly shaped `CloudResource` instances. Integration test `test_full_pipeline_single_account` asserts DDI resources exist and are categorized. |
| 3 | Active IPs are de-duplicated per VPC IP space, and managed assets are de-duplicated across discovery paths | VERIFIED | `ip_counter.py:deduplicate_ips_per_vpc()` uses `(vpc_id_or_account_id, ip_address)` tuple set for O(1) per-VPC dedup. `asset_dedup.py` provides `fold_enis_into_parents()` (ENI folding), `exclude_managed_service_resources()` (EKS tag-based exclusion), and `deduplicate_assets()` (cross-account RAM-shared resource dedup). All three run before categorization in `cli.py` pipeline. EKS exclusion integration test passes. |
| 4 | Token calculation (DDI/25 + IPs/13 + Assets/3) produces correct totals per account and as a provider total, matching manual calculation | VERIFIED | `token_calculator.py` exports `DDI_PER_TOKEN=25`, `IPS_PER_TOKEN=13`, `ASSETS_PER_TOKEN=3`. `calculate_tokens(100, 200, 50)` returns `total_tokens=37` (verified: `ceil(100/25)+ceil(200/13)+ceil(50/3)=4+16+17=37`). Zero-count produces 0 tokens (guard: `if count <= 0: return 0`). `calculate_provider_tokens()` aggregates across accounts. `cli.py` calls `calculate_account_tokens(acct_resources, deduplicated_ip_count=deduped_ip)` per account and `calculate_provider_tokens(account_summaries)` for provider total. |
| 5 | Output XLS file contains a detail sheet (one row per resource with ID, type, account, region, IPs, counted yes/no, category, skip reason) and a summary sheet (totals per account by resource type), plus a SHA-256 proof manifest documenting scan integrity | VERIFIED | `xlsx_report.py:write_xlsx_report()` writes Detail sheet (11 columns: Resource ID, Type, Account, Region, Name, IP Addresses, IP Count, Counted, Category, Skip Reason, Tags), Summary sheet (per-account DDI/IP/Asset counts + tokens + provider TOTAL row), and Warnings sheet. `proof_manifest.py:write_proof_manifest()` uses `hashlib.sha256` for `resource_hash` (sorted resource tuples) and `manifest_hash` (all manifest fields). Integration test `test_output_files_generated` verifies all three output files exist and proof manifest hash is reproducible. |

**Score: 5/5 truths verified**

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `src/cloud_usage/providers/aws/auth.py` | VERIFIED | 129 lines. `AWSAuthValidator(AuthValidator)` with `validate()` and `provider_name`. Handles `SSOTokenLoadError`, `NoCredentialsError`, `ExpiredTokenException`, generic `ClientError` with actionable suggestions. Returns `AuthResult`. |
| `src/cloud_usage/providers/aws/organizations.py` | VERIFIED | `list_organization_accounts()` uses paginator, returns ACTIVE accounts only. `assume_cross_account_role()` wraps `sts.assume_role`. |
| `src/cloud_usage/providers/aws/regions.py` | VERIFIED | `get_enabled_regions()` calls `describe_regions` with opt-in filters, returns sorted region list. |
| `src/cloud_usage/providers/aws/provider.py` | VERIFIED | 375 lines. `AWSDiscoveryProvider(DiscoveryProvider)`. `discover_account()` calls all 18+ collectors across all regions with Route53/S3 called once per account. `_safe_collect()` provides per-resource-type error isolation. |
| `src/cloud_usage/providers/aws/collectors/ec2.py` | VERIFIED | 7 functions: `collect_vpcs`, `collect_subnets`, `collect_enis`, `collect_eips`, `collect_nat_gateways`, `collect_vpn_gateways`, `collect_transit_gateways`. All use `get_paginator()`. ENI collector captures all primary+secondary IPs. |
| `src/cloud_usage/providers/aws/collectors/route53.py` | VERIFIED | `collect_route53_zones` (global, region="global"), `collect_route53_records` (all record types, A/AAAA extract IPs). |
| `src/cloud_usage/providers/aws/collectors/dhcp.py` | VERIFIED | `collect_dhcp_option_sets` with `vpc_dhcp_ids` set for orphan cross-reference. |
| `src/cloud_usage/providers/aws/collectors/compute.py` | VERIFIED | 6 functions: `collect_ec2_instances`, `collect_ecs_tasks`, `collect_eks_node_groups`, `collect_lambda_functions`, `collect_load_balancers_v2`, `collect_classic_load_balancers`. EC2 captures all IPs from all ENI attachments + `network_interface_ids` for folding. Lambda filters to VPC-attached only. |
| `src/cloud_usage/providers/aws/collectors/database.py` | VERIFIED | `collect_rds_instances`, `collect_elasticache_clusters`, `collect_redshift_clusters`. |
| `src/cloud_usage/providers/aws/collectors/token_free.py` | VERIFIED | `collect_ebs_volumes`, `collect_s3_buckets`. Both set `ip_addresses=[]`. |
| `src/cloud_usage/counting/categorizer.py` | VERIFIED | `categorize_resources()` applies DDI_TYPES, TOKEN_FREE_TYPES, orphaned DHCP, VPC-Lambda special case, and prior-exclusion preservation (Step 0: `if resource.counted is False and resource.skip_reason is not None: return`). |
| `src/cloud_usage/counting/ip_counter.py` | VERIFIED | `count_ips()`, `deduplicate_ips_per_vpc()` with `(vpc_id, ip)` tuple dedup key. Returns `per_account` breakdown for CLI pipeline. |
| `src/cloud_usage/counting/asset_dedup.py` | VERIFIED | `fold_enis_into_parents()`, `exclude_managed_service_resources()` (EKS prefix+exact tag match), `deduplicate_assets()`. All use `counted is False` (not falsy None) check. |
| `src/cloud_usage/counting/token_calculator.py` | VERIFIED | `calculate_tokens()`, `calculate_account_tokens()`, `calculate_provider_tokens()`. Constants `DDI_PER_TOKEN=25`, `IPS_PER_TOKEN=13`, `ASSETS_PER_TOKEN=3`. Zero guard: `if count <= 0: return 0`. |
| `src/cloud_usage/output/xlsx_report.py` | VERIFIED | `write_xlsx_report()` with Detail (11 cols, frozen pane, alternating colors, counted_yes/no formatting), Summary (per-account + TOTAL row), Warnings sheets. Professional formatting with xlsxwriter. |
| `src/cloud_usage/output/estimator_csv.py` | VERIFIED | `write_estimator_csv()` with 8-column CSV + TOTAL row. Uses stdlib `csv.writer`. |
| `src/cloud_usage/output/proof_manifest.py` | VERIFIED | `write_proof_manifest()` with `hashlib.sha256` for `resource_hash` (sorted resource tuples) and `manifest_hash` (all manifest fields). Contains scope, ratios, counts, tokens sections. |
| `src/cloud_usage/cli.py` | VERIFIED | Full pipeline: `fold_enis -> exclude_managed -> deduplicate -> categorize -> deduplicate_ips_per_vpc -> calculate_account_tokens -> calculate_provider_tokens -> write_xlsx_report + write_estimator_csv + write_proof_manifest`. AWS-specific flags: `--profile`, `--role-name`, `--include-accounts`, `--exclude-accounts`, `--dry-run`. |
| `tests/test_integration_aws.py` | VERIFIED | 8 integration test classes: `TestFullPipelineSingleAccount`, `TestOutputFilesGenerated`, `TestPartialFailureResilience`, `TestAccountFiltering` (2 tests), `TestDryRunNoDiscovery`, `TestTokenFreeResourcesInReport`, `TestEKSManagedNodesExcluded`. All use `@mock_aws`. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `auth.py` | `auth/validators.py` | `class AWSAuthValidator(AuthValidator)` | WIRED | Implements ABC, imports `AuthResult, AuthValidator`. |
| `provider.py` | `discovery/provider.py` | `class AWSDiscoveryProvider(DiscoveryProvider)` | WIRED | Imports `DiscoveryProvider`. Implements `list_accounts()` and `discover_account()`. |
| `provider.py` | `collectors/` | `discover_account()` calls all collectors | WIRED | 18+ `_safe_collect()` calls importing all collector functions from ec2, route53, dhcp, compute, database, token_free modules. |
| `cli.py` | `providers/aws/provider.py` | `_get_discovery_providers()` creates `AWSDiscoveryProvider` | WIRED | Pattern `AWSDiscoveryProvider` found at line 502. Session + role_name + include/exclude wired. |
| `cli.py` | `counting/` | Pipeline imports and calls after orchestrator.run() | WIRED | All 6 counting pipeline functions imported and called in order at lines 332-360. |
| `cli.py` | `output/` | `write_xlsx_report`, `write_estimator_csv`, `write_proof_manifest` | WIRED | All three output functions imported at lines 33-35 and called at lines 392-405. |
| `xlsx_report.py` | `schema/resource.py` | Reads `CloudResource` fields for Detail sheet rows | WIRED | `resource.resource_id`, `resource.resource_type`, `resource.counted`, `resource.category`, `resource.skip_reason`, `resource.ip_addresses`, `resource.tags` all accessed in `_write_detail_sheet()`. |
| `proof_manifest.py` | `hashlib` | SHA-256 hashing for proof integrity | WIRED | `import hashlib` at line 11. `hashlib.sha256(...).hexdigest()` called twice (resource_hash + manifest_hash). |
| `token_calculator.py` | `categorizer.py` | Consumes categorized resource counts via `ddi_count`/`asset_count` | WIRED | `calculate_account_tokens()` iterates resources checking `resource.category == "ddi"` and `resource.category == "asset"`. |

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| AUTH-01 | 02-01, 02-06 | AWS SSO profile authentication | SATISFIED | `AWSAuthValidator` validates via STS with SSO error handling; wired in CLI auth doctor. |
| DISC-01 | 02-01, 02-06 | Discover resources across all AWS accounts and regions | SATISFIED | `AWSDiscoveryProvider` with Organizations multi-account + region auto-detection + `discover_account()` calling all collectors. |
| DISC-07 | 02-01, 02-06 | Filter accounts with include/exclude | SATISFIED | `include_accounts`/`exclude_accounts` filtering in `list_accounts()` with include-takes-precedence logic. |
| DDI-01 | 02-03 | Count DNS zones (Route53 hosted zones) | SATISFIED | `collect_route53_zones()` with `resource_type="route53-zone"`, categorized as DDI. |
| DDI-02 | 02-03 | Count DNS records within zones | SATISFIED | `collect_route53_records()` with `resource_type="route53-record"`, all types included. |
| DDI-03 | 02-03 | Count subnets (VPC subnets) | SATISFIED | `collect_subnets()` with `resource_type="subnet"`, categorized as DDI. |
| DDI-04 | 02-03 | Count DHCP option sets | SATISFIED | `collect_dhcp_option_sets()` with orphan cross-reference; orphaned sets get `counted=False`. |
| IP-01 | 02-02 | Count all private IP addresses | SATISFIED | `ip_counter.py` extracts all IPs from `resource.ip_addresses`; ENI collector captures all private IPs. |
| IP-02 | 02-02 | Count all public IP addresses | SATISFIED | EIP collector and EC2 instance collector capture public IPs. ENI captures `Association.PublicIp`. |
| IP-03 | 02-02 | De-duplicate IPs per VPC IP space | SATISFIED | `deduplicate_ips_per_vpc()` uses `(vpc_id, ip)` tuple set; same IP in different VPCs counted separately. |
| ASSET-01 | 02-04 | Count resources with IPs as managed assets | SATISFIED | Categorizer rule 4: `if resource.has_ips(): counted=True, category="asset"`. EC2, ELB, ECS, Lambda, NAT GW, etc. |
| ASSET-02 | 02-04 | Discover token-free resources without counting them | SATISFIED | EBS, S3 discovered via `token_free.py` collectors; categorizer sets `counted=False` with skip_reason. |
| ASSET-03 | 02-04 | EBS Volumes and S3 Buckets excluded as token-free | SATISFIED | `TOKEN_FREE_TYPES = {"ebs-volume": "token-free: EBS Volume", "s3-bucket": "token-free: S3 Bucket"}` in categorizer. |
| ASSET-06 | 02-02 | De-duplicate assets across discovery paths | SATISFIED | `deduplicate_assets()` deduplicates by `resource_id` across accounts; RAM-shared resources counted once in owning account. ENI folding prevents double-counting. |
| TOKEN-01 | 02-02 | Token formula: DDI/25 + IPs/13 + Assets/3 | SATISFIED | `calculate_tokens()` with `DDI_PER_TOKEN=25`, `IPS_PER_TOKEN=13`, `ASSETS_PER_TOKEN=3` and `math.ceil` with zero guard. Verified: `calculate_tokens(100,200,50)=37`. |
| TOKEN-02 | 02-02 | Each resource categorized with counted/category/skip_reason | SATISFIED | Categorizer sets all three fields on every `CloudResource`. Output detail sheet exposes all three. |
| TOKEN-03 | 02-02 | Token calculation per account and as provider total | SATISFIED | `calculate_account_tokens()` per account + `calculate_provider_tokens()` for aggregate. Both surfaced in CLI summary and XLS Summary sheet. |
| OUT-01 | 02-05 | One CSV/XLS file per cloud provider | SATISFIED | `write_xlsx_report()` and `write_estimator_csv()` each produce one file per scan. Filename includes provider name and timestamp. |
| OUT-02 | 02-05 | Detail sheet with one row per resource | SATISFIED | `_write_detail_sheet()` writes one row per resource in `resources` list with all 11 required columns. |
| OUT-03 | 02-05 | Summary sheet with totals per account | SATISFIED | `_write_summary_sheet()` writes per-account rows + provider TOTAL row with DDI/IP/Asset counts and token calculations. |
| OUT-04 | 02-05 | SHA-256 proof manifest | SATISFIED | `write_proof_manifest()` produces JSON with `resource_hash` (sorted resource tuples) and `manifest_hash` (all fields). Integration test verifies hash reproducibility. |
| OUT-05 | 02-05 | Output shows what was counted and what was skipped with reasons | SATISFIED | Detail sheet "Counted" column (Yes/No with green/red formatting) and "Skip Reason" column. Summary sheet shows only counted resources. |

**All 21 phase requirements: SATISFIED**

---

### Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|-----------|
| `provider.py` line 374 | `return []` in `_safe_collect` | Info | Correct behavior -- error isolation returning empty list on collector failure, not a stub. |
| `cli.py` line 164 | `return []` in `select_providers` on EOF | Info | Correct behavior -- returns empty list on keyboard interrupt, not a stub. |

No blockers or warnings found. No `TODO`/`FIXME`/placeholder patterns found in any source files. No stub implementations detected.

---

### Human Verification Required

#### 1. AWS SSO Auth Flow

**Test:** Run `python3 -m cloud_usage.cli --aws --profile <expired-sso-profile> --skip-auth-check` with an expired SSO token
**Expected:** Error message "AWS SSO token expired or not found" with suggestion "Run: aws sso login --profile <profile>"
**Why human:** SSOTokenLoadError path handled via `type(exc).__name__` check -- cannot be triggered with moto mocks

#### 2. XLS Output Visual Quality

**Test:** Run a real scan against a dev AWS account and open the generated `.xlsx` file
**Expected:** Three sheets (Detail, Summary, Warnings) with blue header row, alternating row colors, green "Yes"/"red "No" in Counted column, frozen header rows, readable column widths
**Why human:** Visual formatting and readability require human inspection of the produced file

---

### Gaps Summary

No gaps found. All 5 success criteria are verified, all 21 requirements are satisfied, all artifacts pass three-level verification (exists, substantive, wired), all key links are confirmed, 449/449 tests pass, and all 13 Phase 2 commit hashes exist in git history.

The pipeline is complete end-to-end: `python3 -m cloud_usage.cli --aws` will run auth doctor, discover resources across all accounts and regions, run the counting pipeline, and produce XLS + CSV + proof manifest output files.

---

_Verified: 2026-02-23T22:15:00Z_
_Verifier: Claude (gsd-verifier)_
