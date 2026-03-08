---
phase: 30-ad-dashboard
plan: 05
subsystem: ui
tags: [jinja2, htmx, fastapi, forms, ad, winrm]

# Dependency graph
requires:
  - phase: 30-ad-dashboard/30-04
    provides: AD tab wired into tab_bar.html and pages.py; wizard.html rendered in idle/error state
provides:
  - wizard.html form field names aligned to POST /ad/run route handler (servers, auth_mode, autodiscover, winrm_ssl, winrm_port)
  - domain pre-fill expression removed (AdOptions has no .domain field)
  - Regression test confirming wizard field names produce non-empty servers list in AdOptions
affects: [31-dns-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns:
  - "Form field naming must match route handler form.get() keys exactly — no prefix mismatch tolerated"
  - "Jinja2 pre-fill expressions must reference attributes that exist on the dataclass"

key-files:
  created: []
  modified:
    - src/cloud_usage/dashboard/templates/partials/ad/wizard.html
    - tests/test_dashboard_ad.py

key-decisions:
  - "Renamed five wizard.html fields to drop ad_ prefix, matching what ad.py reads: servers, auth_mode, autodiscover, winrm_ssl, winrm_port"
  - "Removed last_options.domain Jinja2 expression (AdOptions has no .domain field) — replaced with value=\"\""
  - "Pre-existing test_integration_*.py failures (fold_enis_into_parents ImportError) are out of scope; confirmed pre-existing"

patterns-established:
  - "Gap closure plan pattern: targeted Edit replacements on specific line numbers, verified with python -c assert script"

requirements-completed: [AD-09, AD-12]

# Metrics
duration: 5min
completed: 2026-03-08
---

# Phase 30 Plan 05: AD Wizard Field Name Alignment and Domain Pre-fill Fix Summary

**Five form field name mismatches between wizard.html and POST /ad/run fixed, plus invalid `last_options.domain` Jinja2 expression removed, with regression test confirming real browser submissions now build a non-empty AdOptions.servers list**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-08T11:30:00Z
- **Completed:** 2026-03-08T11:35:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Fixed five form field name mismatches: `ad_servers` → `servers`, `ad_auth_mode` → `auth_mode`, `ad_autodiscover` → `autodiscover`, `ad_ssl` → `winrm_ssl`, `ad_port` → `winrm_port`
- Removed `last_options.domain` Jinja2 expression (AdOptions dataclass has no `.domain` attribute); domain input now renders `value=""`
- Added `test_ad_run_wizard_field_names` regression test in `TestAdRun` confirming wizard field names reach route correctly and produce non-empty `servers` list
- All 21 AD dashboard tests green; no regressions introduced

## Task Commits

1. **Task 1: Fix wizard.html field names and domain pre-fill** - `f1348d4` (fix)
2. **Task 2: Add integration test for wizard field names** - `52727e7` (test)

**Plan metadata:** (to be recorded in final commit)

## Files Created/Modified

- `src/cloud_usage/dashboard/templates/partials/ad/wizard.html` - Six targeted replacements: five field name renames + domain pre-fill removed
- `tests/test_dashboard_ad.py` - New `test_ad_run_wizard_field_names` test added to `TestAdRun` class (21 tests total)

## Decisions Made

- Renamed only the five mismatched fields; kept `ad_username`, `ad_password`, `ad_svc_dns`, `ad_svc_dhcp`, `ad_svc_user` unchanged (they were already correctly aligned)
- Used `value=""` (static empty) for domain input rather than any dynamic expression — domain is not stored in AdOptions
- Pre-existing `test_integration_*.py` failures (`fold_enis_into_parents` ImportError) confirmed out of scope; deferred to appropriate phase

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

All files verified present. Task commits f1348d4 and 52727e7 confirmed in git log.

## Issues Encountered

Pre-existing import failures in `test_integration_aws.py`, `test_integration_azure.py`, and `test_integration_gcp.py` (missing `fold_enis_into_parents` symbol from `asset_dedup`) caused the `pytest tests/ -x -q -m "not integration"` command to fail early. These are unrelated to this plan; all 21 AD dashboard tests and 1448 other non-integration tests pass. Added to `deferred-items.md`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- AD wizard field name alignment complete; real browser form submissions will now produce valid AdOptions with non-empty servers list
- Phase 30 AD Dashboard fully complete (all 5 plans done)
- Ready for Phase 31: DNS Dashboard

---
*Phase: 30-ad-dashboard*
*Completed: 2026-03-08*
