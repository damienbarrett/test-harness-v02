#!/usr/bin/env bash
# Canonical lifecycle implementation for javascript/library/.
set -eu

cmd_setup() {
  npm ci
  # Symlink the Nix-store-installed playwright into node_modules so
  # ESM imports resolve. PLAYWRIGHT_NPM_PATH is set by the flake's
  # shellHook; package.json intentionally doesn't declare playwright.
  mkdir -p node_modules
  ln -sfT "$PLAYWRIGHT_NPM_PATH" node_modules/playwright
}

cmd_test() {
  if [ -n "${PLAYWRIGHT_FHS:-}" ]; then
    "$PLAYWRIGHT_FHS" -c 'node --test --test-timeout=60000 tests/count.test.js tests/browser.test.js'
  else
    node --test --test-timeout=60000 tests/count.test.js tests/browser.test.js
  fi
  bun test tests/bun.test.js
  deno test --allow-read tests/deno.test.js
}

cmd_coverage() {
  bun test tests/bun.test.js
  deno test --allow-read tests/deno.test.js
  if [ -n "${PLAYWRIGHT_FHS:-}" ]; then
    "$PLAYWRIGHT_FHS" -c "node --test --test-timeout=60000 --experimental-test-coverage --test-coverage-include='src/**' --test-coverage-lines=100 --test-coverage-branches=100 --test-coverage-functions=100 tests/count.test.js tests/browser.test.js"
  else
    node --test --test-timeout=60000 --experimental-test-coverage --test-coverage-include='src/**' --test-coverage-lines=100 --test-coverage-branches=100 --test-coverage-functions=100 tests/count.test.js tests/browser.test.js
  fi
}

cmd_clean() {
  rm -rf .coverage .nyc_output coverage output playwright-report test-results
}

# purge's dependency on `clean` is expressed natively by both runners
# (Taskfile `deps: [clean]` / justfile `purge: clean`), so this only performs
# the leaf-level work that used to be purge's own trailing command.
cmd_purge() {
  rm -rf node_modules
}

verb="${1:-}"
case "$verb" in
  setup) cmd_setup ;;
  test) cmd_test ;;
  coverage) cmd_coverage ;;
  clean) cmd_clean ;;
  purge) cmd_purge ;;
  *)
    echo "lifecycle.sh: unknown verb '$verb'" >&2
    exit 64
    ;;
esac
