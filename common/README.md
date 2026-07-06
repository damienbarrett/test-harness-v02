# common/

Shared contract definitions. This directory has no awareness of the
implementations that depend on it.

## Structure

```
common/
  wit/                  WIT interface definitions
  entities/             JSON Schema for domain types
  schemas/              Shared JSON Schemas for repo conventions (e.g. the suite format itself)
  functions/            Function schemas and test fixtures
  fixtures/             File-backed test fixtures, one subdirectory per capability
```

## Naming convention

Test fixtures follow a convention that mirrors the WIT hierarchy:

```
functions/{interface}/{function}.test.json
functions/{interface}/{function}.schema.json
```

- **Directory name** = WIT interface name (kebab-case)
- **File stem** = WIT function name (kebab-case)

### Example

Given this WIT:

```wit
interface task-collections {
    count-tasks: func(tasks: list<task>) -> u32;
}
```

The corresponding files are:

```
functions/task-collections/count-tasks.test.json
functions/task-collections/count-tasks.schema.json
```

## Test fixture format

```json
{
  "function": "count-tasks",
  "tests": [
    {
      "description": "counts a list of tasks",
      "input": { "tasks": [{ "name": "Task 1" }] },
      "expected": 1
    }
  ]
}
```

- `function` names the function under test (kebab-case), and must equal
  the suite file's stem.
- Each test case has `description` (unique within the suite, non-empty),
  `input` (keyed by parameter name), and `expected` (the return value).
- An optional suite-level `targets` array restricts which execution
  targets a suite applies to -- see
  [`targets` execution metadata](#targets-execution-metadata) below.
- No implementation-specific metadata belongs here.

The format itself is a JSON Schema at
[`schemas/test-suite.schema.json`](schemas/test-suite.schema.json)
(draft 2020-12). Every `*.test.json` suite is validated against it.

## File-backed fixtures

A test input can pull its value from a file under `common/fixtures/`
instead of inlining it, by using a **fixture descriptor** anywhere inside
`input` (at any nesting depth, inside objects and arrays):

```json
{
  "description": "extracts products from a captured page",
  "input": {
    "html": {
      "$fixture": "common/fixtures/html-parser/newworld-search-eggs.html.gz",
      "compression": "gzip",
      "encoding": "utf-8"
    },
    "source-url": "https://example.test/products"
  },
  "expected": { "products": [] }
}
```

The harness (`test-harness`'s `harness.fixtures` module -- the single
owner of this contract) replaces each descriptor with the decoded text
content of the file. Components receive pure data: decoded strings, never
file paths, and never the descriptor object itself.

### Descriptor fields

| Field | Required | Values | Notes |
| --- | --- | --- | --- |
| `$fixture` | yes | repo-root-relative POSIX path | must resolve under `common/fixtures/` |
| `compression` | no | `"gzip"` | no inference from file extension -- compression is applied only when declared |
| `encoding` | no | `"utf-8"` (default) | the only supported encoding |

Any dict containing a `$fixture` key is treated as a descriptor, and **any
other key in it is an error** -- a typo like `"compresion"` fails contract
validation instead of being silently ignored. Unsupported `compression` or
`encoding` values fail with a message naming the value and the supported
set.

### Directory convention

```
common/fixtures/{capability}/
```

One subdirectory per capability (e.g. `html-parser/`), with a `README.md`
recording each captured fixture's provenance (source, capture date, sizes).

### Path safety

- `$fixture` paths are resolved against the repository root.
- The fully-resolved real path (after following symlinks) must remain
  under the real path of `common/fixtures/`. Containment is checked on
  realpaths, never string prefixes.
- `..` traversal, absolute paths, and symlink escapes are all rejected
  with clear errors.

### Size limit

Both the on-disk file size and the decompressed size must stay within the
limit (the latter guards against gzip bombs; decompression is incremental
and aborts as soon as the limit is exceeded).

- Default: 8 MiB (8388608 bytes).
- Override: set the `HARNESS_FIXTURE_MAX_BYTES` environment variable to a
  positive integer number of bytes.

### Resolution order and errors

Fixtures are resolved **before** anything consumes the input:

- Contract validation (`check-contracts` / `contracts:check`) resolves
  every descriptor first and validates the **materialized** input against
  the function's parameter schema. Any resolution failure -- missing file,
  corrupt gzip, non-UTF-8 content, traversal/symlink escape, oversized
  file, unknown descriptor key, unsupported compression/encoding value --
  is a contract-validation error and fails the run before any component
  is invoked. Each failure mode has a distinct, actionable message naming
  the fixture.
- The WASM harness resolves the same descriptors (through the same
  module) before building call arguments, so the component under test
  receives the decoded file contents.

The full behavioral contract lives as a reusable conformance suite in
`test-harness/tests/fixture_conformance.py`; every consumer of the
descriptor format is tested against those same cases.

### Inline vs external HTML

- **Small HTML fragments belong inline** in the suite's `input`, where the
  case exercises one focused behavior and the markup is short enough to
  read in place.
- **Captured real-world pages belong under `common/fixtures/`** as
  external gzipped regression fixtures (`*.html.gz`), referenced via
  `$fixture` with `"compression": "gzip"`. Do not commit an uncompressed
  copy alongside the archive.

### Native fixture adapters

Native (non-WASM) language test runners do not get fixture support
automatically. Add a thin fixture adapter for a language **only when a
suite that language runs natively contains `$fixture` descriptors and
still needs to execute independently of the central harness** -- today no
native suite consumes fixtures (`count-tasks` takes a list of records, not
text), so no adapter exists. Any adapter added later must be tested
against the same conformance cases in
`test-harness/tests/fixture_conformance.py`, not a copied subset.

## `targets` execution metadata

An optional suite-level `targets` array declares which execution targets a
suite applies to:

```json
{ "function": "count-tasks", "targets": ["native", "component"], "tests": [ ... ] }
```

- **Absent** `targets` = no restriction: the suite runs everywhere it can
  (this is the normal case).
- If present it must be non-empty, without duplicates, and every entry
  must be `"native"` or `"component"`. An unknown target value is a
  contract-validation **error** (the schema's enum rejects it) -- never a
  skip.
- A suite whose `targets` exclude `"component"` is not run against WASM
  components: the harness prints an explicit
  `SKIP (declared native-only): <suite>` line and counts the suite as
  neither pass nor fail. Native-only execution is always this kind of
  visible declaration, never a silent omission.

## Schema `$id` and registry convention

Every schema file under `common/` (`entities/*.json`, `schemas/*.json`,
`functions/*/*.schema.json`) declares an `$id` equal to its own
repo-root-relative POSIX path, e.g.:

```json
{ "$id": "common/entities/task-schema.json" }
```

`test-harness`'s `harness.contracts` module scans these files and builds a
single deterministic [`referencing`](https://pypi.org/project/referencing/)
registry keyed by both each schema's `$id` and that same repo-relative
path, with the path also serving as the schema's base URI. This is what
lets a function schema's existing relative `$ref` (e.g.
`"../../entities/task-schema.json"` in `count-tasks.schema.json`) resolve
deterministically without any manual inlining or a separate list of
schemas to register by hand -- add a new schema file with a correct `$id`
and it is picked up automatically.

## Contract validation and WIT-as-authority

`test-harness/check-contracts.py` (wired into both lifecycle runners as
`check-contracts` / `contracts:check`) validates every suite under
`common/functions/` before any component is built or invoked:

- the suite file against `schemas/test-suite.schema.json`;
- its `function` against the filename stem, and its interface (parent
  directory name) against a WIT world's exports;
- each case's `input`/`expected` against the function schema's
  `parameters`/`returns` -- with every `$fixture` descriptor in `input`
  fully resolved first (read, decompressed, decoded, size- and
  path-checked), so it is the materialized input that is validated (see
  [File-backed fixtures](#file-backed-fixtures));
- WIT numeric bounds (e.g. a WIT `u32` return requires the function
  schema's `returns` to declare `minimum: 0` and `maximum: 4294967295` --
  never looser);
- WIT-vs-JSON-Schema record conformance.

For that last check, and in general: **WIT is authoritative.** A WIT
`record` (declared once under `common/wit/`) is the source of truth for a
domain entity's shape. A JSON Schema entity file under `common/entities/`
exists only to mirror that shape for JSON-Schema-based tooling; if the two
disagree, the WIT declaration wins and the entity schema is what must
change. `harness.contracts`'s record-conformance check exists to catch
that mirror drifting, not to introduce a second, independent source of
truth.
