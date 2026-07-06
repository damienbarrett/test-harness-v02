#!/usr/bin/env bash
# Canonical lifecycle implementation for python/library/.
set -eu

# UV_CACHE_DIR default lives here (not duplicated as Taskfile vars:/env: and
# justfile `export ... :=` directives) so both runners inherit identical
# behavior from the one script.
export UV_CACHE_DIR="${UV_CACHE_DIR:-.cache/uv}"

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
  rm -rf .venv
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
