# List available commands
default:
    @just --list

# Provision OS-level prerequisites (Nix, Playwright system libs + browsers)
provision:
    ./container/aarch64-darwin-apple-container-codex-universal/bootstrap-container-tools.sh

# Install all dependencies
setup:
    just python/setup
    just javascript/setup
    just rust/setup
    just test-harness/setup

# Run all tests
test:
    just python/test
    just javascript/test
    just rust/test
    just test-harness/test

# Run all tests with coverage
coverage:
    just python/coverage
    just javascript/coverage
    just rust/coverage
    just test-harness/coverage

# Remove generated outputs while preserving dependency state
clean:
    just python/clean
    just javascript/clean
    just rust/clean
    just test-harness/clean
    rm -rf .output output

# Remove generated outputs and setup artifacts
purge:
    just python/purge
    just javascript/purge
    just rust/purge
    just test-harness/purge
    rm -rf .output output

# Run unified WASM contract tests across all implementations
wasm-test:
    cd test-harness && nix develop --command bash -c 'UV_CACHE_DIR="${UV_CACHE_DIR:-.cache/uv}" ./run-wasm-tests.py'

# Check Taskfile.yml and justfile parity
check-runners:
    cd test-harness && nix develop --command bash -c 'UV_CACHE_DIR="${UV_CACHE_DIR:-.cache/uv}" ./check-runner-parity.py'

# Install container/image tools in the current checked-out repo environment
image-bootstrap:
    ./container/aarch64-darwin-apple-container-codex-universal/bootstrap-container-tools.sh

# Install all dependencies in the current checked-out repo environment
image-setup: setup

# Run all tests in the current checked-out repo environment
image-test: test

# Run all coverage checks in the current checked-out repo environment
image-coverage: coverage

# Remove generated outputs in the current checked-out repo environment
image-clean: clean

# Remove generated outputs and setup artifacts in the current checked-out repo environment
image-purge: purge

# Host step: build an Apple container image containing this checkout
host-container-build:
    ./container/aarch64-darwin-apple-container-codex-universal/container-build.sh

# Host step: open a shell in the source-containing Apple container image without a host bind mount
host-container-shell:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/aarch64-darwin-apple-container-codex-universal/container-shell.sh

# Host step: run an arbitrary task command in the source-containing Apple container image without a host bind mount
host-container-task *command:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh 'task {{command}}'

# Host step: run an arbitrary just command in the source-containing Apple container image without a host bind mount
host-container-just *command:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh 'just {{command}}'

# Host step: run setup and tests in the source-containing Apple container image without a host bind mount
host-container-test:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh './container/aarch64-darwin-apple-container-codex-universal/container-suite.sh both test'

# Host step: run setup and coverage in the source-containing Apple container image without a host bind mount
host-container-coverage:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh './container/aarch64-darwin-apple-container-codex-universal/container-suite.sh both coverage'

# Host step: purge generated outputs and setup artifacts in the source-containing Apple container image without a host bind mount
host-container-purge:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh './container/aarch64-darwin-apple-container-codex-universal/container-suite.sh both purge'

# Host step: check Apple container runtime and the selected harness image
container-healthcheck:
    ./container/aarch64-darwin-apple-container-codex-universal/container-healthcheck.sh

# Host step: reclaim disk space (prune dangling images + remove image builder)
container-prune-all:
    ./container/aarch64-darwin-apple-container-codex-universal/container-prune-all.sh

# Host step: pull the Codex universal image for native Apple silicon
container-pull:
    ./container/aarch64-darwin-apple-container-codex-universal/container-pull.sh

# Host step: build the source-containing harness image
container-build:
    ./container/aarch64-darwin-apple-container-codex-universal/container-build.sh

# Host step: open an interactive shell in the selected image with the host checkout bind-mounted
container-shell:
    ./container/aarch64-darwin-apple-container-codex-universal/container-shell.sh

# Host step: run an arbitrary task command with the host checkout bind-mounted
container-task *command:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh 'task {{command}}'

# Host step: run an arbitrary just command with the host checkout bind-mounted
container-just *command:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh 'just {{command}}'

# Run task setup inside the selected harness image
container-task-setup:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh 'task setup'

# Run task setup and test inside the selected harness image
container-task-test:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh './container/aarch64-darwin-apple-container-codex-universal/container-suite.sh task test'

# Run task setup and coverage inside the selected harness image
container-task-coverage:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh './container/aarch64-darwin-apple-container-codex-universal/container-suite.sh task coverage'

# Run task clean inside the selected harness image
container-task-clean:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh 'task clean'

# Run task purge inside the selected harness image
container-task-purge:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh 'task purge'

# Run just setup inside the selected harness image
container-just-setup:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh 'just setup'

# Run just setup and test inside the selected harness image
container-just-test:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh './container/aarch64-darwin-apple-container-codex-universal/container-suite.sh just test'

# Run just setup and coverage inside the selected harness image
container-just-coverage:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh './container/aarch64-darwin-apple-container-codex-universal/container-suite.sh just coverage'

# Run just clean inside the selected harness image
container-just-clean:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh 'just clean'

# Run just purge inside the selected harness image
container-just-purge:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh 'just purge'

# Run both task setup and just setup inside one container
container-setup:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh './container/aarch64-darwin-apple-container-codex-universal/container-suite.sh both setup'

# Run both task and just setup/test inside one container
container-test:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh './container/aarch64-darwin-apple-container-codex-universal/container-suite.sh both test'

# Run both task and just setup/coverage inside one container
container-coverage:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh './container/aarch64-darwin-apple-container-codex-universal/container-suite.sh both coverage'

# Run both task clean and just clean inside one container
container-clean:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh './container/aarch64-darwin-apple-container-codex-universal/container-suite.sh both clean'

# Run both task purge and just purge inside one container
container-purge:
    ./container/aarch64-darwin-apple-container-codex-universal/container-run.sh './container/aarch64-darwin-apple-container-codex-universal/container-suite.sh both purge'

# Host step: build the NixOS 25.11 Apple container image containing this checkout
host-container-nixos-build:
    ./container/aarch64-darwin-apple-container-nixos-25.11/container-build.sh

# Host step: check the source-containing NixOS 25.11 Apple container image
host-container-nixos-healthcheck:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64-nixos}" ./container/aarch64-darwin-apple-container-nixos-25.11/container-healthcheck.sh

# Host step: open a shell in the source-containing NixOS 25.11 Apple container image without a host bind mount
host-container-nixos-shell:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64-nixos}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/aarch64-darwin-apple-container-nixos-25.11/container-shell.sh

# Host step: run an arbitrary task command in the source-containing NixOS 25.11 Apple container image without a host bind mount
host-container-nixos-task *command:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64-nixos}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/aarch64-darwin-apple-container-nixos-25.11/container-run.sh 'task {{command}}'

# Host step: run an arbitrary just command in the source-containing NixOS 25.11 Apple container image without a host bind mount
host-container-nixos-just *command:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64-nixos}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/aarch64-darwin-apple-container-nixos-25.11/container-run.sh 'just {{command}}'

# Host step: run setup and tests in the source-containing NixOS 25.11 Apple container image without a host bind mount
host-container-nixos-test:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64-nixos}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/aarch64-darwin-apple-container-nixos-25.11/container-run.sh './container/aarch64-darwin-apple-container-nixos-25.11/container-suite.sh both test'

# Host step: run setup and coverage in the source-containing NixOS 25.11 Apple container image without a host bind mount
host-container-nixos-coverage:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64-nixos}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/aarch64-darwin-apple-container-nixos-25.11/container-run.sh './container/aarch64-darwin-apple-container-nixos-25.11/container-suite.sh both coverage'

# Host step: purge generated outputs and setup artifacts in the source-containing NixOS 25.11 Apple container image without a host bind mount
host-container-nixos-purge:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64-nixos}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/aarch64-darwin-apple-container-nixos-25.11/container-run.sh './container/aarch64-darwin-apple-container-nixos-25.11/container-suite.sh both purge'

# Host step: check Apple container runtime and the selected NixOS 25.11 image
container-nixos-healthcheck:
    ./container/aarch64-darwin-apple-container-nixos-25.11/container-healthcheck.sh

# Host step: pull the NixOS 25.11 base image for native Apple silicon
container-nixos-pull:
    ./container/aarch64-darwin-apple-container-nixos-25.11/container-pull.sh

# Host step: build the NixOS 25.11 source-containing harness image
container-nixos-build:
    ./container/aarch64-darwin-apple-container-nixos-25.11/container-build.sh

# Host step: open an interactive shell in the NixOS 25.11 image with the host checkout bind-mounted
container-nixos-shell:
    ./container/aarch64-darwin-apple-container-nixos-25.11/container-shell.sh

# Host step: run an arbitrary task command in the NixOS 25.11 image with the host checkout bind-mounted
container-nixos-task *command:
    ./container/aarch64-darwin-apple-container-nixos-25.11/container-run.sh 'task {{command}}'

# Host step: run an arbitrary just command in the NixOS 25.11 image with the host checkout bind-mounted
container-nixos-just *command:
    ./container/aarch64-darwin-apple-container-nixos-25.11/container-run.sh 'just {{command}}'

# Run both task setup and just setup inside one NixOS 25.11 container
container-nixos-setup:
    ./container/aarch64-darwin-apple-container-nixos-25.11/container-run.sh './container/aarch64-darwin-apple-container-nixos-25.11/container-suite.sh both setup'

# Run both task and just setup/test inside one NixOS 25.11 container
container-nixos-test:
    ./container/aarch64-darwin-apple-container-nixos-25.11/container-run.sh './container/aarch64-darwin-apple-container-nixos-25.11/container-suite.sh both test'

# Run both task and just setup/coverage inside one NixOS 25.11 container
container-nixos-coverage:
    ./container/aarch64-darwin-apple-container-nixos-25.11/container-run.sh './container/aarch64-darwin-apple-container-nixos-25.11/container-suite.sh both coverage'

# Run both task clean and just clean inside one NixOS 25.11 container
container-nixos-clean:
    ./container/aarch64-darwin-apple-container-nixos-25.11/container-run.sh './container/aarch64-darwin-apple-container-nixos-25.11/container-suite.sh both clean'

# Run both task purge and just purge inside one NixOS 25.11 container
container-nixos-purge:
    ./container/aarch64-darwin-apple-container-nixos-25.11/container-run.sh './container/aarch64-darwin-apple-container-nixos-25.11/container-suite.sh both purge'

# Each per-language recipe enters its sub-repo's Nix dev shell so the
# sub-repo's justfile sees its declared toolchain on PATH.

# Install Python dependencies
python-setup:
    cd python && nix develop --command just setup

# Install JavaScript dependencies
javascript-setup:
    cd javascript && nix develop --command just setup

# Install Rust dependencies
rust-setup:
    cd rust && nix develop --command just setup

# Run Python tests
python-test:
    cd python && nix develop --command just test

# Run JavaScript tests
javascript-test:
    cd javascript && nix develop --command just test

# Run Rust tests
rust-test:
    cd rust && nix develop --command just test

# Run Python tests with coverage
python-coverage:
    cd python && nix develop --command just coverage

# Run JavaScript tests with coverage
javascript-coverage:
    cd javascript && nix develop --command just coverage

# Run Rust tests with coverage
rust-coverage:
    cd rust && nix develop --command just coverage

# Clean Python build artifacts
python-clean:
    cd python && nix develop --command just clean

# Clean JavaScript build artifacts
javascript-clean:
    cd javascript && nix develop --command just clean

# Clean Rust build artifacts
rust-clean:
    cd rust && nix develop --command just clean

# Install test harness dependencies
test-harness-setup:
    cd test-harness && nix develop --command just setup

# Run test harness self-checks
test-harness-test:
    cd test-harness && nix develop --command just test

# Run test harness coverage checks
test-harness-coverage:
    cd test-harness && nix develop --command just coverage

# Clean test harness generated outputs
test-harness-clean:
    cd test-harness && nix develop --command just clean

# Purge Python setup artifacts
python-purge:
    cd python && nix develop --command just purge

# Purge JavaScript setup artifacts
javascript-purge:
    cd javascript && nix develop --command just purge

# Purge Rust setup artifacts
rust-purge:
    cd rust && nix develop --command just purge

# Purge test harness setup artifacts
test-harness-purge:
    cd test-harness && nix develop --command just purge
