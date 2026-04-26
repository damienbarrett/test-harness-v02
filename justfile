export PATH := env_var('HOME') + "/.local/bin:" + env_var('HOME') + "/.cargo/bin:" + env_var('HOME') + "/go/bin:" + env_var('HOME') + "/.local/share/mise/shims:" + env_var('PATH')

# List available commands
default:
    @just --list

# Install all dependencies
setup: python-setup javascript-setup rust-setup

# Run all tests
test: python-test javascript-test rust-test

# Run all tests with coverage
coverage: python-coverage javascript-coverage rust-coverage

# Clean all build artifacts
clean: python-clean javascript-clean rust-clean

# Run unified WASM contract tests across all implementations
wasm-test:
    ./test-harness/run-wasm-tests.py

# Check Taskfile.yml and justfile parity
check-runners:
    ./test-harness/check-runner-parity.py

# Install container/image tools in the current checked-out repo environment
image-bootstrap:
    ./container/bootstrap-container-tools.sh

# Install all dependencies in the current checked-out repo environment
image-setup: setup

# Run all tests in the current checked-out repo environment
image-test: test

# Run all coverage checks in the current checked-out repo environment
image-coverage: coverage

# Clean build artifacts in the current checked-out repo environment
image-clean: clean

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

# Host step: check Apple container runtime and the selected harness image
container-healthcheck:
    ./container/container-healthcheck.sh

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

# Install Python dependencies
python-setup:
    just python/setup

# Install JavaScript dependencies
javascript-setup:
    just javascript/setup

# Install Rust dependencies
rust-setup:
    just rust/setup

# Run Python tests
python-test:
    just python/test

# Run JavaScript tests
javascript-test:
    just javascript/test

# Run Rust tests
rust-test:
    just rust/test

# Run Python tests with coverage
python-coverage:
    just python/coverage

# Run JavaScript tests with coverage
javascript-coverage:
    just javascript/coverage

# Run Rust tests with coverage
rust-coverage:
    just rust/coverage

# Clean Python build artifacts
python-clean:
    just python/clean

# Clean JavaScript build artifacts
javascript-clean:
    just javascript/clean

# Clean Rust build artifacts
rust-clean:
    just rust/clean
