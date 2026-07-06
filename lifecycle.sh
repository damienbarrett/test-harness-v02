#!/usr/bin/env bash
# Canonical lifecycle implementation for the repository root.
#
# Both Taskfile.yml and justfile at repo root invoke this script for every
# recipe that has real command-body content (pure aggregator recipes that
# only compose other recipes keep using each runner's native dependency
# mechanism, since that already gives identical, checker-verified behavior
# and lets Task's sources:/generates: incremental-skip hints keep working).
#
# Usage: ./lifecycle.sh <verb> [-- passthrough args]
#
# Sub-repo isolation: this root script is the one script allowed to cd into
# language/test-harness subdirectories (mirroring the pre-Phase-6 root
# recipes); it never reaches into a subdirectory's own library/ or
# component/ layers - those are owned by that subdirectory's own
# lifecycle.sh.
set -eu

codex_dir="container/aarch64-darwin-apple-container-codex-universal"
nixos_dir="container/aarch64-darwin-apple-container-nixos-25.11"

# Runs a language/test-harness directory's own canonical verb inside its Nix
# dev shell. Always delegates to `task` (never `just`) so that both the root
# Taskfile.yml recipe and the root justfile recipe for a given wrapper (e.g.
# python-setup) resolve to the exact same body - which sub-repo runner is
# used internally is an implementation detail, not part of the public
# contract.
lang_step() {
  (cd "$1" && nix develop --command task "$2")
}

verb="${1:-}"
if [ "$#" -gt 0 ]; then
  shift
fi
args="$*"

case "$verb" in
  provision | image:bootstrap)
    ./"$codex_dir"/bootstrap-container-tools.sh
    ;;

  clean | purge)
    rm -rf .output output
    ;;

  wasm:test)
    (cd test-harness && nix develop --command bash -c 'UV_CACHE_DIR="${UV_CACHE_DIR:-.cache/uv}" ./run-wasm-tests.py')
    ;;

  check:runners)
    (cd test-harness && nix develop --command bash -c 'UV_CACHE_DIR="${UV_CACHE_DIR:-.cache/uv}" ./check-runner-parity.py')
    ;;

  contracts:check)
    (cd test-harness && nix develop --command bash -c 'UV_CACHE_DIR="${UV_CACHE_DIR:-.cache/uv}" ./check-contracts.py')
    ;;

  python-setup) lang_step python setup ;;
  javascript-setup) lang_step javascript setup ;;
  rust-setup) lang_step rust setup ;;
  test-harness-setup) lang_step test-harness setup ;;

  python-build) lang_step python build ;;
  javascript-build) lang_step javascript build ;;
  rust-build) lang_step rust build ;;

  python-test) lang_step python test ;;
  javascript-test) lang_step javascript test ;;
  rust-test) lang_step rust test ;;
  test-harness-test) lang_step test-harness test ;;

  python-coverage) lang_step python coverage ;;
  javascript-coverage) lang_step javascript coverage ;;
  rust-coverage) lang_step rust coverage ;;
  test-harness-coverage) lang_step test-harness coverage ;;

  python-clean) lang_step python clean ;;
  javascript-clean) lang_step javascript clean ;;
  rust-clean) lang_step rust clean ;;
  test-harness-clean) lang_step test-harness clean ;;

  python-purge) lang_step python purge ;;
  javascript-purge) lang_step javascript purge ;;
  rust-purge) lang_step rust purge ;;
  test-harness-purge) lang_step test-harness purge ;;

  host:container:build)
    ./"$codex_dir"/container-build.sh
    ;;
  host:container:shell)
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" \
      CODEX_HARNESS_WORKSPACE_MODE=image \
      ./"$codex_dir"/container-shell.sh
    ;;
  host:container:task)
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" \
      CODEX_HARNESS_WORKSPACE_MODE=image \
      ./"$codex_dir"/container-run.sh "task $args"
    ;;
  host:container:just)
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" \
      CODEX_HARNESS_WORKSPACE_MODE=image \
      ./"$codex_dir"/container-run.sh "just $args"
    ;;
  host:container:test)
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" \
      CODEX_HARNESS_WORKSPACE_MODE=image \
      ./"$codex_dir"/container-run.sh "./$codex_dir/container-suite.sh both test"
    ;;
  host:container:coverage)
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" \
      CODEX_HARNESS_WORKSPACE_MODE=image \
      ./"$codex_dir"/container-run.sh "./$codex_dir/container-suite.sh both coverage"
    ;;
  host:container:purge)
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" \
      CODEX_HARNESS_WORKSPACE_MODE=image \
      ./"$codex_dir"/container-run.sh "./$codex_dir/container-suite.sh both purge"
    ;;

  container:healthcheck)
    ./"$codex_dir"/container-healthcheck.sh
    ;;
  container:prune-all)
    ./"$codex_dir"/container-prune-all.sh
    ;;
  container:pull)
    ./"$codex_dir"/container-pull.sh
    ;;
  container:build)
    ./"$codex_dir"/container-build.sh
    ;;
  container:shell)
    ./"$codex_dir"/container-shell.sh
    ;;
  container:task)
    ./"$codex_dir"/container-run.sh "task $args"
    ;;
  container:just)
    ./"$codex_dir"/container-run.sh "just $args"
    ;;
  container:task:setup)
    ./"$codex_dir"/container-run.sh "task setup"
    ;;
  container:task:test)
    ./"$codex_dir"/container-run.sh "./$codex_dir/container-suite.sh task test"
    ;;
  container:task:coverage)
    ./"$codex_dir"/container-run.sh "./$codex_dir/container-suite.sh task coverage"
    ;;
  container:task:clean)
    ./"$codex_dir"/container-run.sh "task clean"
    ;;
  container:task:purge)
    ./"$codex_dir"/container-run.sh "task purge"
    ;;
  container:just:setup)
    ./"$codex_dir"/container-run.sh "just setup"
    ;;
  container:just:test)
    ./"$codex_dir"/container-run.sh "./$codex_dir/container-suite.sh just test"
    ;;
  container:just:coverage)
    ./"$codex_dir"/container-run.sh "./$codex_dir/container-suite.sh just coverage"
    ;;
  container:just:clean)
    ./"$codex_dir"/container-run.sh "just clean"
    ;;
  container:just:purge)
    ./"$codex_dir"/container-run.sh "just purge"
    ;;
  container:setup)
    ./"$codex_dir"/container-run.sh "./$codex_dir/container-suite.sh both setup"
    ;;
  container:test)
    ./"$codex_dir"/container-run.sh "./$codex_dir/container-suite.sh both test"
    ;;
  container:coverage)
    ./"$codex_dir"/container-run.sh "./$codex_dir/container-suite.sh both coverage"
    ;;
  container:clean)
    ./"$codex_dir"/container-run.sh "./$codex_dir/container-suite.sh both clean"
    ;;
  container:purge)
    ./"$codex_dir"/container-run.sh "./$codex_dir/container-suite.sh both purge"
    ;;

  host:container:nixos:build)
    ./"$nixos_dir"/container-build.sh
    ;;
  host:container:nixos:healthcheck)
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64-nixos}" \
      ./"$nixos_dir"/container-healthcheck.sh
    ;;
  host:container:nixos:shell)
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64-nixos}" \
      CODEX_HARNESS_WORKSPACE_MODE=image \
      ./"$nixos_dir"/container-shell.sh
    ;;
  host:container:nixos:task)
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64-nixos}" \
      CODEX_HARNESS_WORKSPACE_MODE=image \
      ./"$nixos_dir"/container-run.sh "task $args"
    ;;
  host:container:nixos:just)
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64-nixos}" \
      CODEX_HARNESS_WORKSPACE_MODE=image \
      ./"$nixos_dir"/container-run.sh "just $args"
    ;;
  host:container:nixos:test)
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64-nixos}" \
      CODEX_HARNESS_WORKSPACE_MODE=image \
      ./"$nixos_dir"/container-run.sh "./$nixos_dir/container-suite.sh both test"
    ;;
  host:container:nixos:coverage)
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64-nixos}" \
      CODEX_HARNESS_WORKSPACE_MODE=image \
      ./"$nixos_dir"/container-run.sh "./$nixos_dir/container-suite.sh both coverage"
    ;;
  host:container:nixos:purge)
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64-nixos}" \
      CODEX_HARNESS_WORKSPACE_MODE=image \
      ./"$nixos_dir"/container-run.sh "./$nixos_dir/container-suite.sh both purge"
    ;;

  container:nixos:healthcheck)
    ./"$nixos_dir"/container-healthcheck.sh
    ;;
  container:nixos:pull)
    ./"$nixos_dir"/container-pull.sh
    ;;
  container:nixos:build)
    ./"$nixos_dir"/container-build.sh
    ;;
  container:nixos:shell)
    ./"$nixos_dir"/container-shell.sh
    ;;
  container:nixos:task)
    ./"$nixos_dir"/container-run.sh "task $args"
    ;;
  container:nixos:just)
    ./"$nixos_dir"/container-run.sh "just $args"
    ;;
  container:nixos:setup)
    ./"$nixos_dir"/container-run.sh "./$nixos_dir/container-suite.sh both setup"
    ;;
  container:nixos:test)
    ./"$nixos_dir"/container-run.sh "./$nixos_dir/container-suite.sh both test"
    ;;
  container:nixos:coverage)
    ./"$nixos_dir"/container-run.sh "./$nixos_dir/container-suite.sh both coverage"
    ;;
  container:nixos:clean)
    ./"$nixos_dir"/container-run.sh "./$nixos_dir/container-suite.sh both clean"
    ;;
  container:nixos:purge)
    ./"$nixos_dir"/container-run.sh "./$nixos_dir/container-suite.sh both purge"
    ;;

  *)
    echo "lifecycle.sh: unknown verb '$verb'" >&2
    exit 64
    ;;
esac
