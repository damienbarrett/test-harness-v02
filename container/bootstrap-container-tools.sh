#!/usr/bin/env bash
# Provisions OS-level prerequisites for the harness:
#   1. Codex universal language version setup (Python/Node/Rust/Go via mise)
#   2. Single-user Nix install with experimental flakes feature
#   3. Playwright system libraries (apt) + browser binaries
#
# The harness's Containerfile bakes all three into codex-harness:arm64-nix
# at build time. This script is the runtime fallback for fresh codex-universal
# images that have none of it. Each step is idempotent — running this on a
# fully provisioned image is a fast no-op.
set -euo pipefail

export USER="${USER:-root}"
export HOME="${HOME:-/root}"
export PATH="/root/.nix-profile/bin:$PATH"

# 1. Nix
if ! command -v nix >/dev/null 2>&1; then
  if ! getent group nixbld >/dev/null; then
    groupadd -r nixbld
    for i in $(seq 1 10); do
      useradd -r -g nixbld -G nixbld -d /var/empty -s /sbin/nologin "nixbld$i" || true
    done
  fi
  curl -L https://nixos.org/nix/install -o /tmp/nix-install
  sh /tmp/nix-install --no-daemon --yes
  rm /tmp/nix-install
  mkdir -p /root/.config/nix
  echo 'experimental-features = nix-command flakes' > /root/.config/nix/nix.conf
fi

# 2. Playwright system libs + browsers
# Marker is written by both Containerfile (build time) and this script (runtime).
playwright_marker="/root/.cache/ms-playwright/.harness-provisioned"
if [[ ! -f "$playwright_marker" ]] && [[ -f /workspace/v02/javascript/library/package-lock.json ]]; then
  pwdir="/tmp/codex-harness-playwright"
  mkdir -p "$pwdir"
  cp /workspace/v02/javascript/library/package.json "$pwdir/"
  cp /workspace/v02/javascript/library/package-lock.json "$pwdir/"
  ( cd "$pwdir" && npm ci && npx playwright install --with-deps chromium webkit )
  rm -rf "$pwdir"
  mkdir -p /root/.cache/ms-playwright
  touch "$playwright_marker"
fi

echo "Container harness provisioned (Nix $(nix --version | awk '{print $3}'))."
