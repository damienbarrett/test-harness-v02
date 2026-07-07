# Agentic Coding Constitution

This document defines the strict, opinionated framework for application development in this repository. It prioritizes extreme reproducibility, contract-driven architecture, and deterministic agentic workflows.

## 1. Architectural Philosophy
- **Extreme Reproducibility**: The environment, code, and test results must be identical regardless of whether they run on an M1 Mac, a Raspberry Pi, or an AI Cloud environment.
- **Contract-Driven Design**: The system is built "model-first." Agnostic contracts (Schemas, requirements, tests) dictate the implementation, not the other way around.
- **Polyglot Parity via Swappable Components**: A capability is defined once as a language-agnostic WIT contract living in `common/`. Every language compiles its implementation to a WebAssembly component that satisfies that exact contract, so any implementation is hot-swappable for another and the calling host cannot tell which language produced it. A single black-box suite proves all implementations equivalent.
- **Agent as a Bounded Function**: AI agents operate within strict guardrails. They receive clear contracts, execute isolated tasks, and rely on deterministic lifecycle feedback rather than ad-hoc exploration.

## 2. Environment & Infrastructure
- **Strict Layer Isolation**:
  - **Host**: Hardware and base OS. Provides only a shell and a container runtime.
  - **Container**: The runtime boundary (e.g., Apple `container`, Docker). Protects the host from filesystem drift.
  - **Guest OS (Nix)**: Nix manages all OS-level capabilities, shared libraries, and CLI tooling inside the container. It defines the guest contract.
  - **Language Tooling**: Native package managers (`uv`, `npm`, `cargo`) own all language-specific dependencies. Nix does *not* replace them.
- **No Host-Container Filesystem Crossing**: To ensure state resiliency and performance, repositories and credentials live within the guest filesystem.
- **Offline Capability**: After the initial `setup` and dependency caching, all subsequent builds and tests must execute successfully without network access.

## 3. Repository Topology
The project operates as a **Monorepo** to enable atomic commits across contracts and implementations.
- `common/`: The language-agnostic source of truth. Contains JSON schemas, WIT definitions, test fixtures, and requirements. Does not contain executable lifecycles.
- `sub-repos/` (e.g., `rust/`, `javascript/`, `python/`): The implementation directories. These have no visibility into each other, only into `common/`.
- **Strict Directory Roles** (state ownership by purpose, not a literal
  `src/`/`build/`/`cache/`/`dist/`/`log/` folder set -- see `README.md`
  "State ownership: the `HARNESS_*` variables" for the full per-directory
  table):
  - **Source**: tracked files committed to Git. Read-only during lifecycle
    execution.
  - **Cache** (`$HARNESS_CACHE_DIR`, default `<dir>/.harness/cache`):
    downloaded external dependencies and build caches (e.g. the shared `uv`
    cache, Cargo's target directory). Survives `clean`; removed only by
    `purge`.
  - **Outputs** (`$HARNESS_OUTPUT_DIR`, default `<dir>/.harness/outputs`):
    compiled artifacts, generated bindings/transpiled code, and coverage
    reports. Removed by both `clean` and `purge`.
  - Each of `python/`, `javascript/`, `rust/`, and `test-harness/` derives
    `HARNESS_DIR` (and the cache/output directories under it) exactly once,
    in that directory's own `lifecycle.sh`; observability output is the
    lifecycle command's own stdout/stderr (§5), not a separate `log/`
    directory.

## 4. Lifecycle Verbs & Orchestration
Orchestration is handled by a lightweight runner (e.g., `Task` or `Just`). Every layer exposes the exact same verbs.
- `setup`: Idempotent environment initialization. Safe to run repeatedly.
- `build`: Compiles each language's WASM component(s). Safe to run repeatedly; nothing else in the lifecycle assumes a build artifact already exists.
- `test`: Validates the implementation against the contracts.
- `lint`: Runs the directory's formatter and linter checks with warnings denied (see §8) so no test run can pass with a formatting, lint, audit, or shellcheck violation.
- `coverage`: Generates code coverage metrics.
- `clean`: Removes generated outputs (compiled artifacts, generated bindings/transpiled code, coverage reports -- the "Outputs" role in §3).
- `purge`: Destructive removal of caches, environment setups, and installed dependencies (the "Cache" role in §3, plus `.venv`/`node_modules`/build-tool target directories).
- `update`: Explicitly upgrades locked dependencies and regenerates lockfiles; the only verb (besides `setup`) expected to need network access, and the only one allowed to change a lockfile.
**Rule**: If any sub-layer fails, the orchestrator exits non-zero immediately. No silent partial successes.

## 5. Agentic Behavior & Feedback Loops
- **Feedback via Lifecycles**: Agents must rely on standard lifecycle commands (e.g., `test`, `build`) and parse standard output/logs for feedback. Arbitrary shell commands are by exception only.
- **Context Minimization**: Agents execute small, bounded loops, ideally editing only a single file per run to avoid context bloat.
- **Planning First**: Architectural planning and definition of done must be completed before writing implementation code.
- **Test-First Platform Changes**: Any modification to platform orchestration or environments must begin with a failing test.

## 6. The Development Lifecycle Phases
1. **Functional Requirements**: Written in plain English Markdown (`requirements.md`). Strictly sectioned into Goal, Scope (In/Out), Inputs, and Outputs.
2. **Data Schemas**: Model-first JSON Schema definitions. No logic. Uses `UUIDv7` created at the application layer (`WITHOUT ROWID` in SQLite).
3. **Contracts**: Language-agnostic definitions (WIT / Smithy / TypeSpec) capable of compiling bindings for all target languages.
   - **Single source of truth**: each capability's interface is declared exactly once — one `package <ns>:<name>;` with its `world`(s) — under `common/wit/`. Interfaces and worlds are never redefined or forked per language.
   - **One component per world, per language**: every implementation compiles a WebAssembly component against that same WIT and emits it at a stable, predictable path (`<lang>/component/<world>.wasm`). The host and the test harness discover components by world name, so artifacts are interchangeable — swap one language's `.wasm` for another's and observable behaviour is identical.
   - **Components stay pure and self-contained**: a component carries only the logic required to satisfy its world and avoids heavyweight host libraries that compromise WASM portability. Rich, dependency-heavy variants of the same logic belong in the language `library/` layer, never in the component.
4. **Tests**: Purely declarative JSON files defining input/expected output. Run via a black-box test harness against the implementation (WASM or REST).

## 7. Language-Specific Constraints
### Universal
- **TDD & Coverage**: Red ➔ Green ➔ Refactor workflow aiming for 100% test coverage.
- **Functional Core**: Business logic must reside in pure functions. I/O and side-effects are pushed to the absolute edges.
- **Domain Types**: In statically typed languages, wrap primitives in domain-specific types (e.g., `UserId`, `Money`) with validation occurring in the constructor.

### JavaScript
- Modern ECMAScript (2027+) only.
- **No build or transpilation step**.
- Isomorphic: Must use ECMAScript modules (ESM) to run interchangeably on client-side (tested via Playwright) and server-side (tested via Node/Bun/Deno).
- Prefer native APIs over external libraries.

### Python
- Package management and testing strictly via `uv`.
- Do not use `pip` or `venv`.
- Code structured as a proper package using `pyproject.toml`.

### WebAssembly (WASM)
- **Target, as actually built** (amended -- see `docs/refactoring-plan.md`
  Phase 8/9): each language's build toolchain (`componentize-py`,
  `jco componentize`, `cargo-component` -- the latter explicitly targeting
  `wasm32-wasip1`, per `rust/flake.nix`) produces a Component Model `.wasm`
  artifact, and the server-side host instantiates every one of them through
  a single plain WASI Preview 2 linker (`wasmtime` 43's
  `linker.add_wasip2()`, see `test-harness/src/harness/invocation.py`) with
  no fallback or retry -- an import that linker does not provide is a
  contract violation, not a compatibility case to patch around. There is no
  Preview 3 usage anywhere in the toolchain today; treat this paragraph, not
  the phrase "latest WASI," as authoritative until the toolchain changes.
- WASM modules should comprise pure functions.
- Implementations must be validated in both client-side (in-browser) and server-side (`wasmtime`) hosts.

## 8. Enforcing Non-Functional Constraints
To ensure a robust codebase before runtime, the pipeline enforces:
- Strict linting and formatting (no warnings permitted). Every implementation directory exposes a `lint` verb — `cargo fmt --check` + `cargo clippy -D warnings` (Rust), `ruff format --check` + `ruff check` (Python), `prettier --check` + `eslint --max-warnings=0` + `npm audit --audit-level=high` (JavaScript), and repo-wide ShellCheck — and the root `test` verb runs the aggregated `lint` before any test executes.

**Aspirational (not yet enforced)**: the following remain stated goals, but each requires dedicated per-language tooling that has not been selected and is not wired into any lifecycle verb; no current gate runs them.
- Abstract Syntax Tree (AST) analysis to enforce pure functions where mandated.
- Mutation testing to validate the integrity of 100% code coverage.
- Cyclomatic complexity limits to ensure maintainability.
