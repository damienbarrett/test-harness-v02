#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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
cpus="${CODEX_HARNESS_CPUS:-8}"
image="${CODEX_HARNESS_IMAGE:-ghcr.io/openai/codex-universal:latest}"
memory="${CODEX_HARNESS_MEMORY:-12G}"
workspace="${CODEX_HARNESS_WORKSPACE:-/workspace/v02}"
bootstrap="${CODEX_HARNESS_BOOTSTRAP:-1}"

if [[ "$bootstrap" == "1" || "$bootstrap" == "true" || "$bootstrap" == "yes" ]]; then
  command="./container/bootstrap-container-tools.sh && exec bash -l"
else
  command="exec bash -l"
fi

exec "$container_bin" run --rm -it \
  --arch "$arch" \
  --memory "$memory" \
  --cpus "$cpus" \
  --env CODEX_ENV_PYTHON_VERSION="${CODEX_ENV_PYTHON_VERSION:-3.13}" \
  --env CODEX_ENV_NODE_VERSION="${CODEX_ENV_NODE_VERSION:-22}" \
  --env CODEX_ENV_RUST_VERSION="${CODEX_ENV_RUST_VERSION:-1.92.0}" \
  --env CODEX_ENV_GO_VERSION="${CODEX_ENV_GO_VERSION:-1.25.9}" \
  --volume "$repo_root:$workspace" \
  --workdir "$workspace" \
  "$image" \
  -lc "$command"
