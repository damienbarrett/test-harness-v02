#!/usr/bin/env bash
# Canonical lifecycle implementation for rust/library/.
#
# State ownership (constitution.md §3): HARNESS_DIR and its
# derived cache/output/CARGO_TARGET_DIR variables are defined once at the
# language root (rust/lifecycle.sh) and inherited here when this script runs
# as that script's delegate. For direct invocation (`cd rust/library && task
# test`), this is the one shared fallback rule used by every child
# lifecycle.sh in this repo: derive HARNESS_DIR relative to the parent
# (language root) directory, then apply the identical derivation chain.
set -eu

script_dir="$(cd "$(dirname "$0")" && pwd)"

export HARNESS_DIR="${HARNESS_DIR:-$(cd "$script_dir/.." && pwd)/.harness}"
export HARNESS_CACHE_DIR="${HARNESS_CACHE_DIR:-$HARNESS_DIR/cache}"
export HARNESS_OUTPUT_DIR="${HARNESS_OUTPUT_DIR:-$HARNESS_DIR/outputs}"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$HARNESS_CACHE_DIR/cargo-target}"

cmd_setup() {
  cargo fetch --locked
}

cmd_test() {
  cargo test --locked --offline --tests
}

# Formatter + lint gate (constitution.md §8). Both tools
# come from the Nix rust toolchain (rust/flake.nix minimal profile + clippy/
# rustfmt extensions), not a Cargo dependency.
cmd_lint() {
  cargo fmt --check
  cargo clippy --all-targets --locked --offline -- -D warnings
}

# Explicitly upgrades locked dependencies and regenerates the lockfile
# (constitution.md §4). Network access is expected here, unlike the
# --locked --offline verbs above.
cmd_update() {
  cargo update
}

cmd_coverage() {
  cargo llvm-cov clean --workspace
  cargo llvm-cov --locked --offline --tests --fail-under-lines 100 --fail-under-functions 100 --fail-under-regions 100
}

# rust/library produces no standalone build artifact of its own (unlike
# rust/component, it has no `.wasm` to copy out) - its only state is the
# $CARGO_TARGET_DIR build cache, which constitution.md §4 classifies as
# cache, not output. There is nothing here for `clean` to remove; the cache
# itself is only removed by `purge`.
cmd_clean() {
  :
}

# CARGO_TARGET_DIR defaults to a directory shared with rust/component (see
# rust/lifecycle.sh). `cargo clean` removes the *entire* target directory it
# resolves to, so running this purge in isolation also clears
# rust/component's cached build artifacts. That is an accepted tradeoff of
# sharing one build cache between the two crates: root/rust orchestration
# always purges both together, and `purge` is meant to be fully destructive
# anyway.
cmd_purge() {
  cargo clean
  rm -rf .task
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
