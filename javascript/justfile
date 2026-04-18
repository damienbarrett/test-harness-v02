export PATH := env_var('HOME') + "/.local/bin:" + env_var('HOME') + "/.cargo/bin:" + env_var('HOME') + "/go/bin:" + env_var('PATH')

# List available commands
default:
    @just --list

# Install all dependencies
setup: library-setup component-setup

# Run all tests
test: library-test component-test

# Run all tests with coverage
coverage: library-coverage component-coverage

# Clean all build artifacts
clean: library-clean component-clean

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
