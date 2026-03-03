---
status: complete
phase: 19-token-breakdown-webui
source: 19-01-SUMMARY.md, 19-02-SUMMARY.md
started: 2026-03-03T00:00:00Z
updated: 2026-03-03T00:01:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Scenario cards show formula rows
expected: Each NIOS scenario card contains inline formula derivation rows: "N,NNN DDI ÷ 50 = X.X" and "NNN IPs ÷ 25 = X.X", followed by a divider and "Total: X.X tokens"
result: pass

### 2. Hybrid UDDI card shows two sub-blocks
expected: The Hybrid UDDI card renders two labeled sub-blocks before the combined total — "NIOS-remaining" using DDI÷50 and IPs÷25, and "NIOSX-migrated" using DDI÷25 and IPs÷13
result: pass

### 3. Formula numbers use correct formatting
expected: Large numbers in formula rows display with comma thousands separators (e.g., "1,234 DDI ÷ 50 = 24.7") and formula results show one decimal place
result: pass

### 4. Asset count row appears conditionally
expected: When asset_count > 0, an Asset count row appears in the formula breakdown; if asset_count is 0, no asset row is shown
result: pass

### 5. Member Attribution section appears below Download CTA
expected: Below the Download CSV button, a "MEMBER ATTRIBUTION" section heading appears with a subtitle note explaining per-member Active IP counts are lease-only and should not be summed for scenario totals
result: pass

### 6. Attribution table has correct columns and data
expected: The attribution table shows columns: Member, Group, DDI Objects, Active IPs, Token Contribution — with member hostnames in monospace font and numeric values comma-formatted; Token Contribution shows two decimal places
result: pass

### 7. Group badges are color-coded
expected: Each row's Group column shows a small badge — gray badge with "NIOS" text for NIOS members, a blue-accented badge with "NIOSX" text for NIOSX members
result: pass

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
