#!/usr/bin/env bash
# Canonical lifecycle implementation for javascript/component/.
#
# State ownership (Phase 7 of docs/refactoring-plan.md): HARNESS_DIR and its
# derived cache/output variables are defined once at the language root
# (javascript/lifecycle.sh) and inherited here when this script runs as that
# script's delegate. For direct invocation (`cd javascript/component && task
# test`), this is the one shared fallback rule used by every child
# lifecycle.sh in this repo: derive HARNESS_DIR relative to the parent
# (language root) directory, then apply the identical derivation chain.
set -eu

script_dir="$(cd "$(dirname "$0")" && pwd)"

export HARNESS_DIR="${HARNESS_DIR:-$(cd "$script_dir/.." && pwd)/.harness}"
export HARNESS_CACHE_DIR="${HARNESS_CACHE_DIR:-$HARNESS_DIR/cache}"
export HARNESS_OUTPUT_DIR="${HARNESS_OUTPUT_DIR:-$HARNESS_DIR/outputs}"

wit_path="../../common/wit/tasks.wit"
world_name="task-component"
output_wasm="task-component.wasm"

cmd_setup() {
  npm ci
}

cmd_build() {
  # -d all disables every optional WASI capability jco/componentize-js knows
  # how to gate (clocks, random, stdio, http, fetch-event). taskCollections
  # is a pure function (see src/app.js) that touches none of them, and
  # empirically the resulting component imports nothing at all -- verified
  # via wasmtime.component.Component.type().imports(engine) against the
  # built artifact (docs/refactoring-plan.md Phase 8). Do not re-add
  # `--enable clocks/random/stdio` (the pre-Phase-8 flags): each one was
  # previously undoing part of `-d all` for no reason this component needs.
  if [ -n "${JCO_FHS:-}" ]; then
    "$JCO_FHS" -c "npx jco componentize src/app.js --wit $wit_path -n $world_name -d all -o $output_wasm"
  else
    npx jco componentize src/app.js --wit "$wit_path" -n "$world_name" -d all -o "$output_wasm"
  fi
  if [ -n "${JCO_FHS:-}" ]; then
    "$JCO_FHS" -c "npx jco transpile $output_wasm -o transpiled/"
  else
    npx jco transpile "$output_wasm" -o transpiled/
  fi
}

# build is a native dependency of test/coverage in both runners, so these
# only perform the leaf-level test invocation.
cmd_test() {
  node --test tests/*.test.js
}

cmd_coverage() {
  node --test --experimental-test-coverage \
    --test-coverage-include='src/**' \
    --test-coverage-lines=100 \
    --test-coverage-branches=100 \
    --test-coverage-functions=100 \
    tests/*.test.js
}

cmd_clean() {
  rm -rf .coverage .nyc_output coverage output test-results transpiled task-component.wasm
}

cmd_purge() {
  rm -rf node_modules .task
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
