#!/usr/bin/env bash
# Canonical lifecycle implementation for rust/.
#
# setup/build/test/coverage stay pure Task/Just native aggregators (they only
# compose library:*/component:* recipes, which already match byte-for-byte
# between Taskfile.yml and justfile) - only clean/purge have real,
# directory-owned command-body content, so only those verbs are implemented
# here.
#
# State ownership (Phase 7 of docs/refactoring-plan.md): this is the ONE
# place rust/'s HARNESS_DIR and its derived cache/output/CARGO_TARGET_DIR
# variables are defined and exported. library/ and component/ inherit these
# exported values when invoked through the `delegate` function below (they
# run as child processes of this script); for direct invocation
# (e.g. `cd rust/component && task test`) each child's own lifecycle.sh
# derives the identical values itself via the same fallback rule, relative
# to its own parent directory. CARGO_TARGET_DIR is deliberately shared
# between rust/library and rust/component (see their lifecycle.sh for the
# build-cache-sharing tradeoff this implies for `cargo clean`/purge).
#
# Sub-repo isolation: this script only reaches into its own subtree
# (library/, component/) and common/; never a sibling language directory.
set -eu

script_dir="$(cd "$(dirname "$0")" && pwd)"
lang="rust"

export HARNESS_DIR="${HARNESS_DIR:-$script_dir/.harness}"
export HARNESS_CACHE_DIR="${HARNESS_CACHE_DIR:-$HARNESS_DIR/cache}"
export HARNESS_OUTPUT_DIR="${HARNESS_OUTPUT_DIR:-$HARNESS_DIR/outputs}"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$HARNESS_CACHE_DIR/cargo-target}"

cmd_clean() {
  rm -rf "$HARNESS_OUTPUT_DIR/$lang"
}

# Removes the whole of $HARNESS_DIR (covering the default case, where it is
# unique to this language, and which already contains CARGO_TARGET_DIR under
# its cache/ slice) plus this language's namespaced slice of
# HARNESS_CACHE_DIR/HARNESS_OUTPUT_DIR (covering the case where HARNESS_DIR
# has been overridden to a directory shared across languages, e.g. by the
# Apple-container scripts under container/), and Task's own checksum cache.
cmd_purge() {
  rm -rf "$HARNESS_DIR" "$HARNESS_CACHE_DIR/$lang" "$HARNESS_OUTPUT_DIR/$lang" "$script_dir/.task"
}

# library:*/component:* delegate verbs: run the child directory's own `task`
# entry point (its own subtree - allowed by the sub-repo isolation rule), not
# lifecycle.sh directly, so the child's native dependency graph still runs
# (e.g. component's test depends on component's build). No nix dev shell
# re-entry is needed here since this script already runs inside rust/'s
# shell.
delegate() {
  (cd "$1" && task "$2")
}

verb="${1:-}"
case "$verb" in
  clean) cmd_clean ;;
  purge) cmd_purge ;;
  library-setup) delegate library setup ;;
  library-test) delegate library test ;;
  library-coverage) delegate library coverage ;;
  library-clean) delegate library clean ;;
  library-purge) delegate library purge ;;
  component-setup) delegate component setup ;;
  component-build) delegate component build ;;
  component-test) delegate component test ;;
  component-coverage) delegate component coverage ;;
  component-clean) delegate component clean ;;
  component-purge) delegate component purge ;;
  *)
    echo "lifecycle.sh: unknown verb '$verb'" >&2
    exit 64
    ;;
esac
