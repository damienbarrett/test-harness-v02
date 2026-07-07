#!/usr/bin/env bash
# Canonical lifecycle implementation for javascript/.
#
# setup/build/test/coverage stay pure Task/Just native aggregators (they only
# compose library:*/component:* recipes, which already match byte-for-byte
# between Taskfile.yml and justfile) - only clean/purge have real,
# directory-owned command-body content, so only those verbs are implemented
# here.
#
# State ownership (Phase 7 of docs/refactoring-plan.md): this is the ONE
# place javascript/'s HARNESS_DIR and its derived cache/output variables are
# defined and exported (JavaScript has no package-manager cache directory
# equivalent to UV_CACHE_DIR/CARGO_TARGET_DIR that needs relocating - `npm
# ci` uses node_modules/ directly, which purge already removes below).
# library/ and component/ inherit these exported values when invoked through
# the `delegate` function below; for direct invocation
# (e.g. `cd javascript/component && task test`) each child's own
# lifecycle.sh derives the identical values itself via the same fallback
# rule, relative to its own parent directory.
#
# Sub-repo isolation: this script only reaches into its own subtree
# (library/, component/) and common/; never a sibling language directory.
set -eu

script_dir="$(cd "$(dirname "$0")" && pwd)"
lang="javascript"

export HARNESS_DIR="${HARNESS_DIR:-$script_dir/.harness}"
export HARNESS_CACHE_DIR="${HARNESS_CACHE_DIR:-$HARNESS_DIR/cache}"
export HARNESS_OUTPUT_DIR="${HARNESS_OUTPUT_DIR:-$HARNESS_DIR/outputs}"

cmd_clean() {
  # ${VAR:?} guards (SC2115): fail loudly instead of expanding to "/" if a
  # derived HARNESS_* variable were ever empty.
  rm -rf "${HARNESS_OUTPUT_DIR:?}/$lang"
}

# Removes the whole of $HARNESS_DIR (covering the default case, where it is
# unique to this language) plus this language's namespaced slice of
# HARNESS_CACHE_DIR/HARNESS_OUTPUT_DIR (covering the case where HARNESS_DIR
# has been overridden to a directory shared across languages, e.g. by the
# Apple-container scripts under container/), and Task's own checksum cache.
cmd_purge() {
  rm -rf "$HARNESS_DIR" "${HARNESS_CACHE_DIR:?}/$lang" "${HARNESS_OUTPUT_DIR:?}/$lang" "$script_dir/.task"
}

# library:*/component:* delegate verbs: run the child directory's own `task`
# entry point (its own subtree - allowed by the sub-repo isolation rule), not
# lifecycle.sh directly, so the child's native dependency graph still runs
# (e.g. component's test/coverage depend on component's build). No nix dev
# shell re-entry is needed here since this script already runs inside
# javascript/'s shell.
delegate() {
  (cd "$1" && task "$2")
}

verb="${1:-}"
case "$verb" in
  clean) cmd_clean ;;
  purge) cmd_purge ;;
  library-setup) delegate library setup ;;
  library-test) delegate library test ;;
  library-lint) delegate library lint ;;
  library-coverage) delegate library coverage ;;
  library-clean) delegate library clean ;;
  library-purge) delegate library purge ;;
  library-update) delegate library update ;;
  component-setup) delegate component setup ;;
  component-build) delegate component build ;;
  component-test) delegate component test ;;
  component-lint) delegate component lint ;;
  component-coverage) delegate component coverage ;;
  component-clean) delegate component clean ;;
  component-purge) delegate component purge ;;
  component-update) delegate component update ;;
  *)
    echo "lifecycle.sh: unknown verb '$verb'" >&2
    exit 64
    ;;
esac
