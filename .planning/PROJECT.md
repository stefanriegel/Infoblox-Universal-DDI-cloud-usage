# Azure Large-Tenant Discovery Fix

## What This Is

A bug fix for the Infoblox Universal DDI cloud usage tool's Azure discovery module. The tool fails to scan most subscriptions when an Azure tenant has 500+ subscriptions, due to credential handling that doesn't scale under concurrent load on Windows. This fix ensures reliable discovery across all subscriptions regardless of tenant size.

## Core Value

Every enabled Azure subscription must be scanned successfully — no subscription should silently fail due to credential or concurrency issues.

## Requirements

### Validated

- Existing Azure discovery works for small tenants (<100 subscriptions) — existing
- Multi-subscription parallel discovery with ThreadPoolExecutor — existing
- Checkpoint/resume mechanism for interrupted scans — existing
- Licensing calculation and proof manifest generation — existing

### Active

- [ ] Azure credential handling scales to 500+ subscription tenants on Windows
- [ ] SharedTokenCacheCredential works reliably as primary credential method
- [ ] AzureCliCredential fallback handles concurrent access without subprocess exhaustion
- [ ] Token is obtained once and reused across all subscription workers
- [ ] Failed subscriptions are retried with credential-aware error handling
- [ ] Duplicate get_all_subscription_ids() calls in discover.py are eliminated

### Out of Scope

- Adding new Azure resource types to discovery — separate enhancement
- Changing the licensing calculation logic — unrelated
- AWS or GCP discovery changes — different providers
- UI/CLI output format changes — cosmetic, not the bug

## Context

**The Bug:**
Customer with 566 Azure subscriptions on Windows 11. When `SharedTokenCacheCredential` fails (no accounts in cache), the tool falls back to `AzureCliCredential` which spawns `az` subprocesses for every token request. With 4 subscription workers creating 5+ management clients each, this overwhelms the Azure CLI on Windows. Result: ~54 subscriptions succeed, ~512 fail with `CredentialUnavailableError: Failed to invoke the Azure CLI`.

**Root Cause Chain:**
1. `SharedTokenCacheCredential` fails on customer's Windows setup ("No accounts found in cache")
2. Code falls back to `AzureCliCredential` (subprocess-based)
3. 4 subscription workers × 5 clients × token refreshes = massive concurrent `az` subprocess calls
4. Windows can't handle the subprocess load → CLI becomes unresponsive
5. All remaining subscriptions fail with `CredentialUnavailableError`

**Key Files:**
- `azure_discovery/config.py` — Credential initialization and caching (lines 223-276)
- `azure_discovery/discover.py` — Subscription parallel processing (lines 288-316), duplicate code (lines 206-274 duplicated)
- `azure_discovery/azure_discovery.py` — Per-subscription client initialization (lines 61-73)

**Customer Environment:**
- Windows 11, PowerShell, Python venv
- 566+ enabled Azure subscriptions in one tenant
- Using `az login` for authentication (no service principal)

## Constraints

- **Backward compatibility**: Must still work on macOS/Linux and small tenants
- **No new dependencies**: Fix should use existing azure-identity library capabilities
- **Windows first**: The fix must prioritize Windows reliability since that's where the bug manifests
- **Credential methods**: Must support service principal, shared token cache, CLI fallback, and interactive browser

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Cache token, not just credential object | AzureCliCredential caches the object but still spawns subprocesses per token refresh | — Pending |
| Use AccessToken caching wrapper | Obtain token once, reuse until expiry, then refresh with serialized access | — Pending |
| Fix SharedTokenCacheCredential reliability | If this works, it avoids CLI subprocesses entirely | — Pending |
| Remove duplicate subscription listing code | discover.py has copy-pasted blocks that waste API calls | — Pending |

---
*Last updated: 2026-02-18 after initialization*
