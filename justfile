# List available commands
default:
    @just --list

# Provision OS-level prerequisites (Nix, Playwright system libs + browsers)
provision:
    ./lifecycle.sh provision

# Install all dependencies
setup: python-setup javascript-setup rust-setup test-harness-setup

# Build all WASM components
build: python-build javascript-build rust-build

# Run all tests (contract validation and quality gates first)
test: contracts-check lint python-test javascript-test rust-test test-harness-test wasm-test

# Run all formatter, lint, dependency-audit, and shellcheck gates
lint: python-lint javascript-lint rust-lint test-harness-lint check-shell

# Run all tests with coverage
coverage: python-coverage javascript-coverage rust-coverage test-harness-coverage

# Remove generated outputs while preserving dependency state
clean: python-clean javascript-clean rust-clean test-harness-clean
    ./lifecycle.sh clean

# Remove generated outputs and setup artifacts
purge: python-purge javascript-purge rust-purge test-harness-purge
    ./lifecycle.sh purge

# Upgrade locked dependencies and regenerate lockfiles everywhere
update: python-update javascript-update rust-update test-harness-update

# Run unified WASM contract tests across all implementations (builds first)
wasm-test: build
    ./lifecycle.sh wasm:test

# Check Taskfile.yml and justfile parity
check-runners:
    ./lifecycle.sh check:runners

# Validate common/ contract suites before any component is invoked
contracts-check:
    ./lifecycle.sh contracts:check

# ShellCheck every tracked shell script in the repository
check-shell:
    ./lifecycle.sh check:shell

# Verify clean/purge state ownership (destructive, restores via setup+build after; not part of test)
check-lifecycle:
    ./lifecycle.sh check:lifecycle

# Install container/image tools in the current checked-out repo environment
image-bootstrap:
    ./lifecycle.sh image:bootstrap

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
    ./lifecycle.sh host:container:build

# Host step: open a shell in the source-containing Apple container image without a host bind mount
host-container-shell:
    ./lifecycle.sh host:container:shell

# Host step: run an arbitrary task command in the source-containing Apple container image without a host bind mount
host-container-task *command:
    ./lifecycle.sh host:container:task {{command}}

# Host step: run an arbitrary just command in the source-containing Apple container image without a host bind mount
host-container-just *command:
    ./lifecycle.sh host:container:just {{command}}

# Host step: run setup and tests in the source-containing Apple container image without a host bind mount
host-container-test:
    ./lifecycle.sh host:container:test

# Host step: run setup and coverage in the source-containing Apple container image without a host bind mount
host-container-coverage:
    ./lifecycle.sh host:container:coverage

# Host step: purge generated outputs and setup artifacts in the source-containing Apple container image without a host bind mount
host-container-purge:
    ./lifecycle.sh host:container:purge

# Host step: check Apple container runtime and the selected harness image
container-healthcheck:
    ./lifecycle.sh container:healthcheck

# Host step: reclaim disk space (prune dangling images + remove image builder)
container-prune-all:
    ./lifecycle.sh container:prune-all

# Host step: pull the Codex universal image for native Apple silicon
container-pull:
    ./lifecycle.sh container:pull

# Host step: build the source-containing harness image
container-build:
    ./lifecycle.sh container:build

# Host step: open an interactive shell in the selected image with the host checkout bind-mounted
container-shell:
    ./lifecycle.sh container:shell

# Host step: run an arbitrary task command with the host checkout bind-mounted
container-task *command:
    ./lifecycle.sh container:task {{command}}

# Host step: run an arbitrary just command with the host checkout bind-mounted
container-just *command:
    ./lifecycle.sh container:just {{command}}

# Run task setup inside the selected harness image
container-task-setup:
    ./lifecycle.sh container:task:setup

# Run task setup and test inside the selected harness image
container-task-test:
    ./lifecycle.sh container:task:test

# Run task setup and coverage inside the selected harness image
container-task-coverage:
    ./lifecycle.sh container:task:coverage

# Run task clean inside the selected harness image
container-task-clean:
    ./lifecycle.sh container:task:clean

# Run task purge inside the selected harness image
container-task-purge:
    ./lifecycle.sh container:task:purge

# Run just setup inside the selected harness image
container-just-setup:
    ./lifecycle.sh container:just:setup

# Run just setup and test inside the selected harness image
container-just-test:
    ./lifecycle.sh container:just:test

# Run just setup and coverage inside the selected harness image
container-just-coverage:
    ./lifecycle.sh container:just:coverage

# Run just clean inside the selected harness image
container-just-clean:
    ./lifecycle.sh container:just:clean

# Run just purge inside the selected harness image
container-just-purge:
    ./lifecycle.sh container:just:purge

# Run both task setup and just setup inside one container
container-setup:
    ./lifecycle.sh container:setup

# Run both task and just setup/test inside one container
container-test:
    ./lifecycle.sh container:test

# Run both task and just setup/coverage inside one container
container-coverage:
    ./lifecycle.sh container:coverage

# Run both task clean and just clean inside one container
container-clean:
    ./lifecycle.sh container:clean

# Run both task purge and just purge inside one container
container-purge:
    ./lifecycle.sh container:purge

# Host step: build the NixOS 25.11 Apple container image containing this checkout
host-container-nixos-build:
    ./lifecycle.sh host:container:nixos:build

# Host step: check the source-containing NixOS 25.11 Apple container image
host-container-nixos-healthcheck:
    ./lifecycle.sh host:container:nixos:healthcheck

# Host step: open a shell in the source-containing NixOS 25.11 Apple container image without a host bind mount
host-container-nixos-shell:
    ./lifecycle.sh host:container:nixos:shell

# Host step: run an arbitrary task command in the source-containing NixOS 25.11 Apple container image without a host bind mount
host-container-nixos-task *command:
    ./lifecycle.sh host:container:nixos:task {{command}}

# Host step: run an arbitrary just command in the source-containing NixOS 25.11 Apple container image without a host bind mount
host-container-nixos-just *command:
    ./lifecycle.sh host:container:nixos:just {{command}}

# Host step: run setup and tests in the source-containing NixOS 25.11 Apple container image without a host bind mount
host-container-nixos-test:
    ./lifecycle.sh host:container:nixos:test

# Host step: run setup and coverage in the source-containing NixOS 25.11 Apple container image without a host bind mount
host-container-nixos-coverage:
    ./lifecycle.sh host:container:nixos:coverage

# Host step: purge generated outputs and setup artifacts in the source-containing NixOS 25.11 Apple container image without a host bind mount
host-container-nixos-purge:
    ./lifecycle.sh host:container:nixos:purge

# Host step: check Apple container runtime and the selected NixOS 25.11 image
container-nixos-healthcheck:
    ./lifecycle.sh container:nixos:healthcheck

# Host step: pull the NixOS 25.11 base image for native Apple silicon
container-nixos-pull:
    ./lifecycle.sh container:nixos:pull

# Host step: build the NixOS 25.11 source-containing harness image
container-nixos-build:
    ./lifecycle.sh container:nixos:build

# Host step: open an interactive shell in the NixOS 25.11 image with the host checkout bind-mounted
container-nixos-shell:
    ./lifecycle.sh container:nixos:shell

# Host step: run an arbitrary task command in the NixOS 25.11 image with the host checkout bind-mounted
container-nixos-task *command:
    ./lifecycle.sh container:nixos:task {{command}}

# Host step: run an arbitrary just command in the NixOS 25.11 image with the host checkout bind-mounted
container-nixos-just *command:
    ./lifecycle.sh container:nixos:just {{command}}

# Run both task setup and just setup inside one NixOS 25.11 container
container-nixos-setup:
    ./lifecycle.sh container:nixos:setup

# Run both task and just setup/test inside one NixOS 25.11 container
container-nixos-test:
    ./lifecycle.sh container:nixos:test

# Run both task and just setup/coverage inside one NixOS 25.11 container
container-nixos-coverage:
    ./lifecycle.sh container:nixos:coverage

# Run both task clean and just clean inside one NixOS 25.11 container
container-nixos-clean:
    ./lifecycle.sh container:nixos:clean

# Run both task purge and just purge inside one NixOS 25.11 container
container-nixos-purge:
    ./lifecycle.sh container:nixos:purge

# Each per-language recipe enters its sub-repo's Nix dev shell so the
# sub-repo's justfile sees its declared toolchain on PATH.

# Install Python dependencies
python-setup:
    ./lifecycle.sh python-setup

# Install JavaScript dependencies
javascript-setup:
    ./lifecycle.sh javascript-setup

# Install Rust dependencies
rust-setup:
    ./lifecycle.sh rust-setup

# Build the Python WASM component
python-build:
    ./lifecycle.sh python-build

# Build the JavaScript WASM component
javascript-build:
    ./lifecycle.sh javascript-build

# Build the Rust WASM component
rust-build:
    ./lifecycle.sh rust-build

# Run Python tests
python-test:
    ./lifecycle.sh python-test

# Run JavaScript tests
javascript-test:
    ./lifecycle.sh javascript-test

# Run Rust tests
rust-test:
    ./lifecycle.sh rust-test

# Run Python formatter and lint gates
python-lint:
    ./lifecycle.sh python-lint

# Run JavaScript formatter, lint, and audit gates
javascript-lint:
    ./lifecycle.sh javascript-lint

# Run Rust formatter and lint gates
rust-lint:
    ./lifecycle.sh rust-lint

# Run Python tests with coverage
python-coverage:
    ./lifecycle.sh python-coverage

# Run JavaScript tests with coverage
javascript-coverage:
    ./lifecycle.sh javascript-coverage

# Run Rust tests with coverage
rust-coverage:
    ./lifecycle.sh rust-coverage

# Clean Python build artifacts
python-clean:
    ./lifecycle.sh python-clean

# Clean JavaScript build artifacts
javascript-clean:
    ./lifecycle.sh javascript-clean

# Clean Rust build artifacts
rust-clean:
    ./lifecycle.sh rust-clean

# Install test harness dependencies
test-harness-setup:
    ./lifecycle.sh test-harness-setup

# Run test harness self-checks
test-harness-test:
    ./lifecycle.sh test-harness-test

# Run test harness formatter and lint gates
test-harness-lint:
    ./lifecycle.sh test-harness-lint

# Run test harness coverage checks
test-harness-coverage:
    ./lifecycle.sh test-harness-coverage

# Clean test harness generated outputs
test-harness-clean:
    ./lifecycle.sh test-harness-clean

# Purge Python setup artifacts
python-purge:
    ./lifecycle.sh python-purge

# Purge JavaScript setup artifacts
javascript-purge:
    ./lifecycle.sh javascript-purge

# Purge Rust setup artifacts
rust-purge:
    ./lifecycle.sh rust-purge

# Purge test harness setup artifacts
test-harness-purge:
    ./lifecycle.sh test-harness-purge

# Upgrade Python locked dependencies
python-update:
    ./lifecycle.sh python-update

# Upgrade JavaScript locked dependencies
javascript-update:
    ./lifecycle.sh javascript-update

# Upgrade Rust locked dependencies
rust-update:
    ./lifecycle.sh rust-update

# Upgrade test harness locked dependencies
test-harness-update:
    ./lifecycle.sh test-harness-update
