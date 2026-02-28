"""TDD tests for parse_backup() — all 10 behaviors.

Fixtures use synthetic in-memory .tar.gz archives. No disk writes (beyond tmp_path).
XML structure mirrors the actual onedb.xml format discovered in the ZF reference backup:
    - OBJECT elements contain PROPERTY children
    - Type is in PROPERTY NAME="__type" VALUE="..." (NOT an XML element attribute)
    - Member fields: virtual_oid (key), host_name (FQDN value)
    - Lease attribution: vnode_id (references virtual_node.virtual_oid)

All actual XML type strings from _XML_TYPE_TO_FAMILY (discovered 2026-02-28):
    - Member:  .com.infoblox.one.virtual_node
    - Network: .com.infoblox.dns.network
    - Lease:   .com.infoblox.dns.lease
    - Zone:    .com.infoblox.dns.zone
"""

from __future__ import annotations

import io
import sys
import tarfile
import types
from pathlib import Path

import pytest

# Add src/ to path so cloud_usage is importable (mirrors existing test convention).
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# All tests import parse_backup from the public API.
# These will fail with ImportError until _parse.py is implemented (RED phase).
from cloud_usage.nios.parser import parse_backup
from cloud_usage.nios.errors import NiosParseError


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _build_onedb_xml(*objects: str) -> str:
    """Build a minimal onedb.xml string containing the given OBJECT XML snippets."""
    objects_xml = "\n".join(objects)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<DATABASE NAME="onedb" VERSION="9.0.6-53318-82020f7ffaad" BUILD="82020f7ffaad" BUILDNO="53318">
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


def _network_object(virtual_oid: str | None = None, **extra_props: str) -> str:
    """Build an XML OBJECT snippet for a network object."""
    extra = ""
    if virtual_oid is not None:
        extra += f'  <PROPERTY NAME="virtual_oid" VALUE="{virtual_oid}"/>\n'
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


def _zone_object(fqdn: str = "example.com") -> str:
    """Build an XML OBJECT snippet for a DNS zone (grid-level family)."""
    return f"""<OBJECT>
  <PROPERTY NAME="__type" VALUE=".com.infoblox.dns.zone"/>
  <PROPERTY NAME="fqdn" VALUE="{fqdn}"/>
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


def test_parse_backup_yields_known_families(tmp_path: Path) -> None:
    """A backup with one MEMBER object + one NETWORK object yields 2 NiosObjects.

    Verifies that parse_backup correctly identifies both families.
    """
    xml = _build_onedb_xml(
        _member_object("101", "ns1.example.com"),
        _network_object(),
    )
    backup = _make_backup(xml, tmp_path)

    objects = list(parse_backup(backup))

    assert len(objects) == 2
    families = {o.family for o in objects}
    assert "member" in families
    assert "network" in families


def test_parse_backup_member_hostname_resolved(tmp_path: Path) -> None:
    """Lease object with vnode_id=42 resolves to member with virtual_oid=42.

    The lease NiosObject.member_hostname must equal the member's host_name.
    """
    xml = _build_onedb_xml(
        _member_object("42", "ns1.example.com"),
        _lease_object("42", ip_address="192.168.1.100"),
    )
    backup = _make_backup(xml, tmp_path)

    objects = list(parse_backup(backup))
    leases = [o for o in objects if o.family == "lease"]

    assert len(leases) == 1
    assert leases[0].member_hostname == "ns1.example.com"


def test_parse_backup_unresolvable_oid_yields_none(tmp_path: Path) -> None:
    """Lease referencing vnode_id=99 (no member has oid=99) yields member_hostname=None.

    Objects with unresolvable OIDs must NOT be skipped — they are yielded with None.
    """
    xml = _build_onedb_xml(
        _member_object("101", "ns1.example.com"),
        _lease_object("99"),  # no member has oid=99
    )
    backup = _make_backup(xml, tmp_path)

    objects = list(parse_backup(backup))
    leases = [o for o in objects if o.family == "lease"]

    assert len(leases) == 1
    assert leases[0].member_hostname is None


def test_parse_backup_grid_level_family_hostname_none(tmp_path: Path) -> None:
    """DNS Zone object (grid-level family) has member_hostname=None by design."""
    xml = _build_onedb_xml(
        _member_object("101", "ns1.example.com"),
        _zone_object("example.com"),
    )
    backup = _make_backup(xml, tmp_path)

    objects = list(parse_backup(backup))
    zones = [o for o in objects if o.family == "dns_zone"]

    assert len(zones) == 1
    assert zones[0].member_hostname is None


def test_parse_backup_empty_member_map_yields_objects(tmp_path: Path) -> None:
    """Backup with no Member objects but has Network objects yields all with member_hostname=None."""
    xml = _build_onedb_xml(
        _network_object(),
        _network_object(),
    )
    backup = _make_backup(xml, tmp_path)

    objects = list(parse_backup(backup))
    networks = [o for o in objects if o.family == "network"]

    assert len(networks) == 2
    for obj in networks:
        assert obj.member_hostname is None


def test_parse_backup_missing_onedb_xml_raises(tmp_path: Path) -> None:
    """A .tar.gz with a different filename inside raises NiosParseError."""
    xml = _build_onedb_xml(_network_object())
    # Write with a wrong filename (not onedb.xml)
    backup = _make_backup(xml, tmp_path, filename="notonedb.xml")

    with pytest.raises(NiosParseError):
        list(parse_backup(backup))


def test_parse_backup_corrupted_archive_raises(tmp_path: Path) -> None:
    """Non-gzip bytes passed as path raises NiosParseError."""
    corrupted = tmp_path / "corrupted.tar.gz"
    corrupted.write_bytes(b"this is not a gzip archive at all, just garbage bytes 12345")

    with pytest.raises(NiosParseError):
        list(parse_backup(corrupted))


def test_parse_backup_raw_attrs_preserved(tmp_path: Path) -> None:
    """Network object attributes cidr and view are preserved verbatim in raw_attrs."""
    xml = _build_onedb_xml(
        _network_object(cidr="10.0.0.0/24", view="default"),
    )
    backup = _make_backup(xml, tmp_path)

    objects = list(parse_backup(backup))
    networks = [o for o in objects if o.family == "network"]

    assert len(networks) == 1
    assert networks[0].raw_attrs.get("cidr") == "10.0.0.0/24"
    assert networks[0].raw_attrs.get("view") == "default"


def test_parse_backup_unknown_xml_types_skipped(tmp_path: Path) -> None:
    """OBJECT with type='Unknown:Garbage' not in _XML_TYPE_TO_FAMILY is not yielded."""
    unknown_object = """<OBJECT>
  <PROPERTY NAME="__type" VALUE="Unknown:Garbage"/>
  <PROPERTY NAME="some_field" VALUE="some_value"/>
</OBJECT>"""
    xml = _build_onedb_xml(
        _network_object(),
        unknown_object,
    )
    backup = _make_backup(xml, tmp_path)

    objects = list(parse_backup(backup))

    # Only the network object should be yielded; the unknown type is skipped
    assert len(objects) == 1
    assert objects[0].family == "network"


def test_parse_backup_is_generator(tmp_path: Path) -> None:
    """parse_backup returns a generator (not a list or other sequence)."""
    xml = _build_onedb_xml(_network_object())
    backup = _make_backup(xml, tmp_path)

    result = parse_backup(backup)

    assert isinstance(result, types.GeneratorType), (
        f"parse_backup() must return a GeneratorType, got {type(result)}"
    )
