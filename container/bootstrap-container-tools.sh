#!/usr/bin/env bash
set -euo pipefail

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/go/bin:$HOME/.local/share/mise/shims:$PATH"
export CODEX_ENV_PYTHON_VERSION="${CODEX_ENV_PYTHON_VERSION:-3.13}"
export CODEX_ENV_NODE_VERSION="${CODEX_ENV_NODE_VERSION:-22}"
export CODEX_ENV_RUST_VERSION="${CODEX_ENV_RUST_VERSION:-1.92.0}"
export CODEX_ENV_GO_VERSION="${CODEX_ENV_GO_VERSION:-1.25.9}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/codex-harness-uv-cache}"
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-1}"
export CARGO_PROFILE_RELEASE_LTO="${CARGO_PROFILE_RELEASE_LTO:-false}"
export CARGO_PROFILE_RELEASE_CODEGEN_UNITS="${CARGO_PROFILE_RELEASE_CODEGEN_UNITS:-16}"

version_matches() {
  local version=$1
  shift

  local output
  if ! output="$("$@" 2>/dev/null)"; then
    return 1
  fi

  grep -Eq "(^|[^0-9])${version//./\\.}([^0-9]|$)" <<<"$output"
}

install_cargo_bin() {
  local command_name=$1
  local package_name=$2
  local version=$3
  shift 3

  local -a version_command=("$command_name" --version)
  if [[ $# -gt 0 ]]; then
    version_command=("$@")
  fi

  if ! command -v "$command_name" >/dev/null 2>&1 || ! version_matches "$version" "${version_command[@]}"; then
    cargo install "$package_name" --locked --version "$version"
  fi
}

install_go_bin() {
  local command_name=$1
  local package_ref=$2
  local version=$3

  if ! command -v "$command_name" >/dev/null 2>&1 || ! version_matches "$version" "$command_name" --version; then
    go install "$package_ref"
  fi
}

if [[ -x /opt/codex/setup_universal.sh ]]; then
  /opt/codex/setup_universal.sh
  hash -r
fi

rustup target add wasm32-wasip1
rustup component add llvm-tools-preview

install_cargo_bin just just 1.49.0
install_cargo_bin cargo-component cargo-component 0.21.1
install_cargo_bin cargo-llvm-cov cargo-llvm-cov 0.6.21 cargo llvm-cov --version
install_go_bin task github.com/go-task/task/v3/cmd/task@v3.50.0 3.50.0

echo "Container harness tools are ready."
