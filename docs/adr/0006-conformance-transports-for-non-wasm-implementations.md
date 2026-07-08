# 0006. Conformance Transports for Non-WASM Implementations

Date: 2026-07-07

Status: proposed (not yet implemented — no transport other than the WASM
component adapter exists in the harness today)

## Context

ADR 0001 makes the shared WIT package the single component authority, and the
constitution's polyglot-parity principle expects every language to compile a
hot-swappable WebAssembly component that a single black-box suite proves
equivalent. Some languages cannot practically produce a WASM *component*:
Swift's component-model support is immature, and other runtimes may never have
a usable path. We want to extend the same black-box contract testing to those
languages without forking the contract, the `*.test.json` suites, the
`$fixture` fixtures, or the equivalence comparison. The enabling observation is
that the seam is narrow: everything in `common/`, plus `harness.contracts`,
`harness.fixtures`, the suite/WIT models, and the final `actual == expected`
comparison, is already transport-agnostic; only `harness.implementations`
(which scans for `{lang}/component/{world}.wasm`) and `harness.invocation` (the
wasmtime linker plus `Variant`/`Record` normalization) are WASM-specific.

## Decision

WIT plus its JSON-Schema mirrors remain the single contract authority for
**every** implementation regardless of how it is reached. We treat the WASM
Component Model as one *transport* — the premium one, because it also gives a
sandbox and a swappable artifact — rather than as the contract itself. We
define a canonical JSON wire encoding of the WIT types, which is exactly the
normalized form the suites' `expected` already uses (kebab-case record keys,
`option<T>` as value-or-`null`, `result<T, E>` as the `{"ok": …}`/`{"err": …}`
envelope from the result-support work, integers kept as integers — e.g. money
as `amount-cents: u32`, never floats). `harness.normalize_return` is then
simply "decode the Component Model ABI into this canonical JSON"; a JSON-native
transport speaks it directly and needs almost no marshalling. We introduce a
transport-adapter interface with two responsibilities — discovery and
`invoke(...) -> canonical JSON` — of which wasmtime is the first
implementation and a `stdio-json` adapter (spawn the implementation, write the
request, read the envelope) is the second; HTTP/REST is a possible third, as
the constitution's "WASM or REST" already anticipates. Each implementation
declares itself through a small manifest (world/interface, transport, and how
to reach it) so discovery no longer hard-codes the `.wasm` path, and the
suite's `targets` routing is generalized to run each suite against every
implementation whose transport is compatible while preserving the existing
rule that an excluded target is an explicit, printed skip and never a silent
one. We recognize two conformance **tiers** with deliberately different, and
explicitly declared, guarantees.

## Consequences

- **Tier 1 (WASM component)** keeps the full guarantee: ABI-level
  interchangeability (swap one `.wasm` for another and the host cannot tell),
  a sandboxed capability proof (`test_real_component_contracts.py` asserts the
  component imports nothing beyond wasip2), and single-artifact reproducibility
  across architectures.
- **Tier 2 (native stdio/HTTP)** proves *behavioral* contract conformance
  only. A Tier-2 pass is strictly weaker than a Tier-1 pass: the artifact is
  not swappable for a `.wasm`, "pure function, no I/O" becomes an unenforced
  convention rather than a sandbox boundary, and reproducibility is
  per-platform and drags the language toolchain into the container per arch.
- The JSON wire encoding must be pinned as rigorously as the Component Model
  ABI, or two "conformant" implementations diverge on encoding rather than
  behavior. The comparison must canonicalize both sides (parse to values, then
  compare) and never string-compare; keeping numeric domain values as integers
  removes the largest source of cross-encoder drift.
- The contract validator, fixture resolution, suite models, and comparison are
  reused unchanged; only discovery and invocation gain a second implementation,
  so the added surface is small and the single-source-of-truth invariant of
  ADR 0001 is preserved.
- This extends, and does not supersede, ADR 0001 (shared WIT authority) and
  ADR 0002 (native-vs-component boundaries); the tier of each implementation
  must be declared in its manifest and surfaced in the README's native-only
  criteria, honoring "native-only execution is declared explicitly."
- Recommended first step before adopting broadly: give an existing language a
  second, stdio-json implementation of `count-tasks` so one suite runs the same
  contract across two transports and proves they agree, de-risking the wire
  encoding on a trivial contract rather than on a real parser.
