---
phase: 29
slug: microsoft-ad-core
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-07
---

# Phase 29 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `venv/bin/python -m pytest tests/test_ad_collector.py tests/test_ad_runner.py tests/test_categorizer.py -k "ad or Ad or TestAdDdi" tests/test_cli.py -k "TestAdCli" -q` |
| **Full suite command** | `venv/bin/python -m pytest tests/ -q` |
| **Estimated runtime** | ~0.1s (phase files), ~few seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** < 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement(s) | Test Type | Automated Command | File Exists | Status |
|---------|------|------|----------------|-----------|-------------------|-------------|--------|
| 29-01-01 | 01 | 1 (W0) | AD-01…AD-08 | unit (RED gate) | `venv/bin/python -m pytest tests/test_ad_collector.py tests/test_ad_runner.py -x -q` | ✅ | ✅ green |
| 29-02-01 | 02 | 2 | AD-01, AD-05, AD-06 | unit | `venv/bin/python -m pytest tests/test_ad_collector.py -k "TestAdOptions or TestNormalize or TestKerberos or TestNtlm" -q` | ✅ | ✅ green |
| 29-02-02 | 02 | 2 | AD-01, AD-02, AD-03, AD-04, AD-07 | unit | `venv/bin/python -m pytest tests/test_ad_collector.py -q` | ✅ | ✅ green |
| 29-03-01 | 03 | 3 | AD-02, AD-03, AD-04, AD-08 | unit | `venv/bin/python -m pytest tests/test_ad_runner.py -q` | ✅ | ✅ green |
| 29-04-01 | 04 | 4 | AD-02, AD-03 (DDI_TYPES) | unit | `venv/bin/python -m pytest tests/test_categorizer.py -k "TestAdDdi" -q` | ✅ | ✅ green |
| 29-04-02 | 04 | 4 | AD-01, AD-05, AD-06, AD-07, AD-08 | unit | `venv/bin/python -m pytest tests/test_cli.py -k "TestAdCli" -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 (Plan 01) wrote RED tests before any implementation. Existing pytest infrastructure covered all phase requirements — no new framework install needed.

- [x] `tests/test_ad_collector.py` — 22 RED test methods covering AD-01 through AD-07 (ModuleNotFoundError gate)
- [x] `tests/test_ad_runner.py` — 16 RED test methods covering AD-01 through AD-04, AD-08 (ModuleNotFoundError gate)
- [x] `tests/test_categorizer.py` — `TestAdDdiTypesInCategorizer` class with 4 assertions (3 RED, 1 immediate GREEN for ad-user exclusion)

---

## Gap Analysis (Nyquist Audit — 2026-03-07)

| Requirement | Tests | Status |
|-------------|-------|--------|
| AD-01 WinRM/PS transport | `TestCollectDns`, `TestCollectDhcp`, `TestCollectUsers`, `TestDcFailureContinue`, `TestAllDcsFail`, `TestAdCli::test_main_ad_runs_pipeline` | COVERED |
| AD-02 DNS zones + records | `TestCollectDns` (4 tests), `TestAdDnsZoneResourceType` (3 tests), `TestAdDnsRecordResourceType` (2 tests), `TestAdDdiTypesInCategorizer::test_ad_dns_zone_in_ddi_types`, `test_ad_dns_record_in_ddi_types` | COVERED |
| AD-03 DHCP scopes/leases | `TestCollectDhcp` (3 tests), `TestAdDhcpScopeResourceType` (2 tests), `TestAdDhcpIpCount` (2 tests), `TestAdDdiTypesInCategorizer::test_ad_dhcp_scope_in_ddi_types` | COVERED |
| AD-04 AD Users (asset) | `TestCollectUsers` (1 test), `TestCollectUsersSidDedup` (1 test), `TestAdUserResourceType` (3 tests), `TestAdDdiTypesInCategorizer::test_ad_user_not_in_ddi_types` | COVERED |
| AD-05 --ad-services flag | `TestNormalizeAdServices` (4 tests), `TestAdCli::test_parse_args_ad_services` | COVERED |
| AD-06 Kerberos/NTLM auth | `TestNtlmRequiresCredentials` (2 tests), `TestKerberosNoCredentialsRequired` (1 test), `TestAdCli::test_main_ad_ntlm_no_credentials_returns_1` | COVERED |
| AD-07 Autodiscovery | `TestAutodiscover` (2 tests), `TestAdCli::test_parse_args_ad_autodiscover` | COVERED |
| AD-08 XLS report | `TestXlsReportProduced` (1 test), `TestAdCli::test_main_ad_runs_pipeline`, `test_main_ad_plus_cloud` | COVERED |

**No gaps.** All 8 requirements have automated verification. 51 AD-related tests across 4 files pass GREEN in 0.07s.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live WinRM connection to real DC (Kerberos) | AD-01 | Requires pywinrm installed, live Windows DC on WinRM port, valid Kerberos tickets on domain-joined machine | Run `cloud-usage --ad-servers <real-dc> --ad-auth-mode kerberos`; expect `ad_analysis_<timestamp>.xlsx` written. |
| Autodiscovery against real AD forest | AD-07 | Requires multi-DC forest environment; Get-ADForest/Get-ADDomainController must return real results | Run `cloud-usage --ad-autodiscover --ad-discovery-server <seed-dc>`; expect deduplication across all discovered DCs. |
| XLS report column fidelity and token formula | AD-08 | Spreadsheet visual inspection; token calculation exercised in unit tests but final layout needs human review | Open `ad_analysis_<timestamp>.xlsx`; verify DDI/IP/Asset counts match DDI÷25, IPs÷13, Assets÷3 formula. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all AD-01 through AD-08 requirements with proper RED gate
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-03-07
