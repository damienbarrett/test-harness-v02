#!/usr/bin/env bash
# Reclaim disk space used by Apple's container CLI.
#
# Apple's `container` doesn't expose a `builder prune` command (Docker has
# `docker buildx prune`); the only way to reclaim build-cache space is to
# remove the builder container entirely. It will be re-created automatically
# on the next `container build`. The trade-off: next build is ~3 minutes
# slower because BuildKit re-fetches base layers and rebuilds its cache.
#
# Run when disk usage is uncomfortable (>~100 GB in
# ~/Library/Application Support/com.apple.container/).
set -euo pipefail

container_bin="${CONTAINER:-}"
if [[ -z "$container_bin" ]]; then
  if command -v container >/dev/null 2>&1; then
    container_bin="$(command -v container)"
  elif [[ -x /usr/local/bin/container ]]; then
    container_bin="/usr/local/bin/container"
  else
    echo "Apple container CLI not found." >&2
    exit 127
  fi
fi

before="$(df -h "/Users/$(id -un)" 2>/dev/null | awk 'NR==2 {print $4 " free"}')"

echo "=== Pruning dangling image layers ==="
"$container_bin" image prune || true

echo
echo "=== Removing image builder (frees BuildKit cache) ==="
"$container_bin" builder stop 2>/dev/null || true
"$container_bin" builder delete 2>/dev/null || true

echo
echo "=== Disk usage ==="
"$container_bin" system df
echo
echo "Before: $before"
echo "After:  $(df -h "/Users/$(id -un)" 2>/dev/null | awk 'NR==2 {print $4 " free"}')"
