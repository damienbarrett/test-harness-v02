# Codex Universal Container

This repository can run inside OpenAI's Codex universal image on Apple silicon through Apple's `container` tool. The commands below prioritize native `linux/arm64` execution.

In this Codex app shell, Apple's binary is installed at `/usr/local/bin/container`, but `/usr/local/bin` may not be on `PATH`. The examples use a `CONTAINER` variable so they work either way.

## Run Existing Image

Start Apple's container service, then run the existing Codex universal image:

```sh
CONTAINER=${CONTAINER:-/usr/local/bin/container}
"$CONTAINER" system start

"$CONTAINER" run --rm -it \
  --arch arm64 \
  --memory 8G \
  --cpus 6 \
  --env CODEX_ENV_PYTHON_VERSION=3.13 \
  --env CODEX_ENV_NODE_VERSION=22 \
  --env CODEX_ENV_RUST_VERSION=1.92.0 \
  --env CODEX_ENV_GO_VERSION=1.25.9 \
  --volume "$PWD:/workspace/v02" \
  --workdir /workspace/v02 \
  ghcr.io/openai/codex-universal:latest
```

Inside the container, bootstrap the tools that are not included in the base image:

```sh
./container/bootstrap-container-tools.sh
```

Then run either harness:

```sh
task setup
task test
task coverage

just setup
just test
just coverage
```

For a one-shot run, run setup and test in the same ephemeral container so
browser runtimes downloaded by Playwright remain available to the tests:

```sh
CONTAINER=${CONTAINER:-/usr/local/bin/container}

"$CONTAINER" run --rm \
  --arch arm64 \
  --memory 8G \
  --cpus 6 \
  --env CODEX_ENV_PYTHON_VERSION=3.13 \
  --env CODEX_ENV_NODE_VERSION=22 \
  --env CODEX_ENV_RUST_VERSION=1.92.0 \
  --env CODEX_ENV_GO_VERSION=1.25.9 \
  --volume "$PWD:/workspace/v02" \
  --workdir /workspace/v02 \
  ghcr.io/openai/codex-universal:latest \
  -lc './container/bootstrap-container-tools.sh && task setup && task test'
```

## Optional Derived Image

If you have enough free disk and want to avoid bootstrapping tools on every run, build the derived image:

```sh
CONTAINER=${CONTAINER:-/usr/local/bin/container}

"$CONTAINER" build --arch arm64 --tag codex-harness:arm64 --file container/Containerfile .
```

Then run:

```sh
"$CONTAINER" run --rm -it \
  --arch arm64 \
  --memory 8G \
  --cpus 6 \
  --volume "$PWD:/workspace/v02" \
  --workdir /workspace/v02 \
  codex-harness:arm64
```

The derived image build uses the repository root as its build context so it can read `javascript/library/package-lock.json` and bake the locked Playwright browser revision into the image. Runtime commands still mount the live checkout, so tests run against local working-tree changes rather than a copy baked into the image.

The JavaScript setup commands install Linux browser dependencies with Playwright when they detect a Linux container. Because the default base-image runs use `--rm`, setup and test must happen in the same container unless you use the derived image or mount a persistent Playwright cache.

## Root Harness Commands

The root `Taskfile.yml` and `justfile` expose container-backed alternatives to the native commands. These commands default to native `arm64`, the Codex universal image, and the runtime versions used by the successful harness run.

Health checks and image setup:

```sh
task container:healthcheck
task container:pull
task container:build

just container-healthcheck
just container-pull
just container-build
```

Run the Task harness inside the container. The test and coverage wrappers run setup first in the same container:

```sh
task container:task:test
task container:task:coverage

just container-task-test
just container-task-coverage
```

Run the Just harness inside the container. The test and coverage wrappers run setup first in the same container:

```sh
task container:just:test
task container:just:coverage

just container-just-test
just container-just-coverage
```

Run both harnesses in the same container, preserving exit codes. The test and coverage wrappers run each harness setup before that harness command:

```sh
task container:test
task container:coverage

just container-test
just container-coverage
```

For one-off commands:

```sh
task container:task -- javascript:library:test
task container:just -- javascript/test

just container-task javascript:library:test
just container-just javascript/test
```

To use the optional derived image after `container:build`, set `CODEX_HARNESS_IMAGE`:

```sh
CODEX_HARNESS_IMAGE=codex-harness:arm64 task container:test
CODEX_HARNESS_IMAGE=codex-harness:arm64 just container-test
```

Other useful overrides:

```sh
CODEX_HARNESS_MEMORY=16G CODEX_HARNESS_CPUS=10 task container:test
CONTAINER=/usr/local/bin/container just container-healthcheck
```
