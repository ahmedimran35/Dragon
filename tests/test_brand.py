"""The product is Dragon: the old names live on only in ``NOTICE`` (GPL attribution).

Every tracked text file in the repository is walked and checked for the old product name
in any of its spellings, and for the old agent name as a word. ``NOTICE`` is the one
exemption: the GPL attribution there is kept as written and never edited. Build output and
binary files are skipped; so are the trees a checkout carries but the repository does not
own (``.git``, virtual environments, ``node_modules``).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTICE = "NOTICE"

# directories never walked into: metadata, dependencies and build output
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "dist",
    "build",
    "target",
    ".cache",
    ".next",
    ".turbo",
    "coverage",
}
# committed build output, by path relative to the root
SKIP_PATHS = {"web/dist", "web/build", "dragon/server/static"}
# files that are not text even when no NUL byte happens to be in the first block
BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tgz",
    ".whl",
    ".jar",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".mp3",
    ".mp4",
    ".mov",
    ".db",
    ".sqlite",
    ".pem",
    ".key",
    ".keystore",
}

# the old product name in every spelling it had, and the old agent name as a word;
# case-insensitive: the rule is the name, not its capitalisation. The name is put
# together from parts so that this file never carries it either.
_PARTS = ("nano", "mus", "e")
_OLD_NAME = "".join(_PARTS)
_OLD_NAME_DASHED = _PARTS[0] + "-" + _PARTS[1] + _PARTS[2]
_OLD_AGENT = r"\b" + _PARTS[1] + _PARTS[2] + r"\b"
PATTERNS = [
    re.compile(_OLD_NAME, re.IGNORECASE),
    re.compile(_OLD_NAME_DASHED, re.IGNORECASE),
    re.compile(_OLD_AGENT, re.IGNORECASE),
]


def _text_files() -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel_dir = Path(dirpath).relative_to(ROOT)
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIP_DIRS and str(rel_dir / d) not in SKIP_PATHS
        )
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if name == NOTICE and rel_dir == Path("."):
                continue
            if path.suffix.lower() in BINARY_SUFFIXES:
                continue
            out.append(path)
    return out


def _is_text(path: Path) -> bool:
    try:
        return b"\x00" not in path.read_bytes()[:8192]
    except OSError:  # pragma: no cover — unreadable files are not text to check
        return False


def test_no_old_names_outside_notice() -> None:
    hits: list[str] = []
    for path in _text_files():
        if not _is_text(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for pattern in PATTERNS:
            for i, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    hits.append(f"{rel}:{i}: {line.strip()[:120]}")
    assert not hits, "the old name survives outside NOTICE:\n" + "\n".join(hits[:20])
