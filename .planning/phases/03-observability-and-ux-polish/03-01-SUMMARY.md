---
phase: 03-observability-and-ux-polish
plan: 01
subsystem: auth
tags: [azure-identity, credential, cli, checkpoint, observability]

# Dependency graph
requires:
  - phase: 02-concurrent-execution-hardening
    provides: per-subscription client lifecycle and retry policy
  - phase: 01-credential-chain-and-code-correctness
    provides: ClientSecretCredential + InteractiveBrowserCredential/DeviceCodeCredential chain in config.py
provides:
  - Credential path logging: all three paths print [Auth] Using X before any blocking call
  - Large-tenant warning: fires when subscription count > warn_sub_threshold and subscription-workers > 2
  - Configurable checkpoint TTL via --checkpoint-ttl-hours (0 = never expire)
  - --warn-sub-threshold flag for tunable warning threshold
affects:
  - users scanning large Azure tenants (warning visibility)
  - users running scripted/automated scans (checkpoint TTL tuning)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "[Auth] Using X bracket prefix for credential selection messages before blocking calls"
    - "[Warning] bracket prefix for non-blocking advisory messages before scan start"
    - "ttl_hours=0 short-circuit for never-expire semantics in load_checkpoint()"
    - "Long-only flag names for new CLI flags (--checkpoint-ttl-hours, --warn-sub-threshold)"

key-files:
  created: []
  modified:
    - azure_discovery/config.py
    - azure_discovery/discover.py
    - main.py

key-decisions:
  - "[03-01]: [Auth] Using InteractiveBrowserCredential prints before browser popup; [Auth] Using DeviceCodeCredential prints before device code prompt — immediate feedback before blocking"
  - "[03-01]: ttl_hours > 0 short-circuit in load_checkpoint() means 0 = never expire (no time comparison at all)"
  - "[03-01]: Warning uses all_subs_total (full pre-checkpoint list) to reflect true tenant scale, not remaining subs after resume"
  - "[03-01]: Warning is non-blocking (print and continue) — no user prompt, no sleep"
  - "[03-01]: Removed stale --checkpoint-interval flag and azure_args.checkpoint_interval forwarding from main.py (dead code since Phase 01)"

patterns-established:
  - "Credential selection message printed BEFORE blocking call (browser popup or device code prompt)"
  - "Subscription warning fires after all_subs_total captured, before checkpoint filtering"
  - "Both parsers (main.py and discover.py) declare identical flags with matching defaults"

requirements-completed:
  - OBSV-01
  - OBSV-02
  - OBSV-03

# Metrics
duration: 1min
completed: 2026-02-18
---

# Phase 3 Plan 01: Observability and UX Polish Summary

**Credential path logging ([Auth] Using X for all three paths), configurable checkpoint TTL (--checkpoint-ttl-hours, 0=never), and large-tenant ARM throttle warning (--warn-sub-threshold) added to config.py, discover.py, and main.py**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-18T22:04:07Z
- **Completed:** 2026-02-18T22:05:07Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- All three credential paths (ClientSecretCredential, InteractiveBrowserCredential, DeviceCodeCredential) now print `[Auth] Using X` before any blocking call
- `load_checkpoint()` parameterized with `ttl_hours=48` default — backward-compatible; `ttl_hours=0` means never expire
- `--checkpoint-ttl-hours` and `--warn-sub-threshold` declared in both `discover.py` and `main.py` parsers with identical defaults and forwarded through `azure_args`
- Large-tenant warning fires before scan using `all_subs_total` (true tenant scale, not post-resume filtered list)
- Removed stale `--checkpoint-interval` dead code from `main.py`

## Task Commits

Each task was committed atomically:

1. **Task 1: Add consistent [Auth] Using messages for all credential paths** - `8ab4577` (feat)
2. **Task 2: Add --checkpoint-ttl-hours and --warn-sub-threshold CLI flags with warning logic** - `94c3920` (feat)

**Plan metadata:** committed with state/roadmap updates (docs: complete plan)

## Files Created/Modified
- `azure_discovery/config.py` - Added `[Auth] Using InteractiveBrowserCredential` before browser popup, `[Auth] Using DeviceCodeCredential` before device code prompt
- `azure_discovery/discover.py` - Parameterized `load_checkpoint(ttl_hours=48)`, added `--checkpoint-ttl-hours` and `--warn-sub-threshold` to local parser, added warning block using `all_subs_total`, updated `load_checkpoint()` call site
- `main.py` - Added `--checkpoint-ttl-hours` and `--warn-sub-threshold` flags, forwarded both to `azure_args`, removed stale `--checkpoint-interval` and its `azure_args.checkpoint_interval` forwarding

## Decisions Made
- `[Auth] Using InteractiveBrowserCredential` prints as FIRST line in `if _has_display():` block, before "Opening browser..." — gives feedback before blocking browser popup
- `[Auth] Using DeviceCodeCredential` prints immediately before the `DeviceCodeCredential(...)` constructor — gives feedback before device code prompt
- `ttl_hours > 0` short-circuit in `load_checkpoint()` means zero entirely skips the time comparison (true never-expire semantics, not "compare to epoch")
- Warning uses `all_subs_total` captured before checkpoint filtering so it reflects tenant scale even on resume
- Warning is non-blocking: `print()` then continue — no user prompt, no sleep delay

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 03 Plan 01 complete. All observability requirements (OBSV-01, OBSV-02, OBSV-03) are satisfied.
- Users can now see which credential path was selected before any blocking auth call.
- Large tenant operators get a visible warning before ARM rate-limit exposure.
- Checkpoint TTL is now tunable without source code edits.

## Self-Check: PASSED

- FOUND: azure_discovery/config.py
- FOUND: azure_discovery/discover.py
- FOUND: main.py
- FOUND: .planning/phases/03-observability-and-ux-polish/03-01-SUMMARY.md
- FOUND commit 8ab4577 (Task 1: [Auth] Using messages)
- FOUND commit 94c3920 (Task 2: checkpoint TTL + warning flags)

---
*Phase: 03-observability-and-ux-polish*
*Completed: 2026-02-18*
