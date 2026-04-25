export PATH := env_var('HOME') + "/.local/bin:" + env_var('HOME') + "/.cargo/bin:" + env_var('HOME') + "/go/bin:" + env_var('PATH')

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

# Check Apple container runtime and the selected harness image
container-healthcheck:
    ./container/container-healthcheck.sh

# Pull the Codex universal image for native Apple silicon
container-pull:
    ./container/container-pull.sh

# Build the optional cached harness image
container-build:
    ./container/container-build.sh

# Open an interactive shell in the selected harness image
container-shell:
    ./container/container-shell.sh

# Run an arbitrary task command inside the selected harness image
container-task *command:
    ./container/container-run.sh 'task {{command}}'

# Run an arbitrary just command inside the selected harness image
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
