"""A file kept to the one person it belongs to.

POSIX takes a mode: ``0600``, the owner reads and writes and nobody else does. Windows
has no mode, and ``chmod`` there clears a read-only flag and nothing else, so every call
to it around this codebase left the calendars, address books, token and key files it
meant to protect open to the machine's other local accounts. The ACL is set instead:
inheritance off, the one account in full control.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def atomic_write(path: Path | str, text: str, *, mode: int | None = None) -> None:
    """Write ``text`` to ``path`` atomically: a temp file beside it, ``fsync``, ``os.replace``.

    A crash mid-write cannot leave a truncated or half-written file — the reader sees
    either the old content or the new. ``mode`` sets permissions on a newly created file
    (the existing one keeps its own).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def keep_private(path: Path | str) -> None:
    """Make ``path`` readable by its owner and no other local account.

    On POSIX this is ``chmod 0600`` and raises as that does. On Windows the inherited
    access rules come off and the current account alone keeps full control; a command
    that cannot run (no ``USERNAME``, an ``icacls`` that refused) is left alone rather
    than unwriting the file, the way a mode no platform honours would be.
    """
    if sys.platform == "win32":
        import subprocess

        user = os.environ.get("USERNAME")
        if user:  # a service without one keeps the file's default rules
            subprocess.run(
                ["icacls", os.fspath(path), "/inheritance:r", "/grant:r", f"{user}:(F)"],
                capture_output=True,
                check=False,
            )
    else:
        os.chmod(path, 0o600)
