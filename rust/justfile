export PATH := env_var('HOME') + "/.local/bin:" + env_var('HOME') + "/.cargo/bin:" + env_var('HOME') + "/go/bin:" + env_var('PATH')
LOCAL_HARNESS_DIR := justfile_directory() + "/.harness"
export HARNESS_DIR := env_var_or_default('HARNESS_DIR', LOCAL_HARNESS_DIR)
export HARNESS_OUTPUT_DIR := env_var_or_default('HARNESS_OUTPUT_DIR', HARNESS_DIR + "/outputs")
export HARNESS_CACHE_DIR := env_var_or_default('HARNESS_CACHE_DIR', HARNESS_DIR + "/cache")
export CARGO_TARGET_DIR := env_var_or_default('CARGO_TARGET_DIR', HARNESS_OUTPUT_DIR + "/rust/cargo-target")

# List available commands
default:
    @just --list

# Install all dependencies
setup:
    just library/setup
    just component/setup

# Run all tests
test:
    just library/test
    just component/test

# Run all tests with coverage
coverage:
    just library/coverage
    just component/coverage

# Remove generated outputs while preserving dependency state
clean:
    just library/clean
    just component/clean
    rm -rf "$HARNESS_OUTPUT_DIR/rust"

# Remove generated outputs and setup artifacts
purge:
    just library/purge
    just component/purge
    rm -rf "{{LOCAL_HARNESS_DIR}}" "$HARNESS_CACHE_DIR/rust" "$HARNESS_OUTPUT_DIR/rust"

# Install library dependencies
library-setup:
    just library/setup

# Install component dependencies
component-setup:
    just component/setup

# Build the component WASM artifact
component-build:
    just component/build

# Run library tests
library-test:
    just library/test

# Run component tests
component-test:
    just component/test

# Run library tests with coverage
library-coverage:
    just library/coverage

# Run component tests with coverage
component-coverage:
    just component/coverage

# Clean library build artifacts
library-clean:
    just library/clean

# Clean component build artifacts
component-clean:
    just component/clean

# Purge library setup artifacts
library-purge:
    just library/purge

# Purge component setup artifacts
component-purge:
    just component/purge
