#!/usr/bin/env bash
set -euo pipefail

container_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

exec "$container_bin" build \
  --arch "$arch" \
  --tag "$tag" \
  --file "$container_dir/Containerfile" \
  "$container_dir"
