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
task lint
task coverage
task clean
task purge
task update
```

`build` compiles each language's WASM component (`{lang}/component/task-component.wasm`) and is safe to run repeatedly; nothing else in the lifecycle assumes a `.wasm` artifact already exists from a prior manual build. `task wasm:test` and `task test` both depend on `build`, so a clean checkout with no `.wasm` files still passes.

`update` (constitution.md §4) explicitly upgrades locked dependencies and regenerates lockfiles; it is the **only** verb allowed to change a lockfile, and the only one besides `setup` expected to need network access. Per project it runs `uv lock --upgrade && uv sync` (Python projects and `test-harness/`, with each project's extras), `cargo update` (Rust crates), and `npm update && npm audit fix` (JavaScript packages); language roots and the repo root aggregate their children like every other verb. Review and commit the resulting lockfile diff deliberately — nothing else regenerates it.

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

## Quality gates (`task lint` / `just lint`)

Root `task test` runs `contracts:check`, then `lint`, then the language/harness test suites, then `wasm:test` — so no test run can pass with a formatting, lint, audit, or shellcheck violation (constitution.md §8: no warnings permitted). `lint` can also be run on its own, at the root or in any implementation directory. What each directory's `lint` verb runs:

| Directory | Formatter | Linter | Extra gate |
| --- | --- | --- | --- |
| `rust/library`, `rust/component` | `cargo fmt --check` | `cargo clippy --all-targets -- -D warnings` | — |
| `python/library`, `python/component`, `test-harness/` | `ruff format --check .` | `ruff check .` | — |
| `javascript/library`, `javascript/component` | `npx prettier --check` (src/tests/config; library also covers `../test-support/`) | `npx eslint --max-warnings=0` (flat config, `@eslint/js` recommended) | `npm audit --audit-level=high` |
| repo-wide (`task check:shell`) | — | `shellcheck` over every tracked `*.sh` plus `bin/dx-worktree` | — |

Notes:

- **Tool provenance.** clippy/rustfmt come from the Nix Rust toolchain (`rust/flake.nix`); ruff and shellcheck come from the Nix dev shells (`python/flake.nix`, `test-harness/flake.nix`) because prebuilt manylinux wheels cannot execute on the FHS-less NixOS guest; prettier/eslint are locked npm devDependencies of each JavaScript package.
- **Generated code is exempt but must still pass.** `rust/component/src/bindings.rs` is regenerated by every build, so the build step itself runs `rustfmt` on it — `cargo fmt --check` passes even from a fresh `task clean && task build`. Python's `bindings/` and JavaScript's `transpiled/` are excluded from linting (gitignore-respecting ruff; explicit eslint/prettier ignore).
- **Shared JS test-support.** `javascript/test-support/` is a non-package directory; `javascript/library`'s lint covers it (its `eslint.config.js` re-exports the library's), and `javascript/component` does not re-lint it.
- **Network.** The `npm audit` gate queries the npm registry, so JavaScript `lint` is the one quality gate that needs network access; everything else lints offline.

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

## Component capability minimization

`javascript/component/lifecycle.sh` builds `task-component.wasm` with
`jco componentize ... -d all` and no `--enable` overrides: `-d all` disables
every optional WASI capability jco knows how to gate (clocks, random,
stdio, http, fetch-event). `taskCollections.countTasks` (`src/app.js`) is a
pure function that touches none of them. An earlier version of this build
passed `-d all --enable clocks --enable random --enable stdio`, which
re-enabled three capabilities the component never used, for no reason —
the component imported 16 `wasi:*` interfaces (cli, clocks, filesystem,
io, random) instead of zero, and was about 30 KB larger. Verified via
`wasmtime.component.Component(...).type.imports(engine)` against the real
built artifact (docs/refactoring-plan.md Phase 8):

| | imports | size (bytes) |
| --- | --- | --- |
| before (`-d all --enable clocks --enable random --enable stdio`) | 16 (`wasi:cli/*`, `wasi:clocks/*`, `wasi:filesystem/*`, `wasi:io/*`, `wasi:random/*`) | 11,576,710 |
| after (`-d all`, no enables) | 0 | 11,546,850 |

The Python and Rust components were not changed. Python's component already
imported nothing; Rust's imports 10 standard `wasi:cli`/`wasi:clocks`/
`wasi:filesystem`/`wasi:io` interfaces (the baseline `wasm32-wasip1` +
`cargo-component` adapter shape), all of which `wasmtime`'s
`Linker.add_wasip2()` provides. All three components now instantiate
against a plain WASIp2-only linker with no additional capabilities and no
retry — `test-harness/src/harness/invocation.py`'s narrower "define unknown
imports as traps" fallback (introduced in Phase 2 for a componentize-js
output that used to import `wasi:http`) was removed entirely once this was
confirmed for all three real components; see
`test-harness/tests/test_real_component_contracts.py`, which fails loudly
(not silently) if a component still needs an import the harness does not
provide, or if `.wasm` artifacts have not been built yet.
