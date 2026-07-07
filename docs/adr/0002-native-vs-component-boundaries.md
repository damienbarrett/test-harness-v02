# 0002. Native Versus Component Implementation Boundaries

Date: 2026-07-07

Status: accepted

## Context

Constitution.md §6.3 requires components to "stay pure and self-contained"
and avoid heavyweight host libraries, while §7 (WASM) separately requires
validation in both a client-side (in-browser) and server-side (`wasmtime`)
host. In practice, some parsing/business logic is naturally rich and
dependency-heavy (e.g. a future HTML parser might want a full DOM library),
which is exactly the kind of code that traps or bloats inside a WASM
component. The repository already has two directories per language --
`{lang}/library/` and `{lang}/component/` -- and a documented test-ownership
split (root `README.md`, "Test ownership model"): the central harness
(`test-harness/`, via `wasm:test`/`wasm-test`) is the one place a
server-side `wasmtime` contract-parity case exists, while each language's
in-browser/transpiled validation stays separate. Today only JavaScript has
any client-side coverage at all: `javascript/library/tests/browser.test.js`
(Playwright, isomorphic library code) and
`javascript/component/tests/wasm-count-tasks.test.js` (the actual compiled
component through `jco`'s transpiled output in Node) -- a genuinely
different host from the harness's `wasmtime`, so it was kept rather than
removed as a duplicate when Phase 5 pruned redundant per-language wasmtime
tests.

## Decision

Split every language into two layers with different rules. `{lang}/library/`
holds rich, dependency-using logic and is tested entirely natively (no WASM
involved) -- library code may depend on whatever it needs. `{lang}/component/`
holds only the minimal code required to satisfy its WIT world and compiles
to `<lang>/component/<world>.wasm`; it must stay self-contained and avoid
heavyweight host libraries that compromise portability (Phase 8 verified this
concretely: the JavaScript component's WASI imports were reduced from 16 to
0, and Rust's/Python's components import nothing beyond the standard
`wasip1`-adapter shape). The central harness is the single owner of
black-box, server-side WASM contract parity across all three languages;
language test suites must not re-implement that fact. In-browser validation
remains each language's own responsibility, since the harness only exercises
the server-side `wasmtime` host and can therefore never be the sole source of
WASM contract confidence.

## Consequences

- Component code stays small and portable by construction; any accumulation
  of real business logic inside `component/` (rather than thin WIT plumbing)
  is a boundary violation to fix, not a pattern to extend.
- Redundant low-level per-language `wasmtime` tests were removed once the
  central harness proved equivalent coverage (Phase 5, rust/component and
  python/component); JavaScript's `jco`/Node component test was kept because
  it is a different host, not a duplicate.
- No language currently runs its compiled `.wasm` component inside a real
  browser -- only JavaScript's library layer gets Playwright coverage. That
  gap is documented as out of scope rather than silently absent.
- Adding a capability requires a per-language judgment call: the library
  implementation can use rich dependencies freely, but the component
  wrapper for the same capability must be re-justified as pure WIT plumbing.
