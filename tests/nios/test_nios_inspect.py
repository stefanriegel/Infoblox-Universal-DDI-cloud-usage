"""TDD tests for inspect_backup() — all 9 behaviors.

Fixtures use synthetic in-memory .tar.gz archives. No disk writes (beyond tmp_path).
XML structure mirrors the actual onedb.xml format discovered in the ZF reference backup:
    - DATABASE element has VERSION as an XML attribute (NOT a PROPERTY child)
    - OBJECT elements contain PROPERTY children
    - Type is in PROPERTY NAME="__type" VALUE="..." (NOT an XML element attribute)
    - Member fields: virtual_oid (key), host_name (FQDN value)
    - Lease attribution: vnode_id (references virtual_node.virtual_oid)

DATABASE element format (confirmed from ZF backup, 2026-02-28):
    <DATABASE NAME="onedb" VERSION="9.0.6-53318-82020f7ffaad" BUILD="..." BUILDNO="...">
"""

from __future__ import annotations

import dataclasses
import io
import sys
import tarfile
from pathlib import Path

import pytest

# Add src/ to path so cloud_usage is importable (mirrors existing test convention).
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# All tests import inspect_backup from the public API.
# These will fail with ImportError until _inspect.py is implemented (RED phase).
from cloud_usage.nios.parser import inspect_backup
from cloud_usage.nios.errors import NiosParseError
from cloud_usage.nios.schema import IntegrityReport
from cloud_usage.nios.parser._families import ALL_EXPECTED_FAMILIES


# ---------------------------------------------------------------------------
# Fixture helpers (shared with test_nios_parser.py pattern)
# ---------------------------------------------------------------------------


def _build_onedb_xml(*objects: str, version: str = "9.0.6-53318-82020f7ffaad") -> str:
    """Build a minimal onedb.xml string with DATABASE VERSION attribute."""
    objects_xml = "\n".join(objects)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<DATABASE NAME="onedb" VERSION="{version}" BUILD="82020f7ffaad" BUILDNO="53318">
{objects_xml}
</DATABASE>
"""


def _member_object(virtual_oid: str, host_name: str) -> str:
    """Build an XML OBJECT snippet for a virtual_node (Member) object."""
    return f"""<OBJECT>
  <PROPERTY NAME="__type" VALUE=".com.infoblox.one.virtual_node"/>
  <PROPERTY NAME="virtual_oid" VALUE="{virtual_oid}"/>
  <PROPERTY NAME="host_name" VALUE="{host_name}"/>
</OBJECT>"""


def _network_object(**extra_props: str) -> str:
    """Build an XML OBJECT snippet for a network object."""
    extra = ""
    for name, value in extra_props.items():
        extra += f'  <PROPERTY NAME="{name}" VALUE="{value}"/>\n'
    return f"""<OBJECT>
  <PROPERTY NAME="__type" VALUE=".com.infoblox.dns.network"/>
{extra}</OBJECT>"""


def _lease_object(vnode_id: str, ip_address: str = "10.0.0.1") -> str:
    """Build an XML OBJECT snippet for a lease object (MEMBER_SCOPED via vnode_id)."""
    return f"""<OBJECT>
  <PROPERTY NAME="__type" VALUE=".com.infoblox.dns.lease"/>
  <PROPERTY NAME="vnode_id" VALUE="{vnode_id}"/>
  <PROPERTY NAME="ip_address" VALUE="{ip_address}"/>
</OBJECT>"""


def _make_backup(xml_content: str, tmp_path: Path, filename: str = "onedb.xml") -> Path:
    """Write a synthetic .tar.gz with the given onedb.xml content to tmp_path."""
    backup_path = tmp_path / "test_backup.tar.gz"
    xml_bytes = xml_content.encode("utf-8")
    with tarfile.open(str(backup_path), "w:gz") as tar:
        info = tarfile.TarInfo(name=filename)
        info.size = len(xml_bytes)
        tar.addfile(info, io.BytesIO(xml_bytes))
    return backup_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_inspect_backup_families_found_has_all_expected_keys(tmp_path: Path) -> None:
    """families_found contains keys for every family in ALL_EXPECTED_FAMILIES.

    Even families with zero objects must appear with count=0 (not absent from dict).
    """
    xml = _build_onedb_xml(
        _member_object("101", "ns1.example.com"),
        _network_object(),
    )
    backup = _make_backup(xml, tmp_path)

    report = inspect_backup(backup)

    # All expected families must be present as keys
    for family in ALL_EXPECTED_FAMILIES:
        assert family in report.families_found, (
            f"Expected family '{family}' missing from families_found keys"
        )


def test_inspect_backup_families_found_counts_correct(tmp_path: Path) -> None:
    """families_found counts reflect actual object counts in the backup."""
    xml = _build_onedb_xml(
        _member_object("101", "ns1.example.com"),
        _member_object("102", "ns2.example.com"),
        _network_object(),
        _lease_object("101"),
        _lease_object("102"),
        _lease_object("101"),
    )
    backup = _make_backup(xml, tmp_path)

    report = inspect_backup(backup)

    assert report.families_found["member"] == 2
    assert report.families_found["network"] == 1
    assert report.families_found["lease"] == 3


def test_inspect_backup_zero_row_families_get_warnings(tmp_path: Path) -> None:
    """Every expected family with 0 objects generates a warning entry."""
    # Only include member and network — all other expected families will have 0 count.
    xml = _build_onedb_xml(
        _member_object("101", "ns1.example.com"),
        _network_object(),
    )
    backup = _make_backup(xml, tmp_path)

    report = inspect_backup(backup)

    # Count how many expected families have 0 objects (excluding member and network)
    zero_families = {f for f in ALL_EXPECTED_FAMILIES if report.families_found.get(f, 0) == 0}
    # Each zero-count family must have a warning
    for family in zero_families:
        found = any(family in w for w in report.warnings)
        assert found, f"Expected warning for zero-count family '{family}', got: {report.warnings}"


def test_inspect_backup_unresolvable_oid_warning(tmp_path: Path) -> None:
    """When a lease references a vnode_id not in member map, a warning is generated.

    The warning must contain the count of unresolvable objects.
    """
    xml = _build_onedb_xml(
        _member_object("101", "ns1.example.com"),
        _lease_object("999"),  # vnode_id=999 does not match any member virtual_oid
    )
    backup = _make_backup(xml, tmp_path)

    report = inspect_backup(backup)

    # At least one warning must mention unresolvable OIDs
    has_oid_warning = any(
        "virtual_oid" in w.lower() or "vnode_id" in w.lower() or "unresol" in w.lower()
        for w in report.warnings
    )
    assert has_oid_warning, (
        f"Expected unresolvable OID warning, got warnings: {report.warnings}"
    )


def test_inspect_backup_no_members_generates_warning(tmp_path: Path) -> None:
    """When no Member objects exist in backup, warnings includes a 'No Member' warning."""
    xml = _build_onedb_xml(
        _network_object(),
        _network_object(),
    )
    backup = _make_backup(xml, tmp_path)

    report = inspect_backup(backup)

    has_member_warning = any("member" in w.lower() for w in report.warnings)
    assert has_member_warning, (
        f"Expected 'No Member objects' warning, got warnings: {report.warnings}"
    )


def test_inspect_backup_nios_version_populated(tmp_path: Path) -> None:
    """nios_version is extracted from the DATABASE element VERSION attribute."""
    expected_version = "9.0.6-53318-82020f7ffaad"
    xml = _build_onedb_xml(
        _member_object("101", "ns1.example.com"),
        version=expected_version,
    )
    backup = _make_backup(xml, tmp_path)

    report = inspect_backup(backup)

    assert report.nios_version is not None, "nios_version should not be None"
    assert report.nios_version == expected_version, (
        f"Expected nios_version={expected_version!r}, got {report.nios_version!r}"
    )


def test_inspect_backup_snapshot_date_is_yyyy_mm_dd(tmp_path: Path) -> None:
    """snapshot_date is a non-None string in YYYY-MM-DD format."""
    xml = _build_onedb_xml(_member_object("101", "ns1.example.com"))
    backup = _make_backup(xml, tmp_path)

    report = inspect_backup(backup)

    assert report.snapshot_date is not None, "snapshot_date should not be None"
    # Must match YYYY-MM-DD format
    import re
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", report.snapshot_date), (
        f"snapshot_date must be YYYY-MM-DD format, got {report.snapshot_date!r}"
    )


def test_inspect_backup_missing_onedb_xml_raises(tmp_path: Path) -> None:
    """A .tar.gz without onedb.xml raises NiosParseError."""
    xml = _build_onedb_xml(_network_object())
    backup = _make_backup(xml, tmp_path, filename="not_onedb.xml")

    with pytest.raises(NiosParseError):
        inspect_backup(backup)


def test_inspect_backup_returns_integrity_report_dataclass(tmp_path: Path) -> None:
    """inspect_backup() returns an IntegrityReport dataclass instance, not a dict or string."""
    xml = _build_onedb_xml(_member_object("101", "ns1.example.com"))
    backup = _make_backup(xml, tmp_path)

    result = inspect_backup(backup)

    assert isinstance(result, IntegrityReport), (
        f"inspect_backup() must return IntegrityReport, got {type(result)}"
    )
    assert dataclasses.is_dataclass(result), "Result must be a dataclass instance"
    # Verify all required fields are accessible
    assert hasattr(result, "families_found")
    assert hasattr(result, "warnings")
    assert hasattr(result, "nios_version")
    assert hasattr(result, "snapshot_date")
