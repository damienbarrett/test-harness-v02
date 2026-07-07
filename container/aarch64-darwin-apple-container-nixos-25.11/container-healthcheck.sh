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
image="${CODEX_HARNESS_IMAGE:-nixpkgs/nix-flakes:nixos-25.11-aarch64-linux}"
image_name="$image"
image_tag=""
if [[ "$image" == *:* ]]; then
  image_name="${image%:*}"
  image_tag="${image##*:}"
fi

echo "container: $container_bin"
"$container_bin" system start >/dev/null
"$container_bin" system status

if [[ -n "$image_tag" ]]; then
  image_found="$("$container_bin" image list | awk -v name="$image_name" -v tag="$image_tag" 'NR > 1 && $1 == name && $2 == tag { print "yes" }')"
else
  image_found="$("$container_bin" image list | awk -v name="$image_name" 'NR > 1 && $1 == name { print "yes" }')"
fi

if [[ "$image_found" != "yes" ]]; then
  echo "Image not found locally: $image" >&2
  echo "Run ./container/aarch64-darwin-apple-container-nixos-25.11/container-pull.sh first, or set CODEX_HARNESS_IMAGE to an existing image." >&2
  exit 1
fi

# shellcheck disable=SC2016 # single quotes are deliberate: $(uname -m) must expand inside the container, not on the host
"$container_bin" run --rm --arch "$arch" "$image" /bin/sh -c 'printf "container arch: %s\n" "$(uname -m)"'
