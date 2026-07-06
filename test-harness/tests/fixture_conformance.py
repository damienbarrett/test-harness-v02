"""Reusable fixture-resolution conformance cases.

Any consumer of the fixture-descriptor contract -- ``harness.fixtures``
itself today, and any future native-language fixture adapter (see
common/README.md for the criterion for adding one) -- must pass this same
set of cases. Each case is a ``(name, tree-builder, descriptor,
expectation)`` record: the builder materializes the required files under a
throwaway repo root, the descriptor is the ``$fixture`` JSON object under
test, and the expectation is either the exact decoded text
(``expect_text``) or a fragment the error message must contain
(``expect_error``). ``max_bytes`` overrides the size limit for the
size-related cases.

Import ``CONFORMANCE_CASES`` and parametrize the adapter under test over
it -- do not copy individual cases into adapter-specific test files, or the
adapters will drift apart.
"""

from __future__ import annotations

import gzip
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class FixtureConformanceCase:
    """One fixture-resolution scenario every adapter must agree on."""

    name: str
    build: Callable[[Path], None]
    descriptor: dict[str, Any]
    expect_text: str | None = None
    expect_error: str | None = None
    max_bytes: int | None = None


def _write(root: Path, rel: str, data: bytes) -> Path:
    """Write ``data`` at ``common/fixtures/{rel}`` under ``root``."""
    path = root / "common" / "fixtures" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _build_nothing(root: Path) -> None:
    (root / "common" / "fixtures").mkdir(parents=True, exist_ok=True)


def _build_plain(root: Path) -> None:
    _write(root, "html-parser/sample.html", "<html>plain</html>".encode("utf-8"))


def _build_unicode(root: Path) -> None:
    _write(root, "html-parser/unicode.html", "<p>café ☕</p>".encode("utf-8"))


def _build_gzip(root: Path) -> None:
    _write(root, "html-parser/page.html.gz", gzip.compress("<html>gzipped</html>".encode("utf-8")))


def _build_corrupt_gzip(root: Path) -> None:
    _write(root, "html-parser/corrupt.html.gz", b"this is not gzip data at all")


def _build_truncated_gzip(root: Path) -> None:
    data = gzip.compress(b"x" * 4096)
    _write(root, "html-parser/truncated.html.gz", data[: len(data) // 2])


def _build_non_utf8(root: Path) -> None:
    _write(root, "html-parser/latin1.html", "café".encode("latin-1"))


def _build_non_utf8_gzip(root: Path) -> None:
    _write(root, "html-parser/latin1.html.gz", gzip.compress("café".encode("latin-1")))


def _build_outside_secret(root: Path) -> None:
    (root / "secret.txt").write_bytes(b"top secret")
    (root / "common" / "fixtures").mkdir(parents=True, exist_ok=True)


def _build_symlink_escape(root: Path) -> None:
    (root / "secret.txt").write_bytes(b"top secret")
    d = root / "common" / "fixtures" / "html-parser"
    d.mkdir(parents=True, exist_ok=True)
    (d / "escape.html").symlink_to(root / "secret.txt")


def _build_oversized(root: Path) -> None:
    _write(root, "html-parser/big.html", b"x" * 64)


def _build_gzip_bomb(root: Path) -> None:
    # A few hundred bytes on disk, 256 KiB decompressed: the on-disk size
    # check alone must NOT be enough to accept it.
    _write(root, "html-parser/bomb.html.gz", gzip.compress(b"\0" * 262144, compresslevel=9))


CONFORMANCE_CASES: list[FixtureConformanceCase] = [
    # --- happy paths -------------------------------------------------------
    FixtureConformanceCase(
        name="plain-text-default-encoding",
        build=_build_plain,
        descriptor={"$fixture": "common/fixtures/html-parser/sample.html"},
        expect_text="<html>plain</html>",
    ),
    FixtureConformanceCase(
        name="plain-text-explicit-utf8",
        build=_build_plain,
        descriptor={"$fixture": "common/fixtures/html-parser/sample.html", "encoding": "utf-8"},
        expect_text="<html>plain</html>",
    ),
    FixtureConformanceCase(
        name="utf8-multibyte-content",
        build=_build_unicode,
        descriptor={"$fixture": "common/fixtures/html-parser/unicode.html"},
        expect_text="<p>café ☕</p>",
    ),
    FixtureConformanceCase(
        name="gzip-with-explicit-encoding",
        build=_build_gzip,
        descriptor={
            "$fixture": "common/fixtures/html-parser/page.html.gz",
            "compression": "gzip",
            "encoding": "utf-8",
        },
        expect_text="<html>gzipped</html>",
    ),
    FixtureConformanceCase(
        name="gzip-default-encoding",
        build=_build_gzip,
        descriptor={"$fixture": "common/fixtures/html-parser/page.html.gz", "compression": "gzip"},
        expect_text="<html>gzipped</html>",
    ),
    # --- missing / wrong file ---------------------------------------------
    FixtureConformanceCase(
        name="missing-file",
        build=_build_nothing,
        descriptor={"$fixture": "common/fixtures/html-parser/missing.html"},
        expect_error="fixture 'common/fixtures/html-parser/missing.html' does not exist",
    ),
    FixtureConformanceCase(
        name="path-is-a-directory",
        build=_build_plain,
        descriptor={"$fixture": "common/fixtures/html-parser"},
        expect_error="does not exist",
    ),
    # --- corrupt / undeclared content ---------------------------------------
    FixtureConformanceCase(
        name="corrupt-gzip",
        build=_build_corrupt_gzip,
        descriptor={
            "$fixture": "common/fixtures/html-parser/corrupt.html.gz",
            "compression": "gzip",
        },
        expect_error="not valid gzip data",
    ),
    FixtureConformanceCase(
        name="truncated-gzip",
        build=_build_truncated_gzip,
        descriptor={
            "$fixture": "common/fixtures/html-parser/truncated.html.gz",
            "compression": "gzip",
        },
        expect_error="not valid gzip data",
    ),
    FixtureConformanceCase(
        name="non-utf8-bytes",
        build=_build_non_utf8,
        descriptor={"$fixture": "common/fixtures/html-parser/latin1.html"},
        expect_error="not valid utf-8",
    ),
    FixtureConformanceCase(
        name="non-utf8-bytes-inside-gzip",
        build=_build_non_utf8_gzip,
        descriptor={
            "$fixture": "common/fixtures/html-parser/latin1.html.gz",
            "compression": "gzip",
        },
        expect_error="not valid utf-8",
    ),
    # --- path safety ---------------------------------------------------------
    FixtureConformanceCase(
        name="dotdot-traversal",
        build=_build_outside_secret,
        descriptor={"$fixture": "common/fixtures/../../secret.txt"},
        expect_error="must resolve under common/fixtures/",
    ),
    FixtureConformanceCase(
        name="absolute-path",
        build=_build_nothing,
        descriptor={"$fixture": "/etc/hostname"},
        expect_error="must be a repo-root-relative path",
    ),
    FixtureConformanceCase(
        name="symlink-escape",
        build=_build_symlink_escape,
        descriptor={"$fixture": "common/fixtures/html-parser/escape.html"},
        expect_error="must resolve under common/fixtures/",
    ),
    # --- size limits ---------------------------------------------------------
    FixtureConformanceCase(
        name="oversized-on-disk",
        build=_build_oversized,
        descriptor={"$fixture": "common/fixtures/html-parser/big.html"},
        expect_error="fixture 'common/fixtures/html-parser/big.html' is 64 bytes on disk",
        max_bytes=16,
    ),
    FixtureConformanceCase(
        name="gzip-decompressed-oversized",
        build=_build_gzip_bomb,
        descriptor={
            "$fixture": "common/fixtures/html-parser/bomb.html.gz",
            "compression": "gzip",
        },
        expect_error="decompresses to more than 1024 bytes",
        max_bytes=1024,
    ),
    # --- descriptor shape ------------------------------------------------------
    FixtureConformanceCase(
        name="unknown-descriptor-key",
        build=_build_plain,
        descriptor={"$fixture": "common/fixtures/html-parser/sample.html", "compresion": "gzip"},
        expect_error="unknown fixture descriptor key(s) ['compresion']",
    ),
    FixtureConformanceCase(
        name="unsupported-compression-value",
        build=_build_gzip,
        descriptor={"$fixture": "common/fixtures/html-parser/page.html.gz", "compression": "zstd"},
        expect_error="unsupported compression 'zstd'",
    ),
    FixtureConformanceCase(
        name="unsupported-encoding-value",
        build=_build_plain,
        descriptor={"$fixture": "common/fixtures/html-parser/sample.html", "encoding": "latin-1"},
        expect_error="unsupported encoding 'latin-1'",
    ),
    FixtureConformanceCase(
        name="non-string-fixture-path",
        build=_build_nothing,
        descriptor={"$fixture": 42},
        expect_error="'$fixture' must be a string",
    ),
]
