# plan.md — Transpose `shopping-optimiser` into this repo (v02 target)

> **HANDOFF DOCUMENT.** This file is the single source of truth for an agent
> with no prior context. Read the whole thing once before doing anything.
> It is written to be executed by a less-sophisticated agent: every step is
> explicit, ordered, and has a copy-pasteable command and a "done when" check.
>
> **Two repos are involved:**
> - **TARGET** (where you work, write code here): `/persist/git/shopping-optimiser-v02`
> - **SOURCE** (read-only reference, never edit): `/persist/git/shopping-optimiser`
>
> The SOURCE already contains a working implementation. You are **reconstructing**
> it inside the TARGET, test-first, following the TARGET's cleaner patterns and
> the constitution. When a step says "reference: SOURCE/<path>", open that file
> and read it — it is the proven answer — but you must still write a failing
> test first (see Ground Rule G4).

---

## Core invariant, authority order & related documents

**Core invariant — the whole point of this design.** The WIT contract lives in
**one shared place, `common/wit/`, and every language compiles a WASM component
against that exact same WIT.** The resulting `{lang}/component/{world}.wasm`
artifacts are **hot-swappable**: the calling code (here, the black-box harness
`test-harness/run-wasm-tests.py`) loads any language's `.wasm` for a given world
and runs the identical JSON test vectors — it neither knows nor cares which
language produced it. **Protect this invariant above any internal-layout
preference:** shared WIT in `common/`, exactly one `.wasm` per world per language
at `{lang}/component/{world}.wasm`, identical observable behaviour. Internal
folder organisation inside each `{lang}/component/` is an implementation detail.

**When instructions conflict, obey in this order:**
1. `constitution.md` (this repo)
2. This plan (`plan.md`)
3. Current TARGET-repo patterns (the `count-tasks` reference example)
4. SOURCE-repo behaviour and its **tests**
5. Any SOURCE planning/notes docs — **historical context only**

**Treat these SOURCE files as historical context, NOT as instructions:**
`PLAN.md`, `requirements.md`, `context.md`, `v01.md`, `v02.md`,
`search-parser.md`, `AGENTS.md`. In particular, **ignore SOURCE's git-submodule /
superproject workflow** — the TARGET uses plain tracked directories.

---

## 0. How to use this document

1. Work **top to bottom**. Phases are ordered by dependency. Do not skip ahead.
2. Each phase has a checklist (`- [ ]`). Tick items as you complete them by
   editing this file (`AGENTS.md` requires keeping the plan current).
3. After **every** code change, run the relevant `task test` for that sub-repo.
   Never batch many changes before testing.
4. All tooling runs inside Nix dev shells: `cd <subdir> && nix develop --command <cmd>`.
   Do not use host-installed toolchains (constitution §2).
5. If something in this plan turns out to be wrong, stop and report it. Do not
   improvise a different architecture.

---

## 1. Mission & definition of success

Transpose the **entire** `shopping-optimiser` feature set into v02:

- **Tier A — WASM contract:** `product-listings` interface / `list-matching-products`
  function, exposed as a WebAssembly component in **all three** languages
  (python, javascript, rust) and validated by the shared black-box harness.
- **Tier B — pure library code (offline):** the multi-retailer search parser
  (`parse-search-results` over new-world, paknsave, the-warehouse, woolworths),
  the woolworths listing parser, and the `provider-search` URL builder — in all
  three languages, tested natively against shared JSON vectors + gzipped HTML
  fixtures.
- **Tier C — CLI + design docs:** the woolworths CLI (live fetch **isolated**
  behind an injection boundary so tests stay offline) and the loose design
  documents (`schema.sql`, `search-parser.md`, etc.).

**Success =** from the TARGET repo root, all of the following pass with **zero
failures** and **100% coverage** where coverage is enforced:

```bash
just setup
just test            # python + javascript + rust + test-harness unit tests
just coverage        # 100% line/branch/function/region per language
just wasm-test       # black-box parity across all built .wasm components
just check-runners   # Taskfile.yml <-> justfile parity
```

(`task <verb>` must work identically to `just <verb>` — they are kept in parity.)

---

## 2. Ground rules (constitution-derived — NON-NEGOTIABLE)

| # | Rule | Source |
|---|------|--------|
| G1 | **Offline.** No live network in `setup`/`test`/`coverage`. Fixtures only. | constitution §2; SOURCE/requirements.md §12 |
| G2 | **Functional core.** Business logic = pure functions. I/O pushed to the edges. | constitution §7 |
| G3 | **Contract-first.** JSON Schema + WIT are the source of truth; code conforms to them, never the reverse. | constitution §1, §6 |
| G4 | **Strict TDD.** Red → Green → Refactor. Write a failing test, watch it fail, write minimum code to pass, refactor. No production line without a test that needed it. | constitution §5, §7; AGENTS.md |
| G5 | **100% coverage**, no exclusions, enforced by each language's coverage task. | constitution §7 |
| G6 | **Lifecycle verbs only.** Each sub-repo exposes `setup test coverage clean purge`. Orchestrator exits non-zero if any sub-layer fails. | constitution §4 |
| G7 | **Runner parity.** Every `Taskfile.yml` has a sibling `justfile` with the same recipe names + deps. `check-runner-parity.py` must pass. | TARGET/test-harness/check-runner-parity.py |
| G8 | **One file per change where practical.** If a change needs many files, treat it as a refactoring smell. | AGENTS.md |
| G9 | **Do not commit or push** until the user explicitly asks. Work on a feature branch. | AGENTS.md; SOURCE/requirements.md §9 |
| G10 | **Domain types.** In typed languages, wrap primitives (e.g. money) with validation in the constructor. | constitution §7 |

---

## 3. Mental model — the two-tier architecture

There are **two layers** per language, and **two test mechanisms**. Do not
confuse them — this is the single most important concept in this repo.

```
                 ┌──────────────────────────────────────────────────────┐
                 │ common/  (language-agnostic contracts — no logic)     │
                 │   wit/*.wit · entities/*.json · functions/**.json     │
                 │   fixtures/**                                          │
                 └──────────────────────────────────────────────────────┘
                        ▲ conforms to                 ▲ conforms to
        ┌───────────────┴───────────────┐   ┌─────────┴──────────────────┐
        │ {lang}/library/                │   │ {lang}/component/          │
        │  Rich, dependency-using pure   │   │  Self-contained pure       │
        │  parsers (bs4 / scraper /      │   │  parsers (regex / manual)  │
        │  injectable scraper).          │   │  compiled to WASM.         │
        │  Tested NATIVELY by the lang's │   │  Tested BLACK-BOX by       │
        │  own runner against fixtures.  │   │  test-harness/ via wasmtime│
        └────────────────────────────────┘   └────────────────────────────┘
```

### Two test mechanisms

1. **WASM black-box harness** (`test-harness/run-wasm-tests.py`):
   discovers `common/functions/{interface}/{fn}.test.json`, finds the WIT world
   that exports `{interface}`, loads `{lang}/component/{world}.wasm`, calls the
   function via wasmtime, compares the result to `expected`. Works only for
   functions whose **inputs/outputs are plain WIT-marshalable values**.
   → **Tier A (`list-matching-products`) is tested this way.**

2. **Language-native runners** (`pytest`, `node --test`, `cargo test`):
   load the same `*.test.json` vectors, read gzipped HTML fixtures from disk,
   call the library function directly, compare. Used when the WASM harness
   can't apply (gzip fixture reading, heavy parser deps).
   → **Tier B (`parse-search-results`) is tested this way.**

### Why two parsers (library vs component)?

The SOURCE progress log (SOURCE/requirements.md §13) records that `bs4`,
`jsdom`, `scraper`, and `regex` all **trap or bloat inside WASM**. Therefore:
- The **library** parser may use rich dependencies (it runs natively).
- The **component** parser must be **self-contained** (plain regex / manual
  scanning, no heavy crates) so it compiles to a small, trap-free WASM module.

The `list-matching-products` component parser is intentionally simple: it only
needs to handle the hand-crafted `product-stamp` HTML shape in the test vectors,
**not** real retailer DOM. (Real DOM is the library's job.)

---

## 4. Current state vs. target

**TARGET today** is a clean baseline containing only the `tasks` / `count-tasks`
reference example. The core pattern files (`count.*`, `tasks.wit`, the
count-tasks contract + tests) are byte-identical to SOURCE — so the pattern is
already proven; you are extending it, not changing it.

**Key differences from SOURCE you must honour:**
- TARGET uses **plain tracked directories** (no git submodules). Ignore all
  submodule / superproject instructions in SOURCE/requirements.md.
- TARGET's `test-harness/run-wasm-tests.py` is the **old single-package**
  version (hardcoded `WIT_PACKAGE = "tasks"`). You must upgrade it (Phase 2).
- TARGET's components are currently **flat single-world** dirs. Each language
  must additionally emit `product-listings-component.wasm` next to the existing
  `task-component.wasm` (see §6 for the per-language layout). The existing
  task-components stay green throughout.

---

## 5. Source map — where the proven reference lives

| What | SOURCE path (read-only reference) |
|------|-----------------------------------|
| Shopping WIT | `common/wit/shopping.wit` |
| Product entity schema | `common/entities/product-schema.json` |
| product-listings contract + tests | `common/functions/product-listings/list-matching-products.{schema,test}.json` |
| product-search contract + tests | `common/functions/product-search/parse-search-results.{schema,test}.json` |
| Gzip HTML fixtures (10 files) | `common/fixtures/search-parser/*.html.gz` + `README.md` |
| Upgraded harness | `test-harness/run-wasm-tests.py` |
| Python library parsers | `python/library/src/{search_parser/parser.py, woolworths/parser.py}` |
| Python library tests | `python/library/tests/{test_search_parser.py, test_woolworths.py, test_woolworths_cli.py}` |
| Python CLI | `python/library/src/woolworths/cli.py` |
| Python shopping component | `python/component/src/shopping_app.py`, `tests/shopping/*`, `tests/test_wasm_product_listings.py` |
| JS library parsers | `javascript/library/src/{search-parser.js, provider-search.js, woolworths/parser.js}` |
| JS library tests | `javascript/library/tests/{search-parser.test.js, provider-search.test.js, woolworths.test.js}` |
| JS shopping component | `javascript/component/src/woolworths/{app.js, parser.js}`, `tests/wasm-product-listings.test.js` |
| Rust library modules | `rust/library/src/{search_parser.rs, woolworths.rs, lib.rs}`, `Cargo.toml` |
| Rust components (multi-crate) | `rust/component/{task-component,product-listings-component}/` + `Taskfile.yml` |
| Design docs | `schema.sql`, `search-parser.md`, `size-7-eggs.csv`, `context.md`, `v01.md`, `v02.md` |

> **Reminder:** SOURCE's per-language component layouts are *inconsistent*
> (python/js use one dir, rust uses subdirs). You are unifying them. Use SOURCE
> for the **logic**, this plan for the **structure**.

### 5.1 Copy verbatim vs. reconstruct via TDD (per-artifact action)

This plan uses **strict TDD reconstruction** for all executable code. Only
inert, language-agnostic artifacts are copied byte-for-byte. Use this table to
know which is which:

| Artifact | Action |
|----------|--------|
| `common/wit/shopping.wit`, `entities/product-schema.json` | **Copy verbatim**, then sanity-check formatting vs TARGET style. |
| `common/functions/**/*.schema.json` + `*.test.json` | **Copy verbatim** (these JSON test vectors are the contract — never hand-edit to fit code). |
| `common/fixtures/**` (10 gz + READMEs) | **Copy binary, as-is.** |
| `test-harness/run-wasm-tests.py` | **Adapt** (test-first): port multi-package discovery + `to_plain` + world-less SKIP into TARGET's file; do not blob-replace. |
| Design docs (`schema.sql`, `search-parser.md`, …) | **Copy verbatim** into `docs/`. |
| Every parser / component / CLI source file | **Reconstruct test-first** (RED→GREEN→REFACTOR). SOURCE is the reference you read during GREEN — not a file to copy. |
| Lockfiles (`uv.lock`, `Cargo.lock`, `package-lock.json`) | **Regenerate** via the language's lock command. Never copy or hand-edit. |
| `node_modules/`, `.venv/`, `target*/`, `bindings/`, `transpiled/`, `*.wasm`, `*.pyc`, coverage, `tmp/` | **Never copy.** Generated locally by the lifecycle. |

---

## 6. Target directory layout

**The contract that must never change** (the swappable-WASM invariant):

```
common/wit/tasks.wit       # package common:tasks     → world task-component
common/wit/shopping.wit    # package common:shopping  → world product-listings-component
{lang}/component/task-component.wasm              # built by each language (gitignored)
{lang}/component/product-listings-component.wasm  # built by each language (gitignored)
```

Every language builds against the **same** `common/wit/*.wit` and emits its
`.wasm` at exactly `{lang}/component/{world}.wasm`. The harness loads whichever
`.wasm` exists and runs identical vectors, so implementations are interchangeable.
**Do not move the WIT, rename worlds, or change the output paths.**

**Internal layout — follow each language's proven/natural shape** (this is what
SOURCE shipped; lowest churn on the already-green task-components):

- **Python & JavaScript — one `component/` dir builds BOTH worlds.** Keep the
  existing single `Taskfile.yml`/`justfile` pair and add a second build target.
  Each world gets its own generated bindings / transpile output and its own `src`
  entrypoint.
  ```
  python/component/
    Taskfile.yml  justfile  pyproject.toml  uv.lock  conftest.py
    src/app.py            # task world entrypoint
    src/shopping_app.py   # product-listings world entrypoint
    bindings/task-component/   bindings/product-listings-component/   (gitignored)
    tests/...   tests/shopping/...
    task-component.wasm   product-listings-component.wasm             (gitignored)

  javascript/component/
    Taskfile.yml  justfile  package.json  package-lock.json
    src/app.js                 # task world
    src/woolworths/app.js      # product-listings world (+ self-contained parser)
    tests/...   tests/wasm-product-listings.test.js
    transpiled/   task-component.wasm   product-listings-component.wasm  (gitignored)
  ```
- **Rust — one crate per world under `component/`** (cargo-component ties one
  world per `Cargo.toml`, so the split is mandatory, not cosmetic). Migrate the
  existing flat crate into `task-component/`, then add
  `product-listings-component/`. One `Taskfile.yml`/`justfile` pair at
  `rust/component/` `cd`s into each crate (mirrors SOURCE/rust/component exactly);
  the crate subdirs hold **no** runner files.
  ```
  rust/component/
    Taskfile.yml  justfile
    task-component/             Cargo.toml  Cargo.lock  src/lib.rs  tests/
    product-listings-component/ Cargo.toml  Cargo.lock  src/lib.rs  tests/
    task-component.wasm   product-listings-component.wasm   (gitignored)
  ```

**Libraries** stay one-per-language with modules (not per-world subdirs):
`{lang}/library/` gains count + search-parser + woolworths + provider-search
modules, tested by the language's native runner.

> Mixed internal shapes are fine **because the external contract is identical**:
> shared WIT + swappable `.wasm` at fixed paths. Matching each toolchain's grain
> avoids needlessly restructuring code that already works.

---

## 7. Execution phases

### Phase 0 — Preparation
- [ ] Create a feature branch in TARGET: `git checkout -b feature/transpose-shopping`.
- [ ] Confirm baseline is green before touching anything:
      `just setup && just test && just wasm-test && just check-runners`.
      If the baseline is not green, **stop and report** — do not build on red.
- [ ] Record the baseline result (and any pre-existing failures) in the Progress
      Log (§14) **before** editing. Never silently build on top of red.
- [ ] `constitution.md` is currently **untracked** (`?? constitution.md`). Track
      it intentionally as part of this work: `git add constitution.md`. Do not
      delete it.
- [ ] Confirm no SOURCE generated/scratch files have leaked into TARGET:
      `git status --short` and `git ls-files --others --exclude-standard`.

### Phase 1 — `common/` contracts & fixtures (contract-first, G3)
No language code yet. Copy/author the agnostic contracts so every later phase
has something to conform to.
- [ ] Copy `common/wit/shopping.wit` from SOURCE verbatim.
- [ ] Copy `common/entities/product-schema.json` from SOURCE verbatim
      (includes the `money` `$def` with `amount` `^[0-9]+\.[0-9]{2}$`, currency `NZD`).
- [ ] Copy `common/functions/product-listings/list-matching-products.schema.json`
      and `.test.json` (5 cases) verbatim.
- [ ] Copy `common/functions/product-search/parse-search-results.schema.json`
      and `.test.json` (9 cases) verbatim.
- [ ] Copy the **10 fixture files** under `common/fixtures/search-parser/`
      (8 × `*.html.gz` + `README.md`) **as binary** (do not re-encode):
      ```bash
      cp -a /persist/git/shopping-optimiser/common/fixtures/search-parser \
            /persist/git/shopping-optimiser-v02/common/fixtures/
      ```
- [ ] Copy `common/fixtures/woolworths-size-7-eggs/README.md`.
- [ ] Verify **every** `fixture` path referenced in `parse-search-results.test.json`
      exists on disk (catches truncated/forgotten fixtures early):
      ```bash
      grep -o '"common/fixtures/[^"]*"' \
        common/functions/product-search/parse-search-results.test.json \
        | tr -d '"' | sort -u \
        | while read -r f; do test -f "$f" && echo "OK $f" || echo "MISSING $f"; done
      ```
      Every line must print `OK`.
- [ ] **Done when:** `git status` shows the new contract + fixture files and the
      JSON files are valid (`python -c 'import json,glob;[json.load(open(f)) for f in glob.glob("common/**/*.json",recursive=True)]'`).

> **Note on the `money` domain type (G10):** the WIT `product` record for
> `product-listings` is intentionally only `{name, url}`. `price`/`club_price`
> appear only in the **product-schema** and the Tier-B `parse-search-results`
> output. Keep that asymmetry.

### Phase 2 — Upgrade the WASM harness (test-first, G4)
The TARGET harness hardcodes the `tasks` package and cannot handle a second WIT
package, record-returning functions, or library-only interfaces.
- [ ] **RED:** add a harness self-test under `test-harness/` (mirror the existing
      test style there) asserting that, given both `tasks.wit` and `shopping.wit`,
      discovery yields two worlds with correct `namespace:package/world` and
      exported interfaces. Run; confirm it fails.
- [ ] **GREEN:** port the three capabilities from SOURCE/test-harness/run-wasm-tests.py:
      1. `discover_wit_worlds()` — parse `package <ns>:<name>;` + `world` blocks +
         `export <iface>;` per WIT file (returns `WitWorld` dataclasses).
      2. `worlds_for_interface()` + invert the main loop to
         `for suite: for world in worlds_for_interface(suite.interface)`, with
         `interface_export = f"{ns}:{pkg}/{interface}"`.
      3. `to_plain(value)` — recursively convert wasmtime record results
         (dataclass / namedtuple / attr objects) to plain `dict`/`list` before
         comparing to JSON.
- [ ] **ADD (intentional improvement over SOURCE):** when a discovered suite's
      interface is exported by **no** world (e.g. `product-search`, which is
      library-only), **skip it with a printed `SKIP` line — do not count it as a
      failure.** Rationale: Tier-B contracts live in `common/functions/` for
      discoverability but are validated by language-native runners, not WASM.
      Add a harness self-test for this skip behaviour (RED first).
- [ ] **Done when:** `cd test-harness && nix develop --command task test` passes,
      and `just wasm-test` still reports the existing `count-tasks` results as
      before (backward compatible) and prints a `SKIP` for `product-search`.

### Phase 3 — Prepare each component dir for a second world (keep green)
Only Rust needs a structural change; Python/JS extend in place. Do one language
at a time and keep the existing task-component tests green throughout.

- [ ] **Python — extend in place (no move).** `python/component/` will build both
      worlds. Plan a second build target writing into
      `bindings/product-listings-component/` (keep `bindings/task-component/`),
      and two pytest invocations to avoid `wit_world` collision (see §8.1).
      Nothing to migrate. **Done when** `cd python && nix develop --command task
      test` is still green.
- [ ] **JavaScript — extend in place (no move).** `javascript/component/` will
      build both worlds (second `src` entrypoint + transpile target). Nothing to
      migrate. **Done when** `cd javascript && nix develop --command task test` is
      still green.
- [ ] **Rust — split into per-world crates (required).** Move
      `rust/component/{Cargo.toml,Cargo.lock,src,tests}` into
      `rust/component/task-component/`, and rewrite `rust/component/Taskfile.yml`
      + `justfile` to `cd` into the crate (mirror SOURCE/rust/component).
      cargo-component emits
      `target-local/wasm32-wasip1/release/task_component.wasm`, copied up to
      `rust/component/task-component.wasm`.
      **Done when** `cd rust && nix develop --command task test` is green and
      `rust/component/task-component.wasm` exists.
- [ ] Update each `{lang}/.gitignore` for the new outputs (see §8.4).
- [ ] **Done when:** `just test`, `just wasm-test`, `just check-runners` are green
      and unchanged in result.

### Phase 4 — `product-listings-component` (Tier A) — TDD per language
For each language, add the second world's sources (Rust: a new
`product-listings-component/` crate; Python/JS: a new entrypoint in the existing
`component/` dir), wire its build so `product-listings-component.wasm` lands in
`{lang}/component/`, and make the black-box harness pass.

For **each** language, in this order — python, then javascript, then rust:
- [ ] **RED 1 (pure parser):** write a unit test for the self-contained parser
      that loads cases from `common/functions/product-listings/list-matching-products.test.json`
      and asserts name normalisation + URL resolution + case-insensitive match
      (spec in §9). Run; fail.
- [ ] **GREEN 1:** write the self-contained parser (regex/manual; reference
      §9 and SOURCE component parsers). Run; pass. **REFACTOR.**
- [ ] **RED 2 (WIT export):** write a test that imports the generated bindings
      and calls the export class' `list_matching_products(page, match_phrase, base_url)`,
      parametrised over the same vectors. (Runs only after a build.)
- [ ] **GREEN 2:** write the thin WIT export wrapper that maps parser dicts to
      the generated `Product` record. Build, run; pass.
- [ ] **RED 3 (end-to-end WASM):** write a low-level wasmtime test (mirror the
      task-component's `wasm` test) against `product-listings-component.wasm`,
      interface export `common:shopping/product-listings`, function
      `list-matching-products`. Build, run; pass.
- [ ] Wire `build:product-listings-component` (+ test/coverage) into the component
      `Taskfile.yml`/`justfile` so the `.wasm` lands at
      `{lang}/component/product-listings-component.wasm`.
- [ ] **Done (per language) when:** `cd {lang} && nix develop --command task test`
      and `task coverage` (100%) pass.
- [ ] **Phase 4 done when:** `just wasm-test` reports **2 worlds** and
      `count-tasks` + `list-matching-products` passing across **all 3** langs.

### Phase 5 — Tier-B library code (search-parser, woolworths, provider-search) — TDD
This is the largest phase. All pure, all offline, tested by native runners
against `parse-search-results.test.json` + the gzip fixtures. Do **per language**.

Library modules to add (names are guidance; match each language's idiom):
- a **search parser** with site detection (new-world, paknsave, the-warehouse,
  woolworths) returning `{site, source_url, next_page_url, products[]}`
  (spec §9; reference SOURCE/{lang}/library parsers).
- a **woolworths listing parser** (the simple `product-stamp` parser shared with
  the component's logic; reference SOURCE/{lang}/library/.../woolworths).
- a **provider-search** URL builder (pure: search term → per-retailer URLs;
  any page-capture is **injected**, never called in tests — reference
  SOURCE/javascript/library/src/provider-search.js, which is already
  dependency-injected via `capturePage`).

Per language:
- [ ] **RED:** copy/author the native test that loads `parse-search-results.test.json`,
      decompresses each fixture (`gzip`), calls the parser, compares to `expected`.
      Run; fail.
- [ ] **GREEN:** implement the parser modules (reference SOURCE; rich deps OK
      here — Python `bs4`, Rust `scraper`+`url`; JS prefer native `DOMParser`/
      regex per constitution §7-JavaScript). Add dependencies to the library's
      manifest + refresh the lockfile via `task update` (or the language's lock
      command) — never hand-edit lockfiles.
- [ ] **REFACTOR** to 100% coverage.
- [ ] Register new modules so coverage sees them (e.g. Python `[tool.coverage.run] include`,
      Rust `pub mod`, JS exports).
- [ ] **Done (per language) when:** `task test` + `task coverage` (100%) pass.
- [ ] **Phase 5 done when:** all three languages parse all 9 `parse-search-results`
      vectors identically, fully offline.

> **Gotchas captured from SOURCE/requirements.md §13 (heed these):**
> - Keep the **component** parser self-contained; never import bs4/jsdom/scraper
>   into a WASM-bound module.
> - Rust component needs `crate-type = ["cdylib", "lib"]` and a cdylib linker
>   workaround for the host tests (see SOURCE/rust/component/product-listings-component).
> - JSON key order in `*.test.json` inputs must match WIT parameter order — the
>   harness passes dict values positionally.

### Phase 6 — Tier-C CLI (offline-isolated) + design docs
- [ ] Implement the woolworths CLI in `python/library` (reference
      SOURCE/python/library/src/woolworths/cli.py) **but isolate the network**:
      - The live fetch (`urllib.request.urlopen`) must sit behind an **injected
        fetcher** parameter (default = real fetch; tests pass a fake). This is
        the only Tier-C network path; G1 forbids it in `task test`.
      - Default (no `--live`) reads a fixture. **Fix the stale fixture path** in
        SOURCE (`common/fixtures/woolworths/page.html` does not exist) — point it
        at a fixture that exists, or decompress a `search-parser/*.html.gz` into a
        test-local temp. Decide the simplest correct path and document it inline.
- [ ] **RED/GREEN/REFACTOR** the CLI test (`test_woolworths_cli.py` reference) so
      it injects the fake fetcher and asserts JSON/TSV output **without network**.
      100% coverage including the `--live` branch (exercise it via the injected
      fetcher, not a real socket).
- [ ] Copy design docs into **`docs/`** (maintainer-confirmed — keep the repo
      root tidy per AGENTS.md): `schema.sql`, `search-parser.md`, `size-7-eggs.csv`,
      `context.md`, `v01.md`, `v02.md`. These are reference material, not executed.
      Add a one-line `docs/README.md` noting they were transposed from SOURCE as
      historical/design context (not active instructions — see Authority order).
- [ ] **Done when:** `task test`/`coverage` for python stay green and offline.

### Phase 7 — Lifecycle wiring & runner parity (G6, G7)
- [ ] Ensure every `{lang}/component/Taskfile.yml` chains all five verbs across
      both worlds, and the sibling `justfile` mirrors recipe names + deps
      (canonical mapping: `build:task-component` ↔ `build-task-component`).
- [ ] Ensure `{lang}/Taskfile.yml` + `justfile` chain `library` + `component`
      for all five verbs (and the CLI tests for python).
- [ ] **Done when:** `just check-runners` (== `task check:runners`) prints
      `OK: N Taskfile.yml/justfile pair(s) in parity` with **zero** drift
      (command-body *warnings* are acceptable; missing recipes / dep mismatches
      are not).

### Phase 7.5 — Container validation (CONDITIONAL)
**Only run this phase if you changed any lifecycle, Nix, container, or root
orchestration file** (`flake.nix`, `flake.lock`, `container/**`, root
`Taskfile.yml`/`justfile`). Pure code/contract changes do not require it.
- [ ] `just container-nixos-test` (or `task container:nixos:test`) passes, **or**
      record the exact command + error in the Progress Log (§14).
- [ ] `just container-nixos-coverage` passes, **or** record the failure.
- [ ] If you did **not** change those files, tick this box and note "N/A — no
      lifecycle/container files changed".

### Phase 8 — Full verification matrix
Run from TARGET root and confirm each is green:
- [ ] `just setup`
- [ ] `just test`
- [ ] `just coverage`  (100% enforced per language)
- [ ] `just wasm-test` → 2 worlds; `count-tasks` + `list-matching-products`
      passing across 3 implementations; `product-search` shows `SKIP`.
- [ ] `just check-runners`
- [ ] Repeat the whole matrix once more after `just clean` to prove
      reproducibility from a clean tree (constitution §1).
- [ ] Confirm **no network** was needed (run with networking disabled if possible).
- [ ] Confirm the working tree is clean of stray/generated files:
      `git status --short` and `git ls-files --others --exclude-standard` show
      only intended new sources, contracts, fixtures, and docs — **no** `*.wasm`,
      `target*/`, `bindings/`, `transpiled/`, `node_modules/`, `.venv/`, lockfile
      noise from SOURCE, or `tmp/` scratch.

### Phase 9 — Wrap up
- [ ] Tick every checkbox above; leave this file as the as-built record.
- [ ] Summarise what changed and what (if anything) deviated from this plan.
- [ ] **Do not commit or push** (G9) — wait for the user.

---

## 8. Per-language specifics & commands

### 8.1 Python
- Library: add modules under `python/library/src/` (e.g. `search_parser/`,
  `woolworths/`), register them in `python/library/pyproject.toml`
  `[tool.hatch.build.targets.wheel] packages` and `[tool.coverage.run] include`.
  Add `bs4` (and any other parser deps) under the `test` extra; run
  `uv lock` (via a `task update` recipe) to refresh `uv.lock` — never hand-edit.
- Component: **one `python/component/` dir builds BOTH worlds** (mirror
  SOURCE/python/component/Taskfile.yml's two-world version):
  - `build`: `build:task-component` then `build:product-listings-component`, each
    generating into its own `bindings/{world}/` then `componentize -o {world}.wasm`.
  - `test` / `coverage`: run the task tests and shopping tests as **separate
    pytest invocations** (e.g. `pytest tests/ --ignore=tests/shopping` then
    `pytest tests/shopping/`) — this avoids the `wit_world` binding collision when
    both worlds' generated packages load in one process.
  - per-world componentize-py (run from `python/component/`):
    ```bash
    uv run --locked --extra build componentize-py -d ../../common/wit/shopping.wit \
        -w product-listings-component bindings bindings/product-listings-component
    uv run --locked --extra build componentize-py -d ../../common/wit/shopping.wit \
        -w product-listings-component componentize \
        -p src -p bindings/product-listings-component -s \
        -o product-listings-component.wasm shopping_app
    ```
- WIT export wrapper `src/shopping_app.py` (reference SOURCE): maps parser dicts →
  generated `Product(**p)`.
- Host tests import the real generated bindings via a `conftest.py` that prepends
  the right `bindings/{world}` + `src` to `sys.path` (reference
  TARGET/python/component/tests/conftest.py and
  SOURCE/python/component/tests/shopping/conftest.py).

### 8.2 JavaScript
- **JS WASM build is approved** (maintainer-confirmed). Build each component
  world with `jco componentize <src> --wit <wit> -n <world> -d all --enable
  clocks --enable random --enable stdio -o <world>.wasm`, then `jco transpile
  <world>.wasm -o transpiled/` (mirror TARGET/javascript/component/Taskfile.yml).
  This compiled step is the sanctioned WASM exception to the constitution's
  "no build step"; the **library** itself still ships as plain ESM, no transpile.
- **Isomorphic / `jsdom` caveat (constitution §7-JavaScript — important).**
  SOURCE's `search-parser.js` does `import { JSDOM } from 'jsdom'` (Node-only),
  which breaks the browser test path the constitution requires. Do **not** port
  that import into isomorphic library code. Instead: make the core parser accept
  an already-parsed `Document` (or use a string/regex approach), and supply the
  `Document` from thin adapters — native `DOMParser` in the browser, a
  `jsdom`-backed wrapper in Node-only/CLI code. Keep `jsdom` out of anything that
  must run in a browser or a WASM component. (The `list-matching-products`
  component parser stays pure regex regardless.)
- Library tests: Node's built-in `node:test` + `node:assert/strict`; gzip via
  `node:zlib`. Coverage: `node --test --experimental-test-coverage
  --test-coverage-lines=100 --test-coverage-branches=100 --test-coverage-functions=100`.
- Component build per world (reference SOURCE/javascript/component):
  ```bash
  jco componentize src/shopping_app.js --wit ../../../common/wit/shopping.wit \
      -n product-listings-component -d all -o ../product-listings-component.wasm
  ```
- provider-search stays dependency-injected (`capturePage`/`scraper` options) so
  tests never hit network (reference SOURCE/javascript/library/src/provider-search.js).

### 8.3 Rust
- Library: add `pub mod search_parser;` + `pub mod woolworths;` to
  `rust/library/src/lib.rs`; add deps (`scraper`, `url`, `serde_json`, …) to
  `rust/library/Cargo.toml` (reference SOURCE) and refresh `Cargo.lock` with
  `cargo update -p <crate>` / `cargo fetch` (offline-friendly). Coverage via
  `cargo llvm-cov ... --fail-under-lines 100 --fail-under-functions 100 --fail-under-regions 100`.
- Components: two crates under `rust/component/` — `task-component/` and
  `product-listings-component/`, each with its own `Cargo.toml` declaring
  `[package.metadata.component] package = "common:<pkg>"` and
  `[package.metadata.component.target] world = "<world>"`, `path = "../../../common/wit"`.
  `crate-type = ["cdylib", "lib"]`. Build with `cargo component build --release
  --target-dir target-local`, copy `target-local/wasm32-wasip1/release/<crate_snake>.wasm`
  up to `rust/component/<world>.wasm` (reference SOURCE/rust/component/Taskfile.yml).
- The component parser is **manual/regex**, self-contained — do **not** pull
  `scraper`/`regex` into the cdylib (WASM allocation issues, per SOURCE §13).
- **Host-coverage pattern (critical — mirror the TARGET task-component).** The
  wit-bindgen export types live behind `#[cfg(target_arch = "wasm32")]`, so host
  `cargo llvm-cov` cannot see them. TARGET/rust/component/src/lib.rs keeps a
  host-testable core plus a `WireTask` mirror struct and a `From<Wire> for
  Native` conversion, with **only** the thin `Guest` impl inside
  `#[cfg(target_arch = "wasm32")] mod wasm`. Do the same for product-listings
  (e.g. `WireProduct` → native product): **all logic host-testable; only CABI
  glue in the wasm-only module.** Never leave business logic where host coverage
  can't reach it (this is how you actually hit 100%). `src/bindings.rs` is
  generated and gitignored.

### 8.4 .gitignore updates
The root `.gitignore` already covers `*.wasm`, `target/`, `bindings/`,
`transpiled/`, `.task/`, caches. Update per-language ignores for the new layout:
- `rust/.gitignore`: replace `component/task-component.wasm`,
  `component/target/`, `component/src/bindings.rs` with subdir-aware globs:
  `component/*.wasm`, `component/*/target/`, `component/*/target-local/`,
  `component/*/src/bindings.rs`.
- `python/.gitignore`: change `component/bindings/` → `component/*/bindings/`.
- `javascript/.gitignore`: `*.wasm` already covered; add `component/*/node_modules/`
  if per-world `package.json`s are used.

---

## 9. The functional spec (embed — do not guess)

### 9.1 `list-matching-products` (Tier A — both library & component)
```
normalise(s)         = " ".join(s.split())            # collapse \t\n\r + repeated spaces, trim
match(name, phrase)  = phrase.casefold() in normalise(name).casefold()
resolve(base, href)  = urljoin(base, href)            # absolute href passes through unchanged
output.name          = normalise(raw_text)
output.url           = resolve(base_url, href)
order                = document order
```
Component parser only needs the hand-crafted shape:
```html
<a class="product-stamp" href="..."><span class="product-stamp-name">NAME</span></a>
```
The 5 contract cases: mixed page (3 of 4 match), empty page → `[]`, no matches →
`[]`, already-absolute URL unchanged, different phrase. (See the `.test.json`.)

### 9.2 `parse-search-results` (Tier B — library only)
Returns `{site, source_url, next_page_url, products[]}` where `products[]` items
are `{name, url}` plus optional `{price, club_price}` (each a `money`
`{amount, currency:"NZD"}`). Behaviour (reference SOURCE/python/.../search_parser/parser.py,
the most readable canonical version):
- **Site detection** by hostname (strip `www.`): `*.newworld.co.nz`/`ishopnewworld` →
  `new-world`; `*.paknsave.co.nz`/`paknsaveonline` → `paknsave`;
  `*.thewarehouse.co.nz` → `the-warehouse`;
  `*.woolworths.co.nz`/`countdown.co.nz`/`shop.countdown.co.nz` → `woolworths`.
  Unknown host → raise an `UnsupportedSite` error.
- **new-world / paknsave (Foodstuffs):** `schema.org/Product` cards + visible
  `/shop/product/` (or `/product/`) anchors; extract club/non-club prices from
  `data-testid` price decals; merge duplicates by canonical URL.
- **the-warehouse:** order from JSON-LD `ItemList` `itemListElement` URLs; names
  from visible `/p/` anchors (fall back to slug-derived name).
- **woolworths:** `/shop/productdetails` anchors, names via `aria-labelledby`
  `*-title` element (fall back to slug), **dedupe by canonical product URL**.
- **Matching** is token-subset on normalised `"name url"` text:
  `all(token in tokens(normalise("name url")) for token in tokens(normalise(phrase)))`
  where `normalise` lowercases and splits on non-alphanumeric runs. (This is why
  "grade 7 eggs" must NOT match "size 7" products — see the negative vectors.)
- **Canonical URL:** `urljoin` then drop the `tr` query param, drop fragment.
- **next_page_url:** first `<a rel="next">` resolved against `source_url`, else null.

> Reproduce this **exactly** — the 9 vectors assert specific ordering, dedup, and
> price extraction. When in doubt, read the SOURCE parser line by line.

### 9.3 provider-search URL templates (pure)
```
new-world     : https://www.newworld.co.nz/shop/search?pg=1&q={urlencode(term)}&sf=products
paknsave      : https://www.paknsave.co.nz/shop/search?pg=1&q={urlencode(term)}&sf=shopping
the-warehouse : https://www.thewarehouse.co.nz/search?q={plusEncode(term)}&lang=default
woolworths    : https://www.woolworths.co.nz/shop/searchproducts?search={urlencode(term)}
```
`plusEncode` = urlencode then `%20`→`+`. Page capture is **injected**; never
fetched in tests (G1).

---

## 10. CLI network-isolation design (Tier C, G1/G2)

The SOURCE CLI calls `urllib.request.urlopen` directly. Refactor so the network
is a pushed-to-the-edge, injectable dependency:

```python
def run(args, *, fetch=fetch_live, read_fixture=_default_fixture_reader):
    page = fetch(args.url) if args.live else read_fixture()
    products = parse_listings(page, args.match, BASE_URL)
    ...  # write JSON + TSV (pure formatting)
```
- Tests call `run(..., fetch=fake_fetch, read_fixture=fake_fixture)` — **no
  socket**. The `--live` branch is covered by asserting `fetch` was invoked, not
  by opening a connection.
- `fetch_live` itself stays a thin, **untested-by-network** wrapper; if 100%
  coverage requires touching it, exercise it via dependency injection / a stub
  transport, never a real request.
- Fix the stale default fixture path (`common/fixtures/woolworths/page.html`
  doesn't exist): point it to an existing fixture (decompress a
  `common/fixtures/search-parser/woolworths-size-7-eggs.html.gz` at runtime, or
  add a small committed plain-HTML fixture). Document the choice inline.

---

## 11. Definition of Done (final gate)

- [ ] `common/` holds the shopping WIT, product schema, both function contracts,
      and all 10 fixtures.
- [ ] `test-harness/run-wasm-tests.py` is multi-package + record-aware + skips
      world-less interfaces; its self-tests pass.
- [ ] All three languages: both `{lang}/component/{task-component,product-listings-component}.wasm`
      built against the shared `common/wit`, both worlds black-box-pass and are
      interchangeable across implementations.
- [ ] All three languages: Tier-B parsers pass all 9 `parse-search-results`
      vectors natively & offline; provider-search URL builders covered.
- [ ] Python CLI works offline via injection; `--live` path covered without network.
- [ ] Design docs present.
- [ ] `just setup/test/coverage/wasm-test/check-runners` all green; 100% coverage
      enforced; reproducible after `just clean`; no network used.
- [ ] This plan's checkboxes all ticked; deviations reported. **Not committed.**

---

## 12. Appendix — quick command reference

```bash
# Per sub-repo lifecycle (run inside the sub-repo via its nix shell)
cd python      && nix develop --command task test
cd javascript  && nix develop --command task coverage
cd rust        && nix develop --command task build

# Root orchestration (both runners must agree — G7)
just setup | just test | just coverage | just wasm-test | just check-runners
task setup | task test | task coverage | task wasm:test | task check:runners

# Validate all common/ JSON
python -c 'import json,glob;[json.load(open(f)) for f in glob.glob("common/**/*.json",recursive=True)]'
```

**Build order is load-bearing:** components must be **built** before `wasm-test`
(the harness only loads existing `.wasm`). The per-language `test`/`coverage`
tasks already `deps: [build]`; the root `wasm-test` assumes a prior `task test`/
`build` produced the artifacts.

---

## 13. Master checklist (single page — copy & tick as you go)

> This mirrors the phase checklists above in one flat list. Tick here for a
> quick at-a-glance status; the per-phase sections hold the detail.

**Phase 0 — Prep**
- [ ] Feature branch created
- [ ] Baseline green (recorded in §14)
- [ ] `constitution.md` tracked
- [ ] No SOURCE scratch leaked in

**Phase 1 — common/ contracts & fixtures**
- [ ] `shopping.wit` + `product-schema.json` copied
- [ ] `product-listings` schema + test JSON copied
- [ ] `product-search` schema + test JSON copied
- [ ] 10 fixtures copied (binary)
- [ ] Every fixture path in test JSON resolves
- [ ] All `common/**` JSON valid

**Phase 2 — harness upgrade**
- [ ] RED self-test for multi-package discovery
- [ ] GREEN: package parsing + `worlds_for_interface` + `to_plain`
- [ ] World-less interface (`product-search`) → SKIP, not FAIL (with test)
- [ ] `count-tasks` still passes (backward compatible)

**Phase 3 — prepare component dirs for a 2nd world (keep green)**
- [ ] Python: extend `component/` to build both worlds (no move); 2 pytest invocations planned
- [ ] JavaScript: extend `component/` to build both worlds (no move)
- [ ] Rust: migrate flat crate into `component/task-component/`; runner `cd`s into it
- [ ] Per-language `.gitignore` updated for new outputs
- [ ] `just test` / `just wasm-test` / `just check-runners` still green

**Phase 4 — product-listings component (Tier A), per language**
- [ ] Python: pure parser → WIT export → e2e WASM (RED→GREEN×3), 100% cov
- [ ] JavaScript: same
- [ ] Rust: same (host-testable core + `WireProduct` + cfg(wasm32) glue)
- [ ] `just wasm-test` → 2 worlds passing across all 3 languages

**Phase 5 — Tier-B library (search-parser / woolworths / provider-search), per language**
- [ ] Python: all 9 `parse-search-results` vectors pass offline; 100% cov
- [ ] JavaScript: same (jsdom kept Node-only; core isomorphic); 100% cov
- [ ] Rust: same (domain types, explicit errors); 100% cov
- [ ] provider-search URL builders covered; capture injected (no network)

**Phase 6 — Tier-C CLI + docs**
- [ ] Python CLI network behind injected `fetch`; default fixture path fixed
- [ ] CLI test offline; `--live` branch covered via injection; 100% cov
- [ ] Design docs in `docs/` + `docs/README.md` provenance note

**Phase 7 — lifecycle wiring & parity**
- [ ] Component runners chain all 5 verbs across both worlds
- [ ] `{lang}` runners chain library + component (+ CLI for python)
- [ ] `just check-runners` clean (warnings OK; missing recipes / dep mismatch not OK)

**Phase 7.5 — container (conditional)**
- [ ] Run if lifecycle/Nix/container files changed, else marked N/A

**Phase 8 — full verification**
- [ ] `just setup` / `test` / `coverage` / `wasm-test` / `check-runners` all green
- [ ] Re-verified after `just clean` (reproducible)
- [ ] No network used
- [ ] Working tree free of generated/scratch files

**Phase 9 — wrap up**
- [ ] All boxes ticked; deviations noted in §14
- [ ] **Not committed / not pushed** (await maintainer)

---

## 14. Progress log & baseline notes (fill in while working)

**Baseline (Phase 0) — record before editing:**
```text
date/time:
just test:          <pass/fail + summary>
just coverage:      <pass/fail>
just wasm-test:     <pass/fail>
just check-runners: <pass/fail>
pre-existing failures (if any):
```

**Progress log (newest first):**
```text
YYYY-MM-DD HH:MM — Phase N — command / result / decision
```

**Deviations from this plan (with justification):**
```text
- (none yet)
```
</content>
</invoke>
