# List available commands
default:
    @just --list

# Provision OS-level prerequisites (Nix, Playwright system libs + browsers)
provision:
    ./container/bootstrap-container-tools.sh

# Install all dependencies
setup: python-setup javascript-setup rust-setup test-harness-setup

# Run all tests
test: python-test javascript-test rust-test test-harness-test

# Run all tests with coverage
coverage: python-coverage javascript-coverage rust-coverage test-harness-coverage

# Remove generated outputs while preserving dependency state
clean: python-clean javascript-clean rust-clean test-harness-clean
    rm -rf .output output

# Remove generated outputs and setup artifacts
purge: python-purge javascript-purge rust-purge test-harness-purge
    rm -rf .output output

# Run unified WASM contract tests across all implementations
wasm-test:
    cd test-harness && nix develop --command bash -c 'UV_CACHE_DIR="${UV_CACHE_DIR:-.cache/uv}" ./run-wasm-tests.py'

# Check Taskfile.yml and justfile parity
check-runners:
    cd test-harness && nix develop --command bash -c 'UV_CACHE_DIR="${UV_CACHE_DIR:-.cache/uv}" ./check-runner-parity.py'

# Install container/image tools in the current checked-out repo environment
image-bootstrap:
    ./container/bootstrap-container-tools.sh

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
    ./container/container-build.sh

# Host step: open a shell in the source-containing Apple container image without a host bind mount
host-container-shell:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/container-shell.sh

# Host step: run an arbitrary task command in the source-containing Apple container image without a host bind mount
host-container-task *command:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/container-run.sh 'task {{command}}'

# Host step: run an arbitrary just command in the source-containing Apple container image without a host bind mount
host-container-just *command:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/container-run.sh 'just {{command}}'

# Host step: run setup and tests in the source-containing Apple container image without a host bind mount
host-container-test:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/container-run.sh './container/container-suite.sh both test'

# Host step: run setup and coverage in the source-containing Apple container image without a host bind mount
host-container-coverage:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/container-run.sh './container/container-suite.sh both coverage'

# Host step: purge generated outputs and setup artifacts in the source-containing Apple container image without a host bind mount
host-container-purge:
    CODEX_HARNESS_IMAGE="${CODEX_HARNESS_IMAGE:-codex-harness:arm64}" CODEX_HARNESS_WORKSPACE_MODE=image ./container/container-run.sh './container/container-suite.sh both purge'

# Host step: check Apple container runtime and the selected harness image
container-healthcheck:
    ./container/container-healthcheck.sh

# Host step: reclaim disk space (prune dangling images + remove image builder)
container-prune-all:
    ./container/container-prune-all.sh

# Host step: pull the Codex universal image for native Apple silicon
container-pull:
    ./container/container-pull.sh

# Host step: build the source-containing harness image
container-build:
    ./container/container-build.sh

# Host step: open an interactive shell in the selected image with the host checkout bind-mounted
container-shell:
    ./container/container-shell.sh

# Host step: run an arbitrary task command with the host checkout bind-mounted
container-task *command:
    ./container/container-run.sh 'task {{command}}'

# Host step: run an arbitrary just command with the host checkout bind-mounted
container-just *command:
    ./container/container-run.sh 'just {{command}}'

# Run task setup inside the selected harness image
container-task-setup:
    ./container/container-run.sh 'task setup'

# Run task setup and test inside the selected harness image
container-task-test:
    ./container/container-run.sh './container/container-suite.sh task test'

# Run task setup and coverage inside the selected harness image
container-task-coverage:
    ./container/container-run.sh './container/container-suite.sh task coverage'

# Run task clean inside the selected harness image
container-task-clean:
    ./container/container-run.sh 'task clean'

# Run task purge inside the selected harness image
container-task-purge:
    ./container/container-run.sh 'task purge'

# Run just setup inside the selected harness image
container-just-setup:
    ./container/container-run.sh 'just setup'

# Run just setup and test inside the selected harness image
container-just-test:
    ./container/container-run.sh './container/container-suite.sh just test'

# Run just setup and coverage inside the selected harness image
container-just-coverage:
    ./container/container-run.sh './container/container-suite.sh just coverage'

# Run just clean inside the selected harness image
container-just-clean:
    ./container/container-run.sh 'just clean'

# Run just purge inside the selected harness image
container-just-purge:
    ./container/container-run.sh 'just purge'

# Run both task setup and just setup inside one container
container-setup:
    ./container/container-run.sh './container/container-suite.sh both setup'

# Run both task and just setup/test inside one container
container-test:
    ./container/container-run.sh './container/container-suite.sh both test'

# Run both task and just setup/coverage inside one container
container-coverage:
    ./container/container-run.sh './container/container-suite.sh both coverage'

# Run both task clean and just clean inside one container
container-clean:
    ./container/container-run.sh './container/container-suite.sh both clean'

# Run both task purge and just purge inside one container
container-purge:
    ./container/container-run.sh './container/container-suite.sh both purge'

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
