# Codex Universal Apple Container Lifecycle

The harness has two separate lifecycle layers:

- **Image lifecycle**: commands run from inside an environment that already has this repository checked out. This is the path for Codex Cloud, Claude Cloud, an interactive Codex universal container, or a locally built Apple container image that contains the source.
- **Host lifecycle**: commands run on a host machine that first needs to create or enter an Apple `container` environment. This is the path for a MacBook Pro or Raspberry Pi controlling containers.

After the host has established an environment, use the same image lifecycle commands everywhere.

## Image Lifecycle

Run these from the repository root inside the checked-out environment:

```sh
task image:bootstrap
task image:setup
task image:test
task image:coverage
task image:clean
task image:purge

just image-bootstrap
just image-setup
just image-test
just image-coverage
just image-clean
just image-purge
```

The shorter root commands are equivalent once the environment has the required tools:

```sh
task setup
task test
task coverage
task clean
task purge

just setup
just test
just coverage
just clean
just purge
```

`image:bootstrap` first runs `/opt/codex/setup_universal.sh` when that Codex universal setup script is present, then installs tools that are not guaranteed to exist in a base image, including `task`, `just`, `cargo-component`, and `cargo-llvm-cov`. It uses version probes so repeated runs do not reinstall tools unnecessarily.

Cloud setup scripts should usually run:

```sh
./container/aarch64-darwin-apple-container-codex-universal/bootstrap-container-tools.sh
task setup
```

Then validation can run:

```sh
task test
task coverage
```

If the repository was cloned without submodules, initialize them before setup:

```sh
git submodule update --init --recursive
```

## Host Lifecycle: Apple Container Without Host Bind Mounts

Use this when the host should establish a container/image first, then run the same lifecycle inside it without binding the host checkout into the container.

```sh
task host:container:build
task host:container:test
task host:container:coverage
task host:container:purge

just host-container-build
just host-container-test
just host-container-coverage
just host-container-purge
```

`host:container:build` builds `codex-harness:arm64` from the repository root. The image contains:

- the Codex universal base image and pinned runtime versions
- harness tools installed by `container/aarch64-darwin-apple-container-codex-universal/Containerfile`
- locked Playwright browser dependencies for the JavaScript browser tests
- this repository source, including initialized submodules

The host test and coverage commands run that source-containing image with:

```sh
CODEX_HARNESS_WORKSPACE_MODE=image
CODEX_HARNESS_IMAGE=codex-harness:arm64
```

In `image` workspace mode, `container/aarch64-darwin-apple-container-codex-universal/container-run.sh` does not pass a `--volume` flag. The repository path inside the image is `/workspace/v02`.

Open a no-bind shell in the image:

```sh
task host:container:shell
just host-container-shell
```

Run one-off no-bind commands:

```sh
task host:container:task -- rust:component:test
task host:container:just -- rust/component/test

just host-container-task rust:component:test
just host-container-just rust/component/test
```

## Host Lifecycle: Apple Container With Host Bind Mounts

Use this for local iteration when you want the container to run against the live host checkout.

```sh
task container:test
task container:coverage
task container:clean
task container:purge

just container-test
just container-coverage
just container-clean
just container-purge
```

These commands use `CODEX_HARNESS_WORKSPACE_MODE=bind` by default and mount:

```sh
<host repo>:/workspace/v02
```

Bind-mounted runs are convenient for local editing, but they are not representative of cloud-hosted environments. Prefer the `host:container:*` commands when validating that the repository works without host filesystem sharing.

## Clean and Purge

`clean` is safe generated-output cleanup. It removes files such as coverage reports, transpiled output, generated bindings, and WASM artifacts while preserving dependency/setup state such as `.venv`, `node_modules`, Cargo caches, Playwright browser downloads, and future Nix store state.

`purge` is destructive setup cleanup for the current layer. It runs the same generated-output cleanup and also removes repo-owned dependency/setup artifacts such as Python virtual environments and JavaScript `node_modules`. The next `setup` may be slower and may require network access unless caches have already been warmed.

`common/` is a source-contract repository and does not expose lifecycle commands. `test-harness/` does expose lifecycle commands because it owns executable harness checks.

## Manual Apple Container Commands

The wrapper scripts default to native `linux/arm64` execution. In this Codex app shell, Apple's binary is installed at `/usr/local/bin/container`, but `/usr/local/bin` may not be on `PATH`.

Start the container service:

```sh
CONTAINER=${CONTAINER:-/usr/local/bin/container}
"$CONTAINER" system start
```

Run a source-containing image without a host bind mount:

```sh
"$CONTAINER" run --rm -it \
  --arch arm64 \
  --memory 8G \
  --cpus 6 \
  --env CODEX_ENV_PYTHON_VERSION=3.13 \
  --env CODEX_ENV_NODE_VERSION=22 \
  --env CODEX_ENV_RUST_VERSION=1.92.0 \
  --env CODEX_ENV_GO_VERSION=1.25.9 \
  --env CARGO_TARGET_DIR=/tmp/codex-harness-cargo-target \
  --env UV_CACHE_DIR=/tmp/codex-harness-uv-cache \
  --workdir /workspace/v02 \
  codex-harness:arm64
```

Run the base Codex universal image with a host bind mount:

```sh
"$CONTAINER" run --rm -it \
  --arch arm64 \
  --memory 8G \
  --cpus 6 \
  --env CODEX_ENV_PYTHON_VERSION=3.13 \
  --env CODEX_ENV_NODE_VERSION=22 \
  --env CODEX_ENV_RUST_VERSION=1.92.0 \
  --env CODEX_ENV_GO_VERSION=1.25.9 \
  --env CARGO_TARGET_DIR=/tmp/codex-harness-cargo-target \
  --env UV_CACHE_DIR=/tmp/codex-harness-uv-cache \
  --volume "$PWD:/workspace/v02" \
  --workdir /workspace/v02 \
  ghcr.io/openai/codex-universal:latest
```

## Useful Overrides

```sh
CODEX_HARNESS_MEMORY=16G CODEX_HARNESS_CPUS=10 task host:container:test
CODEX_HARNESS_BUILD_TAG=codex-harness:dev task host:container:build
CODEX_HARNESS_IMAGE=codex-harness:dev task host:container:test
CODEX_HARNESS_CARGO_TARGET_DIR=/tmp/custom-cargo-target task container:test
CODEX_HARNESS_UV_CACHE_DIR=/tmp/custom-uv-cache task container:test
CONTAINER=/usr/local/bin/container just container-healthcheck
```

`CARGO_TARGET_DIR` defaults to `/tmp/codex-harness-cargo-target` in container-hosted runs. That keeps Rust build artifacts out of a mounted checkout and keeps container builds isolated from host `target/` directories.

`UV_CACHE_DIR` defaults to `/tmp/codex-harness-uv-cache` in container-hosted runs. Direct Python and test-harness lifecycle commands default to a gitignored `.cache/uv` under the repo that owns the command, so they do not depend on the host-global uv cache under the user's home directory.
