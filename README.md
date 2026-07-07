# Getting started

Clone the project:

```bash
git clone https://github.com/damienbarrett/test-harness-v02
```

This is a monorepo. `common/`, `python/`, `javascript/`, `rust/`, and
`test-harness/` are normal tracked directories.

## Architecture overview

- **`common/`** is the language-agnostic contract authority. It holds WIT
  interface/world declarations (`wit/`), JSON Schema mirrors of WIT records
  (`entities/`), per-function schema + declarative test suites
  (`functions/{interface}/`), file-backed test fixtures (`fixtures/`), and
  the suite-format schema plus `$id` registry conventions (`schemas/`).
  `common/` does not expose any lifecycle commands (`constitution.md` §3) --
  see [`common/README.md`](common/README.md) for the full contract format.
- **Language sub-repos** (`python/`, `javascript/`, `rust/`) each have no
  visibility into one another, only into `common/`. Each has two layers:
  `library/` (rich, dependency-using native logic with native tests) and
  `component/` (a thin wrapper that satisfies a WIT world and compiles to
  `{lang}/component/{world}.wasm`). See
  [`docs/adr/0002-native-vs-component-boundaries.md`](docs/adr/0002-native-vs-component-boundaries.md).
- **`test-harness/`** is the black-box WASM contract-parity runner. It
  discovers implementations by scanning for `*/component/` directories,
  parses `common/wit/*.wit` for packages/worlds/exports, matches every
  `common/functions/**/*.test.json` suite to the world(s) that export its
  interface, and asserts that every language's compiled component produces
  identical observable behavior via `wasmtime`.
- **`container/`** holds two independent Apple `container` solutions (a
  Codex-universal-based image and a NixOS 25.11 based image) for running the
  whole lifecycle reproducibly on Apple silicon hosts. See
  [`container/README.md`](container/README.md) and
  [`docs/adr/0005-separate-container-implementations.md`](docs/adr/0005-separate-container-implementations.md).
- **`bin/`** holds `dx-worktree`, the sparse-worktree tool used for isolated
  agent sessions (see "Sparse worktrees" below and
  [`docs/worktrees.md`](docs/worktrees.md)).

### The WIT → component flow

A capability's interface is declared exactly once, under `common/wit/`, as
one `package <ns>:<name>;` with its `world`(s)
([`docs/adr/0001-shared-wit-component-authority.md`](docs/adr/0001-shared-wit-component-authority.md)).
Every language compiles its own implementation against that same WIT file
and emits a component at the fixed path `{lang}/component/{world}.wasm`.
Nothing about that path or the WIT is language-specific, so the harness
(and, conceptually, any host) can swap one language's `.wasm` for another's
without any observable difference:

```text
common/                              contract authority — no lifecycle
├── wit/{package}.wit                interfaces + worlds (single source of truth)
├── entities/*.json                  JSON Schema mirrors of WIT records
├── functions/{interface}/           {function}.schema.json + {function}.test.json
├── fixtures/{capability}/           file-backed fixtures ($fixture descriptors)
└── schemas/                         suite-format schema + $id registry
        │
        │  every language builds against the same common/wit/*.wit
        ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ python/          │   │ javascript/      │   │ rust/            │
│  library/  rich, │   │  library/  rich, │   │  library/  rich, │
│   native tests   │   │   native tests   │   │   native tests   │
│  component/ thin │   │  component/ thin │   │  component/ thin │
│  WIT wrapper  -> │   │  WIT wrapper  -> │   │  WIT wrapper  -> │
│  {world}.wasm    │   │  {world}.wasm    │   │  {world}.wasm    │
└──────────────────┘   └──────────────────┘   └──────────────────┘
        │                     │                     │
        └──────────────┬──────┴──────────────┬──────┘
                        ▼                     ▼
                  test-harness/ (black-box WASM contract parity)
                  discovers {lang}/component/{world}.wasm by convention,
                  matches common/functions/**/*.test.json to the world(s)
                  exporting each suite's interface, and asserts identical
                  behavior across every language's compiled component.
```

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

## Adding a new capability

A "capability" is one WIT interface plus its function contracts. To add one
(say, an `html-parser` interface with a `parse-page` function):

1. **Write the WIT package** under `common/wit/` -- either a new file or a
   new interface/world in an existing one. Declare the interface, its
   record types, and its function signature, then a `world` that exports
   the interface:

   ```wit
   package common:html-parser;

   interface parsing {
       record parse-result {
           products: list<string>,
       }

       parse-page: func(html: string, source-url: string) -> parse-result;
   }

   world html-parser-component {
       export parsing;
   }
   ```

   This is the single source of truth -- never redefine the interface per
   language (`docs/adr/0001-shared-wit-component-authority.md`).
2. **Add JSON Schema entity mirrors if the WIT declares shared records** that
   need JSON-Schema-based validation, under `common/entities/`. Keep the
   fields identical to the WIT record; `harness.contracts`'s
   record-conformance check fails `contracts:check` if they drift, and the
   WIT declaration always wins (`common/README.md`, "Contract validation and
   WIT-as-authority").
3. **Add the function schema and test suite** at
   `common/functions/{interface}/{function}.schema.json` and
   `common/functions/{interface}/{function}.test.json` -- directory name =
   WIT interface name, file stem = WIT function name, both kebab-case (see
   `common/README.md`, "Naming convention"). Give the schema file's `$id`
   its repo-relative path so `$ref`s resolve automatically.
4. **Implement the capability per language**:
   - `{lang}/library/`: the rich, dependency-using implementation, tested
     natively.
   - `{lang}/component/`: a thin wrapper containing only the logic needed to
     satisfy the WIT world -- no heavyweight host libraries -- built to
     `{lang}/component/{world-name}.wasm` via that language's existing build
     step (`componentize-py`, `jco componentize`, or `cargo-component`).
5. **Build and discovery are automatic.** `task build` (root or per
   language) produces the `.wasm` at the conventional path; nothing needs to
   register the new capability anywhere else.
   `test-harness/src/harness/implementations.py` discovers any top-level
   directory with a `component/` subdirectory, and
   `test-harness/src/harness/wit.py` discovers packages/worlds/exports
   straight from `common/wit/*.wit` -- a suite runs only against the
   world(s) that export its interface.
6. **Gates that must pass** before the capability is done: `task
   contracts:check` (suite/schema/WIT validation, before any component
   runs), each language's `task lint`/`task test`, `task wasm:test`
   (black-box parity across all three languages), and `task check:runners`
   if you touched any lifecycle file. `task test` at the repo root runs all
   of these in the right order (see "Lifecycle" below).

## Adding a file-backed parsing test

Use this when a test case's input is a realistic captured page rather than a
small inline fragment -- see
[`docs/adr/0003-file-fixture-transport.md`](docs/adr/0003-file-fixture-transport.md)
for the design rationale. The repository already has a real example fixture
for this, captured for the future `html-parser` capability discussed above:
[`common/fixtures/html-parser/newworld-search-eggs.html.gz`](common/fixtures/html-parser/README.md)
(139,258 bytes gzipped, from a 592,574-byte capture of a `newworld.co.nz`
shop-search results page).

1. **Capture and compress the page** into
   `common/fixtures/{capability}/{name}.html.gz` (gzip only; only the
   compressed file is committed). Record its provenance -- source URL,
   capture date, raw/gzipped sizes -- in that capability's
   `common/fixtures/{capability}/README.md`, following the format in
   [`common/fixtures/html-parser/README.md`](common/fixtures/html-parser/README.md).
2. **Reference it from a test case** with a `$fixture` descriptor anywhere
   inside that case's `input`:

   ```json
   {
     "description": "extracts products from a captured search-results page",
     "input": {
       "html": {
         "$fixture": "common/fixtures/html-parser/newworld-search-eggs.html.gz",
         "compression": "gzip",
         "encoding": "utf-8"
       },
       "source-url": "https://www.newworld.co.nz/shop/search?pg=1&q=size%207%20eggs&sf=products"
     },
     "expected": { "products": [] }
   }
   ```

3. **That's the whole contract.** `test-harness/src/harness/fixtures.py`
   resolves the descriptor to the decoded UTF-8 file contents before
   `contracts:check` validates the case's input and before the harness
   builds the component call -- the component itself only ever receives a
   decoded string, never a path. Resolution enforces realpath containment
   under `common/fixtures/`, an 8 MiB default size limit
   (`HARNESS_FIXTURE_MAX_BYTES` to override), and rejects anything malformed
   (missing file, corrupt gzip, non-UTF-8 bytes, traversal/symlink escape,
   unknown descriptor key) as a `contracts:check` failure naming the
   fixture.
4. **Inline versus external is a judgment call already documented in
   [`common/README.md`](common/README.md#inline-vs-external-html)**: small,
   focused HTML fragments belong inline in a case's `input`; realistic
   captured pages belong under `common/fixtures/` as external gzipped
   regression fixtures like the one above.

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

### Root-only verbs

A handful of verbs only make sense at the repo root, since they operate
across every language rather than within one:

| Verb | Purpose |
| --- | --- |
| `task wasm:test` / `just wasm-test` | Runs the central harness's black-box WASM contract-parity suite across every language's built component. Depends on `build`. |
| `task contracts:check` / `just contracts-check` | Validates every `common/functions/**/*.test.json` suite (schema, WIT agreement, fixture resolution) before any component is built or invoked. |
| `task check:runners` / `just check-runners` | Checks every `Taskfile.yml`/`justfile` pair for parity (recipe names, dependencies, command bodies); fails on drift. |
| `task check:lifecycle` / `just check-lifecycle` | On-demand, destructive-then-restoring verification that `clean`/`purge` remove exactly the state they claim to (not part of `test`; needs network afterward to restore via `setup`+`build`). |

Root `task test` composes, in order: `contracts:check`, then `lint`, then
every language's and the harness's own test suite, then `wasm:test` -- so a
passing `task test` run already proves contract validity, formatting/lint
cleanliness, native test coverage, and WASM parity together (see "Quality
gates" below for what `lint` covers).

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

## Native-only versus component execution criteria

By default, a test suite in `common/functions/{interface}/{function}.test.json`
runs everywhere it can: natively (per the "Test ownership model" above) and,
if a world exports its interface, against every language's WASM component
via `task wasm:test`. An optional suite-level `targets` array narrows that:

```json
{ "function": "count-tasks", "targets": ["native", "component"], "tests": [] }
```

- **Absent `targets`** = no restriction (the normal case).
- If present, it must be non-empty, contain no duplicates, and every entry
  must be `"native"` or `"component"`. An unrecognized value is a
  `contracts:check` **validation error**, never a silently ignored typo.
- A suite whose `targets` excludes `"component"` is not run against WASM
  components at all: the harness prints an explicit
  `SKIP (declared native-only): <suite>` line and counts the suite as
  neither pass nor fail. Native-only execution is always this kind of
  visible declaration -- never an implicit, undocumented omission (see
  `common/README.md`, "`targets` execution metadata").

**When to declare a suite native-only:** only when the function genuinely
cannot run as a portable WASM component -- for example, it depends on a
capability deliberately kept out of the component layer (constitution.md
§6.3: components "avoid heavyweight host libraries that compromise WASM
portability"), such as a rich native parser dependency, real filesystem or
network access, or any other library that would trap or bloat inside WASM
(see `docs/adr/0002-native-vs-component-boundaries.md`). It is not a
shortcut for "the component isn't implemented yet" -- an unimplemented
component is a missing artifact and a loud build/test failure, not a
`targets` declaration.

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

## Architectural decision records

Durable architectural decisions live as short ADRs under
[`docs/adr/`](docs/adr/):

- [`0001-shared-wit-component-authority.md`](docs/adr/0001-shared-wit-component-authority.md)
  -- shared WIT under `common/` as the single component authority.
- [`0002-native-vs-component-boundaries.md`](docs/adr/0002-native-vs-component-boundaries.md)
  -- native versus component implementation boundaries.
- [`0003-file-fixture-transport.md`](docs/adr/0003-file-fixture-transport.md)
  -- file fixture transport (`$fixture` descriptors).
- [`0004-task-just-parity-strategy.md`](docs/adr/0004-task-just-parity-strategy.md)
  -- Task/Just parity strategy.
- [`0005-separate-container-implementations.md`](docs/adr/0005-separate-container-implementations.md)
  -- separate container implementations.

`docs/refactoring-plan.md` remains the phase-by-phase execution history that
produced the current design; the ADRs above are the durable "why," extracted
from that handoff document so a contributor does not need to read historical
phase notes to understand the current architecture.
