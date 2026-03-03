"""NIOS Grid backup parser public API.

Primary interface:
    parse_backup(path) -> Iterator[NiosObject]  -- stream all 21 object families
    inspect_backup(path) -> IntegrityReport     -- structural integrity report
"""

from __future__ import annotations

__all__ = ["parse_backup", "inspect_backup", "get_member_map"]

# Implementations live in _parse.py (Plan 02) and _inspect.py (Plan 03).
# Import at call time to avoid circular imports during package bootstrap.


def parse_backup(path, *, member_map=None):
    """Stream all NIOS object families from a .tar.gz backup. See _parse.py."""
    from cloud_usage.nios.parser._parse import parse_backup as _impl

    return _impl(path, member_map=member_map)


def inspect_backup(path):
    """Return IntegrityReport for a .tar.gz backup. See _inspect.py."""
    from cloud_usage.nios.parser._inspect import inspect_backup as _impl

    return _impl(path)


def get_member_map(path):
    """Return virtual_oid -> hostname map from Member objects. See _member_map.py."""
    from cloud_usage.nios.parser._member_map import _build_member_map

    return _build_member_map(path)
