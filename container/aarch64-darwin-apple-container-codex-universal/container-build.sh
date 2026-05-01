#!/usr/bin/env bash
set -euo pipefail

solution_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$solution_dir/../.." && pwd)"
solution_path="${solution_dir#"$repo_root"/}"

container_bin="${CONTAINER:-}"
if [[ -z "$container_bin" ]]; then
  if command -v container >/dev/null 2>&1; then
    container_bin="$(command -v container)"
  elif [[ -x /usr/local/bin/container ]]; then
    container_bin="/usr/local/bin/container"
  else
    echo "Apple container CLI not found. Install it or set CONTAINER=/path/to/container." >&2
    exit 127
  fi
fi

arch="${CODEX_HARNESS_ARCH:-arm64}"
tag="${CODEX_HARNESS_BUILD_TAG:-codex-harness:arm64}"
build_context="${CODEX_HARNESS_BUILD_CONTEXT:-}"

if [[ -z "$build_context" ]]; then
  build_context="$(mktemp -d "$repo_root/.container-build-context.XXXXXX")"
  trap 'rm -rf "$build_context"' EXIT

  tar -C "$repo_root" \
    --exclude='.dockerignore' \
    --exclude='.DS_Store' \
    --exclude='.git' \
    --exclude='*/.git' \
    --exclude='.cache' \
    --exclude='*/.cache' \
    --exclude='.container-build-context*' \
    --exclude='*/.container-build-context*' \
    --exclude='.claude' \
    --exclude='*/.claude' \
    --exclude='.playwright-mcp' \
    --exclude='*/.playwright-mcp' \
    --exclude='.task' \
    --exclude='*/.task' \
    --exclude='.coverage' \
    --exclude='*/.coverage' \
    --exclude='.pytest_cache' \
    --exclude='*/.pytest_cache' \
    --exclude='.venv' \
    --exclude='*/.venv' \
    --exclude='__pycache__' \
    --exclude='*/__pycache__' \
    --exclude='htmlcov' \
    --exclude='*/htmlcov' \
    --exclude='node_modules' \
    --exclude='*/node_modules' \
    --exclude='target' \
    --exclude='*/target' \
    --exclude='transpiled' \
    --exclude='*/transpiled' \
    --exclude='*.egg-info' \
    --exclude='*.log' \
    --exclude='*.profdata' \
    --exclude='*.profraw' \
    --exclude='*.pyc' \
    --exclude='*.tmp' \
    --exclude='*.temp' \
    --exclude='*.wasm' \
    --exclude='tmp' \
    --exclude='*/tmp' \
    --exclude='temp' \
    --exclude='*/temp' \
    -cf - . | tar -C "$build_context" -xf -
fi

(
  cd "$build_context"
  "$container_bin" build \
    --arch "$arch" \
    --tag "$tag" \
    --file "$solution_path/Containerfile" \
    .
)
