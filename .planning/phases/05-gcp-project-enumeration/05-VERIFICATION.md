---
phase: 05-gcp-project-enumeration
verified: 2026-02-19T13:15:00Z
status: passed
score: 14/14 must-haves verified
re_verification: false
---

# Phase 5: GCP Project Enumeration Verification Report

**Phase Goal:** The tool discovers all ACTIVE GCP projects accessible to the credential and handles edge cases cleanly before any per-project discovery work
**Verified:** 2026-02-19T13:15:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

All truths derived from the PLAN frontmatter `must_haves` across both plans (05-01 and 05-02).

#### Truths from Plan 05-01 (config.py core logic)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `enumerate_gcp_projects()` with no explicit project fetches all ACTIVE projects via `search_projects` and returns a list of `ProjectInfo` | VERIFIED | `config.py:172` calls `client.search_projects(request=request)` in `_fetch_active_projects()`; `config.py:316-324` builds and returns `List[ProjectInfo]` |
| 2 | `enumerate_gcp_projects()` with an explicit project bypasses `search_projects` and returns a single-element `ProjectInfo` list | VERIFIED | `config.py:281` resolves `explicit_project`; `config.py:286-294` single-project branch returns one-element list without calling `_fetch_active_projects()` |
| 3 | When zero projects are found, an actionable error mentioning `resourcemanager.projects.get` is printed and `sys.exit(1)` is called | VERIFIED | `config.py:305-310`: `"ERROR: No ACTIVE GCP projects found. Ensure the credential has resourcemanager.projects.get permission."` followed by `sys.exit(1)` |
| 4 | When `org_id` is provided, `search_projects` query is scoped to `parent:organizations/{org_id}` | VERIFIED | `config.py:162-165`: normalizes org_id with `organizations/` prefix if missing; builds `query = f"state:ACTIVE parent:{parent}"` |
| 5 | Include/exclude glob patterns filter the project list before API pre-checks | VERIFIED | `config.py:302` calls `_apply_project_filters()` before the API pre-check loop at `config.py:317`; `fnmatch.fnmatch()` used at `config.py:194,199` |
| 6 | Per-project API pre-check sets `compute_enabled` and `dns_enabled` booleans on each `ProjectInfo` | VERIFIED | `config.py:204-240` implements `_check_apis_enabled()` using `batch_get_services`; `config.py:320-324` builds `ProjectInfo` with both booleans |
| 7 | Projects with disabled APIs get `[Skip]` log lines; projects with all APIs enabled are silent | VERIFIED | `config.py:244-248`: `_log_api_status()` prints `[Skip] {project_id}: Compute API disabled` / `[Skip] {project_id}: DNS API disabled`; no print for fully-enabled (silent per locked decision) |
| 8 | `google-cloud-resource-manager` and `google-cloud-service-usage` are in `requirements.txt` | VERIFIED | `requirements.txt:19-20`: `google-cloud-resource-manager>=1.12.0` and `google-cloud-service-usage>=1.3.0` present, each exactly once |

#### Truths from Plan 05-02 (discover.py/main.py wiring)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 9 | Running `python main.py gcp` with no `--project` flag or `GOOGLE_CLOUD_PROJECT` triggers multi-project enumeration | VERIFIED | `discover.py:82-90` resolves org_id and calls `enumerate_gcp_projects()` with `project=getattr(args, "project", None)` which is `None` when flag absent; no `GOOGLE_CLOUD_PROJECT` means `explicit_project` is `None` in config.py, triggering multi-project path |
| 10 | Running `python main.py gcp --project my-proj` bypasses enumeration and scans that single project | VERIFIED | `main.py:320` sets `gcp_args.project = args.project`; `discover.py:86` passes `project=getattr(args, "project", None)`; `config.py:281-294` detects explicit project and returns single-element list |
| 11 | Running `python main.py gcp --org-id 123456` scopes enumeration to that org | VERIFIED | `main.py:321`: `gcp_args.org_id = args.org_id`; `discover.py:82`: `org_id = getattr(args, "org_id", None) or os.getenv("GOOGLE_CLOUD_ORG_ID")`; `config.py:162-165` normalizes and builds scoped query |
| 12 | Running `python main.py gcp --include-projects 'prod-*'` filters the project list | VERIFIED | `main.py:322`: `gcp_args.include_projects = args.include_projects`; `discover.py:88` passes `include_patterns`; `config.py:191-195` applies include filter via `fnmatch.fnmatch()` |
| 13 | Running `python main.py gcp --exclude-projects 'test-*'` excludes matching projects | VERIFIED | `main.py:323`: `gcp_args.exclude_projects = args.exclude_projects`; `discover.py:89` passes `exclude_patterns`; `config.py:196-200` applies exclude filter via `fnmatch.fnmatch()` |
| 14 | The `enumerate_gcp_projects()` result is stored and the full project list flows to `scanned_projects` for backward compatibility | VERIFIED | `discover.py:100`: `active_project = projects[0].project_id` for Phase 5 single-scan compat; `discover.py:116`: `scanned_projects = [p.project_id for p in projects]` captures full enumerated list for proof manifest |

**Score:** 14/14 truths verified

---

### Required Artifacts

| Artifact | Provides | Exists | Substantive | Wired | Status |
|----------|----------|--------|-------------|-------|--------|
| `gcp_discovery/config.py` | `ProjectInfo` dataclass | Yes | Yes — `@dataclass` with `project_id`, `compute_enabled`, `dns_enabled` fields at line 27-33 | Yes — imported in `discover.py:13` | VERIFIED |
| `gcp_discovery/config.py` | `enumerate_gcp_projects()` | Yes | Yes — 76-line implementation with single/multi-project paths, org scoping, filtering, pre-check loop | Yes — called at `discover.py:83-90` | VERIFIED |
| `gcp_discovery/config.py` | `_fetch_active_projects()` helper | Yes | Yes — uses deferred `resourcemanager_v3` import, `search_projects`, defense-in-depth state check | Yes — called at `config.py:299` | VERIFIED |
| `gcp_discovery/config.py` | `_apply_project_filters()` helper | Yes | Yes — `fnmatch.fnmatch()` with `is not None` guards (empty list != no filter) | Yes — called at `config.py:302` | VERIFIED |
| `gcp_discovery/config.py` | `_check_apis_enabled()` helper | Yes | Yes — uses `batch_get_services`, `PermissionDenied`->(False,False), other Exception->(True,True) | Yes — called at `config.py:288,318` | VERIFIED |
| `gcp_discovery/config.py` | `_log_api_status()` helper | Yes | Yes — `[Skip]` lines for disabled APIs, silent for enabled | Yes — called at `config.py:289,319` | VERIFIED |
| `gcp_discovery/discover.py` | CLI flags and `enumerate_gcp_projects()` call | Yes | Yes — all 4 flags in parser, call before banner, `GOOGLE_CLOUD_ORG_ID` env fallback | Yes — wired from `main.py:320-324` via `gcp_args` | VERIFIED |
| `main.py` | GCP flags forwarded to `gcp_args` | Yes | Yes — all 4 flags in main parser with `(GCP)` prefix, forwarded to `gcp_args` namespace | Yes — `gcp_main(gcp_args)` called at `main.py:324` | VERIFIED |
| `requirements.txt` | New GCP dependencies | Yes | Yes — `google-cloud-resource-manager>=1.12.0`, `google-cloud-service-usage>=1.3.0` | Yes — in GCP Dependencies section, each exactly once | VERIFIED |

---

### Key Link Verification

#### Plan 05-01 Key Links

| From | To | Via | Status | Evidence |
|------|-----|-----|--------|---------|
| `config.py:enumerate_gcp_projects()` | `resourcemanager_v3.ProjectsClient.search_projects()` | `_fetch_active_projects()` helper | WIRED | `config.py:157` deferred import; `config.py:160` client creation; `config.py:172` call to `client.search_projects(request=request)` |
| `config.py:enumerate_gcp_projects()` | `service_usage_v1.ServiceUsageClient.batch_get_services()` | `_check_apis_enabled()` helper | WIRED | `config.py:283-284` creates `usage_client` once; `config.py:225` calls `client.batch_get_services(request=request)` |
| `config.py:enumerate_gcp_projects()` | `fnmatch.fnmatch()` | `_apply_project_filters()` helper | WIRED | `config.py:5` stdlib import; `config.py:194,199` uses `fnmatch.fnmatch(p, pat)` |

#### Plan 05-02 Key Links

| From | To | Via | Status | Evidence |
|------|-----|-----|--------|---------|
| `main.py:main()` | `gcp_discovery/discover.py:main()` | `gcp_args` namespace | WIRED | `main.py:316-324`: builds `gcp_args` with `project`, `org_id`, `include_projects`, `exclude_projects`; `main.py:324` calls `gcp_main(gcp_args)` |
| `gcp_discovery/discover.py:main()` | `gcp_discovery/config.py:enumerate_gcp_projects()` | function call with args | WIRED | `discover.py:13` imports `enumerate_gcp_projects`; `discover.py:83-90` calls it with all required kwargs |
| `gcp_discovery/discover.py:main()` | `gcp_discovery/config.py:ProjectInfo` | import and usage | WIRED | `discover.py:13` imports `ProjectInfo`; `discover.py:100` uses `projects[0].project_id`; `discover.py:116` uses `[p.project_id for p in projects]` |

---

### Requirements Coverage

All six ENUM requirements were claimed by both plans (05-01 and 05-02). Cross-referenced against REQUIREMENTS.md.

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| ENUM-01 | 05-01, 05-02 | Tool auto-discovers all ACTIVE projects accessible to the credential | SATISFIED | `config.py:172` iterates `search_projects` with `query="state:ACTIVE"`; `config.py:313` prints count; defense-in-depth at `config.py:174` |
| ENUM-02 | 05-01, 05-02 | Tool warns explicitly when 0 projects found with IAM guidance | SATISFIED | `config.py:305-310`: error message names `resourcemanager.projects.get` permission; `sys.exit(1)` called |
| ENUM-03 | 05-01, 05-02 | Single-project backward compat via `--project` flag or `GOOGLE_CLOUD_PROJECT` env var | SATISFIED | `config.py:281` priority chain: `project or os.getenv("GOOGLE_CLOUD_PROJECT") or adc_project`; single-element return at `config.py:290-294`; `--project` flag in `discover.py:48-52` and `main.py:257-261` |
| ENUM-04 | 05-01, 05-02 | Org/folder-aware enumeration when `GOOGLE_CLOUD_ORG_ID` is set | SATISFIED | `config.py:162-165` normalizes org_id to `organizations/{id}` format and scopes query; `discover.py:82` reads `GOOGLE_CLOUD_ORG_ID` env var as fallback; `--org-id` flag in both parsers |
| ENUM-05 | 05-01, 05-02 | Project include/exclude via `--include-projects` / `--exclude-projects` glob patterns | SATISFIED | `config.py:185-201` implements `_apply_project_filters()` using `fnmatch.fnmatch`; applied at `config.py:302` before pre-checks; both flags in both parsers with `nargs="+"` |
| ENUM-06 | 05-01, 05-02 | `accessNotConfigured` errors classified and skipped gracefully (not treated as auth failure) | SATISFIED | `config.py:235-237`: `PermissionDenied` (which includes `accessNotConfigured`) caught in `_check_apis_enabled()`, returns `(False, False)` — project kept in list but marked as APIs unavailable; `[Skip]` lines printed for user visibility |

No orphaned requirements: REQUIREMENTS.md maps exactly ENUM-01 through ENUM-06 to Phase 5, all claimed by both plans.

---

### Anti-Patterns Found

Scan performed across all modified files: `gcp_discovery/config.py`, `gcp_discovery/discover.py`, `main.py`, `requirements.txt`.

No anti-patterns found:
- No TODO/FIXME/XXX/HACK/PLACEHOLDER comments in any modified file
- No `return null` / `return {}` / `return []` stub returns
- No empty handlers or console-log-only implementations
- No bare `except Exception` in credential/auth paths (CRED-05 compliance maintained)
- No module-level imports of `resourcemanager_v3` or `service_usage_v1` (deferred correctly)

One implementation detail worth noting (not a problem): `_check_apis_enabled()` at line 238 uses a bare `except Exception: return True, True` to handle transient errors. This is intentional per the plan design — transient failures assume APIs are enabled and let discovery surface the real error later. This is distinct from the credential anti-pattern (CRED-05) which prohibited bare excepts in the auth chain.

---

### Human Verification Required

Two items require runtime confirmation that cannot be verified by static analysis:

#### 1. Multi-Project Enumeration End-to-End

**Test:** Run `python main.py gcp` with ADC credentials that have access to multiple GCP projects and no `GOOGLE_CLOUD_PROJECT` env var set.
**Expected:** Tool prints `Found N ACTIVE projects` (where N > 1), followed by any `[Skip]` lines for projects with disabled APIs, then proceeds with discovery using the first project.
**Why human:** Requires live GCP credentials and a multi-project environment; search_projects pagination behavior cannot be verified statically.

#### 2. ENUM-06 accessNotConfigured Classification

**Test:** Run `python main.py gcp` against a project where `serviceusage.googleapis.com` or compute/DNS APIs are not enabled. Observe the output.
**Expected:** `[Skip] {project-id}: Compute API disabled` or `[Skip] {project-id}: DNS API disabled` lines appear; the tool does NOT exit or print an error. Discovery proceeds for other projects.
**Why human:** Requires a GCP project in the specific `accessNotConfigured` state; the `PermissionDenied -> (False, False)` path is correct in code but can only be confirmed live.

---

### Noteworthy Implementation Details

The following implementation details exceed plan requirements and strengthen correctness:

- **Defense-in-depth ACTIVE state check:** Server-side `query="state:ACTIVE"` PLUS client-side `project.state == resourcemanager_v3.Project.State.ACTIVE` guard at `config.py:174`. Race condition protection if a project transitions state between query and iteration.
- **`is not None` filter guard:** `_apply_project_filters()` uses `if include_patterns is not None` rather than truthiness — an empty list `[]` means "match nothing" (filter everything out), which is semantically different from `None` (no filter). Correct edge case handling.
- **Single `ServiceUsageClient` reuse:** Created once in `enumerate_gcp_projects()` at `config.py:284` and passed to `_check_apis_enabled()` as the `client` parameter — not recreated per project. Avoids connection overhead in large-org scenarios.
- **Commits are atomic and verified:** All four commits (3e46d63, fae8607, e278cc2, 6f311a4) exist in the repository and their diffs match the claimed changes.

---

### Gaps Summary

None. All 14 must-haves verified, all 6 ENUM requirements satisfied, all key links wired, no anti-patterns, all three files have clean syntax.

---

_Verified: 2026-02-19T13:15:00Z_
_Verifier: Claude (gsd-verifier)_
