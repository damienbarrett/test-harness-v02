#!/usr/bin/env bash
# Canonical lifecycle implementation for rust/component/.
set -eu

cmd_setup() {
  cargo fetch --locked
}

cmd_build() {
  cargo component build --release --locked --offline
  cp "${CARGO_TARGET_DIR:-target}/wasm32-wasip1/release/task_component.wasm" task-component.wasm
}

# build is a native dependency of test in both runners, so this only performs
# the leaf-level test invocation.
cmd_test() {
  cargo test --locked --offline --tests
}

# coverage rebuilds its own instrumented artifact rather than depending on
# the plain `build` verb, matching current (pre-Phase-6) behavior.
cmd_coverage() {
  cargo clean
  cargo component build --release --locked --offline
  cp "${CARGO_TARGET_DIR:-target}/wasm32-wasip1/release/task_component.wasm" task-component.wasm
  cargo llvm-cov clean --workspace
  cargo llvm-cov --locked --offline --tests --fail-under-lines 100 --fail-under-functions 100 --fail-under-regions 100
}

cmd_clean() {
  cargo clean
  rm -f task-component.wasm
}

verb="${1:-}"
case "$verb" in
  setup) cmd_setup ;;
  build) cmd_build ;;
  test) cmd_test ;;
  coverage) cmd_coverage ;;
  clean) cmd_clean ;;
  *)
    echo "lifecycle.sh: unknown verb '$verb'" >&2
    exit 64
    ;;
esac
