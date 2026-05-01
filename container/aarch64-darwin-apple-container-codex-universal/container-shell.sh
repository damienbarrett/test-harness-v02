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
cpus="${CODEX_HARNESS_CPUS:-8}"
image="${CODEX_HARNESS_IMAGE:-ghcr.io/openai/codex-universal:latest}"
memory="${CODEX_HARNESS_MEMORY:-12G}"
workspace="${CODEX_HARNESS_WORKSPACE:-/workspace/v02}"
bootstrap="${CODEX_HARNESS_BOOTSTRAP:-1}"
harness_dir="${CODEX_HARNESS_DIR:-/tmp/codex-harness}"
harness_output_dir="${CODEX_HARNESS_OUTPUT_DIR:-$harness_dir/outputs}"
harness_cache_dir="${CODEX_HARNESS_CACHE_DIR:-$harness_dir/cache}"
cargo_target_dir="${CODEX_HARNESS_CARGO_TARGET_DIR:-$harness_output_dir/rust/cargo-target}"
uv_cache_dir="${CODEX_HARNESS_UV_CACHE_DIR:-$harness_cache_dir/uv}"
workspace_mode="${CODEX_HARNESS_WORKSPACE_MODE:-bind}"

command="exec nix develop ./$solution_path"
if [[ "$bootstrap" == "1" || "$bootstrap" == "true" || "$bootstrap" == "yes" ]]; then
  command="./$solution_path/bootstrap-container-tools.sh && export PATH=/root/.nix-profile/bin:\$PATH && $command"
fi

declare -a run_args=(
  run --rm -it
  --arch "$arch"
  --memory "$memory"
  --cpus "$cpus"
  --env CODEX_ENV_PYTHON_VERSION="${CODEX_ENV_PYTHON_VERSION:-3.13}"
  --env CODEX_ENV_NODE_VERSION="${CODEX_ENV_NODE_VERSION:-22}"
  --env CODEX_ENV_RUST_VERSION="${CODEX_ENV_RUST_VERSION:-1.92.0}"
  --env CODEX_ENV_GO_VERSION="${CODEX_ENV_GO_VERSION:-1.25.9}"
  --env HARNESS_DIR="$harness_dir"
  --env HARNESS_OUTPUT_DIR="$harness_output_dir"
  --env HARNESS_CACHE_DIR="$harness_cache_dir"
  --env CARGO_TARGET_DIR="$cargo_target_dir"
  --env UV_CACHE_DIR="$uv_cache_dir"
)

case "$workspace_mode" in
  bind)
    run_args+=(--volume "$repo_root:$workspace")
    ;;
  image)
    ;;
  *)
    echo "Unsupported CODEX_HARNESS_WORKSPACE_MODE=$workspace_mode. Use 'bind' or 'image'." >&2
    exit 64
    ;;
esac

run_args+=(--workdir "$workspace" "$image" -lc "$command")

exec "$container_bin" "${run_args[@]}"
