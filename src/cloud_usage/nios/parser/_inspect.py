"""inspect_backup() implementation — structural integrity report for NIOS backups.

Uses a full two-pass parse (reusing _iter_raw_objects) for accurate family counts
and unresolvable virtual_oid tracking. Full parse chosen over lightweight metadata
scan because zero-row family warnings require complete traversal.

DATABASE VERSION EXTRACTION:
    The DATABASE element is the root XML element — it is NOT an OBJECT element and
    therefore is NOT yielded by _iter_raw_objects (which uses tag="OBJECT" iterparse).
    A separate pre-scan reads the DATABASE VERSION attribute via a one-shot iterparse
    with events=("start",) and tag="DATABASE". This pre-scan reads only the first
    element of the XML stream (the opening DATABASE tag), which is extremely fast.

    Confirmed format from ZF reference backup (2026-02-28):
        <DATABASE NAME="onedb" VERSION="9.0.6-53318-82020f7ffaad" BUILD="..." BUILDNO="...">
    VERSION is an XML attribute on the DATABASE element. Field name: "VERSION" (uppercase).

MEMBER ATTRIBUTION:
    Only LEASE is MEMBER_SCOPED (vnode_id field on lease objects).
    Pass 1 builds the member map: virtual_oid (key) -> host_name (value).
    Pass 2 counts families and tracks unresolvable vnode_id references.
"""

from __future__ import annotations

import logging
from pathlib import Path

from lxml import etree

from cloud_usage.nios.parser._extractor import _open_onedb_xml
from cloud_usage.nios.parser._families import (
    ALL_EXPECTED_FAMILIES,
    MEMBER_SCOPED_FAMILIES,
    _MEMBER_XML_TYPES,
    _XML_TYPE_TO_FAMILY,
)
from cloud_usage.nios.parser._xml_stream import _iter_raw_objects
from cloud_usage.nios.schema import IntegrityReport

_logger = logging.getLogger(__name__)


def _extract_database_version(fileobj) -> str | None:
    """Extract the VERSION attribute from the DATABASE root element.

    Uses a one-shot iterparse that stops after reading the DATABASE opening tag.
    This is very fast — only the first bytes of the XML stream are consumed.

    The DATABASE element is the root element (not an OBJECT), so _iter_raw_objects
    never yields it. This separate pre-scan is required.

    Args:
        fileobj: Readable binary file object for onedb.xml (from tarfile.extractfile).
                 The caller is responsible for seeking to the start if needed.

    Returns:
        VERSION attribute string (e.g. "9.0.6-53318-82020f7ffaad") or None if absent.
    """
    version: str | None = None
    # lxml 6.x: options passed as direct kwargs (not via XMLParser object).
    for _event, elem in etree.iterparse(
        fileobj,
        events=("start",),
        tag="DATABASE",
        resolve_entities=False,
        no_network=True,
        huge_tree=True,
        recover=True,
    ):
        # VERSION is an XML attribute on the DATABASE element (uppercase).
        # Confirmed from ZF reference backup: VERSION="9.0.6-53318-82020f7ffaad"
        version = elem.get("VERSION")
        break  # Only need the first (and only) DATABASE element
    return version


def inspect_backup(path: str | Path) -> IntegrityReport:
    """Return a structural integrity report without yielding NiosObject instances.

    Performs a full parse of the backup with three sequential passes over onedb.xml:
    - Pre-scan: reads DATABASE element to extract nios_version (stops at first tag).
    - Pass 1: builds member map (virtual_oid -> host_name), captures snapshot_date.
    - Pass 2: counts all object families, tracks unresolvable vnode_id references.

    Args:
        path: Path to the .tar.gz NIOS Grid backup file.

    Returns:
        IntegrityReport with families_found (all expected families, 0 for missing),
        warnings list, nios_version, and snapshot_date.

    Raises:
        NiosParseError: If the archive is corrupted, missing, or lacks onedb.xml.
    """
    path = Path(path)

    # Initialise counts for ALL expected families (zero baseline ensures missing families
    # appear in families_found with count=0 rather than being absent from the dict).
    families_found: dict[str, int] = {f: 0 for f in ALL_EXPECTED_FAMILIES}
    nios_version: str | None = None
    snapshot_date: str | None = None
    member_map: dict[str, str] = {}

    # Pre-scan: extract NIOS version from DATABASE element VERSION attribute.
    # DATABASE is the root XML element — _iter_raw_objects skips it (tag="OBJECT" only).
    # We open a separate archive context to read only the DATABASE tag, then close it.
    with _open_onedb_xml(path) as (fileobj, _snap_date):
        nios_version = _extract_database_version(fileobj)

    # Pass 1: build member identity map + capture snapshot_date.
    with _open_onedb_xml(path) as (fileobj, snap_date):
        snapshot_date = snap_date
        for xml_type, props in _iter_raw_objects(fileobj):
            if xml_type in _MEMBER_XML_TYPES:
                # Confirmed field names from ZF reference backup (2026-02-28):
                # virtual_oid: integer string key (e.g., "101")
                # host_name: FQDN string value (e.g., "frdn77x00.emea.zf-world.com")
                oid = props.get("virtual_oid", "")
                hostname = props.get("host_name", "")
                if oid:
                    member_map[oid] = hostname

    # Pass 2: count all families + track unresolvable vnode_id references.
    unresolved_oid_count = 0
    with _open_onedb_xml(path) as (fileobj, _):
        for xml_type, props in _iter_raw_objects(fileobj):
            family = _XML_TYPE_TO_FAMILY.get(xml_type)
            if family is None:
                continue  # Unknown type — not one of the 21 expected families

            families_found[family] = families_found.get(family, 0) + 1

            if family in MEMBER_SCOPED_FAMILIES:
                # vnode_id is the confirmed attribution field on LEASE objects (ZF backup, 2026-02-28).
                # Unresolvable means the vnode_id references a virtual_oid not in the member map.
                oid = props.get("vnode_id", "")
                if oid and oid not in member_map:
                    unresolved_oid_count += 1

    # Build warnings list.
    warnings: list[str] = []

    # Warning 1: expected families with 0 rows.
    for family in sorted(ALL_EXPECTED_FAMILIES):
        if families_found.get(family, 0) == 0:
            warnings.append(
                f"Expected family '{family}' has 0 rows — backup may be partial"
            )

    # Warning 2: unresolvable vnode_id references.
    if unresolved_oid_count > 0:
        warnings.append(
            f"{unresolved_oid_count} objects reference a virtual_oid "
            f"not found in Member objects"
        )

    # Warning 3: empty member map.
    if not member_map:
        warnings.append(
            "No Member objects found — all objects will have member_hostname=None"
        )

    _logger.debug(
        "inspect_backup %s: %d families, %d warnings, nios_version=%r",
        path.name,
        len(families_found),
        len(warnings),
        nios_version,
    )

    return IntegrityReport(
        families_found=families_found,
        warnings=warnings,
        nios_version=nios_version,
        snapshot_date=snapshot_date,
    )
