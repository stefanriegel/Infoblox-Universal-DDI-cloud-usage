"""NIOS Grid backup parse error taxonomy.

NiosParseError is raised for unrecoverable failures: missing onedb.xml,
corrupted .tar.gz archive, or unreadable file. Callers (Phase 14 CLI,
Phase 15 dashboard) catch this for user-facing error messages.
"""

from __future__ import annotations


class NiosParseError(Exception):
    """Raised for unrecoverable NIOS backup parse failures.

    Covers: missing onedb.xml in archive, corrupted .tar.gz, file not found,
    and onedb.xml member that is not a regular file (e.g., symlink, directory).

    Callers (Phase 14 CLI entry point, Phase 15 dashboard upload handler)
    catch this exception to display a human-readable error message.
    """
