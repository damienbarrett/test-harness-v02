"""Implementation directory discovery.

Any top-level directory containing a ``component/`` sub-directory is treated
as a language implementation, except entries in ``SKIP_DIRS``.
"""

from __future__ import annotations

from pathlib import Path

# Directories to skip when scanning for implementation dirs.
SKIP_DIRS = {
    "common",
    "container",
    "test-harness",
    ".git",
    ".task",
    "node_modules",
}


def discover_implementations(root: Path) -> list[str]:
    """Find language directories that contain a ``component/`` sub-dir."""
    langs: list[str] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if child.name in SKIP_DIRS:
            continue
        if (child / "component").is_dir():
            langs.append(child.name)
    return langs
