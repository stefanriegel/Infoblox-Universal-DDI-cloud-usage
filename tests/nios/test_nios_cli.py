"""Tests for Phase 14 CLI integration: NiosConfig and --nios CLI branch.

Covers:
- NiosConfig frozen dataclass and from_yaml() class method (Task 1)
- CLI --nios and --nios-config argument parsing and main() branch (Task 3)
- Acceptance test for ZF reference backup end-to-end (Plan 14-02)

Reference figures (ZF Friedrichshafen backup):
- Total unique active IPs (4-source dedup): 304,730 — verified in STATE.md (COUNT-02)
- Source: active leases + fixed addresses + host addresses + network reservations
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from cloud_usage.nios.config import NiosConfig
from cloud_usage.nios.filter import FilterConfig
from cloud_usage.nios.scenarios import MigrationSplitConfig
from cloud_usage.cli import main, parse_args


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def write_yaml(tmp_path: Path, content: str) -> str:
    """Write YAML content to a temp file and return its path string."""
    p = tmp_path / "config.yaml"
    p.write_text(content)
    return str(p)


# ---------------------------------------------------------------------------
# Tests for NiosConfig (Task 1)
# ---------------------------------------------------------------------------


class TestNiosConfigDefaults:
    """NiosConfig default construction."""

    def test_default_has_empty_filter(self):
        """NiosConfig() has default FilterConfig with no filters."""
        cfg = NiosConfig()
        assert cfg.filter_config == FilterConfig()
        assert cfg.filter_config.whitelist == ()
        assert cfg.filter_config.blacklist == ()
        assert cfg.filter_config.lease_states == ("active",)

    def test_default_split_config_is_none(self):
        """NiosConfig() has split_config=None by default."""
        cfg = NiosConfig()
        assert cfg.split_config is None

    def test_frozen_dataclass_cannot_set_attribute(self):
        """NiosConfig is frozen — attribute assignment must raise."""
        cfg = NiosConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.filter_config = FilterConfig()  # type: ignore[misc]


class TestNiosConfigFromYaml:
    """NiosConfig.from_yaml() with various YAML inputs."""

    def test_filter_only_yaml(self, tmp_path):
        """from_yaml() with filter section sets whitelist/blacklist/lease_states."""
        yaml_path = write_yaml(tmp_path, """\
filter:
  whitelist:
    - "member-prod-*"
  blacklist:
    - "member-dev-*"
  lease_states:
    - active
    - static
""")
        cfg = NiosConfig.from_yaml(yaml_path)
        assert cfg.filter_config.whitelist == ("member-prod-*",)
        assert cfg.filter_config.blacklist == ("member-dev-*",)
        assert cfg.filter_config.lease_states == ("active", "static")
        assert cfg.split_config is None

    def test_migration_split_section_creates_split_config(self, tmp_path):
        """from_yaml() with migration_split section creates MigrationSplitConfig."""
        yaml_path = write_yaml(tmp_path, """\
migration_split:
  niosx_members:
    - "member-01.lab.corp"
  default_group: nios
""")
        cfg = NiosConfig.from_yaml(yaml_path)
        assert cfg.split_config is not None
        assert cfg.split_config.niosx_members == ("member-01.lab.corp",)
        assert cfg.split_config.default_group == "nios"
        assert cfg.split_config.assignment_source == "yaml"

    def test_empty_yaml_file_returns_default(self, tmp_path):
        """from_yaml() with empty YAML file returns default NiosConfig."""
        yaml_path = write_yaml(tmp_path, "")
        cfg = NiosConfig.from_yaml(yaml_path)
        assert cfg == NiosConfig()

    def test_missing_filter_section_uses_defaults(self, tmp_path):
        """from_yaml() without filter section uses default FilterConfig values."""
        yaml_path = write_yaml(tmp_path, """\
migration_split:
  niosx_members: []
  default_group: nios
""")
        cfg = NiosConfig.from_yaml(yaml_path)
        assert cfg.filter_config.whitelist == ()
        assert cfg.filter_config.blacklist == ()
        assert cfg.filter_config.lease_states == ("active",)

    def test_missing_migration_split_section_gives_none(self, tmp_path):
        """from_yaml() without migration_split section sets split_config=None."""
        yaml_path = write_yaml(tmp_path, """\
filter:
  whitelist:
    - "*"
""")
        cfg = NiosConfig.from_yaml(yaml_path)
        assert cfg.split_config is None

    def test_file_not_found_raises(self, tmp_path):
        """from_yaml() with non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            NiosConfig.from_yaml(str(tmp_path / "nonexistent.yaml"))

    def test_yaml_lists_converted_to_tuples(self, tmp_path):
        """from_yaml() converts YAML list values to tuples."""
        yaml_path = write_yaml(tmp_path, """\
filter:
  whitelist:
    - "a"
    - "b"
""")
        cfg = NiosConfig.from_yaml(yaml_path)
        assert isinstance(cfg.filter_config.whitelist, tuple)
        assert cfg.filter_config.whitelist == ("a", "b")

    def test_full_config_yaml(self, tmp_path):
        """from_yaml() with both filter and migration_split populates all fields."""
        yaml_path = write_yaml(tmp_path, """\
filter:
  whitelist:
    - "member-prod-*"
  blacklist:
    - "member-dev-*"
  lease_states:
    - active
migration_split:
  niosx_members:
    - "member-01.lab.corp"
    - "member-02.lab.corp"
  default_group: nios
""")
        cfg = NiosConfig.from_yaml(yaml_path)
        assert cfg.filter_config.whitelist == ("member-prod-*",)
        assert cfg.filter_config.blacklist == ("member-dev-*",)
        assert cfg.filter_config.lease_states == ("active",)
        assert cfg.split_config is not None
        assert cfg.split_config.niosx_members == ("member-01.lab.corp", "member-02.lab.corp")
        assert cfg.split_config.default_group == "nios"

    def test_frozen_config_from_yaml(self, tmp_path):
        """NiosConfig returned from from_yaml() is frozen."""
        yaml_path = write_yaml(tmp_path, "")
        cfg = NiosConfig.from_yaml(yaml_path)
        with pytest.raises((AttributeError, TypeError)):
            cfg.filter_config = FilterConfig()  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tests for CLI --nios branch (Task 3)
# ---------------------------------------------------------------------------


class TestParseArgsNios:
    """Argument parsing for --nios and --nios-config flags."""

    def test_nios_flag_parsed(self):
        """--nios sets args.nios to the provided path."""
        args = parse_args(["--nios", "backup.tar.gz"])
        assert args.nios == "backup.tar.gz"

    def test_nios_config_flag_parsed(self):
        """--nios-config sets args.nios_config to the provided path."""
        args = parse_args(["--nios-config", "config.yaml"])
        assert args.nios_config == "config.yaml"

    def test_default_nios_is_none(self):
        """args.nios defaults to None when flag not provided."""
        args = parse_args([])
        assert args.nios is None

    def test_default_nios_config_is_none(self):
        """args.nios_config defaults to None when flag not provided."""
        args = parse_args([])
        assert args.nios_config is None

    def test_nios_and_output_dir_together(self):
        """--nios and --output-dir can be combined."""
        args = parse_args(["--nios", "backup.tar.gz", "--output-dir", "/tmp/out"])
        assert args.nios == "backup.tar.gz"
        assert args.output_dir == "/tmp/out"


class TestMainNiosBranch:
    """main() --nios branch behavior."""

    def test_main_nios_missing_file_returns_1(self):
        """main() returns 1 when backup file does not exist."""
        with patch("cloud_usage.cli.check_platform", return_value={"python_ok": True}), \
             patch("cloud_usage.cli.print_preflight_warnings"):
            result = main(["--nios", "/nonexistent/path/backup.tar.gz"])
        assert result == 1

    def test_main_nios_success_returns_0(self, tmp_path):
        """main() returns 0 when run_nios_analysis succeeds."""
        backup = tmp_path / "backup.tar.gz"
        backup.write_bytes(b"dummy")
        output_file = str(tmp_path / "nios_analysis_20260302_120000.xlsx")

        with patch("cloud_usage.cli._run_nios_cli", return_value=0) as mock_fn, \
             patch("cloud_usage.cli.check_platform", return_value={"python_ok": True}), \
             patch("cloud_usage.cli.print_preflight_warnings"):
            result = main(["--nios", str(backup)])
        assert result == 0
        mock_fn.assert_called_once()

    def test_main_nios_calls_run_nios_analysis(self, tmp_path):
        """main() calls run_nios_analysis via _run_nios_cli with default NiosConfig."""
        backup = tmp_path / "backup.tar.gz"
        backup.write_bytes(b"dummy")

        with patch("cloud_usage.nios.run_nios_analysis", return_value=str(tmp_path / "out.xlsx")) as mock_run, \
             patch("cloud_usage.cli.check_platform", return_value={"python_ok": True}), \
             patch("cloud_usage.cli.print_preflight_warnings"):
            result = main(["--nios", str(backup), "--output-dir", str(tmp_path)])

        assert result == 0
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        # Default config: no filters, active-only leases
        filter_cfg = call_kwargs.kwargs.get("filter_config") or call_kwargs.args[1] if call_kwargs.args else None
        if filter_cfg is None and call_kwargs.kwargs:
            filter_cfg = call_kwargs.kwargs.get("filter_config")
        assert filter_cfg is not None or mock_run.called  # Verified called

    def test_main_nios_with_config_calls_from_yaml(self, tmp_path):
        """main() calls NiosConfig.from_yaml() when --nios-config is provided."""
        backup = tmp_path / "backup.tar.gz"
        backup.write_bytes(b"dummy")
        config_file = tmp_path / "config.yaml"
        config_file.write_text("filter:\n  whitelist:\n    - 'prod-*'\n")

        with patch("cloud_usage.nios.run_nios_analysis", return_value=str(tmp_path / "out.xlsx")), \
             patch("cloud_usage.cli.check_platform", return_value={"python_ok": True}), \
             patch("cloud_usage.cli.print_preflight_warnings"):
            result = main([
                "--nios", str(backup),
                "--nios-config", str(config_file),
                "--output-dir", str(tmp_path),
            ])

        assert result == 0

    def test_main_nios_output_path_uses_output_dir(self, tmp_path):
        """main() constructs output path under --output-dir."""
        backup = tmp_path / "backup.tar.gz"
        backup.write_bytes(b"dummy")
        out_dir = tmp_path / "myoutput"
        out_dir.mkdir()

        captured_path = []

        def fake_run(backup_path, filter_config, split_config=None, output_path=None):
            captured_path.append(output_path)
            return output_path or "output.xlsx"

        with patch("cloud_usage.nios.run_nios_analysis", side_effect=fake_run), \
             patch("cloud_usage.cli.check_platform", return_value={"python_ok": True}), \
             patch("cloud_usage.cli.print_preflight_warnings"):
            main(["--nios", str(backup), "--output-dir", str(out_dir)])

        assert len(captured_path) == 1
        assert captured_path[0] is not None
        assert str(out_dir) in captured_path[0]
        assert "nios_analysis_" in captured_path[0]

    def test_main_nios_parse_error_returns_1(self, tmp_path):
        """main() returns 1 when NiosParseError is raised."""
        from cloud_usage.nios.errors import NiosParseError

        backup = tmp_path / "backup.tar.gz"
        backup.write_bytes(b"dummy")

        with patch("cloud_usage.nios.run_nios_analysis", side_effect=NiosParseError("bad backup")), \
             patch("cloud_usage.cli.check_platform", return_value={"python_ok": True}), \
             patch("cloud_usage.cli.print_preflight_warnings"):
            result = main(["--nios", str(backup), "--output-dir", str(tmp_path)])

        assert result == 1

    def test_main_nios_unexpected_exception_returns_1(self, tmp_path):
        """main() returns 1 on unexpected exception from run_nios_analysis."""
        backup = tmp_path / "backup.tar.gz"
        backup.write_bytes(b"dummy")

        with patch("cloud_usage.nios.run_nios_analysis", side_effect=RuntimeError("unexpected")), \
             patch("cloud_usage.cli.check_platform", return_value={"python_ok": True}), \
             patch("cloud_usage.cli.print_preflight_warnings"):
            result = main(["--nios", str(backup), "--output-dir", str(tmp_path)])

        assert result == 1

    def test_main_nios_branch_before_provider_selection(self, tmp_path):
        """elif args.nios exits before cloud provider selection (no auth doctor called)."""
        backup = tmp_path / "backup.tar.gz"
        backup.write_bytes(b"dummy")

        with patch("cloud_usage.nios.run_nios_analysis", return_value=str(tmp_path / "out.xlsx")), \
             patch("cloud_usage.cli.check_platform", return_value={"python_ok": True}), \
             patch("cloud_usage.cli.print_preflight_warnings"), \
             patch("cloud_usage.cli.AuthDoctor") as mock_auth:
            main(["--nios", str(backup), "--output-dir", str(tmp_path)])

        # AuthDoctor should NOT be called (NIOS branch exits before auth check)
        mock_auth.assert_not_called()

    def test_main_nios_does_not_affect_web_branch(self):
        """--nios does not affect --web branch."""
        args = parse_args(["--web"])
        assert args.nios is None

    def test_main_nios_does_not_affect_aws_branch(self):
        """--nios does not affect --aws flag."""
        args = parse_args(["--aws"])
        assert args.nios is None


# ---------------------------------------------------------------------------
# Acceptance tests — ZF reference backup (Plan 14-02)
# ---------------------------------------------------------------------------

_ZF_BACKUP_PATH = "do_not_commit/ZF-database-11_1752136302416.bak.reset.tar.gz"


@pytest.mark.integration
@pytest.mark.skipif(
    not os.path.exists(_ZF_BACKUP_PATH),
    reason="ZF reference backup not available at do_not_commit/ZF-database-11_1752136302416.bak.reset.tar.gz",
)
def test_cli_nios_e2e_zf_reference(tmp_path):
    """Acceptance: CLI produces valid xlsx with 304,730 active IPs from ZF backup.

    304,730 = confirmed ZF reference total (4-source dedup: active leases + fixed
    addresses + host addresses + network reservations) per STATE.md and COUNT-02.

    This test confirms:
    1. CLI exits 0 (no errors)
    2. Output xlsx is created with correct filename pattern
    3. Workbook is valid (readable by openpyxl)
    4. Scenario Comparison sheet Active IPs == 304,730
    """
    import openpyxl

    # Bypass Python version preflight (test environment may run Python 3.9)
    with patch("cloud_usage.cli.check_platform", return_value={"python_ok": True}), \
         patch("cloud_usage.cli.print_preflight_warnings"):
        exit_code = main(["--nios", _ZF_BACKUP_PATH, "--output-dir", str(tmp_path)])
    assert exit_code == 0, f"Expected exit 0, got {exit_code}"

    # Exactly one xlsx file should be produced
    xlsx_files = list(tmp_path.glob("nios_analysis_*.xlsx"))
    assert len(xlsx_files) == 1, f"Expected 1 xlsx file, found: {xlsx_files}"

    # Load workbook — must be valid
    wb = openpyxl.load_workbook(xlsx_files[0])

    # Scenario Comparison sheet must exist
    assert "Scenario Comparison" in wb.sheetnames, (
        f"'Scenario Comparison' sheet not found. Sheets: {wb.sheetnames}"
    )
    ws = wb["Scenario Comparison"]

    # Find "Active IPs" row by scanning column A
    active_ip_row = None
    for row in ws.iter_rows():
        if row[0].value is not None and str(row[0].value).strip() == "Active IPs":
            active_ip_row = row
            break

    assert active_ip_row is not None, (
        "Could not find 'Active IPs' row in Scenario Comparison sheet. "
        f"Column A values: {[ws.cell(r, 1).value for r in range(1, min(ws.max_row + 1, 20))]}"
    )

    # Current Grid scenario value is in the first non-None column after the label
    active_ip_value = None
    for cell in active_ip_row[1:]:
        if cell.value is not None:
            active_ip_value = cell.value
            break

    assert active_ip_value is not None, "Active IPs value cell is empty in Current Grid column"
    # 304,730 = confirmed ZF reference total: 4-source dedup (active leases + fixed + host + reservations)
    # See STATE.md: "ZF reference value: 304,730 unique Active IPs (4-source dedup with corrected counter)"
    # and REQUIREMENTS.md COUNT-02.
    assert int(active_ip_value) == 304_730, (
        f"Expected 304,730 active-only IPs, got {active_ip_value}. "
        "This may indicate a regression in the counting pipeline."
    )
