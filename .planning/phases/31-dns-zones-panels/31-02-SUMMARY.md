---
phase: 31-dns-zones-panels
plan: "02"
subsystem: dashboard
tags: [jinja2, fastapi, dns, ad_manager, htmx, tdd]

requires:
  - phase: 31-01
    provides: Wave 0 xfail test scaffold for DNS-01 and DNS-02 test classes

provides:
  - _compute_top_cloud_dns_zones() helper in pages.py (AWS/Azure direct record_count, GCP counted from gcp-dns-record resources)
  - top_cloud_dns_zones in tab_summary() context and rendered DNS zones panel in summary.html
  - AdScanManager._top_dns_zones attribute, top_dns_zones property, set_complete() top_dns_zones kwarg
  - Per-zone record count extraction in _run_ad_pipeline() using Counter over ad-dns-record resource_ids
  - top_dns_zones in tab_ad() context and rendered DNS zones panel in partials/ad/complete.html

affects: [31-03, 32-attr-display]

tech-stack:
  added: []
  patterns:
    - "Cloud DNS top-5 aggregation: direct record_count for AWS/Azure zones; count gcp-dns-record resources for GCP (no join needed)"
    - "AD DNS top-5: Counter over ad:dns-record resource_id body split on '|' to extract zone name"
    - "Template guard pattern: {% if top_cloud_dns_zones %} / {% if top_dns_zones %} — panel hidden when list empty"
    - "Manager kwarg default: new keyword args to set_complete() always default to None for backward compat"

key-files:
  created: []
  modified:
    - src/cloud_usage/dashboard/routes/pages.py
    - src/cloud_usage/dashboard/services/ad_manager.py
    - src/cloud_usage/dashboard/routes/ad.py
    - src/cloud_usage/dashboard/templates/pages/summary.html
    - src/cloud_usage/dashboard/templates/partials/ad/complete.html
    - tests/test_dashboard_dns_zones.py

key-decisions:
  - "GCP DNS zone record counts computed by counting gcp-dns-record resources (no record_count in zone details), matched via details['zone_name'] internal name"
  - "top_dns_zones kwarg added as final optional keyword arg to set_complete() with None default — existing callers (test_dashboard_ad.py) unaffected"
  - "Counter.most_common(5) used in _run_ad_pipeline() for top AD zones — caller passes list to set_complete, manager stores as-is"

patterns-established:
  - "DNS panel style: section > p (label) > div (border) > table (zone_name monospace, count right-aligned) — reuse for NIOS panel in Plan 03"

requirements-completed: [DNS-01, DNS-02]

duration: 8min
completed: 2026-03-08
---

# Phase 31 Plan 02: DNS Zones Panels (DNS-01 + DNS-02) Summary

**Cloud and AD Top 5 DNS zone panels implemented via in-memory aggregation — no new backend pipeline work, two rendered panels with TDD-verified tests**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-08T12:02:14Z
- **Completed:** 2026-03-08T12:10:34Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- DNS-01: `_compute_top_cloud_dns_zones()` aggregates AWS/Azure zones (direct `record_count`) and GCP zones (counted from `gcp-dns-record` resources), top-5 sorted descending; wired into `tab_summary()` and rendered in `summary.html`
- DNS-02: `AdScanManager` gains `_top_dns_zones` attribute, `top_dns_zones` property, and backward-compatible `set_complete(top_dns_zones=None)` kwarg; `_run_ad_pipeline()` uses `Counter` to tally `ad-dns-record` resource_ids by zone; panel rendered in `partials/ad/complete.html`
- All TestCloudDnsZones (6 tests) and TestCloudDnsZoneTemplate (2 tests) now pass with real assertions; TestAdDnsZones (4) and TestAdDnsZoneTemplate (2) likewise; full `test_dashboard_ad.py` suite (20 tests) remains green

## Task Commits

Each task was committed atomically:

1. **Task 1: DNS-01 — Cloud Top 5 DNS zones** - `0853027` (feat)
2. **Task 2: DNS-02 — AD Top 5 DNS zones** - `34430d1` (feat)

## Files Created/Modified

- `src/cloud_usage/dashboard/routes/pages.py` - Added `_compute_top_cloud_dns_zones()` helper; wired into `tab_summary()` and `tab_ad()` contexts
- `src/cloud_usage/dashboard/services/ad_manager.py` - Added `_top_dns_zones` attr, `top_dns_zones` property, `top_dns_zones` kwarg to `set_complete()`
- `src/cloud_usage/dashboard/routes/ad.py` - Added Counter-based per-zone count extraction in `_run_ad_pipeline()`; passes `top_dns_zones` to `set_complete()`
- `src/cloud_usage/dashboard/templates/pages/summary.html` - Added conditionally-rendered Top 5 DNS Zones panel
- `src/cloud_usage/dashboard/templates/partials/ad/complete.html` - Added conditionally-rendered Top 5 AD DNS Zones panel
- `tests/test_dashboard_dns_zones.py` - Updated TestCloudDnsZones, TestCloudDnsZoneTemplate, TestAdDnsZones, TestAdDnsZoneTemplate with real assertions; removed @XFAIL markers from those 4 classes

## Decisions Made

- GCP zone record counts derived by counting `gcp-dns-record` resources with matching `details["zone_name"]`, then mapping internal name to FQDN from zone's `.name` field — avoids any complex join; aligns with research interface spec
- `top_dns_zones` added as final keyword argument with `None` default to `set_complete()` — ensures zero test regressions in `test_dashboard_ad.py` where callers don't pass this argument
- `Counter.most_common(5)` returns a list of `(zone, count)` tuples — stored directly in `_top_dns_zones`; template iterates with `{% for zone_name, count in top_dns_zones %}`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing `test_integration_aws.py`, `test_integration_azure.py`, `test_integration_gcp.py` fail at collection time due to missing `fold_enis_into_parents` import from `asset_dedup` — unrelated to this plan; not fixed (out of scope).

## Next Phase Readiness

- DNS-01 and DNS-02 panels are live and tested
- Plan 03 (NIOS DNS zones) can now use the same table style pattern established here; only backend pipeline extension to `NiosScanManager` and `_run_nios_pipeline` is required

---
*Phase: 31-dns-zones-panels*
*Completed: 2026-03-08*
