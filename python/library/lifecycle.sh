#!/usr/bin/env bash
# Canonical lifecycle implementation for python/library/.
#
# State ownership (constitution.md §3): HARNESS_DIR and its
# derived cache/output/UV_CACHE_DIR/RUFF_CACHE_DIR variables are defined once
# at the language root (python/lifecycle.sh) and inherited here when this
# script runs as that script's delegate. For direct invocation
# (`cd python/library && task test`), this is the one shared fallback rule
# used by every child lifecycle.sh in this repo: derive HARNESS_DIR relative
# to the parent (language root) directory, then apply the identical
# derivation chain. This script never defaults UV_CACHE_DIR or
# RUFF_CACHE_DIR to a locally-scoped cache directory independently of that
# rule.
set -eu

script_dir="$(cd "$(dirname "$0")" && pwd)"

export HARNESS_DIR="${HARNESS_DIR:-$(cd "$script_dir/.." && pwd)/.harness}"
export HARNESS_CACHE_DIR="${HARNESS_CACHE_DIR:-$HARNESS_DIR/cache}"
export HARNESS_OUTPUT_DIR="${HARNESS_OUTPUT_DIR:-$HARNESS_DIR/outputs}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$HARNESS_CACHE_DIR/uv}"
export RUFF_CACHE_DIR="${RUFF_CACHE_DIR:-$HARNESS_CACHE_DIR/ruff}"

cmd_setup() {
  uv sync --locked --extra test
}

cmd_test() {
  uv run --locked --extra test pytest tests/ -v
}

# Formatter + lint gate (constitution.md §8). ruff comes
# from the Nix dev shell (python/flake.nix), not from this project's locked
# dependencies - see that flake for why (prebuilt manylinux wheels cannot
# execute on this repo's FHS-less NixOS guest). ruff respects .gitignore, so
# .venv/ and other generated state are excluded automatically. ruff's own
# cache is routed to $RUFF_CACHE_DIR (state ownership, Phase 7) instead of
# its default bare `.ruff_cache/` here, so `purge` removes it via
# $HARNESS_DIR without any directory-specific handling.
cmd_lint() {
  ruff format --check .
  ruff check .
}

# Explicitly upgrades locked dependencies and regenerates the lockfile
# (constitution.md §4), then syncs the environment with the same extras
# `setup` installs. Network access is expected here.
cmd_update() {
  uv lock --upgrade
  uv sync --extra test
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
# the leaf-level work that used to be purge's own trailing command. The
# `.ruff_cache` removal is one-time-migration cleanup: before RUFF_CACHE_DIR
# was routed under $HARNESS_DIR, `ruff` defaulted its cache to a bare
# `.ruff_cache/` directly here, which no lifecycle verb ever removed; keep
# this so already-checked-out trees come clean too.
cmd_purge() {
  rm -rf .venv .task .ruff_cache
}

verb="${1:-}"
case "$verb" in
  setup) cmd_setup ;;
  test) cmd_test ;;
  lint) cmd_lint ;;
  coverage) cmd_coverage ;;
  clean) cmd_clean ;;
  purge) cmd_purge ;;
  update) cmd_update ;;
  *)
    echo "lifecycle.sh: unknown verb '$verb'" >&2
    exit 64
    ;;
esac
