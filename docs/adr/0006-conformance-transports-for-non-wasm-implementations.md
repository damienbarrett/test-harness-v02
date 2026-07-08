# 0006. Conformance Transports for Non-WASM Implementations

Date: 2026-07-08

Status: Proposed — considered and **deferred, not adopted**. WASM-only remains
the standing decision (ADR 0001). This record exists so the option and the
criteria that would reopen it are captured, not so it is built. Do not
implement without a forcing case (see Decision).

## Context

ADR 0001 makes the shared WIT package the single component authority, and the
constitution's polyglot-parity principle expects every language to compile a
hot-swappable WebAssembly component that one black-box suite proves equivalent.
This ADR examines whether languages that are awkward to compile to a WASM
*component* — Swift is the motivating example — should instead be reached
through a second, non-WASM transport.

The decisive clarification is that **"a language runs within WASM" is not the
same as "a language has a practical toolchain to compile a WIT component that
meets this repo's bar."** A participating implementation needs all of: a
Component (not a bare core module); a WIT interface exported through generated
bindings; instantiation on wasmtime's plain wasip2 linker; and
capability-minimal, reproducible, offline-buildable packaging in the Nix flake
(Phase 8; constitution §2). "Compiles to WASM" clears only the first.

Measured against that bar the languages form a spectrum of toolchain maturity,
not a WASM-capable / incapable split: Rust is first-class (`wit-bindgen`,
`cargo-component`); JavaScript is already Tier-1 in this repo via
`jco`/componentize-js, at the cost of bundling a JS engine (~11 MB); Python via
`componentize-py` bundles CPython (~18 MB); Swift can produce WASM (SwiftWasm,
Embedded Swift) but, as of early 2026, has no first-class
`wit-bindgen`/componentize path — a component would be hand-assembled from a
core module via `wasm-tools component new` plus a WASI adapter (verify current
state; this area moves quickly). So neither JavaScript nor Swift hits a hard
capability wall; the difference is toolchain maturity, ergonomics, artifact
size, and reproducibility — a moving target that improves over time.

## Decision

**WASM-only stands.** The default and expected path for every language is to
compile a WIT component (ADR 0001); this ADR does **not** introduce a second
transport now. There is no current forcing case: JavaScript is already a
component, and Swift is immature-but-improving — making a second transport
permanent infrastructure to hedge a well-resourced language's trajectory would
be premature and would permanently weaken the uniform interchangeability +
sandbox guarantee. Onboarding a language whose component toolchain is not yet
practical is accepted as blocked on that toolchain maturing (or on investment
to build it), rather than routed around.

The native transport design is recorded so it can be adopted quickly if
needed. *Were* it adopted it would: keep WIT + JSON Schema as the single
contract authority for every implementation; treat the Component Model as one
transport behind a canonical JSON wire encoding — already embodied by the
suites' normalized `expected` form (kebab-case record keys, `option<T>` as
value-or-`null`, `result<T, E>` as the `{"ok": …}`/`{"err": …}` envelope,
integers kept integral, e.g. money as `amount-cents: u32`); add a
transport-adapter interface (`discover` + `invoke -> canonical JSON`) with
wasmtime as the first adapter and a `stdio-json` (or HTTP/REST) adapter as the
second; and declare each implementation's world/interface/transport in a
manifest so discovery stops hard-coding the `{lang}/component/{world}.wasm`
path. Contract validation, fixture resolution, the suite models, and the
comparison would be reused unchanged.

**Reopen only on a forcing case**, defined as EITHER: (a) a need to
conformance-test an implementation this project does **not** compile — a
deployed third-party REST service, a vendor black box, a legacy endpoint —
which is the genuine, non-speculative justification (and the "or REST" the
constitution already anticipates); OR (b) a specific, actually-needed language
that a real componentize *spike* (not unfamiliarity) shows cannot meet the bar
above. Evaluate (b) by measurement — attempt a trivial `count-tasks` component
in that language and check artifact size, plain-wasip2 instantiation,
`option`/`result` binding correctness, and reproducible offline Nix packaging —
rather than by argument.

## Consequences

- The strong, uniform guarantee is preserved: every implementation stays
  ABI-interchangeable, sandbox-capability-proven
  (`test_real_component_contracts.py`), and single-artifact reproducible. No
  second transport, no wire-encoding-parity burden, and no
  "why componentize when stdio works" erosion is incurred.
- A language with an immature component toolchain (Swift today) cannot join
  until the toolchain matures or is invested in — deliberately accepted, since
  the alternative weakens the architecture's central claim for a hypothetical.
- The true trigger to reopen is captured precisely: conformance-testing an
  implementation we do not build, not merely "a non-WASM language." If the
  project never needs to test an uncompiled/external implementation, this ADR
  likely stays deferred indefinitely.
- If reopened, the seam is small — only discovery and invocation gain a second
  implementation — and the single-source-of-truth invariant of ADR 0001 holds;
  the recorded design plus the `{"ok"}/{"err"}` envelope and integer-domain
  decisions from the html-parser work are the ready-made foundation.
- This record extends, and does not supersede, ADR 0001 (shared WIT authority)
  and ADR 0002 (native-vs-component boundaries). Should a native transport ever
  be adopted, each implementation's tier must be declared and surfaced in the
  README's native-only criteria, honoring "native-only execution is declared
  explicitly."
