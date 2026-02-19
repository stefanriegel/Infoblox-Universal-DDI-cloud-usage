# Phase 4: GCP Credential Chain and Fail-Fast - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the broken gcloud-subprocess-based credential check with a validated Python-library credential singleton. The tool exits immediately on invalid/expired tokens with actionable error messages — never reports "Discovery completed successfully!" with 0 resources. Credential is created once on the main thread; workers receive the same instance.

</domain>

<decisions>
## Implementation Decisions

### Error remediation messages
- Include specific shell commands to fix auth problems (e.g., `gcloud auth application-default login`, `export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`)
- When no credentials found at all, suggest both SA and ADC paths equally — don't prefer one over the other
- If the operator only has `gcloud auth` configured (no ADC), guide them: "No ADC found. If you have gcloud configured, run: `gcloud auth application-default login`"
- Match the existing Azure auth error style but adapt for GCP-specific credential types and fix commands

### Credential type identification
- Auth log line should include default project when known (e.g., `[Auth] Using Application Default Credentials (default project: my-project)`)
- SA key and ADC are the two primary paths per success criteria

### Validation depth
- Pre-check permissions with a lightweight API call during validation — don't wait for discovery to fail on obvious permission gaps
- Credential must be validated before any discovery work begins

### Existing gcloud subprocess
- Eliminate ALL gcloud subprocess calls for authentication — use only the google-auth Python library
- No dependency on gcloud CLI being installed for auth to work
- Claude should audit the codebase for all gcloud subprocess calls (not just `gcloud auth list`) and catalog them during research

### Claude's Discretion
- Whether error messages differ per failure type or use a single message with multiple hints (based on what exception types expose)
- How to handle end-user credentials from `gcloud auth login` (warn and continue, block, or treat as ADC variant)
- SA log line detail level (email, key file path, or both)
- Whether Workload Identity Federation gets its own log line or is grouped under ADC
- Validation strategy: refresh-only vs refresh + API call, and retry behavior on transient failure
- Whether to show token expiry time on successful validation
- Whether gcloud CLI is still needed for non-auth operations elsewhere in the tool
- Banner/output ordering relative to validation

</decisions>

<specifics>
## Specific Ideas

- Azure auth error format is the reference point — GCP errors should feel consistent but include GCP-specific remediation
- The tool should work with just `GOOGLE_APPLICATION_CREDENTIALS` set and zero gcloud CLI dependency for auth
- Permission pre-check is desired so operators know immediately if their credential lacks required scopes, rather than discovering this mid-scan

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-gcp-credential-chain-and-fail-fast*
*Context gathered: 2026-02-19*
