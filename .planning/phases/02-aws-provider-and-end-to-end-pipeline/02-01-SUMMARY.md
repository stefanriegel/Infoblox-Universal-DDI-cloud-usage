---
phase: 02-aws-provider-and-end-to-end-pipeline
plan: 01
subsystem: auth, discovery
tags: [aws, boto3, sts, organizations, moto, sso]

# Dependency graph
requires:
  - phase: 01-core-infrastructure
    provides: AuthValidator ABC, DiscoveryProvider ABC, CloudResource schema, CLI entry point, AuthDoctor, DiscoveryOrchestrator
provides:
  - AWSAuthValidator implementing AuthValidator with STS credential check and Organizations account counting
  - Organizations multi-account listing with AccessDenied fallback to single-account
  - STS cross-account role assumption with InfobloxUDDI-Discovery session name
  - Region auto-detection via EC2 describe_regions
  - AWSDiscoveryProvider implementing DiscoveryProvider with account filtering
  - CLI --profile, --role-name, --include-accounts, --exclude-accounts, --dry-run flags
affects: [02-02, 02-03, 02-04, 02-06, 03-azure-provider, 04-gcp-provider]

# Tech tracking
tech-stack:
  added: [boto3, moto]
  patterns: [moto @mock_aws test decorator, Organizations fallback, account filtering]

key-files:
  created:
    - src/cloud_usage/providers/__init__.py
    - src/cloud_usage/providers/aws/__init__.py
    - src/cloud_usage/providers/aws/auth.py
    - src/cloud_usage/providers/aws/organizations.py
    - src/cloud_usage/providers/aws/regions.py
    - src/cloud_usage/providers/aws/provider.py
    - tests/test_aws_auth.py
    - tests/test_aws_provider.py
  modified:
    - src/cloud_usage/cli.py

key-decisions:
  - "AWS Organizations API returns 'Id' not 'AccountId' -- code uses actual API field names"
  - "Auth validator keeps account_count=1 fallback when Organizations returns 0 accounts (no org created)"
  - "SSOTokenLoadError handled via exception class name check since import path varies across botocore versions"

patterns-established:
  - "moto @mock_aws decorator for all AWS service mocking in tests"
  - "Organizations fallback: try list_accounts, on empty or error fall back to STS get_caller_identity single account"
  - "Account filtering: include_accounts takes precedence over exclude_accounts when both provided"

requirements-completed: [AUTH-01, DISC-01, DISC-07]

# Metrics
duration: 6min
completed: 2026-02-23
---

# Phase 2 Plan 01: AWS Provider Foundation Summary

**AWS auth validator with STS/Organizations credential checks, multi-account discovery provider with include/exclude filtering, and CLI integration with --profile/--role-name/--dry-run flags**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-23T20:58:49Z
- **Completed:** 2026-02-23T21:04:56Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- AWSAuthValidator validates SSO credentials via STS with clear pass/fail and actionable suggestions for SSO token expiry and missing credentials
- Organizations multi-account discovery with automatic AccessDenied fallback to single-account mode
- AWSDiscoveryProvider with include/exclude account filtering (include takes precedence) and skeleton discover_account for Plan 06 wiring
- CLI gains --profile, --role-name, --include-accounts, --exclude-accounts, --dry-run flags
- Auth doctor now uses AWSAuthValidator for pre-flight checks
- 37 tests with moto mocks covering all paths (no live AWS credentials needed)

## Task Commits

Each task was committed atomically:

1. **Task 1: AWS auth validator, Organizations, and region discovery** - `7745005` (feat)
2. **Task 2: AWS discovery provider with account filtering and CLI integration** - `1508c64` (feat)

## Files Created/Modified
- `src/cloud_usage/providers/__init__.py` - Cloud providers package init
- `src/cloud_usage/providers/aws/__init__.py` - AWS provider package init
- `src/cloud_usage/providers/aws/auth.py` - AWSAuthValidator implementing AuthValidator ABC
- `src/cloud_usage/providers/aws/organizations.py` - Organizations account listing + STS cross-account role assumption
- `src/cloud_usage/providers/aws/regions.py` - Enabled region discovery via EC2 describe_regions
- `src/cloud_usage/providers/aws/provider.py` - AWSDiscoveryProvider implementing DiscoveryProvider ABC
- `src/cloud_usage/cli.py` - Updated with AWS-specific flags and provider instantiation
- `tests/test_aws_auth.py` - 17 tests for auth validator, organizations, regions
- `tests/test_aws_provider.py` - 20 tests for provider, filtering, CLI args

## Decisions Made
- AWS Organizations list_accounts API returns `Id` not `AccountId` -- code uses the actual API field names (plan referenced incorrect field name)
- Auth validator keeps account_count=1 fallback when Organizations returns 0 active accounts (handles case where no organization is created)
- SSOTokenLoadError handled via exception class name check (`type(exc).__name__`) since the import path varies across botocore versions
- Dry-run mode shows accounts and regions from the provider's session, not hardcoded values

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Organizations API field name from AccountId to Id**
- **Found during:** Task 1 (test_accounts_have_required_fields)
- **Issue:** Plan specified Organizations returns dicts with `AccountId` key, but actual AWS API returns `Id`
- **Fix:** Updated organizations.py docstring and tests to use correct `Id` field name
- **Files modified:** src/cloud_usage/providers/aws/organizations.py, tests/test_aws_auth.py
- **Verification:** test_accounts_have_required_fields passes with correct field name
- **Committed in:** 7745005 (Task 1 commit)

**2. [Rule 1 - Bug] Fixed auth validator Organizations fallback for empty account list**
- **Found during:** Task 1 (test_validate_succeeds_with_valid_credentials)
- **Issue:** When moto Organizations returns 0 accounts (no org created), account_count was set to 0 instead of fallback value 1
- **Fix:** Added `if active:` guard so account_count only overrides default when Organizations returns real accounts
- **Files modified:** src/cloud_usage/providers/aws/auth.py
- **Verification:** test_validate_succeeds_with_valid_credentials and test_validate_falls_back_to_single_account passes
- **Committed in:** 7745005 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness with actual AWS API response format. No scope creep.

## Issues Encountered
None - all issues were caught by tests and fixed immediately.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- AWS provider foundation complete, ready for resource collectors (Plans 02-04)
- AWSDiscoveryProvider.discover_account() is a skeleton returning empty list -- Plan 06 will wire collectors
- CLI integration complete, --aws flag creates and uses the real AWSDiscoveryProvider
- Auth doctor validates AWS credentials before scan starts

## Self-Check: PASSED

All 8 created files verified present. Both task commits (7745005, 1508c64) verified in git log. All 307 tests pass (37 new + 270 existing).

---
*Phase: 02-aws-provider-and-end-to-end-pipeline*
*Completed: 2026-02-23*
