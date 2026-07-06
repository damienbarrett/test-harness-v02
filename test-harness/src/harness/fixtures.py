"""Fixture-descriptor resolution for file-backed test inputs.

This module is the single owner of the ``$fixture`` descriptor contract.
Both ``harness.contracts`` (which materializes fixtures *before* validating
a case's input against the function's parameter schema) and ``harness.cli``
(which materializes them before building call arguments) resolve through
``resolve_fixtures`` -- there is exactly one implementation of the path
safety, size limit, decompression, and decoding rules.

A fixture descriptor is any JSON object containing a ``$fixture`` key::

    {
      "$fixture": "common/fixtures/html-parser/products.html.gz",
      "compression": "gzip",
      "encoding": "utf-8"
    }

Fields:

* ``$fixture`` (required, string): the fixture file's repo-root-relative
  POSIX path. The fully resolved real path (after following symlinks) must
  stay under ``common/fixtures/``; ``..`` traversal, absolute paths, and
  symlink escapes are all rejected.
* ``compression`` (optional): only ``"gzip"`` is supported. There is no
  inference from the file extension -- compression is applied only when
  declared, and declaring it for a non-gzip file is an error.
* ``encoding`` (optional, default ``"utf-8"``): only ``"utf-8"`` is
  supported.

Any other key in the descriptor object is an error -- this catches typos
like ``"compresion"`` instead of silently ignoring them.

Size limits: both the on-disk file size and the decompressed size must stay
within ``max_bytes`` (default 8 MiB, overridable via the
``HARNESS_FIXTURE_MAX_BYTES`` environment variable). Gzip data is
decompressed incrementally and abandoned as soon as the output exceeds the
limit, so a small-on-disk gzip bomb cannot exhaust memory.

Every failure raises ``FixtureError`` with a distinct, actionable message
naming the fixture involved.
"""

from __future__ import annotations

import gzip
import os
import zlib
from pathlib import Path
from typing import Any

DEFAULT_MAX_BYTES = 8 * 1024 * 1024  # 8 MiB
MAX_BYTES_ENV_VAR = "HARNESS_FIXTURE_MAX_BYTES"

_ALLOWED_KEYS = frozenset({"$fixture", "compression", "encoding"})
_SUPPORTED_COMPRESSIONS = ("gzip",)
_SUPPORTED_ENCODINGS = ("utf-8",)
_GZIP_CHUNK_BYTES = 64 * 1024


class FixtureError(Exception):
    """A ``$fixture`` descriptor could not be resolved to text content."""


def default_max_bytes() -> int:
    """The fixture size limit in bytes: ``HARNESS_FIXTURE_MAX_BYTES`` if
    set (a positive integer), otherwise 8 MiB."""
    raw = os.environ.get(MAX_BYTES_ENV_VAR)
    if raw is None:
        return DEFAULT_MAX_BYTES
    try:
        value = int(raw)
    except ValueError as exc:
        raise FixtureError(
            f"{MAX_BYTES_ENV_VAR} must be a whole number of bytes, got {raw!r}"
        ) from exc
    if value <= 0:
        raise FixtureError(f"{MAX_BYTES_ENV_VAR} must be positive, got {value}")
    return value


def resolve_fixtures(value: Any, root: Path, max_bytes: int | None = None) -> Any:
    """Recursively walk any JSON value and replace every fixture descriptor
    (any dict containing a ``$fixture`` key, at any nesting depth) with the
    decoded text content of the file it names. Everything else passes
    through unchanged; the input value is never mutated.

    ``root`` is the repository root that ``$fixture`` paths are resolved
    against. ``max_bytes`` bounds both the on-disk and the decompressed
    fixture size; ``None`` means "use ``default_max_bytes()``".

    Raises ``FixtureError`` for every failure mode (see module docstring).
    """
    if max_bytes is None:
        max_bytes = default_max_bytes()
    return _resolve(value, root, max_bytes)


def _resolve(value: Any, root: Path, max_bytes: int) -> Any:
    if isinstance(value, dict):
        if "$fixture" in value:
            return _resolve_descriptor(value, root, max_bytes)
        return {key: _resolve(item, root, max_bytes) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, root, max_bytes) for item in value]
    return value


def _resolve_descriptor(descriptor: dict[str, Any], root: Path, max_bytes: int) -> str:
    unknown = sorted(set(descriptor) - _ALLOWED_KEYS)
    if unknown:
        raise FixtureError(
            f"unknown fixture descriptor key(s) {unknown}; "
            f"allowed keys are {sorted(_ALLOWED_KEYS)}"
        )

    ref = descriptor["$fixture"]
    if not isinstance(ref, str):
        raise FixtureError(
            f"'$fixture' must be a string repo-root-relative POSIX path, got {ref!r}"
        )

    compression = descriptor.get("compression")
    if compression is not None and compression not in _SUPPORTED_COMPRESSIONS:
        raise FixtureError(
            f"fixture '{ref}': unsupported compression {compression!r}; "
            f"supported compression values: {list(_SUPPORTED_COMPRESSIONS)}"
        )

    encoding = descriptor.get("encoding", "utf-8")
    if encoding not in _SUPPORTED_ENCODINGS:
        raise FixtureError(
            f"fixture '{ref}': unsupported encoding {encoding!r}; "
            f"supported encoding values: {list(_SUPPORTED_ENCODINGS)}"
        )

    path = _confined_path(ref, root)

    if not path.is_file():
        raise FixtureError(f"fixture '{ref}' does not exist (or is not a regular file)")

    disk_size = path.stat().st_size
    if disk_size > max_bytes:
        raise FixtureError(
            f"fixture '{ref}' is {disk_size} bytes on disk, which exceeds the "
            f"{max_bytes}-byte limit (raise it via {MAX_BYTES_ENV_VAR})"
        )

    if compression == "gzip":
        data = _read_gzip(path, ref, max_bytes)
    else:
        data = path.read_bytes()

    try:
        return data.decode(encoding)
    except UnicodeDecodeError as exc:
        raise FixtureError(f"fixture '{ref}' is not valid {encoding}: {exc}") from exc


def _confined_path(ref: str, root: Path) -> Path:
    """Resolve ``ref`` against the repo root and require the fully-resolved
    real path (after following symlinks) to stay under the real path of
    ``common/fixtures/`` -- containment is checked on realpaths, never on
    string prefixes."""
    if Path(ref).is_absolute():
        raise FixtureError(
            f"fixture '{ref}' must be a repo-root-relative path, not an absolute path"
        )
    fixtures_root = (root / "common" / "fixtures").resolve()
    candidate = (root / ref).resolve()
    if not candidate.is_relative_to(fixtures_root):
        raise FixtureError(
            f"fixture '{ref}' must resolve under common/fixtures/ "
            "(path traversal and symlink escapes are rejected)"
        )
    return candidate


def _read_gzip(path: Path, ref: str, max_bytes: int) -> bytes:
    """Decompress ``path`` incrementally, aborting as soon as the output
    exceeds ``max_bytes`` -- a gzip bomb is rejected without ever holding
    more than ``max_bytes`` (plus one chunk) in memory."""
    chunks: list[bytes] = []
    total = 0
    try:
        with gzip.open(path, "rb") as fh:
            while True:
                chunk = fh.read(_GZIP_CHUNK_BYTES)
                if not chunk:
                    return b"".join(chunks)
                total += len(chunk)
                if total > max_bytes:
                    raise FixtureError(
                        f"fixture '{ref}' decompresses to more than {max_bytes} bytes "
                        f"(the size limit; raise it via {MAX_BYTES_ENV_VAR})"
                    )
                chunks.append(chunk)
    except (EOFError, OSError, zlib.error) as exc:
        raise FixtureError(f"fixture '{ref}' is not valid gzip data: {exc}") from exc
