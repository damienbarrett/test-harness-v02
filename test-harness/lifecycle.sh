#!/usr/bin/env bash
# Canonical lifecycle implementation for test-harness/.
#
# State ownership (Phase 7 of docs/refactoring-plan.md): this is the ONE
# place test-harness/'s HARNESS_DIR and its derived cache/output/
# UV_CACHE_DIR/RUFF_CACHE_DIR variables are defined and exported.
# test-harness/ has no library/component children, so there is no
# parent/child fallback split here - this script is both the language root
# and the leaf.
set -eu

script_dir="$(cd "$(dirname "$0")" && pwd)"

export HARNESS_DIR="${HARNESS_DIR:-$script_dir/.harness}"
export HARNESS_CACHE_DIR="${HARNESS_CACHE_DIR:-$HARNESS_DIR/cache}"
export HARNESS_OUTPUT_DIR="${HARNESS_OUTPUT_DIR:-$HARNESS_DIR/outputs}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$HARNESS_CACHE_DIR/uv}"
export RUFF_CACHE_DIR="${RUFF_CACHE_DIR:-$HARNESS_CACHE_DIR/ruff}"

cmd_setup() {
  uv sync --locked
}

cmd_test() {
  uv run --locked pytest -q
}

# Invoked directly by root lifecycle.sh's wasm:test verb (not via `task`) so
# that UV_CACHE_DIR is derived exactly once, here, instead of being
# duplicated at the root.
cmd_wasm_test() {
  ./run-wasm-tests.py
}

cmd_check_runners() {
  ./check-runner-parity.py
}

cmd_check_contracts() {
  ./check-contracts.py
}

# Formatter + lint gate (Phase 9 of docs/refactoring-plan.md). ruff comes
# from the Nix dev shell (test-harness/flake.nix), not from this project's
# locked dependencies - see that flake for why (prebuilt manylinux wheels
# cannot execute on this repo's FHS-less NixOS guest). [tool.ruff] in
# pyproject.toml excludes the three POSIX-sh entry shims kept at .py paths.
# ruff's own cache is routed to $RUFF_CACHE_DIR (state ownership, Phase 7)
# instead of its default bare `.ruff_cache/` here, so `purge` removes it via
# $HARNESS_DIR without any directory-specific handling.
cmd_lint() {
  ruff format --check .
  ruff check .
}

# ShellCheck gate over every tracked shell script in the repository (Phase 9
# of docs/refactoring-plan.md): all tracked *.sh files (lifecycle.sh scripts,
# container/ scripts) plus bin/dx-worktree, a bash script without the .sh
# suffix. This is a repo-wide check that happens to live in the harness
# because shellcheck ships in this directory's dev shell; the root `lint`
# aggregator invokes it once per run via the root `check:shell` /
# `check-shell` wrapper.
cmd_check_shell() {
  (
    cd "$script_dir/.."
    git ls-files -z -- '*.sh' bin/dx-worktree | xargs -0 shellcheck
    echo "OK: shellcheck passed for all tracked shell scripts."
  )
}

# Explicitly upgrades locked dependencies and regenerates the lockfile
# (constitution.md §4), then syncs the environment (the dev dependency
# group is included by default, matching `setup`). Network access is
# expected here.
cmd_update() {
  uv lock --upgrade
  uv sync
}

cmd_coverage() {
  uv run --locked pytest --cov=harness --cov-report=term-missing --cov-fail-under=100
}

cmd_clean() {
  rm -rf __pycache__ .pytest_cache .coverage htmlcov output src/harness/__pycache__ tests/__pycache__
}

# purge's dependency on `clean` is expressed natively by both runners
# (Taskfile `deps: [clean]` / justfile `purge: clean`), so this only performs
# the leaf-level work that used to be purge's own trailing command: removing
# installed dependencies (.venv), the whole HARNESS_DIR (cache + outputs,
# including the uv and ruff caches), and Task's own checksum cache. The
# `.ruff_cache` removal is one-time-migration cleanup: before RUFF_CACHE_DIR
# was routed under $HARNESS_DIR, `ruff` defaulted its cache to a bare
# `.ruff_cache/` directly here, which no lifecycle verb ever removed; keep
# this so already-checked-out trees come clean too.
cmd_purge() {
  rm -rf .venv "$HARNESS_DIR" .task .ruff_cache
}

verb="${1:-}"
case "$verb" in
  setup) cmd_setup ;;
  test) cmd_test ;;
  lint) cmd_lint ;;
  wasm-test) cmd_wasm_test ;;
  check-runners) cmd_check_runners ;;
  check-contracts) cmd_check_contracts ;;
  check-shell) cmd_check_shell ;;
  coverage) cmd_coverage ;;
  clean) cmd_clean ;;
  purge) cmd_purge ;;
  update) cmd_update ;;
  *)
    echo "lifecycle.sh: unknown verb '$verb'" >&2
    exit 64
    ;;
esac
