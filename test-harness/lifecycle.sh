#!/usr/bin/env bash
# Canonical lifecycle implementation for test-harness/.
set -eu

# UV_CACHE_DIR default lives here (not duplicated as Taskfile vars:/env: and
# justfile `export ... :=` directives) so both runners inherit identical
# behavior from the one script.
export UV_CACHE_DIR="${UV_CACHE_DIR:-.cache/uv}"

cmd_setup() {
  uv sync --locked
}

cmd_test() {
  uv run --locked pytest -q
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
# the leaf-level work that used to be purge's own trailing command.
cmd_purge() {
  rm -rf .venv
}

verb="${1:-}"
case "$verb" in
  setup) cmd_setup ;;
  test) cmd_test ;;
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
