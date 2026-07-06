# Getting started

Clone the project:

```bash
git clone https://github.com/damienbarrett/test-harness-v02
```

This is a monorepo. `common/`, `python/`, `javascript/`, `rust/`, and
`test-harness/` are normal tracked directories.

## Sparse worktrees

Use sparse worktrees for agent sessions that should only see part of the
monorepo:

```bash
bin/dx-worktree create rust-bindgen rust
cd .worktrees/rust-bindgen
```

Every sparse worktree includes root-level files, `bin/`, and `common/`.
Additional command arguments select the workstream-specific directories.

Sparse-checkout only controls which files are present in that worktree. It does
not prevent a process from leaving the worktree if the surrounding execution
harness allows it. See `docs/worktrees.md` for details.

## Lifecycle

Repositories that participate in the lifecycle expose:

```bash
task setup
task build
task test
task coverage
task clean
task purge
```

`build` compiles each language's WASM component (`{lang}/component/task-component.wasm`) and is safe to run repeatedly; nothing else in the lifecycle assumes a `.wasm` artifact already exists from a prior manual build. `task wasm:test` and `task test` both depend on `build`, so a clean checkout with no `.wasm` files still passes.

`clean` and `purge` have distinct, tested contracts (constitution.md §4):

- **`clean`** removes *generated outputs only*: built `.wasm` artifacts, Python's `bindings/`, JavaScript's `transpiled/`, coverage artifacts (`.coverage`, `htmlcov/`, `coverage/`), `__pycache__`/`.pytest_cache`, and the contents of `$HARNESS_OUTPUT_DIR`. It preserves caches and installed dependencies: `.venv`, `node_modules`, cargo's build cache, and the `uv` package cache.
- **`purge`** removes *everything repository-owned*: every output `clean` removes, plus `.venv`, `node_modules`, cargo's target directory, `$HARNESS_DIR` (cache and outputs together, including the `uv` cache), and Task's own `.task/` checksum cache. After `task purge` at the repo root, `git status --ignored --porcelain` shows no repository-owned ignored artifact anywhere - verified on demand by `task check:lifecycle` (see below).

### State ownership: the `HARNESS_*` variables

Each of `python/`, `javascript/`, `rust/`, and `test-harness/` defines and exports the same variables exactly once, in that directory's own `lifecycle.sh` (its language/harness root). `library/` and `component/` sub-lifecycles inherit these exported values when invoked through their parent; when invoked directly (e.g. `cd python/component && task test`, with no `HARNESS_*` pre-exported) they derive the identical values themselves via one shared fallback rule - `HARNESS_DIR` relative to their own parent directory, then the same derivation chain. No `library/`/`component/` script defaults any of these independently.

| Variable | Default | Removed by | Purpose |
| --- | --- | --- | --- |
| `HARNESS_DIR` | `<dir>/.harness` | `purge` (whole) | Root of all lifecycle-owned state for that directory. |
| `HARNESS_CACHE_DIR` | `$HARNESS_DIR/cache` | `purge` only | Package-manager/build caches. |
| `HARNESS_OUTPUT_DIR` | `$HARNESS_DIR/outputs` | `clean` and `purge` | Build/report artifacts. |
| `UV_CACHE_DIR` (python, test-harness) | `$HARNESS_CACHE_DIR/uv` | `purge` (via `HARNESS_DIR`) | Shared `uv` package cache - `library` and `component` no longer default this to a local `.cache/uv`. |
| `CARGO_TARGET_DIR` (rust) | `$HARNESS_CACHE_DIR/cargo-target` | `purge` (`cargo clean`) | Cargo build cache, shared between `rust/library` and `rust/component`; `clean` never touches it. |

All four are overridable by exporting them before invoking `task`/`just` - the Apple-container scripts under `container/` already do this, pointing them at a container-local scratch path instead of the checkout.

### What `clean`/`purge` remove, by directory

| Directory | `clean` removes | `purge` additionally removes |
| --- | --- | --- |
| `python/library`, `javascript/library` | language-appropriate output artifacts (`__pycache__`, `.coverage`, `htmlcov`, `coverage/`, etc.) | `.venv` / `node_modules` |
| `python/component`, `javascript/component` | the above, plus the built `.wasm` and `bindings/`/`transpiled/` | `.venv` / `node_modules` |
| `rust/library` | nothing (no standalone output; its only state is the shared `$CARGO_TARGET_DIR` cache) | `cargo clean` (clears `$CARGO_TARGET_DIR`; shared with `rust/component`, so this also clears its cache) |
| `rust/component` | the copied `task-component.wasm` | `cargo clean` (same shared-cache tradeoff) |
| `python/`, `javascript/`, `rust/` (language root) | that language's slice of `$HARNESS_OUTPUT_DIR` | `$HARNESS_DIR` (cache + outputs), plus `.task/` |
| `test-harness/` | `__pycache__`, `.coverage`, `htmlcov`, etc. | `.venv`, `$HARNESS_DIR`, `.task/` |
| repo root | legacy `.output`/`output` (unused by any current recipe) | same |

`task check:lifecycle` / `just check-lifecycle` is an on-demand, **destructive-then-restoring** verification (deliberately not part of `task test`): it runs `task clean` and asserts outputs are gone while caches/dependencies survive, runs `task purge` and asserts zero repository-owned ignored artifacts remain anywhere in the tree, then runs `task setup && task build` to leave the checkout usable again. It needs network access after the purge step to refetch `uv`/`npm`/`cargo` dependencies.

`common/` is a source-contract repository for shared schemas, WIT, and fixtures. It is consumed by lifecycle repositories but does not expose lifecycle commands.

## Test ownership model

Each layer of the lifecycle owns a distinct slice of test coverage; no two
layers should re-prove the same fact:

- **Language tests** (`{lang}/library/tests/`, `{lang}/component/tests/`)
  own pure implementation logic and thin binding adapters. This includes:
  running the native/library logic directly (no WASM involved), and
  exercising the thin `component/src/` entry point against the real
  generated bindings (e.g. Python's `wit_world` package, Rust's
  `bindings.rs`) to catch signature drift between the source and
  `common/wit/`. Run via `task <lang>-test` / `task <lang>-coverage` from
  the repo root (or `task test` / `task coverage` inside `{lang}/`).
- **The central harness** (`test-harness/`, invoked via root
  `task wasm:test` / `just wasm-test`) owns black-box WASM contract
  parity: it discovers every `{lang}/component/task-component.wasm`,
  matches each `common/functions/**/*.test.json` suite to the worlds that
  export its interface, and asserts every language's compiled component
  produces the same observable behavior via `wasmtime`. This is the single
  place a server-side `wasmtime` contract case should exist — language
  test suites must not re-implement it (see Phase 5 of
  `docs/refactoring-plan.md`).
- **In-browser (client-side) validation** stays per-language. The
  constitution (`constitution.md` §7, WASM) requires validation in both a
  client-side (in-browser) and a server-side (`wasmtime`) host; the
  central harness only covers the server-side host, so it can never be the
  sole source of WASM contract confidence. Today JavaScript is the only
  language with any client-side coverage: `javascript/library/tests/
  browser.test.js` runs the isomorphic library module in Chromium/WebKit
  via Playwright, and `javascript/component/tests/wasm-count-tasks.test.js`
  runs the actual compiled component through `jco`'s transpiled output —
  a genuinely different host from the central harness's `wasmtime`, so it
  is kept rather than treated as a duplicate. No language currently runs
  the compiled `.wasm` component inside a real browser; closing that gap
  is out of scope for this phase.
