"""Behavioral parity tests: run real `task` and `just` binaries against a
generated fixture project (Taskfile.yml + justfile + lifecycle.sh, following
the same canonical convention introduced in docs/refactoring-plan.md
Phase 6) and assert their observable behavior is equivalent.

`check-runner-parity.py` only proves the two DSL *texts* agree; these tests
prove that agreement actually produces identical *runtime* behavior:
executed commands' effects, environment variables seen by the script,
working directory, dependency ordering, cleanup paths, and failure
propagation.

Skip-free by design: if `task` or `just` is missing from PATH, that's a hard
failure (`pytest.fail`), not a skip -- both are required, Nix-provided
tooling in this repo (see test-harness/flake.nix), so their absence means the
environment is broken, not that the check is inapplicable.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

LIFECYCLE_SH = """\
#!/usr/bin/env bash
set -eu

cmd_build() {
  echo "build" >> order.log
  echo "built" > build.marker
  : > cache.marker
}

cmd_test() {
  echo "test" >> order.log
  echo "tested" > test.marker
}

cmd_envcheck() {
  echo "LIFECYCLE_TEST_VAR=${LIFECYCLE_TEST_VAR:-unset}" > env.out
}

cmd_pwdcheck() {
  pwd > pwd.out
}

cmd_clean() {
  rm -f build.marker test.marker order.log
}

cmd_purge() {
  rm -f cache.marker
}

cmd_failing() {
  echo "failing on purpose" >&2
  exit 7
}

cmd_depfail_dependent() {
  : > depfail_dependent.marker
}

verb="${1:-}"
case "$verb" in
  build) cmd_build ;;
  test) cmd_test ;;
  envcheck) cmd_envcheck ;;
  pwdcheck) cmd_pwdcheck ;;
  clean) cmd_clean ;;
  purge) cmd_purge ;;
  failing) cmd_failing ;;
  depfail-dependent) cmd_depfail_dependent ;;
  *)
    echo "lifecycle.sh: unknown verb '$verb'" >&2
    exit 64
    ;;
esac
"""

TASKFILE_YML = """\
version: "3"

tasks:
  build:
    cmds:
      - ./lifecycle.sh build

  test:
    deps: [build]
    cmds:
      - ./lifecycle.sh test

  envcheck:
    cmds:
      - ./lifecycle.sh envcheck

  pwdcheck:
    cmds:
      - ./lifecycle.sh pwdcheck

  clean:
    cmds:
      - ./lifecycle.sh clean

  purge:
    deps: [clean]
    cmds:
      - ./lifecycle.sh purge

  failing:
    cmds:
      - ./lifecycle.sh failing

  depfail-dependent:
    deps: [failing]
    cmds:
      - ./lifecycle.sh depfail-dependent
"""

JUSTFILE = """\
build:
    ./lifecycle.sh build

test: build
    ./lifecycle.sh test

envcheck:
    ./lifecycle.sh envcheck

pwdcheck:
    ./lifecycle.sh pwdcheck

clean:
    ./lifecycle.sh clean

purge: clean
    ./lifecycle.sh purge

failing:
    ./lifecycle.sh failing

depfail-dependent: failing
    ./lifecycle.sh depfail-dependent
"""


def _require_binary(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        pytest.fail(
            f"required binary '{name}' not found on PATH; behavioral runner "
            "parity tests must not silently skip (see test-harness/flake.nix)"
        )
    return path


def make_fixture_project(directory: Path) -> Path:
    """Write a lifecycle.sh + Taskfile.yml + justfile trio following the
    Phase 6 canonical convention (identical one-line ``./lifecycle.sh <verb>``
    bodies, native deps for real ordering) into ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "Taskfile.yml").write_text(TASKFILE_YML)
    (directory / "justfile").write_text(JUSTFILE)
    script = directory / "lifecycle.sh"
    script.write_text(LIFECYCLE_SH)
    script.chmod(0o755)
    return directory


# This test process itself runs as a child of test-harness/lifecycle.sh's
# `test` verb, which unconditionally exports HARNESS_DIR/HARNESS_CACHE_DIR/
# HARNESS_OUTPUT_DIR/UV_CACHE_DIR before invoking pytest. Left alone, those
# ambient values would leak into the unrelated fixture projects spawned
# below and be (correctly, by design) treated as caller-provided overrides -
# masking the fixture's own default-derivation behavior. Tests that need a
# genuinely clean environment clear these explicitly via `clear_env_vars`.
HARNESS_ENV_VARS = (
    "HARNESS_DIR",
    "HARNESS_CACHE_DIR",
    "HARNESS_OUTPUT_DIR",
    "UV_CACHE_DIR",
    "CARGO_TARGET_DIR",
)


def run_runner(
    runner: str,
    verb: str,
    cwd: Path,
    extra_env: dict[str, str] | None = None,
    clear_env_vars: tuple[str, ...] = (),
) -> subprocess.CompletedProcess:
    binary = _require_binary(runner)
    env = dict(os.environ)
    for key in clear_env_vars:
        env.pop(key, None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [binary, verb],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_runners_are_on_path():
    """Hard-fail (not skip) if either binary is missing."""
    assert _require_binary("task")
    assert _require_binary("just")


def test_build_effects_match_between_runners(tmp_path):
    task_dir = make_fixture_project(tmp_path / "task-proj")
    just_dir = make_fixture_project(tmp_path / "just-proj")

    task_result = run_runner("task", "build", task_dir)
    just_result = run_runner("just", "build", just_dir)

    assert task_result.returncode == 0, task_result.stderr
    assert just_result.returncode == 0, just_result.stderr
    assert (task_dir / "build.marker").read_text() == (
        just_dir / "build.marker"
    ).read_text()


def test_env_vars_seen_by_script_match_between_runners(tmp_path):
    task_dir = make_fixture_project(tmp_path / "task-proj")
    just_dir = make_fixture_project(tmp_path / "just-proj")
    extra = {"LIFECYCLE_TEST_VAR": "hello-from-behavioral-test"}

    task_result = run_runner("task", "envcheck", task_dir, extra_env=extra)
    just_result = run_runner("just", "envcheck", just_dir, extra_env=extra)

    assert task_result.returncode == 0, task_result.stderr
    assert just_result.returncode == 0, just_result.stderr
    task_env = (task_dir / "env.out").read_text()
    just_env = (just_dir / "env.out").read_text()
    assert task_env == just_env == "LIFECYCLE_TEST_VAR=hello-from-behavioral-test\n"


def test_working_directory_matches_between_runners(tmp_path):
    task_dir = make_fixture_project(tmp_path / "task-proj")
    just_dir = make_fixture_project(tmp_path / "just-proj")

    task_result = run_runner("task", "pwdcheck", task_dir)
    just_result = run_runner("just", "pwdcheck", just_dir)

    assert task_result.returncode == 0, task_result.stderr
    assert just_result.returncode == 0, just_result.stderr
    task_pwd = (task_dir / "pwd.out").read_text().strip()
    just_pwd = (just_dir / "pwd.out").read_text().strip()
    # Both runners must resolve the recipe's working directory to the
    # project directory itself (not the caller's cwd, and not each other's
    # sibling fixture directory).
    assert Path(task_pwd).resolve() == task_dir.resolve()
    assert Path(just_pwd).resolve() == just_dir.resolve()


def test_dependency_ordering_matches_between_runners(tmp_path):
    task_dir = make_fixture_project(tmp_path / "task-proj")
    just_dir = make_fixture_project(tmp_path / "just-proj")

    task_result = run_runner("task", "test", task_dir)
    just_result = run_runner("just", "test", just_dir)

    assert task_result.returncode == 0, task_result.stderr
    assert just_result.returncode == 0, just_result.stderr
    # `test` depends on `build` natively in both files; the dependency must
    # run first in both runners.
    assert (task_dir / "order.log").read_text() == "build\ntest\n"
    assert (just_dir / "order.log").read_text() == "build\ntest\n"


def test_cleanup_paths_match_between_runners(tmp_path):
    task_dir = make_fixture_project(tmp_path / "task-proj")
    just_dir = make_fixture_project(tmp_path / "just-proj")

    for runner_name, project in (("task", task_dir), ("just", just_dir)):
        build_result = run_runner(runner_name, "build", project)
        assert build_result.returncode == 0, build_result.stderr
        test_result = run_runner(runner_name, "test", project)
        assert test_result.returncode == 0, test_result.stderr

    for project in (task_dir, just_dir):
        assert (project / "build.marker").exists()
        assert (project / "test.marker").exists()
        assert (project / "cache.marker").exists()

    task_clean = run_runner("task", "clean", task_dir)
    just_clean = run_runner("just", "clean", just_dir)
    assert task_clean.returncode == 0, task_clean.stderr
    assert just_clean.returncode == 0, just_clean.stderr

    for project in (task_dir, just_dir):
        # clean removes outputs...
        assert not (project / "build.marker").exists()
        assert not (project / "test.marker").exists()
        # ...but preserves the cache/dependency-state marker.
        assert (project / "cache.marker").exists()

    task_purge = run_runner("task", "purge", task_dir)
    just_purge = run_runner("just", "purge", just_dir)
    assert task_purge.returncode == 0, task_purge.stderr
    assert just_purge.returncode == 0, just_purge.stderr

    for project in (task_dir, just_dir):
        # purge (which depends on clean natively) also removes the cache.
        assert not (project / "cache.marker").exists()


def test_failing_verb_exits_non_zero_on_both_runners(tmp_path):
    task_dir = make_fixture_project(tmp_path / "task-proj")
    just_dir = make_fixture_project(tmp_path / "just-proj")

    task_result = run_runner("task", "failing", task_dir)
    just_result = run_runner("just", "failing", just_dir)

    assert task_result.returncode != 0
    assert just_result.returncode != 0


def test_failing_dependency_prevents_dependent_verb_on_both_runners(tmp_path):
    task_dir = make_fixture_project(tmp_path / "task-proj")
    just_dir = make_fixture_project(tmp_path / "just-proj")

    task_result = run_runner("task", "depfail-dependent", task_dir)
    just_result = run_runner("just", "depfail-dependent", just_dir)

    assert task_result.returncode != 0
    assert just_result.returncode != 0
    # The dependent verb's own body must never have run.
    assert not (task_dir / "depfail_dependent.marker").exists()
    assert not (just_dir / "depfail_dependent.marker").exists()


# --- HARNESS_* derivation rule (Phase 7 of docs/refactoring-plan.md) -------
#
# The fixture below follows the exact same derivation rule as every real
# lifecycle.sh in this repo (see e.g. python/lifecycle.sh): HARNESS_DIR
# defaults to `<project>/.harness`, overridable by env; HARNESS_CACHE_DIR and
# HARNESS_OUTPUT_DIR default to subdirectories of it. `build` writes a cache
# marker and an output marker into the derived directories; `clean` removes
# only the output marker; `purge` (which depends on `clean` natively in both
# runners, mirroring every real lifecycle.sh pair in this repo) removes the
# whole HARNESS_DIR, cache included.

LIFECYCLE_SH_HARNESS_DERIVED = """\
#!/usr/bin/env bash
set -eu

script_dir="$(cd "$(dirname "$0")" && pwd)"
export HARNESS_DIR="${HARNESS_DIR:-$script_dir/.harness}"
export HARNESS_CACHE_DIR="${HARNESS_CACHE_DIR:-$HARNESS_DIR/cache}"
export HARNESS_OUTPUT_DIR="${HARNESS_OUTPUT_DIR:-$HARNESS_DIR/outputs}"

cmd_build() {
  mkdir -p "$HARNESS_OUTPUT_DIR" "$HARNESS_CACHE_DIR"
  echo "built" > "$HARNESS_OUTPUT_DIR/build.marker"
  : > "$HARNESS_CACHE_DIR/cache.marker"
}

cmd_clean() {
  rm -f "$HARNESS_OUTPUT_DIR/build.marker"
}

cmd_purge() {
  rm -rf "$HARNESS_DIR"
}

verb="${1:-}"
case "$verb" in
  build) cmd_build ;;
  clean) cmd_clean ;;
  purge) cmd_purge ;;
  *)
    echo "lifecycle.sh: unknown verb '$verb'" >&2
    exit 64
    ;;
esac
"""

TASKFILE_YML_HARNESS_DERIVED = """\
version: "3"

tasks:
  build:
    cmds:
      - ./lifecycle.sh build

  clean:
    cmds:
      - ./lifecycle.sh clean

  purge:
    deps: [clean]
    cmds:
      - ./lifecycle.sh purge
"""

JUSTFILE_HARNESS_DERIVED = """\
build:
    ./lifecycle.sh build

clean:
    ./lifecycle.sh clean

purge: clean
    ./lifecycle.sh purge
"""


def make_harness_derived_fixture_project(directory: Path) -> Path:
    """Write a lifecycle.sh + Taskfile.yml + justfile trio whose state is
    derived from HARNESS_DIR exactly like every real lifecycle.sh in this
    repo, into ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "Taskfile.yml").write_text(TASKFILE_YML_HARNESS_DERIVED)
    (directory / "justfile").write_text(JUSTFILE_HARNESS_DERIVED)
    script = directory / "lifecycle.sh"
    script.write_text(LIFECYCLE_SH_HARNESS_DERIVED)
    script.chmod(0o755)
    return directory


def test_default_harness_dir_places_state_under_dot_harness_on_both_runners(tmp_path):
    task_dir = make_harness_derived_fixture_project(tmp_path / "task-proj")
    just_dir = make_harness_derived_fixture_project(tmp_path / "just-proj")

    task_result = run_runner("task", "build", task_dir, clear_env_vars=HARNESS_ENV_VARS)
    just_result = run_runner("just", "build", just_dir, clear_env_vars=HARNESS_ENV_VARS)

    assert task_result.returncode == 0, task_result.stderr
    assert just_result.returncode == 0, just_result.stderr
    for project in (task_dir, just_dir):
        assert (project / ".harness" / "outputs" / "build.marker").exists()
        assert (project / ".harness" / "cache" / "cache.marker").exists()


def test_overriding_harness_dir_relocates_state_on_both_runners(tmp_path):
    task_dir = make_harness_derived_fixture_project(tmp_path / "task-proj")
    just_dir = make_harness_derived_fixture_project(tmp_path / "just-proj")
    relocated = tmp_path / "elsewhere" / "harness-state"
    extra = {"HARNESS_DIR": str(relocated)}

    task_result = run_runner(
        "task", "build", task_dir, extra_env=extra, clear_env_vars=HARNESS_ENV_VARS
    )
    just_result = run_runner(
        "just", "build", just_dir, extra_env=extra, clear_env_vars=HARNESS_ENV_VARS
    )

    assert task_result.returncode == 0, task_result.stderr
    assert just_result.returncode == 0, just_result.stderr
    # State lands under the overridden HARNESS_DIR instead of the project's
    # own default `.harness/`.
    assert (relocated / "outputs" / "build.marker").exists()
    assert (relocated / "cache" / "cache.marker").exists()
    assert not (task_dir / ".harness").exists()
    assert not (just_dir / ".harness").exists()


def test_harness_clean_keeps_cache_purge_removes_all_on_both_runners(tmp_path):
    task_dir = make_harness_derived_fixture_project(tmp_path / "task-proj")
    just_dir = make_harness_derived_fixture_project(tmp_path / "just-proj")

    for runner_name, project in (("task", task_dir), ("just", just_dir)):
        result = run_runner(
            runner_name, "build", project, clear_env_vars=HARNESS_ENV_VARS
        )
        assert result.returncode == 0, result.stderr

    for project in (task_dir, just_dir):
        assert (project / ".harness" / "outputs" / "build.marker").exists()
        assert (project / ".harness" / "cache" / "cache.marker").exists()

    task_clean = run_runner("task", "clean", task_dir, clear_env_vars=HARNESS_ENV_VARS)
    just_clean = run_runner("just", "clean", just_dir, clear_env_vars=HARNESS_ENV_VARS)
    assert task_clean.returncode == 0, task_clean.stderr
    assert just_clean.returncode == 0, just_clean.stderr

    for project in (task_dir, just_dir):
        # clean removes the output...
        assert not (project / ".harness" / "outputs" / "build.marker").exists()
        # ...but preserves the cache.
        assert (project / ".harness" / "cache" / "cache.marker").exists()

    task_purge = run_runner("task", "purge", task_dir, clear_env_vars=HARNESS_ENV_VARS)
    just_purge = run_runner("just", "purge", just_dir, clear_env_vars=HARNESS_ENV_VARS)
    assert task_purge.returncode == 0, task_purge.stderr
    assert just_purge.returncode == 0, just_purge.stderr

    for project in (task_dir, just_dir):
        # purge (which depends on clean natively) removes the whole
        # HARNESS_DIR, cache included.
        assert not (project / ".harness").exists()
