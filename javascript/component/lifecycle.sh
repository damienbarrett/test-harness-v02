#!/usr/bin/env bash
# Canonical lifecycle implementation for javascript/component/.
#
# State ownership (Phase 7 of docs/refactoring-plan.md): HARNESS_DIR and its
# derived cache/output variables are defined once at the language root
# (javascript/lifecycle.sh) and inherited here when this script runs as that
# script's delegate. For direct invocation (`cd javascript/component && task
# test`), this is the one shared fallback rule used by every child
# lifecycle.sh in this repo: derive HARNESS_DIR relative to the parent
# (language root) directory, then apply the identical derivation chain.
set -eu

script_dir="$(cd "$(dirname "$0")" && pwd)"

export HARNESS_DIR="${HARNESS_DIR:-$(cd "$script_dir/.." && pwd)/.harness}"
export HARNESS_CACHE_DIR="${HARNESS_CACHE_DIR:-$HARNESS_DIR/cache}"
export HARNESS_OUTPUT_DIR="${HARNESS_OUTPUT_DIR:-$HARNESS_DIR/outputs}"

wit_path="../../common/wit/tasks.wit"
world_name="task-component"
output_wasm="task-component.wasm"

parser_wit_path="../../common/wit/html-parser.wit"
parser_world_name="new-world-parser"
parser_output_wasm="new-world-parser.wasm"

cmd_setup() {
  npm ci
}

cmd_build() {
  # -d all disables every optional WASI capability jco/componentize-js knows
  # how to gate (clocks, random, stdio, http, fetch-event). taskCollections
  # is a pure function (see src/app.js) that touches none of them, and
  # empirically the resulting component imports nothing at all -- verified
  # via wasmtime.component.Component.type().imports(engine) against the
  # built artifact (docs/refactoring-plan.md Phase 8). Do not re-add
  # `--enable clocks/random/stdio` (the pre-Phase-8 flags): each one was
  # previously undoing part of `-d all` for no reason this component needs.
  if [ -n "${JCO_FHS:-}" ]; then
    "$JCO_FHS" -c "npx jco componentize src/app.js --wit $wit_path -n $world_name -d all -o $output_wasm"
  else
    npx jco componentize src/app.js --wit "$wit_path" -n "$world_name" -d all -o "$output_wasm"
  fi
  if [ -n "${JCO_FHS:-}" ]; then
    "$JCO_FHS" -c "npx jco transpile $output_wasm -o transpiled/"
  else
    npx jco transpile "$output_wasm" -o transpiled/
  fi
  # The new-world-parser component is equally pure -- no clocks, random, or
  # stdio -- so it uses the same `-d all` capability minimization. Its entry
  # is the single src/new-world-parser.js module (core + binding glue in one
  # file): componentize-js evaluates one self-contained module and does not
  # resolve relative imports, so unlike Python/Rust this language keeps the
  # core and glue together. The central WASM harness owns its black-box
  # contract test; there is no Node-host transpile step for it (unlike
  # task-component, whose transpiled/ output feeds wasm-count-tasks.test.js).
  if [ -n "${JCO_FHS:-}" ]; then
    "$JCO_FHS" -c "npx jco componentize src/new-world-parser.js --wit $parser_wit_path -n $parser_world_name -d all -o $parser_output_wasm"
  else
    npx jco componentize src/new-world-parser.js --wit "$parser_wit_path" -n "$parser_world_name" -d all -o "$parser_output_wasm"
  fi
}

# build is a native dependency of test/coverage in both runners, so these
# only perform the leaf-level test invocation.
cmd_test() {
  node --test tests/*.test.js
}

# Formatter + lint + audit gate (Phase 9 of docs/refactoring-plan.md).
# prettier/eslint are locked devDependencies of this package (package.json /
# package-lock.json); the flat config is ./eslint.config.js, which excludes
# the jco-generated transpiled/ output. The shared ../test-support/
# directory is covered by javascript/library's lint, not re-linted here.
# eslint runs with --max-warnings=0 (constitution.md §8: no warnings
# permitted). The npm audit gate needs registry access, like `update`.
cmd_lint() {
  npx prettier --check "src/**/*.js" "tests/**/*.js" "eslint.config.js"
  npx eslint --max-warnings=0 src tests eslint.config.js
  npm audit --audit-level=high
}

# Explicitly upgrades locked dependencies and regenerates the lockfile
# (constitution.md §4); npm audit fix additionally pulls in any newer
# in-range versions that resolve known advisories, and (like npm audit)
# exits non-zero if unfixable vulnerabilities remain - so update fails
# loudly rather than locking in a known-vulnerable tree. Network access is
# expected here.
#
# Note on package.json's jco range (">=1.16.0 <1.18.0"): every jco release
# in 1.7.0-1.15.0 and >=1.18.0 depends (via @bytecodealliance/componentize-js
# -> @bytecodealliance/weval) on `decompress`, which has an unpatched
# critical advisory (GHSA-mp2f-45pm-3cg9). 1.16.x-1.17.x is the newest clean
# window, so update deliberately stays inside it; widen the range only after
# upstream jco drops the vulnerable weval/decompress chain.
cmd_update() {
  npm update
  npm audit fix
}

cmd_coverage() {
  node --test --experimental-test-coverage \
    --test-coverage-include='src/**' \
    --test-coverage-lines=100 \
    --test-coverage-branches=100 \
    --test-coverage-functions=100 \
    tests/*.test.js
}

cmd_clean() {
  rm -rf .coverage .nyc_output coverage output test-results transpiled task-component.wasm new-world-parser.wasm
}

cmd_purge() {
  rm -rf node_modules .task
}

verb="${1:-}"
case "$verb" in
  setup) cmd_setup ;;
  build) cmd_build ;;
  test) cmd_test ;;
  lint) cmd_lint ;;
  coverage) cmd_coverage ;;
  clean) cmd_clean ;;
  purge) cmd_purge ;;
  update) cmd_update ;;
  *)
    echo "lifecycle.sh: unknown verb '$verb'" >&2
    exit 64
    ;;
esac
