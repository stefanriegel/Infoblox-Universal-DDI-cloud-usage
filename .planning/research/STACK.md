# Stack Research

**Domain:** NIOS Grid backup parsing + UDDI token analysis (Python add-on module)
**Researched:** 2026-02-28
**Confidence:** HIGH

---

## Context: What Already Exists

This is a subsequent milestone on top of a validated Python codebase. The following are
already present and must NOT be re-added:

| Existing | Already in stack |
|----------|-----------------|
| FastAPI + Uvicorn + Jinja2 + HTMX | Web dashboard layer |
| openpyxl | XLS/XLSX multi-sheet output |
| PyYAML (via requirements) | Config parsing — see note below |
| stdlib `tarfile`, `io` | tar.gz handling — no new library needed |
| stdlib `xml.etree.ElementTree` | XML — but should be replaced for this use case (see below) |
| Pydantic v2 | Data modelling and validation |
| pytest + moto | Test framework (853 passing tests) |

The only new dependency this milestone needs is **lxml** for performant 2GB+ streaming XML
parsing. Everything else is stdlib or already installed.

---

## Recommended Stack — New Additions Only

### Core Technologies (new for v1.1)

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| lxml | >=5.3.0 | Streaming XML parse of onedb.xml (2GB+) | C-backed parser (libxml2). `iterparse` is 2-20x faster than stdlib ElementTree, handles `huge_tree=True` for files with >10M nodes, and the memory management pattern (clear processed elements + delete preceding siblings) keeps RAM flat at ~50–100MB regardless of file size. The 2GB+ onedb.xml with 2.5M flat `<OBJECT>` records is exactly the use case iterparse was designed for. Latest stable 6.0.2 (Sep 2025) has wheels for Python 3.8–3.13 on Windows, macOS, Linux. | HIGH |

### YAML Config Library — Recommendation

**Use PyYAML 6.0.3** — already present in the project's requirements.txt (implicitly, as it
is a dependency of other packages). Add it explicitly if needed.

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| PyYAML | >=6.0.2 | Parse NIOS analysis config file (migration split, filter patterns) | The config schema is simple: a flat YAML file with member lists and glob patterns. PyYAML handles this with zero ceremony. Already a transitive dependency. No comment-preservation needed (config is write-once, not round-tripped). YAML 1.1 limitations (Yes/No as bool) do not apply to member hostnames or virtual_oid lists. Latest stable 6.0.3 (Sep 2025). | HIGH |

### What NOT to Add

| Do NOT add | Why | Use instead |
|------------|-----|-------------|
| `ruamel.yaml` | Overkill for simple read-only config. Higher complexity, no benefit for a flat config file that is never round-tripped. | `PyYAML` — already in the project |
| `defusedxml` | lxml 5.x+ disables external entity expansion by default. The onedb.xml is a known trusted file from a NIOS backup. defusedxml adds a layer of protection we do not need here and does not support iterparse. | lxml with `resolve_entities=False, no_network=True` explicitly set on the parser |
| `xml.sax` (stdlib) | SAX is lower-level than iterparse, requires a ContentHandler class, and is not worth the added complexity for a flat `<OBJECT>` record stream where iterparse is cleaner code and similar or better performance. | `lxml.etree.iterparse` |
| `xml.etree.ElementTree.iterparse` (stdlib) | The stdlib iterparse has a known memory leak issue where `elem.clear()` on tag-filtered events does not release ancestor nodes, leading to unbounded memory growth on 2GB+ files. lxml's iterparse handles this correctly with explicit sibling deletion. | `lxml.etree.iterparse` |
| Any tar/gz library (python-libarchive, tarfile-stream, etc.) | Python stdlib `tarfile` handles `.tar.gz` extraction to a file-like object (`tar.extractfile(member)`) without writing to disk. No new library needed. | `import tarfile` (stdlib) |
| `pandas` for new analysis output | Already called out in existing STACK.md as overkill. openpyxl handles multi-sheet XLSX output. | `openpyxl` (already in stack) |

---

## Integration Points with Existing Stack

### tar.gz Handling — stdlib tarfile

Use `tarfile.open(path, "r:gz")` (colon mode = seeking, not streaming). This is critical:
the streaming `r|gz` mode has a known quadratic performance bug in Python's stdlib that makes
it 14x slower on gzip archives (cpython issue #121109, open as of Feb 2026). With seeking
mode, call `tar.extractfile(member)` to obtain an `io.BufferedReader` for `onedb.xml` — no
extraction to disk, no temp files.

```python
import tarfile

with tarfile.open("backup.tar.gz", "r:gz") as tar:
    member = tar.getmember("onedb.xml")
    fileobj = tar.extractfile(member)  # io.BufferedReader, no disk write
    # pass fileobj to lxml.etree.iterparse(fileobj, events=("end",), tag="OBJECT")
```

### lxml iterparse — Memory Management Pattern

The flat `<OBJECT><PROPERTY NAME="...">value</PROPERTY></OBJECT>` structure maps cleanly to
iterparse's end-event pattern. Fire on `end` for `OBJECT`, extract properties, clear the
element, and delete the preceding sibling to release parent references:

```python
from lxml import etree

parser = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    huge_tree=True,    # Required: onedb.xml nodes exceed default 5M node limit
    recover=True,      # Continue past malformed sections (backup corruption resilience)
)

for event, elem in etree.iterparse(fileobj, events=("end",), tag="OBJECT", parser=parser):
    obj_type = elem.get("type")
    props = {p.get("NAME"): p.text for p in elem}
    yield obj_type, props

    # Critical: release memory or RAM grows unboundedly on 2GB files
    elem.clear(keep_tail=True)
    while elem.getprevious() is not None:
        del elem.getparent()[0]
```

This pattern keeps memory flat at ~50–100MB while processing the full 2.5M object ZF
Friedrichshafen reference backup. Without the `while getprevious()` loop, lxml accumulates
processed elements as parent-level siblings and RAM grows linearly.

### YAML Config — Integration with existing CLI / dashboard

MIGR-01 requires a `--nios-config <config.yaml>` CLI flag. The config schema is straightforward:

```yaml
# nios_config.yaml — migration split and filters
migration_split:
  niosx:
    - "infoblox-gm.corp.example.com"
    - "infoblox-m1.corp.example.com"
  # all others default to nios

filters:
  member_whitelist: []   # empty = include all
  member_blacklist:
    - "infoblox-test-*"

lease_states:
  count: ["active", "static"]  # default
```

PyYAML parses this in three lines; no schema validation library needed for this structure.
If validation is desired, run the parsed dict through a Pydantic model (already in stack).

### XLS Output — openpyxl (already in stack)

The five-sheet report (Object Counters, DDI Objects, Active IP by Type, Scenario Comparison,
Member Attribution) maps directly to openpyxl's `Workbook` / `add_sheet` API. No new library
needed. The existing cloud provider XLS output pattern (already implemented with openpyxl) is
the model to follow.

### Token Calculator — Extend, Don't Replace

`cloud_usage/counting/token_calculator.py` implements the UDDI native formula
(`DDI/25 + IPs/13 + Assets/3`). For v1.1, add a parallel `calculate_nios_tokens()` function
in the same module with NIOS Object formula constants (`DDI/50 + IPs/25 + Assets/13`). The
`_ceil_div()` helper is already correct for both formulas. No new library; only new constants
and a new function.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| XML parser | `lxml.etree.iterparse` | `xml.etree.ElementTree.iterparse` (stdlib) | Stdlib iterparse memory leak on tag-filtered events means ancestor nodes are not freed — RAM grows unboundedly on 2GB files. lxml handles this correctly with explicit sibling deletion. |
| XML parser | `lxml.etree.iterparse` | `xml.sax` (stdlib) | SAX requires a ContentHandler class with start/end element callbacks — more code, more state to manage, no memory advantage over lxml iterparse. Not worth the complexity for a flat `<OBJECT>` record stream. |
| XML parser | `lxml.etree.iterparse` | `expat` (stdlib via `xml.parsers.expat`) | Expat is the C parser underlying stdlib ET/SAX. Using it directly bypasses Python abstractions entirely. Extremely low-level for no benefit in this use case. |
| tar.gz access | `tarfile` stdlib | `python-libarchive-c` | Additional C dependency, more complex install (especially on Windows). stdlib tarfile handles .tar.gz fully without any new dependency. |
| tar.gz access | `tarfile` stdlib (`r:gz`) | `tarfile` streaming mode (`r\|gz`) | The streaming `r\|gz` mode has a known quadratic performance bug (cpython #121109): 14x slower than seeking mode on gzip. Always use `r:gz` for local .tar.gz files. |
| YAML | PyYAML | `ruamel.yaml` | ruamel.yaml is warranted when preserving comments or round-tripping YAML is required. The NIOS config is write-once; PyYAML's simpler API is appropriate. |
| YAML | PyYAML | `tomllib` (stdlib Python 3.11+) | TOML is a reasonable alternative for the config format. YAML was specified in MIGR-01 (`--nios-config <config.yaml>`). If the requirement changes to TOML, `tomllib` is zero-dependency on Python 3.11+. |
| YAML | PyYAML | `json` (stdlib) | JSON is a valid alternative for the config file. YAML is more readable for lists of hostnames. The requirement specifies YAML. |

---

## Stack Patterns by Variant

**If the onedb.xml exceeds available RAM (e.g., on a 4GB laptop):**
- The `lxml.etree.iterparse` + `elem.clear()` + sibling deletion pattern described above
  keeps peak memory at ~50–100MB regardless of file size.
- Do not load the file into memory first — pass the `io.BufferedReader` directly to iterparse.

**If the .tar.gz contains multiple files and onedb.xml is not at root:**
- Use `tar.getmembers()` to enumerate all members, filter by `member.name.endswith("onedb.xml")`,
  then call `tar.extractfile(member)`.
- NIOS backup archives consistently place onedb.xml at the archive root, but handle the
  nested case defensively.

**If the config file uses JSON instead of YAML (customer preference):**
- stdlib `json.load()` requires zero new dependencies.
- Validate the parsed dict through the same Pydantic model as the YAML path.

**If running on Windows without C compiler (lxml wheel not available):**
- lxml distributes pre-built wheels for Python 3.8–3.13 on Windows x64 and ARM64.
- `pip install lxml` or `uv add lxml` resolves a wheel — no C compiler needed.
- Verified: lxml 6.0.2 has cp39-win_amd64, cp39-win32, cp39-win_arm64 wheels on PyPI.

---

## Version Compatibility

| Package | Min Version | Tested / Latest | Notes |
|---------|-------------|-----------------|-------|
| lxml | 5.3.0 | 6.0.2 (Sep 2025) | 5.3+ supports Python 3.8–3.12; 6.0+ adds Python 3.13 support. `huge_tree=True` available since 3.x. Minimum 5.3 for libxml2 security fixes. |
| PyYAML | 6.0.2 | 6.0.3 (Sep 2025) | 6.0 fixes the unsafe YAML loader CVE. Always use `yaml.safe_load()`, never `yaml.load()`. |
| tarfile | stdlib | Python 3.9.6 | stdlib. `extractfile()` returns `io.BufferedReader` since Python 3.x. No version pinning needed. |
| openpyxl | 3.1.5 | 3.1.5 | Already in stack. Multi-sheet workbook support stable since 3.0. |
| Python | 3.9+ | 3.12 recommended | The venv in this repo runs 3.9.6. lxml 6.0.2 and PyYAML 6.0.3 both support Python 3.8+, so no Python upgrade is forced by this milestone. The existing research STACK.md targets >=3.12 for production; the parsing module is compatible with either. |

---

## Installation

```bash
# Add lxml to project dependencies
# If using pyproject.toml (recommended per existing STACK.md):
uv add "lxml>=5.3.0"

# If using requirements.txt (current state of this repo):
pip install "lxml>=5.3.0"
```

PyYAML is either already installed (as a transitive dependency) or:

```bash
# Make it explicit:
uv add "PyYAML>=6.0.2"
# or:
pip install "PyYAML>=6.0.2"
```

No other new packages are required for the NIOS parsing milestone.

---

## Sources

- [lxml PyPI page](https://pypi.org/project/lxml/) — version 6.0.2 confirmed, Python 3.9 wheel support confirmed, HIGH confidence
- [lxml Performance Benchmarks](https://lxml.de/performance.html) — iterparse vs cElementTree benchmark numbers, HIGH confidence
- [lxml API: iterparse](https://lxml.de/api/lxml.etree.iterparse-class.html) — huge_tree, recover parameters confirmed, HIGH confidence
- [cpython issue #121109](https://github.com/python/cpython/issues/121109) — tarfile r|gz 14x slower bug, HIGH confidence (open issue, Feb 2026)
- [Python tarfile docs](https://docs.python.org/3/library/tarfile.html) — extractfile() returning io.BufferedReader confirmed, HIGH confidence
- [PyYAML PyPI page](https://pypi.org/project/PyYAML/) — version 6.0.3 confirmed, Python >=3.8 support, HIGH confidence
- [Nick Janetakis: lxml 20x faster XML parsing](https://nickjanetakis.com/blog/how-i-used-the-lxml-library-to-parse-xml-20x-faster-in-python) — practical benchmark, MEDIUM confidence
- [WebScraping.AI: lxml memory management](https://webscraping.ai/faq/lxml/what-are-the-best-practices-for-managing-memory-usage-when-using-lxml) — elem.clear() + sibling deletion pattern, MEDIUM confidence
- [WebScraping.AI: lxml security](https://webscraping.ai/faq/lxml/what-are-the-security-implications-of-using-lxml-for-parsing-untrusted-xml) — resolve_entities=False default since lxml 5.x confirmed, MEDIUM confidence

---

*Stack research for: NIOS Grid backup parsing and UDDI token analysis (v1.1 milestone)*
*Researched: 2026-02-28*
