#!/usr/bin/env bash
# Canonical lifecycle implementation for rust/.
#
# setup/build/test/coverage stay pure Task/Just native aggregators (they only
# compose library:*/component:* recipes, which already match byte-for-byte
# between Taskfile.yml and justfile) - only clean/purge have real,
# directory-owned command-body content, so only those verbs are implemented
# here. This is also where the pre-Phase-6 drift lived: the Taskfile side
# additionally removed this language's slice of the shared .harness
# cache/output directories on purge (and outputs on clean); the justfile side
# did not. Both runners now call this script, so behavior is identical.
#
# Sub-repo isolation: this script only reaches into its own subtree
# (library/, component/) and common/; never a sibling language directory.
set -eu

script_dir="$(cd "$(dirname "$0")" && pwd)"
lang="rust"

cmd_clean() {
  rm -rf "${HARNESS_OUTPUT_DIR:-${HARNESS_DIR:-$script_dir/.harness}/outputs}/$lang"
}

cmd_purge() {
  rm -rf \
    "$script_dir/.harness" \
    "${HARNESS_CACHE_DIR:-${HARNESS_DIR:-$script_dir/.harness}/cache}/$lang" \
    "${HARNESS_OUTPUT_DIR:-${HARNESS_DIR:-$script_dir/.harness}/outputs}/$lang"
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
