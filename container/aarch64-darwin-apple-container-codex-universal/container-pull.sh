#!/usr/bin/env bash
set -euo pipefail

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
image="${CODEX_HARNESS_BASE_IMAGE:-ghcr.io/openai/codex-universal:latest}"

exec "$container_bin" image pull --arch "$arch" "$image"
