# Pitfalls Research

**Domain:** NIOS Grid backup parsing & hybrid UDDI licensing analysis (v1.1 addition to existing cloud discovery tool)
**Researched:** 2026-02-28
**Confidence:** HIGH for Python XML/tarfile/FastAPI pitfalls (verified against CPython issue tracker and official docs); HIGH for NIOS counting semantics (validated against ZF reference backup and domain document); MEDIUM for FastAPI upload + background task interaction (verified pattern, not tested against this specific codebase).

---

## v1.0 Pitfalls (Cloud Discovery — Phases 1–9)

The original pitfalls document (researched 2026-02-23) covers auth token expiry, Azure ARM rate limiting, GCP quota exhaustion, checkpoint corruption, memory exhaustion from in-memory resource accumulation, and broad exception handling. Those pitfalls are not repeated here. This document covers only pitfalls specific to adding NIOS Grid backup parsing to the existing tool.

---

## Critical Pitfalls

### Pitfall 1: iterparse Holds the Entire XML Tree In Memory Unless Elements Are Explicitly Cleared

**What goes wrong:**
`xml.etree.ElementTree.iterparse` appears to stream — it yields events element by element — but internally it builds a growing in-memory tree. Without explicit `elem.clear()` calls after processing each element, every `<OBJECT>` parsed from a 2GB+ onedb.xml stays in memory until the loop completes. For a 2.5M-object file like the ZF reference backup, the process grows to multiple gigabytes of RAM and either is OOM-killed or thrashes swap. The tool appears to be streaming but actually consumes the same memory as a full `ElementTree.parse()`.

**Why it happens:**
CPython's iterparse implementation appends each parsed element to its parent's `_children` list and never removes it unless the code explicitly calls `elem.clear()`. Circular references between parent and child elements prevent the garbage collector from freeing processed nodes promptly. This is a known CPython bug (tracked in issues #102055 and #35502) and is not fixed by design — iterparse is classified as "incremental" not "streaming." Developers assume `iterparse` is automatically memory-efficient, which it is not without explicit lifecycle management.

**How to avoid:**
After extracting data from each `<OBJECT>` element, call `elem.clear()` immediately. Additionally, keep a reference to the root/parent element and call `root.clear()` periodically to release the parent's child list:

```python
root = None
for event, elem in ET.iterparse(fileobj, events=("start", "end")):
    if event == "start" and root is None:
        root = elem          # capture root so we can clear its children list
    if event == "end" and elem.tag == "OBJECT":
        process_object(elem)
        elem.clear()
        if root is not None:
            del root[:]      # remove processed children from root's children list
```

Never clear an element before its children have been processed — clearing a parent that contains unprocessed children destroys their data. Consider `lxml.etree.iterparse` as an alternative; it offers identical API with better memory behavior and ~3–5x faster parsing for flat record structures like onedb.xml.

**Warning signs:**
- Parser process RSS memory growing linearly with progress through the file (visible via `psutil.Process().memory_info().rss` logged every 100K objects).
- Memory usage at 500K objects processed equals memory usage at end of full DOM parse.
- No `elem.clear()` call anywhere in the parser loop.

**Phase to address:**
Phase 10 (NIOS parser core). The clear pattern must be established in the first version of the parser loop before any performance testing. Retrofitting it later requires re-testing the entire parsing pipeline.

---

### Pitfall 2: Extracting onedb.xml From the tar.gz Into a Temp File Before Parsing Doubles Peak Disk I/O and Fails for 2GB+ Files on Low-Disk Systems

**What goes wrong:**
The straightforward approach — `tarfile.extract("onedb.xml", path="/tmp")` then parse the extracted file — creates a full copy of the 2GB+ file on disk before parsing begins. On customer laptops with limited free space (common for enterprise field tools), this can fail with `OSError: [Errno 28] No space left on device` mid-extraction. It also doubles wall-clock time (full extraction, then full parse) compared to piping directly.

**Why it happens:**
Developers reach for `extract()` because it produces a normal file path, which iterparse accepts trivially. The streaming alternative (`tarfile.open(mode="r|gz")` + `extractfile()`) requires understanding pipe-mode limitations and passing a file-like object to iterparse, which is a less familiar pattern.

**How to avoid:**
Use pipe-streaming mode to feed the tar member's file-like object directly into iterparse, avoiding any disk copy of the inner file:

```python
import tarfile
import xml.etree.ElementTree as ET

with tarfile.open(backup_path, mode="r:gz") as tar:
    # mode "r:gz" (colon, not pipe) allows seeking within the gz;
    # use this for .tar.gz files — reserve "r|gz" for stdin/socket streams
    for member in tar.getmembers():
        if member.name.endswith("onedb.xml"):
            fileobj = tar.extractfile(member)
            if fileobj is None:
                raise RuntimeError("onedb.xml is not a regular file in archive")
            for event, elem in ET.iterparse(fileobj, events=("end",)):
                # ... parse ...
```

Important: `extractfile()` returns `None` for directories, symlinks, and special files — always guard against `None` before passing to iterparse. For `.tar.gz` files (not bare streams), `mode="r:gz"` is preferable over `mode="r|gz"` because it supports random access within the gzip stream, which is needed if the tar has multiple members and onedb.xml is not the first entry.

**Warning signs:**
- Code contains `tar.extract(...)` followed by `open(extracted_path)` before calling iterparse.
- Test on a system with <3GB free disk fails or slows dramatically due to swap.
- `extractfile()` result is used without a `None` check.

**Phase to address:**
Phase 10 (NIOS parser core). Must be the established pattern from the first implementation. Document the `None` guard explicitly in code comments.

---

### Pitfall 3: Orphaned DHCP Leases — Leases With member_id Not Present in the Member Map Silently Drop From Per-Member Attribution

**What goes wrong:**
NIOS stores DHCP leases with a `member_id` (virtual_oid integer) that references a Member object. If the Member object for a given `member_id` is missing from onedb.xml (decommissioned members, corrupted entries, or backup truncation), the lease has no resolvable hostname. If the parser drops unresolvable leases during member lookup, those leases silently disappear from the Active IP count. For the ZF reference backup, members 83, 102, 101, and 70 carry significant lease volumes — a missing member entry for any of them would silently reduce the Active IP count by tens of thousands.

**Why it happens:**
When implementing the member map (virtual_oid → hostname lookup), the natural pattern is a dict lookup: `member_map.get(lease_member_id)`. If the result is `None`, the lease is simply not attributed. A developer might then skip the lease because "it has no owner." This conflates two separate concerns: attribution (which member owns the lease for per-member reporting) and counting (whether the lease IP should appear in the global Active IP total).

**How to avoid:**
Separate attribution from counting. All leases matching the configured lease-state filter contribute to the global Active IP count regardless of whether their `member_id` resolves to a known hostname. Attribution to a named member is a reporting concern, not a counting prerequisite. Leases with unresolvable `member_id` should be bucketed as `"[unattributed]"` in per-member tables and flagged in the structural integrity report (PARSE-13):

```python
hostname = member_map.get(lease_member_id, f"[unresolved:{lease_member_id}]")
# lease still added to global IP set; hostname used only for attribution table
active_ips.add(lease_ip)
per_member_leases[hostname].append(lease_ip)
```

The structural integrity report must count and report how many leases had unresolvable member_ids so users can investigate.

**Warning signs:**
- Active IP total differs from expected count after adding the member map lookup.
- No `[unattributed]` bucket in the member attribution table when the grid has decommissioned members.
- Member attribution table total leases < total active leases in summary (leases are being dropped, not just unattributed).

**Phase to address:**
Phase 10 (NIOS parser core) and Phase 11 (counting rules). The separation of "attribution" from "counting" must be enforced in the data model, not as an afterthought during testing.

---

### Pitfall 4: Raw Lease Row Count vs. Active-IP Deduplication — Counting Lease Rows Instead of Unique IPs Produces Totals 3–4x Too High

**What goes wrong:**
The ZF reference backup contains 605,489 raw lease rows but only 168,295 unique active-only lease IPs. If the parser counts lease rows rather than unique IP addresses, the Active IP total is inflated by 3.6x. This is the primary source of the "conflicting numbers" problem described in the domain document: one report shows 600K leases, another shows 168K active IPs, and neither is wrong — they measure different things. Using the raw row count in the token formula produces a dramatically over-estimated license requirement.

**Why it happens:**
NIOS stores one row per lease lifecycle event, not one row per currently-active IP. A single IP address can have multiple lease rows: an initial assignment, a renewal, a rebind, and an expiry. The DHCP server does not delete old rows; it marks them with state fields (`active`, `static`, `backup`, `expired`, `released`). If the parser uses `len(leases)` instead of `len({lease.ip_address for lease in leases if lease.state in counted_states})`, the count is wrong. The raw count is also easy to accidentally confirm: it matches what a naive `grep -c OBJECT onedb.xml` would show.

**How to avoid:**
Always deduplicate by IP address after applying the lease-state filter. The Active IP pipeline must be:

1. Apply lease-state filter (default: `state in {"active", "static"}`)
2. Extract the IP address field from each matching lease
3. Add to a set — duplicates collapse
4. `len(set)` is the Active IP contribution from DHCP leases

The raw lease row count is useful for structural integrity reporting (PARSE-13) but must never appear in the licensing formula path.

The distinction must be preserved in the code's data model: `lease_rows_extracted` (raw count) and `lease_active_ips` (deduplicated set) must be separate fields and labeled distinctly in every output.

**Warning signs:**
- Active IP total from DHCP leases is within 10% of raw lease row count.
- No `set()` or deduplication step in the Active IP calculation code.
- Token estimates are significantly higher than customer's own estimates — ask them how they counted leases.

**Phase to address:**
Phase 11 (NIOS counting rules). The deduplication requirement must be a first-class acceptance criterion, verified against the ZF reference backup numbers (168,295 active-only IPs from 605,489 raw rows).

---

### Pitfall 5: Host Object Expansion Double-Counts DNS Records if Raw Records Are Also Extracted

**What goes wrong:**
A NIOS Host Object implicitly represents multiple DNS records: one A record (IPv4), one AAAA record (IPv6, if configured), one PTR record, and one CNAME record per alias. The REQUIREMENTS state that Host Objects must be "expanded to constituent records" for the DDI count (COUNT-01, PARSE-10). However, NIOS also stores those same A, PTR, and CNAME records as independent DNS Record objects in the backup. If the parser extracts both the Host Object's implicit records AND the independent record objects, every record contributed by a Host Object is counted twice.

**Why it happens:**
The onedb.xml flat format stores Host Objects as a distinct object type and also stores the DNS records they generate as independent objects. Developers implement "extract all DNS records" as a single pass over all record-type objects, then separately "expand Host Objects into their constituent records," without realizing the overlap. In the ZF reference backup, with 168K+ active IPs likely attributable to Host Objects, the double-count could inflate DDI totals by hundreds of thousands of records.

**How to avoid:**
Establish a precedence rule before writing any counting code: Host Object-generated records are counted via Host Object expansion only. Independent DNS record objects are skipped if they are "owned by" a Host Object (identifiable via a parent-reference property in the NIOS object model). Implementation options:

- **Option A (Preferred):** Collect all Host Object OIDs during the parse pass. When processing independent DNS record objects, check if the record's `parent_oid` is in the Host Object OID set; if so, skip it.
- **Option B (Simpler but less precise):** Count Host Objects (each expands to A + PTR + optional CNAME) and count only DNS records whose type is not A/PTR/CNAME generated by host records. This requires a "is this record auto-generated?" flag from NIOS object properties.

Document the chosen rule in the output report's footnotes (OUT-04) so auditors can verify.

**Warning signs:**
- DDI record count significantly higher than what the customer reports from NIOS admin UI.
- A/PTR/CNAME records outnumber all other record types by an unexplained ratio.
- Adding a filter to exclude Host Object-owned records reduces DDI count by a large percentage.
- No "Host Object parent OID" check anywhere in the record extraction code.

**Phase to address:**
Phase 11 (NIOS counting rules). The deduplication logic for Host Object expansion must be in the counting rules specification before any implementation, verified with a small synthetic backup containing known Host Objects and their generated records.

---

### Pitfall 6: Filter Applied After Counting Instead of Before — Member Whitelist/Blacklist Does Not Affect Object Counts

**What goes wrong:**
Member filtering (FILTER-01 to FILTER-04) is supposed to scope the analysis: only objects owned by whitelisted/non-blacklisted members should be counted. If the filter is applied to the member attribution table only (for display purposes) but not to the object extraction pipeline, the DDI counts, Active IP counts, and token totals still include objects from excluded members. The per-member table shows the correct subset of members, but the summary totals are wrong — they represent the entire grid, not the filtered scope.

**Why it happens:**
Filtering is often implemented as a display-time concern ("show only these rows in the table") rather than a data-pipeline concern ("only process these objects"). A developer builds the full counts first, then filters the member table for the output. This is a natural separation of concerns mistake: the member table looks correct in isolation, but the totals that feed the token formula are unconstrained.

**How to avoid:**
Filter must be applied at object ingestion time — during the parse pass, not after counts are accumulated. The effective member set (after whitelist/blacklist resolution) must be computed before any counting begins:

```python
# Phase 1: Build member map (all members)
member_map = extract_all_members(fileobj)

# Phase 2: Apply filter — produce effective_members set
effective_members = apply_filter(member_map, whitelist_patterns, blacklist_patterns)

# Phase 3: Parse objects — only accumulate objects whose member_id is in effective_members
for obj in parse_objects(fileobj):
    if obj.member_id in effective_members:
        accumulate(obj)
```

Note the two-pass implication: member objects must be extracted before the main object parse so the effective member set is available during the single parse pass. This requires either a two-pass read of onedb.xml or storing Member objects first (they appear at a predictable location in the file) and relying on the known file structure.

The structural integrity report must log: total members found, members matched by filter, objects excluded by filter (count per object type), so auditors can verify the filter worked correctly (FILTER-04).

**Warning signs:**
- Changing the whitelist/blacklist has no effect on summary token totals.
- Member attribution table row count changes with filter, but total tokens do not change.
- Filter configuration is stored/logged but not passed to the object extraction function.

**Phase to address:**
Phase 10 (NIOS parser core, two-pass member extraction) and Phase 11 (counting rules, filter-before-count enforcement). The filter-first requirement must be enforced by the data model — the counting functions should only receive pre-filtered objects.

---

### Pitfall 7: Dual Token Formula Misapplication in Hybrid Scenario — Applying the Wrong Rate to the Wrong Member Group

**What goes wrong:**
The hybrid UDDI view (SCEN-02) applies two different token formulas:
- NIOS-remaining members: DDI/50 + IPs/25 + Assets/13 (NIOS Object rates)
- NIOSX-migrated members: DDI/25 + IPs/13 + Assets/3 (native UDDI rates)

A subtle mistake: applying the formulas to the correct counts but using the wrong divisors (e.g., treating NIOS-remaining objects with native UDDI rates because the existing `token_calculator.py` only has native rates hardcoded at `DDI_PER_TOKEN = 25`). Since the existing calculator is used for all cloud discovery with native rates, extending it for NIOS without adding the NIOS Object formula variant will silently apply the wrong (higher) rates to NIOS-remaining members, overestimating their token contribution by 2x.

**Why it happens:**
The existing `token_calculator.py` has three constants (`DDI_PER_TOKEN = 25`, `IPS_PER_TOKEN = 13`, `ASSETS_PER_TOKEN = 3`) and a single `calculate_tokens()` function. It is tempting to reuse `calculate_tokens()` directly for NIOS analysis because the function signature is generic. But the NIOS Object formula has different divisors, and there is no parameter to select which formula to apply. A developer might pass the NIOS counts to the existing function without realizing the divisors are wrong for the NIOS Object case.

**How to avoid:**
Add a `formula` parameter or a separate function for the NIOS Object formula:

```python
# Existing (native UDDI)
DDI_PER_TOKEN_NATIVE: int = 25
IPS_PER_TOKEN_NATIVE: int = 13
ASSETS_PER_TOKEN_NATIVE: int = 3

# New (NIOS Object / NIOS-remaining in hybrid UDDI)
DDI_PER_TOKEN_NIOS: int = 50
IPS_PER_TOKEN_NIOS: int = 25
ASSETS_PER_TOKEN_NIOS: int = 13
```

The hybrid scenario output must show both formula types in the output side-by-side, making it auditable which formula was applied to which member group (OUT-02, OUT-04). The token formula constants must be version-controlled and referenced in the report header (OUT-05) so that formula changes between runs are unambiguous.

Also: the hybrid totals must not simply sum native + NIOS counts and run through a single formula — that would produce a meaningless blended divisor. The two groups must be calculated separately and their token totals summed.

**Warning signs:**
- NIOS-remaining member tokens equal approximately 2x what the customer expects from their current NIOS sizing.
- Hybrid scenario total equals "Current grid" total (indicates both are using the same formula).
- No `NIOS Object` vs `UDDI native` label on individual formula outputs in the report.
- `calculate_tokens()` called with NIOS counts without a formula variant parameter.

**Phase to address:**
Phase 11 (NIOS counting rules) and Phase 12 (scenario views and output). The NIOS Object formula constants must be added to the token calculator before hybrid scenario calculation is implemented. A unit test should verify that the same input counts produce different token totals under each formula.

---

### Pitfall 8: FastAPI UploadFile Is Closed Before the Background Thread Reads It — Large tar.gz Parsing Fails Silently

**What goes wrong:**
The dashboard NIOS Analysis tab will accept a `.tar.gz` upload and kick off parsing. The natural implementation pattern — accept `UploadFile`, pass it to a background task via `asyncio.to_thread()` or `BackgroundTasks.add_task()`, parse inside the thread — fails because FastAPI (Starlette) closes the `UploadFile` temporary file after the HTTP request handler returns. By the time the background thread begins reading, the file object is already closed. The parse fails with a file-closed error, but because it runs in a background thread, the error may not surface visibly in the dashboard UI.

**Why it happens:**
FastAPI's `UploadFile` wraps a `SpooledTemporaryFile`. Starlette's request lifecycle closes this file when the response is sent, which happens before background tasks execute for non-trivial operations. This behavior changed in FastAPI v0.106.0 and has been confirmed as a known issue (GitHub discussion #10936). The background task receives a reference to a closed file handle.

For the existing `_run_scan_pipeline()` pattern in `scan.py`, cloud scans are dispatched via `loop.run_in_executor()` with no file to pass. NIOS parsing requires passing a file path or file content, which changes the threading model.

**How to avoid:**
Save the uploaded file to a known path on disk within the request handler (before returning), then pass the path (not the file handle) to the background task:

```python
import shutil, tempfile, pathlib

@router.post("/api/nios/upload")
async def nios_upload(request: Request, file: UploadFile = File(...)):
    # Save to disk inside the request handler — before any background dispatch
    tmp_path = pathlib.Path("output") / "nios_uploads" / file.filename
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # Pass path, not file handle, to background thread
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _run_nios_pipeline, scan_manager, str(tmp_path), event_bridge)

    return JSONResponse({"status": "started"})
```

The disk save itself must be streamed in chunks (via `shutil.copyfileobj`) to avoid loading the 2GB+ file into memory. Cleanup of the temporary file should happen after parsing completes, not in the request handler.

**Warning signs:**
- `ValueError: I/O operation on closed file` in background thread logs.
- NIOS parse starts, produces zero objects, and terminates without error.
- Background task receives `UploadFile` directly rather than a `str` path.
- Dashboard shows "analysis started" but results page never populates.

**Phase to address:**
Phase 13 (dashboard integration, NIOS tab). The upload-to-disk-then-background-thread pattern must be established in the first upload endpoint implementation. This pattern also aligns with the existing `_run_scan_pipeline()` executor dispatch in `scan.py`.

---

### Pitfall 9: SpooledTemporaryFile Spool Limit — Files Under 1MB Parse Fine in Dev, 2GB Files Fail or Are Radically Slower in Production

**What goes wrong:**
FastAPI's `UploadFile` uses a `SpooledTemporaryFile` with a 1MB in-memory spool threshold. Files smaller than 1MB are held entirely in RAM; files larger than 1MB are spooled to a temporary file on disk. For a 2GB `.tar.gz` upload, the spool transition happens early and the file is on disk — but the read interface changes: operations on the spooled temp file may behave differently across platforms and Python versions (a known issue: `spool_max_size` parameter was ignored in FastAPI through at least v0.100, tracked in GitHub issue #5777).

The practical consequence: in development, testing with a small backup file (under 1MB) produces fast, in-memory behavior. In production, the customer uploads a 150MB+ tar.gz and the behavior is different — writes to disk, reads from disk, potentially with OS temp directory space constraints.

**Why it happens:**
Developers test with small sample files. The spooling behavior is internal to Starlette and not visible in the endpoint code. There is no explicit error when the spool limit is exceeded — it silently switches from memory to disk.

**How to avoid:**
Do not rely on `UploadFile.file` beyond reading it to save to a known path. Once saved to a controlled location (see Pitfall 8), use that path exclusively for all subsequent operations. For the NIOS upload endpoint:
1. Stream the upload to a known output path using `shutil.copyfileobj(file.file, dest_file, length=1024*1024)` (1MB chunks).
2. Close the `UploadFile` immediately after saving.
3. All subsequent parsing uses the saved path, not the `UploadFile`.

Test specifically with files of 1MB, 10MB, 100MB, and 200MB to verify behavior across the spool boundary.

**Warning signs:**
- Tests only use small backup files (< 1MB).
- Code reads from `file.file` multiple times (SpooledTemporaryFile is not rewindable after spooling without explicit `.seek(0)`).
- No explicit chunk-size argument to `shutil.copyfileobj` (defaults to 16KB, adequate but worth making explicit for a 2GB file).

**Phase to address:**
Phase 13 (dashboard integration, NIOS upload endpoint). Include a file-size test in the NIOS upload acceptance criteria.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `iterparse` without `elem.clear()` | Simple code, no lifecycle management | OOM on files > 200MB; process killed on 2GB files | Never — always add clear pattern |
| Extracting onedb.xml to disk before parsing | Trivial file path handling | Doubles disk I/O; fails if free space < file size | Only for files < 50MB in dev/test environments |
| Counting lease rows instead of unique IPs | One-liner count | 3–4x overcount on Active IPs; incorrect token totals | Never in production counting code |
| Reusing existing `calculate_tokens()` for NIOS Object formula | No new code | Silent 2x over-estimation of NIOS-remaining tokens | Never — add formula variant before any NIOS calculation |
| Passing `UploadFile` to background task | No disk intermediate needed | File closed before background task reads it (FastAPI v0.106+) | Never — save to disk first |
| Two-pass file parse for member map + objects | Requires two reads of same tar.gz stream | Needed to resolve member IDs before counting objects | Acceptable — document the two-pass design explicitly |
| Single-pass parse with deferred member resolution | One read of the tar.gz | Member attribution incomplete until post-processing; leases counted before member filter applied | Acceptable only if filter-application is verified to still be correct in single-pass mode |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `token_calculator.py` (existing) | Passing NIOS counts to `calculate_tokens()` which uses native UDDI divisors (25/13/3) | Add `calculate_nios_tokens()` function with NIOS Object divisors (50/25/13); use formula-select parameter for hybrid scenario |
| `scan.py` `_run_scan_pipeline()` (existing) | Assuming NIOS parsing fits the cloud scan executor pattern directly | NIOS parsing is synchronous CPU/IO-bound work and fits `run_in_executor`; however, it receives a file path not cloud credentials, so it needs a separate `_run_nios_pipeline()` function |
| `ScanManager` state machine (existing) | Adding NIOS state to the cloud `ScanState` enum | NIOS analysis is a separate workflow; use a separate `NiosAnalysisState` or a distinct analysis manager rather than coupling NIOS to cloud scan lifecycle |
| `EventBridge` SSE stream (existing) | Sending NIOS parse progress on the same event channel as cloud scan progress | Define NIOS-specific event names (`nios_progress`, `nios_complete`) to avoid cross-contamination with in-progress cloud scans |
| `xlsx_report.py` (existing) | Extending the existing CloudResource-based report with NIOS sheets | NIOS output is structurally different (member attribution table, scenario comparison columns, formula footnotes); write a separate `nios_xlsx_report.py` rather than extending the cloud one |
| `categorizer.py` DDI_TYPES set (existing) | Adding NIOS resource types to the cloud DDI_TYPES set | NIOS resources are not `CloudResource` instances; they have different schemas. Do not conflate the two — NIOS counting lives in its own `nios_counter.py` module |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| No `elem.clear()` in iterparse loop | Memory grows linearly during parse; process killed before completing 2GB file | Add `elem.clear()` after processing each `<OBJECT>` element; also clear root's child list | Files > 200MB |
| Building a `set` of all 605K+ lease IP strings simultaneously | Memory spike at Active IP deduplication step | Process leases in streaming fashion; use a set that grows incrementally during the parse pass, not a post-parse deduplication over a complete list | Files with > 500K leases |
| Two-pass parse on a tar.gz (first for members, second for objects) | Parse wall time doubles vs. single-pass | If the tar.gz is small enough to hold in memory, extract onedb.xml to a temp file on the first pass and reuse it for the second pass; or pre-read all Member objects (they appear early in the file) into a dict before the main parse loop | Files > 2GB where disk is constrained |
| Blocking iterparse in an async FastAPI handler | FastAPI event loop blocked; dashboard unresponsive during parse | Always run the NIOS parse pipeline in a background thread via `asyncio.to_thread()` or `run_in_executor()`, same pattern as `_run_scan_pipeline()` | Any file size — even 100KB parses are slow if blocking the event loop |
| Building per-member full object lists before filtering | Memory proportional to full grid size, not filtered size | Apply member filter during the parse pass; do not accumulate all objects then filter | Grids with > 1M objects where filtering reduces scope by > 50% |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Accepting any `.tar.gz` upload without validating the inner file is `onedb.xml` | Path traversal: a malicious tar could contain `../../etc/passwd` as a member name | Always use `member.name` validation before calling `extractfile()`: check that the path does not contain `..` or absolute components. Use `tarfile.TarFile.extractall()` filter parameter (Python 3.12+) or manual path sanitization |
| Storing uploaded `.tar.gz` files in the web-accessible static directory | Customer backup data (hostnames, IP addresses, DHCP leases) accessible to anyone who knows the URL | Store uploads outside the static mount: use `output/nios_uploads/` or a system temp directory, never `dashboard/static/` |
| Logging NIOS object property values in debug output | NIOS backup contains customer hostnames, IP addresses, and network topology; debug logs may be sent to support | Sanitize log output: log object counts and types, not property values. Use `--debug-nios` flag that is off by default |
| Not cleaning up uploaded `.tar.gz` after parsing | Backup file remains on customer machine in tool output directory indefinitely | Delete the uploaded tar.gz after parsing completes successfully; on error, retain it for diagnostics but document its presence. Never retain in web-accessible paths |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing raw lease row count (605K) in the UI without labeling it as "raw rows, not active IPs" | Users panic at the number and distrust all subsequent metrics | Always label counts: "Raw lease rows: 605,489 — Active IPs (dedup): 168,295" with an explanatory tooltip |
| No progress indication during multi-minute parse of 2GB file | User thinks the dashboard has hung; refreshes and loses parse state | Emit SSE progress events every 100K objects processed (object count, elapsed time, estimated remaining time) |
| Showing token totals before explaining what formula was applied | Customer challenges the numbers without context for defense | Always show: formula name, divisors used, object counts, then token totals — in that order, in the report and in the UI summary |
| Not distinguishing "no migration split defined" from "all members on NIOS" in hybrid view | Hybrid view with no migration split silently produces the same output as the Current Grid view | Require an explicit migration split before enabling the Hybrid view; show a clear "No migration split defined — configure in Step X" message |
| Glob pattern filter matching no members fails silently | User defines a whitelist pattern with a typo; zero members match; analysis runs on an empty dataset and reports zero tokens | Validate filter results before running analysis: if whitelist matches zero members, abort with "Whitelist pattern matched 0 members — verify patterns" error |

---

## "Looks Done But Isn't" Checklist

- [ ] **iterparse memory management:** Parser loop calls `elem.clear()` after every `<OBJECT>` element AND clears the root element's child list — verify with `psutil` memory tracking at 100K, 500K, and 2.5M objects
- [ ] **Lease deduplication:** Active IP count from DHCP leases is a `len(set)` of unique IPs, not `len(list)` of lease rows — verify against ZF reference values (168,295 active-only from 605,489 rows)
- [ ] **Host Object expansion deduplication:** DDI count from Host Objects does not overlap with count from independent A/PTR/CNAME record objects — verify with a synthetic backup containing known Host Objects
- [ ] **Filter-before-count:** Changing whitelist/blacklist configuration changes both the member attribution table AND the summary DDI/IP/token totals — verify that totals are not pre-computed and cached before filter application
- [ ] **Dual formula separation:** NIOS-remaining member tokens use divisors 50/25/13, NIOSX-migrated member tokens use 25/13/3 — verify with a known split that each formula is applied to the correct group
- [ ] **tar.gz streaming:** Parsing does not extract onedb.xml to disk — verify with a 200MB+ backup that no temp file of the inner XML appears in `/tmp` or `output/`
- [ ] **UploadFile background task:** Background parse thread receives a file path string, not a `UploadFile` or `SpooledTemporaryFile` — verify that parse succeeds when the HTTP connection is closed before parse completes
- [ ] **Orphaned lease handling:** Leases with unresolvable `member_id` appear in global Active IP count AND in an `[unattributed]` row of the member attribution table — verify by testing with a backup that has a removed member
- [ ] **Structural integrity report:** Parser reports missing object families, unresolvable member references, and raw vs. unique IP counts — verify PARSE-13 output matches known ZF reference values

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| OOM from missing `elem.clear()` | HIGH | Add `elem.clear()` to parser, re-test from scratch; no partial results recoverable |
| Lease row count used instead of unique IPs | HIGH | Rewrite Active IP calculation; all previously generated reports have wrong numbers and must be regenerated |
| Double-count from Host Object expansion | HIGH | Fix counting rule; all reports must be regenerated; may require customer re-briefing if numbers were shared |
| Filter applied post-count | MEDIUM | Restructure pipeline to filter at ingestion; re-run analysis with correct pipeline |
| Wrong formula in hybrid scenario | MEDIUM | Add NIOS Object formula constants; re-calculate and regenerate report |
| UploadFile closed before background task reads | LOW | Switch to file-path dispatch pattern; no data loss, just fix the upload handler |
| Orphaned leases silently dropped | MEDIUM | Add `[unattributed]` bucket to attribution; re-run; total may change if orphaned leases were excluded from counting |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| iterparse memory (no `elem.clear()`) | Phase 10: NIOS parser core | Memory profiling test: parse 2.5M-object file; verify RSS stays under 500MB |
| tar.gz disk extraction instead of streaming | Phase 10: NIOS parser core | Integration test: parse large backup; verify no temp XML file created |
| Orphaned leases dropped from count | Phase 10: NIOS parser core | Unit test: backup with missing member; verify active IP count includes orphaned lease IPs |
| Lease row count vs. unique IP count | Phase 11: NIOS counting rules | Acceptance test: ZF reference backup produces 168,295 active-only IPs, not 605,489 |
| Host Object expansion double-count | Phase 11: NIOS counting rules | Acceptance test: synthetic backup with known Host Objects; DDI count matches expected expansion |
| Filter applied after counting | Phase 10/11: parser + counting | Functional test: change whitelist; verify token totals change to match filtered scope |
| Dual formula misapplication | Phase 11: counting rules + Phase 12: scenarios | Unit test: same counts produce different tokens under each formula; hybrid total = NIOS tokens + NIOSX tokens |
| UploadFile closed before background task | Phase 13: dashboard NIOS tab | Integration test: upload large file; close browser tab before parse starts; verify parse completes from saved path |
| SpooledTemporaryFile spool limit | Phase 13: dashboard NIOS tab | Upload tests at 1MB, 10MB, 100MB, 200MB file sizes; verify consistent behavior |
| Path traversal in tar.gz upload | Phase 13: dashboard NIOS tab | Security test: craft tar.gz with `../` path member; verify rejection before extraction |
| Wrong ScanManager/EventBridge coupling | Phase 13: dashboard NIOS tab | Integration test: run cloud scan and NIOS analysis concurrently; verify no SSE event cross-contamination |

---

## Sources

- CPython issue #102055: [ElementTree.iterparse fails to free unused elements](https://github.com/python/cpython/issues/102055) — root cause of iterparse memory non-release
- CPython issue #35502: [Memory leak in xml.etree.ElementTree.iterparse](https://bugs.python.org/issue35502) — historical context, same root cause
- CPython issue #125397: [Resource leak in iterparse when exiting loop early](https://github.com/python/cpython/issues/125397) — early-break resource leak
- CPython issue #102120: [tarfile's cache balloons in memory when streaming a big tarfile](https://github.com/python/cpython/issues/102120) — TarFile.members internal cache growth
- FastAPI discussion #10936: [Using UploadFile together with BackgroundTasks results in unexpected behavior](https://github.com/fastapi/fastapi/discussions/10936) — UploadFile closed before background task
- FastAPI issue #5777: [`spool_max_size` is ignored in UploadFile](https://github.com/fastapi/fastapi/issues/5777) — SpooledTemporaryFile spool limit not honored
- [Python tarfile official docs](https://docs.python.org/3/library/tarfile.html) — `extractfile()` returns `None` for non-regular members; pipe mode vs. seekable mode distinction
- [lxml performance benchmarks](https://lxml.de/performance.html) — iterparse throughput comparison vs. stdlib ElementTree
- [do_not_commit/CLAUDE.md](./do_not_commit/CLAUDE.md) — ZF reference backup validated numbers (2.5M objects, 605,489 raw lease rows, 168,295 active-only IPs), domain counting rules, member attribution requirements
- `.planning/REQUIREMENTS.md` — PARSE-02 through PARSE-13, COUNT-01 through COUNT-06, FILTER-01 through FILTER-04
- `.planning/PROJECT.md` — dual token formula constants, validated reference data

---
*Pitfalls research for: NIOS Grid backup parsing & hybrid UDDI licensing estimation (v1.1)*
*Researched: 2026-02-28*

---

---

# v1.4 Pitfalls: Per-Account Attribution Tables and Per-Family NIOS Breakdown

**Domain:** Adding per-account attribution tables (cloud) and per-family DDI breakdown (NIOS) to an existing FastAPI+HTMX tool
**Researched:** 2026-03-03
**Confidence:** HIGH — derived directly from reading the existing codebase (`pages.py`, `scan.py`, `counter.py`, `scenarios.py`, `nios_manager.py`, `complete.html`, `summary.html`). All pitfalls are code-grounded, not speculative.

---

## Critical Pitfalls

### Pitfall A1: Cloud Per-Account Token Total Computed Differently in Summary vs. Attribution Table

**What goes wrong:**
The `_compute_summary()` function in `pages.py` derives grand-total tokens by summing raw DDI/IP/asset counts across all accounts and calling `calculate_tokens(total_ddi, total_ips, total_assets)`. The per-account table sums `result["total_tokens"]` from individual `calculate_account_tokens()` calls. Because `calculate_tokens()` uses ceiling division — `math.ceil(count / divisor)` — the sum of per-account ceilings is always greater than or equal to the ceiling of the sum. This means the "Total" row of the attribution table will routinely exceed the grand-total shown in the summary card, even though both figures are computed from the same underlying data.

Example: two accounts each with 12 DDI objects. Each account: `ceil(12/25) = 1` token. Sum = 2 tokens. Grand total via single call: `ceil(24/25) = 1` token. The attribution table footer would show 2 but the hero number shows 1. Enterprise auditors will flag this immediately.

**Why it happens:**
It is natural to add a footer row to the attribution table that sums the `total_tokens` column. The discrepancy is a fundamental property of ceiling division, not a bug in either calculation. The existing code already has this split: `_compute_summary()` computes a grand total via a single `calculate_tokens()` call on aggregated counts, while `per_account_details` lists per-account results from individual calls. If the template sums the per-account tokens column and shows it as a total, the number will not match the hero summary card.

**How to avoid:**
Do not show a "Total tokens" footer in the per-account attribution table. Instead, display a note: "Token totals are computed on the combined count across all accounts — summing per-account token rows will exceed the actual total due to ceiling division." Alternatively, omit the per-account token column entirely and add a "% of total" column to show relative contribution without implying summability.

The existing `complete.html` member attribution table for NIOS already handles the analogous IP case correctly: it shows a subtitle warning that per-member IP counts are "not summable." Follow the same pattern for cloud per-account token contribution.

**Warning signs:**
- A "Total" row at the bottom of the attribution table sums the Tokens column.
- The Total row value in the table does not match the hero token number in the summary card.
- Customers ask "why do the rows add up to more than your total?".

**Phase to address:**
v1.4 Phase (Cloud per-account attribution table implementation). The warning must be in the initial template design, not added after an auditor complains.

---

### Pitfall A2: Cloud Per-Account IP Counts Are Already Deduplicated Per-Account but Summing Across Accounts Double-Counts Cross-Account Shared IPs

**What goes wrong:**
The IP deduplication in `deduplicate_ips_per_vpc()` produces per-account deduplicated counts stored in `ip_dedup["per_account"]`. These are the values used in `calculate_account_tokens()` for each account. However, if the attribution table shows an "Active IPs" column with a footer that sums these per-account values, the result will double-count any IP address that appears in multiple accounts (e.g., RFC1918 addresses like 10.0.0.1 that are reused across VPCs in different accounts).

The existing global deduplication (`global_ip_set` used in the grand total) prevents this double-count for the hero number. But the per-account attribution table footer would undo that deduplication.

**Why it happens:**
The developer adds a "sum" footer row to the IPs column for completeness, not realizing that IP deduplication is per-account (not cross-account) in the current implementation. The per-account IP counts are themselves deduplicated within each account's VPCs, but accounts can share private IP space.

**How to avoid:**
Same pattern as Pitfall A1 for tokens: do not show a summable IP total in the attribution table footer. Show a note: "Per-account Active IP counts are deduplicated within each account. Cross-account IP totals are not shown here — see the summary card for the globally deduplicated figure." For DDI counts, a footer IS summable (DDI objects cannot be shared across accounts), so a DDI total footer is correct. Differentiate clearly: DDI footer = summable, IP footer = not summable.

**Warning signs:**
- Attribution table has an IP footer that sums per-account values.
- The IP footer value exceeds the summary card IP total.
- No distinction between DDI (summable) and IPs (not summable across accounts) in the table footer.

**Phase to address:**
v1.4 Phase (Cloud per-account attribution table). Establish the summability rules in the template specification before coding: DDI sums correctly; IPs do not.

---

### Pitfall A3: Cloud Provider Terminology Inconsistency Across the Table and the Rest of the UI

**What goes wrong:**
AWS uses "Account" (12-digit account ID), Azure uses "Subscription" (UUID), and GCP uses "Project" (string project ID). The existing `resource.account_id` field stores all three uniformly as strings. If the attribution table header says "Account" and the table contains Azure subscription UUIDs or GCP project IDs, customers will ask why their Azure subscription is labeled "Account." The UI already uses the generic word "Account" throughout (e.g., "Account ID" column in the results table), which is technically correct but providers' own documentation uses their specific terminology.

**Why it happens:**
The cloud discovery layer stores everything in a unified `account_id` field. Templates that call it "Account" are not wrong per the data model, but enterprise customers who know their Azure estate as "subscriptions" or their GCP estate as "projects" may be confused when auditing output alongside their provider console.

**How to avoid:**
Two options: (1) Use "Account / Subscription / Project" as the column header, with a note that AWS shows account IDs, Azure shows subscription IDs, and GCP shows project IDs. (2) Detect provider from the row's `provider` field and use the provider-appropriate label per row. Option 2 is better for large mixed-provider tables but requires per-row conditional rendering in Jinja2. A simple approach: a helper dict `{"aws": "Account", "azure": "Subscription", "gcp": "Project"}` applied in the template per row.

For the table heading, a tooltip or caption explaining the terminology mapping is sufficient if per-row labels add too much visual noise.

**Warning signs:**
- Attribution table column header says "Account ID" for all rows regardless of provider.
- Azure rows show UUIDs under a column labeled "Account" without any explanation.
- GCP rows show project-format strings mixed with AWS numeric IDs, no label differentiation.

**Phase to address:**
v1.4 Phase (Cloud per-account attribution table template design). Decide on the naming convention upfront; retrofitting it after the table is built is purely cosmetic work but creates unnecessary revision cycles.

---

### Pitfall A4: Resource Type Breakdown Column Causes Template Complexity That Masks Data Integrity Errors

**What goes wrong:**
The v1.4 scope includes a "resource type breakdown" per account in the attribution table. This requires grouping counted resources by `resource_type` within each account, then rendering a compact breakdown (e.g., "EC2: 45, EKS: 12, RDS: 8"). The grouping logic in the Python route (`_compute_summary`) would need to be extended, and the template would need to either render a sub-table, a comma-separated string, or a tooltip. This added complexity significantly increases the risk of the breakdown numbers not matching the main resource count or the DDI/IP/asset tallies.

Specifically: if the breakdown counts "EC2: 45" and the DDI total for that account is 52, a sharp auditor will immediately ask what the other 7 are — leading to questions about why some resources contribute to DDI but do not appear in the breakdown.

**Why it happens:**
Resource type breakdown sounds simple but requires coordinating three different counting pathways: raw resource counts (all resources), counted resource counts (only `r.counted == True`), and DDI/IP/asset category counts. If the breakdown shows raw counts but the DDI column shows counted-only counts, the numbers appear to contradict each other.

**How to avoid:**
Be explicit about what the breakdown counts. The breakdown should count only counted resources (`r.counted is True`) grouped by `resource_type`, and should note this explicitly. Do not include skipped resources in the breakdown without a separate "skipped" count. If the breakdown is too complex to fit cleanly in a table cell without confusion, defer it — the per-account DDI/IP/Asset/Tokens columns are already the primary audit data. The breakdown is enrichment, not core data. Consider linking to the Results tab pre-filtered by account as an alternative to embedding the breakdown in the table.

**Warning signs:**
- Breakdown counts do not sum to the DDI count in the same row.
- Breakdown includes both counted and skipped resources without labeling.
- Template renders breakdown as a nested structure inside a table cell, causing visual alignment issues.

**Phase to address:**
v1.4 Phase (Cloud per-account attribution table). If resource type breakdown is in scope, define precisely which resources are counted in the breakdown before implementation. If it adds more complexity than value, scope it out.

---

### Pitfall A5: HTMX State Loss — Cloud Attribution Table Disappears on Tab Navigate-Away-and-Back

**What goes wrong:**
The cloud Summary tab (`/tab/summary`) re-computes `_compute_summary()` from `scan_manager.resources` on every request. Since `resources` is stored in `ScanManager` (in-process, in-memory), navigating away and back works fine as long as the server process has not restarted. However, the NIOS tab (and the new attribution table within it) renders state from `nios_manager.scenario_suite` which is also in-process. If the server restarts between the analysis completing and the user returning to the tab, the state is gone.

The more subtle risk: the v1.4 per-account attribution table for cloud scan may be rendered in a new template path (e.g., a separate partial route). If that partial route is invoked via `hx-get` rather than being included in the initial tab render, and the HTMX swap target resets on tab navigate-away, the attribution table will not be present when the user returns even though the scan data is still in `scan_manager.resources`.

**Why it happens:**
HTMX swaps replace the target element with the response HTML. When the user clicks away (switching tabs), the tab content is replaced by the new tab's HTML fragment. When they return, HTMX makes a fresh `hx-get` to re-render the tab. If the attribution table is a child partial that must be fetched separately and the tab template does not include it on initial render, the re-render of the tab will not include the attribution table.

**How to avoid:**
Render the per-account attribution table as part of the initial `/tab/summary` response (server-side include, not a separate HTMX partial fetch). This ensures that every tab render always includes the full content. Do not put the attribution table behind a lazy-load `hx-get` unless the lazy load is triggered unconditionally on tab load. The existing `summary.html` template already includes `per_account_details` in its context, which is the right pattern to extend.

**Warning signs:**
- Attribution table requires a separate HTMX request to populate (not included in tab initial render).
- Switching away and back to the Summary tab shows the summary cards but not the attribution table.
- An `hx-trigger="load"` on the attribution section makes a separate request that may race with tab rendering.

**Phase to address:**
v1.4 Phase (Summary tab template). Keep the attribution table in the initial tab render response, not as a lazy-loaded partial.

---

### Pitfall A6: NIOS Per-Family DDI Breakdown DDI Counts Must Sum to the Scenario DDI Total — But `families_found` Counts Raw Objects, Not Expanded DDI

**What goes wrong:**
The `IntegrityReport.families_found` dict (available via `inspect_backup()`) contains raw object counts per family. For example: `"host_object": 129930`. But the DDI counter in `counter.py` expands each `host_object` to +2 or +3 depending on whether aliases are present. So `families_found["host_object"] = 129930` does not equal the DDI contribution of host_object to the scenario total.

If the per-family breakdown table is built directly from `families_found`, it will show raw counts. If those raw counts are labeled as "DDI Objects" per family, the column will not sum to `scenario_suite.current_grid.ddi_count` because:
1. `host_object` contributes 2x or 3x per object.
2. `lease`, `fixed_address`, `host_address`, `member` are not DDI families at all — showing them with a "DDI" column label would be misleading.
3. Families with 0 objects are already excluded by the "non-zero only" requirement, which is correct.

An enterprise auditor who sums the "DDI Objects" column in the family breakdown and gets a number different from the scenario DDI total will lose trust in the entire output.

**Why it happens:**
`families_found` is the easiest data source to use — it is already computed by `inspect_backup()` and stored in `IntegrityReport`. Developers reach for it to avoid re-parsing the backup. But `families_found` is a raw count, not a DDI-adjusted count. The DDI expansion for `host_object` (and the exclusion of non-DDI families) is performed inside `count_objects()` in `counter.py`, not in `inspect_backup()`.

**How to avoid:**
The per-family breakdown must use DDI-adjusted per-family counts, not raw `families_found` counts. This requires either:

- Option A: Extend `count_objects()` to return a `per_family_ddi` dict alongside the existing `CountResult`. This adds one dict to the counter's output with keys like `"host_object": 259860` (expanded 2x from 129930 raw). This is the most accurate approach and keeps counting logic in one place.

- Option B: Compute per-family DDI from `families_found` by applying the expansion rules in the template or route:
  - For `host_object`: multiply by 2 (conservative; aliases unknown at this level)
  - For all other DDI families: use raw count as-is
  - For non-DDI families (`lease`, `fixed_address`, `host_address`, `member`, `network_view`): show raw count in a separate "Raw Objects" column, not a DDI column

Option A is preferred because it maintains a single source of truth for counting logic.

The XLS Object Counters sheet already shows raw object counts per family (not DDI-adjusted). The WebUI breakdown should be labeled "DDI Objects (adjusted for host expansion)" to distinguish it from the XLS sheet's raw counts.

**Warning signs:**
- Family breakdown table header says "DDI Objects" but sums to a number different from the scenario DDI total.
- `families_found` used directly to populate a column labeled "DDI" without host_object expansion.
- Non-DDI families (lease, fixed_address, host_address, member) appear in the breakdown with a DDI column value.

**Phase to address:**
v1.4 Phase (NIOS per-family breakdown). Decide on Option A or B before implementation. If Option A (extending CountResult), add the `per_family_ddi` dict to `counter.py` and pass it through `nios_manager` to the template.

---

### Pitfall A7: NIOS Per-Family Breakdown Must Use the Same Scenario's DDI Counts — Which Scenario?

**What goes wrong:**
The NIOS complete screen shows three scenario cards: Current Grid, Hybrid UDDI, and Full Migration. All three use the same underlying DDI count (total_ddi from CountResult) — only the formula divisors differ. So there is only one DDI total, and per-family breakdown would also be unique and not scenario-specific. However, if the UI positions the per-family breakdown below the scenario cards without making this clear, users may assume the breakdown shows DDI per-scenario, which would require three separate breakdowns with different numbers.

The confusion is compounded in the Hybrid scenario: NIOS-remaining and NIOSX-migrated members contribute different amounts of DDI (since grid-level objects always go to NIOS-remaining). A per-family breakdown does not split by member group — it shows grid-wide per-family counts. If a user assumes the breakdown applies to their NIOSX-migrated members only, they may incorrectly interpret which families drive their migration cost.

**Why it happens:**
The breakdown is rendered in a fixed location on the page. Users scan the page and assume contextual relationship between adjacent elements. Placing the family breakdown below the scenario cards implies it relates to the selected/active scenario.

**How to avoid:**
Label the breakdown explicitly: "Object Family Breakdown (all scenarios — same DDI object set is counted under different formulas per scenario)." Position it before or after the scenario cards with a clear section heading that explains it is scenario-independent. If space allows, add a sentence: "Formula divisors differ per scenario but the object counts below are identical for all three."

For Hybrid scenario specifically, note that the breakdown represents all members across the full grid — it does not split by NIOS/NIOSX group assignment.

**Warning signs:**
- Breakdown positioned immediately below a specific scenario card with no explanatory label.
- Users ask "why do these numbers differ from the Hybrid UDDI totals?"
- Breakdown header says "Current Grid Family Breakdown" implying scenario-specificity.

**Phase to address:**
v1.4 Phase (NIOS complete screen template). The section heading and explanatory text must be written into the initial template design.

---

### Pitfall A8: Passing IntegrityReport and CountResult Through nios_manager Requires API Extension — Risk of Breaking Existing Complete Screen

**What goes wrong:**
The per-family breakdown table needs either `IntegrityReport.families_found` or a new `per_family_ddi` dict (see Pitfall A6). Currently, `NiosScanManager.set_complete()` accepts `output_path` and `scenario_suite`. `IntegrityReport` is computed inside `_run_nios_pipeline()` but is not stored on the manager — it is only passed to `write_nios_xlsx_report()` and then discarded.

To render the per-family breakdown, the route handler (`tab_nios`) needs access to `families_found`. If the developer adds `integrity_report` to `NiosScanManager`, it changes the manager's API. If they instead add a separate `families_found` dict field, it also changes the manager. Either way, the existing template (`nios.html` / `complete.html`) must be updated to receive the new context variable.

The risk: if the manager API extension is done carelessly, it could introduce thread-safety issues (the lock in `NiosScanManager` must protect any new fields) or break the existing complete screen that renders without the new data.

**Why it happens:**
The natural path of least resistance is to add `self._integrity_report = None` to `NiosScanManager.__init__()` and `self._integrity_report = integrity` to `set_complete()`. This is mechanically correct but easy to forget the thread-lock wrapper, or to forget to update the `reset()` method to clear it, leaving stale data from a previous run visible on re-analysis.

**How to avoid:**
Follow the exact pattern used for `_scenario_suite`:
1. Add `self._families_found: dict | None = None` to `__init__`.
2. Add `self._families_found = None` to `reset()`.
3. Add `families_found` parameter to `set_complete()` with a thread-lock wrapper.
4. Add a `families_found` property with thread-lock.
5. Pass `families_found` from `_run_nios_pipeline()` to `set_complete()`.
6. Pass it from `tab_nios()` to the template context.

The `reset()` gap is the most common mistake — if `reset()` does not clear `_families_found`, a re-uploaded backup shows stale family data from the previous run until the new analysis completes.

**Warning signs:**
- `reset()` method does not clear `_families_found` (or `_integrity_report`).
- Thread lock not used in the new property getter.
- `tab_nios()` route passes `families_found` to context without checking for `None` — template crashes when no analysis has run.

**Phase to address:**
v1.4 Phase (NIOS manager extension and complete screen update). Use the existing `_scenario_suite` pattern as the exact template for adding any new state fields.

---

### Pitfall A9: Cloud Per-Account Attribution Table Performs Redundant Recomputation if Not Cached

**What goes wrong:**
`_compute_summary()` in `pages.py` already computes `per_account_details` — a list of per-account dicts — every time `/tab/summary` is requested. For a scan with 100+ accounts, this computation calls `deduplicate_ips_per_vpc(resources)` and `calculate_account_tokens()` for every account on every tab visit. With 100+ accounts, this is CPU-bound work that blocks the async event loop (the function is called synchronously in the async route handler).

When v1.4 adds a resource type breakdown per account, the computation grows: now `_compute_summary()` must also group resources by `resource_type` within each account. For a scan with 50,000+ resources across 100 accounts, this grouping on every tab visit is visible latency.

**Why it happens:**
The existing `_compute_summary()` was designed to be stateless and re-computed. For small scans (10 accounts, 1,000 resources), the latency is imperceptible. For large scans (100+ accounts, 50,000+ resources), the grouping and deduplication takes hundreds of milliseconds.

**How to avoid:**
Two approaches: (1) Cache the `per_account_details` result on `scan_manager` after the first computation — invalidate only when a new scan starts. Since `scan_manager.resources` is set once and not mutated after scan completion, the cached summary is stable. (2) Run `_compute_summary()` in a background thread via `asyncio.to_thread()` to avoid blocking the event loop.

The simpler fix is (1): add `_cached_summary: dict | None = None` to `ScanManager`, set it in `set_resources()`, and return it from `_compute_summary()` if already computed. The cache must be cleared in `ScanManager.start()` or `cancel()`.

For v1.4 scope, if the resource type breakdown is added to `per_account_details`, verify performance with a 100-account scan before shipping.

**Warning signs:**
- `/tab/summary` is noticeably slow (>500ms) after a large scan.
- `_compute_summary()` is called in the async route handler without `await asyncio.to_thread()`.
- Resource grouping added inside `_compute_summary()` without performance testing.

**Phase to address:**
v1.4 Phase (Cloud summary tab update). If adding resource type breakdown, benchmark `_compute_summary()` with the ZF-equivalent scale (50K resources, 87 projects) before committing the approach.

---

### Pitfall A10: NIOS Per-Family Breakdown Shows Non-DDI Families With DDI=0, Misleading Auditors Into Thinking Those Families Were Missed

**What goes wrong:**
The XLS Object Counters sheet shows all 26 families, including non-DDI families (lease, fixed_address, host_address, member) with a "Counted for DDI: No" column. The WebUI breakdown is scoped to "non-zero families only." If non-DDI families (which have non-zero raw object counts in virtually every backup) appear in the breakdown with a "DDI Objects: 0" cell, auditors will ask why 605,489 lease objects contribute 0 DDI. They will assume the counting is broken.

**Why it happens:**
If the developer uses `families_found` (all non-zero families) as the data source and renders a "DDI Objects" column for all families, every non-DDI family will show DDI=0 even though it has thousands of raw objects. The "non-zero only" filter applies to raw object counts, not DDI counts — so lease, fixed_address, host_address, and member all have large non-zero raw counts and would appear in a "non-zero only" family table.

**How to avoid:**
The per-family breakdown should show only DDI-contributing families (the 22 families in `_DDI_FAMILIES` from `counter.py`). Non-DDI families (lease, fixed_address, host_address, member) should either be excluded entirely or shown in a separate "IP Sources / Metadata" section clearly labeled as not counting toward DDI tokens.

The simplest safe approach: filter the breakdown to `family in _DDI_FAMILIES` and label the table "DDI Object Families." Add a note: "Families that contribute Active IP counts (leases, fixed addresses, host addresses) and metadata objects (members) are not shown — they are covered in the Active IP by Type section."

**Warning signs:**
- Table shows `lease` family with `DDI Objects: 0` or `DDI Objects: 605489`.
- Auditor asks "why do 605K leases contribute 0 DDI tokens?"
- "Non-zero" filter applied to raw object count rather than to DDI count (all families have non-zero raw counts).

**Phase to address:**
v1.4 Phase (NIOS complete screen template). The family filter (`_DDI_FAMILIES` or a DDI-contributing subset) must be applied before rendering, not after.

---

## Technical Debt Patterns (v1.4 Additions)

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Use `families_found` raw counts directly as DDI breakdown | No extension to CountResult needed | host_object counts wrong (2x/3x expansion missing); non-DDI families pollute table | Never — extend CountResult or apply expansion in route |
| Sum per-account token column in attribution table footer | Simple UX familiar to users | Footer exceeds grand total due to ceiling division; auditors flag discrepancy | Never — show a note instead of a sum |
| Include breakdown table as lazy-loaded HTMX partial | Faster initial tab render | Table missing on tab navigate-away-and-back; HTMX state lost between renders | Only if tab is always re-fetched (it is — tab links use hx-get) and the partial is included in the tab response |
| Skip resource type breakdown (defer it) | Simpler v1.4 scope | Feature is in scope per requirements | Acceptable if complexity outweighs value — reduces Pitfall A4 risk entirely |
| Add `families_found` to nios_manager without updating `reset()` | Faster to code | Stale family data from prior run shows after re-upload until new analysis completes | Never — always update reset() |

---

## Integration Gotchas (v1.4 Additions)

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `_compute_summary()` (existing) | Adding resource type grouping without benchmarking at scale | Test with 87-project GCP equivalent (50K+ resources) before shipping; add caching if latency >500ms |
| `complete.html` partial | Adding `families_found` context variable without guarding for `None` (no analysis run yet) | Always guard: `{% if families_found %}` before rendering the breakdown section |
| `counter.py` `_DDI_FAMILIES` | Importing `_DDI_FAMILIES` from `counter.py` into `output.py` (already done in `nios/output.py`) for family filtering | Do the same in the route or template — do not re-define the set |
| `NiosScanManager` | Adding new state fields without thread-lock wrappers | Use the existing `_scenario_suite` property as the pattern: `with self._lock:` in every getter |
| `summary.html` template | Renaming or restructuring `per_account_details` context key | Existing template uses `per_account_details` — any rename breaks the existing working summary tab |

---

## Performance Traps (v1.4 Additions)

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `_compute_summary()` called synchronously in async handler with resource type grouping | /tab/summary hangs for 2-5 seconds after large scan | Cache computed summary on scan_manager; or run in `asyncio.to_thread()` | Scans with >10K resources across 50+ accounts |
| Per-family breakdown table with 22 DDI family rows — rendered in a scrollable div | No performance issue — 22 rows is tiny | N/A | Not a concern at this data volume |
| Attribution table with 100+ account rows without virtualization | Slow initial render on low-end customer laptops | Add `max-height + overflow-y: auto` scroll container (already used in `complete.html` member table) | 100+ accounts |

---

## UX Pitfalls (v1.4 Additions)

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Cloud attribution table column header "Account" for Azure/GCP rows | Azure customers confused — they know these as "subscriptions" / "projects" | Use provider-aware label: show "Account / Subscription / Project" in the header with a tooltip, or per-row labels based on provider field |
| Per-account token column with a footer total that differs from the hero number | Auditors distrust all numbers on the page | Remove token footer or replace with a note explaining ceiling-division summability |
| NIOS family breakdown shows all 26 families including non-DDI | Auditors ask "why does lease have 0 DDI?" | Show only DDI-contributing families (22 families in `_DDI_FAMILIES`); add a caption noting IPs are covered separately |
| NIOS family breakdown positioned below scenario cards without a clear label | Users assume breakdown is scenario-specific | Add section heading: "Object Family Breakdown (applies equally to all three scenarios)" |
| Per-account table with no "Token Contribution" explanation | Customers ask how token contribution was computed | Add an inline formula derivation (same pattern as the scenario cards: "X DDI ÷ 25 = Y + ...") or at minimum a formula caption below the table |
| IPs column in attribution table with a summable footer | Cross-account IP double-count; footer exceeds summary card total | Show IPs per account without a footer sum; add a note matching the existing member attribution pattern |

---

## "Looks Done But Isn't" Checklist (v1.4 Additions)

- [ ] **Attribution table token footer:** The per-account attribution table does NOT show a "Total" footer that sums the token contribution column — verify that the footer (if any) shows only a note about ceiling division, not a sum.
- [ ] **Attribution table IP footer:** Same check for the IP column — no summable footer; verify the existing member attribution pattern ("not summable") is replicated.
- [ ] **DDI column IS summable:** The DDI column in the cloud attribution table DOES have a correct footer sum (DDI is additive across accounts) — verify this matches the grand total DDI in the summary card.
- [ ] **Per-family breakdown sums to scenario DDI total:** Sum the DDI Objects column in the NIOS family breakdown; verify it equals `scenario_suite.current_grid.ddi_count` — verify host_object expansion (2x or 3x) is applied.
- [ ] **Family breakdown excludes non-DDI families:** No lease, fixed_address, host_address, or member rows appear in the breakdown — verify by checking the rendered table against `_DDI_FAMILIES` from `counter.py`.
- [ ] **`nios_manager.reset()` clears new fields:** After a re-upload, the family breakdown table is empty/absent until new analysis completes — verify by re-uploading a second backup and checking the UI before clicking Run.
- [ ] **Provider-specific terminology:** Verify Azure rows are labeled "Subscription" (or the header is clearly generic) — check with at least one Azure subscription row in the test data.
- [ ] **Tab navigate-away-and-back:** Navigate to another tab and back to Summary/NIOS after scan completion — verify attribution table and family breakdown are still rendered without a separate HTMX action.
- [ ] **Breakdown absent when no analysis run:** With no completed scan/analysis, the attribution table section does not render (no empty table, no zero-count rows) — verify the `{% if ... %}` guard in the template.

---

## Recovery Strategies (v1.4 Additions)

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Token footer sum mismatch discovered by auditor | MEDIUM | Remove footer in template; add explanatory note; no data change needed |
| IP footer double-count discovered | MEDIUM | Remove footer; add note; same as member attribution pattern |
| family_found used directly (wrong DDI counts) | HIGH | Extend CountResult to add per_family_ddi; re-run analysis; WebUI now shows correct values; XLS unaffected |
| Non-DDI families in breakdown confuse auditors | LOW | Add family filter in route or template; re-render; no data change |
| `reset()` not clearing families_found — stale data | MEDIUM | Add to reset(); clarify that data shown is from prior run; no data loss but confusing UX |
| Provider label confusion (Account vs Subscription) | LOW | Update template column header; purely cosmetic fix |

---

## Pitfall-to-Phase Mapping (v1.4 Additions)

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Token column not summable (ceiling division) | v1.4 cloud attribution table | Verify no footer sum; verify hero number matches per-account details; test with 2 accounts each with 12 DDI |
| IP column not summable cross-account | v1.4 cloud attribution table | Verify no IP footer; confirm same note pattern as member attribution in complete.html |
| Provider terminology inconsistency | v1.4 cloud attribution table template | Visual check: Azure subscription UUID row labeled correctly |
| Resource type breakdown count mismatch | v1.4 cloud attribution table (if in scope) | Sum breakdown counts; verify equals DDI for that account |
| HTMX state loss on tab navigate-away | v1.4 summary tab template | Navigate away and back; verify table present; check with browser devtools network tab |
| NIOS family breakdown using raw counts (host_object wrong) | v1.4 NIOS complete screen | Sum family breakdown DDI column; verify equals scenario_suite.current_grid.ddi_count |
| Non-DDI families in breakdown | v1.4 NIOS complete screen | Verify lease/fixed_address/host_address/member not in rendered table |
| Stale families_found after reset | v1.4 NiosScanManager extension | Re-upload backup without running analysis; verify breakdown section absent |
| Scenario label confusion for family breakdown | v1.4 NIOS complete screen template | Check section heading is present and scenario-independent |
| Performance: _compute_summary() slow at scale | v1.4 cloud summary tab | Time /tab/summary with 87-project GCP scan equivalent |

---

## Sources (v1.4 Additions)

- Existing codebase (HIGH confidence — direct code reading):
  - `src/cloud_usage/dashboard/routes/pages.py` — `_compute_summary()` implementation, ceiling division in grand total vs. per-account subtotals
  - `src/cloud_usage/dashboard/routes/scan.py` — per-account token calculation in `_run_scan_pipeline()` via `calculate_account_tokens()`
  - `src/cloud_usage/counting/token_calculator.py` — `_ceil_div()` function confirming ceiling division behavior; `calculate_account_tokens()` and `calculate_provider_tokens()` split
  - `src/cloud_usage/nios/counter.py` — `_DDI_FAMILIES` frozenset (22 families), `host_object` expansion logic (+2 or +3), `CountResult` structure
  - `src/cloud_usage/nios/scenarios.py` — `ScenarioSuite` structure; comment confirming per-member IPs not summable; total_ips from `grid_counts.active_ip_count` only
  - `src/cloud_usage/nios/output.py` — `_ALL_FAMILIES_ORDERED` (26 families), `_UDDI_FLAG_REASON` (non-DDI families), `families_found` usage in XLS Object Counters sheet
  - `src/cloud_usage/dashboard/services/nios_manager.py` — `NiosScanManager.reset()` pattern; thread-lock pattern for all state fields
  - `src/cloud_usage/dashboard/templates/partials/nios/complete.html` — existing member attribution table with "not summable" IP warning; scenario card formula derivation pattern
  - `src/cloud_usage/dashboard/templates/pages/summary.html` — existing `per_account_details` loop; per-provider breakdown table; download section
  - `.planning/PROJECT.md` — v1.4 scope definition, token formula constants, ZF reference scale (304,730 unique Active IPs, 87-project GCP context)

---
*Pitfalls research for: v1.4 Audit Depth — per-account attribution tables and per-family NIOS breakdown*
*Researched: 2026-03-03*
