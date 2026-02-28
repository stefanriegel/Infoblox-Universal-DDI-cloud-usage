"""Public parse_backup() generator — two-pass NIOS backup parser.

Pass 1: builds virtual_oid -> hostname member map (_build_member_map).
Pass 2: streams all 21 object families as resolved NiosObject instances.

Callers receive NiosObject instances with member_hostname already resolved.
No raw virtual_oid integers are ever exposed to callers.

EMPIRICALLY CONFIRMED ATTRIBUTION FIELD (ZF reference backup, 2026-02-28):
    Only LEASE objects are MEMBER_SCOPED. The attribution field is vnode_id:
        lease.vnode_id -> virtual_node.virtual_oid -> virtual_node.host_name
    All other DHCP/DNS families have no direct member attribution field.
    See _families.py for the MEMBER_SCOPED_FAMILIES and GRID_LEVEL_FAMILIES sets.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from cloud_usage.nios.parser._extractor import _open_onedb_xml
from cloud_usage.nios.parser._families import MEMBER_SCOPED_FAMILIES, _XML_TYPE_TO_FAMILY
from cloud_usage.nios.parser._member_map import _build_member_map
from cloud_usage.nios.parser._xml_stream import _iter_raw_objects
from cloud_usage.nios.schema import NiosObject

_logger = logging.getLogger(__name__)


def parse_backup(path: str | Path) -> Iterator[NiosObject]:
    """Stream all NIOS Grid object families as resolved NiosObject instances.

    Two-pass design:
    - Pass 1: reads the archive once to build virtual_oid -> hostname member map.
    - Pass 2: reads the archive again, yields NiosObject for all 21 families
      with member_hostname already resolved.

    MEMBER_SCOPED families (currently only LEASE) use the vnode_id field to
    resolve member_hostname via the member map. All other families are GRID_LEVEL
    and yield member_hostname=None by design.

    Args:
        path: Path to the .tar.gz NIOS Grid backup file.

    Yields:
        NiosObject instances. Every object has family set to a NiosFamily constant.
        member_hostname is the resolved hostname/FQDN, or None for grid-level families
        and objects whose vnode_id could not be resolved in the member map.

    Raises:
        NiosParseError: If the archive is corrupted, missing, or lacks onedb.xml.
    """
    path = Path(path)

    # Pass 1: build complete member identity map before yielding any object.
    member_map = _build_member_map(path)
    if not member_map:
        _logger.warning(
            "No Member objects found in %s — all objects will have member_hostname=None",
            path,
        )

    # Pass 2: yield all object families with member attribution resolved.
    unresolved_count = 0
    with _open_onedb_xml(path) as (fileobj, _snapshot_date):
        for xml_type, props in _iter_raw_objects(fileobj):
            family = _XML_TYPE_TO_FAMILY.get(xml_type)
            if family is None:
                continue  # Unknown type — not one of the 21 expected families

            # Resolve member attribution for member-scoped families.
            # Confirmed attribution field: vnode_id on LEASE objects (only MEMBER_SCOPED family).
            member_hostname: str | None = None
            if family in MEMBER_SCOPED_FAMILIES:
                # vnode_id is the confirmed attribution field on lease objects (ZF backup, 2026-02-28).
                oid = props.get("vnode_id", "")
                if oid:
                    member_hostname = member_map.get(oid)
                    if member_hostname is None:
                        unresolved_count += 1
                        # Still yield — Phase 11 must not silently lose these objects.

            yield NiosObject(
                family=family,
                member_hostname=member_hostname,
                raw_attrs=props,
            )

    if unresolved_count > 0:
        _logger.warning(
            "%d objects in %s reference a vnode_id not found in Member objects",
            unresolved_count,
            path,
        )
