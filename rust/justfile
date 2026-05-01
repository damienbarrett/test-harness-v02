# List available commands
default:
    @just --list

# Install all dependencies
setup: library-setup component-setup

# Run all tests
test: library-test component-test

# Run all tests with coverage
coverage: library-coverage component-coverage

# Remove generated outputs while preserving dependency state
clean: library-clean component-clean

# Remove generated outputs and setup artifacts
purge: library-purge component-purge

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
