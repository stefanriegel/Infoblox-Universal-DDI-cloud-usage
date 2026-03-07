---
phase: 29-microsoft-ad-core
plan: "04"
subsystem: cli
tags: [argparse, ad, categorizer, ddi-types, winrm]

# Dependency graph
requires:
  - phase: 29-03
    provides: run_ad_analysis() runner and AdOptions dataclass wired in providers/ad package
provides:
  - ad-dns-zone, ad-dns-record, ad-dhcp-scope in categorizer.DDI_TYPES
  - 12 --ad-* CLI flags in parse_args()
  - _run_ad_cli() function following NIOS pattern (lazy import, validation, output path)
  - Non-exclusive AD branch in main() — coexists with --aws/--azure/--gcp
affects: [cli, categorizer, phase-29-complete]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Non-exclusive CLI branch: AD runs before cloud provider selection; exits only if no cloud flags"
    - "Lazy import in _run_ad_cli: from cloud_usage.providers.ad import AdOptions, run_ad_analysis"
    - "Port determination: explicit --ad-winrm-port > SSL-sensitive default (5986 SSL / 5985 plain)"

key-files:
  created:
    - tests/test_cli.py (TestAdCli class appended)
  modified:
    - src/cloud_usage/counting/categorizer.py (3 AD DDI types added to DDI_TYPES)
    - src/cloud_usage/cli.py (parse_args AD group + _run_ad_cli() + main() AD branch)

key-decisions:
  - "AD branch in main() is non-exclusive: calls _run_ad_cli, then continues to cloud scan if --aws/--azure/--gcp set; exits only when no cloud flags present"
  - "Port selection: args.ad_winrm_port or (5986 if args.ad_winrm_ssl else 5985) — explicit always wins"
  - "ntlm-without-credentials caught at AdOptions.__post_init__ ValueError; re-raised to _run_ad_cli -> stderr + return 1"
  - "All-DCs-failed guard: empty resources + non-empty errors -> return 1 from _run_ad_cli"

patterns-established:
  - "AD DDI types in categorizer follow same comment style as GCP/Azure DDI Gaps phases"

requirements-completed: [AD-01, AD-05, AD-06, AD-07, AD-08]

# Metrics
duration: 8min
completed: 2026-03-07
---

# Phase 29 Plan 04: Microsoft AD CLI Wiring and Categorizer DDI Types Summary

**AD provider wired into CLI via 12 --ad-* flags and _run_ad_cli(); ad-dns-zone, ad-dns-record, ad-dhcp-scope added to DDI_TYPES; all 8 AD requirements GREEN**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-07T19:25:00Z
- **Completed:** 2026-03-07T19:33:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added ad-dns-zone, ad-dns-record, ad-dhcp-scope to DDI_TYPES in categorizer.py (ad-user and ad-dhcp-ip intentionally absent)
- Added 12 --ad-* CLI flags in a dedicated argument group in parse_args()
- Implemented _run_ad_cli() following the NIOS pattern: lazy import, AdOptions construction, exception handling, output path with timestamp
- Added non-exclusive AD branch in main() — AD scan runs before cloud provider selection and does not block cloud scan when --aws/--azure/--gcp are also provided
- All 152 non-integration tests pass; TestAdCli 9/9, TestAdDdiTypesInCategorizer 4/4 GREEN

## Task Commits

Each task was committed atomically:

1. **Task 1: Add AD DDI types to categorizer (TDD GREEN)** - `b2709cf` (feat)
2. **Task 2: CLI argument group and _run_ad_cli() wiring (TDD RED)** - `71b31cd` (test)
3. **Task 2: CLI argument group and _run_ad_cli() wiring (TDD GREEN)** - `c6b0057` (feat)

**Plan metadata:** (this commit — docs)

_Note: TDD tasks have separate RED (test) and GREEN (feat) commits_

## Files Created/Modified

- `src/cloud_usage/counting/categorizer.py` - 3 AD DDI types appended to DDI_TYPES set
- `src/cloud_usage/cli.py` - AD argument group in parse_args(), _run_ad_cli() function, AD branch in main()
- `tests/test_cli.py` - TestAdCli class with 9 tests covering parse_args and main() AD behavior

## Decisions Made

- AD branch in main() is non-exclusive: calls _run_ad_cli, then continues to cloud scan if --aws/--azure/--gcp set; exits only when no cloud flags present
- Port selection: args.ad_winrm_port or (5986 if args.ad_winrm_ssl else 5985) — explicit flag always wins over SSL-sensitive default
- NTLM-without-credentials caught at AdOptions.__post_init__ ValueError; bubbles up to _run_ad_cli -> stderr + return 1
- All-DCs-failed guard: empty resources + non-empty errors -> return 1 from _run_ad_cli (prevents silent no-output success)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 29 (Microsoft AD Core) is COMPLETE. All 8 AD requirements (AD-01 through AD-08) are fulfilled:
- AD-01: MicrosoftAdCollector with WinRM/PowerShell transport
- AD-02: DNS zones and records collection (ad-dns-zone, ad-dns-record in DDI_TYPES)
- AD-03: DHCP scopes collection (ad-dhcp-scope in DDI_TYPES)
- AD-04: Users collection with sentinel IP for asset categorization
- AD-05: Authentication modes (kerberos default, ntlm with credentials)
- AD-06: Autodiscovery mode (--ad-autodiscover + --ad-discovery-server)
- AD-07: CLI integration (--ad-servers triggers pipeline)
- AD-08: XLS output (ad_analysis_<timestamp>.xlsx via run_ad_analysis)

Milestone v1.7 Reference Parity: ALL 5 phases (25-29) and 28 requirements COMPLETE.

---
*Phase: 29-microsoft-ad-core*
*Completed: 2026-03-07*
