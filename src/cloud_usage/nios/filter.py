"""NIOS Grid member filter module.

Provides FilterConfig (frozen dataclass) and filter_objects() (lazy generator)
for scoping a stream of NiosObject instances to specific grid members using
fnmatch-style hostname glob patterns.

Design notes:
- filter_objects() is a lazy generator — it never materialises the input stream.
- Objects with member_hostname=None (grid-level) always pass through unconditionally.
- Whitelist-first semantics: if whitelist is non-empty, only matching members are
  admitted; blacklist then excludes from the admitted set.
- After stream exhaustion, a logging.warning() is emitted once per whitelist pattern
  that matched no member_hostname values in the stream.
- fnmatch.fnmatch() (not fnmatchcase) is used — DNS hostnames are case-insensitive
  by RFC; the default normcase behaviour is correct.
- FilterConfig.lease_states is included for Phase 11 counter.py to access via
  the shared config object; it is not used by filter_objects() itself.
"""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field
from typing import Iterator

from cloud_usage.nios.schema import NiosObject

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FilterConfig:
    """Configuration for filtering and counting NIOS Grid objects.

    All fields are tuples (not lists) to enforce true immutability on a frozen
    dataclass — lists are mutable and cannot be safely stored in frozen dataclasses.

    Args:
        whitelist: fnmatch-style glob patterns for member_hostname values to include.
            Empty tuple means no whitelist filtering — all members are admitted.
        blacklist: fnmatch-style glob patterns for member_hostname values to exclude.
            Applied after whitelist. Empty tuple means no blacklist filtering.
        lease_states: DHCP binding_state values counted as Active IPs.
            Used by counter.py (not by filter_objects()). Default: active + static.
    """

    whitelist: tuple[str, ...] = field(default_factory=tuple)
    blacklist: tuple[str, ...] = field(default_factory=tuple)
    lease_states: tuple[str, ...] = field(default_factory=lambda: ("active", "static"))


def filter_objects(
    objects: Iterator[NiosObject],
    config: FilterConfig,
) -> Iterator[NiosObject]:
    """Filter a stream of NiosObject instances by member_hostname glob patterns.

    Grid-level objects (member_hostname=None) always pass through unconditionally,
    regardless of whitelist or blacklist configuration.

    For member-scoped objects:
    1. If whitelist is non-empty: only objects whose member_hostname matches at least
       one whitelist pattern are admitted (whitelist-first gate).
    2. If blacklist is non-empty: objects whose member_hostname matches any blacklist
       pattern are excluded from the admitted set.
    3. Surviving objects are yielded.

    After the stream is exhausted, a logging.warning() is emitted once for each
    whitelist pattern that matched zero member_hostname values during the entire
    stream traversal.

    Args:
        objects: Iterator of NiosObject instances (e.g., from parse_backup()).
        config: FilterConfig controlling whitelist, blacklist, and lease_states.

    Yields:
        NiosObject instances that pass the filter.
    """
    whitelist = config.whitelist
    blacklist = config.blacklist

    # Track which whitelist patterns have matched at least one hostname.
    # Used for post-stream zero-match warnings.
    matched_patterns: set[str] = set()

    for obj in objects:
        hostname = obj.member_hostname

        # Grid-level objects always pass through unconditionally.
        if hostname is None:
            yield obj
            continue

        # --- Whitelist gate (if configured) ---
        if whitelist:
            admitted = False
            for pattern in whitelist:
                if fnmatch.fnmatch(hostname, pattern):
                    admitted = True
                    matched_patterns.add(pattern)
            if not admitted:
                continue  # not in whitelist — skip

        # --- Blacklist exclusion (if configured) ---
        if blacklist:
            excluded = False
            for pattern in blacklist:
                if fnmatch.fnmatch(hostname, pattern):
                    excluded = True
                    break
            if excluded:
                continue  # blacklisted — skip

        yield obj

    # Post-stream: warn for each whitelist pattern that matched nothing.
    for pattern in whitelist:
        if pattern not in matched_patterns:
            _logger.warning(
                "Whitelist pattern %r matched no members in backup", pattern
            )
