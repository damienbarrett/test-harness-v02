#!/usr/bin/env bash
# Canonical lifecycle implementation for rust/library/.
set -eu

cmd_setup() {
  cargo fetch --locked
}

cmd_test() {
  cargo test --locked --offline --tests
}

cmd_coverage() {
  cargo llvm-cov clean --workspace
  cargo llvm-cov --locked --offline --tests --fail-under-lines 100 --fail-under-functions 100 --fail-under-regions 100
}

cmd_clean() {
  cargo clean
}

verb="${1:-}"
case "$verb" in
  setup) cmd_setup ;;
  test) cmd_test ;;
  coverage) cmd_coverage ;;
  clean) cmd_clean ;;
  *)
    echo "lifecycle.sh: unknown verb '$verb'" >&2
    exit 64
    ;;
esac
