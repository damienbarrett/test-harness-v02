#!/usr/bin/env bash
# Canonical lifecycle implementation for javascript/component/.
set -eu

wit_path="../../common/wit/tasks.wit"
world_name="task-component"
output_wasm="task-component.wasm"

cmd_setup() {
  npm ci
}

cmd_build() {
  if [ -n "${JCO_FHS:-}" ]; then
    "$JCO_FHS" -c "npx jco componentize src/app.js --wit $wit_path -n $world_name -d all --enable clocks --enable random --enable stdio -o $output_wasm"
  else
    npx jco componentize src/app.js --wit "$wit_path" -n "$world_name" -d all --enable clocks --enable random --enable stdio -o "$output_wasm"
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
  rm -rf node_modules
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
