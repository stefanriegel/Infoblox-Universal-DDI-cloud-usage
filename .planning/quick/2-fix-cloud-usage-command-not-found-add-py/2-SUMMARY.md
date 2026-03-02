---
phase: quick-2
plan: "01"
subsystem: packaging
tags: [packaging, entry-point, pyproject, setup-scripts]
dependency_graph:
  requires: []
  provides: [cloud-usage-console-script]
  affects: [setup_venv.sh, setup_venv.ps1, setup_venv.bat, README.md]
tech_stack:
  added: [setuptools>=68, pyproject.toml]
  patterns: [PEP 517 editable install, console_scripts entry point]
key_files:
  created:
    - pyproject.toml
  modified:
    - setup_venv.sh
    - setup_venv.ps1
    - setup_venv.bat
    - README.md
decisions:
  - "pyproject.toml only — no setup.py or setup.cfg needed; setuptools>=68 supports pure-pyproject editable installs"
  - "dependencies = [] in [project] to avoid duplicating requirements.txt into pyproject.toml"
  - "[tool.setuptools.packages.find] where = [src] so setuptools discovers cloud_usage under src/"
metrics:
  duration: "~2 min"
  completed: "2026-03-02"
  tasks_completed: 2
  files_changed: 5
---

# Quick Task 2: Fix cloud-usage command-not-found — add pyproject.toml Summary

**One-liner:** Added `pyproject.toml` with `cloud-usage = "cloud_usage.cli:main"` entry point and `pip install -e .` to all three setup scripts plus README manual setup sections.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create pyproject.toml with cloud-usage entry point | 065006a | pyproject.toml |
| 2 | Add pip install -e . to all three setup scripts and README manual setup | 517fcd2 | setup_venv.sh, setup_venv.ps1, setup_venv.bat, README.md |

## What Was Built

### pyproject.toml

Created at project root with:
- `[build-system]`: setuptools>=68, wheel, setuptools.build_meta backend
- `[project]`: name=cloud-usage, version=1.2.0, requires-python>=3.9, dependencies=[]
- `[project.scripts]`: `cloud-usage = "cloud_usage.cli:main"`
- `[tool.setuptools.packages.find]`: `where = ["src"]`

### Setup Script Updates

All three scripts now run `pip install -e .` immediately after `pip install -r requirements.txt`:
- `setup_venv.sh` (line 49): `pip install -e .`
- `setup_venv.ps1` (line 62): `python -m pip install -e .`
- `setup_venv.bat` (line 36): `python -m pip install -e .`

### README Manual Setup

Both code blocks (macOS/Linux and Windows) in the Manual Setup section now end with `pip install -e .`.

## Verification

End-to-end check passed using project venv (Python 3.14, pip 26.0.1):
- `pip install -e .` succeeded with `pyproject.toml`
- `venv/bin/cloud-usage --help` printed usage without ImportError
- Entry point registered at `venv/bin/cloud-usage`

## Decisions Made

- **No setup.py duplication:** `pyproject.toml` alone is sufficient; setuptools>=68 handles editable installs via pyproject.toml without `setup.py`.
- **Empty dependencies:** `dependencies = []` in `[project]` avoids duplicating `requirements.txt`; users still run `pip install -r requirements.txt` first.
- **src layout discovery:** `[tool.setuptools.packages.find] where = ["src"]` ensures `cloud_usage` package is found under `src/`.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- pyproject.toml: FOUND at project root with correct entry point
- setup_venv.sh: FOUND — contains `pip install -e .` at line 49
- setup_venv.ps1: FOUND — contains `python -m pip install -e .` at line 62
- setup_venv.bat: FOUND — contains `python -m pip install -e .` at line 36
- README.md: FOUND — contains `pip install -e .` at lines 89 and 98
- Commit 065006a: pyproject.toml
- Commit 517fcd2: setup scripts + README
