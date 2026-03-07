---
phase: 27
slug: azure-ddi-gaps
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-07
---

# Phase 27 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `venv/bin/python -m pytest tests/test_azure_collectors_hybrid_networking.py tests/test_categorizer.py -q` |
| **Full suite command** | `venv/bin/python -m pytest tests/ -q` |
| **Estimated runtime** | ~0.05s (phase files), ~few seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** < 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 27-W0-01 | 01 | 0 (W0) | AZUG-01 | unit (RED gate) | `venv/bin/python -m pytest tests/test_azure_collectors_hybrid_networking.py -k "VpnGateway" -q` | ✅ | ✅ green |
| 27-W0-02 | 01 | 0 (W0) | AZUG-02 | unit (RED gate) | `venv/bin/python -m pytest tests/test_azure_collectors_hybrid_networking.py -k "PrivateLinkService" -q` | ✅ | ✅ green |
| 27-W0-03 | 01 | 0 (W0) | AZUG-03 | unit (RED gate) | `venv/bin/python -m pytest tests/test_azure_collectors_hybrid_networking.py -k "VirtualWan" -q` | ✅ | ✅ green |
| 27-W0-04 | 01 | 0 (W0) | AZUG-04 | unit (RED gate) | `venv/bin/python -m pytest tests/test_azure_collectors_hybrid_networking.py -k "RouteTable" -q` | ✅ | ✅ green |
| 27-W0-05 | 01 | 0 (W0) | AZUG-05 | unit (RED gate) | `venv/bin/python -m pytest tests/test_azure_collectors_hybrid_networking.py -k "Tenant" -q` | ✅ | ✅ green |
| 27-W0-06 | 01 | 0 (W0) | AZUG-01–05 | unit (RED gate) | `venv/bin/python -m pytest tests/test_categorizer.py -k "azure_ddi" -q` | ✅ | ✅ green |
| 27-02-01 | 02 | 2 | AZUG-01–05 | unit | `venv/bin/python -m pytest tests/test_azure_collectors_hybrid_networking.py -q` | ✅ | ✅ green |
| 27-03-01 | 03 | 3 | AZUG-01–05 | integration | `venv/bin/python -m pytest tests/test_azure_collectors_hybrid_networking.py tests/test_categorizer.py tests/test_azure_provider.py -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 0 (Plan 01) wrote RED tests before any implementation. Existing pytest infrastructure covered all phase requirements — no new framework install needed.

- [x] `tests/test_azure_collectors_hybrid_networking.py` — RED stubs: `TestCollectAzureVpnGateways` (updated to assert `azure-vnet-gateway`), `TestCollectAzurePrivateLinkServices`, `TestCollectAzureVirtualWans`, `TestCollectAzureRouteTables`, `TestCollectAzureTenants`
- [x] `tests/test_categorizer.py` — `test_azure_ddi_gaps_in_ddi_types()` with 5 positive assertions + `azure-vpn-gateway` not-in-DDI_TYPES negative assertion

---

## Gap Analysis (Nyquist Audit — 2026-03-07)

| Requirement | Tests | Status |
|-------------|-------|--------|
| AZUG-01 VNet Gateways | `TestCollectAzureVpnGateways` (2 tests asserts azure-vnet-gateway), `test_azure_ddi_gaps_in_ddi_types` | COVERED |
| AZUG-02 Private Link Services | `TestCollectAzurePrivateLinkServices` (2 tests), `test_azure_ddi_gaps_in_ddi_types` | COVERED |
| AZUG-03 Virtual WANs | `TestCollectAzureVirtualWans` (1 test), `test_azure_ddi_gaps_in_ddi_types` | COVERED |
| AZUG-04 Route Tables | `TestCollectAzureRouteTables` (1 test), `test_azure_ddi_gaps_in_ddi_types` | COVERED |
| AZUG-05 Tenants | `TestCollectAzureTenants` (1 test + dedup guard), `test_azure_ddi_gaps_in_ddi_types` | COVERED |

**No gaps.** All 5 requirements have automated verification. 94 tests across hybrid_networking + categorizer pass GREEN in 0.05s.

---

## Manual-Only Verifications

None. VERIFICATION.md (9/9 truths, 2026-03-07) explicitly confirmed no manual verification required: the XLS resource-type breakdown is driven automatically by `CloudResource.resource_type` — no new XLS code path exists to verify manually. The original draft listed two manual items; both were superseded by the verifier's finding that the pipeline is fully automated.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all AZUG-01 through AZUG-05 requirements with proper RED gate
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-03-07

---

## Validation Audit 2026-03-07

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Note | Pre-execution draft updated to post-execution state; all tasks GREEN; manual items removed per VERIFICATION.md finding |
