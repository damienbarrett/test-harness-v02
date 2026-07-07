# New World Product Search Contract (html-parser capability)

## Execution status (living handoff section)

Keep this section current so another agent can resume the work. Branch:
`feature/new-world-html-parser` (from `main` at `3ca0aec`); plan committed
as `db98211`.

- **Stage 1 — DONE, commit `3f85528`**: harness `result<T, E>` support.
  Key empirical finding, recorded in `harness/conversion.py`: wasmtime 43
  does NOT raise for `result::err` — it returns
  `wasmtime.component.Variant(tag, payload)`, itself a dataclass that the
  generic dataclass branch would have silently misnormalized to
  `{"tag": ..., "payload": ...}`; the envelope detection intercepts it by
  field shape. Returns-side record conformance, one-key ok/err envelope
  validation, numeric-bounds skip for record results, and the
  common/README.md convention all landed. 259 harness tests, 100%.
- **Stage 2 — DONE**. Full capability across all three languages. The
  subagent (running on Fable 5) was exhausted after building the contract
  files + Rust crate + Python core/components/tests; the orchestrator
  completed the JavaScript implementation and all verification directly.
  - Contract: `common/wit/html-parser.wit` (interface
    `new-world-product-search`, world `new-world-parser`), five entity
    schemas, `common/functions/new-world-product-search/` (function schema
    with the oneOf ok/err envelope + suite driving the gzip fixture).
  - Rust: `rust/component/new-world-parser/` crate (scraper/html5ever core)
    + component build wiring.
  - Python: `new_world_parser.py` core (stdlib html.parser) + `parser_app.py`
    glue (componentize-py bundles the src dir), native tests.
  - JavaScript: single `src/new-world-parser.js` — a hand-rolled tolerant
    tokenizer (byte-identical output to Python/Rust, no parse5 dependency)
    plus the `newWorldProductSearch` binding glue in the SAME file, because
    componentize-js evaluates one self-contained module and does not
    resolve relative imports (Python/Rust can bundle a dir/crate, JS can't
    — the per-language core-placement latitude the plan allows). Native
    tests at 100% branch coverage of the src tokenizer; a thin fixture
    adapter mirrors the conformance case names.
  - Result-envelope binding conventions confirmed empirically via
    `wasm:test`: componentize-js returns the ok value and throws the err
    value for `result<T,E>`; `option<>` none is `undefined`.
  - All gates green: `contracts:check`, `task test` (composed), `task
    coverage` 100% (harness 262 tests + all language gates), `wasm:test`
    12/12 across 3 implementations, `lint`, `check:runners` 11 pairs/0
    warnings, and a clean→rebuild cycle (clean removes all six .wasm
    artifacts, rebuild regenerates and passes 12/12).
- This completes the one DoD item the refactoring plan deferred: a single
  external HTML fixture now drives the same contract case through native
  execution AND all three WASM components, with the parser receiving
  decoded HTML strings (never a filesystem path).

## Summary

Add the repository's second capability: parsing the committed New World HTML
fixture into structured product-card data. The capability is defined once as
a WIT contract under `common/`, implemented in all three languages, and
compiled to a WebAssembly component per language so the central harness
black-box-proves all implementations equivalent — the constitution's polyglot
parity principle. This is the template for every future site parser.

This plan supersedes the earlier native-first draft. Review findings that
reshaped it, and the decisions taken:

- **Component-first, not native-first.** `targets: ["native"]` would have
  left the one black-box runner never exercising the parser, required
  weakening `test_real_component_contracts.py` (which hard-fails on a
  discovered world with missing artifacts, by design), and left "WASM-ready"
  an untested claim. All three languages ship components in the same change;
  gates stay green throughout.
- **`result<search-results, parse-error>`, not a bare return.** A total
  function cannot distinguish "no results" from "site redesigned, selectors
  dead" — a silent partial success (constitution §4). The error channel is
  in the contract from day one; the first suite ships ok-cases only.
- **Structured money values, not display text.** Consumers compute on
  prices; parsing "$0.81/ea" belongs in the one per-site parser, not in
  every consumer (model-first; constitution §7 Domain Types). Raw display
  strings are retained alongside for provenance.
- **Per-site interfaces.** Suite routing matches a suite's interface to
  every world exporting it, so one generic `product-search` interface
  implemented by many site components would run each site's suites against
  every other site's component. The scalable shape is one interface and one
  world per site: `new-world-product-search` / `new-world-parser`.
- **No per-language schema re-validation.** Native tests execute and
  deep-compare only; `contracts:check` owns schema conformance (Phase 3
  decision stands).

## Contract

### WIT — `common/wit/html-parser.wit`

```wit
package common:html-parser;

interface new-world-product-search {
    /// A price as displayed on a product card.
    record price {
        /// Whole price in cents (e.g. $9.73 -> 973).
        amount-cents: u32,
        /// The per-unit designator shown with the price (e.g. "ea").
        per: string,
        /// Raw display text, for provenance (e.g. "$9.73").
        display: string,
    }

    /// A comparative unit price (e.g. "$0.81/ea").
    record unit-price {
        amount-cents: u32,
        unit: string,
        display: string,
    }

    record product-card {
        product-id: string,
        name: string,
        subtitle: option<string>,
        url: string,
        image-url: option<string>,
        price: option<price>,
        unit-price: option<unit-price>,
    }

    record search-results {
        site: string,
        source-url: string,
        next-page-url: option<string>,
        products: list<product-card>,
    }

    record parse-error {
        /// Stable kebab-case error code (e.g. "no-results-container").
        code: string,
        message: string,
    }

    parse-search-results: func(html: string, source-url: string)
        -> result<search-results, parse-error>;
}

world new-world-parser {
    export new-world-product-search;
}
```

Records live inside the site interface for now (mirroring `tasks.wit`).
When a second site lands, shared records move to a `use`-imported types
interface — a known evolution that may need harness WIT-parser support;
do not build it speculatively.

### JSON Schema mirrors (`common/entities/`)

`price-schema.json`, `unit-price-schema.json`, `product-card-schema.json`,
`search-results-schema.json`, `parse-error-schema.json` — each with a
repo-relative `$id`. Conventions:

- Every WIT record field is a **required** schema property; optional WIT
  fields are `["<type>", "null"]`, never omitted keys (matches how the
  harness normalizes `option<>` to `null`).
- `amount-cents` properties carry `"minimum": 0, "maximum": 4294967295`
  (u32). Field-level numeric conformance checking in the central validator
  is a noted future hardening; the schemas carry correct bounds regardless.
- `site` is `"const": "new-world"`.

### Function schema and suite (`common/functions/new-world-product-search/`)

- `parse-search-results.schema.json` — `parameters` for `html` (string) and
  `source-url` (string, uri); `returns` validates the **result envelope**
  (see below) with `oneOf` ok/err branches `$ref`-ing the entity schemas.
- `parse-search-results.test.json` — one captured-page case, unrestricted
  `targets` (runs everywhere). Input uses the standard `$fixture` descriptor
  for `common/fixtures/html-parser/newworld-search-eggs.html.gz`
  (gzip, utf-8) plus the original source URL. Focused inline HTML-fragment
  cases (promo pricing, missing images, error cases) are follow-ups during
  parser hardening.

### Result envelope convention (new, harness-wide)

A suite case for a `result<T, E>`-returning function encodes `expected` as
exactly one of:

```json
{ "ok": <value matching the ok schema> }
{ "err": <value matching the err schema> }
```

The harness normalizes a component's returned result value into the same
envelope before comparison. The function schema's `returns` validates the
envelope. Non-result functions (e.g. `count-tasks`) are unchanged.

## Parser contract (observable behavior, pinned by the suite)

- Product cards are elements with `itemtype="https://schema.org/Product"`.
- `product-id` is the `data-testid` **on the Product element itself**,
  stripped of its `product-` prefix. (The page also has
  `product-title`/`product-image`/`product-card-details`/etc. test ids on
  descendants — prefix-matching anywhere is wrong.)
- `name` from `data-testid="product-title"`, `subtitle` from
  `data-testid="product-subtitle"` (absent -> null).
- `url` resolves the card link against `source-url`, removes the volatile
  `tr` query parameter and any fragment, and keeps **all other** query
  parameters exactly as found.
- `image-url` from the product image `src` (absent -> null).
- `price` from the `data-testid="price"` group: `amount-cents` from
  dollars/cents elements (`$9.73` -> 973), `per` from
  `data-testid="price-per"` (`"ea"`), `display` reconstructed (`"$9.73"`).
- `unit-price` from `data-testid="non-promo-unit-price"` text
  (`"$0.81/ea"` -> `{amount-cents: 81, unit: "ea", display: "$0.81/ea"}`;
  absent -> null). The promo-price card structure is not present in this
  fixture and is explicitly out of scope for the first case.
- Deduplicate products by canonical `url`, preserving document order.
- `next-page-url` is the first `a[rel=next]` resolved against `source-url`,
  else null.
- Errors: return `err(parse-error)` when the document contains no
  recognizable search-results structure at all (code
  `"no-results-container"`). A recognizable page with zero product cards is
  `ok` with empty `products`. (Error cases enter the suite as inline
  fixtures during implementation follow-up.)

Expected first-case value (verified against the fixture: exactly 3
`schema.org/Product` cards, no `rel="next"`):

```json
{
  "ok": {
    "site": "new-world",
    "source-url": "https://www.newworld.co.nz/shop/search?pg=1&q=size%207%20eggs&sf=products",
    "next-page-url": null,
    "products": [
      {
        "product-id": "5240876-EA-000",
        "name": "Farmer Brown Fresh Colony Size 7 Eggs",
        "subtitle": "12pk",
        "url": "https://www.newworld.co.nz/shop/product/5240876_ea_000nw?name=farmer-brown-fresh-colony-size-7-eggs",
        "image-url": "https://a.fsimg.co.nz/product/retail/fan/image/400x400/5240876.png?w=384",
        "price": { "amount-cents": 973, "per": "ea", "display": "$9.73" },
        "unit-price": { "amount-cents": 81, "unit": "ea", "display": "$0.81/ea" }
      },
      {
        "product-id": "5309531-EA-000",
        "name": "Farmer Brown Fresh Colony Size 7 Eggs",
        "subtitle": "6pk",
        "url": "https://www.newworld.co.nz/shop/product/5309531_ea_000nw?name=farmer-brown-fresh-colony-size-7-eggs",
        "image-url": "https://a.fsimg.co.nz/product/retail/fan/image/400x400/5309531.png?w=384",
        "price": { "amount-cents": 565, "per": "ea", "display": "$5.65" },
        "unit-price": { "amount-cents": 94, "unit": "ea", "display": "$0.94/ea" }
      },
      {
        "product-id": "5281163-EA-000",
        "name": "Rise N Shine Size 7 12 Pack Colony Eggs",
        "subtitle": "12pk",
        "url": "https://www.newworld.co.nz/shop/product/5281163_ea_000nw?name=rise-n-shine-size-7-12-pack-colony-eggs",
        "image-url": "https://a.fsimg.co.nz/product/retail/fan/image/400x400/5281163.png?w=384",
        "price": { "amount-cents": 799, "per": "ea", "display": "$7.99" },
        "unit-price": { "amount-cents": 67, "unit": "ea", "display": "$0.67/ea" }
      }
    ]
  }
}
```

## Implementation shape

- **One parsing core per language** — used by both native tests and the
  component build; never two copies of the extraction logic in one language.
  Where the core lives (library crate/package the component depends on, or
  the component with the library re-exporting) is decided per language by
  what each component toolchain can bundle; record the choice per language.
- **Parser dependencies must be WASM-portable** (constitution §6.3):
  - Rust: an html5ever-family crate (e.g. `scraper`) verified to build for
    `wasm32-wasip1`.
  - Python: stdlib `html.parser`-based core (componentize-py bundles stdlib).
  - JavaScript: a pure-JS parser (e.g. `parse5`) if `jco componentize` can
    bundle it; otherwise a minimal tolerant tokenizer sufficient for this
    contract, with limits documented. No DOM APIs (StarlingMonkey has none).
- **Components stay minimal**: built with the existing capability-minimized
  flags; they must instantiate on the plain wasip2 linker
  (`test_real_component_contracts.py` enforces this for every world x
  language, including the new `new-world-parser.wasm`).
- **Build/clean wiring**: each language's component lifecycle builds BOTH
  `task-component.wasm` and `new-world-parser.wasm`; `clean` removes both;
  Task `sources:`/`generates:` hints updated. Runner parity (identical
  bodies) maintained.
- **Native tests**: load the shared suite JSON, resolve `$fixture` through a
  thin per-language adapter (gzip + utf-8 + containment only), call the
  core, deep-compare against `expected`. No schema validation in language
  tests. Adapter tests mirror the canonical case list in
  `test-harness/tests/fixture_conformance.py` by name (the relevant subset:
  missing file, corrupt gzip, non-UTF-8, traversal, oversized) so drift is
  grep-detectable across languages.

## Harness prerequisites (land first, gates green, before the contract)

1. WIT parser: `result<T, E>` return types parsed into ok/err components;
   records reachable through returns (including via `result`, `option`,
   `list`) participate in entity-schema record conformance.
2. `normalize_return`: wasmtime-py result values (determine empirically how
   wasmtime 43 surfaces them) normalize to the `{"ok": ...}`/`{"err": ...}`
   envelope.
3. Central validator: for result-returning functions, `expected` must be a
   one-key ok/err envelope validating against the `returns` schema; numeric
   return-bounds checking applies to the ok branch when numeric, and is
   skipped (not crashed) for record/result returns.
4. Suite-format schema: unchanged (`expected` already allows any value).
5. Docs: envelope convention added to common/README.md.

## Test plan / gates

- `task contracts:check` validates the new WIT, all five entity schemas,
  the function schema, the fixture descriptor, and the expected envelope.
- `task wasm:test` runs the suite against `new-world-parser.wasm` for all
  three languages (9 count-tasks cases + 1 x 3 parser cases minimum).
- `task test` (composed) green end-to-end: contracts, lint, language natives
  (each parsing the real fixture through its adapter), harness suite,
  wasm parity. `test_real_component_contracts.py` covers the new world
  automatically via discovery.
- `task lint`, `task check:runners` (0 warnings), harness coverage 100%.
- Fixture stays byte-identical; no uncompressed copy committed.

## Sequencing

1. Harness result<>/conformance support (separate commit, all gates green).
2. Contract + three cores + three components + native tests (single commit —
   partial-language landings break wasm:test and the real-component gate by
   design). Merge when the full gate suite passes from a clean state.

## Explicit non-goals (this change)

- Promo-price card structure (not in the fixture; follow-up inline cases).
- Shared `use`-imported WIT types interface (second site's problem).
- Field-level numeric conformance in the validator (noted hardening).
- Pagination beyond `rel=next` (fixture has none).
