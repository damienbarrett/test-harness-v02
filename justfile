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

# Run task test inside the selected harness image
container-task-test:
    ./container/container-run.sh 'task test'

# Run task coverage inside the selected harness image
container-task-coverage:
    ./container/container-run.sh 'task coverage'

# Run task clean inside the selected harness image
container-task-clean:
    ./container/container-run.sh 'task clean'

# Run just setup inside the selected harness image
container-just-setup:
    ./container/container-run.sh 'just setup'

# Run just test inside the selected harness image
container-just-test:
    ./container/container-run.sh 'just test'

# Run just coverage inside the selected harness image
container-just-coverage:
    ./container/container-run.sh 'just coverage'

# Run just clean inside the selected harness image
container-just-clean:
    ./container/container-run.sh 'just clean'

# Run both task setup and just setup inside one container
container-setup:
    ./container/container-run.sh 'task_status=0; just_status=0; echo "=== task setup ==="; task setup; task_status=$?; echo "=== just setup ==="; just setup; just_status=$?; echo "=== summary ==="; echo "task setup exit=$task_status"; echo "just setup exit=$just_status"; if [ "$task_status" -ne 0 ] || [ "$just_status" -ne 0 ]; then exit 1; fi'

# Run both task test and just test inside one container
container-test:
    ./container/container-run.sh 'task_status=0; just_status=0; echo "=== task test ==="; task test; task_status=$?; echo "=== just test ==="; just test; just_status=$?; echo "=== summary ==="; echo "task test exit=$task_status"; echo "just test exit=$just_status"; if [ "$task_status" -ne 0 ] || [ "$just_status" -ne 0 ]; then exit 1; fi'

# Run both task coverage and just coverage inside one container
container-coverage:
    ./container/container-run.sh 'task_status=0; just_status=0; echo "=== task coverage ==="; task coverage; task_status=$?; echo "=== just coverage ==="; just coverage; just_status=$?; echo "=== summary ==="; echo "task coverage exit=$task_status"; echo "just coverage exit=$just_status"; if [ "$task_status" -ne 0 ] || [ "$just_status" -ne 0 ]; then exit 1; fi'

# Run both task clean and just clean inside one container
container-clean:
    ./container/container-run.sh 'task_status=0; just_status=0; echo "=== task clean ==="; task clean; task_status=$?; echo "=== just clean ==="; just clean; just_status=$?; echo "=== summary ==="; echo "task clean exit=$task_status"; echo "just clean exit=$just_status"; if [ "$task_status" -ne 0 ] || [ "$just_status" -ne 0 ]; then exit 1; fi'

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
