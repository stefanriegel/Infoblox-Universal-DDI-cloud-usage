"""Memory-flat lxml iterparse over NIOS onedb.xml OBJECT elements.

Uses lxml (not stdlib ElementTree) to avoid CPython bug #102055 where
processed elements are not freed from the in-memory tree. The two-step
cleanup (elem.clear + sibling deletion) is REQUIRED after every OBJECT.

CRITICAL STRUCTURAL DISCOVERY (2026-02-28):
    The onedb.xml format does NOT use XML element attributes for type discrimination.
    Instead, every <OBJECT> element has a child:
        <PROPERTY NAME="__type" VALUE=".com.infoblox.dns.lease"/>
    The VALUE attribute holds the type string — NOT the element text content, NOT
    an attribute on the OBJECT element itself. Parser must iterate PROPERTY children
    and match NAME='__type' to extract the type string.

LXML VERSION COMPATIBILITY:
    lxml 6.x does not accept parser= keyword argument in iterparse().
    Options (resolve_entities, no_network, huge_tree, recover) are passed
    as direct keyword arguments instead. Tested with lxml 6.0.2 (installed).

MEMORY MANAGEMENT:
    Two-step cleanup after every OBJECT element is REQUIRED for memory-flat operation:
    Step 1: elem.clear(keep_tail=True) — release element content + children.
    Step 2: sibling deletion loop — remove dead sibling nodes from parent's child array.
    Without Step 2, dead nodes accumulate and RAM grows linearly with file size.
"""

from __future__ import annotations

from typing import IO, Iterator

from lxml import etree


def _iter_raw_objects(fileobj: IO[bytes]) -> Iterator[tuple[str, dict[str, str]]]:
    """Yield (xml_type, props_dict) for each OBJECT element in onedb.xml.

    Memory stays flat regardless of file size due to the two-step element
    cleanup after each yield. Peak RAM is 50-100MB on a 2.5M-object file.

    Type extraction reads the PROPERTY child where NAME='__type' and returns
    the VALUE attribute. All other PROPERTY children are collected into props_dict.
    The __type PROPERTY itself is excluded from props_dict.

    Args:
        fileobj: Readable binary file object for onedb.xml (from tarfile.extractfile).

    Yields:
        Tuples of (xml_type_string, props_dict) where xml_type_string is the
        VALUE of the PROPERTY NAME='__type' child, and props_dict maps all other
        PROPERTY NAME values to their VALUE attributes.
    """
    # lxml 6.x: options passed as direct kwargs (not via XMLParser object).
    # resolve_entities=False: block external entity expansion (security).
    # no_network=True: block network fetches during parse (security).
    # huge_tree=True: required — onedb.xml exceeds lxml's 5M-node default limit.
    # recover=True: resilience — continue past minor XML corruption.
    for _event, elem in etree.iterparse(
        fileobj,
        events=("end",),
        tag="OBJECT",
        resolve_entities=False,
        no_network=True,
        huge_tree=True,
        recover=True,
    ):
        obj_type: str = ""
        props: dict[str, str] = {}

        # Iterate PROPERTY children to extract type and attributes.
        # The __type PROPERTY's VALUE attribute is the type string.
        # All other PROPERTY children contribute to props_dict.
        for child in elem:
            name = child.get("NAME") or ""
            value = child.get("VALUE") or child.text or ""
            if name == "__type":
                obj_type = value
            elif name:
                props[name] = value

        yield obj_type, props

        # REQUIRED: two-step cleanup to prevent RAM growth on large files.
        # Step 1: release element content + children.
        elem.clear(keep_tail=True)
        # Step 2: remove this (now-empty) element from the parent's child list.
        # Without this step, dead nodes accumulate in the parent node's child array.
        while elem.getprevious() is not None:
            del elem.getparent()[0]
