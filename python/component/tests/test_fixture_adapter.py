"""Fixture-adapter error paths, mirroring the canonical conformance case
names in ``test-harness/tests/fixture_conformance.py`` (the relevant subset
plus descriptor-shape checks) so drift between the languages' adapters
stays grep-detectable: missing-file, path-is-a-directory, corrupt-gzip,
non-utf8-bytes, dotdot-traversal, absolute-path, oversized-on-disk,
gzip-decompressed-oversized, non-string-fixture-path,
unsupported-compression-value, unsupported-encoding-value.
"""

import gzip

import pytest

from fixture_adapter import FixtureError, resolve_fixture


def _fixture_tree(tmp_path):
    (tmp_path / "common" / "fixtures" / "html-parser").mkdir(parents=True)
    return tmp_path


def _write(root, rel, data: bytes):
    path = root / "common" / "fixtures" / rel
    path.write_bytes(data)
    return path


def test_happy_path_plain_and_gzip(tmp_path):
    root = _fixture_tree(tmp_path)
    _write(root, "html-parser/sample.html", b"<html>plain</html>")
    _write(root, "html-parser/page.html.gz", gzip.compress(b"<html>gzipped</html>"))
    assert (
        resolve_fixture({"$fixture": "common/fixtures/html-parser/sample.html"}, root)
        == "<html>plain</html>"
    )
    assert (
        resolve_fixture(
            {
                "$fixture": "common/fixtures/html-parser/page.html.gz",
                "compression": "gzip",
                "encoding": "utf-8",
            },
            root,
        )
        == "<html>gzipped</html>"
    )


def test_missing_file(tmp_path):
    root = _fixture_tree(tmp_path)
    with pytest.raises(FixtureError, match="does not exist"):
        resolve_fixture({"$fixture": "common/fixtures/html-parser/missing.html"}, root)


def test_path_is_a_directory(tmp_path):
    root = _fixture_tree(tmp_path)
    with pytest.raises(FixtureError, match="does not exist"):
        resolve_fixture({"$fixture": "common/fixtures/html-parser"}, root)


def test_corrupt_gzip(tmp_path):
    root = _fixture_tree(tmp_path)
    _write(root, "html-parser/corrupt.html.gz", b"this is not gzip data at all")
    with pytest.raises(FixtureError, match="not valid gzip data"):
        resolve_fixture(
            {
                "$fixture": "common/fixtures/html-parser/corrupt.html.gz",
                "compression": "gzip",
            },
            root,
        )


def test_non_utf8_bytes(tmp_path):
    root = _fixture_tree(tmp_path)
    _write(root, "html-parser/latin1.html", "café".encode("latin-1"))
    with pytest.raises(FixtureError, match="not valid utf-8"):
        resolve_fixture({"$fixture": "common/fixtures/html-parser/latin1.html"}, root)


def test_dotdot_traversal(tmp_path):
    root = _fixture_tree(tmp_path)
    (root / "secret.txt").write_bytes(b"top secret")
    with pytest.raises(FixtureError, match="must resolve under common/fixtures/"):
        resolve_fixture({"$fixture": "common/fixtures/../../secret.txt"}, root)


def test_absolute_path(tmp_path):
    root = _fixture_tree(tmp_path)
    with pytest.raises(FixtureError, match="must be a repo-root-relative path"):
        resolve_fixture({"$fixture": "/etc/hostname"}, root)


def test_oversized_on_disk(tmp_path):
    root = _fixture_tree(tmp_path)
    _write(root, "html-parser/big.html", b"x" * 64)
    with pytest.raises(FixtureError, match="is 64 bytes on disk"):
        resolve_fixture(
            {"$fixture": "common/fixtures/html-parser/big.html"}, root, max_bytes=16
        )


def test_gzip_decompressed_oversized(tmp_path):
    root = _fixture_tree(tmp_path)
    _write(root, "html-parser/bomb.html.gz", gzip.compress(b"\0" * 262144))
    with pytest.raises(FixtureError, match="decompresses to more than 1024 bytes"):
        resolve_fixture(
            {
                "$fixture": "common/fixtures/html-parser/bomb.html.gz",
                "compression": "gzip",
            },
            root,
            max_bytes=1024,
        )


def test_non_string_fixture_path(tmp_path):
    root = _fixture_tree(tmp_path)
    with pytest.raises(FixtureError, match="'\\$fixture' must be a string"):
        resolve_fixture({"$fixture": 42}, root)


def test_unsupported_compression_value(tmp_path):
    root = _fixture_tree(tmp_path)
    with pytest.raises(FixtureError, match="unsupported compression 'zstd'"):
        resolve_fixture(
            {"$fixture": "common/fixtures/html-parser/x", "compression": "zstd"}, root
        )


def test_unsupported_encoding_value(tmp_path):
    root = _fixture_tree(tmp_path)
    with pytest.raises(FixtureError, match="unsupported encoding 'latin-1'"):
        resolve_fixture(
            {"$fixture": "common/fixtures/html-parser/x", "encoding": "latin-1"}, root
        )
