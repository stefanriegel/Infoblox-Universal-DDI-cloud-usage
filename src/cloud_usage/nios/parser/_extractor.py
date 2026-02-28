"""NIOS backup archive extractor.

Opens a .tar.gz backup and yields the onedb.xml file object without disk extraction.
Uses tarfile r:gz seeking mode (not r|gz pipe mode) to avoid CPython #121109.

CPython issue #121109: tarfile r|gz (pipe mode) is 14x slower than r:gz (seek mode)
for random access patterns. This is significant for a 2.5GB file with 2.5M objects.
"""

from __future__ import annotations

import datetime
import tarfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from cloud_usage.nios.errors import NiosParseError


@contextmanager
def _open_onedb_xml(path: str | Path) -> Generator[tuple, None, None]:
    """Yield (io.BufferedReader, snapshot_date_str) for onedb.xml inside .tar.gz.

    No disk extraction. Seeking mode (r:gz) used for performance.
    snapshot_date derived from tar member mtime in UTC ISO date format.

    Matches the exact basename "onedb.xml" (not endswith) to avoid falsely
    matching filenames like "notonedb.xml".

    Args:
        path: Path to the .tar.gz NIOS Grid backup file.

    Yields:
        Tuple of (fileobj, snapshot_date_str) where fileobj is the onedb.xml
        binary file object and snapshot_date_str is 'YYYY-MM-DD' or None.

    Raises:
        NiosParseError: If archive is corrupted, missing, or lacks onedb.xml.
    """
    path = Path(path)
    try:
        with tarfile.open(path, "r:gz") as tar:
            for member in tar.getmembers():
                # Exact basename match — endswith("onedb.xml") would falsely match "notonedb.xml".
                if Path(member.name).name == "onedb.xml":
                    snapshot_date: str | None = None
                    try:
                        snapshot_date = datetime.datetime.fromtimestamp(
                            member.mtime, tz=datetime.timezone.utc
                        ).strftime("%Y-%m-%d")
                    except (OSError, ValueError, OverflowError):
                        pass  # mtime unavailable — snapshot_date remains None
                    fileobj = tar.extractfile(member)
                    if fileobj is None:
                        raise NiosParseError(
                            f"onedb.xml is not a regular file in {path} "
                            f"(it may be a symlink or directory)"
                        )
                    yield fileobj, snapshot_date
                    return
            members_preview = [m.name for m in tar.getmembers()[:10]]
            raise NiosParseError(
                f"onedb.xml not found in {path}. "
                f"Archive contains: {members_preview}"
            )
    except tarfile.TarError as exc:
        raise NiosParseError(
            f"Cannot open backup archive {path}: {exc}"
        ) from exc
