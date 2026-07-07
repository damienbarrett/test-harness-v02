import copy
from pathlib import Path

import pytest

from harness.fixtures import (
    DEFAULT_MAX_BYTES,
    MAX_BYTES_ENV_VAR,
    FixtureError,
    default_max_bytes,
    resolve_fixtures,
)

from .fixture_conformance import CONFORMANCE_CASES

# test-harness/tests/test_fixtures.py -> repo root is two levels up.
_REPO_ROOT = Path(__file__).resolve().parents[2]


# --- shared conformance cases ---------------------------------------------
#
# Every fixture-resolution adapter (harness.fixtures today, any future
# native-language adapter) must pass these same cases -- see
# tests/fixture_conformance.py.


@pytest.mark.parametrize("case", CONFORMANCE_CASES, ids=lambda case: case.name)
def test_fixture_resolution_conformance(case, tmp_path, monkeypatch):
    monkeypatch.delenv(MAX_BYTES_ENV_VAR, raising=False)
    case.build(tmp_path)
    value = {"html": case.descriptor}
    if case.expect_error is not None:
        with pytest.raises(FixtureError) as exc_info:
            resolve_fixtures(value, tmp_path, case.max_bytes)
        assert case.expect_error in str(exc_info.value)
    else:
        assert resolve_fixtures(value, tmp_path, case.max_bytes) == {
            "html": case.expect_text
        }


# --- recursive walk semantics ----------------------------------------------


def _write_fixture(root: Path, rel: str, text: str) -> str:
    path = root / "common" / "fixtures" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return f"common/fixtures/{rel}"


def test_descriptor_at_the_top_level_resolves_to_text(tmp_path):
    ref = _write_fixture(tmp_path, "html-parser/top.html", "<html>top</html>")
    assert resolve_fixtures({"$fixture": ref}, tmp_path) == "<html>top</html>"


def test_descriptors_nested_in_dicts_and_lists_are_replaced_in_place(tmp_path):
    ref = _write_fixture(tmp_path, "html-parser/nested.html", "<p>deep</p>")
    value = {
        "html": {"$fixture": ref},
        "pages": [[{"$fixture": ref}], "literal"],
        "meta": {"inner": {"$fixture": ref}, "count": 3},
    }
    assert resolve_fixtures(value, tmp_path) == {
        "html": "<p>deep</p>",
        "pages": [["<p>deep</p>"], "literal"],
        "meta": {"inner": "<p>deep</p>", "count": 3},
    }


def test_non_descriptor_values_pass_through_unchanged(tmp_path):
    value = {
        "text": "plain",
        "number": 4294967295,
        "flag": True,
        "nothing": None,
        "empty-dict": {},
        "empty-list": [],
        "plain-dict": {"name": "Task 1"},
    }
    assert resolve_fixtures(value, tmp_path) == value


def test_input_value_is_not_mutated(tmp_path):
    ref = _write_fixture(tmp_path, "html-parser/pure.html", "<html></html>")
    value = {"html": {"$fixture": ref}, "tags": [{"$fixture": ref}]}
    snapshot = copy.deepcopy(value)
    resolve_fixtures(value, tmp_path)
    assert value == snapshot


# --- size-limit configuration -----------------------------------------------


def test_default_max_bytes_is_8_mib_when_env_var_is_unset(monkeypatch):
    monkeypatch.delenv(MAX_BYTES_ENV_VAR, raising=False)
    assert default_max_bytes() == DEFAULT_MAX_BYTES == 8388608


def test_env_var_overrides_the_default_limit(monkeypatch):
    monkeypatch.setenv(MAX_BYTES_ENV_VAR, "123")
    assert default_max_bytes() == 123


def test_env_var_limit_applies_when_no_explicit_limit_is_passed(tmp_path, monkeypatch):
    ref = _write_fixture(tmp_path, "html-parser/limited.html", "0123456789")
    monkeypatch.setenv(MAX_BYTES_ENV_VAR, "4")
    with pytest.raises(FixtureError) as exc_info:
        resolve_fixtures({"$fixture": ref}, tmp_path)
    assert "is 10 bytes on disk" in str(exc_info.value)
    assert "4-byte limit" in str(exc_info.value)


def test_non_integer_env_var_is_a_clear_error(monkeypatch):
    monkeypatch.setenv(MAX_BYTES_ENV_VAR, "lots")
    with pytest.raises(FixtureError) as exc_info:
        default_max_bytes()
    assert MAX_BYTES_ENV_VAR in str(exc_info.value)
    assert "'lots'" in str(exc_info.value)


def test_non_positive_env_var_is_a_clear_error(monkeypatch):
    monkeypatch.setenv(MAX_BYTES_ENV_VAR, "0")
    with pytest.raises(FixtureError) as exc_info:
        default_max_bytes()
    assert MAX_BYTES_ENV_VAR in str(exc_info.value)
    assert "positive" in str(exc_info.value)


# --- the real captured fixture ----------------------------------------------


def test_real_newworld_capture_resolves_through_the_real_repo_root():
    """Integration: the gzipped New World search capture under the real
    ``common/fixtures/html-parser/`` resolves (gzip + utf-8) to the exact
    text of the original 592574-byte capture. See
    common/fixtures/html-parser/README.md for provenance."""
    descriptor = {
        "$fixture": "common/fixtures/html-parser/newworld-search-eggs.html.gz",
        "compression": "gzip",
        "encoding": "utf-8",
    }
    resolved = resolve_fixtures({"html": descriptor}, _REPO_ROOT)
    text = resolved["html"]
    assert len(text.encode("utf-8")) == 592574
    lowered = text.lower()
    assert "<html" in lowered
    assert "new world" in lowered
