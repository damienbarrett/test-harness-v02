#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage: container-suite.sh <task|just|both> <setup|test|coverage|clean|purge>

Runs harness commands inside one container process. The test and coverage
actions run setup first so ephemeral containers keep setup artifacts such as
Playwright browser downloads available for the following test command.
EOF
}

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

declare -a summary=()
overall_status=0

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
    run_runner just
    ;;
esac

echo "=== summary ==="
printf '%s\n' "${summary[@]}"
exit "$overall_status"
