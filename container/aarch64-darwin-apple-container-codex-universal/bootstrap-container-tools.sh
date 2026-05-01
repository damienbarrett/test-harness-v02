#!/usr/bin/env bash
# Provisions OS-level prerequisites for the harness — currently just Nix.
# Browsers + system libraries for Playwright are owned end-to-end by
# javascript/flake.nix (pkgs.playwright + pkgs.playwright-driver), so
# apt-get is no longer involved.
#
# The harness's Containerfile installs Nix at image build time so this
# script is a fast no-op on `codex-harness:arm64-nix`. On a fresh
# `codex-universal:latest` image, it installs Nix once at runtime.
set -euo pipefail

export USER="${USER:-root}"
export HOME="${HOME:-/root}"
export PATH="/root/.nix-profile/bin:$PATH"

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

echo "Container harness provisioned (Nix $(nix --version | awk '{print $3}'))."
