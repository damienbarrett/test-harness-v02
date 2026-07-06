#!/usr/bin/env bash
# Canonical lifecycle implementation for python/library/.
#
# State ownership (Phase 7 of docs/refactoring-plan.md): HARNESS_DIR and its
# derived cache/output/UV_CACHE_DIR variables are defined once at the
# language root (python/lifecycle.sh) and inherited here when this script
# runs as that script's delegate. For direct invocation
# (`cd python/library && task test`), this is the one shared fallback rule
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

cmd_setup() {
  uv sync --locked --extra test
}

cmd_test() {
  uv run --locked --extra test pytest tests/ -v
}

cmd_coverage() {
  uv run --locked --extra test pytest tests/ --cov --cov-report=term-missing
}

cmd_clean() {
  rm -rf __pycache__ .pytest_cache .coverage htmlcov output tests/__pycache__ src/tasks/__pycache__
  find . -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
}

# purge's dependency on `clean` is expressed natively by both runners
# (Taskfile `deps: [clean]` / justfile `purge: clean`), so this only performs
# the leaf-level work that used to be purge's own trailing command.
cmd_purge() {
  rm -rf .venv .task
}

verb="${1:-}"
case "$verb" in
  setup) cmd_setup ;;
  test) cmd_test ;;
  coverage) cmd_coverage ;;
  clean) cmd_clean ;;
  purge) cmd_purge ;;
  *)
    echo "lifecycle.sh: unknown verb '$verb'" >&2
    exit 64
    ;;
esac
