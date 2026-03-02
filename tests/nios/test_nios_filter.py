"""TDD tests for filter_objects() and FilterConfig — all FILTER-01 through FILTER-04 behaviors.

Tests use in-memory NiosObject construction (no .tar.gz fixtures needed).
filter_objects() takes Iterator[NiosObject], not a path.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Iterator

import pytest

# Add src/ to path so cloud_usage is importable (mirrors existing test convention).
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# These will fail with ImportError until filter.py is implemented (RED phase).
from cloud_usage.nios.filter import filter_objects, FilterConfig
from cloud_usage.nios.schema import NiosObject, NiosFamily


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _obj(family: str, member: str | None = None, **attrs: str) -> NiosObject:
    """Build a NiosObject directly for filter testing."""
    return NiosObject(family=family, member_hostname=member, raw_attrs=dict(attrs))


def _lease(member: str | None, ip: str = "10.0.0.1", binding_state: str = "active") -> NiosObject:
    """Build a LEASE NiosObject attributed to a specific member."""
    return _obj(NiosFamily.LEASE, member=member, ip_address=ip, binding_state=binding_state)


def _dns_a(ip: str = "192.168.1.1") -> NiosObject:
    """Build a grid-level DNS A record (member_hostname=None)."""
    return _obj(NiosFamily.DNS_RECORD_A, member=None, ip_address=ip)


def _network(cidr: str = "10.0.0.0/24") -> NiosObject:
    """Build a grid-level NETWORK object (member_hostname=None)."""
    return _obj(NiosFamily.NETWORK, member=None, cidr=cidr)


# ---------------------------------------------------------------------------
# FILTER-01: Whitelist passes matching members
# ---------------------------------------------------------------------------

def test_whitelist_passes_matching_members():
    """filter_objects() with a whitelist passes objects whose member_hostname matches glob."""
    config = FilterConfig(whitelist=("gm*",), blacklist=(), lease_states=("active",))
    objects = [
        _lease("gm-member-01.corp.example.com", ip="10.0.0.1"),
        _lease("ns1.example.com", ip="10.0.0.2"),
        _lease("gm-member-02.corp.example.com", ip="10.0.0.3"),
        _lease("other-host.example.com", ip="10.0.0.4"),
    ]
    result = list(filter_objects(iter(objects), config))
    hostnames = [o.member_hostname for o in result]
    assert "gm-member-01.corp.example.com" in hostnames
    assert "gm-member-02.corp.example.com" in hostnames
    assert "ns1.example.com" not in hostnames
    assert "other-host.example.com" not in hostnames


# ---------------------------------------------------------------------------
# FILTER-01: Grid-level objects (member_hostname=None) always pass through
# ---------------------------------------------------------------------------

def test_grid_level_always_passes():
    """Objects with member_hostname=None pass through regardless of whitelist/blacklist."""
    config = FilterConfig(whitelist=("gm*",), blacklist=("gm*",), lease_states=("active",))
    objects = [
        _dns_a("192.168.1.1"),            # grid-level DNS record
        _network("10.0.0.0/24"),          # grid-level NETWORK
        _obj(NiosFamily.DNS_ZONE, member=None, name="example.com"),
        _lease("gm-member-01.example.com", ip="10.0.0.1"),  # member-level, matches whitelist AND blacklist
    ]
    result = list(filter_objects(iter(objects), config))
    # Grid-level objects must ALL pass through
    grid_objects = [o for o in result if o.member_hostname is None]
    assert len(grid_objects) == 3  # DNS A, NETWORK, DNS_ZONE all pass

    # The gm-member lease: whitelist admits "gm*", then blacklist "gm*" excludes it
    member_objects = [o for o in result if o.member_hostname is not None]
    assert len(member_objects) == 0


def test_grid_level_passes_without_any_filter():
    """Grid-level objects pass through even with no whitelist/blacklist configured."""
    config = FilterConfig(whitelist=(), blacklist=(), lease_states=("active",))
    objects = [
        _dns_a("192.168.1.1"),
        _network("10.0.0.0/24"),
    ]
    result = list(filter_objects(iter(objects), config))
    assert len(result) == 2


# ---------------------------------------------------------------------------
# FILTER-02: Blacklist excludes matching members
# ---------------------------------------------------------------------------

def test_blacklist_excludes_matching_members():
    """filter_objects() with a blacklist drops objects whose member_hostname matches."""
    config = FilterConfig(whitelist=(), blacklist=("ns1.*",), lease_states=("active",))
    objects = [
        _lease("ns1.example.com", ip="10.0.0.1"),
        _lease("ns2.example.com", ip="10.0.0.2"),
        _lease("gm-member-01.corp.example.com", ip="10.0.0.3"),
        _dns_a("192.168.1.1"),  # grid-level, always passes
    ]
    result = list(filter_objects(iter(objects), config))
    hostnames = [o.member_hostname for o in result]
    assert "ns1.example.com" not in hostnames
    assert "ns2.example.com" in hostnames
    assert "gm-member-01.corp.example.com" in hostnames
    # Grid-level DNS record always passes
    assert None in hostnames


# ---------------------------------------------------------------------------
# FILTER-03: Whitelist-first semantics
# ---------------------------------------------------------------------------

def test_whitelist_first_semantics():
    """Whitelist gates admission first; blacklist excludes from the admitted set.

    whitelist=("gm*",), blacklist=("gm*",):
    - "gm-01" is admitted by whitelist
    - then blacklist "gm*" excludes it from admitted set
    - result: "gm-01" is dropped
    """
    config = FilterConfig(whitelist=("gm*",), blacklist=("gm*",), lease_states=("active",))
    objects = [
        _lease("gm-member-01.corp.example.com", ip="10.0.0.1"),
        _lease("ns1.example.com", ip="10.0.0.2"),  # not in whitelist, dropped
    ]
    result = list(filter_objects(iter(objects), config))
    member_objects = [o for o in result if o.member_hostname is not None]
    assert len(member_objects) == 0  # all member-level objects excluded


def test_whitelist_first_partial_overlap():
    """Whitelist admits a subset; blacklist then applies only to that subset."""
    config = FilterConfig(whitelist=("member-*",), blacklist=("member-02*",), lease_states=("active",))
    objects = [
        _lease("member-01.corp.example.com", ip="10.0.0.1"),
        _lease("member-02.corp.example.com", ip="10.0.0.2"),
        _lease("other-host.example.com", ip="10.0.0.3"),  # not in whitelist, dropped
    ]
    result = list(filter_objects(iter(objects), config))
    member_objects = [o for o in result if o.member_hostname is not None]
    hostnames = [o.member_hostname for o in member_objects]
    # member-01: admitted by whitelist, not excluded by blacklist
    assert "member-01.corp.example.com" in hostnames
    # member-02: admitted by whitelist, then excluded by blacklist
    assert "member-02.corp.example.com" not in hostnames
    # other-host: not admitted by whitelist
    assert "other-host.example.com" not in hostnames


# ---------------------------------------------------------------------------
# FILTER-04: Zero-match whitelist emits warning
# ---------------------------------------------------------------------------

def test_zero_match_whitelist_warns(caplog):
    """After stream exhaustion, logging.warning() is emitted for each non-matching whitelist pattern."""
    config = FilterConfig(whitelist=("no-match-pattern-*",), blacklist=(), lease_states=("active",))
    objects = [
        _lease("gm-member-01.corp.example.com", ip="10.0.0.1"),
        _lease("ns1.example.com", ip="10.0.0.2"),
        _dns_a("192.168.1.1"),  # grid-level, passes through
    ]
    with caplog.at_level(logging.WARNING, logger="cloud_usage.nios.filter"):
        result = list(filter_objects(iter(objects), config))

    # Grid-level objects always pass through
    grid_results = [o for o in result if o.member_hostname is None]
    assert len(grid_results) == 1

    # No member-level objects pass (pattern matches nothing)
    member_results = [o for o in result if o.member_hostname is not None]
    assert len(member_results) == 0

    # Warning must be emitted for the unmatched pattern
    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_messages) >= 1
    assert any("no-match-pattern-*" in str(msg) for msg in warning_messages)


def test_zero_match_multiple_patterns_warns(caplog):
    """Each non-matching pattern in whitelist emits exactly one warning."""
    config = FilterConfig(
        whitelist=("no-match-a-*", "no-match-b-*"),
        blacklist=(),
        lease_states=("active",),
    )
    objects = [
        _lease("gm-member-01.corp.example.com", ip="10.0.0.1"),
    ]
    with caplog.at_level(logging.WARNING, logger="cloud_usage.nios.filter"):
        result = list(filter_objects(iter(objects), config))

    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    # Two patterns, each should emit one warning
    assert len(warning_messages) >= 2
    assert any("no-match-a-*" in str(msg) for msg in warning_messages)
    assert any("no-match-b-*" in str(msg) for msg in warning_messages)


def test_matching_pattern_does_not_warn(caplog):
    """No warning is emitted for whitelist patterns that do match at least one member."""
    config = FilterConfig(whitelist=("gm*",), blacklist=(), lease_states=("active",))
    objects = [
        _lease("gm-member-01.corp.example.com", ip="10.0.0.1"),
    ]
    with caplog.at_level(logging.WARNING, logger="cloud_usage.nios.filter"):
        result = list(filter_objects(iter(objects), config))

    warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_messages) == 0


# ---------------------------------------------------------------------------
# Additional: Empty whitelist/blacklist behaviors
# ---------------------------------------------------------------------------

def test_empty_whitelist_passes_all():
    """Empty whitelist (default) means no whitelist filtering — all members pass."""
    config = FilterConfig(whitelist=(), blacklist=(), lease_states=("active",))
    objects = [
        _lease("gm-member-01.corp.example.com", ip="10.0.0.1"),
        _lease("ns1.example.com", ip="10.0.0.2"),
        _lease("other-host.example.com", ip="10.0.0.3"),
        _dns_a("192.168.1.1"),
    ]
    result = list(filter_objects(iter(objects), config))
    assert len(result) == 4  # all objects pass through


def test_empty_blacklist_passes_all():
    """Empty blacklist (default) means no blacklist filtering."""
    config = FilterConfig(whitelist=(), blacklist=(), lease_states=("active",))
    objects = [
        _lease("gm-member-01.corp.example.com", ip="10.0.0.1"),
        _lease("ns1.example.com", ip="10.0.0.2"),
    ]
    result = list(filter_objects(iter(objects), config))
    assert len(result) == 2


# ---------------------------------------------------------------------------
# FilterConfig: structural tests
# ---------------------------------------------------------------------------

def test_filter_config_is_frozen():
    """FilterConfig must be a frozen dataclass (immutable)."""
    config = FilterConfig(whitelist=("gm*",), blacklist=(), lease_states=("active", "static"))
    with pytest.raises((AttributeError, TypeError)):
        config.whitelist = ("new*",)  # type: ignore[misc]


def test_filter_config_tuple_fields():
    """FilterConfig fields must be tuples, not lists."""
    config = FilterConfig(whitelist=("gm*",), blacklist=("ns*",), lease_states=("active",))
    assert isinstance(config.whitelist, tuple)
    assert isinstance(config.blacklist, tuple)
    assert isinstance(config.lease_states, tuple)


def test_filter_config_defaults():
    """FilterConfig has sensible defaults: empty whitelist/blacklist, active+static lease_states."""
    config = FilterConfig()
    assert config.whitelist == ()
    assert config.blacklist == ()
    assert config.lease_states == ("active", "static")


# ---------------------------------------------------------------------------
# Lazy generator test
# ---------------------------------------------------------------------------

def test_filter_objects_is_lazy_generator():
    """filter_objects() must return a generator (lazy) — not materialise the stream."""
    import types
    config = FilterConfig(whitelist=(), blacklist=(), lease_states=("active",))
    objects = [_lease("gm-member-01.corp.example.com")]
    result = filter_objects(iter(objects), config)
    # Must return a generator, not a list or tuple
    assert isinstance(result, types.GeneratorType)
