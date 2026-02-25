---
phase: 06-platform-hardening
plan: "02"
subsystem: CI/CD and code signing
tags: [ci, github-actions, powershell, code-signing, python-matrix, cross-platform]
dependency_graph:
  requires: []
  provides: [multi-platform-ci, powershell-signing, enterprise-resign-docs]
  affects: [.github/workflows/ci.yml, .github/workflows/sign-ps1.yml, docs/enterprise-resign.md]
tech_stack:
  added: []
  patterns: [github-actions-matrix, powershell-code-signing, self-signed-cert]
key_files:
  modified:
    - .github/workflows/ci.yml
    - .github/workflows/sign-ps1.yml
  created:
    - docs/enterprise-resign.md
decisions:
  - "CI matrix uses os x python-version product: 3 platforms x 3 Python versions = 9 jobs per matrix job"
  - "Integration test commands updated from python main.py to python -m cloud_usage.cli (main.py deleted in Phase 2)"
  - "sign-ps1.yml: CN=Infoblox UDDI Estimator, 2-year expiry, -HashAlgorithm sha256 added"
  - "enterprise-resign.md covers both paths: enterprise CA signing and self-signed cert import"
metrics:
  duration: "2min"
  completed_date: "2026-02-25"
  tasks_completed: 2
  files_modified: 3
---

# Phase 6 Plan 02: CI Hardening and PowerShell Code Signing Summary

**One-liner:** Multi-platform CI matrix (ubuntu/windows/macos x Python 3.10/3.11/3.12) with smoke tests, corrected PowerShell signing cert (CN=Infoblox UDDI Estimator, 2-year, SHA256), and enterprise re-signing guide.

## What Was Built

### Task 1: CI Workflow Multi-Platform Python 3.10+ Testing

Updated `.github/workflows/ci.yml`:

- **Branch triggers:** Added `main` alongside `dev` for push and pull_request triggers
- **Python matrix:** Added `python-version: ['3.10', '3.11', '3.12']` to both `setup-test` and `unit-test` jobs; `actions/setup-python@v4` now uses `${{ matrix.python-version }}`
- **Platform matrix:** Both `setup-test` and `unit-test` test on ubuntu, windows, and macos (existing platform matrix retained and combined with Python matrix)
- **Smoke tests added to setup-test:** Dashboard import smoke test and preflight smoke test run after setup script on all platforms
- **Setup script invocation:** Changed `echo "4" | bash setup_venv.sh` to `bash setup_venv.sh 4` (positional arg) for CI-friendly non-interactive invocation
- **Integration test commands:** Updated from `python main.py aws/azure/gcp` to `python -m cloud_usage.cli --aws/--azure/--gcp` (main.py was deleted in Phase 2)
- **Lint job:** Kept at ubuntu-latest only with Python 3.11 (no matrix needed for linting)

### Task 2: PowerShell Signing Workflow and Enterprise Re-Signing Guide

Updated `.github/workflows/sign-ps1.yml`:

- Changed `-Subject "CN=Infoblox Universal DDI Setup"` to `-Subject "CN=Infoblox UDDI Estimator"` per CONTEXT.md decision
- Changed `-NotAfter (Get-Date).AddYears(1)` to `-NotAfter (Get-Date).AddYears(2)` per CONTEXT.md decision
- Added `-HashAlgorithm sha256` for best-practice code signing (explicit hash algorithm)
- All other workflow structure unchanged: signing step, verification step, commit with `[skip ci]`, release upload

Created `docs/enterprise-resign.md`:

- **Overview:** Explains why self-signed certs are not trusted by default and when each path applies
- **Path 1 (Enterprise re-signing):** Prerequisites (code signing EKU cert from internal CA), step-by-step PowerShell commands to select cert and re-sign, distribution guidance
- **Path 2 (Self-signed cert import):** One-time `Import-Certificate` into `Cert:\LocalMachine\Root` requiring admin elevation
- **Troubleshooting:** Four scenarios covered: cert verification failure, Restricted execution policy, no code signing cert installed, GPO-enforced AllSigned/Restricted

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1    | d4bf5ac | feat(06-02): update CI workflow for multi-platform Python 3.10+ testing |
| 2    | f92ab45 | feat(06-02): update PowerShell signing workflow and add enterprise re-signing guide |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated integration test CLI entry point**
- **Found during:** Task 1
- **Issue:** `python main.py aws` referenced `main.py` which was deleted in Phase 2 (per [02-06] decision). The integration test would have failed if credentials were present.
- **Fix:** Updated to `python -m cloud_usage.cli --aws/--azure/--gcp --format txt`
- **Files modified:** `.github/workflows/ci.yml`
- **Commit:** d4bf5ac

None - All other plan steps executed exactly as written.

## Self-Check: PASSED

- FOUND: .github/workflows/ci.yml
- FOUND: .github/workflows/sign-ps1.yml
- FOUND: docs/enterprise-resign.md
- FOUND commit: d4bf5ac
- FOUND commit: f92ab45
