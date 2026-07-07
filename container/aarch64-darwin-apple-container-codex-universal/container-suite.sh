#!/usr/bin/env bash
set -euo pipefail

# Failure policy (docs/refactoring-plan.md Phase 10; constitution.md §4: "If
# any sub-layer fails, the orchestrator exits non-zero immediately. No silent
# partial successes."):
#
#   * Fail-fast by default. The first failing step stops the run right away
#     with a message naming the step. In particular a failed `setup` is never
#     followed by `test`/`coverage` -- there is nothing to gain from testing
#     against an environment whose setup did not complete.
#   * `--diagnostic` (or CONTAINER_SUITE_DIAGNOSTIC=1) opts into running every
#     remaining step anyway, e.g. to see whether `test` also fails after a
#     broken `setup`. Diagnostic runs are always exit non-zero if anything
#     failed and their output is clearly labelled DIAGNOSTIC MODE so nobody
#     mistakes a diagnostic run for a clean pass.

usage() {
  cat >&2 <<'EOF'
Usage: container-suite.sh [--diagnostic] <task|just|both> <setup|test|coverage|clean|purge>

Runs harness commands inside one container process. The test and coverage
actions run setup first so ephemeral containers keep setup artifacts such as
Playwright browser downloads available for the following test command.

Fail-fast by default: the first failing step stops the suite immediately
(a failed setup is not followed by test/coverage). Pass --diagnostic, or set
CONTAINER_SUITE_DIAGNOSTIC=1, to run every step anyway for troubleshooting;
the run still exits non-zero if anything failed, and is labelled DIAGNOSTIC
MODE in its output.
EOF
}

diagnostic=${CONTAINER_SUITE_DIAGNOSTIC:-0}
if [[ "$diagnostic" != 0 ]]; then
  diagnostic=1
fi

args=()
for arg in "$@"; do
  case "$arg" in
    --diagnostic)
      diagnostic=1
      ;;
    *)
      args+=("$arg")
      ;;
  esac
done
set -- "${args[@]}"

if [[ $# -ne 2 ]]; then
  usage
  exit 64
fi

scope="$1"
action="$2"

case "$scope" in
  task | just | both) ;;
  *)
    usage
    exit 64
    ;;
esac

case "$action" in
  setup | test | coverage | clean | purge) ;;
  *)
    usage
    exit 64
    ;;
esac

if [[ "$diagnostic" -eq 1 ]]; then
  echo "=== DIAGNOSTIC MODE: continuing past step failures; run will still exit non-zero on any failure ==="
fi

declare -a summary=()
overall_status=0
stop=0

run_step() {
  local label="$1"
  shift

  echo "=== $label ==="
  set +e
  "$@"
  local status=$?
  set -e

  summary+=("$label exit=$status")
  if [[ "$status" -ne 0 ]]; then
    overall_status=1
    if [[ "$diagnostic" -eq 1 ]]; then
      echo "DIAGNOSTIC MODE: '$label' failed (exit=$status); continuing because --diagnostic/CONTAINER_SUITE_DIAGNOSTIC is set." >&2
    else
      echo "container-suite.sh: '$label' failed (exit=$status); stopping (fail-fast). Re-run with --diagnostic to see what else fails." >&2
      stop=1
    fi
  fi
}

run_runner() {
  local runner="$1"

  case "$action" in
    setup)
      run_step "$runner setup" "$runner" setup
      ;;
    test | coverage)
      run_step "$runner setup" "$runner" setup
      [[ "$stop" -eq 0 ]] || return 0
      run_step "$runner $action" "$runner" "$action"
      ;;
    clean | purge)
      run_step "$runner $action" "$runner" "$action"
      ;;
  esac
}

case "$scope" in
  task)
    run_runner task
    ;;
  just)
    run_runner just
    ;;
  both)
    run_runner task
    if [[ "$stop" -eq 0 ]]; then
      run_runner just
    fi
    ;;
esac

if [[ "$diagnostic" -eq 1 && "$overall_status" -ne 0 ]]; then
  echo "=== DIAGNOSTIC MODE: run finished with failures; see per-step exit codes below ==="
fi
echo "=== summary ==="
printf '%s\n' "${summary[@]}"
exit "$overall_status"
