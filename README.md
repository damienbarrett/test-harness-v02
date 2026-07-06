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

`build` compiles each language's WASM component (`{lang}/component/task-component.wasm`) and is safe to run repeatedly; nothing else in the lifecycle assumes a `.wasm` artifact already exists from a prior manual build. `task wasm:test` and `task test` both depend on `build`, so a clean checkout with no `.wasm` files still passes. `clean` removes generated outputs while preserving dependency/setup state. `purge` removes generated outputs and repo-owned setup artifacts, so the next `setup` may be slower.

Ignored workspace state is organized under `.harness/` by the lifecycle stage that removes it:

```text
.harness/
  outputs/  # removed by clean and purge
  cache/    # removed by purge
```

Lifecycle state names should describe the lifecycle step that owns removal. Build and report artifacts belong under `outputs`; dependency and setup reuse state belongs under `cache`.

Python and test-harness lifecycle commands use `.harness/cache` by default instead of the host-global uv cache under the user's home directory. Override with `HARNESS_DIR=/path/to/state` or `UV_CACHE_DIR=/path/to/cache` when needed.

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
