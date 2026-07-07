# 0001. Shared WIT Under `common/` as the Single Component Authority

Date: 2026-07-07

Status: accepted

## Context

Every capability in this repository must stay language-independent, and
Python, JavaScript, and Rust implementations must remain interchangeable at
the WIT boundary (constitution.md §1, §6). Today `common/wit/tasks.wit`
declares exactly one package, `common:tasks`, with one interface
(`task-collections`) and one world (`task-component`) that exports it. Each
language compiles its own component against that same file and the test
harness discovers artifacts purely by convention: any top-level directory
containing a `component/` subdirectory is a language
(`test-harness/src/harness/implementations.py`), and each world's `.wasm` is
expected at exactly `{lang}/component/{world}.wasm`
(`test-harness/src/harness/cli.py`). A JSON Schema entity file
(`common/entities/task-schema.json`) also exists to describe the same record
shape for JSON-Schema-based tooling (suite validation), which raises the
question of which representation is authoritative when the two could drift.

## Decision

Declare each capability's interface exactly once under `common/wit/` as one
`package <ns>:<name>;` with its `world`(s) -- interfaces and worlds are never
redefined or forked per language. Every language implementation compiles a
WebAssembly component against that exact WIT and emits it at the fixed,
predictable path `<lang>/component/<world>.wasm`; the harness discovers
implementations and their artifacts by that convention alone, so swapping one
language's compiled component for another's is a file-path substitution, not
a code change. Where a JSON Schema entity also has to describe the same
shape (for schema-based suite validation), that schema is an enforced
mirror, not a second source of truth: WIT is authoritative, and
`harness.contracts`'s record-conformance check fails `contracts:check` if an
entity schema's fields disagree with the corresponding WIT record -- the
entity schema is what must change, never the WIT (`common/README.md`,
"Contract validation and WIT-as-authority").

## Consequences

- Adding a capability means authoring exactly one WIT package/world under
  `common/wit/`, never a per-language copy of the interface.
- Any language whose component satisfies the same world is a drop-in
  replacement for any other; the harness treats them as identical black
  boxes and cannot tell which language produced a given `.wasm`.
- JSON Schema entity files that mirror a WIT record must be kept in sync by
  hand, but forgetting to do so is now a hard `contracts:check` failure
  rather than silent drift.
- Entities that exist only as JSON Schema (no corresponding WIT record) fall
  outside this conformance check -- the guarantee only applies where both
  representations exist side by side.
