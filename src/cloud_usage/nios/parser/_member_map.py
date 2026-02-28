"""Pass 1: builds the virtual_oid -> hostname member map from NIOS Member objects.

Must complete before Pass 2 (parse_backup) begins, since member attribution
must be resolved before any NiosObject is yielded to callers.

EMPIRICALLY CONFIRMED FIELD NAMES (ZF reference backup, 2026-02-28):
    Member object type:  .com.infoblox.one.virtual_node
    Key field:           virtual_oid  (integer string, e.g., "101")
    Value field:         host_name    (FQDN, e.g., "frdn77x00.emea.zf-world.com")

The member_map keys (virtual_oid strings) are referenced by LEASE objects
via the lease.vnode_id field. The map is passed to Pass 2 for resolution.
"""

from __future__ import annotations

from pathlib import Path

from cloud_usage.nios.parser._extractor import _open_onedb_xml
from cloud_usage.nios.parser._families import _MEMBER_XML_TYPES
from cloud_usage.nios.parser._xml_stream import _iter_raw_objects


def _build_member_map(path: str | Path) -> dict[str, str]:
    """Return virtual_oid -> hostname map from all Member objects in the backup.

    Pass 1 of the two-pass parse design. Reads the entire archive once to
    collect member identity before any other object is yielded.

    Field names confirmed empirically against ZF Friedrichshafen reference backup
    (do_not_commit/ZF-database-11_1752136302416.bak.reset.tar.gz, 2026-02-28):
    - virtual_oid: integer string key (e.g., "101")
    - host_name: FQDN string value (e.g., "frdn77x00.emea.zf-world.com")

    Args:
        path: Path to the .tar.gz NIOS Grid backup file.

    Returns:
        Dict mapping virtual_oid string to hostname/FQDN string.
        Empty dict if no Member objects found (all objects will get member_hostname=None).
    """
    member_map: dict[str, str] = {}
    with _open_onedb_xml(path) as (fileobj, _snapshot_date):
        for xml_type, props in _iter_raw_objects(fileobj):
            if xml_type not in _MEMBER_XML_TYPES:
                continue
            # Confirmed field names from ZF reference backup discovery (2026-02-28).
            oid = props.get("virtual_oid", "")
            hostname = props.get("host_name", "")
            if oid:
                member_map[oid] = hostname
    return member_map
