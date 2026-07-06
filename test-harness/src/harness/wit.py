"""WIT world discovery.

Minimal regex-based extraction of world names from WIT files under
``common/wit/``. This intentionally does not parse namespace, package, or
exported-interface information yet -- that correction is Phase 2 of
``docs/refactoring-plan.md``. Phase 1 preserves the current behavior exactly:
every world found in every ``*.wit`` file is returned, in file-then-match
order, with no deduplication and no filtering by interface.
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import WitWorld

_WORLD_RE = re.compile(r"^\s*world\s+([\w-]+)\s*\{", re.MULTILINE)


def discover_worlds(root: Path) -> list[WitWorld]:
    """Extract world names from WIT files under ``common/wit/``."""
    wit_dir = root / "common" / "wit"
    worlds: list[WitWorld] = []
    if not wit_dir.is_dir():
        return worlds
    for wit_file in sorted(wit_dir.glob("*.wit")):
        text = wit_file.read_text()
        worlds.extend(WitWorld(name=name) for name in _WORLD_RE.findall(text))
    return worlds
