#!/usr/bin/env bash
# Canonical lifecycle implementation for python/component/.
set -eu

# UV_CACHE_DIR default lives here (not duplicated as Taskfile vars:/env: and
# justfile `export ... :=` directives) so both runners inherit identical
# behavior from the one script.
export UV_CACHE_DIR="${UV_CACHE_DIR:-.cache/uv}"

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
  rm -rf __pycache__ .pytest_cache .coverage htmlcov output tests/__pycache__ "$bindings_dir" "$output_wasm"
}

cmd_purge() {
  rm -rf .venv
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
