#!/usr/bin/env bash
# Canonical lifecycle implementation for test-harness/.
#
# State ownership (Phase 7 of docs/refactoring-plan.md): this is the ONE
# place test-harness/'s HARNESS_DIR and its derived cache/output/
# UV_CACHE_DIR variables are defined and exported. test-harness/ has no
# library/component children, so there is no parent/child fallback split
# here - this script is both the language root and the leaf.
set -eu

script_dir="$(cd "$(dirname "$0")" && pwd)"

export HARNESS_DIR="${HARNESS_DIR:-$script_dir/.harness}"
export HARNESS_CACHE_DIR="${HARNESS_CACHE_DIR:-$HARNESS_DIR/cache}"
export HARNESS_OUTPUT_DIR="${HARNESS_OUTPUT_DIR:-$HARNESS_DIR/outputs}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$HARNESS_CACHE_DIR/uv}"

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
# including the uv cache), and Task's own checksum cache.
cmd_purge() {
  rm -rf .venv "$HARNESS_DIR" .task
}

verb="${1:-}"
case "$verb" in
  setup) cmd_setup ;;
  test) cmd_test ;;
  wasm-test) cmd_wasm_test ;;
  check-runners) cmd_check_runners ;;
  check-contracts) cmd_check_contracts ;;
  coverage) cmd_coverage ;;
  clean) cmd_clean ;;
  purge) cmd_purge ;;
  *)
    echo "lifecycle.sh: unknown verb '$verb'" >&2
    exit 64
    ;;
esac
