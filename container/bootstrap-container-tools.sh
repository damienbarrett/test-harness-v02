#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/go/bin:$PATH"
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-1}"
export CARGO_PROFILE_RELEASE_LTO="${CARGO_PROFILE_RELEASE_LTO:-false}"
export CARGO_PROFILE_RELEASE_CODEGEN_UNITS="${CARGO_PROFILE_RELEASE_CODEGEN_UNITS:-16}"

install_cargo_bin() {
  local command_name=$1
  local package_name=$2
  local version=$3

  if ! command -v "$command_name" >/dev/null 2>&1; then
    cargo install "$package_name" --locked --version "$version"
  fi
}

install_go_bin() {
  local command_name=$1
  local package_ref=$2

  if ! command -v "$command_name" >/dev/null 2>&1; then
    go install "$package_ref"
  fi
}

rustup target add wasm32-wasip1
rustup component add llvm-tools-preview

install_cargo_bin just just 1.49.0
install_cargo_bin cargo-component cargo-component 0.21.1
install_cargo_bin cargo-llvm-cov cargo-llvm-cov 0.6.21
install_go_bin task github.com/go-task/task/v3/cmd/task@v3.50.0

echo "Container harness tools are ready."
