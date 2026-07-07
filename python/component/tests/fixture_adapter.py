"""Thin native fixture adapter: gzip + utf-8 + containment under
common/fixtures/ only.

Mirrors the harness's ``$fixture`` descriptor contract
(``test-harness/src/harness/fixtures.py``) for the subset a native suite
needs, so this language's tests can drive the same declarative cases the
central WASM harness runs. The error paths are pinned by
``test_fixture_adapter.py`` against the canonical conformance case names in
``test-harness/tests/fixture_conformance.py``.
"""

from __future__ import annotations

import gzip
import zlib
from pathlib import Path
from typing import Any

DEFAULT_MAX_BYTES = 8 * 1024 * 1024


class FixtureError(Exception):
    """A ``$fixture`` descriptor could not be resolved to text content."""


def resolve_fixture(
    descriptor: dict[str, Any], root: Path, max_bytes: int = DEFAULT_MAX_BYTES
) -> str:
    ref = descriptor.get("$fixture")
    if not isinstance(ref, str):
        raise FixtureError("'$fixture' must be a string repo-root-relative path")

    compression = descriptor.get("compression")
    if compression not in (None, "gzip"):
        raise FixtureError(f"unsupported compression {compression!r}")
    encoding = descriptor.get("encoding", "utf-8")
    if encoding != "utf-8":
        raise FixtureError(f"unsupported encoding {encoding!r}")

    if Path(ref).is_absolute():
        raise FixtureError(
            f"fixture '{ref}' must be a repo-root-relative path, not an absolute path"
        )

    # resolve() follows symlinks and collapses `..`, so the containment
    # check rejects both traversal and symlink escapes on real paths.
    path = (root / ref).resolve()
    if not path.is_relative_to((root / "common" / "fixtures").resolve()):
        raise FixtureError(f"fixture '{ref}' must resolve under common/fixtures/")
    if not path.is_file():
        raise FixtureError(f"fixture '{ref}' does not exist (or is not a regular file)")

    data = path.read_bytes()
    if len(data) > max_bytes:
        raise FixtureError(
            f"fixture '{ref}' is {len(data)} bytes on disk, "
            f"which exceeds the {max_bytes}-byte limit"
        )

    if compression == "gzip":
        try:
            data = gzip.decompress(data)
        except (OSError, EOFError, zlib.error) as exc:
            raise FixtureError(
                f"fixture '{ref}' is not valid gzip data: {exc}"
            ) from exc
        if len(data) > max_bytes:
            raise FixtureError(
                f"fixture '{ref}' decompresses to more than {max_bytes} bytes"
            )

    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FixtureError(f"fixture '{ref}' is not valid utf-8: {exc}") from exc
