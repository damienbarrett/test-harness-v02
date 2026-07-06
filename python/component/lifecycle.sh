#!/usr/bin/env bash
# Canonical lifecycle implementation for python/component/.
#
# State ownership (Phase 7 of docs/refactoring-plan.md): HARNESS_DIR and its
# derived cache/output/UV_CACHE_DIR variables are defined once at the
# language root (python/lifecycle.sh) and inherited here when this script
# runs as that script's delegate. For direct invocation
# (`cd python/component && task test`), this is the one shared fallback rule
# used by every child lifecycle.sh in this repo: derive HARNESS_DIR relative
# to the parent (language root) directory, then apply the identical
# derivation chain. This script never defaults UV_CACHE_DIR to a
# locally-scoped cache directory independently of that rule.
set -eu

script_dir="$(cd "$(dirname "$0")" && pwd)"

export HARNESS_DIR="${HARNESS_DIR:-$(cd "$script_dir/.." && pwd)/.harness}"
export HARNESS_CACHE_DIR="${HARNESS_CACHE_DIR:-$HARNESS_DIR/cache}"
export HARNESS_OUTPUT_DIR="${HARNESS_OUTPUT_DIR:-$HARNESS_DIR/outputs}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$HARNESS_CACHE_DIR/uv}"

wit_dir="../../common/wit"
output_wasm="task-component.wasm"
bindings_dir="bindings"

cmd_setup() {
  uv sync --locked --extra build --extra test
}

# Emits the wit-bindgen-generated `wit_world` package to `bindings/` (a
# stable, gitignored location) so host tests can import the real bindings
# instead of mocking them away. `componentize` then bundles src + bindings.
cmd_build() {
  rm -rf "$bindings_dir"
  uv run --locked --extra build componentize-py \
    -d "$wit_dir" -w task-component bindings "$bindings_dir"
  uv run --locked --extra build componentize-py \
    -d "$wit_dir" -w task-component componentize \
    -p src -p "$bindings_dir" -s -o "$output_wasm" app
}

# build is a native dependency of test/coverage in both runners, so this
# only performs the leaf-level test invocation.
cmd_test() {
  uv run --locked --extra test pytest tests/ -v
}

cmd_coverage() {
  uv run --locked --extra test pytest tests/ --cov --cov-report=term-missing
}

cmd_clean() {
  rm -rf __pycache__ .pytest_cache .coverage htmlcov output tests/__pycache__ src/__pycache__ "$bindings_dir" "$output_wasm"
}

cmd_purge() {
  rm -rf .venv .task
}

verb="${1:-}"
case "$verb" in
  setup) cmd_setup ;;
  build) cmd_build ;;
  test) cmd_test ;;
  coverage) cmd_coverage ;;
  clean) cmd_clean ;;
  purge) cmd_purge ;;
  *)
    echo "lifecycle.sh: unknown verb '$verb'" >&2
    exit 64
    ;;
esac
