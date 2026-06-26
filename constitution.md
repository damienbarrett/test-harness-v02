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
- **Strict Directory Roles** (enforced via sandbox/permissions where possible):
  - `src/`: Read-only during lifecycle execution. Only source code committed to Git.
  - `build/`: Transitory compilation files.
  - `cache/`: Downloaded external dependencies.
  - `dist/`: Compiled, ready-to-use artifacts.
  - `log/`: Output for observability and agent feedback.

## 4. Lifecycle Verbs & Orchestration
Orchestration is handled by a lightweight runner (e.g., `Task` or `Just`). Every layer exposes the exact same verbs.
- `setup`: Idempotent environment initialization. Safe to run repeatedly.
- `test`: Validates the implementation against the contracts.
- `coverage`: Generates code coverage metrics.
- `clean`: Removes generated outputs (`build/`, `dist/`).
- `purge`: Destructive removal of `cache/` and environment setups.
- `update`: Explicitly upgrades locked dependencies and regenerates lockfiles.
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
- Target the latest WASI (e.g., Preview 3 / Component Model).
- WASM modules should comprise pure functions.
- Implementations must be validated in both client-side (in-browser) and server-side (`wasmtime`) hosts.

## 8. Enforcing Non-Functional Constraints
To ensure a robust codebase before runtime, the pipeline leverages:
- Strict linting and formatting (no warnings permitted).
- Abstract Syntax Tree (AST) analysis to enforce pure functions where mandated.
- Mutation testing to validate the integrity of 100% code coverage.
- Cyclomatic complexity limits to ensure maintainability.
