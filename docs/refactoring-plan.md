# Repository Refactoring Plan

## Execution status (living handoff section)

Keep this section and the phase checkboxes current in every phase commit so
another agent can take over at any point.

- Branch: `refactor/harness-foundations`, branched from `main`.
- Working model: each phase is implemented by a subagent, then reviewed,
  independently re-verified, and committed as one reviewable change by the
  orchestrating session. Gates that must stay green after every phase:
  `task test`, `just test`, `task wasm:test`, `task contracts:check`,
  `task check:runners` (71 command-body warnings are pre-existing baseline,
  resolved in Phase 6).
- Phase 0 — DONE, commit `84def6c`. Baseline in `docs/baseline-phase0.md`.
  Pre-existing failures to fix in Phase 9: rustfmt drift (the rust/library
  instance was incidentally removed by Phase 3; rust/component remains),
  fast-uri high-severity npm audit finding in both JS packages.
- Phase 1 — DONE, commit `deb322e`. `test-harness/` is a locked uv project;
  the monolith is split into `src/harness/{models,wit,implementations,
  conversion,invocation,cli,runner_parity}.py`; `task coverage` enforces
  100% on `src/harness/`; entry shims `./run-wasm-tests.py`,
  `./check-runner-parity.py` keep their paths.
- Phase 2 — DONE, commit `1631c09`. Full WIT parsing (namespace, package,
  worlds, exports, function signatures, records); suites run only against
  exporting worlds; WIT-declared param order; recursive record conversion
  and return normalization; unknown-import fallback narrowed to wasmtime's
  "matching implementation was not found in the linker"; duplicate world
  names fail fast.
- Phase 3 — DONE, commit `2fce384`. `harness.contracts` central validator
  runs before any component invocation and via root
  `contracts:check`/`contracts-check`; suite-format schema at
  `common/schemas/test-suite.schema.json`; schemas carry repo-relative
  `$id`s resolved through a scan-built registry; u32 bounds on count-tasks
  returns; duplicated per-language schema-validation tests removed.
- Phase 4 — IN PROGRESS (subagent): `harness/fixtures.py` recursive
  `$fixture` resolver (gzip/utf-8, realpath containment under
  `common/fixtures/`, `HARNESS_FIXTURE_MAX_BYTES` default 8 MiB),
  resolution before validation and execution, `targets` semantics,
  New World HTML capture copied to
  `common/fixtures/html-parser/newworld-search-eggs.html.gz`. Note: the
  full "same case drives native and WASM" demo is deferred until an
  html-parser capability exists (the plan forbids starting the parser
  before items 1–4 are complete); the machinery is proven by the
  conformance suite plus a real-fixture integration test.
- Untracked files at repo root to leave alone: `parser-plan.md` and the raw
  `www.newworld.co.nz_...html` capture (original of the Phase 4 fixture).

## Goal

Make the repository safe to extend beyond the current `count-tasks` example,
with particular support for file-backed parsing contracts such as HTML
fixtures.

The refactoring must preserve these invariants:

- Contracts remain language-independent under `common/`.
- Python, JavaScript, and Rust components remain interchangeable at the WIT
  boundary.
- Components receive pure data and do not read fixture files themselves.
- Lifecycle commands remain reproducible and work through both Task and Just.
- Existing `count-tasks` behavior remains unchanged throughout.

## Scope

In scope:

- WASM harness structure, discovery, validation, and tests.
- File-backed fixture conventions and resolution.
- Task/Just lifecycle behavior and parity.
- Contract and schema validation.
- Build/test responsibility boundaries.
- Component capability minimization.
- Documentation and development quality gates.

Out of scope unless separately approved:

- Replacing WIT or JSON Schema with a different contract language.
- Removing either Task or Just.
- Combining the two Apple container implementations.
- Changing the observable `count-tasks` contract.

## Delivery principles

- Work in the phases below; do not batch all changes into one patch.
- Begin every behavioral change with a failing test.
- Keep `task test`, `just test`, and the existing WASM parity test green after
  each phase.
- Do not make fixture paths part of a component's business API.
- Do not silently skip a contract. Native-only execution must be declared
  explicitly.

## Phase 0 — Establish the baseline

- [x] Create a feature branch.
- [x] Record the output of:
  - [x] `task setup`
  - [x] `task test`
  - [x] `task wasm:test`
  - [x] `task coverage`
  - [x] `task check:runners`
- [x] Record existing non-lifecycle checks:
  - [x] All JSON files parse.
  - [x] All shell scripts pass `bash -n`.
  - [x] Rust passes `cargo clippy --all-targets -- -D warnings`.
  - [x] Record the existing Rust formatting failure before fixing it.
  - [x] Record current `npm audit` results.
- [x] Confirm the worktree contains no generated artifacts.

Done when the current behavior and pre-existing failures are documented.

## Phase 1 — Give the test harness real tests

The harness is central infrastructure, but its current test task only compiles
its Python files.

- [x] Add a locked Python project for `test-harness/` with pytest, PyYAML,
  coverage, and Wasmtime dependencies.
- [x] Replace `uv run --with ...` dependency resolution with locked
  dependencies.
- [x] Split `run-wasm-tests.py` into focused modules:
  - [x] Contract and suite models.
  - [x] WIT discovery.
  - [x] Implementation discovery.
  - [x] Fixture/value conversion.
  - [x] Component invocation.
  - [x] Reporting and CLI entry point.
- [x] Add unit tests for:
  - [x] No WIT worlds found.
  - [x] No suites found.
  - [x] No implementations found.
  - [x] Multiple WIT packages.
  - [x] Multiple worlds in one package.
  - [x] Interfaces exported by only one applicable world.
  - [x] Missing component artifacts.
  - [x] Missing interface and function exports.
  - [x] Instantiation and invocation failures.
  - [x] Nested lists, records, options, and result values.
  - [x] Structured component return values converted to plain JSON values.
- [x] Make `test-harness` coverage enforce the agreed threshold instead of
  aliasing `py_compile`. (Threshold: 100% on `src/harness/`.)

Done when a deliberate defect in discovery or value conversion causes
`test-harness` tests to fail.

## Phase 2 — Correct WIT and suite discovery

- [x] Replace hardcoded `common:tasks` namespace/package values with information
  discovered from each WIT package.
- [x] Parse, for each world:
  - [x] Namespace.
  - [x] Package name.
  - [x] World name.
  - [x] Exported interfaces.
- [x] Match each test suite only to worlds that export its interface.
- [x] Stop executing the Cartesian product of every suite and every world.
- [x] Use contract-declared parameter order instead of JSON object insertion
  order.
- [x] Make record conversion recursive.
- [x] Normalize component return values recursively before comparison.
- [x] Restrict unknown-import fallback to the specific missing-import failure
  it is intended to handle. (Matches wasmtime 43's "matching implementation
  was not found in the linker".)
- [x] Preserve a useful original exception when fallback instantiation also
  fails.
- [x] Detect duplicate world artifact names across packages.

Done when tests containing two packages, multiple worlds, and record-shaped
outputs execute only against their correct components.

## Phase 3 — Centralize contract validation

- [x] Define and validate a JSON Schema for the `*.test.json` suite format.
- [x] Check that:
  - [x] The suite's function name agrees with its filename.
  - [x] The interface agrees with its directory name.
  - [x] Every case has a unique, non-empty description.
  - [x] Every input validates against the function parameter schema.
  - [x] Every expected value validates against the return schema.
  - [x] Every referenced fixture exists. (Phase 3: existence + confinement
    under `common/fixtures/`; full resolution semantics land in Phase 4.)
- [x] Add `$id` values or a deterministic schema registry so `$ref` resolution
  does not require manually replacing nested schemas. (Both: `$id` = repo-
  relative path, resolved via a scan-built registry.)
- [x] Align JSON Schema with WIT numeric constraints.
  - [x] Add `minimum: 0` and `maximum: 4294967295` for `u32` results.
- [x] Add a conformance check for duplicate types represented in both WIT and
  JSON Schema, or document which representation is authoritative. (Both: WIT
  documented authoritative; entity schemas checked as exact field mirrors.)
- [x] Remove duplicated schema-validation tests from language implementations
  once the central validator covers them. (ajv left as an unused JS
  devDependency on purpose — dependency pruning is Phase 8/9.)
- [x] Add a root lifecycle command such as `task contracts:check` and its Just
  equivalent.

Done when malformed suites, missing fixtures, WIT/schema numeric drift, and
incorrect function paths fail before any component is invoked.

## Phase 4 — Add file-backed fixture support

### Directory convention

Use:

```text
common/
  fixtures/{capability}/
    example.html
    realistic-page.html.gz
  functions/{interface}/
    {function}.schema.json
    {function}.test.json
  wit/
    {package}.wit
```

### Contract boundary

The parser contract accepts file contents, not a file path:

```wit
parse-page: func(
    html: string,
    source-url: string,
) -> result<parse-result, parse-error>;
```

File reading, decompression, and text decoding belong to the host test
transport. The component remains pure.

### Fixture descriptor

Allow fixture descriptors anywhere in test input values:

```json
{
  "description": "extracts products from a captured page",
  "input": {
    "html": {
      "$fixture": "common/fixtures/html-parser/products.html.gz",
      "compression": "gzip",
      "encoding": "utf-8"
    },
    "source-url": "https://example.test/products"
  },
  "expected": {
    "products": []
  }
}
```

- [ ] Add a recursive fixture resolver to the harness.
- [ ] Resolve fixture descriptors before validating the materialized input.
- [ ] Support initially:
  - [ ] Plain text.
  - [ ] UTF-8 decoding.
  - [ ] Gzip decompression.
- [ ] Reject unsupported encodings and compression formats clearly.
- [ ] Resolve paths relative to the repository root.
- [ ] Require resolved paths to remain under `common/fixtures/`.
- [ ] Reject traversal and symlink escapes.
- [ ] Add configurable fixture-size limits to avoid accidental oversized
  inputs.
- [ ] Test missing, corrupt, non-UTF-8, traversal, and oversized fixtures.
- [ ] Document when HTML should be inline versus stored externally:
  - [ ] Small HTML fragments inline for focused behavior.
  - [ ] Captured pages as external compressed regression fixtures.
- [ ] Add explicit suite execution metadata where needed, for example:

  ```json
  { "targets": ["native", "component"] }
  ```

- [ ] Treat an unsupported target as a validation error, not an implicit skip.
- [ ] Add thin fixture adapters for native language tests only if they still
  need to execute independently of the central harness.
- [ ] Test all adapters against the same fixture-resolution conformance cases.

Done when one external HTML fixture drives the same native and WASM contract
case without exposing filesystem access to the parser.

## Phase 5 — Clarify build and test responsibilities

- [ ] Add a consistent `build` lifecycle verb at:
  - [ ] Root (missing today).
  - [ ] Each language root (missing today: `rust/`, `python/`, `javascript/`).
  - [ ] Each component (already present in `rust/component`, `python/component`,
    and `javascript/component`; keep these as-is).
- [ ] Make `wasm:test` either build required components or explicitly depend on
  `build`.
- [ ] Define the test ownership model:
  - [ ] Language tests cover pure implementation logic and thin binding
    adapters.
  - [ ] The central harness owns black-box WASM contract parity.
- [ ] Remove redundant per-language low-level Wasmtime tests only after the
  central harness provides equivalent coverage.
- [ ] Remove unnecessary Rust Wasmtime development dependencies if integration
  testing moves fully to the harness.
- [ ] Align any remaining Wasmtime versions.
- [ ] Make root `test` run the contract validator and unified parity test after
  component builds.

Done when `task test` from a clean checkout cannot accidentally omit unified
contract parity, and `task wasm:test` does not depend on undocumented prior
commands.

## Phase 6 — Make Task and Just behavior genuinely equivalent

- [ ] Decide on one canonical representation for lifecycle behavior:
  - [ ] Preferred: shared scripts or a declarative lifecycle manifest invoked
    by both runners.
  - [ ] Alternative: enhance parity parsing until normalized command semantics
    can be compared reliably.
- [ ] Preserve public Task and Just recipe names.
- [ ] Eliminate the current command-body warning backlog.
- [ ] Add parity tests for:
  - [ ] Commands.
  - [ ] Environment variables.
  - [ ] Working directories.
  - [ ] Dependencies.
  - [ ] Cleanup paths.
  - [ ] Failure propagation.
- [ ] Resolve Task/Just differences in `.harness` cleanup.
- [ ] Add tests that execute both runners against a temporary fixture project.
- [ ] Reduce the root Taskfile and Justfile container-command matrix using
  parameterized shared scripts while preserving the existing CLI aliases.

Done when a command or environment difference between Task and Just fails CI
instead of producing a warning.

## Phase 7 — Repair lifecycle state ownership

- [ ] Define `HARNESS_DIR` once at each language root.
- [ ] Derive and export:
  - [ ] `HARNESS_CACHE_DIR`.
  - [ ] `HARNESS_OUTPUT_DIR`.
  - [ ] `UV_CACHE_DIR`.
  - [ ] `CARGO_TARGET_DIR` where appropriate.
- [ ] Stop child projects from independently defaulting to `.cache/uv`.
- [ ] Ensure:
  - [ ] `clean` removes outputs but keeps caches and installed dependencies.
  - [ ] `purge` removes all repository-owned outputs, caches, and installed
    dependencies.
- [ ] Add lifecycle tests that snapshot ignored state before and after `clean`
  and `purge`.
- [ ] Make README lifecycle documentation match tested behavior.

Done when no repository-owned `.cache/uv`, `.venv`, `node_modules`, target,
binding, transpiled, or WASM artifacts survive `purge`.

## Phase 8 — Minimize component capabilities and build cost

- [ ] Determine which JCO flags are actually required by each JavaScript
  component.
- [ ] Remove clocks, randomness, stdio, and broad `-d all` capability exposure
  from pure components where possible.
- [ ] Record component sizes before and after the change.
- [ ] Assert required imports/exports in harness tests.
- [ ] Confirm unknown-import trap fallback is no longer needed, or narrow it to
  an explicitly documented compatibility case.
- [ ] Change the Rust Nix toolchain from the default profile to a minimal
  profile with only required extensions.
- [ ] Split heavyweight JavaScript browser/FHS tooling from lighter workflows
  if this can be done without weakening reproducibility.

Done when component imports reflect actual needs and setup/build costs are
measurably reduced.

## Phase 9 — Restore enforceable quality gates

- [ ] Add formatter checks:
  - [ ] Rust `cargo fmt --check`.
  - [ ] Python formatter.
  - [ ] JavaScript formatter.
- [ ] Add lint checks:
  - [ ] Rust Clippy with warnings denied.
  - [ ] Python linting and, if useful, type checking.
  - [ ] JavaScript linting.
  - [ ] ShellCheck for shell scripts.
- [ ] Fix the existing Rust formatting failure.
- [ ] Implement the `update` lifecycle verb that `constitution.md` §4 already
  requires ("Explicitly upgrades locked dependencies and regenerates
  lockfiles"). No `update` task/recipe currently exists at root, any language
  root, or `test-harness/`. Either add it everywhere or explicitly amend the
  constitution to drop it — do not leave the documented verb unimplemented.
- [ ] Update the transitive vulnerable `fast-uri` dependency (currently
  <=3.1.1 in both `javascript/component/package-lock.json` and
  `javascript/library/package-lock.json`, flagged high severity by
  `npm audit`) through supported parent dependency updates.
- [ ] Decide whether mutation testing, AST purity analysis, and complexity
  limits remain requirements.
  - [ ] Implement them if they remain required.
  - [ ] Remove or soften the constitutional claims if they are aspirational.
- [ ] Wire quality checks into both Task and Just.

Done when the quality claims in `constitution.md` correspond to commands that
are executed in CI.

## Phase 10 — Container and worktree safety

- [ ] Decide whether container suites are fail-fast or failure-collecting.
- [ ] Align behavior with the documented policy.
- [ ] Do not run `test` or `coverage` after a failed setup unless explicitly in
  diagnostic mode.
- [ ] Keep the two container solutions separate unless the existing
  duplication policy is intentionally revised.
- [ ] If shared code is approved, extract only low-level, base-image-neutral
  operations and keep separate public entry scripts.
- [ ] Change `bin/dx-worktree destroy` to use safe branch deletion by default.
- [ ] Add an explicit `--force` option for deleting unmerged branches.
- [ ] Add cleanup for partially created worktrees when sparse-checkout setup
  fails.
- [ ] Validate sparse paths by path segments rather than rejecting every name
  containing `..`.

Done when routine cleanup cannot silently discard unmerged commits and
container failure behavior is unambiguous.

## Phase 11 — Documentation cleanup

- [ ] Move the existing root `plan.md` to an explicitly historical location or
  mark it as archived.
- [ ] Do the same for root `todo.txt`: every item in it is already checked
  off and it documents a completed, separate effort (the NixOS 25.11
  container base). Archive it alongside `plan.md` rather than leaving two
  stale root-level planning documents for a contributor to sort through.
- [ ] Remove stale absolute repository paths and references to absent policy
  files.
- [ ] Convert durable architectural decisions into short ADRs:
  - [ ] Shared WIT as the component authority.
  - [ ] Native versus component implementation boundaries.
  - [ ] File fixture transport.
  - [ ] Task/Just parity strategy.
  - [ ] Separate container implementations.
- [ ] Expand README with:
  - [ ] Architecture overview.
  - [ ] Adding a new capability.
  - [ ] Adding a file-backed parsing test.
  - [ ] Build/test lifecycle.
  - [ ] Native-only versus component execution criteria.
- [ ] Reconcile documented lifecycle verbs, directory roles, WASI target, and
  actual tooling.

Done when a contributor can add a new HTML parsing capability without relying
on historical handoff documents.

## Recommended delivery sequence

Deliver as small reviewable changes, one per phase:

1. Harness project plus behavioral tests. (Phase 1)
2. Multi-package/world discovery correction. (Phase 2)
3. Central suite/schema validation. (Phase 3)
4. Fixture descriptor and HTML resolver. (Phase 4)
5. Build/test ownership cleanup. (Phase 5)
6. Canonical lifecycle implementation and runner parity. (Phase 6)
7. Cache/output ownership. (Phase 7)
8. Component capability and dependency reduction. (Phase 8)
9. Quality gates. (Phase 9)
10. Container/worktree safety. (Phase 10)
11. Documentation cleanup. (Phase 11)

Do not begin a real HTML parser implementation before items 1–4 are complete;
otherwise the parser will be built on conventions that are already known to
need replacement.

## Final definition of done

- [ ] Multiple WIT packages and worlds are discovered and matched correctly.
- [ ] Harness behavior is covered by real tests.
- [ ] Every contract suite and fixture is centrally validated.
- [ ] Plain and gzip HTML fixtures can drive native and WASM tests.
- [ ] Components receive decoded HTML strings, not filesystem paths.
- [ ] Native-only execution is explicit.
- [ ] Task and Just execute equivalent commands and environments.
- [ ] `clean` and `purge` have tested, documented state semantics.
- [ ] JavaScript component capabilities are minimized.
- [ ] Formatting, linting, tests, coverage, contract checks, parity, and
  dependency audit gates pass.
- [ ] `task test`, `just test`, `task coverage`, `just coverage`,
  `task wasm:test`, and `just wasm-test` pass from a clean checkout.
- [ ] Container suite setup failures do not silently proceed to `test` or
  `coverage`, and the fail-fast-versus-failure-collecting policy is
  documented and matches actual behavior.
- [ ] `bin/dx-worktree destroy` defaults to safe (non-force) branch deletion,
  with an explicit opt-in for deleting unmerged branches.
- [ ] Durable architectural decisions are captured as ADRs, and the README
  matches tested lifecycle behavior rather than historical handoff notes.
- [ ] The `update` lifecycle verb required by `constitution.md` §4 either
  exists everywhere `setup`/`test`/`coverage`/`clean`/`purge` do, or the
  constitution has been explicitly amended to remove it.
- [ ] The final worktree contains no generated artifacts.
