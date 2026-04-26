# Container and Cloud Lifecycle

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

just image-bootstrap
just image-setup
just image-test
just image-coverage
```

The shorter root commands are equivalent once the environment has the required tools:

```sh
task setup
task test
task coverage

just setup
just test
just coverage
```

`image:bootstrap` first runs `/opt/codex/setup_universal.sh` when that Codex universal setup script is present, then installs tools that are not guaranteed to exist in a base image, including `task`, `just`, `cargo-component`, and `cargo-llvm-cov`. It uses version probes so repeated runs do not reinstall tools unnecessarily.

Cloud setup scripts should usually run:

```sh
./container/bootstrap-container-tools.sh
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

just host-container-build
just host-container-test
just host-container-coverage
```

`host:container:build` builds `codex-harness:arm64` from the repository root. The image contains:

- the Codex universal base image and pinned runtime versions
- harness tools installed by `container/Containerfile`
- locked Playwright browser dependencies for the JavaScript browser tests
- this repository source, including initialized submodules

The host test and coverage commands run that source-containing image with:

```sh
CODEX_HARNESS_WORKSPACE_MODE=image
CODEX_HARNESS_IMAGE=codex-harness:arm64
```

In `image` workspace mode, `container/container-run.sh` does not pass a `--volume` flag. The repository path inside the image is `/workspace/v02`.

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

just container-test
just container-coverage
```

These commands use `CODEX_HARNESS_WORKSPACE_MODE=bind` by default and mount:

```sh
<host repo>:/workspace/v02
```

Bind-mounted runs are convenient for local editing, but they are not representative of cloud-hosted environments. Prefer the `host:container:*` commands when validating that the repository works without host filesystem sharing.

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
CONTAINER=/usr/local/bin/container just container-healthcheck
```

`CARGO_TARGET_DIR` defaults to `/tmp/codex-harness-cargo-target` in container-hosted runs. That keeps Rust build artifacts out of a mounted checkout and keeps container builds isolated from host `target/` directories.
